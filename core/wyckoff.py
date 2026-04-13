"""
Wyckoff Distribution Phase 탐지 모듈

Wyckoff Distribution Phases (A~E):
  Phase A: 상승 추세 정지 (PSY → BC → AR → ST)
  Phase B: 분배 Trading Range (기관 매도 진행)
  Phase C: 테스트 (UT / UTAD - 불트랩)
  Phase D: 약세 확인 (SOW, LPSY)
  Phase E: Markdown 시작

참조:
  - Richard D. Wyckoff Method (StockCharts / Wyckoff Analytics)
  - AlphaExtract - Wyckoff Event Detection (TradingView)
"""
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Optional

import numpy as np
import pandas as pd

import config

logger = logging.getLogger(__name__)


class WyckoffPhase(Enum):
    NONE = "None"
    MARKUP = "Markup"          # 상승 중 (분배 아님)
    PHASE_A = "Phase A"        # 상승 정지, BC/AR 출현
    PHASE_B = "Phase B"        # Trading Range, 분배 진행
    PHASE_C = "Phase C"        # UT/UTAD (불트랩)
    PHASE_D = "Phase D"        # SOW/LPSY (약세 확인)
    PHASE_E = "Phase E"        # Markdown 진행


@dataclass
class WyckoffResult:
    """Wyckoff 분석 결과"""
    phase: WyckoffPhase
    events_detected: list[str]    # 탐지된 이벤트 목록
    tr_upper: Optional[float]     # Trading Range 상단
    tr_lower: Optional[float]     # Trading Range 하단
    volume_declining: bool        # 랠리 시 거래량 감소 여부
    score: float                  # 0~100 분배 위험 점수


