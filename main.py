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
from src.utils import console, log_info, log_success, log_warn, log_error, log_step

async def login_session(config: BotConfig, is_mobile: bool = False):
    """Open browser in visible mode for user to log in."""
    bm = BrowserManager(config)
    mode_str = "Mobile" if is_mobile else "Desktop"
    log_info(f"Đang mở trình duyệt {mode_str} để đăng nhập...")
    
    try:
        context = await bm.get_context(is_mobile=is_mobile, force_headed=True)
        page = await context.new_page()
        await page.goto("https://rewards.bing.com/")
        
        console.print(Panel.fit(
            f"[bold yellow]HƯỚNG DẪN ĐĂNG NHẬP ({mode_str}):[/bold yellow]\n"
            "1. Đăng nhập tài khoản Microsoft trên cửa sổ trình duyệt vừa mở ra.\n"
            "2. Kiểm tra trang https://rewards.bing.com/ và https://www.bing.com/ đã hiển thị tài khoản của bạn.\n"
            "3. Sau khi hoàn tất, quay lại đây và nhấn [bold green]ENTER[/bold green] để lưu phiên đăng nhập.",
            title=f"Đăng nhập Microsoft Rewards ({mode_str})",
            border_style="cyan"
        ))
        
        await asyncio.to_thread(input, "Nhấn ENTER sau khi bạn đã hoàn tất đăng nhập trên trình duyệt...")
        
        # Verify and sync Bing search cookies
        try:
            await page.goto("https://www.bing.com/", wait_until="domcontentloaded", timeout=15000)
            await asyncio.sleep(2)
        except Exception:
            pass

        log_success(f"Đã lưu session đăng nhập cho {mode_str} profile!")
    finally:
        await bm.close()

async def run_full_bot(config: BotConfig):
    """Run full automation workflow."""
    bm = BrowserManager(config)
    start_points = "N/A"
    end_points = "N/A"

    try:
        # Phase 1: Desktop Context (Daily set, More activities, Desktop Search)
        log_step("GIAI ĐOẠN 1: DESKTOP WORKFLOW")
        context_desk = await bm.get_context(is_mobile=False)
        page_desk = await context_desk.new_page()

        dashboard = RewardsDashboard(page_desk, context_desk, config)
        is_logged_in = await dashboard.open_dashboard()

        if not is_logged_in:
            log_error("Chưa đăng nhập tài khoản Microsoft! Vui lòng chọn menu 'Đăng nhập' trước.")
            return

        summary = await dashboard.get_account_summary()
        start_points = summary.get("points", "N/A")
        log_info(f"Số điểm ban đầu: [bold green]{start_points}[/bold green] (Chuỗi: {summary.get('streak', '0')} ngày)")

        # 1. Daily Set
        if config.run_daily_set:
            await dashboard.solve_daily_set()

        # 2. More Activities
        if config.run_more_activities:
            await dashboard.solve_more_activities()

        # 3. Desktop Search
        if config.run_desktop_search and config.desktop_searches > 0:
            searcher_desk = BingSearcher(page_desk, config, is_mobile=False)
            await searcher_desk.run_searches(config.desktop_searches)

        await bm.close()

        # Phase 2: Mobile Context (Mobile Search)
        if config.run_mobile_search and config.mobile_searches > 0:
            log_step("GIAI ĐOẠN 2: MOBILE SEARCH WORKFLOW")
            context_mob = await bm.get_context(is_mobile=True)
            page_mob = await context_mob.new_page()

            searcher_mob = BingSearcher(page_mob, config, is_mobile=True)
            await searcher_mob.run_searches(config.mobile_searches)

            await bm.close()

        # Phase 3: Final Point Summary
        log_step("TỔNG KẾT")
        context_final = await bm.get_context(is_mobile=False)
        page_final = await context_final.new_page()
        dash_final = RewardsDashboard(page_final, context_final, config)
        if await dash_final.open_dashboard():
            end_summary = await dash_final.get_account_summary()
            end_points = end_summary.get("points", "N/A")

        table = Table(title="Kết Quả Hoàn Thành Microsoft Rewards", style="cyan")
        table.add_column("Mục", style="bold white")
        table.add_column("Chi tiết", style="bold yellow")
        table.add_row("Điểm ban đầu", str(start_points))
        table.add_row("Điểm sau khi chạy", str(end_points))
        table.add_row("Trạng thái", "[bold green]HOÀN TẤT THÀNH CÔNG[/bold green]")
        console.print(table)

        # Send Telegram notification if configured
        from src.telegram_bot import TelegramNotifier
        notifier = TelegramNotifier()
        if notifier.is_configured:
            notifier.send_rewards_summary(start_pts=start_points, end_pts=end_points, status="Thành công")

    except Exception as e:
        log_error(f"Đã xảy ra lỗi trong quá trình chạy: {e}")
        from src.telegram_bot import TelegramNotifier
        notifier = TelegramNotifier()
        if notifier.is_configured:
            notifier.send_message(f"⚠️ <b>LỖI CHẠY BOT MICROSOFT REWARDS:</b>\n<code>{e}</code>")
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
        console.print("[0] 🚪 Thoát")

        choice = Prompt.ask("\nNhập lựa chọn của bạn", choices=["0", "1", "2", "3", "4", "5", "6", "7"], default="1")

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

def main():
    parser = argparse.ArgumentParser(description="Bing Rewards Automation Bot")
    parser.add_argument("--all", action="store_true", help="Chạy toàn bộ tự động không cần menu tương tác")
    parser.add_argument("--login", action="store_true", help="Mở trình duyệt để đăng nhập")
    parser.add_argument("--headless", action="store_true", help="Chạy ở chế độ không mở cửa sổ trình duyệt")

    args = parser.parse_args()
    config = BotConfig.load()

    if args.headless:
        config.headless = True

    if args.login:
        asyncio.run(login_session(config))
    elif args.all:
        asyncio.run(run_full_bot(config))
    else:
        show_menu(config)

if __name__ == "__main__":
    main()
