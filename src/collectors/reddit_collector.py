"""Reddit collector using public JSON API (no auth required)."""

import asyncio
from datetime import datetime, timedelta, timezone

import aiohttp
import structlog

from .base import BaseCollector, CollectedArticle

logger = structlog.get_logger()

REDDIT_BASE = "https://www.reddit.com"
USER_AGENT = "DailyPracticesCollector/1.0 (data platform BP collector)"


class RedditCollector(BaseCollector):
    def get_source_name(self) -> str:
        return "reddit"

    async def collect(self) -> list[CollectedArticle]:
        reddit_config = self.config.get("reddit", {})
        subreddits = reddit_config.get("subreddits", [])
        min_upvotes = reddit_config.get("min_upvotes", 10)
        if not subreddits:
            return []

        cutoff = datetime.now(timezone.utc) - timedelta(
            hours=self.config.get("lookback_hours", 26)
        )
        articles = []

        headers = {"User-Agent": USER_AGENT}
        async with aiohttp.ClientSession(headers=headers) as session:
            for subreddit in subreddits:
                try:
                    items = await self._fetch_subreddit(
                        session, subreddit, min_upvotes, cutoff
                    )
                    articles.extend(items)
                except Exception as e:
                    logger.error("reddit_error", error=str(e), subreddit=subreddit)
                await asyncio.sleep(self.config.get("rate_limit_delay", 1.0) * 2)

        return self.filter_and_score(articles)

    async def _fetch_subreddit(
        self,
        session: aiohttp.ClientSession,
        subreddit: str,
        min_upvotes: int,
        cutoff: datetime,
    ) -> list[CollectedArticle]:
        """Fetch recent posts from a subreddit via public JSON API."""
        url = f"{REDDIT_BASE}/r/{subreddit}/new.json"
        params = {"limit": 50, "raw_json": 1}
        articles = []

        async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=30)) as resp:
            if resp.status == 429:
                logger.warning("reddit_rate_limited", subreddit=subreddit)
                return []
            if resp.status != 200:
                logger.warning("reddit_fetch_failed", status=resp.status, subreddit=subreddit)
                return []
            data = await resp.json()

        posts = data.get("data", {}).get("children", [])
        for post in posts:
            post_data = post.get("data", {})
            created_utc = post_data.get("created_utc")
            if not created_utc:
                continue
            published_at = datetime.fromtimestamp(created_utc, tz=timezone.utc)
            ups = post_data.get("ups", 0)

            if published_at < cutoff:
                continue
            if ups < min_upvotes:
                continue
            if post_data.get("author") in ("[deleted]", None):
                continue

            selftext = post_data.get("selftext", "") or ""
            if selftext == "[removed]":
                selftext = ""
            permalink = f"https://reddit.com{post_data.get('permalink', '')}"
            url = permalink if post_data.get("is_self") else post_data.get("url", permalink)

            articles.append(
                CollectedArticle(
                    title=post_data.get("title", ""),
                    url=url,
                    source="reddit",
                    source_type="discussion",
                    content_snippet=selftext[:500],
                    author=post_data.get("author"),
                    published_at=published_at,
                    tags=[subreddit],
                    metadata={
                        "upvotes": ups,
                        "num_comments": post_data.get("num_comments", 0),
                        "subreddit": subreddit,
                        "permalink": permalink,
                    },
                )
            )

        logger.info("reddit_fetched", subreddit=subreddit, count=len(articles))
        return articles
