"""Multi-stage deduplication for collected articles."""

import hashlib

import structlog

from ..collectors.base import CollectedArticle
from .normalizer import normalize_url, normalize_text

logger = structlog.get_logger()


def _simhash_tokens(text: str, hash_bits: int = 64) -> int:
    """Compute a simple SimHash from text tokens."""
    tokens = normalize_text(text).split()
    if not tokens:
        return 0

    v = [0] * hash_bits
    for token in tokens:
        h = int(hashlib.md5(token.encode()).hexdigest(), 16)
        for i in range(hash_bits):
            if h & (1 << i):
                v[i] += 1
            else:
                v[i] -= 1

    fingerprint = 0
    for i in range(hash_bits):
        if v[i] > 0:
            fingerprint |= 1 << i
    return fingerprint


def _hamming_distance(a: int, b: int) -> int:
    """Compute hamming distance between two integers."""
    return bin(a ^ b).count("1")


class Deduplicator:
    """Three-stage deduplication: URL match, SimHash, optional semantic."""

    def __init__(self, simhash_threshold: int = 3):
        self.simhash_threshold = simhash_threshold
        self.seen_urls: set[str] = set()
        self.seen_simhashes: list[tuple[int, str]] = []  # (hash, url)

    def load_existing(self, existing_urls: set[str], existing_hashes: list[tuple[int, str]]):
        """Load previously seen URLs and hashes from database."""
        self.seen_urls = existing_urls
        self.seen_simhashes = existing_hashes

    def deduplicate(self, articles: list[CollectedArticle]) -> list[CollectedArticle]:
        """Run multi-stage deduplication, returning only new articles."""
        unique = []
        stats = {"url_dupes": 0, "simhash_dupes": 0}

        for article in articles:
            # Stage 1: URL exact match
            norm_url = normalize_url(article.url)
            if norm_url in self.seen_urls:
                stats["url_dupes"] += 1
                continue

            # Stage 2: SimHash content similarity
            text = f"{article.title} {article.content_snippet}"
            article_hash = _simhash_tokens(text)

            is_dup = False
            for existing_hash, _ in self.seen_simhashes:
                if _hamming_distance(article_hash, existing_hash) <= self.simhash_threshold:
                    is_dup = True
                    stats["simhash_dupes"] += 1
                    break

            if is_dup:
                continue

            # Not a duplicate - add to seen sets
            self.seen_urls.add(norm_url)
            self.seen_simhashes.append((article_hash, norm_url))
            article.metadata["url_normalized"] = norm_url
            article.metadata["content_simhash"] = str(article_hash)
            unique.append(article)

        logger.info(
            "deduplication_complete",
            total=len(articles),
            unique=len(unique),
            url_dupes=stats["url_dupes"],
            simhash_dupes=stats["simhash_dupes"],
        )
        return unique
