import random
import time
import asyncio
import sys
from typing import Tuple
from playwright.async_api import Page
from rich.console import Console
from rich.theme import Theme

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

custom_theme = Theme({
    "info": "cyan",
    "warning": "yellow",
    "error": "bold red",
    "success": "bold green",
    "highlight": "bold magenta",
})

console = Console(theme=custom_theme, legacy_windows=False)


def log_info(msg: str):
    console.print(f"[info][INFO][/info] {msg}")

def log_success(msg: str):
    console.print(f"[success][SUCCESS][/success] {msg}")

def log_warn(msg: str):
    console.print(f"[warning][WARN][/warning] {msg}")

def log_error(msg: str):
    console.print(f"[error][ERROR][/error] {msg}")

def log_step(title: str):
    console.rule(f"[bold cyan]{title}[/bold cyan]")

async def random_delay(min_sec: float = 6.0, max_sec: float = 12.0, reason: str = ""):
    """Async delay with random duration to mimic human behavior."""
    delay = round(random.uniform(min_sec, max_sec), 2)
    if reason:
        log_info(f"Đang chờ {delay}s ({reason})...")
    else:
        log_info(f"Đang chờ {delay}s...")
    await asyncio.sleep(delay)


def parse_pts(val) -> int:
    """Parse point value from various formats ('1,234', '1.234', 'N/A', None) to int."""
    if val is None or str(val).strip().upper() == "N/A":
        return 0
    try:
        return int(str(val).replace(",", "").replace(".", "").strip())
    except (ValueError, TypeError):
        return 0


async def is_bot_blocked(page: Page) -> Tuple[bool, str]:
    """Detect if Microsoft is serving a bot-detection / warning page.

    Returns: (is_blocked, reason)
        reason is one of: captcha, warning, redirect, empty, blocked_title
    """
    try:
        url = page.url.lower()
        title = (await page.title()).lower()
        body_text = (await page.evaluate("document.body?.innerText || ''")).lower()

        signals = [
            ("captcha",
             "captcha" in body_text or "verify you're human" in body_text
             or "i'm not a robot" in body_text),
            ("warning",
             "unusual traffic" in body_text or "automated queries" in body_text
             or "your computer or network" in body_text),
            ("redirect",
             "login.live.com" in url and "/dashboard" not in url and "/earn" not in url),
            ("empty",
             len(body_text.strip()) < 50 and "rewards" not in body_text),
            ("blocked_title",
             "access denied" in title or "sorry" in title),
        ]

        for reason, detected in signals:
            if detected:
                return True, reason
        return False, ""
    except Exception:
        return False, ""
