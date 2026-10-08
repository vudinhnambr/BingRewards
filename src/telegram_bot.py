import os
import html
import requests
from typing import Optional
from src.utils import log_info, log_warn, log_success, parse_pts

class TelegramNotifier:
    """Sends notifications to Telegram channel or direct chat."""

    def __init__(self, token: Optional[str] = None, chat_id: Optional[str] = None):
        # Ưu tiên: tham số truyền vào → env var → fallback đọc config.json
        self.token = token or os.environ.get("TELEGRAM_BOT_TOKEN")
        self.chat_id = chat_id or os.environ.get("TELEGRAM_CHAT_ID")
        # Chỉ load BotConfig từ disk khi cả env var đều thiếu (tránh đọc file thừa)
        if not self.token or not self.chat_id:
            try:
                from src.config import BotConfig
                cfg = BotConfig.load()
                self.token = self.token or getattr(cfg, "telegram_bot_token", None)
                self.chat_id = self.chat_id or getattr(cfg, "telegram_chat_id", None)
            except Exception:
                pass

    @property
    def is_configured(self) -> bool:
        return bool(self.token and self.chat_id)

    def send_message(self, message: str) -> bool:
        """Send formatted message via Telegram Bot API with fallback for parsing errors."""
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
            # Fallback if HTML tags caused parse error
            if "can't parse entities" in resp.text:
                payload.pop("parse_mode", None)
                # Strip simple html tags
                clean_text = message.replace("<b>", "").replace("</b>", "").replace("<i>", "").replace("</i>", "").replace("<code>", "").replace("</code>", "")
                payload["text"] = clean_text
                fallback_resp = requests.post(url, json=payload, timeout=10)
                if fallback_resp.status_code == 200:
                    log_success("Đã gửi thông báo về Telegram (chế độ plain-text fallback)!")
                    return True
            log_warn(f"Lỗi gửi Telegram ({resp.status_code}): {resp.text}")
        except Exception as e:
            log_warn(f"Không thể kết nối tới Telegram: {e}")
        return False

    def send_rewards_summary(self, start_pts: str, end_pts: str, status: str = "Thành công", account_label: str = ""):
        """Send standardized Rewards daily summary."""
        try:
            start_num = parse_pts(start_pts)
            end_num = parse_pts(end_pts)
            gained = end_num - start_num if end_num >= start_num else 0
            gained_str = f"+{gained}" if gained > 0 else f"{gained}"
        except Exception:
            gained_str = "N/A"

        safe_label = html.escape(str(account_label))
        safe_status = html.escape(str(status))
        safe_start = html.escape(str(start_pts))
        safe_end = html.escape(str(end_pts))

        acc_header = f"👤 <b>Tài khoản:</b> <code>{safe_label}</code>\n" if safe_label else ""
        msg = (
            f"🤖 <b>BÁO CÁO MICROSOFT REWARDS HÀNG NGÀY</b>\n\n"
            f"{acc_header}"
            f"💎 <b>Điểm đầu ngày:</b> <code>{safe_start}</code>\n"
            f"🎯 <b>Điểm sau khi chạy:</b> <code>{safe_end}</code> (<b>{gained_str} điểm</b>)\n"
            f"📊 <b>Trạng thái:</b> <code>{safe_status}</code>\n"
            f"⏰ <b>Thời gian:</b> <i>{get_current_time_str()}</i>\n\n"
            f"🚀 <i>Bot tự động cày điểm đã hoàn thành nhiệm vụ!</i>"
        )
        return self.send_message(msg)

    def send_grand_multi_account_summary(self, results: list):
        """Send a grand consolidated summary table of all accounts."""
        if not results:
            return False

        total_pts = 0
        total_gained = 0
        lines = []

        for r in results:
            acc = html.escape(str(r.get("account", "Account")))
            end_p = str(r.get("end_points", "0"))
            safe_end = html.escape(end_p)
            gained = r.get("gained", 0)
            streak = html.escape(str(r.get("streak", "0")))
            status = r.get("status", "Thành công")

            try:
                pts_num = int(str(end_p).replace(",", "").replace(".", ""))
                total_pts += pts_num
            except Exception:
                pass
            total_gained += gained

            status_icon = "✅" if status == "Thành công" else "⚠️"
            lines.append(f"{status_icon} <b>{acc}:</b> <code>{safe_end}</code> pts (<b>+{gained}</b>) | 🔥 {streak}d")

        accounts_text = "\n".join(lines)
        msg = (
            f"🏆 <b>TỔNG KẾT TẤT CẢ TÀI KHOẢN MICROSOFT REWARDS</b> 🏆\n\n"
            f"{accounts_text}\n"
            f"───────────────────────\n"
            f"💎 <b>TỔNG ĐIỂM:</b> <code>{total_pts:,}</code> pts\n"
            f"🚀 <b>Điểm cày hôm nay:</b> <code>+{total_gained:,}</code> pts\n"
            f"👥 <b>Số tài khoản:</b> {len(results)}\n"
            f"⏰ <b>Thời gian:</b> <i>{get_current_time_str()}</i>"
        )
        return self.send_message(msg)


def get_current_time_str() -> str:
    from datetime import datetime, timezone, timedelta
    vn_tz = timezone(timedelta(hours=7))
    return datetime.now(vn_tz).strftime("%H:%M:%S - %d/%m/%Y")
