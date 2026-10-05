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
    """Performs natural searches on Bing to accumulate points with anti-detection and cooldown handling."""

    def __init__(self, page: Page, config: BotConfig, is_mobile: bool = False):
        self.page = page
        self.config = config
        self.is_mobile = is_mobile

    async def safe_goto(self, url: str, timeout: int = 30000, retries: int = 2) -> bool:
        """Safely navigate to URL with retry against net::ERR_ABORTED and timeouts."""
        for attempt in range(1, retries + 1):
            try:
                await self.page.goto(url, wait_until="domcontentloaded", timeout=timeout)
                await asyncio.sleep(1.0)
                return True
            except Exception as e:
                err_msg = str(e)
                if ("ERR_ABORTED" in err_msg or "net::ERR" in err_msg or "Timeout" in err_msg) and attempt < retries:
                    log_warn(f"Điều hướng tới '{url[:60]}' gặp sự cố ({err_msg[:60]}), đang thử lại lần {attempt + 1}...")
                    await asyncio.sleep(2.0)
                    continue
                log_warn(f"Không thể tải trang '{url[:60]}': {err_msg[:80]}")
                return False
        return False

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
                "button:has-text('Stay signed out')", "button:has-text('Duy trì đăng xuất')",
                "[aria-label*='Close']", "[aria-label*='Đóng']", ".bnp_close_btn",
                "#id_cancel", "#bep_close"
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
            await self.safe_goto("https://www.bing.com/", timeout=30000)
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
                await self.safe_goto(
                    "https://www.bing.com/fd/auth/signin?action=interactive&provider=windows_live_id&return_url=https%3A%2F%2Fwww.bing.com%2F",
                    timeout=30000
                )
                await asyncio.sleep(3)
                try:
                    await self.page.wait_for_load_state("domcontentloaded", timeout=15000)
                except Exception:
                    pass
        except Exception as e:
            log_warn(f"Lỗi khi đồng bộ đăng nhập Bing: {e}")

    async def get_current_points(self) -> str:
        """Attempt to extract current points counter from Bing header."""
        try:
            # Strategy 1: Try known selectors
            for selector in [
                "#id_rc", "#rh_meter", ".id_rc", "#id_rh", "#b_id_rc",
                "#rh_anim_container", "[id*='reward'] [class*='point']",
                "[data-bm] [id*='rc']", "#flyout #id_rc", "#b_header #id_rc",
                "#mHamburger #id_rc", ".b_idPartner #id_rc"
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

    async def _simulate_human_reading(self):
        """Simulate realistic human scrolling and interaction with search results."""
        try:
            # 1. Random scroll down
            scroll_dist = random.randint(350, 750)
            await self.page.evaluate(f"window.scrollBy({{top: {scroll_dist}, behavior: 'smooth'}})")
            await asyncio.sleep(random.uniform(1.2, 2.8))

            # 2. Occasional hover on a search headline
            if not self.is_mobile and random.random() < 0.6:
                links = await self.page.query_selector_all("#b_results h2 a, #b_results .b_algo h2")
                if links:
                    target_link = random.choice(links[:4])
                    if await target_link.is_visible():
                        await target_link.hover()
                        await asyncio.sleep(random.uniform(0.5, 1.2))

            # 3. Occasional scroll back up slightly
            if random.random() < 0.5:
                scroll_up = random.randint(120, 280)
                await self.page.evaluate(f"window.scrollBy({{top: -{scroll_up}, behavior: 'smooth'}})")
                await asyncio.sleep(random.uniform(0.8, 1.6))
        except Exception:
            pass

    async def run_searches(self, target_count: int):
        """Execute search loop with natural human simulation, retry logic, and cooldown warnings."""
        mode_str = "Mobile" if self.is_mobile else "Desktop"
        log_info(f"Bắt đầu chuỗi tìm kiếm {mode_str} ({target_count} lượt)...")

        # 1. Ensure user is logged in to Bing
        await self.ensure_bing_login()
        await asyncio.sleep(1.5)

        words = WordGenerator.generate_words(target_count)

        last_points = None
        stagnant_count = 0
        cooldown_warned = False

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
                            await asyncio.sleep(random.uniform(0.2, 0.5))
                            await search_input.fill("", timeout=2500)
                            
                            # Type with human typing latency
                            await search_input.type(query, delay=random.randint(50, 120))
                            await asyncio.sleep(random.uniform(0.5, 1.2))

                            # Human Enter press
                            await search_input.press("Enter")
                            try:
                                await self.page.wait_for_load_state("domcontentloaded", timeout=15000)
                            except Exception:
                                pass
                            search_success = True
                        except Exception as input_err:
                            log_warn(f"Không thể gõ trực tiếp vào ô tìm kiếm: {input_err}. Đang mở URL...")
                            search_success = False

                    if not search_success or "search?q=" not in self.page.url:
                        await self.safe_goto(fallback_url, timeout=25000, retries=2)

                    # Simulate realistic reading & scrolling
                    await self._simulate_human_reading()

                    # Points tracking & Cooldown inspection
                    points = await self.get_current_points()
                    if points != "N/A":
                        log_info(f"[{i}/{len(words)}] Tìm kiếm: '{query}' | Điểm hiện tại: [bold green]{points}[/bold green]")
                        if last_points is not None:
                            if points == last_points:
                                stagnant_count += 1
                                if stagnant_count >= 5 and not cooldown_warned:
                                    log_warn("[WARN] ⚠️ Điểm không tăng sau 5 lượt tìm kiếm liên tiếp (Có thể do Microsoft đang bật Cooldown 15 phút hoặc đã đạt hạn mức ngày).")
                                    cooldown_warned = True
                            else:
                                stagnant_count = 0
                                cooldown_warned = False
                        last_points = points
                    else:
                        log_info(f"[{i}/{len(words)}] Tìm kiếm: '{query}'")

                    # Batch cooldown (Giãn cách an toàn sau mỗi đợt)
                    if self.config.search_cooldown_batch_size > 0 and i % self.config.search_cooldown_batch_size == 0 and i < len(words):
                        cooldown = self.config.search_cooldown_wait_sec + random.uniform(2.0, 5.0)
                        log_info(f"Nghỉ giãn cách batch sau {self.config.search_cooldown_batch_size} lượt: {cooldown:.1f}s...")
                        await asyncio.sleep(cooldown)
                    else:
                        await random_delay(self.config.min_delay_sec, self.config.max_delay_sec)

                except Exception as e:
                    log_warn(f"Lỗi ở lượt tìm kiếm #{i} ('{query}'): {e}")
                    await asyncio.sleep(2.0)

                progress.update(task_id, advance=1)

        log_success(f"Hoàn thành {len(words)} lượt tìm kiếm {mode_str}!")
