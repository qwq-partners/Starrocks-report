"""Main entry point for the Daily Practices Collector."""

import asyncio
import os
from datetime import datetime
from pathlib import Path

import click
import structlog
from dotenv import load_dotenv

# Load .env from project root
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from .config import Config
from .collectors import (
    GitHubCollector, HackerNewsCollector, GeekNewsCollector, RSSCollector,
    RedditCollector, TechBlogCollector,
)
from .processing.deduplicator import Deduplicator
from .processing.enricher import Enricher
from .report.generator import ReportGenerator
from .storage.database import Database
from .distribution.telegram_notifier import TelegramNotifier
from .utils.logger import setup_logging

logger = structlog.get_logger()


async def run_collection(config: Config, skip_enrichment: bool = False):
    """Execute the full collection pipeline."""
    setup_logging()
    report_date = datetime.now().strftime("%Y-%m-%d")
    logger.info("collection_started", date=report_date)

    # Initialize database
    db = Database(config.db_path)
    await db.initialize()

    # Build shared collector config
    collector_config = {
        **config.sources,
        "max_items_per_source": config.max_items_per_source,
        "rate_limit_delay": config.rate_limit_delay,
        "lookback_hours": config.lookback_hours,
    }
    keywords = config.all_keywords
    negative = config.negative_keywords
    keyword_groups = config.keyword_groups

    # Run collectors in parallel
    collectors = [
        GitHubCollector(keywords, negative, collector_config, keyword_groups),
        HackerNewsCollector(keywords, negative, collector_config, keyword_groups),
        GeekNewsCollector(keywords, negative, collector_config, keyword_groups),
        RSSCollector(keywords, negative, collector_config, keyword_groups),
        RedditCollector(keywords, negative, collector_config, keyword_groups),
        TechBlogCollector(keywords, negative, collector_config, keyword_groups),
    ]

    all_articles = []
    collector_stats = []
    collection_started = datetime.now().isoformat()
    results = await asyncio.gather(
        *[c.collect() for c in collectors], return_exceptions=True
    )

    total_raw = 0
    for collector, result in zip(collectors, results):
        name = collector.get_source_name()
        if isinstance(result, Exception):
            logger.error("collector_failed", collector=name, error=str(result))
            await db.log_collection(name, 0, 0, "failed", str(result), started_at=collection_started)
            continue
        count = len(result)
        total_raw += count
        all_articles.extend(result)
        collector_stats.append({"name": name, "count": count})
        await db.log_collection(name, count, 0, "success", started_at=collection_started)
        logger.info("collector_done", collector=name, count=count)

    logger.info("total_raw_collected", count=total_raw)

    # Deduplication
    dedup = Deduplicator(
        simhash_threshold=config.app["deduplication"]["simhash_threshold"]
    )
    existing_urls = await db.get_existing_urls()
    existing_hashes = await db.get_existing_simhashes()
    dedup.load_existing(existing_urls, existing_hashes)
    unique_articles = dedup.deduplicate(all_articles)

    dedup_count = total_raw - len(unique_articles)
    logger.info("after_dedup", unique=len(unique_articles), removed=dedup_count)

    # LLM Enrichment (optional)
    if not skip_enrichment and unique_articles:
        try:
            enricher = Enricher(
                model=config.llm_model,
                max_articles=config.max_articles_to_summarize,
            )
            unique_articles = await enricher.enrich_articles(unique_articles)
            logger.info("enrichment_complete")
        except Exception as e:
            logger.error("enrichment_failed", error=str(e))

    # Save to database
    saved = await db.save_articles(unique_articles)

    # Generate report
    stats = {
        "total_raw": total_raw,
        "new_count": len(unique_articles),
        "dedup_count": dedup_count,
        "saved_count": saved,
    }

    generator = ReportGenerator(output_dir=config.report_output_dir)
    report_path = generator.generate(unique_articles, report_date, stats)

    # Save report record
    await db.save_report_record(
        report_date=report_date,
        total=total_raw,
        new=len(unique_articles),
        dedup=dedup_count,
        path=report_path,
    )

    # Telegram notification
    telegram_config = config.app.get("distribution", {}).get("telegram", {})
    if telegram_config.get("enabled", True):
        notifier = TelegramNotifier()
        if notifier.is_configured:
            highlights = [
                {"title": a.title, "url": a.url, "summary": a.summary_ko or a.content_snippet[:200]}
                for a in unique_articles
                if a.relevance_to_team == "high"
            ][:5]
            if not highlights:
                highlights = [
                    {"title": a.title, "url": a.url, "summary": a.summary_ko or a.content_snippet[:200]}
                    for a in sorted(unique_articles, key=lambda x: x.relevance_score, reverse=True)
                ][:5]
            await notifier.send_report_summary(report_date, stats, highlights)
            await notifier.close()

    # Cleanup old data
    await db.cleanup_old_articles(keep_days=config.app["storage"]["keep_days"])

    logger.info(
        "collection_complete",
        date=report_date,
        total_raw=total_raw,
        unique=len(unique_articles),
        dedup_removed=dedup_count,
        report=report_path,
    )

    return report_path


@click.group()
def cli():
    """Daily Practices Collector - StarRocks/Spark BP 사례 수집기"""
    pass


@cli.command()
@click.option("--config-dir", default="config", help="Configuration directory path")
@click.option("--skip-enrichment", is_flag=True, help="Skip LLM enrichment step")
def collect(config_dir: str, skip_enrichment: bool):
    """Run the collection pipeline once."""
    config = Config(config_dir)
    report_path = asyncio.run(run_collection(config, skip_enrichment))
    click.echo(f"Report generated: {report_path}")


@cli.command()
@click.option("--config-dir", default="config", help="Configuration directory path")
def schedule(config_dir: str):
    """Run the collector on a daily schedule."""
    from apscheduler.schedulers.blocking import BlockingScheduler

    config = Config(config_dir)
    scheduler = BlockingScheduler(timezone=config.app["app"]["timezone"])

    cron_expr = config.app["schedule"]["cron"]
    parts = cron_expr.split()
    scheduler.add_job(
        lambda: asyncio.run(run_collection(config)),
        "cron",
        minute=parts[0],
        hour=parts[1],
        day=parts[2],
        month=parts[3],
        day_of_week=parts[4],
    )

    click.echo(f"Scheduler started. Cron: {cron_expr}")
    scheduler.start()


if __name__ == "__main__":
    cli()
