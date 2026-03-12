"""GitHub collector: repos, releases, trending, and search results."""

import asyncio
import os
from datetime import datetime, timedelta, timezone

import aiohttp
import structlog

from .base import BaseCollector, CollectedArticle

logger = structlog.get_logger()

GITHUB_API = "https://api.github.com"


class GitHubCollector(BaseCollector):
    def get_source_name(self) -> str:
        return "github"

    async def collect(self) -> list[CollectedArticle]:
        token = os.environ.get("GITHUB_TOKEN", "")
        headers = {"Accept": "application/vnd.github+json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"

        articles = []
        async with aiohttp.ClientSession(headers=headers) as session:
            tasks = [
                self._collect_search(session),
                self._collect_releases(session),
                self._collect_trending_repos(session),
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for result in results:
                if isinstance(result, Exception):
                    logger.error("github_collector_error", error=str(result))
                    continue
                articles.extend(result)

        return self.filter_and_score(articles)

    async def _collect_search(self, session: aiohttp.ClientSession) -> list[CollectedArticle]:
        """Search GitHub repositories matching our keywords."""
        articles = []
        queries = self.config.get("github", {}).get("search_queries", [])
        cutoff = datetime.now(timezone.utc) - timedelta(hours=self.config.get("lookback_hours", 26))
        date_str = cutoff.strftime("%Y-%m-%d")

        for query in queries:
            url = f"{GITHUB_API}/search/repositories"
            params = {"q": f"{query} pushed:>{date_str}", "sort": "stars", "per_page": 10}
            try:
                async with session.get(url, params=params) as resp:
                    if resp.status != 200:
                        logger.warning("github_search_failed", status=resp.status, query=query)
                        continue
                    data = await resp.json()
                    for repo in data.get("items", []):
                        articles.append(
                            CollectedArticle(
                                title=f"[GitHub] {repo['full_name']} - {repo.get('description', '')}",
                                url=repo["html_url"],
                                source="github",
                                source_type="repository",
                                content_snippet=repo.get("description", "") or "",
                                author=repo["owner"]["login"],
                                published_at=datetime.fromisoformat(
                                    repo["updated_at"].replace("Z", "+00:00")
                                ),
                                tags=repo.get("topics", []),
                                language=repo.get("language", "unknown") or "unknown",
                                metadata={
                                    "stars": repo["stargazers_count"],
                                    "forks": repo["forks_count"],
                                    "open_issues": repo["open_issues_count"],
                                },
                            )
                        )
            except Exception as e:
                logger.error("github_search_error", error=str(e), query=query)

            await asyncio.sleep(self.config.get("rate_limit_delay", 1.0))

        return articles

    async def _collect_releases(self, session: aiohttp.ClientSession) -> list[CollectedArticle]:
        """Check for new releases in tracked repositories."""
        articles = []
        repos = self.config.get("github", {}).get("repositories", [])
        cutoff = datetime.now(timezone.utc) - timedelta(hours=self.config.get("lookback_hours", 26))

        for repo in repos:
            url = f"{GITHUB_API}/repos/{repo}/releases"
            params = {"per_page": 5}
            try:
                async with session.get(url, params=params) as resp:
                    if resp.status != 200:
                        continue
                    releases = await resp.json()
                    for release in releases:
                        pub_date = datetime.fromisoformat(
                            release["published_at"].replace("Z", "+00:00")
                        )
                        if pub_date < cutoff:
                            continue
                        articles.append(
                            CollectedArticle(
                                title=f"[Release] {repo} {release['tag_name']}",
                                url=release["html_url"],
                                source="github",
                                source_type="release",
                                content_snippet=release.get("body", "")[:500],
                                author=release.get("author", {}).get("login"),
                                published_at=pub_date,
                                tags=["release", repo.split("/")[0]],
                            )
                        )
            except Exception as e:
                logger.error("github_release_error", error=str(e), repo=repo)

            await asyncio.sleep(self.config.get("rate_limit_delay", 1.0))

        return articles

    async def _collect_trending_repos(
        self, session: aiohttp.ClientSession
    ) -> list[CollectedArticle]:
        """Search for recently created high-star repos related to our keywords."""
        articles = []
        cutoff = datetime.now(timezone.utc) - timedelta(days=7)
        date_str = cutoff.strftime("%Y-%m-%d")

        for keyword in ["starrocks", "spark lakehouse", "iceberg", "data lakehouse"]:
            url = f"{GITHUB_API}/search/repositories"
            params = {
                "q": f"{keyword} created:>{date_str}",
                "sort": "stars",
                "order": "desc",
                "per_page": 5,
            }
            try:
                async with session.get(url, params=params) as resp:
                    if resp.status != 200:
                        continue
                    data = await resp.json()
                    for repo in data.get("items", []):
                        if repo["stargazers_count"] < 3:
                            continue
                        articles.append(
                            CollectedArticle(
                                title=f"[Trending] {repo['full_name']} ({repo['stargazers_count']}★)",
                                url=repo["html_url"],
                                source="github",
                                source_type="trending",
                                content_snippet=repo.get("description", "") or "",
                                author=repo["owner"]["login"],
                                tags=repo.get("topics", []),
                                metadata={"stars": repo["stargazers_count"]},
                            )
                        )
            except Exception as e:
                logger.error("github_trending_error", error=str(e), keyword=keyword)

            await asyncio.sleep(self.config.get("rate_limit_delay", 1.0))

        return articles
