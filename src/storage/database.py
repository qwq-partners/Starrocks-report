"""SQLite database for article storage and deduplication."""

import json
from datetime import datetime
from pathlib import Path

import aiosqlite
import structlog

from ..collectors.base import CollectedArticle

logger = structlog.get_logger()

SCHEMA = """
CREATE TABLE IF NOT EXISTS articles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    url_normalized TEXT UNIQUE NOT NULL,
    source TEXT NOT NULL,
    source_type TEXT NOT NULL,
    content_snippet TEXT,
    full_content TEXT,
    author TEXT,
    language TEXT DEFAULT 'en',
    published_at TIMESTAMP,
    collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    relevance_score REAL DEFAULT 0.0,
    content_simhash TEXT,
    summary_ko TEXT,
    summary_en TEXT,
    category TEXT,
    relevance_to_team TEXT,
    key_takeaways TEXT,
    difficulty TEXT,
    metadata TEXT
);

CREATE TABLE IF NOT EXISTS article_tags (
    article_id INTEGER REFERENCES articles(id),
    tag TEXT NOT NULL,
    PRIMARY KEY (article_id, tag)
);

CREATE TABLE IF NOT EXISTS daily_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_date DATE UNIQUE NOT NULL,
    total_collected INTEGER DEFAULT 0,
    new_articles INTEGER DEFAULT 0,
    dedup_removed INTEGER DEFAULT 0,
    report_path TEXT,
    generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS collection_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    collector_name TEXT NOT NULL,
    started_at TIMESTAMP,
    finished_at TIMESTAMP,
    items_collected INTEGER DEFAULT 0,
    items_new INTEGER DEFAULT 0,
    status TEXT DEFAULT 'pending',
    error_message TEXT
);

CREATE INDEX IF NOT EXISTS idx_articles_date ON articles(collected_at);
CREATE INDEX IF NOT EXISTS idx_articles_category ON articles(category);
CREATE INDEX IF NOT EXISTS idx_articles_source ON articles(source);
CREATE INDEX IF NOT EXISTS idx_articles_simhash ON articles(content_simhash);
"""


class Database:
    def __init__(self, db_path: str):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    async def initialize(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.executescript(SCHEMA)
            await db.commit()
        logger.info("database_initialized", path=self.db_path)

    async def get_existing_urls(self) -> set[str]:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT url_normalized FROM articles")
            rows = await cursor.fetchall()
            return {row[0] for row in rows}

    async def get_existing_simhashes(self) -> list[tuple[int, str]]:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT content_simhash, url_normalized FROM articles WHERE content_simhash IS NOT NULL"
            )
            rows = await cursor.fetchall()
            return [(int(row[0]), row[1]) for row in rows if row[0]]

    async def save_articles(self, articles: list[CollectedArticle]) -> int:
        saved = 0
        async with aiosqlite.connect(self.db_path) as db:
            for article in articles:
                try:
                    await db.execute(
                        """INSERT OR IGNORE INTO articles
                        (title, url, url_normalized, source, source_type,
                         content_snippet, full_content, author, language,
                         published_at, relevance_score, content_simhash,
                         summary_ko, summary_en, category, relevance_to_team,
                         key_takeaways, difficulty, metadata)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            article.title,
                            article.url,
                            article.metadata.get("url_normalized", article.url),
                            article.source,
                            article.source_type,
                            article.content_snippet,
                            article.full_content,
                            article.author,
                            article.language,
                            article.published_at.isoformat() if article.published_at else None,
                            article.relevance_score,
                            article.metadata.get("content_simhash"),
                            article.summary_ko,
                            article.summary_en,
                            article.category,
                            article.relevance_to_team,
                            json.dumps(article.key_takeaways, ensure_ascii=False),
                            article.difficulty,
                            json.dumps(article.metadata, ensure_ascii=False, default=str),
                        ),
                    )
                    saved += 1

                    # Save tags
                    cursor = await db.execute(
                        "SELECT id FROM articles WHERE url_normalized = ?",
                        (article.metadata.get("url_normalized", article.url),),
                    )
                    row = await cursor.fetchone()
                    if row:
                        for tag in article.tags:
                            await db.execute(
                                "INSERT OR IGNORE INTO article_tags (article_id, tag) VALUES (?, ?)",
                                (row[0], tag),
                            )
                except Exception as e:
                    logger.error("save_article_error", error=str(e), url=article.url)

            await db.commit()

        logger.info("articles_saved", count=saved)
        return saved

    async def save_report_record(
        self, report_date: str, total: int, new: int, dedup: int, path: str
    ):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """INSERT OR REPLACE INTO daily_reports
                (report_date, total_collected, new_articles, dedup_removed, report_path)
                VALUES (?, ?, ?, ?, ?)""",
                (report_date, total, new, dedup, path),
            )
            await db.commit()

    async def cleanup_old_articles(self, keep_days: int = 90):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "DELETE FROM articles WHERE collected_at < datetime('now', ?)",
                (f"-{keep_days} days",),
            )
            await db.commit()
        logger.info("old_articles_cleaned", keep_days=keep_days)
