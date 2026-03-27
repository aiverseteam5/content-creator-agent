"""Split text into overlapping word-window chunks."""

from __future__ import annotations

_CHUNK_WORDS = 400  # target words per chunk
_OVERLAP_WORDS = 50  # overlap between consecutive chunks
_MIN_CHARS = 80  # discard chunks shorter than this


def chunk_text(text: str, chunk_words: int = _CHUNK_WORDS, overlap: int = _OVERLAP_WORDS) -> list[str]:
    """Return a list of overlapping text chunks from *text*."""
    words = text.split()
    if not words:
        return []

    chunks: list[str] = []
    step = max(1, chunk_words - overlap)
    i = 0
    while i < len(words):
        chunk = " ".join(words[i : i + chunk_words])
        if len(chunk.strip()) >= _MIN_CHARS:
            chunks.append(chunk)
        i += step

    return chunks
