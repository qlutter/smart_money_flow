# 🔍 Smart Money Distribution Scanner

**EV/EBITDA × RSI Divergence × Wyckoff × VPIN → Telegram 알림**

GitHub Actions에서 스케줄 실행되어 `ticker.txt`의 종목을 스캔하고,
분배(Distribution) 시그널 감지 시 Telegram으로 알림을 보냅니다.

## 아키텍처

```
ticker.txt (종목 리스트)
    │
    ▼
┌─────────────────────────────────┐
│  GitHub Actions (cron: 매일 2회) │
│  ┌───────────────────────────┐  │
│  │  1. 데이터 수집            │  │
│  │     Yahoo Finance API     │  │
│  │     (OHLCV + 재무데이터)   │  │
│  ├───────────────────────────┤  │
│  │  2. 분석 엔진              │  │
│  │  ┌─────────┬────────────┐ │  │
│  │  │Valuation│ Technical  │ │  │
│  │  │EV/EBITDA│ RSI Div    │ │  │
│  │  │Z-Score  │ Bollinger  │ │  │
│  │  ├─────────┼────────────┤ │  │
│  │  │  VPIN   │  Wyckoff   │ │  │
│  │  │Flow Tox │ Phase Det  │ │  │
│  │  └─────────┴────────────┘ │  │
│  ├───────────────────────────┤  │
│  │  3. Composite Risk Score  │  │
│  │     CRS > 70 → ALERT     │  │
│  └───────────────────────────┘  │
└────────────┬────────────────────┘
             │
             ▼
     Telegram Bot 알림
     (위험 종목 리포트)
```

## 빠른 시작

### 1. Repository Secrets 설정

GitHub repo → Settings → Secrets and variables → Actions:

| Secret Name | 설명 |
|---|---|
| `TELEGRAM_BOT_TOKEN` | @BotFather에서 생성한 봇 토큰 |
| `TELEGRAM_CHAT_ID` | 알림 받을 채팅/채널 ID |

### 2. ticker.txt 편집

```
AAPL
TSLA
NVDA
005930.KS
000660.KS
```

한 줄에 하나의 티커. Yahoo Finance 형식 사용.
KRX 종목은 `종목코드.KS` (KOSPI) 또는 `종목코드.KQ` (KOSDAQ)

### 3. 수동 실행 테스트

GitHub Actions → "Smart Money Distribution Scanner" → Run workflow

### 4. 자동 실행

기본 설정: **매일 KST 08:30, 15:30** (장 전/후) 자동 실행

## 알림 예시

```
🚨 Distribution Alert — 2026-04-13

━━━━━━━━━━━━━━━━━━━━
🔴 TSLA | CRS: 82/100 | EXTREME
━━━━━━━━━━━━━━━━━━━━
📊 EV/EBITDA: 58.3x (섹터 Z: +2.4σ)
📈 RSI(14): 74.2 | Bearish Div 감지
📉 VPIN: 0.78 (Toxic Flow)
🏗 Wyckoff: Phase C (UTAD 의심)
⚠️ 볼린저 %B: 1.12 (상단 이탈)

━━━━━━━━━━━━━━━━━━━━
🟡 NVDA | CRS: 61/100 | ELEVATED
━━━━━━━━━━━━━━━━━━━━
📊 EV/EBITDA: 42.1x (섹터 Z: +1.8σ)
📈 RSI(14): 68.5 | Divergence 없음
📉 VPIN: 0.52 (Normal)
🏗 Wyckoff: Phase B (분배 진행 중)

━━━━━━━━━━━━━━━━━━━━
✅ 정상: AAPL, 005930.KS, 000660.KS
```

## 파일 구조

```
scanner/
├── .github/workflows/
│   └── scan.yml              # GitHub Actions 워크플로우
├── core/
│   ├── __init__.py
│   ├── data_fetcher.py       # Yahoo Finance 데이터 수집
│   ├── valuation.py          # EV/EBITDA 프리미엄 분석
│   ├── technical.py          # RSI, Bollinger, Divergence
│   ├── vpin.py               # VPIN 계산 엔진
│   ├── wyckoff.py            # Wyckoff Phase 탐지
│   └── composite_scorer.py   # CRS 종합 점수
├── notifier/
│   ├── __init__.py
│   └── telegram_bot.py       # Telegram 알림 발송
├── data/
│   └── ticker.txt            # 스캔 대상 종목 리스트
├── main.py                   # 엔트리포인트
├── config.py                 # 설정 관리
├── requirements.txt
└── README.md
```

## 커스터마이징

### CRS 가중치 조정
`config.py`에서:
```python
CRS_WEIGHTS = {
    "valuation": 0.25,    # EV/EBITDA 프리미엄
    "technical": 0.25,     # RSI + Bollinger
    "vpin": 0.25,          # 유동성 독성
    "wyckoff": 0.25,       # 분배 Phase
}
```

### 알림 임계값
```python
ALERT_THRESHOLD_EXTREME = 70   # 🔴 즉시 알림
ALERT_THRESHOLD_ELEVATED = 50  # 🟡 주의 알림
```

### 스캔 주기 변경
`.github/workflows/scan.yml`의 cron 표현식 수정

## 라이선스

MIT
