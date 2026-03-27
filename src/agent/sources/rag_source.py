"""RAG source — retrieves relevant knowledge-base chunks as ContentSources."""

from __future__ import annotations

from datetime import datetime, timezone

from agent.core.logging import get_logger
from agent.sources.protocol import ContentSource

logger = get_logger(__name__)


def search_rag(topic: str, top_k: int = 5) -> list[ContentSource]:
    """
    Query the vector knowledge base for chunks relevant to *topic*.
    Returns an empty list when the knowledge base is empty or unavailable.
    """
    try:
        from agent.rag.retriever import retrieve_chunks

        chunks = retrieve_chunks(topic, top_k=top_k)
    except Exception as exc:
        logger.warning("rag_search_failed", topic=topic, error=str(exc))
        return []

    if not chunks:
        return []

    sources: list[ContentSource] = []
    for chunk in chunks:
        sources.append(
            ContentSource(
                source_type="rag",
                title=chunk.doc_title,
                summary=chunk.content[:500],
                url=chunk.source_url,
                relevance_score=chunk.similarity,
                freshness=datetime.now(timezone.utc),  # treat local KB as always fresh
                full_text=chunk.content,
                metadata={
                    "doc_id": str(chunk.doc_id),
                    "chunk_index": chunk.chunk_index,
                },
            )
        )

    logger.info("rag_search_complete", topic=topic, results=len(sources))
    return sources
