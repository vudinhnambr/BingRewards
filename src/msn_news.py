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
            # Navigate to MSN News
            await self.page.goto("https://www.msn.com/en-us/news", wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(3)

            # Find news article links
            articles = await self.page.query_selector_all("a[href*='/en-us/news/'], a[href*='/en-us/feed/']")
            urls = []
            for a in articles:
                href = await a.get_attribute("href")
                if href and ("http" in href or href.startswith("/")) and href not in urls:
                    full_url = href if href.startswith("http") else f"https://www.msn.com{href}"
                    if not any(x in full_url for x in ["weather", "sports/scores", "video"]):
                        urls.append(full_url)
                if len(urls) >= count + 5:
                    break

            log_info(f"Tìm thấy {len(urls)} bài báo tin tức. Đang tiến hành đọc...")

            read_count = 0
            for i, url in enumerate(urls[:count], start=1):
                try:
                    await self.page.goto(url, wait_until="domcontentloaded", timeout=25000)
                    
                    # Simulate human reading: scroll down slowly
                    for _ in range(3):
                        scroll = random.randint(400, 800)
                        await self.page.evaluate(f"window.scrollBy(0, {scroll})")
                        await asyncio.sleep(random.uniform(1.2, 2.5))

                    read_count += 1
                    log_info(f"[{i}/{count}] Đã đọc bài báo #{i}...")
                    await random_delay(3.0, 5.0)

                except Exception as e:
                    log_warn(f"Lỗi khi đọc bài báo #{i}: {e}")

            log_success(f"Hoàn thành đọc {read_count} bài báo trên MSN News!")
        except Exception as e:
            log_warn(f"Lỗi khi thực hiện đọc báo MSN: {e}")
