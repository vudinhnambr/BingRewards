import asyncio
import random
from playwright.async_api import Page, BrowserContext
from src.utils import log_info, log_success, log_warn, random_delay

class MSNNewsReader:
    """Automates MSN News reading to earn the 'Read to Earn' mobile bonus (+30 points/day)."""

    def __init__(self, page: Page, context: BrowserContext):
        self.page = page
        self.context = context

    async def read_articles(self, count: int = 10):
        """Browse MSN news articles to trigger read rewards."""
        log_info(f"📰 Bắt đầu đọc {count} bài báo trên MSN News (Read to Earn bonus)...")
        try:
            # Navigate to MSN News - try multiple URLs
            for msn_url in ["https://www.msn.com/en-us/news", "https://www.msn.com/news", "https://www.msn.com/"]:
                try:
                    await self.page.goto(msn_url, wait_until="domcontentloaded", timeout=30000)
                    await asyncio.sleep(3)
                    # Check if page loaded successfully
                    if "msn.com" in self.page.url:
                        break
                except Exception:
                    continue

            # Dismiss any cookie/consent popups
            try:
                accept_btn = await self.page.query_selector("button:has-text('Accept'), button:has-text('I agree'), button:has-text('OK'), #onetrust-accept-btn-handler")
                if accept_btn and await accept_btn.is_visible():
                    await accept_btn.click()
                    await asyncio.sleep(1)
            except Exception:
                pass

            # Scroll down to load more content
            for _ in range(3):
                await self.page.evaluate("window.scrollBy(0, 800)")
                await asyncio.sleep(1.5)

            # Find news article links with multiple selector strategies
            urls = []
            article_selectors = [
                "a[href*='/en-us/news/']",
                "a[href*='/en-us/feed/']",
                "a[href*='/news/']",
                "a[href*='article']",
                "a[class*='card']",
                "a[class*='Card']",
                "a[class*='article']",
                "a[class*='headline']",
                "[class*='card'] a",
                "[class*='Card'] a",
                "[data-t] a",
                "a[href*='msn.com'][href*='news']",
            ]

            for selector in article_selectors:
                try:
                    articles = await self.page.query_selector_all(selector)
                    for a in articles:
                        try:
                            href = await a.get_attribute("href")
                            if not href:
                                continue
                            # Make absolute URL
                            full_url = href if href.startswith("http") else f"https://www.msn.com{href}"
                            # Filter out non-article URLs
                            skip_patterns = ["weather", "sports/scores", "video", "login", "signin", "account", "#", "javascript:"]
                            if any(x in full_url.lower() for x in skip_patterns):
                                continue
                            # Must be on msn.com domain
                            if "msn.com" not in full_url:
                                continue
                            if full_url not in urls:
                                urls.append(full_url)
                        except Exception:
                            continue
                    if len(urls) >= count + 5:
                        break
                except Exception:
                    continue

            # Fallback: get all visible links if no articles found
            if not urls:
                log_info("Không tìm thấy bài báo qua selector, thử lấy tất cả link...")
                all_links = await self.page.query_selector_all("a[href]")
                for a in all_links:
                    try:
                        href = await a.get_attribute("href")
                        if href and href.startswith("http") and "msn.com" in href and len(href) > 30:
                            text = (await a.text_content() or "").strip()
                            if len(text) > 20:  # Likely an article headline
                                urls.append(href)
                    except Exception:
                        continue
                    if len(urls) >= count + 5:
                        break

            log_info(f"Tìm thấy {len(urls)} bài báo tin tức. Đang tiến hành đọc...")

            read_count = 0
            for i, url in enumerate(urls[:count], start=1):
                try:
                    await self.page.goto(url, wait_until="domcontentloaded", timeout=25000)

                    # Simulate human reading: scroll down slowly
                    for _ in range(4):
                        scroll = random.randint(400, 800)
                        await self.page.evaluate(f"window.scrollBy(0, {scroll})")
                        await asyncio.sleep(random.uniform(2.5, 5.5))

                        # Occasionally scroll up a bit
                        if random.choice([True, False]):
                            await self.page.evaluate(f"window.scrollBy(0, -{random.randint(100, 300)})")
                            await asyncio.sleep(random.uniform(1.0, 2.5))

                    read_count += 1
                    log_info(f"[{i}/{count}] Đã đọc bài báo #{i}...")
                    await random_delay(5.0, 10.0)

                except Exception as e:
                    log_warn(f"Lỗi khi đọc bài báo #{i}: {e}")

            log_success(f"Hoàn thành đọc {read_count} bài báo trên MSN News!")
        except Exception as e:
            log_warn(f"Lỗi khi thực hiện đọc báo MSN: {e}")
