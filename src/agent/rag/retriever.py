"""pgvector-based cosine similarity retrieval and document management."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from agent.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class RetrievedChunk:
    doc_id: uuid.UUID
    doc_title: str
    source_url: str | None
    chunk_index: int
    content: str
    similarity: float  # 0–1, higher = more similar


def _run_async(coro):
    """Run an async coroutine from a sync context."""
    import asyncio
    import concurrent.futures

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, coro).result()
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# Public API (sync wrappers over async DB)
# ---------------------------------------------------------------------------


def retrieve_chunks(query: str, top_k: int = 5) -> list[RetrievedChunk]:
    """Return the top-k most relevant chunks for *query*."""
    from agent.rag.embedder import embed_query

    try:
        vector = embed_query(query)
    except Exception as exc:
        logger.warning("retrieve_embed_failed", error=str(exc))
        return []

    return _run_async(_async_retrieve(vector, top_k))


def list_docs() -> list[dict]:
    """Return a list of all ingested documents (id, title, url, chunk_count, created_at)."""
    return _run_async(_async_list_docs())


def delete_doc(doc_id: str) -> bool:
    """Delete a document and all its chunks. Returns True if found and deleted."""
    return _run_async(_async_delete_doc(doc_id))


# ---------------------------------------------------------------------------
# Async DB helpers
# ---------------------------------------------------------------------------


async def _async_retrieve(vector: list[float], top_k: int) -> list[RetrievedChunk]:
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    from agent.core.config import get_settings

    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    results: list[RetrievedChunk] = []
    try:
        async with async_session() as session:
            # Use raw SQL for pgvector cosine distance ordering
            stmt = text(
                """
                SELECT
                    kc.id,
                    kc.doc_id,
                    kd.title        AS doc_title,
                    kd.source_url,
                    kc.chunk_index,
                    kc.content,
                    1 - (kc.embedding <=> CAST(:vec AS vector)) AS similarity
                FROM knowledge_chunks kc
                JOIN knowledge_docs   kd ON kd.id = kc.doc_id
                WHERE kc.embedding IS NOT NULL
                ORDER BY kc.embedding <=> CAST(:vec AS vector)
                LIMIT :k
                """
            )
            # pgvector expects a vector literal like '[0.1, 0.2, ...]'
            vec_literal = "[" + ",".join(f"{v:.8f}" for v in vector) + "]"
            rows = (await session.execute(stmt, {"vec": vec_literal, "k": top_k})).all()
            results = [
                RetrievedChunk(
                    doc_id=r.doc_id,
                    doc_title=r.doc_title,
                    source_url=r.source_url,
                    chunk_index=r.chunk_index,
                    content=r.content,
                    similarity=float(r.similarity),
                )
                for r in rows
            ]
    finally:
        await engine.dispose()

    logger.info("retrieve_chunks_complete", query_len=len(str(vector)), results=len(results))
    return results


async def _async_list_docs() -> list[dict]:
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    from agent.core.config import get_settings
    from agent.core.models import KnowledgeDoc

    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    docs: list[dict] = []
    try:
        async with async_session() as session:
            rows = (
                (await session.execute(select(KnowledgeDoc).order_by(KnowledgeDoc.created_at.desc()))).scalars().all()
            )
            docs = [
                {
                    "id": str(d.id),
                    "title": d.title,
                    "source_url": d.source_url,
                    "chunk_count": d.chunk_count,
                    "created_at": d.created_at.isoformat() if d.created_at else None,
                }
                for d in rows
            ]
    finally:
        await engine.dispose()

    return docs


async def _async_delete_doc(doc_id: str) -> bool:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    from agent.core.config import get_settings
    from agent.core.models import KnowledgeDoc

    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    deleted = False
    try:
        async with async_session() as session:
            doc = await session.get(KnowledgeDoc, uuid.UUID(doc_id))
            if doc:
                await session.delete(doc)
                await session.commit()
                deleted = True
    except (ValueError, Exception) as exc:
        logger.error("delete_doc_error", doc_id=doc_id, error=str(exc))
    finally:
        await engine.dispose()

    return deleted
