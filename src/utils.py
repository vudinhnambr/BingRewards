import random
import time
import asyncio
import sys
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
