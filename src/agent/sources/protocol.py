"""Unified ContentSource dataclass — shared format for all source adapters."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime


@dataclass
class ContentSource:
    source_type: str  # "web_search" | "rss" | "rag" | "mcp"
    title: str
    summary: str
    url: str | None
    relevance_score: float  # 0.0 – 1.0
    freshness: datetime
    full_text: str | None = None
    metadata: dict = field(default_factory=dict)  # source-specific extras
