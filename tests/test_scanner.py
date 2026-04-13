"""
Scanner 테스트 모듈
pytest로 실행: pytest tests/
"""
import numpy as np
import pandas as pd


def _make_dummy_df(n=100):
    """테스트용 더미 OHLCV DataFrame 생성"""
    np.random.seed(42)
    close = 100 + np.cumsum(np.random.randn(n) * 2)
    return pd.DataFrame({
        "Open": close - np.random.rand(n),
        "High": close + np.abs(np.random.randn(n)),
        "Low": close - np.abs(np.random.randn(n)),
        "Close": close,
        "Volume": np.random.randint(1_000_000, 10_000_000, n),
    })


def test_rsi_range():
    """RSI 값이 0~100 범위인지 확인"""
    from core.technical import TechnicalAnalyzer
    df = _make_dummy_df(200)
    result = TechnicalAnalyzer().analyze(df)
    assert 0 <= result.rsi <= 100


def test_vpin_range():
    """VPIN 값이 0~1 범위인지 확인"""
    from core.vpin import VPINCalculator
    df = _make_dummy_df(500)
    result = VPINCalculator().calculate(df)
    if result.vpin is not None:
        assert 0 <= result.vpin <= 1


def test_valuation_z_score():
    """Valuation Z-Score 계산 검증"""
    from core.valuation import ValuationAnalyzer
    result = ValuationAnalyzer().analyze(40.0, "Technology")
    assert result.z_score is not None
    assert result.z_score > 0  # 40 > 22 (median)


def test_composite_score_range():
    """CRS가 0~100 범위인지 확인"""
    from core.valuation import ValuationResult
    from core.technical import TechnicalResult
    from core.vpin import VPINResult
    from core.wyckoff import WyckoffResult, WyckoffPhase
    from core.composite_scorer import CompositeScorer

    val = ValuationResult(30, "Tech", 22, 10, 0.8, "Normal", 40)
    tech = TechnicalResult(65, False, False, 0, 0.7, {}, 35)
    vpin = VPINResult(0.5, "Normal", 0, [], 30)
    wyckoff = WyckoffResult(WyckoffPhase.NONE, [], None, None, False, 0)

    result = CompositeScorer().score("TEST", "Test", val, tech, vpin, wyckoff)
    assert 0 <= result.crs <= 100
