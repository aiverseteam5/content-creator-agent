"""Unit tests for RAG text chunker (F12)."""

from __future__ import annotations

from agent.rag.chunker import chunk_text


class TestChunkText:
    def test_empty_string_returns_empty_list(self):
        assert chunk_text("") == []

    def test_whitespace_only_returns_empty_list(self):
        assert chunk_text("   \n\t  ") == []

    def test_short_text_returns_single_chunk(self):
        # Text must be >= _MIN_CHARS (80) to survive the filter
        text = "This is a reasonably long sentence about AI agents and their autonomous capabilities."
        result = chunk_text(text)
        assert len(result) == 1
        assert result[0] == text

    def test_long_text_produces_multiple_chunks(self):
        # 800 words should give at least 2 chunks with default chunk_words=400
        words = ["word"] * 800
        text = " ".join(words)
        result = chunk_text(text)
        assert len(result) >= 2

    def test_chunk_size_respected(self):
        words = ["w"] * 1000
        text = " ".join(words)
        result = chunk_text(text, chunk_words=100, overlap=10)
        # Each chunk should have at most 100 words
        for chunk in result:
            assert len(chunk.split()) <= 100

    def test_overlap_means_consecutive_chunks_share_words(self):
        words = [f"word{i}" for i in range(200)]
        text = " ".join(words)
        result = chunk_text(text, chunk_words=100, overlap=20)
        assert len(result) >= 2
        # Last words of chunk 0 should appear at start of chunk 1
        end_of_first = set(result[0].split()[-20:])
        start_of_second = set(result[1].split()[:20])
        assert len(end_of_first & start_of_second) > 0

    def test_tiny_chunks_are_filtered(self):
        # A single word is shorter than _MIN_CHARS → should be filtered out
        # Create a scenario where the last chunk would be a single word
        result = chunk_text("x", chunk_words=400, overlap=50)
        # "x" is 1 char, less than _MIN_CHARS (80), so filtered
        assert result == []

    def test_content_preserved(self):
        text = "The quick brown fox jumps over the lazy dog. " * 20
        result = chunk_text(text)
        combined = " ".join(result)
        # Every original word should appear in at least one chunk
        for word in text.split()[:10]:
            assert word in combined

    def test_custom_chunk_words(self):
        # Use longer words so each chunk exceeds _MIN_CHARS (80 chars)
        words = ["technology"] * 50
        text = " ".join(words)
        result = chunk_text(text, chunk_words=10, overlap=2)
        assert len(result) > 1
