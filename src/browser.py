import os
from pathlib import Path
from typing import Optional, Tuple
from playwright.async_api import async_playwright, BrowserContext, Page, Playwright
from src.config import BotConfig
from src.utils import log_info, log_warn, log_success

USER_DATA_DIR = Path(__file__).resolve().parent.parent / "browser_data"

# Desktop User-Agent (Edge on Windows)
DESKTOP_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36 Edg/140.0.0.0"

# Mobile User-Agent (Edge on Android / iPhone)
MOBILE_UA = "Mozilla/5.0 (Linux; Android 15; Pixel 9 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Mobile Safari/537.36 EdgA/140.0.0.0"

MOBILE_VIEWPORT = {"width": 393, "height": 851}
DESKTOP_VIEWPORT = {"width": 1280, "height": 800}

class BrowserManager:
    """Manages Playwright browser sessions with persistent cookies/profiles."""

    def __init__(self, config: BotConfig):
        self.config = config
        self.playwright: Optional[Playwright] = None
        self.context: Optional[BrowserContext] = None

    async def get_context(self, is_mobile: bool = False, force_headed: bool = False, is_login: bool = False) -> BrowserContext:
        """Launch or return persistent browser context (unified profile)."""
        # Close existing context before creating a new one to avoid leaks
        if self.context:
            try:
                await self.context.close()
            except Exception:
                pass
            self.context = None

        profile_dir = USER_DATA_DIR / "desktop_profile"
        profile_dir.mkdir(parents=True, exist_ok=True)

        # Cleanup stale singleton locks if browser closed unexpectedly
        for lock_name in ["SingletonLock", "SingletonCookie", "SingletonSocket", "lockfile"]:
            lock_path = profile_dir / lock_name
            if lock_path.exists():
                try:
                    if lock_path.is_file():
                        lock_path.unlink(missing_ok=True)
                except Exception:
                    pass

        # Restore storage state from env or file if running in CI/GitHub Actions
        session_env = os.environ.get("MICROSOFT_SESSION")
        session_file = Path(__file__).resolve().parent.parent / "session.json"
        storage_param = None

        if not is_login:
            if session_env:
                import base64
                try:
                    decoded = base64.b64decode(session_env.strip()).decode("utf-8")
                    with open(session_file, "w", encoding="utf-8") as f:
                        f.write(decoded)
                    storage_param = str(session_file)
                except Exception as e:
                    log_warn(f"Không thể giải mã MICROSOFT_SESSION: {e}")
            elif session_file.exists():
                storage_param = str(session_file)

        if not self.playwright:
            self.playwright = await async_playwright().start()

        headless = False if force_headed else self.config.headless

        viewport = MOBILE_VIEWPORT if is_mobile else DESKTOP_VIEWPORT
        user_agent = MOBILE_UA if is_mobile else DESKTOP_UA

        args = [
            "--disable-blink-features=AutomationControlled",
            "--no-default-browser-check",
            "--disable-infobars",
            "--disable-features=msEdgeAutoSignIn,msForceBrowserSignIn,SingleSignOnPool",
            "--no-first-run",
            "--start-maximized" if not is_mobile else "",
        ]
        args = [a for a in args if a]

        # Try to launch with msedge channel first if configured, fallback to chromium
        launch_channel = self.config.browser_channel if self.config.browser_channel in ["msedge", "chrome"] else None

        try:
            self.context = await self.playwright.chromium.launch_persistent_context(
                user_data_dir=str(profile_dir),
                headless=headless,
                channel=launch_channel,
                user_agent=user_agent,
                viewport=viewport,
                is_mobile=is_mobile,
                has_touch=is_mobile,
                locale="en-US",
                timezone_id="Asia/Ho_Chi_Minh",
                args=args,
                ignore_default_args=["--enable-automation"]
            )
        except Exception as e:
            log_warn(f"Không thể khởi chạy với channel='{launch_channel}': {e}. Đang dùng Chromium mặc định...")
            self.context = await self.playwright.chromium.launch_persistent_context(
                user_data_dir=str(profile_dir),
                headless=headless,
                user_agent=user_agent,
                viewport=viewport,
                is_mobile=is_mobile,
                has_touch=is_mobile,
                locale="en-US",
                timezone_id="Asia/Ho_Chi_Minh",
                args=args,
                ignore_default_args=["--enable-automation"]
            )

        # Inject session cookies if available and not login mode
        if not is_login and session_file.exists():
            try:
                import json
                with open(session_file, "r", encoding="utf-8") as f:
                    state_data = json.load(f)
                cookies = state_data.get("cookies", [])
                if cookies:
                    await self.context.add_cookies(cookies)
            except Exception as e:
                log_warn(f"Lỗi khi nạp cookies vào trình duyệt: {e}")

        # Inject stealth scripts
        await self.context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)

        return self.context

    async def close(self):
        """Close context and playwright instance."""
        try:
            if self.context:
                await self.context.close()
                self.context = None
            if self.playwright:
                await self.playwright.stop()
                self.playwright = None
        except Exception:
            pass
