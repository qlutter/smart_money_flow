"""
VPIN (Volume-Synchronized Probability of Informed Trading) 모듈

논문 기반:
  - Easley, López de Prado & O'Hara (2012)
    "Flow Toxicity and Liquidity in a High Frequency World"
    Review of Financial Studies, 25(5), 1457-1493.

  - Abad & Yagüe (2012)
    "From PIN to VPIN: An Introduction to Order Flow Toxicity"
    Spanish Review of Financial Economics.

핵심 개념:
  1. Volume Clock: 시간이 아닌 거래량 기준으로 데이터 샘플링
  2. Bulk Volume Classification (BVC): 바 단위로 매수/매도 볼륨 분류
  3. VPIN = Σ|V_buy - V_sell| / (n × VBS)
"""
import logging
from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd
from scipy.stats import norm

import config

logger = logging.getLogger(__name__)


@dataclass
class VPINResult:
    """VPIN 분석 결과"""
    vpin: Optional[float]           # 현재 VPIN 값 (0~1)
    toxicity_level: str             # "Low" / "Normal" / "Toxic" / "Critical"
    sustained_toxic_bars: int       # 연속 독성 바 수
    vpin_series: list[float]        # VPIN 시계열 (차트용)
    score: float                    # 0~100 정규화 점수


class VPINCalculator:
    """
    VPIN 계산 엔진

    Process:
      1. 분봉 데이터를 Volume Bucket으로 분할
      2. 각 버킷에서 Bulk Volume Classification(BVC)으로 매수/매도 분류
      3. 버킷 간 order imbalance 계산
      4. 이동평균으로 VPIN 산출
    """

    def calculate(self, df: pd.DataFrame) -> VPINResult:
        """
        분봉(intraday) 데이터로 VPIN 계산.

        Parameters:
            df: 분봉 OHLCV DataFrame (columns: Open, High, Low, Close, Volume)
        """
        if df.empty or len(df) < 20:
            logger.warning("VPIN 계산 불가: 데이터 부족")
            return VPINResult(
                vpin=None,
                toxicity_level="N/A",
                sustained_toxic_bars=0,
                vpin_series=[],
                score=0.0,
            )

        try:
            # ── Step 1: Volume Bucket Size (VBS) 결정 ──
            total_volume = df["Volume"].sum()
            num_bars = len(df)
            # VBS = 전체 거래량 / 목표 버킷 수
            vbs = total_volume / config.VPIN_NUM_BUCKETS
            if vbs <= 0:
                return self._empty_result("VBS가 0")

            # ── Step 2: Bulk Volume Classification (BVC) ──
            # 각 바의 종가 위치로 매수/매도 비율 추정
            # Z = (Close - Open) / (High - Low)를 정규분포 CDF로 변환
            buy_volumes, sell_volumes = self._bulk_volume_classify(df, vbs)

            if len(buy_volumes) < config.VPIN_SAMPLE_LENGTH:
                return self._empty_result("버킷 수 부족")

            # ── Step 3: Order Imbalance per Bucket ──
            imbalances = np.abs(
                np.array(buy_volumes) - np.array(sell_volumes)
            )

            # ── Step 4: VPIN = 이동평균(|OI|) / VBS ──
            n = config.VPIN_SAMPLE_LENGTH
            vpin_series = []
            for i in range(n, len(imbalances) + 1):
                window = imbalances[i - n : i]
                vpin_val = np.mean(window) / vbs if vbs > 0 else 0
                vpin_series.append(min(1.0, vpin_val))

            if not vpin_series:
                return self._empty_result("VPIN 시리즈 비어있음")

            current_vpin = vpin_series[-1]

            # ── Step 5: Toxicity Level 판정 ──
            if current_vpin >= config.VPIN_CRITICAL_THRESHOLD:
                level = "Critical"
            elif current_vpin >= config.VPIN_TOXIC_THRESHOLD:
                level = "Toxic"
            elif current_vpin >= 0.4:
                level = "Normal"
            else:
                level = "Low"

            # ── Step 6: 지속적 고독성 바 카운트 ──
            sustained = 0
            for v in reversed(vpin_series):
                if v >= config.VPIN_TOXIC_THRESHOLD:
                    sustained += 1
                else:
                    break

            # ── Score 변환 ──
            # VPIN 0~1 → Score 0~100 (비선형)
            if current_vpin >= config.VPIN_CRITICAL_THRESHOLD:
                score = 85 + (current_vpin - 0.85) * 100
            elif current_vpin >= config.VPIN_TOXIC_THRESHOLD:
                score = 60 + (current_vpin - 0.7) * 166
            elif current_vpin >= 0.4:
                score = 20 + (current_vpin - 0.4) * 133
            else:
                score = current_vpin * 50

            # 지속적 독성 보너스
            if sustained >= config.VPIN_SUSTAINED_BARS:
                score = min(100, score + 10)

            score = max(0, min(100, score))

            logger.info(
                f"VPIN: {current_vpin:.3f} ({level}), "
                f"sustained={sustained}, score={score:.0f}"
            )

            return VPINResult(
                vpin=round(current_vpin, 3),
                toxicity_level=level,
                sustained_toxic_bars=sustained,
                vpin_series=[round(v, 3) for v in vpin_series[-20:]],
                score=round(score, 1),
            )

        except Exception as e:
            logger.error(f"VPIN 계산 오류: {e}")
            return self._empty_result(str(e))

    def _bulk_volume_classify(
        self, df: pd.DataFrame, vbs: float
    ) -> tuple[list[float], list[float]]:
        """
        Bulk Volume Classification (BVC).

        각 바에서:
          Z = (Close - Open) / (High - Low)  (가격 범위 대비 종가 위치)
          V_buy = Volume × Φ(Z)              (정규분포 CDF)
          V_sell = Volume × (1 - Φ(Z))

        이를 Volume Bucket 단위로 누적 합산.
        """
        buy_buckets: list[float] = []
        sell_buckets: list[float] = []

        cum_buy = 0.0
        cum_sell = 0.0
        cum_vol = 0.0

        for _, row in df.iterrows():
            o, h, l, c, v = (
                row["Open"], row["High"], row["Low"], row["Close"], row["Volume"]
            )
            if v <= 0:
                continue

            spread = h - l
            if spread > 0:
                z = (c - o) / spread
            else:
                z = 0.0

            # 정규분포 CDF로 매수 비율 추정
            buy_pct = norm.cdf(z)
            bar_buy = v * buy_pct
            bar_sell = v * (1 - buy_pct)

            cum_buy += bar_buy
            cum_sell += bar_sell
            cum_vol += v

            # 버킷이 채워지면 분할
            while cum_vol >= vbs and vbs > 0:
                overflow = cum_vol - vbs
                ratio = (vbs / (vbs + overflow)) if (vbs + overflow) > 0 else 1

                buy_buckets.append(cum_buy * ratio)
                sell_buckets.append(cum_sell * ratio)

                cum_buy = cum_buy * (1 - ratio)
                cum_sell = cum_sell * (1 - ratio)
                cum_vol = overflow

        return buy_buckets, sell_buckets

    @staticmethod
    def _empty_result(reason: str) -> VPINResult:
        logger.warning(f"VPIN 빈 결과: {reason}")
        return VPINResult(
            vpin=None,
            toxicity_level="N/A",
            sustained_toxic_bars=0,
            vpin_series=[],
            score=0.0,
        )
