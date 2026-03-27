"""Research module — web search (primary) + RSS (fallback) with unified output."""

from __future__ import annotations

import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import UTC

import feedparser

from agent.core.config import get_sources_config
from agent.core.logging import get_logger
from agent.sources.normalizer import normalize
from agent.sources.protocol import ContentSource
from agent.sources.rag_source import search_rag
from agent.sources.web_search import build_queries, search_web

logger = get_logger(__name__)

FEED_TIMEOUT = 8
MAX_WORKERS = 6


# ---------------------------------------------------------------------------
# Legacy ArticleResult — kept for backwards compatibility with generators
# ---------------------------------------------------------------------------
@dataclass
class ArticleResult:
    title: str
    url: str
    summary: str
    source: str
    published_ts: float = field(default_factory=time.time)


def _content_source_to_article(cs: ContentSource) -> ArticleResult:
    return ArticleResult(
        title=cs.title,
        url=cs.url or "",
        summary=cs.summary,
        source=cs.source_type if cs.source_type != "web_search" else cs.metadata.get("query", "Web"),
        published_ts=cs.freshness.timestamp(),
    )


# ---------------------------------------------------------------------------
# RSS (fallback)
# ---------------------------------------------------------------------------
def _fetch_one_feed(name: str, url: str, per_feed: int) -> list[ContentSource]:
    from datetime import datetime

    try:
        with urllib.request.urlopen(url, timeout=FEED_TIMEOUT) as resp:
            content = resp.read()
        parsed = feedparser.parse(content)
    except Exception as exc:
        logger.warning("rss_feed_fetch_failed", feed=name, error=str(exc))
        return []

    results = []
    for entry in parsed.entries[:per_feed]:
        pub_ts: float = time.mktime(entry.published_parsed) if getattr(entry, "published_parsed", None) else time.time()
        summary = (entry.get("summary", "") or entry.get("description", ""))[:500]
        results.append(
            ContentSource(
                source_type="rss",
                title=entry.get("title", "(no title)"),
                summary=summary,
                url=entry.get("link", ""),
                relevance_score=0.6,
                freshness=datetime.fromtimestamp(pub_ts, tz=UTC),
                metadata={"feed": name},
            )
        )
    return results


def _fetch_rss_sources(per_feed: int = 2) -> list[ContentSource]:
    sources = get_sources_config()
    feeds: list[dict] = sources.get("rss_feeds", [])
    all_results: list[ContentSource] = []

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(_fetch_one_feed, f.get("name", "?"), f.get("url", ""), per_feed): f
            for f in feeds
            if f.get("url")
        }
        for future in as_completed(futures, timeout=FEED_TIMEOUT + 2):
            try:
                all_results.extend(future.result())
            except Exception as exc:
                logger.warning("rss_future_error", error=str(exc))

    return all_results


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------
def fetch_rss_articles(max_total: int = 5, per_feed: int = 2) -> list[ArticleResult]:
    """Backwards-compatible wrapper — used by generators and slack_bot."""
    return fetch_articles(topic=None, max_total=max_total)


def fetch_articles(topic: str | None = None, max_total: int = 5) -> list[ArticleResult]:
    """Fetch research articles using web search (primary) + RSS (fallback).

    Args:
        topic: User-specified focus topic, or None for general AI news.
        max_total: Max articles to return.

    Returns:
        List of ArticleResult sorted by relevance + freshness.
    """
    all_sources: list[ContentSource] = []

    # --- Primary: web search ---
    queries = build_queries(topic)
    web_results = search_web(queries, max_results_per_query=3)
    all_sources.extend(web_results)
    logger.info("web_search_results", count=len(web_results), topic=topic or "general")

    # --- RAG: knowledge-base retrieval (when topic is given) ---
    if topic:
        rag_results = search_rag(topic, top_k=3)
        all_sources.extend(rag_results)
        logger.info("rag_results", count=len(rag_results), topic=topic)

    # --- Fallback: RSS (always run, supplements web search) ---
    rss_results = _fetch_rss_sources(per_feed=2)
    all_sources.extend(rss_results)
    logger.info("rss_results", count=len(rss_results))

    # --- Normalize: deduplicate + rank ---
    top_sources = normalize(all_sources, top_k=max_total)
    logger.info("research_complete", total_raw=len(all_sources), returning=len(top_sources))

    return [_content_source_to_article(s) for s in top_sources]
