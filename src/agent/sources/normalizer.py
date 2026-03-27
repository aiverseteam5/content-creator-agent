"""Normalizer — combine, deduplicate, and rank ContentSource results from all adapters."""

from __future__ import annotations

from datetime import datetime, timezone

from agent.sources.protocol import ContentSource


def _freshness_score(freshness: datetime) -> float:
    """Score 0.0–1.0 based on age: 1.0 = just published, 0.0 = 7+ days old."""
    now = datetime.now(timezone.utc)
    if freshness.tzinfo is None:
        freshness = freshness.replace(tzinfo=timezone.utc)
    age_hours = (now - freshness).total_seconds() / 3600
    return max(0.0, 1.0 - age_hours / 168)   # 168 hours = 7 days


def _combined_score(source: ContentSource) -> float:
    """Weighted combination of relevance and freshness."""
    return 0.7 * source.relevance_score + 0.3 * _freshness_score(source.freshness)


def _dedup_key(source: ContentSource) -> str:
    """Return a key for deduplication — prefer URL, fall back to title."""
    return (source.url or source.title).lower().strip()


def normalize(sources: list[ContentSource], top_k: int = 5) -> list[ContentSource]:
    """Deduplicate and return the top_k highest-scoring sources.

    Web search results are boosted slightly over RSS to prefer fresher content.

    Args:
        sources: Combined results from all adapters.
        top_k: How many to return.

    Returns:
        Sorted, deduplicated list of top ContentSource objects.
    """
    # Boost web search sources
    boosted = []
    for s in sources:
        if s.source_type == "web_search":
            boosted.append(ContentSource(
                **{**s.__dict__, "relevance_score": min(1.0, s.relevance_score * 1.2)}
            ))
        else:
            boosted.append(s)

    # Deduplicate by URL/title
    seen: set[str] = set()
    unique: list[ContentSource] = []
    for s in boosted:
        key = _dedup_key(s)
        if key not in seen:
            seen.add(key)
            unique.append(s)

    # Sort by combined score descending
    unique.sort(key=_combined_score, reverse=True)
    return unique[:top_k]
