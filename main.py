import argparse
import asyncio
import sys

# Ensure UTF-8 output on Windows console
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from rich.table import Table
from rich.panel import Panel
from rich.prompt import Prompt, Confirm


from src.config import BotConfig
from src.browser import BrowserManager
from src.searcher import BingSearcher
from src.activities import RewardsDashboard
from src.utils import console, log_info, log_success, log_warn, log_error, log_step, parse_pts

async def login_session(config: BotConfig, is_mobile: bool = False, force_clean: bool = True):
    """Open browser in visible mode for user to log in."""
    import shutil
    import json
    import base64
    import subprocess
    from pathlib import Path
    from export_session import clean_session_data

    # Always clean session files when initiating a new login
    profile_dir = Path(__file__).resolve().parent / "browser_data" / "desktop_profile"
    session_file = Path(__file__).resolve().parent / "session.json"
    txt_file = Path(__file__).resolve().parent / "session_base64.txt"

    if profile_dir.exists():
        try:
            shutil.rmtree(profile_dir, ignore_errors=True)
        except Exception:
            pass
    if session_file.exists():
        session_file.unlink(missing_ok=True)
    if txt_file.exists():
        txt_file.unlink(missing_ok=True)

    log_info("Đã làm sạch dữ liệu trình duyệt và phiên đăng nhập cũ!")

    bm = BrowserManager(config)
    mode_str = "Mobile" if is_mobile else "Desktop"
    log_info(f"Đang mở trình duyệt {mode_str} để đăng nhập tài khoản mới...")
    
    try:
        context = await bm.get_context(is_mobile=is_mobile, force_headed=True, is_login=True)
        page = await context.new_page()
        
        # Ensure logout of any previous session first
        try:
            await page.goto("https://login.live.com/logout.srf", wait_until="domcontentloaded", timeout=10000)
            await asyncio.sleep(1)
        except Exception:
            pass

        # Open Microsoft login page directly
        await page.goto("https://login.live.com/", wait_until="domcontentloaded", timeout=30000)
        
        console.print(Panel.fit(
            f"[bold yellow]HƯỚNG DẪN ĐĂNG NHẬP ({mode_str}):[/bold yellow]\n"
            "1. Nhập email và mật khẩu của [bold cyan]TÀI KHOẢN MỚI[/bold cyan] trên trình duyệt vừa mở ra.\n"
            "2. Sau khi đăng nhập thành công, mở trang https://rewards.bing.com/ để kiểm tra.\n"
            "3. Quay lại cửa sổ này và nhấn [bold green]ENTER[/bold green] để tự động lưu và copy mã session vào bộ nhớ tạm (Clipboard).",
            title=f"Đăng nhập Microsoft Rewards ({mode_str})",
            border_style="cyan"
        ))
        
        await asyncio.to_thread(input, "\n👉 Nhấn ENTER sau khi bạn đã đăng nhập xong trên trình duyệt...")
        
        # Save and auto-export session
        try:
            # Navigate to rewards and bing to ensure all auth tokens are set
            try:
                if not page.is_closed():
                    await page.goto("https://rewards.bing.com/", wait_until="domcontentloaded", timeout=15000)
                    await asyncio.sleep(2)
                    await page.goto("https://www.bing.com/", wait_until="domcontentloaded", timeout=15000)
                    await asyncio.sleep(2)
            except Exception:
                pass

            raw_state = await context.storage_state()
            cleaned_state = clean_session_data(raw_state)
            compact_json = json.dumps(cleaned_state, separators=(',', ':'))

            with open(session_file, "w", encoding="utf-8") as f:
                f.write(compact_json)

            b64_session = base64.b64encode(compact_json.encode("utf-8")).decode("utf-8")
            with open(txt_file, "w", encoding="utf-8") as f:
                f.write(b64_session)

            # Copy to clipboard
            copied = False
            try:
                process = subprocess.Popen('clip', stdin=subprocess.PIPE, shell=True)
                process.communicate(input=b64_session.encode('utf-8'))
                copied = True
            except Exception:
                pass

            size_kb = len(b64_session) / 1024
            console.print(Panel.fit(
                f"[bold green]✅ ĐÃ LƯU VÀ SAO CHÉP MÃ SESSION THÀNH CÔNG![/bold green]\n\n"
                f"{'👉 Đã copy vào bộ nhớ tạm (Clipboard) — Bạn có thể nhấn Ctrl+V để dán ngay!' if copied else 'Mã session đã lưu tại file session_base64.txt'}\n"
                f"⚡ Dung lượng: [bold yellow]{size_kb:.1f} KB[/bold yellow] (Hợp lệ cho GitHub Secret < 48 KB)\n\n"
                "📌 [bold cyan]HƯỚNG DẪN THÊM VÀO GITHUB ACTIONS (Nhiều tài khoản):[/bold cyan]\n"
                "1. Vào GitHub repo ➔ [bold white]Settings[/bold white] ➔ [bold white]Secrets and variables[/bold white] ➔ [bold white]Actions[/bold white]\n"
                "2. Nhấn [bold green]New repository secret[/bold green]\n"
                "   • [bold white]Name:[/bold white] [bold yellow]MICROSOFT_SESSION_3[/bold yellow] (hoặc _2, _4, _5 tương ứng)\n"
                "   • [bold white]Secret:[/bold white] Nhấn [bold yellow]Ctrl + V[/bold yellow] để dán mã\n"
                "3. Nhấn [bold green]Add secret[/bold green]. GitHub Actions sẽ tự động chạy tài khoản này mỗi ngày!",
                title="ĐĂNG NHẬP & XUẤT SESSION THÀNH CÔNG",
                border_style="green"
            ))
        except Exception as e:
            log_error(f"Lỗi khi trích xuất session: {e}")

    finally:
        await bm.close()

