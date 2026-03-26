"""Research module: fetch top AI news from configured RSS feeds."""

from __future__ import annotations

import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field

import feedparser

from agent.core.config import get_sources_config
from agent.core.logging import get_logger

logger = get_logger(__name__)

FEED_TIMEOUT = 8   # seconds per feed request
MAX_WORKERS = 6    # concurrent feed fetches


@dataclass
class ArticleResult:
    title: str
    url: str
    summary: str
    source: str
    published_ts: float = field(default_factory=time.time)


def _fetch_one_feed(name: str, url: str, per_feed: int) -> list[ArticleResult]:
    """Fetch a single RSS feed with a hard timeout. Returns [] on any error."""
    try:
        with urllib.request.urlopen(url, timeout=FEED_TIMEOUT) as resp:
            content = resp.read()
        parsed = feedparser.parse(content)
    except Exception as exc:
        logger.warning("rss_feed_fetch_failed", feed=name, error=str(exc))
        return []

    articles: list[ArticleResult] = []
    for entry in parsed.entries[:per_feed]:
        pub_ts: float = (
            time.mktime(entry.published_parsed)
            if getattr(entry, "published_parsed", None)
            else time.time()
        )
        summary: str = (entry.get("summary", "") or entry.get("description", ""))[:500]
        articles.append(
            ArticleResult(
                title=entry.get("title", "(no title)"),
                url=entry.get("link", ""),
                summary=summary,
                source=name,
                published_ts=pub_ts,
            )
        )
    return articles


def fetch_rss_articles(max_total: int = 5, per_feed: int = 2) -> list[ArticleResult]:
    """Fetch top articles from all configured RSS feeds concurrently with timeouts."""
    sources = get_sources_config()
    feeds: list[dict] = sources.get("rss_feeds", [])
    all_articles: list[ArticleResult] = []

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(_fetch_one_feed, f.get("name", "?"), f.get("url", ""), per_feed): f
            for f in feeds if f.get("url")
        }
        for future in as_completed(futures, timeout=FEED_TIMEOUT + 2):
            try:
                all_articles.extend(future.result())
            except Exception as exc:
                logger.warning("rss_future_error", error=str(exc))

    all_articles.sort(key=lambda a: a.published_ts, reverse=True)
    result = all_articles[:max_total]
    logger.info("rss_fetch_complete", total=len(all_articles), returning=len(result))
    return result
