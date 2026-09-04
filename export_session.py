import asyncio
import base64
import json
from pathlib import Path
from src.config import BotConfig
from src.browser import BrowserManager
from src.utils import console, log_info, log_success, log_error
from rich.panel import Panel

SESSION_FILE = Path(__file__).resolve().parent / "session.json"

async def export():
    config = BotConfig.load()
    config.headless = True
    bm = BrowserManager(config)
    
    log_info("Đang trích xuất cookie và session từ trình duyệt...")
    try:
        context = await bm.get_context(is_mobile=False)
        page = await context.new_page()
        await page.goto("https://rewards.bing.com/dashboard", wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(3)
        
        # Save storage state (cookies + localStorage)
        await context.storage_state(path=str(SESSION_FILE))
        
        with open(SESSION_FILE, "r", encoding="utf-8") as f:
            session_json = f.read()
            
        b64_session = base64.b64encode(session_json.encode("utf-8")).decode("utf-8")
        
        console.clear()
        console.print(Panel.fit(
            "[bold green]XUẤT SESSION THÀNH CÔNG ĐỂ DÙNG TRÊN GITHUB ACTIONS![/bold green]\n\n"
            "1. Vào GitHub Repo của bạn ➔ [bold cyan]Settings[/bold cyan] ➔ [bold cyan]Secrets and variables[/bold cyan] ➔ [bold cyan]Actions[/bold cyan]\n"
            "2. Nhấn [bold yellow]New repository secret[/bold yellow]\n"
            "3. Đặt Name: [bold white]MICROSOFT_SESSION[/bold white]\n"
            "4. Dán toàn bộ chuỗi mã hóa bên dưới vào phần Secret Value:\n\n"
            f"[bold magenta]{b64_session}[/bold magenta]\n\n"
            "[dim](Chuỗi này cũng đã được lưu tự động vào file session.json trong thư mục dự án)[/dim]",
            title="MICROSOFT SESSION FOR GITHUB ACTIONS",
            border_style="green"
        ))
        
    except Exception as e:
        log_error(f"Lỗi khi trích xuất session: {e}")
    finally:
        await bm.close()

if __name__ == "__main__":
    asyncio.run(export())
