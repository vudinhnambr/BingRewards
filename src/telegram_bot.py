import os
import requests
from typing import Optional
from src.utils import log_info, log_warn, log_success

class TelegramNotifier:
    """Sends notifications to Telegram channel or direct chat."""

    def __init__(self, token: Optional[str] = None, chat_id: Optional[str] = None):
        self.token = token or os.environ.get("TELEGRAM_BOT_TOKEN")
        self.chat_id = chat_id or os.environ.get("TELEGRAM_CHAT_ID")

    @property
    def is_configured(self) -> bool:
        return bool(self.token and self.chat_id)

    def send_message(self, message: str) -> bool:
        """Send formatted message via Telegram Bot API."""
        if not self.is_configured:
            return False

        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": True
        }

        try:
            resp = requests.post(url, json=payload, timeout=10)
            if resp.status_code == 200:
                log_success("Đã gửi thông báo kết quả về Telegram!")
                return True
            else:
                log_warn(f"Lỗi gửi Telegram ({resp.status_code}): {resp.text}")
        except Exception as e:
            log_warn(f"Không thể kết nối tới Telegram: {e}")
        return False

    def send_rewards_summary(self, start_pts: str, end_pts: str, status: str = "Thành công"):
        """Send standardized Rewards daily summary."""
        try:
            start_num = int(str(start_pts).replace(",", "").replace(".", "")) if str(start_pts).isdigit() else 0
            end_num = int(str(end_pts).replace(",", "").replace(".", "")) if str(end_pts).isdigit() else 0
            gained = end_num - start_num if end_num >= start_num else 0
            gained_str = f"+{gained}" if gained > 0 else f"{gained}"
        except Exception:
            gained_str = "N/A"

        msg = (
            f"🤖 <b>BÁO CÁO MICROSOFT REWARDS HÀNG NGÀY</b>\n\n"
            f"💎 <b>Điểm đầu ngày:</b> <code>{start_pts}</code>\n"
            f"🎯 <b>Điểm sau khi chạy:</b> <code>{end_pts}</code> (<b>{gained_str} điểm</b>)\n"
            f"📊 <b>Trạng thái:</b> <code>{status}</code>\n"
            f"⏰ <b>Thời gian:</b> <i>{get_current_time_str()}</i>\n\n"
            f"🚀 <i>Bot tự động cày điểm đã hoàn thành nhiệm vụ hôm nay!</i>"
        )
        return self.send_message(msg)


def get_current_time_str() -> str:
    from datetime import datetime, timezone, timedelta
    vn_tz = timezone(timedelta(hours=7))
    return datetime.now(vn_tz).strftime("%H:%M:%S - %d/%m/%Y")
