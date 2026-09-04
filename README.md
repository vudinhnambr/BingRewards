# 🤖 Bing Rewards Automation Bot (Microsoft Rewards)

Công cụ tự động hóa hoàn thành nhiệm vụ và kiếm điểm hàng ngày trên **Microsoft Rewards** (`https://rewards.bing.com/`) bằng Python & Playwright.

---

## ✨ Tính năng nổi bật

- 💻 **Desktop Search**: Tự động tìm kiếm các từ khóa phong phú trên Bing phiên bản máy tính.
- 📱 **Mobile Search**: Giả lập trình duyệt di động (Pixel / iPhone) để nhận điểm tìm kiếm Mobile.
- 🎯 **Daily Set & More Activities**: Tự động nhận diện và hoàn thành nhiệm vụ hàng ngày:
  - Khảo sát nhanh (Daily Polls)
  - Câu đố trắc nghiệm (Quizzes & Supersonic/Lightspeed Quiz)
  - Các thẻ thông tin, bài viết quảng bá (Cards & Activities)
- 🔒 **Đăng nhập an toàn (Session Profile)**: Đăng nhập trực tiếp trên trình duyệt thật 1 lần duy nhất, tool tự động lưu cookie vào thư mục `browser_data/`, không cần lưu password dạng text.
- 🛡️ **Cơ chế chống bot / cooldown**: Tự động thay đổi độ trễ ngẫu nhiên giữa các lần tìm kiếm và tự động nghỉ giải lao sau mỗi batch tìm kiếm.
- 📊 **Giao diện CLI trực quan**: Hiển thị bảng tiến trình, thống kê điểm ban đầu và điểm sau khi hoàn thành.

---

## 🛠️ Hướng dẫn cài đặt

### 1. Cài đặt môi trường ảo và thư viện

Mở PowerShell tại thư mục dự án:

```powershell
# Tạo môi trường ảo (nếu chưa có)
python -m venv .venv

# Kích hoạt môi trường ảo
.\.venv\Scripts\Activate.ps1

# Cài đặt thư viện
pip install -r requirements.txt

# Cài đặt trình duyệt Playwright (Chromium)
playwright install chromium
```

---

## 🚀 Hướng dẫn sử dụng

### Bước 1: Đăng nhập tài khoản Microsoft lần đầu

Chạy lệnh:
```powershell
.\.venv\Scripts\python main.py --login
```
1. Cửa sổ trình duyệt sẽ tự động mở trang `https://rewards.bing.com/`.
2. Bạn tiến hành đăng nhập tài khoản Microsoft của mình.
3. Sau khi thấy trang chủ Rewards đã hiển thị số điểm của bạn, quay lại cửa sổ dòng lệnh và nhấn **ENTER** để lưu session.

### Bước 2: Chạy bot làm nhiệm vụ

**Cách 1: Giao diện Menu tương tác**
```powershell
.\.venv\Scripts\python main.py
```
Tại menu, bạn có thể chọn:
- `[1]` Chạy toàn bộ nhiệm vụ (Daily Set + Desktop Search + Mobile Search)
- `[2]` Chỉ làm Daily Set & Activities
- `[3]` Chỉ tìm kiếm Desktop
- `[4]` Chỉ tìm kiếm Mobile
- `[7]` Tùy chỉnh số lượt tìm kiếm, bật/tắt chạy ẩn (headless)...

**Cách 2: Chạy nhanh 1 lệnh (Dùng để chạy ngầm hoặc lên lịch)**
```powershell
# Chạy toàn bộ ở chế độ ẩn (không hiện cửa sổ)
.\.venv\Scripts\python main.py --all --headless
```

---

## ⚙️ Cấu hình tùy chỉnh (`config.json`)

Bạn có thể chỉnh sửa trực tiếp file `config.json` hoặc qua menu:

```json
{
  "headless": false,
  "browser_channel": "msedge",
  "run_daily_set": true,
  "run_more_activities": true,
  "run_desktop_search": true,
  "desktop_searches": 35,
  "run_mobile_search": true,
  "mobile_searches": 25,
  "min_delay_sec": 6,
  "max_delay_sec": 12,
  "search_cooldown_batch_size": 4,
  "search_cooldown_wait_sec": 15
}
```

---

## ⏰ Lên lịch chạy tự động hàng ngày (Windows Task Scheduler)

Để tool tự động chạy vào mỗi buổi sáng mà không cần bạn bấm tay:

1. Mở **Task Scheduler** trên Windows (`Win + R` -> gõ `taskschd.msc`).
2. Chọn **Create Basic Task...**
3. Đặt tên: `Bing Rewards Auto Run`
4. Chọn Trigger: **Daily** (Hàng ngày lúc 08:00 AM).
5. Chọn Action: **Start a program**:
   - **Program/script**: `E:\BingRewards\BingRewards\.venv\Scripts\python.exe`
   - **Add arguments**: `main.py --all --headless`
   - **Start in**: `E:\BingRewards\BingRewards`
6. Nhấn **Finish**.
