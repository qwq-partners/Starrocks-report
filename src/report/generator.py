"""Markdown and HTML report generator."""

import json
from collections import Counter
from pathlib import Path

import structlog
from jinja2 import Environment, FileSystemLoader

from ..collectors.base import CollectedArticle

logger = structlog.get_logger()

CATEGORY_LABELS = {
    "StarRocks": "StarRocks Best Practices",
    "Spark": "Spark & Lakehouse",
    "Iceberg": "Iceberg / Table Format",
    "Lakehouse": "Data Lakehouse",
    "AI-Data": "AI-Ready Data",
    "Infrastructure": "Infrastructure",
}


class ReportGenerator:
    def __init__(self, output_dir: str, template_dir: str | None = None):
        self.output_dir = Path(output_dir)
        self.template_dir = template_dir or str(Path(__file__).parent / "templates")
        self.env = Environment(
            loader=FileSystemLoader(self.template_dir),
            autoescape=False,  # Markdown template; HTML template uses |e filter
        )

    def generate(
        self,
        articles: list[CollectedArticle],
        report_date: str,
        stats: dict,
    ) -> str:
        """Generate daily report in Markdown format."""
        date_dir = self.output_dir / report_date
        date_dir.mkdir(parents=True, exist_ok=True)

        categorized = self._categorize(articles)
        highlights = self._pick_highlights(articles, max_count=5)
        source_stats = self._source_stats(articles)
        category_stats = self._category_stats(articles)
        gh_trending = [a for a in articles if a.source == "github" and a.source_type == "trending"]

        source_str = ", ".join(f"{k}({v})" for k, v in source_stats.items())
        cat_str = ", ".join(f"{k}({v})" for k, v in category_stats.items())

        # Render using Jinja2 template
        template = self.env.get_template("daily_report.md.j2")
        report = template.render(
            report_date=report_date,
            articles=articles,
            highlights=highlights,
            categorized=categorized,
            category_labels=CATEGORY_LABELS,
            gh_trending=gh_trending,
            source_stats_str=source_str,
            category_stats_str=cat_str,
            stats=stats,
        )

        # Write Markdown
        report_path = date_dir / "daily-report.md"
        report_path.write_text(report, encoding="utf-8")

        # Write HTML
        html_template = self.env.get_template("daily_report.html.j2")
        html_report = html_template.render(
            report_date=report_date,
            articles=articles,
            highlights=highlights,
            categorized=categorized,
            category_labels=CATEGORY_LABELS,
            gh_trending=gh_trending,
            stats=stats,
        )
        html_path = date_dir / "daily-report.html"
        html_path.write_text(html_report, encoding="utf-8")

        raw_path = date_dir / "raw-articles.json"
        raw_data = [
            {
                "title": a.title,
                "url": a.url,
                "source": a.source,
                "category": a.category,
                "relevance_score": a.relevance_score,
                "summary_ko": a.summary_ko,
                "published_at": a.published_at.isoformat() if a.published_at else None,
            }
            for a in articles
        ]
        raw_path.write_text(json.dumps(raw_data, ensure_ascii=False, indent=2), encoding="utf-8")

        stats_path = date_dir / "summary-stats.json"
        stats_data = {
            "date": report_date,
            "total_articles": len(articles),
            "source_stats": source_stats,
            "category_stats": category_stats,
            **stats,
        }
        stats_path.write_text(
            json.dumps(stats_data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        logger.info("report_generated", path=str(report_path), articles=len(articles))
        return str(report_path)

    def _categorize(self, articles: list[CollectedArticle]) -> dict[str, list[CollectedArticle]]:
        cats: dict[str, list[CollectedArticle]] = {}
        for a in articles:
            cat = a.category or "Other"
            cats.setdefault(cat, []).append(a)
        return cats

    def _pick_highlights(
        self, articles: list[CollectedArticle], max_count: int = 5
    ) -> list[CollectedArticle]:
        high_relevance = [a for a in articles if a.relevance_to_team == "high"]
        if not high_relevance:
            high_relevance = sorted(articles, key=lambda a: a.relevance_score, reverse=True)
        return high_relevance[:max_count]

    def _source_stats(self, articles: list[CollectedArticle]) -> dict[str, int]:
        return dict(Counter(a.source for a in articles))

    def _category_stats(self, articles: list[CollectedArticle]) -> dict[str, int]:
        return dict(Counter(a.category or "Other" for a in articles))
