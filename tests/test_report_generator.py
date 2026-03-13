"""Tests for report generator (Markdown + HTML)."""

import json
import os
import tempfile

from src.collectors.base import CollectedArticle
from src.report.generator import ReportGenerator


def _make_articles():
    return [
        CollectedArticle(
            title="StarRocks 3.4 Guide",
            url="https://example.com/sr34",
            source="techblog",
            source_type="article",
            content_snippet="Major performance improvements.",
            relevance_score=0.8,
            category="StarRocks",
            relevance_to_team="high",
            summary_ko="StarRocks 3.4 성능 가이드",
            key_takeaways=["성능 2배", "Iceberg 지원"],
        ),
        CollectedArticle(
            title="Spark Iceberg Tutorial",
            url="https://example.com/spark-ice",
            source="github",
            source_type="trending",
            content_snippet="Spark + Iceberg optimization.",
            relevance_score=0.6,
            category="Spark",
            metadata={"stars": 42},
        ),
    ]


def test_generates_markdown_file():
    with tempfile.TemporaryDirectory() as tmpdir:
        gen = ReportGenerator(output_dir=tmpdir)
        path = gen.generate(_make_articles(), "2026-03-12", {
            "total_raw": 10, "new_count": 2, "dedup_count": 8, "saved_count": 2,
        })
        assert path.endswith("daily-report.md")
        assert os.path.exists(path)
        content = open(path).read()
        assert "StarRocks 3.4 Guide" in content
        assert "2026-03-12" in content


def test_generates_html_file():
    with tempfile.TemporaryDirectory() as tmpdir:
        gen = ReportGenerator(output_dir=tmpdir)
        gen.generate(_make_articles(), "2026-03-12", {
            "total_raw": 10, "new_count": 2, "dedup_count": 8, "saved_count": 2,
        })
        html_path = os.path.join(tmpdir, "2026-03-12", "daily-report.html")
        assert os.path.exists(html_path)
        content = open(html_path).read()
        assert "<!DOCTYPE html>" in content
        assert "StarRocks 3.4 Guide" in content
        assert "StarRocks 3.4 성능 가이드" in content


def test_generates_raw_json():
    with tempfile.TemporaryDirectory() as tmpdir:
        gen = ReportGenerator(output_dir=tmpdir)
        gen.generate(_make_articles(), "2026-03-12", {
            "total_raw": 10, "new_count": 2, "dedup_count": 8, "saved_count": 2,
        })
        raw_path = os.path.join(tmpdir, "2026-03-12", "raw-articles.json")
        data = json.loads(open(raw_path).read())
        assert len(data) == 2
        assert data[0]["title"] == "StarRocks 3.4 Guide"


def test_generates_stats_json():
    with tempfile.TemporaryDirectory() as tmpdir:
        gen = ReportGenerator(output_dir=tmpdir)
        gen.generate(_make_articles(), "2026-03-12", {
            "total_raw": 10, "new_count": 2, "dedup_count": 8, "saved_count": 2,
        })
        stats_path = os.path.join(tmpdir, "2026-03-12", "summary-stats.json")
        data = json.loads(open(stats_path).read())
        assert data["total_raw"] == 10
        assert data["total_articles"] == 2
        assert "source_stats" in data


def test_empty_articles():
    with tempfile.TemporaryDirectory() as tmpdir:
        gen = ReportGenerator(output_dir=tmpdir)
        path = gen.generate([], "2026-03-12", {
            "total_raw": 0, "new_count": 0, "dedup_count": 0, "saved_count": 0,
        })
        assert os.path.exists(path)


def test_html_escapes_special_chars():
    articles = [
        CollectedArticle(
            title='Test <script>alert("xss")</script>',
            url="https://example.com/xss",
            source="test",
            source_type="article",
            content_snippet='<b>bold</b> & "quotes"',
            relevance_score=0.5,
            category="Other",
            relevance_to_team="high",
        ),
    ]
    with tempfile.TemporaryDirectory() as tmpdir:
        gen = ReportGenerator(output_dir=tmpdir)
        gen.generate(articles, "2026-03-12", {
            "total_raw": 1, "new_count": 1, "dedup_count": 0, "saved_count": 1,
        })
        html_path = os.path.join(tmpdir, "2026-03-12", "daily-report.html")
        content = open(html_path).read()
        # HTML template uses |e filter, so script tags should be escaped
        assert "<script>" not in content
        assert "&lt;script&gt;" in content
