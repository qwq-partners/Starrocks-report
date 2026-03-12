"""Generic RSS/Atom feed collector."""

import asyncio
from datetime import datetime, timezone

import aiohttp
import feedparser
import structlog

from .base import BaseCollector, CollectedArticle

logger = structlog.get_logger()


class RSSCollector(BaseCollector):
    def get_source_name(self) -> str:
        return "rss"

    async def collect(self) -> list[CollectedArticle]:
        feeds = self.config.get("rss_feeds", [])
        articles = []

        async with aiohttp.ClientSession() as session:
            for feed_config in feeds:
                try:
                    items = await self._fetch_feed(session, feed_config)
                    articles.extend(items)
                except Exception as e:
                    logger.error(
                        "rss_feed_error", error=str(e), feed=feed_config.get("name")
                    )
                await asyncio.sleep(self.config.get("rate_limit_delay", 1.0))

        return self.filter_and_score(articles)

    async def _fetch_feed(
        self, session: aiohttp.ClientSession, feed_config: dict
    ) -> list[CollectedArticle]:
        url = feed_config["url"]
        category = feed_config.get("category", "general")

        async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
            if resp.status != 200:
                logger.warning("rss_fetch_failed", status=resp.status, url=url)
                return []
            text = await resp.text()

        feed = feedparser.parse(text)
        articles = []

        for entry in feed.entries[:self.max_items]:
            published_at = None
            if hasattr(entry, "published_parsed") and entry.published_parsed:
                try:
                    published_at = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
                except Exception:
                    pass

            content = ""
            if hasattr(entry, "summary"):
                content = entry.summary
            elif hasattr(entry, "content") and entry.content:
                content = entry.content[0].get("value", "")

            articles.append(
                CollectedArticle(
                    title=entry.get("title", ""),
                    url=entry.get("link", ""),
                    source="rss",
                    source_type="article",
                    content_snippet=content[:500],
                    author=entry.get("author"),
                    published_at=published_at,
                    tags=[category],
                    metadata={"feed_name": feed_config["name"]},
                )
            )

        return articles
