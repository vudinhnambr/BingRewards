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

    async def dismiss_popups(self):
        """Dismiss common Bing modals, cookie banners, or Copilot prompts that block search."""
        try:
            await self.page.keyboard.press("Escape")
            await asyncio.sleep(0.3)
            dismiss_selectors = [
                "#bnp_btn_accept", "#bnp_btn_reject",
                "button:has-text('Maybe later')", "button:has-text('Để sau')",
                "button:has-text('No thanks')", "button:has-text('Không, cảm ơn')",
                "button:has-text('Got it')", "button:has-text('Đã hiểu')",
                "[aria-label*='Close']", "[aria-label*='Đóng']", ".bnp_close_btn"
            ]
            for sel in dismiss_selectors:
                btn = await self.page.query_selector(sel)
                if btn and await btn.is_visible():
                    try:
                        await btn.click(timeout=1500)
                        await asyncio.sleep(0.5)
                    except Exception:
                        pass
        except Exception:
            pass

    async def ensure_bing_login(self):
        """Ensure session is signed in on Bing Search."""
        try:
            await self.page.goto("https://www.bing.com/", wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(2)
            await self.dismiss_popups()

            needs_login = False
            sign_in_el = await self.page.query_selector("a#id_s, a:has-text('Sign in'), a:has-text('Đăng nhập'), #id_l, #hb_s")
            if sign_in_el and await sign_in_el.is_visible():
                text = (await sign_in_el.text_content() or "").strip().lower()
                if any(k in text for k in ["sign in", "đăng nhập", "login"]):
                    needs_login = True
            elif self.is_mobile:
                # On mobile, verify if user points or profile is visible
                user_id_el = await self.page.query_selector("#id_n, #id_rh, #id_rc, #b_idProviders, .b_idPartner")
                if not user_id_el:
                    hamb = await self.page.query_selector("#mHamburger")
                    if hamb and await hamb.is_visible():
                        await hamb.click()
                        await asyncio.sleep(1)
                        m_signin = await self.page.query_selector("#hb_s, a:has-text('Sign in'), a:has-text('Đăng nhập')")
                        if m_signin and await m_signin.is_visible():
                            needs_login = True
                        await self.page.keyboard.press("Escape")

            if needs_login:
                log_info(f"Đang đồng bộ đăng nhập tài khoản Microsoft trên Bing Search ({'Mobile' if self.is_mobile else 'Desktop'})...")
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
            for selector in [
                "#id_rc", "#rh_meter", ".id_rc", "#id_rh", "#b_id_rc",
                "#rh_anim_container", "[id*='reward'] [class*='point']",
                "[data-bm] [id*='rc']", "#flyout #id_rc", "#b_header #id_rc"
            ]:
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
                    const headerEls = document.querySelectorAll('#b_header, #id_h, header, [class*="header"], [id*="reward"]');
                    for (const header of headerEls) {
                        const all = header.querySelectorAll('*');
                        for (const el of all) {
                            const text = (el.innerText || el.textContent || '').trim();
                            if (/^\d[\d,.]*$/.test(text) && text.length <= 8) {
                                const num = parseInt(text.replace(/[,.\s]/g, ''));
                                if (num > 0 && num < 1000000) {
                                    return text;
                                }
                            }
                        }
                    }
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
                    await self.dismiss_popups()

                    form_code = "QBRE" if i > 1 else "QBLH"
                    fallback_url = f"https://www.bing.com/search?q={urllib.parse.quote_plus(query)}&form={form_code}"
                    search_success = False

                    # Check if search input is directly interactable on current page
                    search_input = await self.page.query_selector("#sb_form_q, input[name='q'], input[type='search']")

                    if search_input and await search_input.is_visible():
                        try:
                            await search_input.click(timeout=2500)
                            await search_input.fill("", timeout=2500)
                            # Type with realistic slow delay
                            await search_input.type(query, delay=random.randint(60, 140))
                            await asyncio.sleep(random.uniform(0.6, 1.2))

                            # CRITICAL: Trigger authentic form submit so Bing processes the query and generates tracking parameters
                            submitted = await self.page.evaluate("""
                                (q) => {
                                    const input = document.querySelector('#sb_form_q') || document.querySelector('input[name="q"]');
                                    if (input) {
                                        input.value = q;
                                        input.dispatchEvent(new Event('input', { bubbles: true }));
                                        input.dispatchEvent(new Event('change', { bubbles: true }));
                                    }
                                    const form = document.querySelector('#sb_form') || document.querySelector('form');
                                    if (form) {
                                        form.submit();
                                        return true;
                                    }
                                    return false;
                                }
                            """, query)

                            if submitted:
                                try:
                                    await self.page.wait_for_load_state("domcontentloaded", timeout=15000)
                                except Exception:
                                    pass
                                search_success = True
                        except Exception as input_err:
                            log_warn(f"Không thể submit qua form: {input_err}. Chuyển sang URL trực tiếp...")
                            await self.page.keyboard.press("Escape")
                            search_success = False

                    if not search_success or "search?q=" not in self.page.url:
                        await self.page.goto(fallback_url, wait_until="domcontentloaded", timeout=30000)

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
                    if points != "N/A":
                        log_info(f"[{i}/{len(words)}] Tìm kiếm: '{query}' | Điểm hiện tại: [bold green]{points}[/bold green]")
                    else:
                        log_info(f"[{i}/{len(words)}] Tìm kiếm: '{query}'")

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