async def run_full_bot(config: BotConfig, account_label: str = "") -> dict:
    """Run full automation workflow for a specific account and return result dict."""
    bm = BrowserManager(config)
    start_points = "N/A"
    end_points = "N/A"
    streak = "0"
    account_name = account_label or "Account 1"

    try:
        # Phase 1: Desktop Context (Daily set, More activities, Desktop Search)
        log_step(f"GIAI ĐOẠN 1: DESKTOP WORKFLOW {f'({account_label})' if account_label else ''}")
        context_desk = await bm.get_context(is_mobile=False)
        page_desk = await context_desk.new_page()

        dashboard = RewardsDashboard(page_desk, context_desk, config)
        is_logged_in = await dashboard.open_dashboard()

        if not is_logged_in:
            log_error(f"Chưa đăng nhập tài khoản Microsoft {f'[{account_label}]' if account_label else ''}!")
            from src.telegram_bot import TelegramNotifier
            from src.reporter import AccountReporter
            AccountReporter.log_account_run(account_name, "N/A", "N/A", streak="0", status="Lỗi đăng nhập")
            notifier = TelegramNotifier()
            if notifier.is_configured:
                notifier.send_message(f"⚠️ <b>LỖI ĐĂNG NHẬP {f'({account_label})' if account_label else ''}:</b>\nKhông thể truy cập Rewards Dashboard (Session có thể đã hết hạn hoặc cookie bị thiếu). Vui lòng cập nhật lại Secret trên GitHub!")
            return {"account": account_name, "start_points": "N/A", "end_points": "N/A", "gained": 0, "streak": "0", "status": "Lỗi đăng nhập"}

        summary = await dashboard.get_account_summary()
        start_points = summary.get("points", "N/A")
        streak = summary.get("streak", "0")
        log_info(f"Số điểm ban đầu: [bold green]{start_points}[/bold green] (Chuỗi: {streak} ngày)")

        # 1. Daily Set & Activities
        if config.run_daily_set:
            await dashboard.solve_daily_set()

        # 2. Desktop Search
        if config.run_desktop_search and config.desktop_searches > 0:
            searcher_desk = BingSearcher(page_desk, config, is_mobile=False)
            await searcher_desk.run_searches(config.desktop_searches)

        await bm.close()

        # Phase 2: Mobile Context (Mobile Check-in, Mobile Search & MSN News)
        if config.run_mobile_search or config.run_msn_news or config.run_daily_set:
            log_step(f"GIAI ĐOẠN 2: MOBILE TASKS & MOBILE SEARCH {f'({account_label})' if account_label else ''}")
            context_mob = await bm.get_context(is_mobile=True)
            page_mob = await context_mob.new_page()

            # Mobile Dashboard Check-in and Drawers
            dash_mob = RewardsDashboard(page_mob, context_mob, config, is_mobile=True)
            if await dash_mob.open_dashboard("https://rewards.bing.com/earn"):
                await dash_mob.handle_drawer_actions()

            # Mobile Search
            if config.run_mobile_search and config.mobile_searches > 0:
                searcher_mob = BingSearcher(page_mob, config, is_mobile=True)
                await searcher_mob.run_searches(config.mobile_searches)

            # MSN News Read to Earn (+30 pts bonus)
            if config.run_msn_news:
                from src.msn_news import MSNNewsReader
                news_reader = MSNNewsReader(page_mob, context_mob)
                await news_reader.read_articles(count=10)

            await bm.close()

        # Phase 3: Final Point Summary + UrlReward retry on /earn
        log_step(f"TỔNG KẾT {f'({account_label})' if account_label else ''}")
        context_final = await bm.get_context(is_mobile=False)
        page_final = await context_final.new_page()
        dash_final = RewardsDashboard(page_final, context_final, config)

        # Try /earn first for urlreward, then fallback to /dashboard for points
        earn_loaded = await dash_final.open_dashboard("https://rewards.bing.com/earn")
        if earn_loaded:
            await dash_final.handle_urlreward_promotions()
        # Always read final points from /dashboard (more reliable)
        if await dash_final.open_dashboard("https://rewards.bing.com/dashboard"):
            end_summary = await dash_final.get_account_summary()
            end_points = end_summary.get("points", "N/A")
            streak = end_summary.get("streak", streak)

        table = Table(title=f"Kết Quả Microsoft Rewards {f'[{account_label}]' if account_label else ''}", style="cyan")
        table.add_column("Mục", style="bold white")
        table.add_column("Chi tiết", style="bold yellow")
        table.add_row("Điểm ban đầu", str(start_points))
        table.add_row("Điểm sau khi chạy", str(end_points))
        table.add_row("Chuỗi ngày (Streak)", f"🔥 {streak} ngày")
        table.add_row("Trạng thái", "[bold green]HOÀN TẤT THÀNH CÔNG[/bold green]")
        console.print(table)

        # Log to AccountReporter and generate dashboard
        from src.reporter import AccountReporter
        AccountReporter.log_account_run(account_name, start_points, end_points, streak=streak, status="Thành công")

        # Send Telegram notification for this account
        from src.telegram_bot import TelegramNotifier
        notifier = TelegramNotifier()
        if notifier.is_configured:
            notifier.send_rewards_summary(start_pts=start_points, end_pts=end_points, status="Thành công", account_label=account_label)

        gained = max(0, parse_pts(end_points) - parse_pts(start_points))
        return {"account": account_name, "start_points": str(start_points), "end_points": str(end_points), "gained": gained, "streak": str(streak), "status": "Thành công"}

    except Exception as e:
        log_error(f"Đã xảy ra lỗi trong quá trình chạy {f'({account_label})' if account_label else ''}: {e}")
        from src.reporter import AccountReporter
        AccountReporter.log_account_run(account_name, start_points, end_points, streak=streak, status="Lỗi")
        from src.telegram_bot import TelegramNotifier
        notifier = TelegramNotifier()
        if notifier.is_configured:
            notifier.send_message(f"⚠️ <b>LỖI CHẠY BOT MICROSOFT REWARDS {f'({account_label})' if account_label else ''}:</b>\n<code>{e}</code>")
        return {"account": account_name, "start_points": str(start_points), "end_points": str(end_points), "gained": 0, "streak": str(streak), "status": "Lỗi"}
    finally:
        await bm.close()

