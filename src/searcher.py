import random
import asyncio
import re
import urllib.parse
from playwright.async_api import Page
from src.config import BotConfig
from src.word_generator import WordGenerator
from src.utils import log_info, log_success, log_warn, random_delay, console
from rich.progress import Progress, BarColumn, TextColumn, TimeRemainingColumn

class BingSearcher:
    """Performs natural searches on Bing to accumulate points."""

    def __init__(self, page: Page, config: BotConfig, is_mobile: bool = False):
        self.page = page
        self.config = config
        self.is_mobile = is_mobile

    async def ensure_bing_login(self):
        """Ensure session is signed in on Bing Search."""
        try:
            await self.page.goto("https://www.bing.com/", wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(3)

            # Check if already logged in (user avatar or rewards counter visible)
            logged_in = await self.page.evaluate(r"""
                () => {
                    // Check for signed-in indicators
                    const avatar = document.querySelector('#id_s img, #id_n, .b_scopebar #id_n, [id*="id_n"], #id_rh');
                    const signIn = document.querySelector('#id_s, a[href*="signin"], a[href*="login"]');
                    if (avatar) return true;
                    if (signIn) {
                        const text = (signIn.textContent || signIn.innerText || '').toLowerCase();
                        // If text contains points number or user name, we're signed in
                        if (/\d/.test(text) && !text.includes('sign') && !text.includes('đăng')) return true;
                    }
                    return false;
                }
            """)

            if logged_in:
                log_info("Đã đăng nhập Bing Search.")
                return

            # Not logged in - try to sign in
            log_info("Chưa đăng nhập Bing Search, đang thử đăng nhập...")
            sign_in_el = await self.page.query_selector("a#id_s, a:has-text('Sign in'), a:has-text('Đăng nhập'), #id_l")
            if sign_in_el and await sign_in_el.is_visible():
                await sign_in_el.click()
                await asyncio.sleep(3)
            else:
                # Try direct auth URL
                await self.page.goto(
                    "https://www.bing.com/fd/auth/signin?action=interactive&provider=windows_live_id&return_url=https%3A%2F%2Fwww.bing.com%2F",
                    wait_until="domcontentloaded",
                    timeout=30000
                )
                await asyncio.sleep(3)

            # Verify login
            current_url = self.page.url
            if "login.live.com" in current_url or "login.microsoftonline.com" in current_url:
                log_warn(f"Bing login redirect to auth page: {current_url[:80]}")
            else:
                # Check if login succeeded
                points = await self.get_current_points()
                if points != "N/A":
                    log_info(f"Đăng nhập Bing Search thành công. Điểm: {points}")
                else:
                    log_warn("Đăng nhập Bing Search không xác nhận được (điểm = N/A)")

        except Exception as e:
            log_warn(f"Lỗi khi đồng bộ đăng nhập Bing: {e}")

    async def get_current_points(self) -> str:
        """Attempt to extract current points counter from Bing header."""
        try:
            for selector in ["#id_rc", "#rh_meter", ".id_rc", "#id_rh", "#b_id_rc", "#id_s", "#rh_anim_container"]:
                el = await self.page.query_selector(selector)
                if el:
                    text = (await el.text_content() or "").strip()
                    if text and any(c.isdigit() for c in text):
                        m = re.search(r"[\d,.]+", text)
                        if m:
                            return m.group(0)
        except Exception:
            pass
        return "N/A"

    async def run_searches(self, target_count: int):
        """Execute search loop with random delays and human-like actions."""
        mode_str = "Mobile" if self.is_mobile else "Desktop"
        log_info(f"Bắt đầu chuỗi tìm kiếm {mode_str} ({target_count} lượt)...")

        # 1. Ensure user is logged in to Bing
        await self.ensure_bing_login()

        words = WordGenerator.generate_words(target_count)

        with Progress(
            TextColumn(f"[bold blue]{mode_str} Search:"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TextColumn("({task.completed}/{task.total})"),
            TimeRemainingColumn(),
            console=console
        ) as progress:
            task_id = progress.add_task("searching", total=len(words))

            for i, query in enumerate(words, start=1):
                try:
                    # Check if search input is directly interactable on current page
                    search_input = await self.page.query_selector("#sb_form_q, input[name='q'], input[type='search']")
                    
                    if search_input and await search_input.is_visible():
                        await search_input.click()
                        await search_input.fill("")
                        # Type with realistic slow delay
                        await search_input.type(query, delay=random.randint(80, 200))
                        await asyncio.sleep(random.uniform(1.2, 3.0))
                        await self.page.keyboard.press("Enter")
                        try:
                            await self.page.wait_for_load_state("domcontentloaded", timeout=20000)
                        except Exception:
                            pass
                    else:
                        search_url = f"https://www.bing.com/search?q={urllib.parse.quote_plus(query)}"
                        await self.page.goto(search_url, wait_until="domcontentloaded", timeout=30000)

                    # Simulate human scrolling down and slightly up
                    try:
                        scroll_distance = random.randint(300, 700)
                        await self.page.evaluate(f"window.scrollBy(0, {scroll_distance})")
                        await asyncio.sleep(random.uniform(1.5, 3.0))
                        
                        if random.choice([True, False]):
                            await self.page.evaluate(f"window.scrollBy(0, -{random.randint(100, 300)})")
                            await asyncio.sleep(random.uniform(1.0, 2.0))
                    except Exception:
                        pass

                    points = await self.get_current_points()
                    log_info(f"[{i}/{len(words)}] Tìm kiếm: '{query}' | Điểm hiện tại: [bold green]{points}[/bold green]")

                    # Batch cooldown (Microsoft occasionally restricts searches in short windows)
                    if self.config.search_cooldown_batch_size > 0 and i % self.config.search_cooldown_batch_size == 0 and i < len(words):
                        cooldown = self.config.search_cooldown_wait_sec + random.uniform(2, 5)
                        log_info(f"Nghỉ giãn cách batch sau {self.config.search_cooldown_batch_size} lượt: {cooldown:.1f}s...")
                        await asyncio.sleep(cooldown)
                    else:
                        await random_delay(self.config.min_delay_sec + 3.0, self.config.max_delay_sec + 8.0)

                except Exception as e:
                    log_warn(f"Lỗi ở lượt tìm kiếm #{i} ('{query}'): {e}")
                    await asyncio.sleep(3)

                progress.update(task_id, advance=1)

        log_success(f"Hoàn thành {len(words)} lượt tìm kiếm {mode_str}!")
