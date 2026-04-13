"""
Telegram 알림 모듈
스캔 결과를 Telegram Bot API로 전송
"""
import logging
from datetime import datetime

import requests

import config

logger = logging.getLogger(__name__)


class TelegramNotifier:
    """Telegram Bot을 통한 알림 발송"""

    API_URL = "https://api.telegram.org/bot{token}/sendMessage"

    def __init__(self):
        self.token = config.TELEGRAM_BOT_TOKEN
        self.chat_id = config.TELEGRAM_CHAT_ID
        self.enabled = bool(self.token and self.chat_id)

        if not self.enabled:
            logger.warning(
                "Telegram 비활성화: TELEGRAM_BOT_TOKEN 또는 "
                "TELEGRAM_CHAT_ID가 설정되지 않았습니다."
            )

    def send_scan_report(self, results: list) -> bool:
        """
        전체 스캔 결과를 하나의 메시지로 전송.

        Parameters:
            results: list[CompositeResult]
        """
        if not self.enabled:
            logger.info("Telegram 비활성화 → 콘솔 출력만 수행")
            return False

        now = datetime.now().strftime("%Y-%m-%d %H:%M")

        # 위험도별 분류
        extreme = [r for r in results if r.risk_level == "EXTREME"]
        elevated = [r for r in results if r.risk_level == "ELEVATED"]
        normal = [r for r in results if r.risk_level == "NORMAL"]

        lines = []

        # 헤더
        if extreme:
            lines.append(f"🚨 Distribution Alert — {now}")
        else:
            lines.append(f"📋 Scan Report — {now}")

        lines.append("")

        # EXTREME 종목
        for r in extreme:
            lines.append(r.to_summary())
            lines.append("")

        # ELEVATED 종목
        for r in elevated:
            lines.append(r.to_summary())
            lines.append("")

        # NORMAL 종목 (티커만)
        if normal:
            tickers = ", ".join(r.ticker for r in normal)
            lines.append(f"✅ 정상: {tickers}")

        # 푸터
        lines.append("")
        lines.append(f"📊 총 {len(results)}종목 스캔 완료")

        message = "\n".join(lines)

        return self._send(message)

    def send_alert(self, result) -> bool:
        """단일 종목 긴급 알림"""
        if not self.enabled:
            return False

        message = (
            f"🚨 EXTREME ALERT\n\n"
            f"{result.to_summary()}\n\n"
            f"⏰ {datetime.now().strftime('%H:%M:%S')}"
        )
        return self._send(message)

    def _send(self, text: str) -> bool:
        """Telegram API 호출"""
        try:
            url = self.API_URL.format(token=self.token)
            payload = {
                "chat_id": self.chat_id,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            }
            resp = requests.post(url, json=payload, timeout=10)

            if resp.status_code == 200:
                logger.info("Telegram 전송 성공")
                return True
            else:
                logger.error(
                    f"Telegram 전송 실패: {resp.status_code} {resp.text}"
                )
                return False

        except Exception as e:
            logger.error(f"Telegram 전송 오류: {e}")
            return False


# ──────────────────────────────────────────────
# Notifier init
# ──────────────────────────────────────────────
__all__ = ["TelegramNotifier"]
