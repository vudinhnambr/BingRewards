import asyncio
import re
import json
import logging
from datetime import datetime
from playwright.async_api import Page
from src.utils import log_info, log_warn, log_success, is_bot_blocked

logger = logging.getLogger(__name__)


class UrlRewardHandler:
    """Complete Microsoft Rewards urlreward promotions via Next.js server actions.

    Reference: TheNetsky/Microsoft-Rewards-Script v4 UrlReward.ts

    Modern dashboard (v4, 2025+) requires POST to /earn with Next-Action header
    instead of simple URL visits.
    """

    SKIP_TITLES = [
        "Set a Rewards goal",
        "Join Microsoft Rewards",
    ]

    ACTION_ID_PATTERNS = [
        r'reportActivity["\']?\s*:\s*["\']([a-f0-9]{40})',
        r'setGoal["\']?\s*:\s*["\']([a-f0-9]{40})',
        r'completeOffer["\']?\s*:\s*["\']([a-f0-9]{40})',
        r'["\']([a-f0-9]{40})["\']\s*[,\s]*reportActivity',
    ]

    def __init__(self, page: Page):
        self.page = page
        self.action_id: str | None = None
        self.router_tree: str | None = None
        self.deployment_id: str | None = None

    async def run(self) -> dict:
        """Main entry: bootstrap → detect block → find/complete offers."""
        log_info("=== Phase: UrlReward Server-Action Handler ===")

        bootstrap_ok = await self.bootstrap()
        if not bootstrap_ok:
            return {"status": "bootstrap_failed", "completed": [], "skipped": []}

        blocked, reason = await is_bot_blocked(self.page)
        if blocked:
            log_warn(f"⚠️  Bot-block detected ({reason}) - skipping urlreward phase")
            log_warn("   Searches will still run, but Microsoft may not credit points")
            return {"status": "bot_blocked", "reason": reason, "completed": [], "skipped": []}

        offers = await self.find_incomplete_urlrewards()
        if not offers:
            log_info("No incomplete urlreward promotions found")
            return {"status": "no_offers", "completed": [], "skipped": []}

        log_info(f"Found {len(offers)} incomplete urlreward promotion(s)")

        completed, skipped = [], []
        for offer in offers:
            success = await self.complete_offer(offer)
            if success:
                completed.append(offer["title"])
                log_success(f"✅ Completed: {offer['title']} (+{offer['points']} pts)")
            else:
                skipped.append(offer["title"])
                log_warn(f"⚠️  Failed: {offer['title']}")
            await asyncio.sleep(2)

        return {
            "status": "ok",
            "completed": completed,
            "skipped": skipped,
            "total_found": len(offers),
        }

    async def bootstrap(self) -> bool:
        """Visit /earn, dismiss welcome dialog, extract tokens."""
        try:
            # Try /earn first, fallback to /dashboard
            for url in ["https://rewards.bing.com/earn", "https://rewards.bing.com/dashboard"]:
                try:
                    await self.page.goto(url, wait_until="domcontentloaded", timeout=30000)
                    await asyncio.sleep(3)
                    body_text = await self.page.evaluate("document.body?.innerText?.length || 0")
                    if body_text > 200:
                        log_info(f"Bootstrap: loaded {url} ({body_text} chars)")
                        break
                except Exception:
                    continue

            # Dismiss welcome dialog if present
            try:
                close_btn = await self.page.wait_for_selector(
                    "section[role='dialog'] button[slot='close'], [role='dialog'] button[aria-label*='Close']",
                    timeout=3000,
                )
                await close_btn.click()
                await asyncio.sleep(1.5)
                log_info("Dismissed welcome dialog")
            except Exception:
                pass

            # Wait for any dashboard content (not just section#dailyset)
            try:
                await self.page.wait_for_selector(
                    "section#dailyset, [class*='dashboard'], [class*='Dashboard'], [data-testid], mee-card",
                    timeout=10000,
                )
            except Exception:
                log_warn("Dashboard content not fully loaded - continuing anyway")

            # Extract router tree from RSC payload
            self.router_tree = await self.page.evaluate(
                """
                () => {
                    const scripts = document.querySelectorAll('script');
                    for (const s of scripts) {
                        const txt = s.textContent || '';
                        if (txt.includes('routerState') || txt.includes('__next_f')
                            || txt.includes('server-actions') || txt.includes('actionId')) {
                            return txt.substring(0, 50000);
                        }
                    }
                    // Fallback: return all inline script content joined
                    let combined = '';
                    for (const s of scripts) {
                        if (s.textContent) combined += s.textContent + '\\n';
                        if (combined.length > 50000) break;
                    }
                    return combined || null;
                }
                """
            )

            self.action_id = await self._resolve_action_id()
            self.deployment_id = await self._extract_deployment_id()

            if not self.action_id:
                log_warn("Failed to resolve Next-Action ID - trying inline script extraction")
                self.action_id = await self._resolve_action_id_from_inline()

            if not self.action_id:
                log_warn("All action_id resolution methods failed - urlreward phase will skip")
                return False

            log_info(f"Bootstrap OK: action_id={self.action_id[:12]}...")
            return True

        except Exception as e:
            log_warn(f"Bootstrap failed: {e}")
            return False

    async def _resolve_action_id(self) -> str | None:
        """Find reportActivity Next-Action ID from Next.js JS chunks."""
        try:
            chunk_urls = await self.page.evaluate(
                """
                () => Array.from(document.querySelectorAll('script[src]'))
                    .map(s => s.src)
                    .filter(s => s.includes('/_next/static/chunks/') || s.includes('/_next/static/'))
                """
            )

            log_info(f"Found {len(chunk_urls)} JS chunks to scan")
            for url in chunk_urls[:50]:
                try:
                    resp = await self.page.request.get(url, timeout=8000)
                    if resp.status != 200:
                        continue
                    text = await resp.text()
                    for pattern in self.ACTION_ID_PATTERNS:
                        match = re.search(pattern, text)
                        if match:
                            return match.group(1)
                except Exception:
                    continue
        except Exception as e:
            log_warn(f"_resolve_action_id error: {e}")
        return None

    async def _resolve_action_id_from_inline(self) -> str | None:
        """Fallback: search inline scripts for action IDs."""
        try:
            inline_scripts = await self.page.evaluate(
                """
                () => Array.from(document.querySelectorAll('script:not([src])'))
                    .map(s => s.textContent || '')
                    .filter(t => t.length > 50)
                """
            )
            for text in inline_scripts:
                for pattern in self.ACTION_ID_PATTERNS:
                    match = re.search(pattern, text)
                    if match:
                        return match.group(1)
                # Generic: look for 40-char hex near action keywords
                match = re.search(r'action["\']?\s*:\s*["\']([a-f0-9]{40})', text)
                if match:
                    return match.group(1)
        except Exception as e:
            log_warn(f"_resolve_action_id_from_inline error: {e}")
        return None

    async def _extract_deployment_id(self) -> str | None:
        try:
            return await self.page.evaluate(
                "() => document.querySelector('meta[name=\"deployment-id\"]')?.content || null"
            )
        except Exception:
            return None

    async def get_userinfo(self) -> dict:
        """Fetch dashboard JSON via legacy getuserinfo API."""
        try:
            resp = await self.page.request.get(
                "https://rewards.bing.com/api/getuserinfo",
                timeout=15000,
            )
            if resp.status == 200:
                return await resp.json()
        except Exception as e:
            log_warn(f"getuserinfo failed: {e}")
        return {}

    async def find_incomplete_urlrewards(self) -> list:
        """Return list of urlreward offers that are not yet complete."""
        data = await self.get_userinfo()
        if not data:
            return []

        dashboard = data.get("dashboard", {})
        promotions = (
            dashboard.get("morePromotions", [])
            + dashboard.get("dailySetPromotions", [])
            + dashboard.get("promotions", [])
        )

        result = []
        for promo in promotions:
            title = promo.get("title", "")
            if not title:
                continue
            if any(skip.lower() in title.lower() for skip in self.SKIP_TITLES):
                continue
            if promo.get("complete"):
                continue
            if promo.get("promotionType") != "urlreward":
                continue
            points = promo.get("pointProgressMax", 0)
            if points <= 0:
                continue
            result.append({
                "offerId": promo.get("offerId"),
                "title": title,
                "hash": promo.get("hash", ""),
                "points": points,
            })
        return result

    async def complete_offer(self, offer: dict) -> bool:
        """POST server action to mark urlreward offer complete."""
        if not self.action_id:
            return False

        try:
            tz_offset = int(-datetime.now().astimezone().utcoffset().total_seconds() / 60)

            body = json.dumps([
                offer.get("hash", ""),
                11,
                {
                    "offerid": offer.get("offerId"),
                    "isPromotional": True,
                    "timezoneOffset": tz_offset,
                },
            ])

            headers = {
                "Next-Action": self.action_id,
                "Content-Type": "text/plain;charset=UTF-8",
                "Accept": "text/x-component",
            }
            if self.router_tree:
                headers["Next-Router-State-Tree"] = self.router_tree[:8000]
            if self.deployment_id:
                headers["X-Deployment-Id"] = self.deployment_id

            resp = await self.page.request.post(
                "https://rewards.bing.com/earn",
                headers=headers,
                data=body,
                timeout=15000,
            )
            return resp.status == 200

        except Exception as e:
            log_warn(f"complete_offer error: {e}")
            return False
