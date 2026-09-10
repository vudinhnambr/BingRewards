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
- 📰 **MSN News Read to Earn**: Tự động đọc bài báo trên MSN để nhận bonus +30 điểm/ngày.
- 🔒 **Đăng nhập an toàn (Session Profile)**: Đăng nhập trực tiếp trên trình duyệt thật 1 lần duy nhất, tool tự động lưu cookie vào thư mục `browser_data/`, không cần lưu password dạng text.
- 🛡️ **Cơ chế chống bot / cooldown**: Tự động thay đổi độ trễ ngẫu nhiên giữa các lần tìm kiếm và tự động nghỉ giải lao sau mỗi batch tìm kiếm.
- 📊 **Giao diện CLI trực quan**: Hiển thị bảng tiến trình, thống kê điểm ban đầu và điểm sau khi hoàn thành.
- 📱 **Telegram Notification**: Gửi báo cáo kết quả về Telegram sau khi chạy xong.
- 📈 **HTML Dashboard**: Bảng tổng quan điểm thưởng với biểu đồ, lịch sử theo ngày.

---

## 🏗️ Kiến trúc code

```
BingRewards/
├── main.py                 # Entry point: CLI menu, multi-account runner
├── config.json             # Cấu hình (search count, delays, account labels)
├── run_local_all.bat       # [LOCAL] Chạy tuần tự tất cả account 1-6
├── export_session.py       # Xuất session cookie sang base64 cho GitHub Actions
├── src/
│   ├── config.py           # BotConfig dataclass (load/save config.json)
│   ├── browser.py          # BrowserManager: Playwright browser lifecycle
│   ├── searcher.py         # BingSearcher: thực hiện tìm kiếm trên Bing
│   ├── activities.py       # RewardsDashboard: giải nhiệm vụ Daily Set, Quiz, Poll
│   ├── msn_news.py         # MSNNewsReader: đọc bài báo MSN cho bonus
│   ├── word_generator.py   # Sinh từ khóa tìm kiếm (Google Trends + fallback)
│   ├── telegram_bot.py     # TelegramNotifier: gửi thông báo Telegram
│   ├── reporter.py         # AccountReporter: log history, generate HTML dashboard
│   └── utils.py            # Logging, random_delay, parse_pts utility
├── data/
│   └── accounts_history.json  # Lịch sử chạy (points, streak, status)
├── dashboard.html          # Dashboard tổng quan (auto-generated)
├── index.html              # Dashboard copy cho GitHub Pages
└── .github/workflows/
    └── rewards.yml         # GitHub Actions workflow (2 flows/ngày)
```

### Flow chạy chính (`run_full_bot`):

```
Phase 1: Desktop
  ├── Mở rewards dashboard → lấy điểm ban đầu
  ├── Daily Set & Activities (quizzes, polls, cards)
  └── Desktop Search (30 lượt)

Phase 2: Mobile
  ├── Mobile Dashboard check-in
  ├── Mobile Search (20 lượt)
  └── MSN News Read to Earn (10 bài)

Phase 3: Tổng kết
  ├── Lấy điểm sau khi chạy
  ├── Tính điểm kiếm được
  ├── Log vào history + generate dashboard
  └── Gửi Telegram notification
```

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

### Cách 1: Chạy local bằng file .bat (Đơn giản nhất)

1. Mở `run_local_all.bat` bằng Notepad
2. Thay `YOUR_TOKEN_HERE` bằng Telegram Bot Token (từ @BotFather)
3. Double-click `run_local_all.bat` → chạy tuần tự Account 1→6

### Cách 2: Giao diện Menu tương tác

```powershell
.\.venv\Scripts\python main.py
```

Tại menu, bạn có thể chọn:
- `[1]` Chạy toàn bộ nhiệm vụ (Daily Set + Desktop Search + Mobile Search)
- `[2]` Chỉ làm Daily Set & Activities
- `[3]` Chỉ tìm kiếm Desktop
- `[4]` Chỉ tìm kiếm Mobile
- `[5]` Đăng nhập / Đổi tài khoản (Desktop)
- `[6]` Đăng nhập tài khoản Mobile
- `[7]` Tùy chỉnh cấu hình
- `[8]` Mở Dashboard

### Cách 3: Chạy nhanh 1 lệnh

```powershell
# Chạy 1 account cụ thể
.\.venv\Scripts\python main.py --all --headless --account "Account 1"

# Chạy tất cả account
.\.venv\Scripts\python main.py --all --headless --account "All"

# Chạy có cửa sổ trình duyệt (debug)
.\.venv\Scripts\python main.py --all --account "Account 1"
```

---

## ⚙️ Cấu hình tùy chỉnh (`config.json`)

