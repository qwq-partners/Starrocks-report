"""Base collector class and common data model."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class CollectedArticle:
    """Standardized data model for a collected article."""

    title: str
    url: str
    source: str  # "github", "hackernews", "geeknews", "rss", ...
    source_type: str  # "repository", "article", "discussion", "release", ...
    content_snippet: str = ""
    full_content: Optional[str] = None
    author: Optional[str] = None
    published_at: Optional[datetime] = None
    collected_at: datetime = field(default_factory=datetime.utcnow)
    tags: list[str] = field(default_factory=list)
    relevance_score: float = 0.0
    language: str = "en"
    metadata: dict = field(default_factory=dict)

    # Populated after LLM enrichment
    summary_ko: Optional[str] = None
    summary_en: Optional[str] = None
    category: Optional[str] = None
    relevance_to_team: Optional[str] = None
    key_takeaways: list[str] = field(default_factory=list)
    difficulty: Optional[str] = None


class BaseCollector(ABC):
    """Abstract base class for all source collectors."""

    def __init__(self, keywords: list[str], negative_keywords: list[str], config: dict):
        self.keywords = keywords
        self.negative_keywords = negative_keywords
        self.config = config
        self.max_items = config.get("max_items_per_source", 50)

    @abstractmethod
    async def collect(self) -> list[CollectedArticle]:
        """Collect articles from the source. Must be implemented by subclasses."""
        pass

    @abstractmethod
    def get_source_name(self) -> str:
        """Return the name of this source."""
        pass

    def calculate_relevance(self, article: CollectedArticle) -> float:
        """Calculate relevance score based on keyword matching."""
        text = f"{article.title} {article.content_snippet}".lower()

        # Check negative keywords first
        for neg in self.negative_keywords:
            if neg.lower() in text:
                return 0.0

        score = 0.0
        for keyword in self.keywords:
            if keyword.lower() in text:
                score += 0.15
        return min(score, 1.0)

    def filter_and_score(self, articles: list[CollectedArticle]) -> list[CollectedArticle]:
        """Filter irrelevant articles and assign relevance scores."""
        scored = []
        for article in articles:
            article.relevance_score = self.calculate_relevance(article)
            if article.relevance_score > 0.0:
                scored.append(article)
        return sorted(scored, key=lambda a: a.relevance_score, reverse=True)[: self.max_items]
