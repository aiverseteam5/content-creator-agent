"""Pydantic schemas for API and internal data transfer."""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import uuid
    from datetime import datetime

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------
class Platform(StrEnum):
    LINKEDIN = "linkedin"
    TWITTER = "twitter"


class ContentStatus(StrEnum):
    DRAFT = "draft"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    PUBLISHED = "published"
    FAILED = "failed"
    REJECTED = "rejected"


class ContentType(StrEnum):
    POST = "post"
    TWEET = "tweet"
    THREAD = "thread"


class SignalSource(StrEnum):
    RSS = "rss"
    REDDIT = "reddit"
    ARXIV = "arxiv"
    GOOGLE_NEWS = "google_news"


class Priority(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# ---------------------------------------------------------------------------
# Content Signal schemas
# ---------------------------------------------------------------------------
class ContentSignalCreate(BaseModel):
    source: SignalSource
    source_url: str
    title: str
    summary: str | None = None
    raw_data: dict | None = None


class ContentSignalRead(BaseModel):
    id: uuid.UUID
    source: str
    source_url: str
    title: str
    summary: str | None
    score: float
    processed: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Content Brief (used by LangGraph orchestrator)
# ---------------------------------------------------------------------------
class ContentBrief(BaseModel):
    signal_id: uuid.UUID
    topic: str
    angle: str
    key_points: list[str] = Field(..., min_length=3, max_length=5)
    target_platforms: list[Platform]
    priority: Priority = Priority.MEDIUM
    source_url: str | None = None
    source_summary: str | None = None


# ---------------------------------------------------------------------------
# Generated Content
# ---------------------------------------------------------------------------
class GeneratedContent(BaseModel):
    platform: Platform
    content_type: ContentType
    body: str
    hashtags: list[str] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Content Item schemas
# ---------------------------------------------------------------------------
class ContentItemCreate(BaseModel):
    signal_id: uuid.UUID | None = None
    platform: Platform
    content_type: ContentType
    title: str | None = None
    body: str
    hashtags: list[str] | None = None
    metadata: dict = Field(default_factory=dict)
    scheduled_at: datetime | None = None


class ContentItemRead(BaseModel):
    id: uuid.UUID
    signal_id: uuid.UUID | None
    platform: str
    content_type: str
    title: str | None
    body: str
    hashtags: list[str] | None
    status: str
    scheduled_at: datetime | None
    published_at: datetime | None
    platform_post_id: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Post Performance
# ---------------------------------------------------------------------------
class PostPerformanceRead(BaseModel):
    id: uuid.UUID
    content_item_id: uuid.UUID
    platform: str
    impressions: int
    likes: int
    shares: int
    comments: int
    clicks: int
    engagement_rate: float
    measured_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# API Health Check
# ---------------------------------------------------------------------------
class HealthResponse(BaseModel):
    status: str = "healthy"
    version: str
    environment: str
    database: str = "unknown"
    redis: str = "unknown"


# ---------------------------------------------------------------------------
# Slack Interaction schemas
# ---------------------------------------------------------------------------
class SlackInstruction(BaseModel):
    intent: str  # "focus_topic", "create_post", "change_schedule", "get_status", "unknown"
    params: dict = Field(default_factory=dict)
    raw_text: str = ""
