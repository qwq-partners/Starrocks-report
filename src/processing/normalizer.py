"""URL and text normalization for deduplication."""

import re
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode


def normalize_url(url: str) -> str:
    """Normalize a URL for deduplication comparison.

    - Lowercases scheme and host
    - Removes tracking parameters (utm_*, fbclid, etc.)
    - Removes trailing slashes
    - Removes fragments
    """
    parsed = urlparse(url.strip())

    # Lowercase scheme and host
    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()

    # Remove www. prefix
    if netloc.startswith("www."):
        netloc = netloc[4:]

    # Remove tracking query parameters
    tracking_params = {"utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
                       "fbclid", "gclid", "ref", "source"}
    if parsed.query:
        params = parse_qs(parsed.query)
        filtered = {k: v for k, v in params.items() if k.lower() not in tracking_params}
        query = urlencode(filtered, doseq=True)
    else:
        query = ""

    # Remove trailing slash from path
    path = parsed.path.rstrip("/") or "/"

    # Remove fragment
    return urlunparse((scheme, netloc, path, parsed.params, query, ""))


def normalize_text(text: str) -> str:
    """Normalize text for content comparison."""
    text = text.lower()
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[^\w\s]", "", text)
    return text.strip()