def show_menu(config: BotConfig):
    """Show interactive CLI menu."""
    while True:
        console.clear()
        console.print(Panel.fit(
            "[bold cyan]🤖 BING REWARDS AUTOMATION TOOL 🤖[/bold cyan]\n"
            f"[dim]Trình duyệt: {config.browser_channel} | Headless: {config.headless} | Desktop: {config.desktop_searches} | Mobile: {config.mobile_searches}[/dim]",
            border_style="bright_blue"
        ))

        console.print("[1] 🚀 Chạy toàn bộ nhiệm vụ (Daily Set + Desktop Search + Mobile Search)")
        console.print("[2] 📋 Chỉ làm Daily Set & More Activities")
        console.print("[3] 💻 Chỉ chạy Desktop Search")
        console.print("[4] 📱 Chỉ chạy Mobile Search")
        console.print("[5] 🔑 Đăng nhập / Đổi tài khoản (Mở trình duyệt Desktop)")
        console.print("[6] 📲 Đăng nhập tài khoản Mobile (Nếu cần)")
        console.print("[7] ⚙️  Cài đặt cấu hình (Headless, số lượt tìm kiếm...)")
        console.print("[8] 📊 Mở Bảng Tổng Quan Điểm Thưởng (Web Dashboard)")
        console.print("[0] 🚪 Thoát")

        choice = Prompt.ask("\nNhập lựa chọn của bạn", choices=["0", "1", "2", "3", "4", "5", "6", "7", "8"], default="1")

        if choice == "0":
            console.print("[green]Tạm biệt![/green]")
            break
        elif choice == "1":
            asyncio.run(run_full_bot(config))
            Prompt.ask("\nNhấn Enter để quay lại menu...")
        elif choice == "2":
            sub_cfg = BotConfig.load()
            sub_cfg.run_desktop_search = False
            sub_cfg.run_mobile_search = False
            asyncio.run(run_full_bot(sub_cfg))
            Prompt.ask("\nNhấn Enter để quay lại menu...")
        elif choice == "3":
            sub_cfg = BotConfig.load()
            sub_cfg.run_daily_set = False
            sub_cfg.run_more_activities = False
            sub_cfg.run_mobile_search = False
            asyncio.run(run_full_bot(sub_cfg))
            Prompt.ask("\nNhấn Enter để quay lại menu...")
        elif choice == "4":
            sub_cfg = BotConfig.load()
            sub_cfg.run_daily_set = False
            sub_cfg.run_more_activities = False
            sub_cfg.run_desktop_search = False
            asyncio.run(run_full_bot(sub_cfg))
            Prompt.ask("\nNhấn Enter để quay lại menu...")
        elif choice == "5":
            asyncio.run(login_session(config, is_mobile=False))
            Prompt.ask("\nNhấn Enter để quay lại menu...")
        elif choice == "6":
            asyncio.run(login_session(config, is_mobile=True))
            Prompt.ask("\nNhấn Enter để quay lại menu...")
        elif choice == "7":
            config.headless = Confirm.ask("Chạy ở chế độ ẩn danh (Headless - không hiện cửa sổ trình duyệt)?", default=config.headless)
            config.desktop_searches = int(Prompt.ask("Số lượt tìm kiếm Desktop", default=str(config.desktop_searches)))
            config.mobile_searches = int(Prompt.ask("Số lượt tìm kiếm Mobile", default=str(config.mobile_searches)))
            config.min_delay_sec = float(Prompt.ask("Thời gian chờ tối thiểu giữa các tìm kiếm (giây)", default=str(config.min_delay_sec)))
            config.max_delay_sec = float(Prompt.ask("Thời gian chờ tối đa giữa các tìm kiếm (giây)", default=str(config.max_delay_sec)))
            config.save()
            log_success("Đã lưu cấu hình mới!")
            Prompt.ask("\nNhấn Enter để quay lại menu...")
        elif choice == "8":
            import webbrowser
            from src.reporter import AccountReporter
            dash_path = AccountReporter.generate_html_dashboard()
            webbrowser.open(dash_path.as_uri())
            log_success(f"Đã mở Bảng tổng quan tại: {dash_path}")
            Prompt.ask("\nNhấn Enter để quay lại menu...")

