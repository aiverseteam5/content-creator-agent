"""Web search adapter using Tavily — primary research source."""

from __future__ import annotations

from datetime import datetime, timezone

from agent.core.config import get_settings
from agent.core.logging import get_logger
from agent.sources.protocol import ContentSource

logger = get_logger(__name__)


def search_web(queries: list[str], max_results_per_query: int = 5) -> list[ContentSource]:
    """Search the web for each query and return unified ContentSource results.

    Args:
        queries: List of search queries (e.g. ["NVIDIA GTC 2025 highlights"]).
        max_results_per_query: Max results to fetch per query.

    Returns:
        Flat list of ContentSource objects across all queries.
    """
    settings = get_settings()

    if not settings.tavily_api_key:
        logger.warning("web_search_skipped", reason="TAVILY_API_KEY not set")
        return []

    try:
        from tavily import TavilyClient
    except ImportError:
        logger.error("tavily_not_installed", hint="pip install tavily-python")
        return []

    client = TavilyClient(api_key=settings.tavily_api_key)
    results: list[ContentSource] = []

    for query in queries:
        try:
            response = client.search(
                query=query,
                max_results=max_results_per_query,
                search_depth="advanced",
                include_raw_content=False,
            )
            for r in response.get("results", []):
                results.append(
                    ContentSource(
                        source_type="web_search",
                        title=r.get("title", "(no title)"),
                        summary=r.get("content", "")[:500],
                        full_text=r.get("raw_content"),
                        url=r.get("url"),
                        relevance_score=float(r.get("score", 0.5)),
                        freshness=datetime.now(timezone.utc),
                        metadata={"query": query, "tavily_score": r.get("score")},
                    )
                )
            logger.info("web_search_complete", query=query, hits=len(response.get("results", [])))
        except Exception as exc:
            logger.warning("web_search_failed", query=query, error=str(exc))

    return results


def build_queries(topic: str | None) -> list[str]:
    """Build search queries from a topic or return generic AI trend queries."""
    if topic:
        return [
            topic,
            f"{topic} latest news 2025",
            f"{topic} key highlights",
        ]
    return [
        "AI technology news today",
        "large language models latest developments",
        "AI startup funding 2025",
    ]
