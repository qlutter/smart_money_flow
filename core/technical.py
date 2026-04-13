"""
기술적 분석 모듈
RSI Divergence, Bollinger Band, 이격도 기반 과열 탐지
"""
import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd

import config

logger = logging.getLogger(__name__)


@dataclass
class TechnicalResult:
    """기술적 분석 결과"""
    rsi: float
    rsi_overbought: bool
    bearish_divergence: bool       # RSI Bearish Divergence 감지 여부
    divergence_strength: float     # Divergence 강도 (0~1)
    bollinger_pct_b: float         # %B 위치 (>1 = 상단 이탈)
    ma_disparity: dict             # 이동평균 이격도
    score: float                   # 0~100 종합 기술적 과열 점수


class TechnicalAnalyzer:
    """기술적 과열 지수 분석기"""

    def analyze(self, df: pd.DataFrame) -> TechnicalResult:
        """
        일봉 데이터로 기술적 과열 분석 수행.

        Components:
          1. RSI 과매수 (30점)
          2. Bearish RSI Divergence (30점)
          3. Bollinger %B (20점)
          4. 이동평균 이격도 (20점)
        """
        if df.empty or len(df) < config.BOLLINGER_PERIOD + 10:
            return TechnicalResult(
                rsi=50, rsi_overbought=False,
                bearish_divergence=False, divergence_strength=0,
                bollinger_pct_b=0.5, ma_disparity={}, score=0,
            )

        close = df["Close"].values
        high = df["High"].values

        # ── 1. RSI 계산 ──
        rsi = self._calc_rsi(close, config.RSI_PERIOD)
        current_rsi = rsi[-1]
        rsi_overbought = current_rsi >= config.RSI_OVERBOUGHT
        rsi_score = max(0, min(30, (current_rsi - 50) / 30 * 30))

        # ── 2. Bearish RSI Divergence ──
        bearish_div, div_strength = self._detect_bearish_divergence(
            high, rsi, config.DIVERGENCE_LOOKBACK
        )
        div_score = div_strength * 30  # 0~30

        # ── 3. Bollinger %B ──
        pct_b = self._calc_bollinger_pct_b(
            close, config.BOLLINGER_PERIOD, config.BOLLINGER_STD
        )
        # %B > 1.0 = 상단 이탈, 점수 증가
        bb_score = max(0, min(20, (pct_b - 0.5) * 40))

        # ── 4. 이동평균 이격도 ──
        disparities = {}
        disp_score_total = 0
        for period in config.MA_PERIODS:
            if len(close) >= period:
                ma = np.mean(close[-period:])
                disp = ((close[-1] - ma) / ma) * 100
                disparities[f"MA{period}"] = round(disp, 2)
                # 이격도 10% 이상이면 최대 점수
                disp_score_total += max(0, min(1, disp / 10))

        ma_score = min(20, (disp_score_total / len(config.MA_PERIODS)) * 20)

        # ── 종합 점수 ──
        total = rsi_score + div_score + bb_score + ma_score
        total = max(0.0, min(100.0, total))

        logger.info(
            f"Technical: RSI={current_rsi:.1f}, "
            f"BearDiv={bearish_div}, "
            f"%B={pct_b:.2f}, score={total:.0f}"
        )

        return TechnicalResult(
            rsi=round(current_rsi, 1),
            rsi_overbought=rsi_overbought,
            bearish_divergence=bearish_div,
            divergence_strength=round(div_strength, 2),
            bollinger_pct_b=round(pct_b, 2),
            ma_disparity=disparities,
            score=round(total, 1),
        )

    # ─────────────────────────────────────────
    # 내부 계산 함수들
    # ─────────────────────────────────────────

    @staticmethod
    def _calc_rsi(close: np.ndarray, period: int) -> np.ndarray:
        """Wilder RSI 계산"""
        deltas = np.diff(close)
        gains = np.where(deltas > 0, deltas, 0.0)
        losses = np.where(deltas < 0, -deltas, 0.0)

        avg_gain = np.zeros_like(close)
        avg_loss = np.zeros_like(close)

        # 초기값: 단순 평균
        avg_gain[period] = np.mean(gains[:period])
        avg_loss[period] = np.mean(losses[:period])

        # Wilder smoothing
        for i in range(period + 1, len(close)):
            avg_gain[i] = (avg_gain[i - 1] * (period - 1) + gains[i - 1]) / period
            avg_loss[i] = (avg_loss[i - 1] * (period - 1) + losses[i - 1]) / period

        rs = np.divide(
            avg_gain, avg_loss,
            out=np.full_like(avg_gain, 100.0),
            where=avg_loss != 0,
        )
        rsi = 100.0 - 100.0 / (1.0 + rs)
        rsi[:period] = 50.0  # warmup 구간
        return rsi

    @staticmethod
    def _detect_bearish_divergence(
        high: np.ndarray,
        rsi: np.ndarray,
        lookback: int,
    ) -> tuple[bool, float]:
        """
        Bearish RSI Divergence 탐지.

        조건: 가격은 Higher High인데 RSI는 Lower High
        → 모멘텀 약화 = 잠재적 반전 시그널

        Returns: (detected: bool, strength: 0~1)
        """
        if len(high) < lookback * 2:
            return False, 0.0

        # 최근 구간과 이전 구간의 피벗 하이 비교
        recent = slice(-lookback, None)
        prev = slice(-lookback * 2, -lookback)

        recent_high_idx = np.argmax(high[recent]) + (len(high) - lookback)
        prev_high_idx = np.argmax(high[prev]) + (len(high) - lookback * 2)

        price_higher = high[recent_high_idx] > high[prev_high_idx]
        rsi_lower = rsi[recent_high_idx] < rsi[prev_high_idx]

        if price_higher and rsi_lower:
            # Divergence 강도: RSI 하락폭에 비례
            rsi_drop = rsi[prev_high_idx] - rsi[recent_high_idx]
            strength = min(1.0, rsi_drop / 20.0)  # 20pt 하락 = 최대 강도
            return True, strength

        return False, 0.0

    @staticmethod
    def _calc_bollinger_pct_b(
        close: np.ndarray,
        period: int,
        num_std: float,
    ) -> float:
        """
        Bollinger Band %B 계산.

        %B = (Price - Lower) / (Upper - Lower)
        %B > 1.0 → 상단 밴드 이탈 (과매수)
        %B < 0.0 → 하단 밴드 이탈 (과매도)
        """
        if len(close) < period:
            return 0.5

        recent = close[-period:]
        ma = np.mean(recent)
        std = np.std(recent, ddof=1)

        upper = ma + num_std * std
        lower = ma - num_std * std

        band_width = upper - lower
        if band_width == 0:
            return 0.5

        pct_b = (close[-1] - lower) / band_width
        return pct_b
