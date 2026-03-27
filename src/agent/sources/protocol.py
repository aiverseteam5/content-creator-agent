"""Unified ContentSource dataclass — shared format for all source adapters."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class ContentSource:
    source_type: str            # "web_search" | "rss" | "rag" | "mcp"
    title: str
    summary: str
    url: Optional[str]
    relevance_score: float      # 0.0 – 1.0
    freshness: datetime
    full_text: Optional[str] = None
    metadata: dict = field(default_factory=dict)   # source-specific extras
