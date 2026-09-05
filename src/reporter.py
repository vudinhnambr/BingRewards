import json
import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
HISTORY_FILE = DATA_DIR / "accounts_history.json"
DASHBOARD_FILE = Path(__file__).resolve().parent.parent / "dashboard.html"
INDEX_FILE = Path(__file__).resolve().parent.parent / "index.html"

class AccountReporter:
    """Manages multi-account point tracking, history logging, and visual HTML dashboard generation."""

    @staticmethod
    def _init_data():
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        if not HISTORY_FILE.exists():
            with open(HISTORY_FILE, "w", encoding="utf-8") as f:
                json.dump([], f)

    @classmethod
    def load_history(cls) -> List[Dict[str, Any]]:
        cls._init_data()
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []

    @classmethod
    def sync_git(cls):
        """Auto commit & push updated dashboard & history to GitHub if git is available."""
        try:
            root_dir = Path(__file__).resolve().parent.parent
            subprocess.run(["git", "add", "data/accounts_history.json", "dashboard.html", "index.html"], cwd=root_dir, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.run(["git", "commit", "-m", "chore(stats): auto sync rewards dashboard [skip ci]"], cwd=root_dir, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.run(["git", "push", "origin", "main"], cwd=root_dir, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass

    @classmethod
    def log_account_run(cls, account_label: str, start_pts: Any, end_pts: Any, streak: Any = "0", status: str = "Thành công"):
        """Record account execution results to persistent history."""
        try:
            from src.config import BotConfig
            cfg = BotConfig.load()
            if cfg.account_labels and account_label in cfg.account_labels:
                account_label = cfg.account_labels[account_label]
        except Exception:
            pass

        history = cls.load_history()

        def parse_pts(val):
            try:
                if val == "N/A" or val is None:
                    return 0
                return int(str(val).replace(",", "").replace(".", "").strip())
            except Exception:
                return 0

        start_num = parse_pts(start_pts)
        end_num = parse_pts(end_pts)
        gained = max(0, end_num - start_num) if end_num > 0 and start_num > 0 else 0

        now_str = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        date_key = datetime.now().strftime("%d/%m/%Y")

        entry = {
            "account": account_label or "Account 1",
            "start_points": str(start_pts),
            "end_points": str(end_pts),
            "gained": gained,
            "streak": str(streak),
            "status": status,
            "timestamp": now_str,
            "date": date_key
        }

        history.append(entry)
        
        # Keep last 200 runs
        if len(history) > 200:
            history = history[-200:]

        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)

        cls.generate_html_dashboard()
        cls.sync_git()

    @classmethod
    def get_latest_summary(cls) -> Dict[str, Any]:
        """Aggregate latest point stats for all distinct accounts."""
        history = cls.load_history()
        accounts_map = {}

        # First populate from config.json to show all configured accounts immediately
        try:
            from src.config import BotConfig
            cfg = BotConfig.load()
            if cfg.account_labels:
                for label, name in cfg.account_labels.items():
                    accounts_map[name] = {
                        "account": name,
                        "start_points": "0",
                        "end_points": "0",
                        "gained": 0,
                        "streak": "0",
                        "status": "Chờ chạy",
                        "timestamp": "Chưa có lượt chạy",
                        "date": ""
                    }
        except Exception:
            pass

        for item in history:
            acc = item.get("account", "Account 1")
            accounts_map[acc] = item  # Latest entry overrides

        return accounts_map

    @classmethod
    def generate_html_dashboard(cls):
        """Generate a sleek, modern, mobile-first glassmorphism HTML dashboard."""
        history = cls.load_history()
        latest_accounts = cls.get_latest_summary()

        total_pts = 0
        total_gained_today = 0
        max_streak = 0

        today_str = datetime.now().strftime("%d/%m/%Y")

        for acc, data in latest_accounts.items():
            try:
                pts = int(str(data.get("end_points", "0")).replace(",", "").replace(".", ""))
                total_pts += pts
            except Exception:
                pass

            try:
                stk = int(str(data.get("streak", "0")))
                if stk > max_streak:
                    max_streak = stk
            except Exception:
                pass

        for item in history:
            if item.get("date") == today_str:
                total_gained_today += item.get("gained", 0)

        history_json = json.dumps(history, ensure_ascii=False)
        latest_json = json.dumps(latest_accounts, ensure_ascii=False)

        html_content = f"""<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Bảng Tổng Quan Microsoft Rewards</title>
    <!-- Fonts -->
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
    <!-- Chart.js -->
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        :root {{
            --bg-primary: #0b0f19;
            --bg-secondary: #111827;
            --card-bg: rgba(30, 41, 59, 0.7);
            --card-border: rgba(255, 255, 255, 0.08);
            --accent-cyan: #06b6d4;
            --accent-blue: #3b82f6;
            --accent-purple: #8b5cf6;
            --accent-green: #10b981;
            --accent-yellow: #f59e0b;
            --accent-red: #ef4444;
            --text-main: #f8fafc;
            --text-muted: #94a3b8;
        }}

        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
            font-family: 'Outfit', sans-serif;
            -webkit-tap-highlight-color: transparent;
        }}

        body {{
            background: radial-gradient(circle at top right, #1e1b4b 0%, #0b0f19 50%, #030712 100%);
            color: var(--text-main);
            min-height: 100vh;
            padding: 1rem 0.75rem 2rem;
        }}

        .container {{
            max-width: 1100px;
            margin: 0 auto;
        }}

        /* Header */
        .header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 0.75rem;
            margin-bottom: 1.25rem;
            padding-bottom: 1rem;
            border-bottom: 1px solid var(--card-border);
        }}

        .header-title h1 {{
            font-size: 1.35rem;
            font-weight: 800;
            background: linear-gradient(135deg, #38bdf8 0%, #818cf8 50%, #c084fc 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            display: flex;
            align-items: center;
            gap: 0.5rem;
            line-height: 1.2;
        }}

        .header-title p {{
            color: var(--text-muted);
            margin-top: 0.2rem;
            font-size: 0.8rem;
        }}

        .btn-refresh {{
            background: linear-gradient(135deg, var(--accent-blue), var(--accent-purple));
            color: white;
            border: none;
            padding: 0.5rem 0.9rem;
            border-radius: 0.6rem;
            font-weight: 600;
            font-size: 0.8rem;
            cursor: pointer;
            display: inline-flex;
            align-items: center;
            gap: 0.4rem;
            white-space: nowrap;
            box-shadow: 0 4px 12px rgba(59, 130, 246, 0.3);
            transition: all 0.2s;
        }}

        .btn-refresh:active {{
            transform: scale(0.96);
        }}

        /* Stats Grid (2x2 on Mobile, 4x1 on Desktop) */
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 0.65rem;
            margin-bottom: 1.25rem;
        }}

        @media (min-width: 768px) {{
            .stats-grid {{
                grid-template-columns: repeat(4, 1fr);
                gap: 1rem;
            }}
            body {{
                padding: 1.75rem 1.5rem 3rem;
            }}
            .header-title h1 {{
                font-size: 1.85rem;
            }}
            .header-title p {{
                font-size: 0.95rem;
            }}
        }}

        .stat-card {{
            background: var(--card-bg);
            border: 1px solid var(--card-border);
            backdrop-filter: blur(12px);
            border-radius: 0.85rem;
            padding: 0.9rem 1rem;
            position: relative;
            overflow: hidden;
        }}

        .stat-card::before {{
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 3px;
        }}

        .stat-card.c-blue::before {{ background: linear-gradient(90deg, #38bdf8, #3b82f6); }}
        .stat-card.c-green::before {{ background: linear-gradient(90deg, #34d399, #10b981); }}
        .stat-card.c-purple::before {{ background: linear-gradient(90deg, #a78bfa, #8b5cf6); }}
        .stat-card.c-yellow::before {{ background: linear-gradient(90deg, #fbbf24, #f59e0b); }}

        .stat-label {{
            color: var(--text-muted);
            font-size: 0.7rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.04em;
        }}

        .stat-value {{
            font-size: 1.45rem;
            font-weight: 800;
            margin: 0.35rem 0 0.15rem;
            letter-spacing: -0.02em;
        }}

        .stat-sub {{
            color: var(--text-muted);
            font-size: 0.72rem;
        }}

        /* Section Headings */
        .section-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 0.85rem;
            gap: 0.5rem;
        }}

        .section-title {{
            font-size: 1.1rem;
            font-weight: 700;
            display: flex;
            align-items: center;
            gap: 0.4rem;
        }}

        /* Accounts Grid */
        .accounts-grid {{
            display: grid;
            grid-template-columns: 1fr;
            gap: 0.65rem;
            margin-bottom: 1.5rem;
        }}

        @media (min-width: 640px) {{
            .accounts-grid {{
                grid-template-columns: repeat(2, 1fr);
                gap: 0.85rem;
            }}
        }}

        @media (min-width: 1024px) {{
            .accounts-grid {{
                grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
                gap: 1rem;
            }}
        }}

        .account-card {{
            background: var(--card-bg);
            border: 1px solid var(--card-border);
            backdrop-filter: blur(12px);
            border-radius: 0.85rem;
            padding: 0.9rem 1.1rem;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            transition: border-color 0.2s;
        }}

        .acc-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 0.65rem;
            gap: 0.5rem;
        }}

        .acc-name {{
            font-size: 0.95rem;
            font-weight: 700;
            display: flex;
            align-items: center;
            gap: 0.4rem;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }}

        .acc-badge {{
            background: rgba(16, 185, 129, 0.15);
            color: var(--accent-green);
            padding: 0.2rem 0.55rem;
            border-radius: 9999px;
            font-size: 0.7rem;
            font-weight: 600;
            border: 1px solid rgba(16, 185, 129, 0.3);
            white-space: nowrap;
        }}

        .acc-badge.error {{
            background: rgba(239, 68, 68, 0.15);
            color: var(--accent-red);
            border-color: rgba(239, 68, 68, 0.3);
        }}

        .acc-badge.wait {{
            background: rgba(245, 158, 11, 0.15);
            color: var(--accent-yellow);
            border-color: rgba(245, 158, 11, 0.3);
        }}

        .acc-points-box {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            background: rgba(15, 23, 42, 0.6);
            border-radius: 0.65rem;
            padding: 0.65rem 0.9rem;
            margin-bottom: 0.65rem;
        }}

        .acc-pts-large {{
            font-size: 1.45rem;
            font-weight: 800;
            color: #38bdf8;
        }}

        .acc-gained {{
            font-size: 0.85rem;
            font-weight: 700;
            color: var(--accent-green);
        }}

        .acc-footer {{
            display: flex;
            justify-content: space-between;
            font-size: 0.75rem;
            color: var(--text-muted);
            border-top: 1px solid rgba(255, 255, 255, 0.05);
            padding-top: 0.5rem;
        }}

        /* Panel Container */
        .panel {{
            background: var(--card-bg);
            border: 1px solid var(--card-border);
            backdrop-filter: blur(12px);
            border-radius: 0.85rem;
            padding: 1rem;
            margin-bottom: 1.5rem;
        }}

        @media (min-width: 768px) {{
            .panel {{
                padding: 1.35rem;
            }}
        }}

        .chart-container {{
            position: relative;
            height: 220px;
            width: 100%;
        }}

        @media (min-width: 768px) {{
            .chart-container {{
                height: 280px;
            }}
        }}

        /* History Accordion (Collapsed by Default) */
        .btn-toggle-all {{
            background: rgba(255, 255, 255, 0.06);
            color: var(--text-muted);
            border: 1px solid var(--card-border);
            padding: 0.25rem 0.65rem;
            border-radius: 0.4rem;
            font-size: 0.75rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
        }}

        .btn-toggle-all:hover {{
            background: rgba(255, 255, 255, 0.12);
            color: white;
        }}

        .day-card {{
            background: rgba(15, 23, 42, 0.6);
            border: 1px solid var(--card-border);
            border-radius: 0.75rem;
            margin-bottom: 0.65rem;
            overflow: hidden;
            transition: all 0.2s ease;
        }}

        .day-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 0.75rem 0.95rem;
            cursor: pointer;
            background: rgba(30, 41, 59, 0.4);
            user-select: none;
            transition: background 0.2s;
            gap: 0.5rem;
        }}

        .day-header:hover, .day-header:active {{
            background: rgba(30, 41, 59, 0.8);
        }}

        .day-title {{
            display: flex;
            align-items: center;
            gap: 0.5rem;
            font-weight: 700;
            font-size: 0.9rem;
        }}

        .day-badges {{
            display: flex;
            align-items: center;
            gap: 0.4rem;
            flex-wrap: wrap;
        }}

        .badge-pill {{
            font-size: 0.7rem;
            padding: 0.15rem 0.5rem;
            border-radius: 9999px;
            font-weight: 600;
        }}

        .badge-gained {{
            background: rgba(16, 185, 129, 0.2);
            color: #34d399;
            border: 1px solid rgba(16, 185, 129, 0.3);
        }}

        .badge-runs {{
            background: rgba(59, 130, 246, 0.2);
            color: #60a5fa;
            border: 1px solid rgba(59, 130, 246, 0.3);
        }}

        .badge-today {{
            background: linear-gradient(135deg, #06b6d4, #3b82f6);
            color: white;
            font-size: 0.65rem;
            padding: 0.1rem 0.4rem;
            border-radius: 0.3rem;
            font-weight: 700;
            text-transform: uppercase;
        }}

        .chevron {{
            transition: transform 0.2s ease;
            width: 16px;
            height: 16px;
            color: var(--text-muted);
            flex-shrink: 0;
        }}

        .day-card.open .chevron {{
            transform: rotate(180deg);
        }}

        .day-content {{
            display: none;
            padding: 0.4rem 0.65rem 0.65rem;
            border-top: 1px solid rgba(255, 255, 255, 0.05);
        }}

        .day-card.open .day-content {{
            display: block;
        }}

        /* Clean Mobile Run List */
        .run-item {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 0.55rem 0.4rem;
            border-bottom: 1px solid rgba(255, 255, 255, 0.04);
            font-size: 0.8rem;
            gap: 0.5rem;
        }}

        .run-item:last-child {{
            border-bottom: none;
        }}

        .run-info {{
            display: flex;
            flex-direction: column;
            gap: 0.15rem;
            min-width: 0;
        }}

        .run-acc {{
            font-weight: 600;
            color: var(--text-main);
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }}

        .run-time {{
            font-size: 0.7rem;
            color: var(--text-muted);
            font-family: 'JetBrains Mono', monospace;
        }}

        .run-stats {{
            display: flex;
            align-items: center;
            gap: 0.6rem;
            flex-shrink: 0;
            text-align: right;
        }}

        .run-pts {{
            font-family: 'JetBrains Mono', monospace;
            font-weight: 600;
            color: #38bdf8;
            font-size: 0.85rem;
        }}

        .run-gained {{
            font-size: 0.75rem;
            font-weight: 700;
            color: #34d399;
        }}

        .status-pill {{
            padding: 0.15rem 0.45rem;
            border-radius: 0.35rem;
            font-size: 0.68rem;
            font-weight: 600;
            white-space: nowrap;
        }}

        .status-success {{
            background: rgba(16, 185, 129, 0.15);
            color: #34d399;
        }}

        .status-fail {{
            background: rgba(239, 68, 68, 0.15);
            color: #f87171;
        }}
    </style>
</head>
<body>
    <div class="container">
        <!-- Header -->
        <div class="header">
            <div class="header-title">
                <h1>💎 MS Rewards</h1>
                <p>Theo dõi điểm thưởng & chuỗi tự động</p>
            </div>
            <div>
                <button class="btn-refresh" onclick="location.reload()">
                    <svg width="15" height="15" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path></svg>
                    Làm mới
                </button>
            </div>
        </div>

        <!-- Stats 2x2 Grid -->
        <div class="stats-grid">
            <div class="stat-card c-blue">
                <div class="stat-label">Tổng Điểm</div>
                <div class="stat-value">{total_pts:,}</div>
                <div class="stat-sub">💎 Tích lũy khả dụng</div>
            </div>
            <div class="stat-card c-green">
                <div class="stat-label">Hôm Nay</div>
                <div class="stat-value">+{total_gained_today:,}</div>
                <div class="stat-sub">🚀 Điểm mới cày</div>
            </div>
            <div class="stat-card c-purple">
                <div class="stat-label">Tài Khoản</div>
                <div class="stat-value">{len(latest_accounts)}</div>
                <div class="stat-sub">👥 Đang hoạt động</div>
            </div>
            <div class="stat-card c-yellow">
                <div class="stat-label">Streak Max</div>
                <div class="stat-value">🔥 {max_streak}</div>
                <div class="stat-sub">📅 Ngày duy trì</div>
            </div>
        </div>

        <!-- Account Cards -->
        <div class="section-header">
            <div class="section-title">👤 Trạng Thái Tài Khoản</div>
        </div>
        <div class="accounts-grid" id="accountsList">
            <!-- Dynamic Account Cards -->
        </div>

        <!-- Chart Panel -->
        <div class="panel">
            <div class="section-header">
                <div class="section-title">📈 Tăng Trưởng Điểm</div>
            </div>
            <div class="chart-container">
                <canvas id="pointsChart"></canvas>
            </div>
        </div>

        <!-- History Grouped by Day (Collapsed by Default) -->
        <div class="panel">
            <div class="section-header">
                <div class="section-title">📋 Lịch Sử Theo Ngày</div>
                <button class="btn-toggle-all" id="toggleAllBtn" onclick="toggleAllDays()">Mở tất cả</button>
            </div>
            <div id="historyGroupedContainer">
                <!-- Dynamic Day Cards -->
            </div>
        </div>
    </div>

    <script>
        const historyData = {history_json};
        const latestAccounts = {latest_json};

        // Render Account Cards
        const accContainer = document.getElementById('accountsList');
        accContainer.innerHTML = '';

        if (Object.keys(latestAccounts).length === 0) {{
            accContainer.innerHTML = '<div style="color: var(--text-muted); font-size: 0.85rem;">Chưa có dữ liệu tài khoản.</div>';
        }} else {{
            for (const [accName, acc] of Object.entries(latestAccounts)) {{
                const isSuccess = acc.status === 'Thành công';
                const isWait = acc.status === 'Chờ chạy';
                const badgeClass = isSuccess ? '' : (isWait ? 'wait' : 'error');
                
                const card = document.createElement('div');
                card.className = 'account-card';
                card.innerHTML = `
                    <div>
                        <div class="acc-header">
                            <div class="acc-name" title="${{accName}}">
                                <span>👤</span> ${{accName}}
                            </div>
                            <span class="acc-badge ${{badgeClass}}">${{acc.status}}</span>
                        </div>
                        <div class="acc-points-box">
                            <div>
                                <div style="font-size: 0.7rem; color: var(--text-muted);">ĐIỂM HIỆN TẠI</div>
                                <div class="acc-pts-large">${{acc.end_points || '0'}}</div>
                            </div>
                            <div class="acc-gained">+${{acc.gained || 0}} pts</div>
                        </div>
                    </div>
                    <div class="acc-footer">
                        <span>🔥 Chuỗi: <b>${{acc.streak || 0}} ngày</b></span>
                        <span>🕒 ${{acc.timestamp || 'N/A'}}</span>
                    </div>
                `;
                accContainer.appendChild(card);
            }}
        }}

        // Render Day-Grouped History (Collapsed by Default)
        const historyContainer = document.getElementById('historyGroupedContainer');
        historyContainer.innerHTML = '';

        if (!historyData || historyData.length === 0) {{
            historyContainer.innerHTML = '<div style="color: var(--text-muted); font-size: 0.85rem; padding: 0.5rem 0;">Chưa có nhật ký nào.</div>';
        }} else {{
            const historyByDate = {{}};
            historyData.forEach(item => {{
                const d = item.date || (item.timestamp ? item.timestamp.split(' ')[0] : 'Chưa phân loại');
                if (!historyByDate[d]) historyByDate[d] = [];
                historyByDate[d].push(item);
            }});

            const datesSorted = Object.keys(historyByDate).reverse();

            datesSorted.forEach((dateKey, index) => {{
                const runs = historyByDate[dateKey];
                const totalGained = runs.reduce((acc, cur) => acc + (parseInt(cur.gained) || 0), 0);
                const successCount = runs.filter(r => r.status === 'Thành công').length;
                const isToday = (index === 0);

                let listHtml = '';
                [...runs].reverse().forEach(item => {{
                    const isSuccess = item.status === 'Thành công';
                    const timeOnly = item.timestamp ? (item.timestamp.split(' ')[1] || item.timestamp) : '';
                    listHtml += `
                        <div class="run-item">
                            <div class="run-info">
                                <div class="run-acc">${{item.account}}</div>
                                <div class="run-time">${{timeOnly}} • Gốc: ${{item.start_points}}</div>
                            </div>
                            <div class="run-stats">
                                <div>
                                    <div class="run-pts">${{item.end_points}}</div>
                                    <div class="run-gained">+${{item.gained}}</div>
                                </div>
                                <div>
                                    <span class="status-pill ${{isSuccess ? 'status-success' : 'status-fail'}}">${{item.status}}</span>
                                    <div style="font-size: 0.68rem; color: var(--text-muted); margin-top: 2px;">🔥 ${{item.streak}}d</div>
                                </div>
                            </div>
                        </div>
                    `;
                }});

                const dayCard = document.createElement('div');
                // Collapsed by default
                dayCard.className = 'day-card';
                dayCard.innerHTML = `
                    <div class="day-header" onclick="this.parentElement.classList.toggle('open')">
                        <div class="day-title">
                            <span>📅 ${{dateKey}}</span>
                            ${{isToday ? '<span class="badge-today">Hôm nay</span>' : ''}}
                        </div>
                        <div class="day-badges">
                            <span class="badge-pill badge-gained">+${{totalGained.toLocaleString()}} pts</span>
                            <span class="badge-pill badge-runs">${{runs.length}} lượt (${{successCount}} OK)</span>
                            <svg class="chevron" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"></path></svg>
                        </div>
                    </div>
                    <div class="day-content">
                        ${{listHtml}}
                    </div>
                `;
                historyContainer.appendChild(dayCard);
            }});
        }}

        function toggleAllDays() {{
            const cards = document.querySelectorAll('.day-card');
            const btn = document.getElementById('toggleAllBtn');
            const anyClosed = Array.from(cards).some(c => !c.classList.contains('open'));
            
            cards.forEach(c => {{
                if (anyClosed) {{
                    c.classList.add('open');
                }} else {{
                    c.classList.remove('open');
                }}
            }});
            btn.textContent = anyClosed ? 'Thu gọn tất cả' : 'Mở tất cả';
        }}

        // Render Chart
        const ctx = document.getElementById('pointsChart').getContext('2d');
        const datesSet = new Set();
        const accDatasets = {{}};

        historyData.forEach(item => {{
            datesSet.add(item.date);
            const acc = item.account;
            if (!accDatasets[acc]) {{
                accDatasets[acc] = {{}};
            }}
            const pts = parseInt(String(item.end_points).replace(/[,.]/g, '')) || 0;
            accDatasets[acc][item.date] = pts;
        }});

        const labels = Array.from(datesSet).slice(-7);
        const colors = ['#38bdf8', '#a855f7', '#34d399', '#f59e0b', '#ec4899', '#6366f1', '#14b8a6'];
        
        const datasets = Object.keys(accDatasets).map((acc, index) => {{
            const color = colors[index % colors.length];
            const data = labels.map(d => accDatasets[acc][d] || null);
            return {{
                label: acc.split('@')[0], // Short name for mobile chart legend
                data: data,
                borderColor: color,
                backgroundColor: color + '15',
                borderWidth: 2.5,
                tension: 0.35,
                fill: false,
                pointRadius: 3,
                pointHoverRadius: 5
            }};
        }});

        new Chart(ctx, {{
            type: 'line',
            data: {{ labels: labels, datasets: datasets }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    legend: {{
                        position: 'bottom',
                        labels: {{ 
                            color: '#94a3b8', 
                            boxWidth: 10,
                            padding: 8,
                            font: {{ family: 'Outfit', size: 11 }} 
                        }}
                    }}
                }},
                scales: {{
                    x: {{
                        grid: {{ color: 'rgba(255, 255, 255, 0.04)' }},
                        ticks: {{ color: '#94a3b8', font: {{ family: 'Outfit', size: 10 }} }}
                    }},
                    y: {{
                        grid: {{ color: 'rgba(255, 255, 255, 0.04)' }},
                        ticks: {{ color: '#94a3b8', font: {{ family: 'Outfit', size: 10 }} }}
                    }}
                }}
            }}
        }});
    </script>
</body>
</html>
"""
        with open(DASHBOARD_FILE, "w", encoding="utf-8") as f:
            f.write(html_content)
        with open(INDEX_FILE, "w", encoding="utf-8") as f:
            f.write(html_content)

        return DASHBOARD_FILE