class WyckoffDetector:
    """
    Wyckoff Distribution Phase 탐지기

    알고리즘:
      1. ZigZag으로 주요 피벗(고점/저점) 추출
      2. 가격-거래량 패턴으로 Wyckoff 이벤트 식별
      3. 이벤트 시퀀스로 현재 Phase 판정
      4. Phase → 분배 위험 점수 변환
    """

    def detect(self, df: pd.DataFrame) -> WyckoffResult:
        """일봉 데이터로 Wyckoff Distribution 탐지"""
        if df.empty or len(df) < config.WYCKOFF_TR_MIN_BARS * 2:
            return WyckoffResult(
                phase=WyckoffPhase.NONE,
                events_detected=[],
                tr_upper=None,
                tr_lower=None,
                volume_declining=False,
                score=0.0,
            )

        close = df["Close"].values
        high = df["High"].values
        low = df["Low"].values
        volume = df["Volume"].values

        events = []

        # ── 1. 최근 상승 추세 확인 ──
        lookback_trend = min(120, len(close) - 1)
        trend_start = close[-lookback_trend]
        trend_end = close[-1]
        uptrend = trend_end > trend_start * 1.15  # 15%+ 상승

        if not uptrend:
            return WyckoffResult(
                phase=WyckoffPhase.NONE,
                events_detected=["선행 상승 추세 미확인"],
                tr_upper=None,
                tr_lower=None,
                volume_declining=False,
                score=0.0,
            )

        # ── 2. Trading Range 경계 설정 ──
        tr_bars = min(60, len(close) // 2)
        recent_high = high[-tr_bars:]
        recent_low = low[-tr_bars:]
        recent_close = close[-tr_bars:]
        recent_vol = volume[-tr_bars:]

        tr_upper = np.max(recent_high)
        tr_lower = np.min(recent_low)
        tr_range = tr_upper - tr_lower

        if tr_range <= 0:
            return WyckoffResult(
                phase=WyckoffPhase.NONE,
                events_detected=[],
                tr_upper=None,
                tr_lower=None,
                volume_declining=False,
                score=0.0,
            )

        # ── 3. Wyckoff 이벤트 탐지 ──

        # PSY (Preliminary Supply): 상승 중 거래량 급증
        vol_mean = np.mean(volume[-tr_bars * 2 : -tr_bars]) if len(volume) > tr_bars * 2 else np.mean(recent_vol)
        early_vol_spikes = np.where(
            recent_vol[:tr_bars // 3] > vol_mean * config.WYCKOFF_VOLUME_RATIO
        )[0]
        if len(early_vol_spikes) > 0:
            events.append("PSY (Preliminary Supply)")

        # BC (Buying Climax): 최고점 부근 거래량 최대
        peak_idx = np.argmax(recent_high)
        peak_vol_zone = recent_vol[max(0, peak_idx - 2) : peak_idx + 3]
        if len(peak_vol_zone) > 0 and np.max(peak_vol_zone) > vol_mean * 1.8:
            events.append("BC (Buying Climax)")

        # AR (Automatic Reaction): BC 이후 급격한 하락
        if peak_idx < len(recent_close) - 3:
            post_peak_drop = (tr_upper - np.min(recent_low[peak_idx:])) / tr_range
            if post_peak_drop > 0.3:
                events.append("AR (Automatic Reaction)")

        # ST (Secondary Test): BC 부근 재테스트, 거래량 감소
        if peak_idx < len(recent_high) - 5:
            post_peak_highs = recent_high[peak_idx + 3 :]
            retest_zone = np.where(post_peak_highs > tr_upper * 0.97)[0]
            if len(retest_zone) > 0:
                retest_vol = recent_vol[peak_idx + 3 :][retest_zone[0]]
                if retest_vol < peak_vol_zone.max() * 0.7:
                    events.append("ST (Secondary Test)")

        # UT/UTAD (Upthrust After Distribution): 상단 돌파 후 복귀
        last_10_high = recent_high[-10:]
        last_10_close = recent_close[-10:]
        for i in range(len(last_10_high)):
            if last_10_high[i] > tr_upper and last_10_close[i] < tr_upper:
                events.append("UT/UTAD (Upthrust)")
                break

        # SOW (Sign of Weakness): 하단 이탈
        last_20_low = recent_low[-20:]
        for i in range(len(last_20_low)):
            if last_20_low[i] < tr_lower:
                events.append("SOW (Sign of Weakness)")
                break

        # LPSY (Last Point of Supply): 하단 재테스트, 약한 반등
        if "SOW (Sign of Weakness)" in events:
            last_5_high = recent_high[-5:]
            if np.max(last_5_high) < tr_upper * 0.95:
                events.append("LPSY (Last Point of Supply)")

        # Volume declining on rallies (분배 확인)
        half = len(recent_vol) // 2
        first_half_vol = np.mean(recent_vol[:half])
        second_half_vol = np.mean(recent_vol[half:])
        volume_declining = second_half_vol < first_half_vol * 0.8

        if volume_declining:
            events.append("랠리 시 거래량 감소")

        # ── 4. Phase 판정 ──
        phase = self._determine_phase(events)

        # ── 5. Score 변환 ──
        phase_scores = {
            WyckoffPhase.NONE: 0,
            WyckoffPhase.MARKUP: 5,
            WyckoffPhase.PHASE_A: 30,
            WyckoffPhase.PHASE_B: 50,
            WyckoffPhase.PHASE_C: 75,
            WyckoffPhase.PHASE_D: 90,
            WyckoffPhase.PHASE_E: 100,
        }
        base_score = phase_scores.get(phase, 0)

        # 이벤트 수에 따른 보너스
        event_bonus = min(15, len(events) * 3)
        score = min(100, base_score + event_bonus)

        logger.info(
            f"Wyckoff: {phase.value}, "
            f"events={len(events)}, score={score:.0f}"
        )

        return WyckoffResult(
            phase=phase,
            events_detected=events,
            tr_upper=round(tr_upper, 2) if tr_upper else None,
            tr_lower=round(tr_lower, 2) if tr_lower else None,
            volume_declining=volume_declining,
            score=round(score, 1),
        )

    @staticmethod
    def _determine_phase(events: list[str]) -> WyckoffPhase:
        """탐지된 이벤트 시퀀스로 현재 Phase 추론"""
        e = set(events)

        if "LPSY (Last Point of Supply)" in e:
            return WyckoffPhase.PHASE_D
        if "SOW (Sign of Weakness)" in e:
            return WyckoffPhase.PHASE_D
        if "UT/UTAD (Upthrust)" in e:
            return WyckoffPhase.PHASE_C
        if "ST (Secondary Test)" in e:
            return WyckoffPhase.PHASE_B
        if "AR (Automatic Reaction)" in e:
            return WyckoffPhase.PHASE_A
        if "BC (Buying Climax)" in e:
            return WyckoffPhase.PHASE_A
        if "PSY (Preliminary Supply)" in e:
            return WyckoffPhase.PHASE_A

        return WyckoffPhase.NONE
