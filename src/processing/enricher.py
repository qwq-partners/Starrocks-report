"""LLM-based content enrichment using Claude API."""

import asyncio
import json
import os

import anthropic
import structlog

from ..collectors.base import CollectedArticle

logger = structlog.get_logger()

SUMMARIZE_PROMPT = """당신은 Data Platform 팀의 기술 리서처입니다.
아래 아티클을 분석하여 JSON 형식으로 응답하세요.

팀 컨텍스트:
- 환경: k8s + Iceberg + Polaris + DataHub + Spark + StarRocks + S3
- 목표: AI-Ready Data 서비스 구축
- 사용자: Superset/StarRocks/Spark 기반 분석

아티클:
제목: {title}
URL: {url}
본문: {content}

반드시 아래 JSON 형식만 응답하세요 (다른 텍스트 없이):
{{
  "summary_ko": "3-5문장 한국어 요약",
  "summary_en": "3-5 sentence English summary",
  "category": "StarRocks|Spark|Iceberg|Lakehouse|AI-Data|Infrastructure|Other 중 하나",
  "relevance_to_team": "high|medium|low 중 하나",
  "key_takeaways": ["핵심 포인트 1", "핵심 포인트 2"],
  "difficulty": "beginner|intermediate|advanced 중 하나"
}}"""

MAX_CONCURRENT = 5


class Enricher:
    """Enrich articles with LLM-generated summaries and classifications."""

    def __init__(self, model: str = "claude-sonnet-4-6", max_articles: int = 30):
        self.model = model
        self.max_articles = max_articles
        self._api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        self.client = anthropic.AsyncAnthropic(api_key=self._api_key) if self._api_key else None

    async def enrich_articles(self, articles: list[CollectedArticle]) -> list[CollectedArticle]:
        """Enrich top articles with LLM summaries."""
        if not self.client:
            logger.warning("enrichment_skipped", reason="ANTHROPIC_API_KEY not set")
            return articles

        sorted_articles = sorted(articles, key=lambda a: a.relevance_score, reverse=True)
        to_enrich = sorted_articles[: self.max_articles]

        semaphore = asyncio.Semaphore(MAX_CONCURRENT)

        async def _enrich_one(article: CollectedArticle):
            async with semaphore:
                try:
                    result = await self._summarize(article)
                    article.summary_ko = result.get("summary_ko")
                    article.summary_en = result.get("summary_en")
                    article.category = result.get("category")
                    article.relevance_to_team = result.get("relevance_to_team")
                    article.key_takeaways = result.get("key_takeaways", [])
                    article.difficulty = result.get("difficulty")
                    logger.info("enriched_article", title=article.title[:60])
                except Exception as e:
                    logger.error("enrichment_error", error=str(e), title=article.title[:60])

        await asyncio.gather(*[_enrich_one(a) for a in to_enrich])
        return articles

    async def _summarize(self, article: CollectedArticle) -> dict:
        content = article.full_content or article.content_snippet
        prompt = SUMMARIZE_PROMPT.format(
            title=article.title, url=article.url, content=content[:3000]
        )

        response = await self.client.messages.create(
            model=self.model,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )

        text = response.content[0].text.strip()
        # Extract JSON from response
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        return json.loads(text)
