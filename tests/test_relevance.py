"""Tests for weighted relevance scoring."""

from src.processing.relevance import compute_relevance


def test_primary_keyword_high_weight():
    score = compute_relevance(
        "StarRocks performance tuning",
        "Best practices for StarRocks optimization",
        primary_keywords=["StarRocks"],
        secondary_keywords=[],
        tertiary_keywords=[],
        negative_keywords=[],
    )
    assert score == 0.25


def test_multiple_primary_keywords():
    score = compute_relevance(
        "StarRocks with Apache Spark",
        "Integration guide",
        primary_keywords=["StarRocks", "Apache Spark"],
        secondary_keywords=[],
        tertiary_keywords=[],
        negative_keywords=[],
    )
    assert score == 0.50


def test_secondary_keyword_lower_weight():
    score = compute_relevance(
        "OLAP analytics dashboard",
        "Superset dashboard setup",
        primary_keywords=[],
        secondary_keywords=["OLAP analytics", "Superset dashboard"],
        tertiary_keywords=[],
        negative_keywords=[],
    )
    assert score == 0.30


def test_tertiary_keyword_lowest_weight():
    score = compute_relevance(
        "AI-ready data pipeline",
        "Feature store setup",
        primary_keywords=[],
        secondary_keywords=[],
        tertiary_keywords=["AI-ready data", "feature store"],
        negative_keywords=[],
    )
    assert score == 0.20


def test_mixed_keyword_groups():
    score = compute_relevance(
        "StarRocks OLAP analytics with AI-ready data",
        "",
        primary_keywords=["StarRocks"],
        secondary_keywords=["OLAP analytics"],
        tertiary_keywords=["AI-ready data"],
        negative_keywords=[],
    )
    assert score == 0.50  # 0.25 + 0.15 + 0.10


def test_negative_keyword_returns_zero():
    score = compute_relevance(
        "StarRocks job posting - hiring engineers",
        "We are hiring",
        primary_keywords=["StarRocks"],
        secondary_keywords=[],
        tertiary_keywords=[],
        negative_keywords=["job posting", "hiring"],
    )
    assert score == 0.0


def test_score_capped_at_one():
    score = compute_relevance(
        "StarRocks Apache Spark Apache Iceberg Data Lakehouse Polaris",
        "OLAP analytics real-time analytics Superset dashboard",
        primary_keywords=["StarRocks", "Apache Spark", "Apache Iceberg", "Data Lakehouse"],
        secondary_keywords=["Polaris", "OLAP analytics", "real-time analytics", "Superset dashboard"],
        tertiary_keywords=[],
        negative_keywords=[],
    )
    assert score == 1.0


def test_case_insensitive():
    score = compute_relevance(
        "starrocks BEST PRACTICES",
        "",
        primary_keywords=["StarRocks"],
        secondary_keywords=[],
        tertiary_keywords=[],
        negative_keywords=[],
    )
    assert score == 0.25


def test_empty_text_returns_zero():
    score = compute_relevance(
        "", "",
        primary_keywords=["StarRocks"],
        secondary_keywords=[],
        tertiary_keywords=[],
        negative_keywords=[],
    )
    assert score == 0.0
