"""Markdown and HTML report generator."""

import json
from collections import Counter
from datetime import datetime
from pathlib import Path

import structlog
from jinja2 import Environment, FileSystemLoader

from ..collectors.base import CollectedArticle

logger = structlog.get_logger()


class ReportGenerator:
    def __init__(self, output_dir: str, template_dir: str | None = None):
        self.output_dir = Path(output_dir)
        self.template_dir = template_dir or str(Path(__file__).parent / "templates")
        self.env = Environment(loader=FileSystemLoader(self.template_dir))

    def generate(
        self,
        articles: list[CollectedArticle],
        report_date: str,
        stats: dict,
    ) -> str:
        """Generate daily report in Markdown format."""
        date_dir = self.output_dir / report_date
        date_dir.mkdir(parents=True, exist_ok=True)

        # Categorize articles
        categorized = self._categorize(articles)
        highlights = self._pick_highlights(articles, max_count=5)
        source_stats = self._source_stats(articles)
        category_stats = self._category_stats(articles)

        # Build report content
        report = self._render_markdown(
            report_date=report_date,
            highlights=highlights,
            categorized=categorized,
            source_stats=source_stats,
            category_stats=category_stats,
            stats=stats,
            articles=articles,
        )

        # Write files
        report_path = date_dir / "daily-report.md"
        report_path.write_text(report, encoding="utf-8")

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

    def _render_markdown(self, **kwargs) -> str:
        report_date = kwargs["report_date"]
        highlights = kwargs["highlights"]
        categorized = kwargs["categorized"]
        source_stats = kwargs["source_stats"]
        category_stats = kwargs["category_stats"]
        stats = kwargs["stats"]
        articles = kwargs["articles"]

        lines = [
            f"# Daily Data Platform Practices Report",
            f"**{report_date}** | 수집 건수: {len(articles)}건 | "
            f"신규: {stats.get('new_count', len(articles))}건",
            "",
            "---",
            "",
            "## Today's Highlights",
            "",
        ]

        for i, a in enumerate(highlights, 1):
            lines.append(f"### {i}. [{a.title}]({a.url})")
            if a.summary_ko:
                lines.append(f"> {a.summary_ko}")
            elif a.content_snippet:
                lines.append(f"> {a.content_snippet[:200]}")
            if a.key_takeaways:
                for kt in a.key_takeaways:
                    lines.append(f"- {kt}")
            lines.append("")

        # Category sections
        category_labels = {
            "StarRocks": "StarRocks Best Practices",
            "Spark": "Spark & Lakehouse",
            "Iceberg": "Iceberg / Table Format",
            "Lakehouse": "Data Lakehouse",
            "AI-Data": "AI-Ready Data",
            "Infrastructure": "Infrastructure",
        }

        for cat, label in category_labels.items():
            cat_articles = categorized.get(cat, [])
            if not cat_articles:
                continue
            lines.append(f"## {label}")
            lines.append("")
            for a in cat_articles[:10]:
                lines.append(f"- [{a.title}]({a.url}) ({a.source})")
                if a.summary_ko:
                    lines.append(f"  > {a.summary_ko}")
                lines.append("")

        # GitHub trending section
        gh_articles = [a for a in articles if a.source == "github" and a.source_type == "trending"]
        if gh_articles:
            lines.append("## GitHub Trending")
            lines.append("")
            lines.append("| Repo | Stars | 설명 |")
            lines.append("|------|-------|------|")
            for a in gh_articles[:10]:
                stars = a.metadata.get("stars", "?")
                lines.append(f"| [{a.title}]({a.url}) | {stars} | {a.content_snippet[:80]} |")
            lines.append("")

        # Statistics
        lines.append("## 통계")
        lines.append("")
        lines.append(f"- 전체 수집: {len(articles)}건")
        lines.append(f"- 중복 제거: {stats.get('dedup_count', 0)}건")

        source_str = ", ".join(f"{k}({v})" for k, v in source_stats.items())
        lines.append(f"- 소스별: {source_str}")

        cat_str = ", ".join(f"{k}({v})" for k, v in category_stats.items())
        lines.append(f"- 카테고리별: {cat_str}")
        lines.append("")
        lines.append("---")
        lines.append("*Generated by Daily Practices Collector v1.0*")

        return "\n".join(lines)
