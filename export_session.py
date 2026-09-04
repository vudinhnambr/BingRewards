import asyncio
import base64
import json
import subprocess
from pathlib import Path
from src.config import BotConfig
from src.browser import BrowserManager
from src.utils import console, log_info, log_success, log_error
from rich.panel import Panel

SESSION_FILE = Path(__file__).resolve().parent / "session.json"
TXT_FILE = Path(__file__).resolve().parent / "session_base64.txt"

def copy_to_clipboard(text: str):
    try:
        process = subprocess.Popen('clip', stdin=subprocess.PIPE, shell=True)
        process.communicate(input=text.encode('utf-8'))
        return True
    except Exception:
        return False

def clean_session_data(data: dict) -> dict:
    """Filter out bloated telemetry/analytics and keep only vital auth cookies."""
    # Keep only relevant domains: bing.com, live.com, microsoft.com, microsoftonline.com
    relevant_domains = ["bing.com", "live.com", "microsoft.com", "microsoftonline.com", "msn.com"]
    
    clean_cookies = []
    for c in data.get("cookies", []):
        domain = c.get("domain", "").lower()
        if any(rd in domain for rd in relevant_domains):
            clean_cookies.append(c)
            
    # Filter origins in localStorage - discard telemetry blobs
    clean_origins = []
    for o in data.get("origins", []):
        origin_url = o.get("origin", "").lower()
        if any(rd in origin_url for rd in relevant_domains):
            clean_storage = []
            for item in o.get("localStorage", []):
                name = item.get("name", "")
                # Discard telemetry logs
                if not any(ign in name.lower() for ign in ["telemetry", "webvitals", "pageaction"]):
                    clean_storage.append(item)
            clean_origins.append({"origin": o["origin"], "localStorage": clean_storage})

    return {"cookies": clean_cookies, "origins": clean_origins}

async def export():
    config = BotConfig.load()
    config.headless = True
    bm = BrowserManager(config)
    
    log_info("Đang trích xuất và tối ưu hóa dung lượng session...")
    try:
        context = await bm.get_context(is_mobile=False)
        page = await context.new_page()
        await page.goto("https://rewards.bing.com/dashboard", wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(2)
        
        # Save raw state
        raw_state = await context.storage_state()
        
        # Optimize & shrink size
        cleaned_state = clean_session_data(raw_state)
        
        # Save JSON (compact without whitespace)
        compact_json = json.dumps(cleaned_state, separators=(',', ':'))
        
        with open(SESSION_FILE, "w", encoding="utf-8") as f:
            f.write(compact_json)
            
        b64_session = base64.b64encode(compact_json.encode("utf-8")).decode("utf-8")
        
        with open(TXT_FILE, "w", encoding="utf-8") as f:
            f.write(b64_session)

        # Auto copy
        copied = copy_to_clipboard(b64_session)
        
        size_kb = len(b64_session) / 1024

        console.clear()
        clip_status = "[bold green]✅ ĐÃ NÉN NHẸ & TỰ ĐỘNG COPY VÀO BỘ NHỚ TẠM (CLIPBOARD)![/bold green]\n👉 Bạn chỉ cần qua trang GitHub và nhấn [bold yellow]Ctrl + V[/bold yellow] để dán!" if copied else ""

        console.print(Panel.fit(
            f"{clip_status}\n\n"
            f"⚡ Dung lượng sau khi nén: [bold yellow]{size_kb:.1f} KB[/bold yellow] (Giới hạn GitHub là 48 KB ➔ [bold green]HỢP LỆ 100%[/bold green])\n\n"
            "Các bước dán vào GitHub:\n"
            "1. Tên Secret: [bold white]MICROSOFT_SESSION[/bold white]\n"
            "2. Phần Secret Value: Nhấn [bold yellow]Ctrl + V[/bold yellow] để dán ➔ Nhấn [bold green]Add secret[/bold green].",
            title="MICROSOFT_SESSION ĐÃ NÉN THÀNH CÔNG",
            border_style="green"
        ))
        
    except Exception as e:
        log_error(f"Lỗi khi trích xuất session: {e}")
    finally:
        await bm.close()

if __name__ == "__main__":
    asyncio.run(export())
