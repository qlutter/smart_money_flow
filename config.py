"""
Smart Money Distribution Scanner — Configuration
"""
import os
from pathlib import Path

# ──────────────────────────────────────────────
# Paths
# ──────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
TICKER_FILE = BASE_DIR / "data" / "ticker.txt"
RESULTS_DIR = BASE_DIR / "data" / "results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

# ──────────────────────────────────────────────
# Telegram
# ──────────────────────────────────────────────
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

# ──────────────────────────────────────────────
# Data Fetcher
# ──────────────────────────────────────────────
LOOKBACK_DAYS = 365          # 1년치 일봉
INTRADAY_PERIOD = "5d"       # 최근 5일 분봉 (VPIN용)
INTRADAY_INTERVAL = "5m"     # 5분봉

# ──────────────────────────────────────────────
# Valuation (EV/EBITDA)
# ──────────────────────────────────────────────
# 섹터 평균 EV/EBITDA (Yahoo Finance 기준, 정기 업데이트 필요)
SECTOR_EV_EBITDA_MEDIAN = {
    "Technology":        22.0,
    "Consumer Cyclical": 14.0,
    "Communication Services": 12.0,
    "Healthcare":        16.0,
    "Financial Services": 10.0,
    "Industrials":       13.0,
    "Consumer Defensive": 15.0,
    "Energy":             7.0,
    "Basic Materials":    9.0,
    "Real Estate":       18.0,
    "Utilities":         12.0,
    "default":           14.0,
}

SECTOR_EV_EBITDA_STD = {
    "Technology":        10.0,
    "Consumer Cyclical":  6.0,
    "Communication Services": 5.0,
    "Healthcare":         8.0,
    "Financial Services": 4.0,
    "Industrials":        5.0,
    "Consumer Defensive": 5.0,
    "Energy":             4.0,
    "Basic Materials":    4.0,
    "Real Estate":        7.0,
    "Utilities":          4.0,
    "default":            6.0,
}

# ──────────────────────────────────────────────
# Technical Indicators
# ──────────────────────────────────────────────
RSI_PERIOD = 14
RSI_OVERBOUGHT = 70
RSI_OVERSOLD = 30
BOLLINGER_PERIOD = 20
BOLLINGER_STD = 2.0
DIVERGENCE_LOOKBACK = 14     # RSI Divergence 피벗 탐색 범위
MA_PERIODS = [20, 60, 120]   # 이격도 계산용 이동평균

# ──────────────────────────────────────────────
# VPIN (Volume-Synchronized Probability of Informed Trading)
# ──────────────────────────────────────────────
VPIN_NUM_BUCKETS = 50         # 일평균 거래량을 50개 버킷으로 분할
VPIN_SAMPLE_LENGTH = 50       # VPIN 이동평균 윈도우
VPIN_TOXIC_THRESHOLD = 0.7    # 경고 수준
VPIN_CRITICAL_THRESHOLD = 0.85 # 위험 수준
VPIN_SUSTAINED_BARS = 8       # 연속 고독성 바 수

# ──────────────────────────────────────────────
# Wyckoff Phase Detection
# ──────────────────────────────────────────────
WYCKOFF_PIVOT_STRENGTH = 5    # 피벗 감지 민감도 (봉 수)
WYCKOFF_VOLUME_RATIO = 1.5   # 평균 대비 거래량 비율 임계값
WYCKOFF_TR_MIN_BARS = 20     # Trading Range 최소 봉 수

# ──────────────────────────────────────────────
# Composite Risk Score (CRS)
# ──────────────────────────────────────────────
CRS_WEIGHTS = {
    "valuation": 0.25,        # EV/EBITDA 프리미엄
    "technical": 0.25,        # RSI + Bollinger 과열
    "vpin":      0.25,        # 유동성 독성
    "wyckoff":   0.25,        # Wyckoff 분배 Phase
}

ALERT_THRESHOLD_EXTREME = 70   # 🔴 EXTREME: Telegram 즉시 알림
ALERT_THRESHOLD_ELEVATED = 50  # 🟡 ELEVATED: 주의 알림
ALERT_THRESHOLD_NORMAL = 30    # 🟢 NORMAL: 리포트만 기록
