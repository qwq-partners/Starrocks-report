"""Relevance scoring with weighted keyword matching."""


def compute_relevance(
    title: str,
    content: str,
    primary_keywords: list[str],
    secondary_keywords: list[str],
    tertiary_keywords: list[str],
    negative_keywords: list[str],
) -> float:
    """Compute weighted relevance score for an article."""
    text = f"{title} {content}".lower()

    # Negative keyword check
    for neg in negative_keywords:
        if neg.lower() in text:
            return 0.0

    score = 0.0

    # Primary keywords: highest weight
    for kw in primary_keywords:
        if kw.lower() in text:
            score += 0.25

    # Secondary keywords
    for kw in secondary_keywords:
        if kw.lower() in text:
            score += 0.15

    # Tertiary keywords
    for kw in tertiary_keywords:
        if kw.lower() in text:
            score += 0.10

    return min(score, 1.0)
