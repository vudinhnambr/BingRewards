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

            # Robust check for sign-in state on Bing (both Desktop & Mobile)
            is_signed_in = await self.page.evaluate(r"""
                () => {
                    // 1. Check for logged-in profile name or identity container with non-empty text
                    const userEl = document.querySelector('#id_n, .id_n, #hb_n, [data-bm] #id_n');
                    if (userEl && (userEl.innerText || userEl.textContent || '').trim().length > 0) {
                        return true;
                    }
                    // 2. Check for rewards points element with valid numbers
                    const pointsEl = document.querySelector('#id_rc, #b_id_rc, .id_rc, #id_rh, #hb_rc');
                    if (pointsEl) {
                        const txt = (pointsEl.innerText || pointsEl.textContent || '').trim();
                        if (/\d+/.test(txt)) return true;
                    }
                    // 3. Explicit sign in buttons indicate definitely not signed in
                    const signInBtn = document.querySelector('#id_s, #hb_s, a[href*="fd/auth/signin"]');
                    if (signInBtn) {
                        const txt = (signInBtn.innerText || signInBtn.textContent || '').toLowerCase();
                        if (txt.includes('sign in') || txt.includes('đăng nhập') || txt.includes('login')) {
                            return false;
                        }
                    }
                    return false;
                }
            """)

            # On mobile, double check flyout menu if sign-in status is still uncertain
            if not is_signed_in and self.is_mobile:
                try:
                    hamb = await self.page.query_selector("#mHamburger")
                    if hamb and await hamb.is_visible():
                        await hamb.click()
                        await asyncio.sleep(0.8)
                        flyout_signed_in = await self.page.evaluate(r"""
                            () => {
                                const signIn = document.querySelector('#hb_s, a[href*="fd/auth/signin"]');
                                if (signIn) {
                                    const t = (signIn.innerText || '').toLowerCase();
                                    if (t.includes('sign in') || t.includes('đăng nhập') || t.includes('login')) return false;
                                }
                                const user = document.querySelector('#hb_n, #id_n, #hb_rc, #id_rc');
                                if (user && (user.innerText || '').trim().length > 0) return true;
                                return false;
                            }
                        """)
                        await self.page.keyboard.press("Escape")
                        await asyncio.sleep(0.5)
                        is_signed_in = flyout_signed_in
                except Exception:
                    pass

            if not is_signed_in:
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
                await self.dismiss_popups()
        except Exception as e:
            log_warn(f"Lỗi khi đồng bộ đăng nhập Bing: {e}")

    async def get_current_points(self) -> str:
        """Attempt to extract current points counter from Bing header."""
        try:
            # Strategy 1: Try known selectors (including mobile header & hamburger flyout)
            for selector in [
                "#id_rc", "#rh_meter", ".id_rc", "#id_rh", "#b_id_rc",
                "#rh_anim_container", "[id*='reward'] [class*='point']",
                "[data-bm] [id*='rc']", "#flyout #id_rc", "#b_header #id_rc",
                "#mHamburger #id_rc", ".b_idPartner #id_rc", "#hb_rc",
                ".b_idPartner #hb_rc", "#flyout #hb_rc", "[aria-label*='points' i]",
                "[aria-label*='điểm' i]"
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
                    const headerEls = document.querySelectorAll('#b_header, #id_h, header, [class*="header"], [id*="reward"], #flyout, #mHamburger, .b_idPartner');
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
                            
                            # Verify if the navigation actually occurred for this query
                            curr_url = urllib.parse.unquote_plus(self.page.url).lower()
                            if "search?q=" in self.page.url and any(w.lower() in curr_url for w in query.split()[:2]):
                                search_success = True
                            else:
                                search_success = False
                        except Exception as input_err:
                            log_warn(f"Không thể gõ trực tiếp vào ô tìm kiếm: {input_err}. Đang mở URL...")
                            search_success = False

                    if not search_success:
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
                                if stagnant_count >= 5:
                                    log_warn(f"[COOLDOWN] ⚠️ Điểm không tăng sau {stagnant_count} lượt tìm kiếm liên tiếp (đã đạt giới hạn ngày hoặc đang trong Cooldown 15 phút của Microsoft).")
                                    log_warn(f"🛑 Tự động dừng sớm chuỗi tìm kiếm {mode_str} tại lượt {i}/{len(words)} để tránh spam và bảo vệ tài khoản khỏi bị phạt.")
                                    progress.update(task_id, completed=len(words))
                                    break
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
