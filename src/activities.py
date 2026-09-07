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
        self.processed_urls: Set[str] = set()

    async def open_dashboard(self, url: str = "https://rewards.bing.com/dashboard") -> bool:
        """Navigate to rewards page and check authentication."""
        log_info(f"Dang truy cap {url} ({'Mobile' if self.is_mobile else 'Desktop'})...")
        try:
            await self.page.goto(url, wait_until="domcontentloaded", timeout=45000)
            await asyncio.sleep(4)
            if "login.live.com" in self.page.url:
                log_warn("Trinh duyet dang o trang Dang nhap!")
                return False
            return True
        except Exception as e:
            log_warn(f"Khong the tai trang {url}: {e}")
            return False

    async def get_account_summary(self) -> Dict[str, Any]:
        """Scrape account overview (available points, streak, level, etc.)."""
        summary = {"points": "N/A", "streak": "0", "level": "Member"}
        try:
            points_data = await self.page.evaluate(r"""
                () => {
                    const all = Array.from(document.querySelectorAll('*'));
                    for (let i = 0; i < all.length; i++) {
                        const text = (all[i].innerText || all[i].textContent || '').trim();
                        if (text === 'Available points' || text === 'Diem kha dung') {
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

            streak_data = await self.page.evaluate(r"""
                () => {
                    const all = Array.from(document.querySelectorAll('*'));
                    for (let i = 0; i < all.length; i++) {
                        const text = (all[i].innerText || all[i].textContent || '').trim();
                        if (text.toLowerCase().includes('day streak') || text.toLowerCase().includes('ngay lien tiep')) {
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
                "button:has(svg[data-icon-name*='Dismiss']), button:has-text('Close'), button:has-text('Dong')"
            )
            for btn in close_buttons:
                if await btn.is_visible():
                    try:
                        await btn.click()
                        await asyncio.sleep(0.8)
                    except Exception:
                        pass
            await self.page.keyboard.press("Escape")
            await asyncio.sleep(0.4)
        except Exception:
            pass

    async def handle_drawer_actions(self):
        """Perform actions inside opened side drawer."""
        await asyncio.sleep(1.5)
        action_selectors = [
            ("Check-in now", "button:has-text('Check-in now'), button:has-text('Check-in'), button:has-text('Diem danh')"),
            ("Activate streak", "button:has-text('Activate streak'), button:has-text('Activate'), button:has-text('Kich hoat')"),
            ("Claim points", "button:has-text('Claim points'), button:has-text('Claim'), button:has-text('Nhan diem')"),
            ("Search now", "button:has-text('Search now'), button:has-text('Tim kiem ngay')")
        ]
        drawer = await self.page.query_selector("[role='dialog'], [aria-modal='true'], [class*='drawer'], [class*='flyout'], [class*='Drawer']")
        container = drawer if drawer else self.page
        for action_name, sel in action_selectors:
            btn = await container.query_selector(sel)
            if btn and await btn.is_visible():
                log_info(f"Bam nut trong Side Drawer: {action_name}")
                try:
                    await btn.click()
                    await asyncio.sleep(3)
                except Exception:
                    pass
                break
        await self.close_any_drawer()

    async def _expand_all_accordions(self):
        """FIX #3: Mo rong tat ca accordion sections bang nhieu chien luoc."""
        try:
            # Chien luoc 1: click theo keyword lien quan rewards
            expanded = await self.page.evaluate(r"""
                () => {
                    let clicked = 0;
                    const collapsed = Array.from(document.querySelectorAll('[aria-expanded="false"]'));
                    for (const el of collapsed) {
                        const text = (el.innerText || el.textContent || '').toLowerCase();
                        const keywords = ['daily set', 'keep earning', 'explore', 'your activity', 'get started', 'earn', 'activity'];
                        if (keywords.some(k => text.includes(k))) {
                            el.click();
                            clicked++;
                        }
                    }
                    return clicked;
                }
            """)
            if expanded:
                log_info(f"[+] Mo {expanded} accordion section(s) theo keyword")
                await asyncio.sleep(0.8)

            # Chien luoc 2: click tat ca collapsed element co kich thuoc hop le
            await self.page.evaluate(r"""
                () => {
                    const collapsed = Array.from(document.querySelectorAll('[aria-expanded="false"]'));
                    for (const el of collapsed) {
                        const rect = el.getBoundingClientRect();
                        if (rect.width > 100 && rect.height > 20) {
                            el.click();
                        }
                    }
                }
            """)
            await asyncio.sleep(1.0)

        except Exception as e:
            log_warn(f"Khong the mo accordion: {e}")

    async def scan_and_solve_page_cards(self):
        """Intelligently find and solve all uncompleted activity cards on current page."""
        log_info("=== Bat dau quet tat ca the nhiem vu tren trang ===")

        # B1: Mo accordion
        await self._expand_all_accordions()

        # B2: Daily check-in Bing App streak
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

        base_url = self.page.url
        max_iterations = 20
        skipped_count = 0

        for iteration in range(max_iterations):
            try:
                # Re-expand moi 5 vong
                if iteration % 5 == 0:
                    await self._expand_all_accordions()

                # FIX #1 & #2: Selector mo rong + bo filter diem cung nhac
                next_card_info = await self.page.evaluate(r"""
                    () => {
                        const candidates = Array.from(document.querySelectorAll(
                            "mee-rewards-daily-set-item-content, " +
                            "mee-rewards-more-activities-card-item, " +
                            "div[class*='card']:not([class*='card-container']):not([class*='cards-group']), " +
                            "div[class*='Card']:not([class*='CardList']):not([class*='CardGroup']), " +
                            "mee-card, " +
                            "li[class*='card'], " +
                            "div[data-m], " +
                            "[data-bi-id*='card'], " +
                            "[data-bi-id*='Card'], " +
                            "a[class*='reward'], " +
                            "[class*='activity-card'], " +
                            "[class*='activityCard'], " +
                            "[class*='rewardCard']"
                        ));

                        for (let i = 0; i < candidates.length; i++) {
                            const el = candidates[i];
                            const rect = el.getBoundingClientRect();
                            if (rect.width < 40 || rect.height < 30) continue;
                            if (el.getAttribute('data-reward-done') === 'true') continue;

                            const text = (el.innerText || el.textContent || '').trim();
                            if (!text || text.length < 5) continue;

                            const lowerText = text.toLowerCase();
                            if (
                                lowerText.includes('completed') ||
                                lowerText.includes('hoan thanh') ||
                                lowerText.includes('rewards app only') ||
                                lowerText.includes('mobile app only') ||
                                text.includes('\u2713')
                            ) {
                                el.setAttribute('data-reward-done', 'true');
                                continue;
                            }

                            // Loc chinh xac: chi chap nhan card co diem thuong HOAC link den Bing/Microsoft
                            // Loai bo info card khong co diem
                            const infoKeywords = [
                                "expires in", "search for", "search 1 time", "your activity",
                                "day streak", "days streak", "for 7 days", "for 30 days",
                                "available points", "level 1", "level 2", "member"
                            ];
                            if (infoKeywords.some(k => lowerText.startsWith(k))) {
                                el.setAttribute("data-reward-done", "true");
                                continue;
                            }

                            // SKIP card khong completable
                            if (lowerText.includes('unlocks tomorrow') ||
                                lowerText.includes('unlocks in') ||
                                lowerText.includes('mo khoa ngay mai') ||
                                lowerText.includes('required') ||
                                lowerText.includes('yeu cau')) {
                                el.setAttribute("data-reward-done", "true");
                                continue;
                            }

                            // SKIP donation cards (khong co diem thuc te)
                            if (lowerText.includes('donate') || lowerText.includes('quyen gop')) {
                                el.setAttribute("data-reward-done", "true");
                                continue;
                            }

                            // SKIP sweepstakes/contest (khong tu dong duoc)
                            if (lowerText.includes('sweepstakes') || lowerText.includes('contest')) {
                                el.setAttribute("data-reward-done", "true");
                                continue;
                            }

                            // Phai co so diem thuong ro rang
                            const hasPoints = /\+\s*\d+\s*(pts?|points?)?/i.test(text) ||
                                             /\b\d+\s*(pts|points)\b/i.test(text) ||
                                             /\(\+\d+\)/i.test(text);

                            // Hoac la card co link den Bing/Microsoft (Daily Set, quiz, poll)
                            const activityLink = el.querySelector("a[href*='bing.com'], a[href*='rewards.bing'], a[href*='microsoft.com']");
                            const hasBingLink = activityLink !== null;

                            if (!hasPoints && !hasBingLink) continue;

                            // Tranh wrapper chua nhieu card con
                            let isParent = false;
                            const pointPattern = /\+?\s*\b([3-9]|[1-9]\d{1,3})\b/;
                            for (let j = 0; j < el.children.length; j++) {
                                const child = el.children[j];
                                const cText = (child.innerText || child.textContent || '').trim();
                                if (pointPattern.test(cText) && cText !== text && cText.length > 5) {
                                    isParent = true;
                                    break;
                                }
                            }
                            if (isParent) continue;

                            const titleEl = el.querySelector('[class*="title"], [class*="Title"], h2, h3, h4, strong, b') || el;
                            const title = (titleEl.innerText || titleEl.textContent || text).split('\n')[0].trim().substring(0, 100);
                            const link = el.querySelector('a[href]');
                            const href = link ? link.href : '';

                            el.setAttribute('data-reward-next', 'true');
                            return {
                                found: true,
                                title: title,
                                href: href,
                                text_preview: text.substring(0, 200)
                            };
                        }
                        return { found: false };
                    }
                """)

                if not next_card_info.get("found"):
                    log_info(f"[OK] Khong con the nhiem vu nao (da quet {iteration} vong).")
                    break

                title = next_card_info.get("title", "").strip()
                href = next_card_info.get("href", "")
                text_preview = next_card_info.get("text_preview", "")

                # FIX #4: Dung ca title + href lam tracking key
                tracking_key = f"{title}||{href}" if href else title

                if tracking_key in self.processed_titles:
                    log_warn(f"[SKIP] Da xu ly: '{title}' [{href}]")
                    await self.page.evaluate(
                        "() => { const el = document.querySelector('[data-reward-next]'); "
                        "if (el) { el.removeAttribute('data-reward-next'); el.setAttribute('data-reward-done', 'true'); } }"
                    )
                    skipped_count += 1
                    if skipped_count > 10:
                        log_warn("[WARN] Da bo qua qua nhieu card, dung vong lap.")
                        break
                    continue

                card_elem = await self.page.query_selector("[data-reward-next='true']")
                if not card_elem:
                    break

                skipped_count = 0
                self.processed_titles.add(tracking_key)

                log_info(f"[{iteration+1}] The nhiem vu: '{title}'")
                if href:
                    log_info(f"    URL: {href}")
                log_info(f"    Preview: {text_preview[:100]}")

                await self.page.evaluate(
                    "(el) => { el.removeAttribute('data-reward-next'); el.setAttribute('data-reward-done', 'true'); }",
                    card_elem
                )

                await self._process_card(card_elem)
                await random_delay(2.5, 4.5)

                if self.page.url != base_url:
                    log_info(f"Quay ve dashboard: {base_url}")
                    await self.open_dashboard(base_url)
                    await asyncio.sleep(1.5)
                    await self._expand_all_accordions()

            except Exception as e:
                log_warn(f"[ERR] Vong {iteration}: {e}")
                if self.page.url != base_url:
                    await self.open_dashboard(base_url)
                    await asyncio.sleep(1.5)

        log_info(f"=== Hoan tat: Tong so the da xu ly = {len(self.processed_titles)} ===")

    async def solve_all_activities(self):
        """Complete all tasks across Dashboard, Earn page, and Get Started onboarding."""
        log_info("=== Phase 1: Dashboard (Daily Set + Streaks + Activities) ===")
        await self.open_dashboard("https://rewards.bing.com/dashboard")
        await self.scan_and_solve_page_cards()

        log_info("=== Phase 2: Trang /earn (Keep earning & Explore on Bing) ===")
        await self.open_dashboard("https://rewards.bing.com/earn")
        await self.scan_and_solve_page_cards()

        try:
            log_info("=== Phase 3: Kiem tra trang Get Started Onboarding ===")
            get_started_link = await self.page.query_selector("a[href*='getstarted'], button:has-text('Earn 1320 points')")
            if get_started_link and await get_started_link.is_visible():
                log_info("Mo trang nhiem vu khoi dong 'Get started with Rewards'...")
                await get_started_link.click()
                await asyncio.sleep(2)
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
        start_url = self.page.url

        click_target = await card_element.query_selector("a[href], button, [role='button']") or card_element

        try:
            await click_target.click()
        except Exception:
            try:
                await self.page.evaluate("(el) => el.click()", click_target)
            except Exception as e:
                log_warn(f"Khong the click card: {e}")
                return

        await asyncio.sleep(2)

        # 1. New tab opened
        pages = self.context.pages
        if len(pages) > initial_pages:
            new_page = pages[-1]
            log_info(f"Mo tab moi: {new_page.url[:80]}")
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

        # 2. Same tab navigation
        if self.page.url != start_url:
            log_info(f"Dieu huong trong tab: {self.page.url[:80]}")
            try:
                await self._handle_activity_page(self.page)
            except Exception:
                pass
            return

        # 3. Drawer / Dialog opened
        drawer = await self.page.query_selector("[role='dialog'], [aria-modal='true'], [class*='drawer'], [class*='flyout'], [class*='Drawer']")
        if drawer and await drawer.is_visible():
            log_info("Phat hien Side Drawer, dang xu ly...")
            await self.handle_drawer_actions()
            return

        # 4. Fallback: handle activity on current page
        log_info("Xu ly activity tren trang hien tai...")
        await self._handle_activity_page(self.page)

    async def _handle_activity_page(self, page: Page):
        """Smart quiz solver: handles Polls, Warpspeed, Supersonic, Turbocharge, A/B/C and Puzzles."""
        await asyncio.sleep(1.5)
        log_info(f"Xu ly activity tai: {page.url[:80]}")

        # 1. Daily Poll
        poll_options = await page.query_selector_all("#btoption0, #btoption1, .btOption, [id^='btoption'], div[class*='pollOption']")
        if poll_options:
            log_info(f"Phat hien Poll ({len(poll_options)} lua chon), dang binh chon...")
            chosen = random.choice(poll_options)
            try:
                await chosen.click()
                await random_delay(2.0, 4.0)
                log_success("Da binh chon Poll thanh cong!")
            except Exception as e:
                log_warn(f"Loi khi binh chon Poll: {e}")
            return

        # 2. Quizzes (Warpspeed, Supersonic, Turbocharge, A B C, This or That)
        start_quiz_btn = await page.query_selector(
            "#rqStartQuiz, #rqAnswerOption0, .wk_OptionClickClass, [id^='rqAnswerOption'], [class*='quizOption'], input[value='Start playing']"
        )
        if start_quiz_btn:
            log_info("Phat hien Quiz, dang tu dong giai...")
            start_btn = await page.query_selector("#rqStartQuiz, button:has-text('Start playing'), button:has-text('Start quiz')")
            if start_btn and await start_btn.is_visible():
                await start_btn.click()
                await random_delay(1.5, 3.0)

            for step in range(15):
                options = await page.query_selector_all(
                    "[id^='rqAnswerOption'], .wk_OptionClickClass, .rqOption, input[type='radio'], "
                    "[class*='b_cards'] [role='button'], [class*='quizOption'], div[class*='bt_option']"
                )
                if not options:
                    log_info(f"  Quiz step {step+1}: khong con dap an, ket thuc.")
                    break

                log_info(f"  Quiz step {step+1}: {len(options)} dap an")
                for opt in options:
                    try:
                        if await opt.is_visible():
                            await opt.click()
                            await random_delay(1.5, 3.0)
                    except Exception:
                        pass

                next_btn = await page.query_selector("#rqNextQuestion, input[value='Next Question'], button:has-text('Next')")
                if next_btn and await next_btn.is_visible():
                    await next_btn.click()
                    await random_delay(1.0, 2.0)

                complete_el = await page.query_selector(".rqComplete, #quizCompleteMessage, [class*='quizComplete']")
                if complete_el and await complete_el.is_visible():
                    log_success("Da hoan thanh Quiz thanh cong!")
                    break
                await random_delay(1.5, 2.5)
            return

        # 3. Puzzle & Exploration Tasks (only on rewards activity pages, not bing.com)
        try:
            if "rewards.bing.com" in (page.url or ""):
                puzzle_tiles = await page.query_selector_all("[class*='puzzle'], [class*='tile']")
                if puzzle_tiles:
                    log_info(f"Phat hien Puzzle ({len(puzzle_tiles)} tiles), dang click...")
                for p_tile in puzzle_tiles[:4]:
                    if await p_tile.is_visible():
                        try:
                            await p_tile.click()
                            await asyncio.sleep(0.8)
                        except Exception:
                            pass
        except Exception:
            pass

        # 4. Standard Explore (scroll + wait for tracking pixel)
        log_info("Cuon trang va cho tracking pixel...")
        try:
            await page.evaluate("window.scrollBy(0, 450)")
        except Exception:
            pass
        await asyncio.sleep(random.uniform(5.0, 7.0))
