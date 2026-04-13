"""
데이터 수집 모듈
Yahoo Finance API를 통해 OHLCV + 재무 데이터 수집
"""
import logging
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd
import yfinance as yf

import config

logger = logging.getLogger(__name__)


@dataclass
class TickerData:
    """단일 종목의 수집된 데이터 컨테이너"""
    ticker: str
    daily_df: pd.DataFrame          # 일봉 OHLCV
    intraday_df: pd.DataFrame       # 분봉 OHLCV (VPIN용)
    info: dict = field(default_factory=dict)
    ev_ebitda: Optional[float] = None
    sector: str = "default"
    name: str = ""
    error: Optional[str] = None


class DataFetcher:
    """Yahoo Finance 기반 데이터 수집기"""

    def fetch(self, ticker: str) -> TickerData:
        """단일 종목 데이터 수집"""
        logger.info(f"[{ticker}] 데이터 수집 시작")

        try:
            stock = yf.Ticker(ticker)
            info = stock.info or {}

            # ── 일봉 데이터 ──
            daily_df = stock.history(
                period=f"{config.LOOKBACK_DAYS}d",
                auto_adjust=True,
            )
            if daily_df.empty:
                return TickerData(
                    ticker=ticker,
                    daily_df=pd.DataFrame(),
                    intraday_df=pd.DataFrame(),
                    error="일봉 데이터 없음",
                )

            # ── 분봉 데이터 (VPIN 계산용) ──
            intraday_df = stock.history(
                period=config.INTRADAY_PERIOD,
                interval=config.INTRADAY_INTERVAL,
                auto_adjust=True,
            )

            # ── EV/EBITDA 추출 ──
            ev = info.get("enterpriseValue")
            ebitda = info.get("ebitda")
            ev_ebitda = None
            if ev and ebitda and ebitda > 0:
                ev_ebitda = ev / ebitda

            sector = info.get("sector", "default")
            name = info.get("shortName", ticker)

            logger.info(
                f"[{ticker}] 수집 완료: "
                f"daily={len(daily_df)}봉, "
                f"intraday={len(intraday_df)}봉, "
                f"EV/EBITDA={ev_ebitda}"
            )

            return TickerData(
                ticker=ticker,
                daily_df=daily_df,
                intraday_df=intraday_df,
                info=info,
                ev_ebitda=ev_ebitda,
                sector=sector,
                name=name,
            )

        except Exception as e:
            logger.error(f"[{ticker}] 수집 실패: {e}")
            return TickerData(
                ticker=ticker,
                daily_df=pd.DataFrame(),
                intraday_df=pd.DataFrame(),
                error=str(e),
            )

    def fetch_all(self, tickers: list[str]) -> list[TickerData]:
        """전체 종목 리스트 수집"""
        results = []
        for t in tickers:
            results.append(self.fetch(t.strip()))
        return results
