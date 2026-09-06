import asyncio
import re
import random
from typing import Dict, List, Any, Set
from playwright.async_api import Page, BrowserContext
from src.config import BotConfig
from src.utils import log_info, log_success, log_warn, random_delay

class RewardsDashboard:
    """Intelligent, thorough automation engine for all Microsoft Rewards tasks (2026 UI & Classic)."""

    def __init__(self, page: Page, context: BrowserContext, config: BotConfig, is_mobile: bool = False):
        self.page = page
        self.context = context
        self.config = config
        self.is_mobile = is_mobile
        self.processed_titles: Set[str] = set()

    async def open_dashboard(self, url: str = "https://rewards.bing.com/dashboard") -> bool:
        """Navigate to rewards page and check authentication."""
        log_info(f"Đang truy cập {url} ({'Mobile' if self.is_mobile else 'Desktop'})...")
        try:
            await self.page.goto(url, wait_until="domcontentloaded", timeout=45000)
            await asyncio.sleep(4)

            # Check if redirected to welcome or login page
            if "login.live.com" in self.page.url:
                log_warn("Trình duyệt đang ở trang Đăng nhập (Chưa có phiên đăng nhập Microsoft)!")
                return False

            return True
        except Exception as e:
            log_warn(f"Không thể tải trang {url}: {e}")
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
            streak_data = await self.page.evaluate(r"""
                () => {
                    const all = Array.from(document.querySelectorAll('*'));
                    for (let i = 0; i < all.length; i++) {
                        const text = (all[i].innerText || all[i].textContent || '').trim();
                        if (text.toLowerCase().includes('day streak') || text.toLowerCase().includes('chuỗi') || text.toLowerCase().includes('ngày liên tiếp')) {
                            const nums = text.match(/\d+/g);
                            if (nums) return nums[0];
                        }
                    }
                    return null;
                }
            """)
            if streak_data:
                summary["streak"] = streak_data
            else:
                streak_el = await self.page.query_selector(".streak-count, [aria-label*='streak'], mee-rewards-streak-status, [class*='streak']")
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
                        await asyncio.sleep(0.8)
                    except Exception:
                        pass
            # Escape key fallback
            await self.page.keyboard.press("Escape")
            await asyncio.sleep(0.4)
        except Exception:
            pass

    async def handle_drawer_actions(self):
        """Perform actions inside opened side drawer (Check-in, Activate, Claim, Solve nested cards)."""
        await asyncio.sleep(1.5)

        # 1. Action Buttons in Drawers
        action_selectors = [
            ("Check-in now", "button:has-text('Check-in now'), button:has-text('Check-in'), button:has-text('Điểm danh')"),
            ("Activate streak", "button:has-text('Activate streak'), button:has-text('Activate'), button:has-text('Kích hoạt')"),
            ("Claim points", "button:has-text('Claim points'), button:has-text('Claim'), button:has-text('Nhận điểm')"),
            ("Search now", "button:has-text('Search now'), button:has-text('Tìm kiếm ngay')")
        ]

        drawer = await self.page.query_selector("[role='dialog'], [aria-modal='true'], [class*='drawer'], [class*='flyout'], [class*='Drawer']")
        container = drawer if drawer else self.page

        for action_name, sel in action_selectors:
            btn = await container.query_selector(sel)
            if btn and await btn.is_visible():
                log_info(f"✨ Bấm nút trong Side Drawer: '[bold cyan]{action_name}[/bold cyan]'")
                try:
                    await btn.click()
                    await asyncio.sleep(3)
                except Exception:
                    pass
                break

        await self.close_any_drawer()

    async def scan_and_solve_page_cards(self):
        """Intelligently find and solve all uncompleted activity cards on current page."""
        # 1. Expand all accordions if collapsed
        try:
            await self.page.evaluate(r"""
                () => {
                    const accordions = Array.from(document.querySelectorAll("div[class*='cursor-pointer'], button, [role='button']"));
                    for (const acc of accordions) {
                        const text = (acc.innerText || acc.textContent || '').trim();
                        if (['Daily set', 'Keep earning', 'Explore on Bing', 'Your activity', 'Get started'].some(k => text.startsWith(k))) {
                            const isExpanded = acc.getAttribute('aria-expanded') === 'true';
                            // If not already expanded, click to expand
                            if (!isExpanded) {
                                acc.click();
                            }
                        }
                    }
                }
            """)
            await asyncio.sleep(1.5)
        except Exception:
            pass

        # 2. Daily check-in on Bing App streak (in Your activity)
        try:
            bing_app_tiles = await self.page.query_selector_all("div:has-text('Mobile App'), div:has-text('Bing App Streak')")
            for tile in bing_app_tiles:
                text = (await tile.inner_text() or "").strip()
                if ("Mobile App" in text or "Bing App Streak" in text) and "Check-in" in text:
                    if "Bing App Streak Checkin" not in self.processed_titles:
                        self.processed_titles.add("Bing App Streak Checkin")
                        await tile.click()
                        await self.handle_drawer_actions()
                        break
        except Exception:
            pass

        # 3. Detect and solve all uncompleted cards on page
        try:
            # Tag all uncompleted cards directly in DOM
            card_count = await self.page.evaluate(r"""
                () => {
                    document.querySelectorAll('[data-reward-task]').forEach(el => el.removeAttribute('data-reward-task'));
                    
                    const candidates = Array.from(document.querySelectorAll(
                        "div[class*='card'], div[class*='Card'], mee-card, .mee-rewards-daily-set-item-content, " +
                        ".mee-rewards-more-activities-card-item, a[class*='card'], [data-bi-id*='Card'], [data-bi-id*='Activity']"
                    ));
                    
                    let found = 0;
                    for (const el of candidates) {
                        const rect = el.getBoundingClientRect();
                        if (rect.width < 50 || rect.height < 30) continue;
                        
                        const text = (el.innerText || '').trim();
                        if (!text) continue;
                        
                        // Ignore completed or locked cards
                        if (text.includes('Completed') || text.includes('✓') || text.toLowerCase().includes('rewards app only')) continue;
                        
                        // Must have point value
                        if (!/\+?\b(5|10|15|20|25|30|40|50|100|500)\b/.test(text)) continue;
                        
                        // Avoid multi-card parent wrappers
                        let isParentWrapper = false;
                        for (let i = 0; i < el.children.length; i++) {
                            const cText = (el.children[i].innerText || '').trim();
                            if (/\+?\b(5|10|15|20|25|30|40|50|100|500)\b/.test(cText) && cText.length > 5 && cText !== text) {
                                isParentWrapper = true;
                                break;
                            }
                        }
                        if (isParentWrapper) continue;
                        
                        el.setAttribute('data-reward-task', 'pending');
                        found++;
                    }
                    return found;
                }
            """)

            cards = await self.page.query_selector_all("[data-reward-task='pending']")
            log_info(f"🔍 Quét thấy {len(cards)} mục điểm hoạt động trên trang...")

            for card_elem in cards:
                try:
                    raw_text = (await card_elem.inner_text() or "").strip()
                    title = raw_text.split("\n")[0].strip()
                    if not title or title in self.processed_titles or "Completed" in raw_text or "✓" in raw_text:
                        continue
                    self.processed_titles.add(title)

                    log_info(f"-> 🎯 Đang thực hiện nhiệm vụ: '[bold green]{title}[/bold green]'...")
                    await self._process_card(card_elem)
                    await random_delay(4.0, 7.5)

                except Exception as e:
                    log_warn(f"Lỗi khi xử lý thẻ nhiệm vụ: {e}")

        except Exception as e:
            log_warn(f"Lỗi quét hoạt động: {e}")

    async def solve_all_activities(self):
        """Complete all tasks across Dashboard, Earn page (/earn), and Get Started onboarding."""
        # Phase 1: Main Dashboard (Daily Set + Streaks + Activities)
        await self.open_dashboard("https://rewards.bing.com/dashboard")
        await self.scan_and_solve_page_cards()

        # Phase 2: Earn Page (/earn - contains 710+ points in 'Keep earning' & 'Explore on Bing')
        await self.open_dashboard("https://rewards.bing.com/earn")
        await self.scan_and_solve_page_cards()

        # Phase 3: Onboarding Checklist (/welcome/getstarted - +1,320 pts)
        try:
            get_started_link = await self.page.query_selector("a[href*='getstarted'], button:has-text('Earn 1320 points')")
            if get_started_link and await get_started_link.is_visible():
                log_info("🚀 Mở trang nhiệm vụ khởi động 'Get started with Rewards'...")
                await get_started_link.click()
                await asyncio.sleep(4)
                await self.scan_and_solve_page_cards()
        except Exception:
            pass

    async def solve_daily_set(self):
        """Unified entry point to solve all tasks."""
        await self.solve_all_activities()

    async def solve_more_activities(self):
        """Unified runner for more activities."""
        pass

    async def _process_card(self, card_element):
        """Click on card, handle new tab, quiz, poll, or side drawer."""
        initial_pages = len(self.context.pages)

        # Click the action link or card
        click_target = await card_element.query_selector("a, button, [role='button']") or card_element

        try:
            await click_target.click()
        except Exception:
            await self.page.evaluate("(el) => el.click()", click_target)

        await asyncio.sleep(3.5)

        # 1. Check if a new tab opened (typical for Daily Set quizzes, polls, and bing searches)
        pages = self.context.pages
        if len(pages) > initial_pages:
            new_page = pages[-1]
            try:
                await new_page.wait_for_load_state("domcontentloaded", timeout=25000)
                await self._handle_activity_page(new_page)
            finally:
                try:
                    await new_page.close()
                except Exception:
                    pass
                await self.page.bring_to_front()
                await asyncio.sleep(1.5)
            return

        # 2. Check if a drawer was opened instead of a new tab
        drawer = await self.page.query_selector("[role='dialog'], [aria-modal='true'], [class*='drawer'], [class*='flyout'], [class*='Drawer']")
        if drawer and await drawer.is_visible():
            await self.handle_drawer_actions()
            return

        # 3. Handle activity on current page if redirected
        await self._handle_activity_page(self.page)

    async def _handle_activity_page(self, page: Page):
        """Smart quiz solver: handles Polls, Warpspeed, Supersonic, Turbocharge, A/B/C and Puzzles."""
        await asyncio.sleep(2)

        # 1. Daily Poll (Bình chọn)
        poll_options = await page.query_selector_all("#btoption0, #btoption1, .btOption, [id^='btoption'], div[class*='pollOption']")
        if poll_options:
            log_info("📊 Phát hiện Poll (Bình chọn), đang tự động chọn đáp án...")
            chosen = random.choice(poll_options)
            try:
                await chosen.click()
                await random_delay(4.0, 7.0)
            except Exception:
                pass
            return

        # 2. Quizzes (Warpspeed, Supersonic, Turbocharge, A B C, This or That)
        start_quiz_btn = await page.query_selector(
            "#rqStartQuiz, #rqAnswerOption0, .wk_OptionClickClass, [id^='rqAnswerOption'], [class*='quizOption'], input[value='Start playing']"
        )
        if start_quiz_btn:
            log_info("🧠 Phát hiện Quiz (Bài kiểm tra trắc nghiệm), đang tự động giải bài...")
            start_btn = await page.query_selector("#rqStartQuiz, button:has-text('Start playing'), button:has-text('Start quiz')")
            if start_btn and await start_btn.is_visible():
                await start_btn.click()
                await random_delay(3.0, 5.0)

            for step in range(30):
                options = await page.query_selector_all(
                    "[id^='rqAnswerOption'], .wk_OptionClickClass, .rqOption, input[type='radio'], "
                    "[class*='b_cards'] [role='button'], [class*='quizOption'], div[class*='bt_option']"
                )
                if not options:
                    break

                # Click multiple visible options (essential for Supersonic Quiz where 3 correct options must be clicked)
                for opt in options:
                    try:
                        if await opt.is_visible():
                            await opt.click()
                            await random_delay(2.0, 4.0)
                    except Exception:
                        pass

                # Next question button if present
                next_btn = await page.query_selector("#rqNextQuestion, input[value='Next Question'], button:has-text('Next')")
                if next_btn and await next_btn.is_visible():
                    await next_btn.click()
                    await random_delay(2.0, 4.0)

                complete_el = await page.query_selector(".rqComplete, #quizCompleteMessage, [class*='quizComplete']")
                if complete_el and await complete_el.is_visible():
                    log_success("🎉 Đã hoàn thành toàn bộ Quiz thành công!")
                    break
                await random_delay(1.5, 3.0)
            return

        # 3. Puzzle & Exploration Tasks
        try:
            puzzle_tiles = await page.query_selector_all("[class*='puzzle'], [class*='tile']")
            for p_tile in puzzle_tiles[:4]:
                if await p_tile.is_visible():
                    try:
                        await p_tile.click()
                        await asyncio.sleep(0.8)
                    except Exception:
                        pass
        except Exception:
            pass

        # 4. Standard Explore & Click-to-Earn (Scroll and hold session for tracking pixel)
        try:
            await page.evaluate("window.scrollBy(0, 450)")
        except Exception:
            pass
        await asyncio.sleep(random.uniform(4.0, 6.0))
