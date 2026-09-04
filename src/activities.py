import asyncio
import re
import random
from typing import Dict, List, Any
from playwright.async_api import Page, BrowserContext
from src.config import BotConfig
from src.utils import log_info, log_success, log_warn, random_delay

class RewardsDashboard:
    """Solves Daily Set and More Activities on Microsoft Rewards dashboard (Supports 2026 UI & Classic UI)."""

    def __init__(self, page: Page, context: BrowserContext, config: BotConfig):
        self.page = page
        self.context = context
        self.config = config

    async def open_dashboard(self) -> bool:
        """Navigate to rewards dashboard and check authentication."""
        log_info("Đang truy cập https://rewards.bing.com/dashboard ...")
        try:
            await self.page.goto("https://rewards.bing.com/dashboard", wait_until="domcontentloaded", timeout=45000)
            await asyncio.sleep(4)

            # Check if redirected to welcome or login page
            if "login.live.com" in self.page.url or "welcome" in self.page.url.lower():
                log_warn("Trình duyệt đang ở trang Welcome/Đăng nhập (Chưa đăng nhập tài khoản Microsoft)!")
                return False

            return True
        except Exception as e:
            log_warn(f"Không thể tải trang dashboard: {e}")
            return False

    async def get_account_summary(self) -> Dict[str, Any]:
        """Scrape account overview (available points, streak, level, etc.)."""
        summary = {"points": "N/A", "streak": "0", "level": "Member"}
        try:
            # Method 1: Modern 2026 UI extraction
            points_data = await self.page.evaluate(r"""
                () => {
                    const all = Array.from(document.querySelectorAll('*'));
                    for (let i = 0; i < all.length; i++) {
                        const text = (all[i].innerText || all[i].textContent || '').trim();
                        if (text === 'Available points' || text === 'Điểm khả dụng') {
                            let p = all[i].parentElement;
                            if (p) {
                                const nums = p.innerText.match(/\d[\d,.]*/g);
                                if (nums) return nums[0];
                            }
                        }
                    }
                    return null;
                }
            """)
            if points_data:
                summary["points"] = points_data

            # Method 2: Classic UI selectors fallback
            if summary["points"] == "N/A":
                selectors = [
                    "mee-rewards-counter-animation span",
                    ".pointsDetail",
                    ".pointsValue",
                    "#userPointsHeader"
                ]
                for sel in selectors:
                    el = await self.page.query_selector(sel)
                    if el:
                        text = (await el.text_content() or "").strip()
                        m = re.search(r"[\d,.]+", text)
                        if m and not any(w in text.lower() for w in ["earn", "how", "streak"]):
                            summary["points"] = m.group(0)
                            break

            # Streak & Level
            streak_el = await self.page.query_selector(".streak-count, [aria-label*='streak'], mee-rewards-streak-status")
            if streak_el:
                streak_text = (await streak_el.text_content() or "").strip()
                m_streak = re.search(r"\d+", streak_text)
                if m_streak:
                    summary["streak"] = m_streak.group(0)

        except Exception:
            pass
        return summary

    async def claim_ready_points(self):
        """Claim points that are marked 'Ready to claim' / 'Claim points' in drawer."""
        try:
            # 1. Click 'Ready to claim' or 'Claim points' buttons
            claim_btns = await self.page.query_selector_all("button:has-text('Claim points'), button:has-text('Claim'), button:has-text('Nhận')")
            for btn in claim_btns:
                txt = (await btn.text_content() or "").strip()
                if txt and ("claim" in txt.lower() or "nhận" in txt.lower()):
                    log_info(f"🎁 Bấm nút: '{txt}'")
                    try:
                        await btn.click()
                        await asyncio.sleep(2)
                    except Exception:
                        pass

            # 2. Check if the 'Claim points' side drawer is open, click the main black 'Claim points' button inside it
            drawer_claim_btn = await self.page.query_selector("button:has-text('Claim points')")
            if drawer_claim_btn and await drawer_claim_btn.is_visible():
                log_info("🎁 Bấm 'Claim points' trong khung nhận thưởng...")
                await drawer_claim_btn.click()
                await asyncio.sleep(2)

            # 3. Close the drawer (Click 'X' or press Escape) so it doesn't block the screen
            close_btn = await self.page.query_selector("[aria-label*='Close'], [aria-label*='close'], button:has(svg[data-icon-name*='Cancel']), button:has(svg[data-icon-name*='Dismiss'])")
            if close_btn and await close_btn.is_visible():
                await close_btn.click()
                await asyncio.sleep(1)
            else:
                await self.page.keyboard.press("Escape")
                await asyncio.sleep(1)

        except Exception as e:
            log_warn(f"Lỗi khi nhận điểm thưởng: {e}")

    async def solve_all_activities(self):
        """Find and solve all uncompleted cards across modern and classic dashboard."""
        log_info("Đang quét các thẻ nhiệm vụ và hoạt động kiếm điểm...")
        
        # 1. Claim ready points first
        await self.claim_ready_points()

        # 2. Expand accordion sections (Your progress, Daily set, Your activity, Achievements)
        try:
            accordions = await self.page.query_selector_all("div[class*='cursor-pointer'], button[class*='w-full'], [role='button']")
            for acc in accordions:
                text = (await acc.text_content() or "").strip()
                # If section has uncompleted points (e.g. +5 without checkmark)
                if any(k in text for k in ["Achievements", "Daily set", "Your activity", "Your progress"]):
                    # If not already has checkmark svg
                    has_check = await acc.query_selector("svg[class*='check'], [class*='check'], span[class*='check']")
                    if not has_check:
                        log_info(f"Mở rộng mục: '{text.splitlines()[0]}'")
                        try:
                            await acc.click()
                            await asyncio.sleep(1.5)
                        except Exception:
                            pass
        except Exception:
            pass

        # 3. Modern 2026 UI Cards (+10, +25, +5, +50)
        try:
            modern_badges = await self.page.query_selector_all("div:has-text('+10'), div:has-text('+25'), div:has-text('+5'), div:has-text('+50'), div:has-text('+15')")
            log_info(f"Tìm thấy {len(modern_badges)} mục điểm hoạt động trên Dashboard.")

            processed_texts = set()
            for idx, badge in enumerate(modern_badges, start=1):
                try:
                    # Find clickable parent card
                    card = await badge.evaluate_handle(r"""
                        (el) => {
                            let curr = el;
                            while (curr && curr !== document.body) {
                                if (curr.tagName === 'A' || curr.tagName === 'BUTTON' || curr.getAttribute('role') === 'button' || curr.classList.contains('cursor-pointer') || (curr.className && curr.className.includes('p-paddingCardBody'))) {
                                    return curr;
                                }
                                curr = curr.parentElement;
                            }
                            return el;
                        }
                    """)
                    
                    if not card:
                        continue

                    card_elem = card.as_element()
                    if not card_elem:
                        continue

                    raw_text = (await card_elem.inner_text() or "").strip()
                    title = raw_text.split("\n")[0].strip()
                    if not title or title in processed_texts:
                        continue
                    processed_texts.add(title)

                    # Check if already completed (contains checkmark icon)
                    is_done = await card_elem.query_selector("svg, [class*='check'], [aria-label*='completed'], [class*='statusSuccess']")
                    # If already checked with green tick, skip
                    if "✓" in raw_text:
                        log_info(f"✓ Nhiệm vụ [{title}] đã có tích xanh.")
                        continue

                    log_info(f"-> Đang thực hiện: '{title}'...")
                    await self._process_card(card_elem)
                    await random_delay(3.0, 5.0)

                except Exception as e:
                    log_warn(f"Lỗi khi xử lý thẻ #{idx}: {e}")

        except Exception as e:
            log_warn(f"Lỗi quét hoạt động: {e}")


        # 3. Classic Dashboard Cards (#daily-sets, mee-card)
        try:
            classic_cards = await self.page.query_selector_all("#daily-sets .c-card, mee-card.c-card, #more-activities .c-card")
            for idx, card in enumerate(classic_cards, start=1):
                try:
                    is_completed = await card.query_selector(".mee-icon-SkypeCircleCheck, .completed, [aria-label*='completed']")
                    if is_completed:
                        continue
                    title_el = await card.query_selector("h3, .c-heading, .title")
                    title = (await title_el.text_content() if title_el else f"Nhiệm vụ classic #{idx}").strip()

                    log_info(f"-> Đang thực hiện nhiệm vụ: '{title}'...")
                    await self._process_card(card)
                    await random_delay(3.0, 5.0)
                except Exception:
                    pass
        except Exception:
            pass

    async def solve_daily_set(self):
        """Unified runner for Daily Set and modern tasks."""
        await self.solve_all_activities()

    async def solve_more_activities(self):
        """Unified runner for more activities."""
        pass

    async def _process_card(self, card_element):
        """Click on card, handle new tab or quiz/poll interaction."""
        initial_pages = len(self.context.pages)

        # Click the action link or card
        click_target = await card_element.query_selector("a, button, [role='button']")
        target = click_target or card_element

        try:
            await target.click()
        except Exception:
            await self.page.evaluate("(el) => el.click()", target)

        await asyncio.sleep(3)

        # Check if a new tab opened
        pages = self.context.pages
        if len(pages) > initial_pages:
            new_page = pages[-1]
            try:
                await new_page.wait_for_load_state("domcontentloaded", timeout=20000)
                await self._handle_activity_page(new_page)
            finally:
                try:
                    await new_page.close()
                except Exception:
                    pass
                await self.page.bring_to_front()
        else:
            await self._handle_activity_page(self.page)

    async def _handle_activity_page(self, page: Page):
        """Handle quiz, poll, or standard click-and-wait task on page."""
        await asyncio.sleep(2)

        # 1. Check for Poll (Bình chọn)
        poll_options = await page.query_selector_all("#btoption0, #btoption1, .btOption, [id^='btoption']")
        if poll_options:
            log_info("Phát hiện Poll (Bình chọn), đang chọn đáp án ngẫu nhiên...")
            chosen = random.choice(poll_options)
            await chosen.click()
            await asyncio.sleep(3)
            return

        # 2. Check for Quiz / Trivia
        start_quiz_btn = await page.query_selector("#rqStartQuiz, #rqAnswerOption0, .wk_OptionClickClass, [id^='rqAnswerOption']")
        if start_quiz_btn:
            log_info("Phát hiện Quiz (Trắc nghiệm), đang tự động trả lời...")
            start_btn = await page.query_selector("#rqStartQuiz")
            if start_btn and await start_btn.is_visible():
                await start_btn.click()
                await asyncio.sleep(2)

            for _ in range(12):
                options = await page.query_selector_all("[id^='rqAnswerOption'], .wk_OptionClickClass, .rqOption")
                if not options:
                    break

                for opt in options:
                    try:
                        if await opt.is_visible():
                            await opt.click()
                            await asyncio.sleep(1.2)
                    except Exception:
                        pass

                complete_el = await page.query_selector(".rqComplete, #quizCompleteMessage")
                if complete_el and await complete_el.is_visible():
                    log_success("Đã hoàn thành Quiz!")
                    break
                await asyncio.sleep(2)
            return

        # 3. Simple click-through / explore page
        await page.evaluate("window.scrollBy(0, 300)")
        await asyncio.sleep(random.uniform(3.0, 5.0))
