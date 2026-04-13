"""
Composite Risk Score (CRS) 모듈
개별 시그널을 가중 합산하여 단일 분배 위험 점수 산출

CRS = w₁·Valuation + w₂·Technical + w₃·VPIN + w₄·Wyckoff
"""
import logging
from dataclasses import dataclass

from .valuation import ValuationResult
from .technical import TechnicalResult
from .vpin import VPINResult
from .wyckoff import WyckoffResult
import config

logger = logging.getLogger(__name__)


@dataclass
class CompositeResult:
    """종합 분석 결과"""
    ticker: str
    name: str
    crs: float                     # 0~100 종합 위험 점수
    risk_level: str                # "NORMAL" / "ELEVATED" / "EXTREME"
    valuation: ValuationResult
    technical: TechnicalResult
    vpin: VPINResult
    wyckoff: WyckoffResult

    def to_summary(self) -> str:
        """텔레그램 메시지용 요약 문자열"""
        emoji = {"EXTREME": "🔴", "ELEVATED": "🟡", "NORMAL": "🟢"}.get(
            self.risk_level, "⚪"
        )

        lines = [
            f"{emoji} {self.ticker} | CRS: {self.crs:.0f}/100 | {self.risk_level}",
            f"{'━' * 32}",
        ]

        # Valuation
        if self.valuation.ev_ebitda is not None:
            lines.append(
                f"📊 EV/EBITDA: {self.valuation.ev_ebitda:.1f}x "
                f"(섹터 Z: {self.valuation.z_score:+.1f}σ)"
            )
        else:
            lines.append("📊 EV/EBITDA: N/A")

        # Technical
        div_flag = " | Bearish Div 감지 ⚠" if self.technical.bearish_divergence else ""
        lines.append(
            f"📈 RSI({config.RSI_PERIOD}): {self.technical.rsi:.1f}{div_flag}"
        )

        # VPIN
        if self.vpin.vpin is not None:
            lines.append(
                f"📉 VPIN: {self.vpin.vpin:.2f} ({self.vpin.toxicity_level})"
            )
        else:
            lines.append("📉 VPIN: N/A")

        # Wyckoff
        lines.append(
            f"🏗 Wyckoff: {self.wyckoff.phase.value}"
        )

        # Bollinger
        if self.technical.bollinger_pct_b > 1.0:
            lines.append(
                f"⚠️ 볼린저 %B: {self.technical.bollinger_pct_b:.2f} (상단 이탈)"
            )

        return "\n".join(lines)


class CompositeScorer:
    """종합 위험 점수 계산기"""

    def score(
        self,
        ticker: str,
        name: str,
        valuation: ValuationResult,
        technical: TechnicalResult,
        vpin: VPINResult,
        wyckoff: WyckoffResult,
    ) -> CompositeResult:
        """
        CRS = Σ(weight_i × score_i)

        각 모듈의 score는 이미 0~100으로 정규화되어 있음.
        가중 합산 후 최종 0~100 점수 산출.
        """
        w = config.CRS_WEIGHTS

        crs = (
            w["valuation"] * valuation.score
            + w["technical"] * technical.score
            + w["vpin"] * vpin.score
            + w["wyckoff"] * wyckoff.score
        )
        crs = max(0.0, min(100.0, crs))

        if crs >= config.ALERT_THRESHOLD_EXTREME:
            level = "EXTREME"
        elif crs >= config.ALERT_THRESHOLD_ELEVATED:
            level = "ELEVATED"
        else:
            level = "NORMAL"

        logger.info(
            f"[{ticker}] CRS={crs:.0f} ({level}) | "
            f"Val={valuation.score:.0f} Tech={technical.score:.0f} "
            f"VPIN={vpin.score:.0f} Wyckoff={wyckoff.score:.0f}"
        )

        return CompositeResult(
            ticker=ticker,
            name=name,
            crs=round(crs, 1),
            risk_level=level,
            valuation=valuation,
            technical=technical,
            vpin=vpin,
            wyckoff=wyckoff,
        )
