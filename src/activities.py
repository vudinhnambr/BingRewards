import asyncio
import re
import random
from typing import Dict, List, Any
from playwright.async_api import Page, BrowserContext
from src.config import BotConfig
from src.utils import log_info, log_success, log_warn, random_delay

class RewardsDashboard:
    """Solves Daily Set, Side Drawers, Streaks, Quizzes, Polls and More Activities on Microsoft Rewards 2026 & Classic UI."""

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

    async def close_any_drawer(self):
        """Close any opened slide drawer or modal overlay."""
        try:
            close_buttons = await self.page.query_selector_all(
                "[aria-label*='Close'], [aria-label*='close'], button:has(svg[data-icon-name*='Cancel']), "
                "button:has(svg[data-icon-name*='Dismiss']), button:has-text('Close'), button:has-text('Đóng')"
            )
            for btn in close_buttons:
                if await btn.is_visible():
                    try:
                        await btn.click()
                        await asyncio.sleep(1)
                    except Exception:
                        pass
            # Fallback Escape key
            await self.page.keyboard.press("Escape")
            await asyncio.sleep(0.5)
        except Exception:
            pass

    async def handle_drawer_actions(self):
        """Perform action buttons inside an opened side drawer (Check-in, Activate, Claim, Solve items)."""
        await asyncio.sleep(1.5)

        # 1. Action Buttons in Drawers (Check-in now, Activate streak, Claim points, Search now)
        action_selectors = [
            ("Check-in now", "button:has-text('Check-in now'), button:has-text('Check-in'), button:has-text('Điểm danh')"),
            ("Activate streak", "button:has-text('Activate streak'), button:has-text('Activate'), button:has-text('Kích hoạt')"),
            ("Claim points", "button:has-text('Claim points'), button:has-text('Claim'), button:has-text('Nhận điểm')"),
            ("Search now", "button:has-text('Search now'), button:has-text('Tìm kiếm ngay')")
        ]

        for action_name, sel in action_selectors:
            btn = await self.page.query_selector(sel)
            if btn and await btn.is_visible():
                log_info(f"✨ Bấm nút trong ngăn kéo (Side Drawer): '[bold cyan]{action_name}[/bold cyan]'")
                try:
                    await btn.click()
                    await asyncio.sleep(3)
                except Exception:
                    pass

        # 2. Daily Set / Activity Items inside the Side Drawer
        drawer_cards = await self.page.query_selector_all(
            "div:has-text('+10'), div:has-text('+15'), div:has-text('+5'), div:has-text('+30'), div:has-text('+50')"
        )
        for badge in drawer_cards:
            try:
                card = await badge.evaluate_handle(r"""
                    (el) => {
                        let curr = el;
                        while (curr && curr !== document.body) {
                            if (curr.tagName === 'A' || curr.tagName === 'BUTTON' || curr.getAttribute('role') === 'button' || (curr.className && String(curr.className).includes('Card'))) {
                                return curr;
                            }
                            curr = curr.parentElement;
                        }
                        return el;
                    }
                """)
                if card:
                    card_elem = card.as_element()
                    if card_elem and await card_elem.is_visible():
                        text = (await card_elem.inner_text() or "").strip()
                        # Skip if completed
                        if "✓" in text or "completed" in text.lower():
                            continue
                        first_line = text.split("\n")[0].strip()
                        if first_line and not any(w in first_line for w in ["Daily set", "Your progress"]):
                            log_info(f"-> Đang thực hiện nhiệm vụ trong ngăn kéo: '{first_line}'...")
                            await self._process_card(card_elem)
                            await random_delay(2.5, 4.5)
            except Exception:
                pass

        # Close the drawer after processing
        await self.close_any_drawer()

    async def solve_all_activities(self):
        """Find and solve all uncompleted cards across modern 2026 and classic dashboard."""
        log_info("Đang quét các thẻ nhiệm vụ và hoạt động kiếm điểm...")

        # 1. Expand all accordion sections (Your progress, Daily set, Your activity, Achievements)
        try:
            accordions = await self.page.query_selector_all(
                "div[class*='cursor-pointer'], button[class*='w-full'], [role='button']"
            )
            for acc in accordions:
                text = (await acc.text_content() or "").strip()
                if any(k in text for k in ["Daily set", "Your activity", "Your progress", "Achievements", "Get started"]):
                    has_check = await acc.query_selector("svg[class*='check'], [class*='check'], span[class*='check']")
                    if not has_check:
                        try:
                            await acc.click()
                            await asyncio.sleep(1)
                        except Exception:
                            pass
        except Exception:
            pass

        # 2. Process 'Your activity' interactive tiles (Bing, Daily Set, Edge, Mobile App, Visual Search)
        try:
            activity_tiles = await self.page.query_selector_all(
                "div:has-text('Bing'), div:has-text('Daily Set'), div:has-text('Edge'), div:has-text('Mobile App'), div:has-text('Visual Search')"
            )
            for tile in activity_tiles:
                try:
                    tile_box = await tile.evaluate_handle(r"""
                        (el) => {
                            let curr = el;
                            while (curr && curr !== document.body) {
                                if (curr.tagName === 'A' || curr.tagName === 'BUTTON' || (curr.className && String(curr.className).includes('Card')) || curr.classList.contains('cursor-pointer')) {
                                    return curr;
                                }
                                curr = curr.parentElement;
                            }
                            return el;
                        }
                    """)
                    if tile_box:
                        tile_elem = tile_box.as_element()
                        if tile_elem and await tile_elem.is_visible():
                            tile_text = (await tile_elem.inner_text() or "").strip()
                            if "How to activate" in tile_text or "Check-in" in tile_text or "Activity" in tile_text or "Search" in tile_text:
                                log_info(f"👉 Mở bảng hoạt động: '{tile_text.splitlines()[0]}'")
                                await tile_elem.click()
                                await self.handle_drawer_actions()
                except Exception:
                    pass
        except Exception:
            pass

        # 3. Process 'Get started with Rewards' Onboarding Cards (Search 1 time, Set goal, Browse Earn page...)
        try:
            onboarding_cards = await self.page.query_selector_all(
                "div:has-text('Search 1 time'), div:has-text('Set a Rewards goal'), div:has-text('Browse the Earn page'), div:has-text('Earn 1320 points')"
            )
            for card in onboarding_cards:
                try:
                    c_box = await card.evaluate_handle(r"""
                        (el) => {
                            let curr = el;
                            while (curr && curr !== document.body) {
                                if (curr.tagName === 'A' || curr.tagName === 'BUTTON' || (curr.className && String(curr.className).includes('Card')) || curr.classList.contains('cursor-pointer')) {
                                    return curr;
                                }
                                curr = curr.parentElement;
                            }
                            return el;
                        }
                    """)
                    if c_box:
                        c_elem = c_box.as_element()
                        if c_elem and await c_elem.is_visible():
                            c_text = (await c_elem.inner_text() or "").strip()
                            if "✓" not in c_text and "completed" not in c_text.lower():
                                log_info(f"🎯 Thực hiện nhiệm vụ khởi động: '{c_text.splitlines()[0]}'")
                                await self._process_card(c_elem)
                                await random_delay(2.5, 4.0)
                except Exception:
                    pass
        except Exception:
            pass

        # 4. Modern 2026 UI Badges (+10, +25, +5, +50, +15, +30)
        try:
            badges = await self.page.query_selector_all(
                "div:has-text('+10'), div:has-text('+25'), div:has-text('+5'), div:has-text('+50'), div:has-text('+15'), div:has-text('+30')"
            )
            processed_titles = set()
            for idx, badge in enumerate(badges, start=1):
                try:
                    card = await badge.evaluate_handle(r"""
                        (el) => {
                            let curr = el;
                            while (curr && curr !== document.body) {
                                if (curr.tagName === 'A' || curr.tagName === 'BUTTON' || curr.getAttribute('role') === 'button' || curr.classList.contains('cursor-pointer') || (curr.className && String(curr.className).includes('Card'))) {
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
                    if not card_elem or not await card_elem.is_visible():
                        continue

                    raw_text = (await card_elem.inner_text() or "").strip()
                    title = raw_text.split("\n")[0].strip()
                    if not title or title in processed_titles or "✓" in raw_text or "completed" in raw_text.lower():
                        continue
                    processed_titles.add(title)

                    log_info(f"-> Đang thực hiện nhiệm vụ: '{title}'...")
                    await self._process_card(card_elem)
                    await random_delay(3.0, 5.0)

                except Exception as e:
                    log_warn(f"Lỗi khi xử lý thẻ #{idx}: {e}")

        except Exception as e:
            log_warn(f"Lỗi quét hoạt động: {e}")

        # 5. Classic Cards Fallback (#daily-sets, mee-card)
        try:
            classic_cards = await self.page.query_selector_all("#daily-sets .c-card, mee-card.c-card, #more-activities .c-card")
            for idx, card in enumerate(classic_cards, start=1):
                try:
                    is_completed = await card.query_selector(".mee-icon-SkypeCircleCheck, .completed, [aria-label*='completed']")
                    if is_completed:
                        continue
                    title_el = await card.query_selector("h3, .c-heading, .title")
                    title = (await title_el.text_content() if title_el else f"Nhiệm vụ classic #{idx}").strip()

                    log_info(f"-> Đang thực hiện nhiệm vụ Classic: '{title}'...")
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

        # Check if a drawer was opened instead of a new tab
        drawer_actions = await self.page.query_selector("button:has-text('Check-in now'), button:has-text('Activate streak'), button:has-text('Claim points')")
        if drawer_actions and await drawer_actions.is_visible():
            await self.handle_drawer_actions()
            return

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

        # 1. Check for Poll (Bình chọn hàng ngày)
        poll_options = await page.query_selector_all("#btoption0, #btoption1, .btOption, [id^='btoption'], div[class*='pollOption']")
        if poll_options:
            log_info("Phát hiện Poll (Bình chọn), đang chọn đáp án ngẫu nhiên...")
            chosen = random.choice(poll_options)
            try:
                await chosen.click()
                await asyncio.sleep(3)
            except Exception:
                pass
            return

        # 2. Check for Quiz / Trivia / 'A, B, or C?'
        start_quiz_btn = await page.query_selector("#rqStartQuiz, #rqAnswerOption0, .wk_OptionClickClass, [id^='rqAnswerOption'], [class*='quizOption']")
        if start_quiz_btn:
            log_info("Phát hiện Quiz (Trắc nghiệm), đang tự động hoàn thành...")
            start_btn = await page.query_selector("#rqStartQuiz, button:has-text('Start playing'), button:has-text('Start quiz')")
            if start_btn and await start_btn.is_visible():
                await start_btn.click()
                await asyncio.sleep(2)

            for _ in range(15):
                options = await page.query_selector_all(
                    "[id^='rqAnswerOption'], .wk_OptionClickClass, .rqOption, input[type='radio'], [class*='b_cards'] [role='button'], [class*='quizOption']"
                )
                if not options:
                    break

                for opt in options:
                    try:
                        if await opt.is_visible():
                            await opt.click()
                            await asyncio.sleep(1.2)
                    except Exception:
                        pass

                # Next question button if exists
                next_btn = await page.query_selector("#rqNextQuestion, input[value='Next Question'], button:has-text('Next')")
                if next_btn and await next_btn.is_visible():
                    await next_btn.click()
                    await asyncio.sleep(1.5)

                complete_el = await page.query_selector(".rqComplete, #quizCompleteMessage, [class*='quizComplete']")
                if complete_el and await complete_el.is_visible():
                    log_success("Đã hoàn thành Quiz trắc nghiệm thành công!")
                    break
                await asyncio.sleep(1.5)
            return

        # 3. Simple click-through / explore page
        try:
            await page.evaluate("window.scrollBy(0, 350)")
        except Exception:
            pass
        await asyncio.sleep(random.uniform(3.0, 5.0))
