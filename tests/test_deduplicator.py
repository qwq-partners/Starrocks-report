"""Tests for the deduplication module."""

from src.collectors.base import CollectedArticle
from src.processing.deduplicator import Deduplicator, _simhash_tokens, _hamming_distance
from src.processing.normalizer import normalize_url


def make_article(title: str, url: str, snippet: str = "") -> CollectedArticle:
    return CollectedArticle(
        title=title,
        url=url,
        source="test",
        source_type="article",
        content_snippet=snippet,
    )


def test_normalize_url_removes_tracking():
    assert normalize_url("https://example.com/path?utm_source=twitter&id=1") == \
           "https://example.com/path?id=1"


def test_normalize_url_removes_www():
    assert normalize_url("https://www.example.com/path") == \
           "https://example.com/path"


def test_normalize_url_removes_trailing_slash():
    assert normalize_url("https://example.com/path/") == \
           "https://example.com/path"


def test_simhash_identical_texts():
    h1 = _simhash_tokens("StarRocks best practices for data lakehouse")
    h2 = _simhash_tokens("StarRocks best practices for data lakehouse")
    assert h1 == h2


def test_simhash_similar_texts():
    h1 = _simhash_tokens("StarRocks best practices for data lakehouse architecture")
    h2 = _simhash_tokens("StarRocks best practices for data lakehouse design")
    assert _hamming_distance(h1, h2) <= 10


def test_simhash_different_texts():
    h1 = _simhash_tokens("StarRocks best practices for data lakehouse")
    h2 = _simhash_tokens("Python web framework comparison Flask vs Django")
    assert _hamming_distance(h1, h2) > 5


def test_dedup_url_exact():
    dedup = Deduplicator()
    articles = [
        make_article("Article 1", "https://example.com/a"),
        make_article("Article 1 copy", "https://example.com/a"),
        make_article("Article 2", "https://example.com/b"),
    ]
    result = dedup.deduplicate(articles)
    assert len(result) == 2


def test_dedup_url_with_tracking():
    dedup = Deduplicator()
    articles = [
        make_article("Article 1", "https://example.com/a"),
        make_article("Article 1", "https://example.com/a?utm_source=twitter"),
    ]
    result = dedup.deduplicate(articles)
    assert len(result) == 1


def test_dedup_existing_urls():
    dedup = Deduplicator()
    dedup.load_existing({"https://example.com/old"}, [])
    articles = [
        make_article("Old article", "https://example.com/old"),
        make_article("New article", "https://example.com/new"),
    ]
    result = dedup.deduplicate(articles)
    assert len(result) == 1
    assert result[0].title == "New article"


def test_dedup_simhash_similar():
    dedup = Deduplicator(simhash_threshold=3)
    articles = [
        make_article("StarRocks best practices guide", "https://a.com/1", "StarRocks best practices guide for data engineers"),
        make_article("StarRocks best practices guide", "https://b.com/2", "StarRocks best practices guide for data engineers"),
    ]
    result = dedup.deduplicate(articles)
    assert len(result) == 1
