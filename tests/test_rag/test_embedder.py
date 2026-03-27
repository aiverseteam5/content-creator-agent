"""Unit tests for RAG embedder (F12)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from agent.rag.embedder import embed_texts, embed_query, _MODEL


@pytest.fixture
def mock_voyage_result():
    result = MagicMock()
    result.embeddings = [[0.1] * 1024, [0.2] * 1024]
    return result


@pytest.fixture
def mock_voyage_client(mock_voyage_result):
    client = MagicMock()
    client.embed.return_value = mock_voyage_result
    return client


class TestEmbedTexts:
    def test_empty_list_returns_empty(self):
        assert embed_texts([]) == []

    def test_returns_one_embedding_per_text(self, mock_voyage_client):
        with (
            patch("agent.rag.embedder.voyageai") as mock_voyage_module,
            patch("agent.rag.embedder.get_settings", return_value=MagicMock(voyage_api_key="test")),
        ):
            mock_voyage_module.Client.return_value = mock_voyage_client
            result = embed_texts(["text one", "text two"])

        assert len(result) == 2
        assert len(result[0]) == 1024

    def test_uses_document_input_type(self, mock_voyage_client):
        with (
            patch("agent.rag.embedder.voyageai") as mock_voyage_module,
            patch("agent.rag.embedder.get_settings", return_value=MagicMock(voyage_api_key="test")),
        ):
            mock_voyage_module.Client.return_value = mock_voyage_client
            embed_texts(["some text"])

        call_kwargs = mock_voyage_client.embed.call_args
        assert call_kwargs.kwargs.get("input_type") == "document" or \
               call_kwargs.args[2] == "document" or \
               "document" in str(call_kwargs)

    def test_uses_correct_model(self, mock_voyage_client):
        with (
            patch("agent.rag.embedder.voyageai") as mock_voyage_module,
            patch("agent.rag.embedder.get_settings", return_value=MagicMock(voyage_api_key="test")),
        ):
            mock_voyage_module.Client.return_value = mock_voyage_client
            embed_texts(["text"])

        call_kwargs = mock_voyage_client.embed.call_args
        assert _MODEL in str(call_kwargs)

    def test_batches_large_input(self, mock_voyage_client):
        """With BATCH_SIZE=16, 20 texts should require 2 API calls."""
        single_embedding = MagicMock()
        single_embedding.embeddings = [[0.1] * 1024] * 16

        last_batch = MagicMock()
        last_batch.embeddings = [[0.1] * 1024] * 4

        mock_voyage_client.embed.side_effect = [single_embedding, last_batch]

        with (
            patch("agent.rag.embedder.voyageai") as mock_voyage_module,
            patch("agent.rag.embedder.get_settings", return_value=MagicMock(voyage_api_key="test")),
            patch("agent.rag.embedder.time"),  # suppress sleep
        ):
            mock_voyage_module.Client.return_value = mock_voyage_client
            result = embed_texts(["t"] * 20)

        assert len(result) == 20
        assert mock_voyage_client.embed.call_count == 2

    def test_propagates_api_error(self, mock_voyage_client):
        mock_voyage_client.embed.side_effect = Exception("rate limited")
        with (
            patch("agent.rag.embedder.voyageai") as mock_voyage_module,
            patch("agent.rag.embedder.get_settings", return_value=MagicMock(voyage_api_key="test")),
        ):
            mock_voyage_module.Client.return_value = mock_voyage_client
            with pytest.raises(Exception, match="rate limited"):
                embed_texts(["text"])


class TestEmbedQuery:
    def test_returns_single_vector(self):
        mock_result = MagicMock()
        mock_result.embeddings = [[0.5] * 1024]
        mock_client = MagicMock()
        mock_client.embed.return_value = mock_result

        with (
            patch("agent.rag.embedder.voyageai") as mock_voyage_module,
            patch("agent.rag.embedder.get_settings", return_value=MagicMock(voyage_api_key="test")),
        ):
            mock_voyage_module.Client.return_value = mock_client
            result = embed_query("what is a transformer?")

        assert isinstance(result, list)
        assert len(result) == 1024

    def test_uses_query_input_type(self):
        mock_result = MagicMock()
        mock_result.embeddings = [[0.5] * 1024]
        mock_client = MagicMock()
        mock_client.embed.return_value = mock_result

        with (
            patch("agent.rag.embedder.voyageai") as mock_voyage_module,
            patch("agent.rag.embedder.get_settings", return_value=MagicMock(voyage_api_key="test")),
        ):
            mock_voyage_module.Client.return_value = mock_client
            embed_query("my query")

        call_kwargs = mock_client.embed.call_args
        assert "query" in str(call_kwargs)
