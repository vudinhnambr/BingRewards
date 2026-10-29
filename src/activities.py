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
        """Navigate to rewards page and check authentication with smart redirect & retry handling."""
        log_info(f"Đang truy cập {url} ({'Mobile' if self.is_mobile else 'Desktop'})...")
        for attempt in range(1, 4):
            try:
                await self.page.goto(url, wait_until="domcontentloaded", timeout=45000)
                await asyncio.sleep(3)

                # Chờ silent OAuth handshake redirect (nếu URL đang chuyển tiếp qua login.live.com)
                if "login.live.com" in self.page.url:
                    log_info("Phát hiện URL chuyển hướng qua login.live.com, đang đợi xác thực tự động...")
                    for _ in range(8):
                        await asyncio.sleep(1.5)
                        if "login.live.com" not in self.page.url and "rewards" in self.page.url:
                            log_success("Xác thực chuyển tiếp tự động thành công!")
                            break

                # Nếu vẫn còn ở trang login, kiểm tra thử lại
                if "login.live.com" in self.page.url:
                    if attempt < 3:
                        log_warn(f"Chưa vào được dashboard (lần thử {attempt}/3), đang thử tải lại...")
                        await asyncio.sleep(3)
                        continue
                    log_warn("Trình duyệt đang ở trang Đăng nhập (Session có thể đã hết hạn)!")
                    return False

                return True
            except Exception as e:
                log_warn(f"Không thể tải trang {url} (lần {attempt}/3): {e}")
                if attempt < 3:
                    await asyncio.sleep(3)
                    continue
                return False
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

            email_data = await self.page.evaluate(r"""
                () => {
                    const sel = '#mectrl_currentAccount_secondary, [data-testid*="email"], .identity-email, #id_a, #b_idProviders';
                    const el = document.querySelector(sel);
                    if (el && el.innerText && el.innerText.includes('@')) {
                        return el.innerText.trim();
                    }
                    const ariaEls = document.querySelectorAll('[aria-label*="@"], [title*="@"]');
                    for (const e of ariaEls) {
                        const val = e.getAttribute('aria-label') || e.getAttribute('title') || '';
                        const m = val.match(/[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+/);
                        if (m) return m[0];
                    }
                    if (document.body) {
                        const m = document.body.innerText.match(/[a-zA-Z0-9_.+-]+@(gmail|outlook|hotmail|live|yahoo|msn|microsoft)\.[a-zA-Z0-9-.]+/i);
                        if (m) return m[0];
                    }
                    return null;
                }
            """)
            if email_data:
                summary["email"] = email_data

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
        """Perform actions inside opened side drawer, such as Claiming points or Checking in."""
        await asyncio.sleep(1.5)

        drawer = await self.page.query_selector("[role='dialog'], [aria-modal='true'], [class*='drawer'], [class*='flyout'], [class*='Drawer'], .flyout")
        container = drawer if drawer else self.page

        action_selectors = [
            ("Check-in", "button:has-text('Check-in now'), button:has-text('Check-in'), button:has-text('Check in now'), button:has-text('Check in'), button:has-text('Điểm danh ngay'), button:has-text('Điểm danh'), [aria-label*='check-in' i], [aria-label*='check in' i], [aria-label*='checkin' i]"),
            ("Claim", "button:has-text('Claim points'), button:has-text('Claim'), button:has-text('Nhận điểm'), button:has-text('Nhận'), a:has-text('Claim'), [aria-label*='claim' i]"),
            ("Activate", "button:has-text('Activate streak'), button:has-text('Activate'), button:has-text('Kích hoạt')"),
            ("Collect Stamp", "button:has-text('Get stamp'), button:has-text('Stamp'), button:has-text('Collect')"),
            ("Complete", "button:has-text('Complete'), button:has-text('Done'), button:has-text('Finish')")
        ]

        action_performed = False

        # 1. Primary actionable buttons scan
        for action_name, sel in action_selectors:
            btns = await container.query_selector_all(sel)
            for btn in btns:
                try:
                    if await btn.is_visible():
                        txt = (await btn.inner_text() or "").strip()
                        if "redeem" in txt.lower():
                            continue
                        log_info(f"Bấm nút trong Side Drawer: {action_name} ('{txt[:40]}')")
                        await btn.click()
                        await asyncio.sleep(2.5)
                        action_performed = True
                except Exception:
                    pass

        # 1.5. Check for day streak / checkin day icons in drawer
        try:
            day_btns = await container.query_selector_all(
                "div[class*='checkin'] button, [data-day] button, [class*='dayItem']:not([class*='completed']), div[class*='item-wrapper']:has(span:has-text('+')), button:has([class*='streak'])"
            )
            for d_btn in day_btns:
                try:
                    if await d_btn.is_visible():
                        d_txt = (await d_btn.inner_text() or "").strip()
                        if "redeem" in d_txt.lower():
                            continue
                        log_info(f"Bấm nút ngày điểm danh trong Side Drawer: '{d_txt[:40]}'")
                        await d_btn.click()
                        await asyncio.sleep(2.5)
                        action_performed = True
                        break
                except Exception:
                    pass
        except Exception:
            pass

        # 2. Fallback scan for all clickable elements with claim / point keywords
        try:
            fallback_btns = await container.query_selector_all("button, [role='button'], mee-button, a[role='button']")
            for btn in fallback_btns:
                try:
                    if await btn.is_visible():
                        btn_text = (await btn.inner_text() or "").strip()
                        lower_txt = btn_text.lower()
                        if "redeem" in lower_txt:
                            continue
                        if any(k in lower_txt for k in ["claim", "nhận", "check-in", "check in", "điểm danh", "collect"]):
                            log_info(f"Fallback bấm nút trong Side Drawer: '{btn_text[:50]}'")
                            await btn.click()
                            await asyncio.sleep(2.5)
                            action_performed = True
                except Exception:
                    pass
        except Exception as e:
            log_warn(f"Fallback claim click error: {e}")

        if not action_performed:
            log_info("Side Drawer không có nút hành động nào còn lại, đóng lại...")

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
                    (processedList) => {
                        const processedSet = new Set(processedList || []);
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
                                "expires in", "your activity",
                                "available points", "level 1", "level 2", "member"
                            ];
                            // Only skip if text is very short and matches info keywords exactly
                            if (text.length < 30 && infoKeywords.some(k => lowerText.startsWith(k))) {
                                el.setAttribute("data-reward-done", "true");
                                continue;
                            }

                            // SKIP card khong completable
                            if (lowerText.includes('unlocks tomorrow') ||
                                lowerText.includes('unlocks in') ||
                                lowerText.includes('mo khoa ngay mai') ||
                                lowerText.includes('level required') ||
                                lowerText.includes('cap do yeu cau') ||
                                lowerText.includes('set a goal')) {
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

                            // SKIP gift card redemption pages (khong phai nhiem vu)
                            if (lowerText.includes('gift card') || lowerText.includes('gift cards')) {
                                el.setAttribute("data-reward-done", "true");
                                continue;
                            }

                            // SKIP info bonus cards (chi hien thi thong tin, khong completable)
                            if (lowerText.includes('stamp bonus') ||
                                lowerText.includes('star bonus') ||
                                lowerText.includes('level up bonus') ||
                                lowerText.includes('default search bonus') ||
                                lowerText.includes('earned last month') ||
                                lowerText.includes('not eligible')) {
                                el.setAttribute("data-reward-done", "true");
                                continue;
                            }

                            // SKIP links to redeem pages
                            const redeemLink = el.querySelector("a[href*='/redeem/']");
                            if (redeemLink) {
                                el.setAttribute("data-reward-done", "true");
                                continue;
                            }

                            // Phai co so diem thuong ro rang
                            const hasPoints = /\+\s*\d+\s*(pts?|points?)?/i.test(text) ||
                                             /\b\d+\s*(pts|points)\b/i.test(text) ||
                                             /\(\+\d+\)/i.test(text);

                            // CHAP NHAN "Ready to claim" keyword
                            const isReadyToClaim = lowerText.includes('ready to claim');

                            // Hoac la card co link den Bing/Microsoft (Daily Set, quiz, poll)
                            const activityLink = el.querySelector("a[href*='bing.com'], a[href*='rewards.bing'], a[href*='microsoft.com']");
                            const hasBingLink = activityLink !== null;

                            if (!hasPoints && !hasBingLink && !isReadyToClaim) continue;

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
                            const trackingKey = href ? `${title}||${href}` : title;

                            if (processedSet.has(trackingKey) || processedSet.has(title)) {
                                el.setAttribute('data-reward-done', 'true');
                                continue;
                            }

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
                """, list(self.processed_titles))

                if not next_card_info.get("found"):
                    log_info(f"[OK] Khong con the nhiem vu nao (da quet {iteration} vong).")
                    break

                title = next_card_info.get("title", "").strip()
                href = next_card_info.get("href", "")
                text_preview = next_card_info.get("text_preview", "")

                # Debug: log all candidates with 'ready' keyword
                if "ready" in text_preview.lower():
                    log_info(f"[DEBUG] Found 'ready' candidate: '{text_preview[:150]}'")

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

    async def claim_ready_points(self):
        """Click 'Ready to claim' / 'Claim >' button on dashboard and earn pages to collect pending points."""
        try:
            for page_url in ["https://rewards.bing.com/dashboard", "https://rewards.bing.com/earn"]:
                await self.open_dashboard(page_url)
                await asyncio.sleep(2)
                await self._expand_all_accordions()

                claim_selectors = [
                    "button:has-text('Claim')",
                    "a:has-text('Claim')",
                    "[aria-label*='claim' i]",
                    "div:has-text('Ready to claim') button",
                    "div:has-text('Ready to claim') a",
                    "div[class*='claim'] button",
                    "div[class*='Claim'] button"
                ]

                claimed = False
                for sel in claim_selectors:
                    btns = await self.page.query_selector_all(sel)
                    for btn in btns:
                        try:
                            if await btn.is_visible():
                                txt = (await btn.inner_text() or "").strip()
                                lower_txt = txt.lower()
                                if "redeem" in lower_txt:
                                    continue
                                if "claim" in lower_txt or "nhận" in lower_txt:
                                    log_info(f"[Claim] Nhấn nút claim: '{txt[:50]}'")
                                    await btn.click()
                                    await asyncio.sleep(2.0)
                                    claimed = True

                                    # If clicking opened a side drawer, handle all actions inside it
                                    drawer = await self.page.query_selector("[role='dialog'], [aria-modal='true'], [class*='drawer'], [class*='flyout'], [class*='Drawer']")
                                    if drawer and await drawer.is_visible():
                                        await self.handle_drawer_actions()
                        except Exception:
                            pass

                # Also check direct card clicking for "Ready to claim"
                try:
                    ready_cards = await self.page.query_selector_all("div:has-text('Ready to claim'), [aria-label*='Ready to claim' i]")
                    for r_card in ready_cards:
                        if await r_card.is_visible():
                            # Exclude navigation header, banner, footer or huge parent containers
                            is_wrapper = await r_card.evaluate("el => Boolean(el.closest('header, nav, [role=\"navigation\"], [role=\"banner\"], footer')) || el.children.length > 8")
                            if is_wrapper:
                                continue
                            c_text = (await r_card.inner_text() or "").strip()
                            # If contains non-zero points or claim button
                            if "claim" in c_text.lower() and not "0\nclaim" in c_text.lower():
                                log_info(f"[Claim] Nhấn thẻ Ready to claim: '{c_text[:50]}'")
                                await r_card.click()
                                await asyncio.sleep(2.0)
                                claimed = True
                                drawer = await self.page.query_selector("[role='dialog'], [aria-modal='true'], [class*='drawer'], [class*='flyout'], [class*='Drawer']")
                                if drawer and await drawer.is_visible():
                                    await self.handle_drawer_actions()
                except Exception:
                    pass

                if not claimed:
                    log_info(f"[Claim] Không tìm thấy điểm đang chờ claim tại {page_url.split('/')[-1]}.")
        except Exception as e:
            log_warn(f"[Claim] Lỗi khi claim ready points: {e}")

    async def solve_all_activities(self):
        """Complete all tasks across Dashboard, Earn page, and Get Started onboarding."""
        log_info("=== Phase 0: Claim Ready Points ===")
        await self.claim_ready_points()

        log_info("=== Phase 1: Dashboard (Daily Set + Streaks + Activities) ===")
        await self.open_dashboard("https://rewards.bing.com/dashboard")
        await self.scan_and_solve_page_cards()

        log_info("=== Phase 2: Trang /earn (Keep earning & Explore on Bing) ===")
        await self.open_dashboard("https://rewards.bing.com/earn")
        await self.scan_and_solve_page_cards()

        log_info("=== Phase 2.5: UrlReward Server-Action Handler ===")
        await self.handle_urlreward_promotions()

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

        if getattr(self.config, "run_visual_search", True):
            log_info("=== Phase 4: Kiem tra nhiem vu Visual Search ===")
            await self.solve_visual_search()

    async def handle_urlreward_promotions(self):
        """Find and complete urlreward promotions via Next.js server actions."""
        try:
            from src.urlreward import UrlRewardHandler
            handler = UrlRewardHandler(self.page)
            result = await handler.run()

            if result.get("completed"):
                try:
                    from src.telegram_bot import TelegramNotifier
                    notifier = TelegramNotifier()
                    if notifier.is_configured:
                        lines = "\n".join(f"  ✅ {t}" for t in result["completed"])
                        notifier.send_message(f"🎯 <b>UrlReward Completed:</b>\n{lines}")
                except Exception:
                    pass
            return result
        except Exception as e:
            log_warn(f"handle_urlreward_promotions error: {e}")
            return {"status": "error", "completed": [], "skipped": []}

    async def solve_daily_set(self):
        """Unified entry point to solve all tasks."""
        await self.solve_all_activities()

    async def solve_more_activities(self):
        """Unified runner for more activities."""
        pass

    async def solve_mobile_app_checkin(self) -> bool:
        """Find and complete the Mobile App daily check-in streak on rewards dashboard."""
        log_info("=== 📱 Kiểm tra & Điểm danh Mobile App Check-in ===")
        try:
            # Ensure on rewards dashboard
            if "rewards.bing.com" not in self.page.url:
                await self.open_dashboard("https://rewards.bing.com/dashboard")
                await asyncio.sleep(2.0)

            # Strategy 1: Check legitimate tile on page (strictly exclude header / navigation wrappers)
            card_info = await self.page.evaluate(r"""
                () => {
                    const elements = Array.from(document.querySelectorAll(
                        "mee-card, [class*='card'], [class*='Card'], [role='article'], li, a, button, div"
                    ));
                    for (const el of elements) {
                        if (el.closest('header, nav, [role="navigation"], [role="banner"], footer, #raf-flyout')) {
                            continue;
                        }
                        const rect = el.getBoundingClientRect();
                        if (rect.width < 40 || rect.height < 25) continue;

                        const txt = (el.innerText || el.textContent || '').trim();
                        if (!txt || txt.length > 250) continue;

                        const lower = txt.toLowerCase();
                        if (!lower.includes('mobile app') && !lower.includes('bing app streak') && !(lower.includes('app') && lower.includes('check-in'))) {
                            continue;
                        }

                        // Avoid wrapper if a child element also matches
                        let hasMatchingChild = false;
                        for (const child of Array.from(el.children)) {
                            const cTxt = (child.innerText || child.textContent || '').toLowerCase();
                            if (cTxt.includes('mobile app') || cTxt.includes('bing app streak') || (cTxt.includes('app') && cTxt.includes('check-in'))) {
                                const cRect = child.getBoundingClientRect();
                                if (cRect.width >= 40 && cRect.height >= 25) {
                                    hasMatchingChild = true;
                                    break;
                                }
                            }
                        }
                        if (hasMatchingChild) continue;

                        const isDone = txt.includes('1/1') || lower.includes('completed') || txt.includes('✓') || lower.includes('đã điểm danh');
                        const isNotDone = txt.includes('0/1') || lower.includes('check-in: 0/1') || lower.includes('chưa điểm danh');
                        return {
                            found: true,
                            isDone: isDone,
                            isNotDone: isNotDone,
                            text: txt.replace(/\s+/g, ' ').substring(0, 100)
                        };
                    }
                    return { found: false };
                }
            """)

            if card_info.get("found"):
                preview = card_info.get("text", "")
                if card_info.get("isDone") and not card_info.get("isNotDone"):
                    log_success(f"📱 [Mobile App] Đã điểm danh hôm nay rồi: '{preview}'")
                    return True

                log_info(f"📱 [Mobile App] Tìm thấy thẻ điểm danh: '{preview}'. Đang tiến hành click điểm danh...")
                
                # Locate element and click safely
                tile_clicked = False
                selectors = [
                    "mee-card:has-text('Bing App Streak')",
                    "mee-card:has-text('Mobile App')",
                    "[class*='card']:has-text('Bing App Streak')",
                    "button:has-text('Mobile App')",
                    "a:has-text('Mobile App')",
                    "[aria-label*='Mobile App' i]"
                ]
                for sel in selectors:
                    tiles = await self.page.query_selector_all(sel)
                    for tile in tiles:
                        try:
                            if not await tile.is_visible():
                                continue
                            is_in_nav = await tile.evaluate("el => Boolean(el.closest('header, nav, [role=\"navigation\"], [role=\"banner\"], footer'))")
                            if is_in_nav:
                                continue
                            t_txt = (await tile.inner_text() or "").strip()
                            if len(t_txt) > 250:
                                continue
                            if "Mobile App" in t_txt or "Bing App" in t_txt:
                                await tile.click()
                                tile_clicked = True
                                await asyncio.sleep(2.5)
                                break
                        except Exception:
                            pass
                    if tile_clicked:
                        break

                if tile_clicked:
                    await self.handle_drawer_actions()
            else:
                log_info("📱 [Mobile App] Không thấy thẻ điểm danh riêng trên trang.")

            return True
        except Exception as e:
            log_warn(f"Lỗi khi xử lý Mobile App Check-in: {e}")
            return False

    async def solve_visual_search(self) -> bool:
        """Find and complete Visual Search task on dashboard and Bing."""
        log_info("=== 📷 Kiểm tra & Xử lý nhiệm vụ Visual Search ===")
        try:
            # 1. Check if card exists on dashboard (strictly exclude header / navigation wrappers)
            card_info = await self.page.evaluate(r"""
                () => {
                    const elements = Array.from(document.querySelectorAll(
                        "mee-card, [class*='card'], [class*='Card'], [role='article'], li, a, button, div"
                    ));
                    for (const el of elements) {
                        if (el.closest('header, nav, [role="navigation"], [role="banner"], footer, #raf-flyout')) {
                            continue;
                        }
                        const rect = el.getBoundingClientRect();
                        if (rect.width < 40 || rect.height < 25) continue;

                        const txt = (el.innerText || el.textContent || '').trim();
                        if (!txt || txt.length > 250) continue;

                        const lower = txt.toLowerCase();
                        if (!lower.includes('visual search') && !lower.includes('tìm kiếm bằng hình ảnh')) {
                            continue;
                        }

                        // Avoid wrapper if a child element also matches (pick deepest card)
                        let hasMatchingChild = false;
                        for (const child of Array.from(el.children)) {
                            const cTxt = (child.innerText || child.textContent || '').toLowerCase();
                            if (cTxt.includes('visual search') || cTxt.includes('tìm kiếm bằng hình ảnh')) {
                                const cRect = child.getBoundingClientRect();
                                if (cRect.width >= 40 && cRect.height >= 25) {
                                    hasMatchingChild = true;
                                    break;
                                }
                            }
                        }
                        if (hasMatchingChild) continue;

                        const isDone = txt.includes('1/1') || lower.includes('completed') || txt.includes('✓') || lower.includes('đã hoàn thành');
                        const isNotDone = txt.includes('0/1') || lower.includes('activity: 0/1') || lower.includes('chưa hoàn thành');
                        return {
                            found: true,
                            isDone: isDone,
                            isNotDone: isNotDone,
                            text: txt.replace(/\s+/g, ' ').substring(0, 100)
                        };
                    }
                    return { found: false };
                }
            """)

            if card_info.get("found"):
                preview = card_info.get("text", "")
                if card_info.get("isDone") and not card_info.get("isNotDone"):
                    log_success(f"📷 [Visual Search] Đã hoàn thành hôm nay: '{preview}'")
                    return True

                log_info(f"📷 [Visual Search] Phát hiện thẻ Visual Search chưa hoàn tất: '{preview}'. Đang click thẻ...")

                # Click on card
                initial_pages = len(self.context.pages)
                clicked = False
                selectors = [
                    "mee-card:has-text('Visual Search'), mee-card:has-text('Tìm kiếm bằng hình ảnh')",
                    "[class*='card']:has-text('Visual Search'), [class*='card']:has-text('Tìm kiếm bằng hình ảnh')",
                    "[class*='Card']:has-text('Visual Search'), [class*='Card']:has-text('Tìm kiếm bằng hình ảnh')",
                    "button:has-text('Visual Search'), button:has-text('Tìm kiếm bằng hình ảnh')",
                    "a:has-text('Visual Search'), a:has-text('Tìm kiếm bằng hình ảnh')",
                    "[aria-label*='Visual Search' i], [aria-label*='Tìm kiếm bằng hình ảnh' i]"
                ]
                for sel in selectors:
                    cards = await self.page.query_selector_all(sel)
                    for card in cards:
                        try:
                            if not await card.is_visible():
                                continue
                            # Ensure not in navigation or header
                            is_in_nav = await card.evaluate("el => Boolean(el.closest('header, nav, [role=\"navigation\"], [role=\"banner\"], footer'))")
                            if is_in_nav:
                                continue
                            c_txt = (await card.inner_text() or "").strip()
                            if len(c_txt) > 250:
                                continue
                            await card.click()
                            clicked = True
                            await asyncio.sleep(2.5)
                            break
                        except Exception:
                            pass
                    if clicked:
                        break

                # If new tab opened
                if len(self.context.pages) > initial_pages:
                    new_page = self.context.pages[-1]
                    try:
                        await new_page.wait_for_load_state("domcontentloaded", timeout=15000)
                        await asyncio.sleep(3.0)
                        await new_page.evaluate("window.scrollBy({top: 400, behavior: 'smooth'})")
                        await asyncio.sleep(2.0)
                    except Exception:
                        pass
                    finally:
                        try:
                            await new_page.close()
                        except Exception:
                            pass
                else:
                    # Check if drawer opened
                    drawer = await self.page.query_selector("[role='dialog'], [aria-modal='true'], [class*='drawer'], [class*='flyout'], [class*='Drawer']")
                    if drawer and await drawer.is_visible():
                        await self.handle_drawer_actions()

            # 2. Perform authentic Bing Visual Search query to guarantee reward registration
            await self.perform_bing_visual_search()
            return True

        except Exception as e:
            log_warn(f"Lỗi khi xử lý Visual Search: {e}")
            return False

    async def perform_bing_visual_search(self):
        """Execute authentic Bing Visual Search with varied realistic image query parameters."""
        try:
            log_info("📷 [Visual Search] Đang thực hiện tìm kiếm hình ảnh trên Bing...")
            sample_images = [
                "https%3A%2F%2Fth.bing.com%2Fth%3Fid%3DOMR.VisualSearch.VNext.BackgroundImage.png%26pid%3DRewards",
                "https%3A%2F%2Fth.bing.com%2Fth%3Fid%3DOHR.MilkyWayTasmania_EN-US8181820468_1920x1080.jpg%26pid%3DRewards",
                "https%3A%2F%2Fth.bing.com%2Fth%3Fid%3DOHR.MountRainierFall_EN-US8743120934_1920x1080.jpg%26pid%3DRewards",
                "https%3A%2F%2Fth.bing.com%2Fth%3Fid%3DOHR.BamburghCastle_EN-US9283741823_1920x1080.jpg%26pid%3DRewards",
                "https%3A%2F%2Fth.bing.com%2Fth%3Fid%3DOHR.AutumnMaple_EN-US9182347102_1920x1080.jpg%26pid%3DRewards"
            ]
            chosen_img = random.choice(sample_images)
            target_url = f"https://www.bing.com/images/search?view=detailv2&iss=sbi&FORM=SBIHMP&sbisrc=UrlPaste&q=imgurl:{chosen_img}"
            
            await self.page.goto(target_url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(random.uniform(2.5, 4.0))

            # Scroll down smoothly to trigger results & telemetry
            await self.page.evaluate("window.scrollBy({top: 450, behavior: 'smooth'})")
            await asyncio.sleep(random.uniform(1.8, 3.0))

            # Try hovering or clicking a visual search result/tag if present
            try:
                result_elements = await self.page.query_selector_all(
                    ".img_cont, .vsi_card, a.iusc, [class*='visualSearch'], [class*='item'] a, .b_visualSearch, [data-tag]"
                )
                if result_elements:
                    sample_elem = random.choice(result_elements[:3])
                    if await sample_elem.is_visible():
                        await sample_elem.hover()
                        await asyncio.sleep(random.uniform(1.0, 1.8))
            except Exception:
                pass

            await asyncio.sleep(random.uniform(2.0, 3.5))
            log_success("📷 [Visual Search] Hoàn thành lượt tìm kiếm bằng hình ảnh trên Bing!")
        except Exception as e:
            log_warn(f"Lỗi khi thực hiện Bing Visual Search trực tiếp: {e}")

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

        # 3. Puzzle & Exploration Tasks
        try:
            puzzle_tiles = await page.query_selector_all("[class*='puzzle'], [class*='tile']")
            if puzzle_tiles:
                log_info(f"Phat hien Puzzle ({len(puzzle_tiles)} tiles), dang click tat ca...")
            for p_tile in puzzle_tiles:  # Click ALL tiles, not just 4
                if await p_tile.is_visible():
                    try:
                        await p_tile.click()
                        await asyncio.sleep(0.5)
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
