"""Unit tests for RAG retriever and rag_source (F12)."""

from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest

from agent.rag.retriever import RetrievedChunk, delete_doc, list_docs, retrieve_chunks
from agent.sources.rag_source import search_rag

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_chunks() -> list[RetrievedChunk]:
    doc_id = uuid.uuid4()
    return [
        RetrievedChunk(
            doc_id=doc_id,
            doc_title="AI Agents Guide",
            source_url="https://example.com/ai-agents",
            chunk_index=0,
            content="AI agents are autonomous software systems that perceive their environment.",
            similarity=0.91,
        ),
        RetrievedChunk(
            doc_id=doc_id,
            doc_title="AI Agents Guide",
            source_url="https://example.com/ai-agents",
            chunk_index=1,
            content="They can take actions and make decisions without direct human intervention.",
            similarity=0.87,
        ),
    ]


@pytest.fixture
def sample_docs() -> list[dict]:
    return [
        {
            "id": str(uuid.uuid4()),
            "title": "AI Agents Guide",
            "source_url": "https://example.com/ai-agents",
            "chunk_count": 12,
            "created_at": "2026-03-25T08:00:00+00:00",
        },
        {
            "id": str(uuid.uuid4()),
            "title": "LLM Architecture Overview",
            "source_url": "https://example.com/llm",
            "chunk_count": 8,
            "created_at": "2026-03-24T15:30:00+00:00",
        },
    ]


# ---------------------------------------------------------------------------
# retrieve_chunks
# ---------------------------------------------------------------------------


class TestRetrieveChunks:
    def test_returns_empty_list_when_embed_fails(self):
        # embed_query is imported locally inside retrieve_chunks → patch at source
        with patch("agent.rag.embedder.embed_query", side_effect=Exception("API down")):
            result = retrieve_chunks("AI agents", top_k=5)
        assert result == []

    def test_returns_chunks_on_success(self, sample_chunks):
        with (
            patch("agent.rag.embedder.embed_query", return_value=[0.1] * 1024),
            patch("agent.rag.retriever._run_async", return_value=sample_chunks),
        ):
            result = retrieve_chunks("AI agents", top_k=5)

        assert len(result) == 2
        assert result[0].similarity == pytest.approx(0.91)
        assert result[1].chunk_index == 1

    def test_chunk_fields_are_correct_types(self, sample_chunks):
        with (
            patch("agent.rag.embedder.embed_query", return_value=[0.1] * 1024),
            patch("agent.rag.retriever._run_async", return_value=sample_chunks),
        ):
            result = retrieve_chunks("query", top_k=5)

        chunk = result[0]
        assert isinstance(chunk.doc_id, uuid.UUID)
        assert isinstance(chunk.doc_title, str)
        assert isinstance(chunk.similarity, float)
        assert isinstance(chunk.content, str)


# ---------------------------------------------------------------------------
# list_docs
# ---------------------------------------------------------------------------


class TestListDocs:
    def test_returns_list_of_dicts(self, sample_docs):
        with patch("agent.rag.retriever._run_async", return_value=sample_docs):
            result = list_docs()

        assert isinstance(result, list)
        assert len(result) == 2
        assert "id" in result[0]
        assert "title" in result[0]
        assert "chunk_count" in result[0]

    def test_returns_empty_when_no_docs(self):
        with patch("agent.rag.retriever._run_async", return_value=[]):
            result = list_docs()
        assert result == []


# ---------------------------------------------------------------------------
# delete_doc
# ---------------------------------------------------------------------------


class TestDeleteDoc:
    def test_returns_true_when_doc_found(self):
        with patch("agent.rag.retriever._run_async", return_value=True):
            assert delete_doc(str(uuid.uuid4())) is True

    def test_returns_false_when_doc_not_found(self):
        with patch("agent.rag.retriever._run_async", return_value=False):
            assert delete_doc(str(uuid.uuid4())) is False


# ---------------------------------------------------------------------------
# search_rag (rag_source)
# ---------------------------------------------------------------------------


class TestSearchRag:
    def test_returns_content_sources_from_chunks(self, sample_chunks):
        with patch("agent.rag.retriever.retrieve_chunks", return_value=sample_chunks):
            results = search_rag("AI agents", top_k=5)

        assert len(results) == 2
        source = results[0]
        assert source.source_type == "rag"
        assert source.title == "AI Agents Guide"
        assert source.relevance_score == pytest.approx(0.91)
        assert source.url == "https://example.com/ai-agents"

    def test_returns_empty_when_no_chunks(self):
        with patch("agent.rag.retriever.retrieve_chunks", return_value=[]):
            results = search_rag("obscure topic", top_k=5)
        assert results == []

    def test_returns_empty_on_retriever_error(self):
        with patch("agent.rag.retriever.retrieve_chunks", side_effect=Exception("DB down")):
            results = search_rag("AI", top_k=5)
        assert results == []

    def test_summary_truncated_to_500_chars(self, sample_chunks):
        long_chunk = RetrievedChunk(
            doc_id=uuid.uuid4(),
            doc_title="Long Doc",
            source_url=None,
            chunk_index=0,
            content="A" * 1000,
            similarity=0.80,
        )
        with patch("agent.rag.retriever.retrieve_chunks", return_value=[long_chunk]):
            results = search_rag("something", top_k=1)

        assert len(results[0].summary) <= 500

    def test_full_text_is_full_chunk_content(self, sample_chunks):
        with patch("agent.rag.retriever.retrieve_chunks", return_value=[sample_chunks[0]]):
            results = search_rag("agents", top_k=1)

        assert results[0].full_text == sample_chunks[0].content

    def test_metadata_contains_doc_id_and_chunk_index(self, sample_chunks):
        with patch("agent.rag.retriever.retrieve_chunks", return_value=[sample_chunks[0]]):
            results = search_rag("agents", top_k=1)

        meta = results[0].metadata
        assert "doc_id" in meta
        assert "chunk_index" in meta
        assert meta["chunk_index"] == 0
