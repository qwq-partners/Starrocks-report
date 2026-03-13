"""Tests for collector base class and relevance integration."""

from src.collectors.base import BaseCollector, CollectedArticle


class DummyCollector(BaseCollector):
    """Concrete collector for testing."""

    async def collect(self):
        return []

    def get_source_name(self):
        return "test"


def test_calculate_relevance_with_keyword_groups():
    groups = {
        "primary": ["StarRocks", "Apache Spark"],
        "secondary": ["OLAP analytics"],
        "tertiary": ["AI-ready data"],
        "enterprise": ["Baidu data platform"],
    }
    collector = DummyCollector(
        keywords=[], negative_keywords=["hiring"],
        config={}, keyword_groups=groups,
    )
    article = CollectedArticle(
        title="StarRocks OLAP analytics",
        url="https://example.com",
        source="test",
        source_type="article",
    )
    score = collector.calculate_relevance(article)
    assert score == 0.40  # primary 0.25 + secondary 0.15


def test_calculate_relevance_fallback_without_groups():
    collector = DummyCollector(
        keywords=["StarRocks", "Spark"],
        negative_keywords=[],
        config={},
        keyword_groups=None,
    )
    article = CollectedArticle(
        title="StarRocks and Spark integration",
        url="https://example.com",
        source="test",
        source_type="article",
    )
    score = collector.calculate_relevance(article)
    assert score == 0.30  # 2 keywords × 0.15


def test_negative_keyword_blocks_scoring():
    groups = {"primary": ["StarRocks"], "secondary": [], "tertiary": [], "enterprise": []}
    collector = DummyCollector(
        keywords=[], negative_keywords=["hiring"],
        config={}, keyword_groups=groups,
    )
    article = CollectedArticle(
        title="StarRocks hiring engineers",
        url="https://example.com",
        source="test",
        source_type="article",
    )
    score = collector.calculate_relevance(article)
    assert score == 0.0


def test_filter_and_score_removes_irrelevant():
    groups = {"primary": ["StarRocks"], "secondary": [], "tertiary": [], "enterprise": []}
    collector = DummyCollector(
        keywords=[], negative_keywords=[],
        config={"max_items_per_source": 50},
        keyword_groups=groups,
    )
    articles = [
        CollectedArticle(
            title="StarRocks guide",
            url="https://a.com",
            source="test", source_type="article",
        ),
        CollectedArticle(
            title="Unrelated Python Flask tutorial",
            url="https://b.com",
            source="test", source_type="article",
        ),
    ]
    filtered = collector.filter_and_score(articles)
    assert len(filtered) == 1
    assert filtered[0].title == "StarRocks guide"
    assert filtered[0].relevance_score > 0


def test_filter_and_score_respects_max_items():
    groups = {"primary": ["test"], "secondary": [], "tertiary": [], "enterprise": []}
    collector = DummyCollector(
        keywords=[], negative_keywords=[],
        config={"max_items_per_source": 2},
        keyword_groups=groups,
    )
    articles = [
        CollectedArticle(
            title=f"test article {i}",
            url=f"https://example.com/{i}",
            source="test", source_type="article",
        )
        for i in range(10)
    ]
    filtered = collector.filter_and_score(articles)
    assert len(filtered) == 2
