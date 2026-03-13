"""Tests for database storage."""

import asyncio
import tempfile
import os

import pytest

from src.collectors.base import CollectedArticle
from src.storage.database import Database


@pytest.fixture
def db_path():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield os.path.join(tmpdir, "test.db")


@pytest.fixture
def db(db_path):
    return Database(db_path)


async def test_initialize_creates_tables(db):
    await db.initialize()
    urls = await db.get_existing_urls()
    assert urls == set()


async def test_save_and_retrieve_articles(db):
    await db.initialize()
    articles = [
        CollectedArticle(
            title="Test Article",
            url="https://example.com/test",
            source="test",
            source_type="article",
            content_snippet="Test content",
            tags=["tag1", "tag2"],
            metadata={"url_normalized": "https://example.com/test", "content_simhash": "12345"},
        ),
    ]
    saved = await db.save_articles(articles)
    assert saved == 1

    urls = await db.get_existing_urls()
    assert "https://example.com/test" in urls


async def test_duplicate_url_not_saved_twice(db):
    await db.initialize()
    articles = [
        CollectedArticle(
            title="Test",
            url="https://example.com/dup",
            source="test",
            source_type="article",
            metadata={"url_normalized": "https://example.com/dup"},
        ),
    ]
    await db.save_articles(articles)
    saved = await db.save_articles(articles)  # second save
    assert saved == 1  # INSERT OR IGNORE, still returns 1 but no actual insert

    urls = await db.get_existing_urls()
    assert len(urls) == 1


async def test_get_existing_simhashes(db):
    await db.initialize()
    articles = [
        CollectedArticle(
            title="Test",
            url="https://example.com/hash",
            source="test",
            source_type="article",
            metadata={"url_normalized": "https://example.com/hash", "content_simhash": "9999"},
        ),
    ]
    await db.save_articles(articles)
    hashes = await db.get_existing_simhashes()
    assert len(hashes) == 1
    assert hashes[0][0] == 9999


async def test_log_collection(db):
    await db.initialize()
    await db.log_collection("github", 10, 5, "success")
    await db.log_collection("hackernews", 0, 0, "failed", "timeout error")
    # No assertion needed beyond no exception


async def test_save_report_record(db):
    await db.initialize()
    await db.save_report_record("2026-03-12", 50, 10, 40, "/reports/2026-03-12/daily-report.md")
    # No assertion needed beyond no exception


async def test_cleanup_old_articles(db):
    await db.initialize()
    await db.cleanup_old_articles(keep_days=0)  # delete everything
    urls = await db.get_existing_urls()
    assert urls == set()
