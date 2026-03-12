"""Hacker News collector using the Algolia Search API."""

import asyncio
from datetime import datetime, timedelta, timezone

import aiohttp
import structlog

from .base import BaseCollector, CollectedArticle

logger = structlog.get_logger()

HN_SEARCH_API = "https://hn.algolia.com/api/v1/search"


class HackerNewsCollector(BaseCollector):
    def get_source_name(self) -> str:
        return "hackernews"

    async def collect(self) -> list[CollectedArticle]:
        articles = []
        queries = self.config.get("hackernews", {}).get("search_queries", [])
        min_points = self.config.get("hackernews", {}).get("min_points", 5)
        cutoff = datetime.now(timezone.utc) - timedelta(hours=self.config.get("lookback_hours", 26))
        cutoff_ts = int(cutoff.timestamp())

        async with aiohttp.ClientSession() as session:
            for query in queries:
                params = {
                    "query": query,
                    "tags": "story",
                    "numericFilters": f"created_at_i>{cutoff_ts},points>{min_points}",
                    "hitsPerPage": 20,
                }
                try:
                    async with session.get(HN_SEARCH_API, params=params) as resp:
                        if resp.status != 200:
                            logger.warning("hn_search_failed", status=resp.status, query=query)
                            continue
                        data = await resp.json()
                        for hit in data.get("hits", []):
                            url = hit.get("url") or f"https://news.ycombinator.com/item?id={hit['objectID']}"
                            articles.append(
                                CollectedArticle(
                                    title=hit.get("title", ""),
                                    url=url,
                                    source="hackernews",
                                    source_type="article",
                                    content_snippet=hit.get("story_text", "") or "",
                                    author=hit.get("author"),
                                    published_at=datetime.fromtimestamp(
                                        hit["created_at_i"], tz=timezone.utc
                                    ),
                                    metadata={
                                        "points": hit.get("points", 0),
                                        "num_comments": hit.get("num_comments", 0),
                                        "hn_id": hit["objectID"],
                                    },
                                )
                            )
                except Exception as e:
                    logger.error("hn_search_error", error=str(e), query=query)

                await asyncio.sleep(self.config.get("rate_limit_delay", 1.0))

        return self.filter_and_score(articles)