async def run_multi_accounts(config: BotConfig, target_account: str = None):
    """Detect all configured account sessions and run sequentially (or run specific target account)."""
    import os
    import shutil
    from pathlib import Path
    from src.reporter import AccountReporter
    from src.telegram_bot import TelegramNotifier
    
    # Collect all available account sessions
    accounts = []
    
    def _is_valid_session(val: str) -> bool:
        """Check if session string looks like valid base64-encoded JSON."""
        if not val or len(val.strip()) < 50:
            return False
        try:
            import base64
            decoded = base64.b64decode(val.strip())
            return decoded.startswith(b'{') or decoded.startswith(b'[')
        except Exception:
            return False

    # Check default session
    sec_1 = os.environ.get("MICROSOFT_SESSION") or os.environ.get("MICROSOFT_SESSION_1")
    if _is_valid_session(sec_1):
        accounts.append(("Account 1", sec_1.strip()))
        
    # Check numbered sessions (MICROSOFT_SESSION_2, 3, 4, 5...)
    for i in range(2, 11):
        val = os.environ.get(f"MICROSOFT_SESSION_{i}")
        if _is_valid_session(val):
            accounts.append((f"Account {i}", val.strip()))

    # If no env sessions found, run default local profile
    if not accounts:
        res = await run_full_bot(config, account_label="Local Account")
        return

    # Filter target account if requested
    if target_account and target_account.strip().lower() != "all":
        t = target_account.strip().lower().replace("account", "").strip()
        filtered = [a for a in accounts if a[0].lower() == target_account.lower() or a[0].lower().endswith(t)]
        if filtered:
            accounts = filtered
            log_info(f"Đã chọn chạy riêng biệt: {[a[0] for a in accounts]}")
        else:
            log_warn(f"Không tìm thấy cấu hình phiên cho '{target_account}'. Sẽ chạy các tài khoản khả dụng: {[a[0] for a in accounts]}")

    log_info(f"Phát hiện {len(accounts)} tài khoản Microsoft được cấu hình: {[a[0] for a in accounts]}!")

    all_results = []
    for idx, (label, session_b64) in enumerate(accounts, start=1):
        log_step(f"BẮT ĐẦU TÀI KHOẢN [{idx}/{len(accounts)}]: {label}")
        
        # Reset desktop profile directory and session.json for isolated clean run
        profile_dir = Path(__file__).resolve().parent / "browser_data" / "desktop_profile"
        session_file = Path(__file__).resolve().parent / "session.json"

        if profile_dir.exists():
            try:
                shutil.rmtree(profile_dir, ignore_errors=True)
            except Exception:
                pass
        if session_file.exists():
            try:
                session_file.unlink(missing_ok=True)
            except Exception:
                pass

        # Set session for this specific account
        os.environ["MICROSOFT_SESSION"] = session_b64

        display_name = config.account_labels.get(label, label) if (config.account_labels and label in config.account_labels) else label
        res = None
        try:
            res = await run_full_bot(config, account_label=display_name)
        except Exception as e:
            log_error(f"Lỗi khi chạy {display_name}: {e}")
            res = {"account": display_name, "start_points": "N/A", "end_points": "N/A", "gained": 0, "streak": "0", "status": "Lỗi"}

        if res:
            all_results.append(res)

        # Long cool down between different accounts to avoid temporary limits
        if idx < len(accounts):
            import random
            delay_secs = random.randint(60, 150)
            log_info(f"Nghỉ {delay_secs} giây trước khi chuyển sang tài khoản tiếp theo (chậm mà chắc)...")
            await asyncio.sleep(delay_secs)

    # Generate visual dashboard and send Grand Multi-Account Summary via Telegram
    AccountReporter.generate_html_dashboard()
    if len(all_results) > 1:
        notifier = TelegramNotifier()
        if notifier.is_configured:
            notifier.send_grand_multi_account_summary(all_results)

def main():
    parser = argparse.ArgumentParser(description="Bing Rewards Automation Bot")
    parser.add_argument("--all", action="store_true", help="Chạy toàn bộ tự động không cần menu tương tác")
    parser.add_argument("--account", type=str, default="All", help="Chọn tài khoản cụ thể để chạy (ví dụ: 'Account 3' hoặc '3' hoặc 'All')")
    parser.add_argument("--login", action="store_true", help="Mở trình duyệt để đăng nhập")
    parser.add_argument("--headless", action="store_true", help="Chạy ở chế độ không mở cửa sổ trình duyệt")
    parser.add_argument("--dashboard", action="store_true", help="Mở Bảng tổng quan Dashboard trên trình duyệt")

    args = parser.parse_args()
    config = BotConfig.load()

    if args.headless:
        config.headless = True

    if args.dashboard:
        import webbrowser
        from src.reporter import AccountReporter
        p = AccountReporter.generate_html_dashboard()
        webbrowser.open(p.as_uri())
    elif args.login:
        asyncio.run(login_session(config))
    elif args.all:
        asyncio.run(run_multi_accounts(config, target_account=args.account))
    else:
        show_menu(config)

if __name__ == "__main__":
    main()
