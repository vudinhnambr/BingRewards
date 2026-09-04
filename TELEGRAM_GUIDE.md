# 📱 Hướng Dẫn Thiết Lập Chạy Bot Trên Cloud & Báo Về Telegram

Hệ thống này giúp bạn **chạy tự động hoàn toàn trên GitHub Actions (Cloud 24/7)**, không cần bật máy tính hay điện thoại. Mỗi khi cày điểm xong, bot sẽ gửi tin nhắn báo cáo kết quả về Telegram của bạn.

---

## BƯỚC 1: Tạo Telegram Bot để nhận thông báo (Mất 1 phút)

1. Mở ứng dụng **Telegram** trên điện thoại (hoặc máy tính).
2. Tìm kiếm bot tên: **`@BotFather`** (có dấu tích xanh) ➔ Bấm **Start**.
3. Gửi lệnh: `/newbot`
4. Đặt tên cho bot của bạn (ví dụ: `Nam Bing Rewards Bot`).
5. Đặt username kết thúc bằng chữ `bot` (ví dụ: `nambingrewards_bot`).
6. BotFather sẽ gửi cho bạn một đoạn mã **API Token** (dạng `7123456789:AAH...`). Hãy copy lưu lại làm **`TELEGRAM_BOT_TOKEN`**.
7. Bấm vào link bot bạn vừa tạo và bấm **Start** một tin nhắn bất kỳ (để kích hoạt chat).

### Lấy Chat ID của bạn:
1. Trên Telegram, tìm kiếm bot: **`@userinfobot`** ➔ Bấm **Start**.
2. Bot sẽ trả về thông tin của bạn, copy dãy số tại dòng **`Id`** (ví dụ `123456789`) làm **`TELEGRAM_CHAT_ID`**.

---

## BƯỚC 2: Trích xuất Session tài khoản Microsoft

Nhấp đúp vào file:
```
export_session.bat
```
(hoặc chạy lệnh `python export_session.py` trong PowerShell).
- Màn hình sẽ hiển thị chuỗi mã hóa **`MICROSOFT_SESSION`** (chuỗi ký tự dài). Hãy copy chuỗi này.

---

## BƯỚC 3: Đưa dự án lên GitHub và cấu hình Secrets

1. Tạo một Repository mới trên GitHub (nên để chế độ **Private** để bảo mật session).
2. Đẩy toàn bộ mã nguồn của thư mục này lên GitHub Repo của bạn.
3. Trên trang GitHub Repo của bạn:
   - Vào **Settings** ➔ chọn **Secrets and variables** ➔ chọn **Actions**.
   - Bấm nút **New repository secret** và thêm 3 biến sau:

| Name (Tên biến) | Secret Value (Giá trị) |
| :--- | :--- |
| `MICROSOFT_SESSION` | Dán toàn bộ chuỗi dài copy từ Bước 2 |
| `TELEGRAM_BOT_TOKEN` | Mã Token nhận từ @BotFather ở Bước 1 |
| `TELEGRAM_CHAT_ID` | Số ID nhận từ @userinfobot ở Bước 1 |

---

## BƯỚC 4: Tận hưởng tự động hóa!

- **Lịch tự động**: GitHub Actions sẽ tự động kích hoạt bot vào lúc **07:45 sáng mỗi ngày (giờ VN)**.
- **Chạy thử ngay lập tức**:
  - Trên GitHub Repo, vào tab **Actions** ➔ chọn workflow **Bing Rewards Daily Automation** ở cột trái.
  - Bấm nút **Run workflow** ➔ chọn **Run workflow**.
- Sau khi chạy xong, điện thoại của bạn sẽ nhận được tin nhắn thông báo:
  ```
  🤖 BÁO CÁO MICROSOFT REWARDS HÀNG NGÀY
  💎 Điểm đầu ngày: 376
  🎯 Điểm sau khi chạy: 536 (+160 điểm)
  📊 Trạng thái: Thành công
  ⏰ Thời gian: 07:48:15 - 05/09/2026
  ```