```json
{
  "headless": false,
  "browser_channel": "msedge",
  "run_daily_set": true,
  "run_more_activities": true,
  "run_desktop_search": true,
  "desktop_searches": 30,
  "run_mobile_search": true,
  "mobile_searches": 20,
  "min_delay_sec": 5.5,
  "max_delay_sec": 12.5,
  "fast_mode": false,
  "run_msn_news": true,
  "telegram_bot_token": "",
  "telegram_chat_id": "",
  "search_cooldown_batch_size": 5,
  "search_cooldown_wait_sec": 4.0,
  "account_labels": {
    "Account 1": "email1@gmail.com",
    "Account 2": "email2@gmail.com"
  }
}
```

| Config | Mô tả | Default |
|--------|--------|---------|
| `headless` | Chạy ẩn trình duyệt | `false` |
| `desktop_searches` | Số lượt tìm kiếm Desktop | `30` |
| `mobile_searches` | Số lượt tìm kiếm Mobile | `20` |
| `min_delay_sec` | Delay tối thiểu giữa searches (giây) | `5.5` |
| `max_delay_sec` | Delay tối đa giữa searches (giây) | `12.5` |
| `search_cooldown_batch_size` | Số search rồi nghỉ batch | `5` |
| `search_cooldown_wait_sec` | Thời gian nghỉ batch (giây) | `4.0` |
| `telegram_bot_token` | Token Telegram (ưu tiên env var) | `""` |
| `telegram_chat_id` | Chat ID Telegram (ưu tiên env var) | `""` |

---

## 🔐 Cấu hình Telegram

**Ưu tiên đọc token (theo thứ tự):**
1. Environment variable `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID`
2. Giá trị trong `config.json` (nếu có)

**Cách set env vars trên Windows (chạy local):**

```powershell
[System.Environment]::SetEnvironmentVariable("TELEGRAM_BOT_TOKEN", "TOKEN_TU_BOTFATHER", "User")
[System.Environment]::SetEnvironmentVariable("TELEGRAM_CHAT_ID", "1023253824", "User")
```

**Cách set trên GitHub Actions:**
Vào repo → Settings → Secrets and variables → Actions → New repository secret:
- `TELEGRAM_BOT_TOKEN`: Token từ @BotFather
- `TELEGRAM_CHAT_ID`: Chat ID của bạn

---

## 🔒 Bảo mật

- **Telegram Token**: Không hardcode trong code. Chỉ dùng env vars hoặc GitHub Secrets.
- **Session Cookies**: File `session.json` và `browser_data/` đã được gitignore.
- **User-Agent**: Cập nhật lên Chrome/Edge 140 (cập nhật mới nhất: September 2025).
- **Anti-detection**: Delay ngẫu nhiên `5.5~12.5s` giữa searches, cooldown batch mỗi 5 lượt.

---

## 📊 Kiểm tra tính chính xác của Dashboard

1. **So sánh trực tiếp**: Vào `https://rewards.bing.com/` trên trình duyệt thật, so sánh số điểm.
2. **Kiểm tra log**: Mỗi lần chạy hiện `Điểm ban đầu` và `Điểm sau khi chạy`.
3. **Kiểm tra history**: Mở `data/accounts_history.json` → mỗi entry có `start_points`, `end_points`, `gained`.

---

## 🐛 Troubleshooting

| Vấn đề | Nguyên nhân | Giải pháp |
|--------|-------------|-----------|
| Telegram 401 Unauthorized | Token cũ đã revoke | Tạo token mới qua @BotFather, update env var/secret |
| Điểm hiện tại N/A trong search | Selector Bing UI thay đổi |不影响 kết quả cuối (dashboard vẫn chính xác) |
| MSN News tìm thấy 0 bài | Selector MSN thay đổi | Đã fix: thử nhiều URL + scroll + fallback selectors |
| Browser bị treo | Context cũ không close | Đã fix: auto close context cũ trước khi tạo mới |
| Session expired | Cookie hết hạn | Chạy `python main.py --login` để đăng nhập lại |

---

## ⏰ GitHub Actions Schedule

Chạy 2 lần/ngày, mỗi lần 2 flows cách nhau 3 giờ:

| Flow | Thời gian (VN) | Accounts |
|------|----------------|----------|
| Flow 1 | 00:30 AM | Account 1, 2, 3 |
| Flow 2 | 03:30 AM | Account 4, 5, 6 |
| Flow 1 | 12:30 PM | Account 1, 2, 3 |
| Flow 2 | 15:30 PM | Account 4, 5, 6 |

---

## 📝 Changelog (Gần đây)

- **2025-09**: Fix context leak, update UA to Chrome140, deduplicate parse_pts
- **2025-09**: Remove hardcoded Telegram token, fix search delay offset
- **2025-09**: Improve Bing points detection (JS fallback), MSN News selectors
- **2025-09**: Add `run_local_all.bat` cho chạy local dễ dàng
