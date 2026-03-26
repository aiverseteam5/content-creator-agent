"""Fetch a URL, extract text, chunk, embed, and persist to knowledge_chunks."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from agent.core.logging import get_logger
from agent.rag.chunker import chunk_text
from agent.rag.embedder import embed_texts

logger = get_logger(__name__)

_MAX_CONTENT_CHARS = 200_000  # cap to avoid runaway documents


@dataclass
class IngestResult:
    success: bool
    doc_id: Optional[str]
    title: str
    chunk_count: int
    message: str


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def ingest_url(url: str) -> IngestResult:
    """Fetch *url*, extract text, chunk, embed, and store in the knowledge base."""
    logger.info("ingest_url_start", url=url)

    try:
        raw_text, title = _fetch_content(url)
    except Exception as exc:
        return IngestResult(success=False, doc_id=None, title="", chunk_count=0,
                            message=f":x: Failed to fetch `{url}`: `{exc}`")

    if not raw_text.strip():
        return IngestResult(success=False, doc_id=None, title=title, chunk_count=0,
                            message=":warning: The page returned no readable text.")

    raw_text = raw_text[:_MAX_CONTENT_CHARS]
    chunks = chunk_text(raw_text)
    if not chunks:
        return IngestResult(success=False, doc_id=None, title=title, chunk_count=0,
                            message=":warning: Content too short to ingest.")

    logger.info("ingest_chunked", url=url, chunks=len(chunks))

    try:
        embeddings = embed_texts(chunks)
    except Exception as exc:
        return IngestResult(success=False, doc_id=None, title=title, chunk_count=0,
                            message=f":x: Embedding failed: `{exc}`")

    try:
        doc_id = _persist(url, title, chunks, embeddings)
    except Exception as exc:
        return IngestResult(success=False, doc_id=None, title=title, chunk_count=0,
                            message=f":x: Database error: `{exc}`")

    logger.info("ingest_complete", url=url, doc_id=doc_id, chunks=len(chunks))
    return IngestResult(
        success=True,
        doc_id=doc_id,
        title=title,
        chunk_count=len(chunks),
        message=(
            f":white_check_mark: Ingested *{title}* — "
            f"{len(chunks)} chunk{'s' if len(chunks) != 1 else ''} stored.\n"
            f"_doc id: `{doc_id}`_"
        ),
    )


# ---------------------------------------------------------------------------
# Fetch helpers
# ---------------------------------------------------------------------------

def _fetch_content(url: str) -> tuple[str, str]:
    """Return (plain_text, title) from a URL. Handles HTML and PDF."""
    import httpx

    resp = httpx.get(url, follow_redirects=True, timeout=20.0,
                     headers={"User-Agent": "Mozilla/5.0 ContentCreatorAgent/1.0"})
    resp.raise_for_status()

    content_type = resp.headers.get("content-type", "")

    if "application/pdf" in content_type or url.lower().endswith(".pdf"):
        return _extract_pdf(resp.content, url)
    else:
        return _extract_html(resp.text, url)


def _extract_html(html: str, url: str) -> tuple[str, str]:
    """Strip HTML tags and return plain text + page title."""
    # Extract title
    title_match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    title = title_match.group(1).strip() if title_match else url

    # Remove scripts / styles / head
    html = re.sub(r"<(script|style|head)[^>]*>.*?</\1>", " ", html, flags=re.IGNORECASE | re.DOTALL)
    # Strip remaining tags
    text = re.sub(r"<[^>]+>", " ", html)
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text, title


def _extract_pdf(content: bytes, url: str) -> tuple[str, str]:
    """Extract text from a PDF binary using pypdf."""
    try:
        from pypdf import PdfReader
        import io

        reader = PdfReader(io.BytesIO(content))
        pages = []
        for page in reader.pages:
            pages.append(page.extract_text() or "")
        text = "\n".join(pages)

        # Use filename as title if no metadata
        title = reader.metadata.title if (reader.metadata and reader.metadata.title) else url.split("/")[-1]
        return text, title
    except ImportError:
        raise ImportError("pypdf is required for PDF ingestion. Run: pip install pypdf")


# ---------------------------------------------------------------------------
# Database persistence (async → sync wrapper)
# ---------------------------------------------------------------------------

def _persist(url: str, title: str, chunks: list[str], embeddings: list[list[float]]) -> str:
    """Store the document and its chunks. Returns the new doc UUID as a string."""
    import asyncio
    import concurrent.futures

    async def _do_persist() -> str:
        import uuid
        from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
        from sqlalchemy.orm import sessionmaker

        from agent.core.config import get_settings
        from agent.core.models import KnowledgeChunk, KnowledgeDoc

        settings = get_settings()
        engine = create_async_engine(settings.database_url, echo=False)
        async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        try:
            async with async_session() as session:
                doc = KnowledgeDoc(
                    title=title,
                    source_url=url,
                    source_type="pdf" if url.lower().endswith(".pdf") else "url",
                    chunk_count=len(chunks),
                )
                session.add(doc)
                await session.flush()  # get doc.id

                for idx, (text, vec) in enumerate(zip(chunks, embeddings)):
                    session.add(KnowledgeChunk(
                        doc_id=doc.id,
                        chunk_index=idx,
                        content=text,
                        embedding=vec,
                    ))

                await session.commit()
                return str(doc.id)
        finally:
            await engine.dispose()

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, _do_persist()).result()
    return asyncio.run(_do_persist())
