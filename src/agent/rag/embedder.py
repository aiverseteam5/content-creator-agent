"""Voyage AI embeddings wrapper."""

from __future__ import annotations

import time

from agent.core.config import get_settings
from agent.core.logging import get_logger

logger = get_logger(__name__)

_MODEL = "voyage-3"
_BATCH_SIZE = 16  # Voyage rate-limit-safe batch size


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a list of document strings. Returns one vector per text."""
    if not texts:
        return []
    import voyageai

    settings = get_settings()
    client = voyageai.Client(api_key=settings.voyage_api_key)

    all_embeddings: list[list[float]] = []
    for i in range(0, len(texts), _BATCH_SIZE):
        batch = texts[i : i + _BATCH_SIZE]
        try:
            result = client.embed(batch, model=_MODEL, input_type="document")
            all_embeddings.extend(result.embeddings)
        except Exception as exc:
            logger.error("embed_texts_error", batch_start=i, error=str(exc))
            raise
        if i + _BATCH_SIZE < len(texts):
            time.sleep(0.5)  # be polite to Voyage rate limits

    logger.info("embed_texts_complete", count=len(all_embeddings), model=_MODEL)
    return all_embeddings


def embed_query(query: str) -> list[float]:
    """Embed a single query string for retrieval."""
    import voyageai

    settings = get_settings()
    client = voyageai.Client(api_key=settings.voyage_api_key)
    result = client.embed([query], model=_MODEL, input_type="query")
    return result.embeddings[0]
