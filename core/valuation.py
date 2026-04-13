"""
밸류에이션 분석 모듈
EV/EBITDA 기반 과대평가 프리미엄 정량화
"""
import logging
from dataclasses import dataclass
from typing import Optional

import config

logger = logging.getLogger(__name__)


@dataclass
class ValuationResult:
    """밸류에이션 분석 결과"""
    ev_ebitda: Optional[float]
    sector: str
    sector_median: float
    sector_std: float
    z_score: Optional[float]       # 섹터 대비 표준화 점수
    percentile_label: str          # "Normal" / "Elevated" / "Extreme"
    score: float                   # 0~100 정규화 점수


class ValuationAnalyzer:
    """EV/EBITDA 프리미엄 분석기"""

    def analyze(self, ev_ebitda: Optional[float], sector: str) -> ValuationResult:
        """
        섹터 대비 EV/EBITDA Z-Score 계산.

        Z = (종목 EV/EBITDA - 섹터 중앙값) / 섹터 표준편차

        Z > 2.0 → Extreme (score 80~100)
        Z > 1.0 → Elevated (score 50~79)
        Z ≤ 1.0 → Normal (score 0~49)
        """
        median = config.SECTOR_EV_EBITDA_MEDIAN.get(
            sector, config.SECTOR_EV_EBITDA_MEDIAN["default"]
        )
        std = config.SECTOR_EV_EBITDA_STD.get(
            sector, config.SECTOR_EV_EBITDA_STD["default"]
        )

        if ev_ebitda is None or ev_ebitda <= 0:
            logger.warning(f"EV/EBITDA 데이터 없음 (sector={sector})")
            return ValuationResult(
                ev_ebitda=ev_ebitda,
                sector=sector,
                sector_median=median,
                sector_std=std,
                z_score=None,
                percentile_label="N/A",
                score=0.0,
            )

        z = (ev_ebitda - median) / std if std > 0 else 0.0

        # Z-Score → 0~100 점수 변환 (sigmoid-like mapping)
        if z >= 3.0:
            score = 100.0
            label = "Extreme"
        elif z >= 2.0:
            score = 80.0 + (z - 2.0) * 20.0  # 80~100
            label = "Extreme"
        elif z >= 1.0:
            score = 50.0 + (z - 1.0) * 30.0  # 50~80
            label = "Elevated"
        elif z >= 0:
            score = z * 50.0                   # 0~50
            label = "Normal"
        else:
            score = 0.0
            label = "Undervalued"

        score = max(0.0, min(100.0, score))

        logger.info(
            f"Valuation: EV/EBITDA={ev_ebitda:.1f}, "
            f"sector={sector}, Z={z:+.2f}, "
            f"score={score:.0f} ({label})"
        )

        return ValuationResult(
            ev_ebitda=ev_ebitda,
            sector=sector,
            sector_median=median,
            sector_std=std,
            z_score=round(z, 2),
            percentile_label=label,
            score=round(score, 1),
        )
