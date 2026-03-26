"""Pydantic schemas for API and internal data transfer."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------
class Platform(str, Enum):
    LINKEDIN = "linkedin"
    TWITTER = "twitter"


class ContentStatus(str, Enum):
    DRAFT = "draft"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    PUBLISHED = "published"
    FAILED = "failed"
    REJECTED = "rejected"


class ContentType(str, Enum):
    POST = "post"
    TWEET = "tweet"
    THREAD = "thread"


class SignalSource(str, Enum):
    RSS = "rss"
    REDDIT = "reddit"
    ARXIV = "arxiv"
    GOOGLE_NEWS = "google_news"


class Priority(str, Enum):
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
    summary: Optional[str] = None
    raw_data: Optional[dict] = None


class ContentSignalRead(BaseModel):
    id: uuid.UUID
    source: str
    source_url: str
    title: str
    summary: Optional[str]
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
    source_url: Optional[str] = None
    source_summary: Optional[str] = None


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
    signal_id: Optional[uuid.UUID] = None
    platform: Platform
    content_type: ContentType
    title: Optional[str] = None
    body: str
    hashtags: Optional[list[str]] = None
    metadata: dict = Field(default_factory=dict)
    scheduled_at: Optional[datetime] = None


class ContentItemRead(BaseModel):
    id: uuid.UUID
    signal_id: Optional[uuid.UUID]
    platform: str
    content_type: str
    title: Optional[str]
    body: str
    hashtags: Optional[list[str]]
    status: str
    scheduled_at: Optional[datetime]
    published_at: Optional[datetime]
    platform_post_id: Optional[str]
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
