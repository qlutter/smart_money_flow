#!/usr/bin/env python3
"""
Smart Money Distribution Scanner — Main Entry Point

Pipeline:
  1. ticker.txt 읽기
  2. 종목별 데이터 수집 (Yahoo Finance)
  3. 4개 분석 엔진 병렬 실행
  4. Composite Risk Score 산출
  5. Telegram 알림 발송
  6. 결과 JSON 저장
"""
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

import config
from core import (
    DataFetcher,
    ValuationAnalyzer,
    TechnicalAnalyzer,
    VPINCalculator,
    WyckoffDetector,
    CompositeScorer,
)
from notifier import TelegramNotifier

# ──────────────────────────────────────────────
# Logging
# ──────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("scanner")


def load_tickers() -> list[str]:
    """ticker.txt에서 종목 리스트 로드"""
    path = config.TICKER_FILE
    if not path.exists():
        logger.error(f"ticker.txt 없음: {path}")
        sys.exit(1)

    tickers = []
    with open(path) as f:
        for line in f:
            t = line.strip()
            if t and not t.startswith("#"):
                tickers.append(t)

    logger.info(f"총 {len(tickers)}개 종목 로드: {tickers}")
    return tickers


def run_scan():
    """메인 스캔 파이프라인 실행"""
    start = datetime.now()
    logger.info("=" * 50)
    logger.info("🔍 Smart Money Distribution Scanner 시작")
    logger.info("=" * 50)

    # 1. 종목 로드
    tickers = load_tickers()

    # 2. 엔진 초기화
    fetcher = DataFetcher()
    val_analyzer = ValuationAnalyzer()
    tech_analyzer = TechnicalAnalyzer()
    vpin_calc = VPINCalculator()
    wyckoff_det = WyckoffDetector()
    scorer = CompositeScorer()
    notifier = TelegramNotifier()

    # 3. 종목별 분석
    results = []
    for ticker_data in fetcher.fetch_all(tickers):
        ticker = ticker_data.ticker

        if ticker_data.error:
            logger.warning(f"[{ticker}] 스킵: {ticker_data.error}")
            continue

        logger.info(f"\n{'─' * 40}")
        logger.info(f"[{ticker}] 분석 시작")

        # ── 4개 엔진 실행 ──

        # (a) Valuation
        val_result = val_analyzer.analyze(
            ticker_data.ev_ebitda,
            ticker_data.sector,
        )

        # (b) Technical
        tech_result = tech_analyzer.analyze(ticker_data.daily_df)

        # (c) VPIN
        vpin_result = vpin_calc.calculate(ticker_data.intraday_df)

        # (d) Wyckoff
        wyckoff_result = wyckoff_det.detect(ticker_data.daily_df)

        # ── Composite Score ──
        composite = scorer.score(
            ticker=ticker,
            name=ticker_data.name,
            valuation=val_result,
            technical=tech_result,
            vpin=vpin_result,
            wyckoff=wyckoff_result,
        )
        results.append(composite)

    # 4. 결과 정렬 (위험도 높은 순)
    results.sort(key=lambda r: r.crs, reverse=True)

    # 5. 콘솔 출력
    logger.info(f"\n{'=' * 50}")
    logger.info("📊 스캔 결과 요약")
    logger.info(f"{'=' * 50}")
    for r in results:
        print(r.to_summary())
        print()

    # 6. Telegram 발송
    if results:
        notifier.send_scan_report(results)

    # 7. JSON 저장
    save_results(results)

    elapsed = (datetime.now() - start).total_seconds()
    logger.info(f"✅ 스캔 완료: {len(results)}종목, {elapsed:.1f}초 소요")


def save_results(results: list):
    """스캔 결과를 JSON으로 저장"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = config.RESULTS_DIR / f"scan_{timestamp}.json"

    data = []
    for r in results:
        data.append({
            "ticker": r.ticker,
            "name": r.name,
            "crs": r.crs,
            "risk_level": r.risk_level,
            "valuation": {
                "ev_ebitda": r.valuation.ev_ebitda,
                "sector": r.valuation.sector,
                "z_score": r.valuation.z_score,
                "score": r.valuation.score,
            },
            "technical": {
                "rsi": r.technical.rsi,
                "bearish_divergence": r.technical.bearish_divergence,
                "bollinger_pct_b": r.technical.bollinger_pct_b,
                "score": r.technical.score,
            },
            "vpin": {
                "vpin": r.vpin.vpin,
                "toxicity_level": r.vpin.toxicity_level,
                "sustained_toxic_bars": r.vpin.sustained_toxic_bars,
                "score": r.vpin.score,
            },
            "wyckoff": {
                "phase": r.wyckoff.phase.value,
                "events": r.wyckoff.events_detected,
                "score": r.wyckoff.score,
            },
            "timestamp": timestamp,
        })

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    logger.info(f"결과 저장: {output_path}")


if __name__ == "__main__":
    run_scan()
