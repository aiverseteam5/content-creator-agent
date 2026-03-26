"""Unit tests for RAG ingester (F12)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from agent.rag.ingester import (
    IngestResult,
    _extract_html,
    _extract_pdf,
    ingest_url,
)


# ---------------------------------------------------------------------------
# HTML extraction
# ---------------------------------------------------------------------------

class TestExtractHtml:
    def test_extracts_title(self):
        html = "<html><head><title>My Page Title</title></head><body>Hello world</body></html>"
        text, title = _extract_html(html, "https://example.com")
        assert title == "My Page Title"

    def test_falls_back_to_url_when_no_title(self):
        html = "<html><body>No title here</body></html>"
        text, title = _extract_html(html, "https://example.com/page")
        assert title == "https://example.com/page"

    def test_strips_html_tags(self):
        html = "<html><body><p>Hello <b>world</b></p></body></html>"
        text, _ = _extract_html(html, "https://example.com")
        assert "<" not in text
        assert "Hello" in text
        assert "world" in text

    def test_removes_script_tags(self):
        html = "<html><body><script>alert('xss')</script><p>Content</p></body></html>"
        text, _ = _extract_html(html, "https://example.com")
        assert "alert" not in text
        assert "Content" in text

    def test_removes_style_tags(self):
        html = "<html><head><style>body{color:red}</style></head><body>Text</body></html>"
        text, _ = _extract_html(html, "https://example.com")
        assert "color:red" not in text
        assert "Text" in text

    def test_collapses_whitespace(self):
        html = "<p>Hello   \n\n   world</p>"
        text, _ = _extract_html(html, "https://x.com")
        assert "  " not in text  # no double spaces


# ---------------------------------------------------------------------------
# PDF extraction
# ---------------------------------------------------------------------------

class TestExtractPdf:
    def test_extracts_text_from_pages(self):
        mock_page1 = MagicMock()
        mock_page1.extract_text.return_value = "Page one content"
        mock_page2 = MagicMock()
        mock_page2.extract_text.return_value = "Page two content"

        mock_reader = MagicMock()
        mock_reader.pages = [mock_page1, mock_page2]
        mock_reader.metadata = MagicMock(title="PDF Title")

        with patch("agent.rag.ingester.PdfReader", return_value=mock_reader):
            text, title = _extract_pdf(b"%PDF-fake", "https://example.com/doc.pdf")

        assert "Page one content" in text
        assert "Page two content" in text
        assert title == "PDF Title"

    def test_uses_filename_when_no_metadata_title(self):
        mock_reader = MagicMock()
        mock_reader.pages = []
        mock_reader.metadata = MagicMock(title=None)

        with patch("agent.rag.ingester.PdfReader", return_value=mock_reader):
            _, title = _extract_pdf(b"%PDF-fake", "https://example.com/my-report.pdf")

        assert title == "my-report.pdf"

    def test_raises_import_error_when_pypdf_missing(self):
        with patch.dict("sys.modules", {"pypdf": None}):
            with pytest.raises((ImportError, ModuleNotFoundError, TypeError)):
                _extract_pdf(b"data", "https://example.com/doc.pdf")


# ---------------------------------------------------------------------------
# ingest_url — integration (all external calls mocked)
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_html_response():
    resp = MagicMock()
    resp.headers = {"content-type": "text/html"}
    resp.text = "<html><head><title>AI News</title></head><body>" + ("AI is transforming the world. " * 200) + "</body></html>"
    resp.content = b""
    resp.raise_for_status = MagicMock()
    return resp


class TestIngestUrl:
    def test_happy_path_html(self, mock_html_response):
        fake_embeddings = [[0.1] * 1024] * 3  # assume 3 chunks

        with (
            patch("agent.rag.ingester.httpx") as mock_httpx,
            patch("agent.rag.ingester.embed_texts", return_value=fake_embeddings),
            patch("agent.rag.ingester._persist", return_value="abc-123-uuid"),
            patch("agent.rag.ingester.chunk_text", return_value=["chunk1", "chunk2", "chunk3"]),
        ):
            mock_httpx.get.return_value = mock_html_response
            result = ingest_url("https://example.com/article")

        assert result.success is True
        assert result.doc_id == "abc-123-uuid"
        assert result.chunk_count == 3
        assert "AI News" in result.title or result.title != ""
        assert "✅" in result.message or "white_check_mark" in result.message

    def test_fetch_failure_returns_error_result(self):
        with patch("agent.rag.ingester.httpx") as mock_httpx:
            mock_httpx.get.side_effect = Exception("Connection refused")
            result = ingest_url("https://unreachable.example.com/")

        assert result.success is False
        assert "Connection refused" in result.message or "Failed to fetch" in result.message

    def test_empty_content_returns_error(self, mock_html_response):
        mock_html_response.text = "<html><body></body></html>"
        with (
            patch("agent.rag.ingester.httpx") as mock_httpx,
            patch("agent.rag.ingester.chunk_text", return_value=[]),
        ):
            mock_httpx.get.return_value = mock_html_response
            result = ingest_url("https://example.com/empty")

        assert result.success is False

    def test_embed_failure_returns_error(self, mock_html_response):
        with (
            patch("agent.rag.ingester.httpx") as mock_httpx,
            patch("agent.rag.ingester.chunk_text", return_value=["chunk one"]),
            patch("agent.rag.ingester.embed_texts", side_effect=Exception("API down")),
        ):
            mock_httpx.get.return_value = mock_html_response
            result = ingest_url("https://example.com/article")

        assert result.success is False
        assert "Embedding failed" in result.message or "API down" in result.message

    def test_db_failure_returns_error(self, mock_html_response):
        with (
            patch("agent.rag.ingester.httpx") as mock_httpx,
            patch("agent.rag.ingester.chunk_text", return_value=["chunk one"]),
            patch("agent.rag.ingester.embed_texts", return_value=[[0.1] * 1024]),
            patch("agent.rag.ingester._persist", side_effect=Exception("DB error")),
        ):
            mock_httpx.get.return_value = mock_html_response
            result = ingest_url("https://example.com/article")

        assert result.success is False
        assert "Database error" in result.message or "DB error" in result.message

    def test_pdf_url_routes_to_pdf_extractor(self):
        resp = MagicMock()
        resp.headers = {"content-type": "text/html"}
        resp.content = b"%PDF-fake-content"
        resp.raise_for_status = MagicMock()

        with (
            patch("agent.rag.ingester.httpx") as mock_httpx,
            patch("agent.rag.ingester._extract_pdf", return_value=("PDF text content " * 100, "My PDF")) as mock_pdf,
            patch("agent.rag.ingester.embed_texts", return_value=[[0.1] * 1024]),
            patch("agent.rag.ingester._persist", return_value="pdf-doc-id"),
            patch("agent.rag.ingester.chunk_text", return_value=["chunk"]),
        ):
            mock_httpx.get.return_value = resp
            result = ingest_url("https://example.com/report.pdf")

        mock_pdf.assert_called_once()
