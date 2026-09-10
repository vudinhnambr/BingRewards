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
            await asyncio.sleep(2)

            sign_in_el = await self.page.query_selector("a#id_s, a:has-text('Sign in'), a:has-text('Đăng nhập'), #id_l")
            if sign_in_el and await sign_in_el.is_visible():
                text = (await sign_in_el.text_content() or "").strip().lower()
                if any(k in text for k in ["sign in", "đăng nhập", "login"]):
                    log_info("Đang đồng bộ đăng nhập tài khoản Microsoft trên Bing Search...")
                    await self.page.goto(
                        "https://www.bing.com/fd/auth/signin?action=interactive&provider=windows_live_id&return_url=https%3A%2F%2Fwww.bing.com%2F",
                        wait_until="domcontentloaded",
                        timeout=30000
                    )
                    await asyncio.sleep(3)
        except Exception as e:
            log_warn(f"Lỗi khi đồng bộ đăng nhập Bing: {e}")

    async def get_current_points(self) -> str:
        """Attempt to extract current points counter from Bing header."""
        try:
            # Strategy 1: Try known selectors
            for selector in ["#id_rc", "#rh_meter", ".id_rc", "#id_rh", "#b_id_rc", "#rh_anim_container", "[id*='reward'] [class*='point']", "[data-bm] [id*='rc']"]:
                el = await self.page.query_selector(selector)
                if el:
                    text = (await el.text_content() or "").strip()
                    if text and any(c.isdigit() for c in text):
                        m = re.search(r"[\d,.]+", text)
                        if m:
                            return m.group(0)

            # Strategy 2: JavaScript scan for points-related elements in header
            points_text = await self.page.evaluate(r"""
                () => {
                    // Look for elements containing "points" or "pts" text in the header area
                    const headerEls = document.querySelectorAll('#b_header, #id_h, header, [class*="header"], [id*="reward"]');
                    for (const header of headerEls) {
                        const all = header.querySelectorAll('*');
                        for (const el of all) {
                            const text = (el.innerText || el.textContent || '').trim();
                            // Match standalone numbers (likely points counter)
                            if (/^\d[\d,.]*$/.test(text) && text.length <= 8) {
                                const num = parseInt(text.replace(/[,.\s]/g, ''));
                                if (num > 0 && num < 1000000) {
                                    return text;
                                }
                            }
                        }
                    }
                    // Fallback: search entire page for rewards counter patterns
                    const allEls = document.querySelectorAll('[id*="rc"], [id*="point"], [class*="point"], [class*="reward"]');
                    for (const el of allEls) {
                        const text = (el.innerText || el.textContent || '').trim();
                        if (/^\d[\d,.]*$/.test(text) && text.length <= 8) {
                            const num = parseInt(text.replace(/[,.\s]/g, ''));
                            if (num > 0 && num < 1000000) return text;
                        }
                    }
                    return null;
                }
            """)
            if points_text:
                return points_text.strip()
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
                        await random_delay(self.config.min_delay_sec, self.config.max_delay_sec)

                except Exception as e:
                    log_warn(f"Lỗi ở lượt tìm kiếm #{i} ('{query}'): {e}")
                    await asyncio.sleep(3)

                progress.update(task_id, advance=1)

        log_success(f"Hoàn thành {len(words)} lượt tìm kiếm {mode_str}!")
