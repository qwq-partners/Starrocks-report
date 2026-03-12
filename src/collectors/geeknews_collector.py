"""GeekNews (news.hada.io) collector via RSS feed scraping."""

import aiohttp
import structlog
from bs4 import BeautifulSoup
from datetime import datetime, timezone

from .base import BaseCollector, CollectedArticle

logger = structlog.get_logger()

GEEKNEWS_RSS = "https://news.hada.io/rss"


class GeekNewsCollector(BaseCollector):
    def get_source_name(self) -> str:
        return "geeknews"

    async def collect(self) -> list[CollectedArticle]:
        if not self.config.get("geeknews", {}).get("enabled", True):
            return []

        articles = []
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(GEEKNEWS_RSS, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                    if resp.status != 200:
                        logger.warning("geeknews_fetch_failed", status=resp.status)
                        return []
                    text = await resp.text()

            soup = BeautifulSoup(text, "xml")
            items = soup.find_all("item")

            for item in items:
                title = item.find("title")
                link = item.find("link")
                description = item.find("description")
                pub_date = item.find("pubDate")

                if not title or not link:
                    continue

                published_at = None
                if pub_date and pub_date.text:
                    try:
                        from email.utils import parsedate_to_datetime
                        published_at = parsedate_to_datetime(pub_date.text)
                    except Exception:
                        pass

                articles.append(
                    CollectedArticle(
                        title=title.text.strip(),
                        url=link.text.strip(),
                        source="geeknews",
                        source_type="article",
                        content_snippet=(description.text.strip() if description else "")[:500],
                        published_at=published_at,
                        language="ko",
                    )
                )

        except Exception as e:
            logger.error("geeknews_error", error=str(e))

        return self.filter_and_score(articles)
