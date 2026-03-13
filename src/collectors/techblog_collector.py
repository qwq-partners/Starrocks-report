"""Enterprise tech blog collector via RSS feeds and HTML scraping."""

import asyncio
from datetime import datetime, timezone

import aiohttp
import feedparser
import structlog
from bs4 import BeautifulSoup

from .base import BaseCollector, CollectedArticle

logger = structlog.get_logger()


class TechBlogCollector(BaseCollector):
    def get_source_name(self) -> str:
        return "techblog"

    async def collect(self) -> list[CollectedArticle]:
        blogs = self.config.get("tech_blogs", [])
        if not blogs:
            return []

        articles = []
        async with aiohttp.ClientSession(
            headers={"User-Agent": "DailyPracticesCollector/1.0"},
            timeout=aiohttp.ClientTimeout(total=30),
        ) as session:
            for blog in blogs:
                try:
                    method = blog.get("scrape_method", "rss")
                    if method == "rss":
                        items = await self._collect_rss(session, blog)
                    else:
                        items = await self._collect_html(session, blog)
                    articles.extend(items)
                    logger.info(
                        "techblog_fetched",
                        blog=blog.get("name"),
                        count=len(items),
                    )
                except Exception as e:
                    logger.error(
                        "techblog_error", error=str(e), blog=blog.get("name")
                    )
                await asyncio.sleep(self.config.get("rate_limit_delay", 1.0))

        return self.filter_and_score(articles)

    async def _collect_rss(
        self, session: aiohttp.ClientSession, blog: dict
    ) -> list[CollectedArticle]:
        """Collect from blogs that provide RSS/Atom feeds."""
        url = blog["url"]
        if not url.endswith(("/rss", "/feed", "/atom.xml", ".xml")):
            # Try common RSS paths
            for suffix in ["/rss", "/feed", "/rss.xml", "/atom.xml"]:
                try_url = url.rstrip("/") + suffix
                async with session.get(try_url) as resp:
                    if resp.status == 200:
                        url = try_url
                        break
                    await asyncio.sleep(0.3)
            else:
                logger.warning("techblog_no_rss", blog=blog.get("name"), url=blog["url"])
                return []

        async with session.get(url) as resp:
            if resp.status != 200:
                logger.warning("techblog_rss_failed", status=resp.status, url=url)
                return []
            text = await resp.text()

        feed = feedparser.parse(text)
        articles = []
        lang = blog.get("language", "en")
        category = blog.get("category", "general")

        for entry in feed.entries[:self.max_items]:
            published_at = None
            if hasattr(entry, "published_parsed") and entry.published_parsed:
                try:
                    published_at = datetime(
                        *entry.published_parsed[:6], tzinfo=timezone.utc
                    )
                except Exception:
                    pass

            content = ""
            if hasattr(entry, "summary"):
                content = entry.summary
            elif hasattr(entry, "content") and entry.content:
                content = entry.content[0].get("value", "")

            # Strip HTML tags from content snippet
            if "<" in content:
                content = BeautifulSoup(content, "html.parser").get_text(separator=" ")

            articles.append(
                CollectedArticle(
                    title=entry.get("title", ""),
                    url=entry.get("link", ""),
                    source="techblog",
                    source_type="article",
                    content_snippet=content[:500],
                    author=entry.get("author"),
                    published_at=published_at,
                    tags=[category, blog.get("name", "")],
                    language=lang,
                    metadata={"blog_name": blog["name"]},
                )
            )

        return articles

    async def _collect_html(
        self, session: aiohttp.ClientSession, blog: dict
    ) -> list[CollectedArticle]:
        """Scrape articles from blog HTML pages."""
        url = blog["url"]
        async with session.get(url) as resp:
            if resp.status != 200:
                logger.warning("techblog_html_failed", status=resp.status, url=url)
                return []
            text = await resp.text()

        soup = BeautifulSoup(text, "html.parser")
        articles = []
        lang = blog.get("language", "en")
        selectors = blog.get("selectors", {})

        # Try common article list patterns
        article_selector = selectors.get("article", "article, .post, .article-item, .entry")
        title_selector = selectors.get("title", "h2 a, h3 a, .title a, .post-title a")
        snippet_selector = selectors.get("snippet", "p, .summary, .excerpt, .description")

        article_elements = soup.select(article_selector)[:self.max_items]

        if not article_elements:
            # Fallback: just look for links with keywords
            article_elements = soup.find_all("a", href=True)

        for el in article_elements:
            title_el = el.select_one(title_selector) if el.name != "a" else el
            if not title_el:
                continue

            title = title_el.get_text(strip=True)
            href = title_el.get("href", "")
            if not title or not href:
                continue

            # Make absolute URL
            if href.startswith("/"):
                from urllib.parse import urlparse
                parsed = urlparse(url)
                href = f"{parsed.scheme}://{parsed.netloc}{href}"
            elif not href.startswith("http"):
                continue

            snippet = ""
            snippet_el = el.select_one(snippet_selector) if el.name != "a" else None
            if snippet_el:
                snippet = snippet_el.get_text(strip=True)[:500]

            articles.append(
                CollectedArticle(
                    title=title,
                    url=href,
                    source="techblog",
                    source_type="article",
                    content_snippet=snippet,
                    language=lang,
                    tags=[blog.get("category", "general"), blog.get("name", "")],
                    metadata={"blog_name": blog["name"]},
                )
            )

        return articles
