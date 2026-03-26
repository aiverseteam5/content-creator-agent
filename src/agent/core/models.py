"""SQLAlchemy ORM models for all database tables."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from agent.core.database import Base


class ContentSignal(Base):
    """Raw research signals before they become content."""

    __tablename__ = "content_signals"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    source_url: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    raw_data: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    score: Mapped[float] = mapped_column(Float, default=0.0)
    processed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    content_items: Mapped[list["ContentItem"]] = relationship(
        back_populates="signal", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_signals_unprocessed", "processed", score.desc(), postgresql_where=(~processed)),
        Index("idx_signals_source", "source", created_at.desc()),
    )

    def __repr__(self) -> str:
        return f"<ContentSignal(id={self.id}, source={self.source}, title={self.title[:50]})>"


class ContentItem(Base):
    """Generated content at every stage of the pipeline."""

    __tablename__ = "content_items"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    signal_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )
    platform: Mapped[str] = mapped_column(String(20), nullable=False)
    content_type: Mapped[str] = mapped_column(String(20), nullable=False)
    title: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    hashtags: Mapped[Optional[list[str]]] = mapped_column(ARRAY(Text), nullable=True)
    metadata_: Mapped[Optional[dict]] = mapped_column(
        "metadata", JSONB, default=dict
    )
    status: Mapped[str] = mapped_column(String(20), default="draft")
    scheduled_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    published_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    platform_post_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    rejection_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    edit_instructions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    embedding = mapped_column(Vector(1024), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    signal: Mapped[Optional["ContentSignal"]] = relationship(back_populates="content_items")
    performance: Mapped[list["PostPerformance"]] = relationship(
        back_populates="content_item", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_items_status", "status", "scheduled_at"),
        Index("idx_items_platform", "platform", "status"),
    )

    def __repr__(self) -> str:
        return f"<ContentItem(id={self.id}, platform={self.platform}, status={self.status})>"


class PostPerformance(Base):
    """Engagement metrics pulled after publishing."""

    __tablename__ = "post_performance"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    content_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
    )
    platform: Mapped[str] = mapped_column(String(20), nullable=False)
    impressions: Mapped[int] = mapped_column(Integer, default=0)
    likes: Mapped[int] = mapped_column(Integer, default=0)
    shares: Mapped[int] = mapped_column(Integer, default=0)
    comments: Mapped[int] = mapped_column(Integer, default=0)
    clicks: Mapped[int] = mapped_column(Integer, default=0)
    engagement_rate: Mapped[float] = mapped_column(Float, default=0.0)
    raw_metrics: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    measured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    content_item: Mapped["ContentItem"] = relationship(back_populates="performance")

    __table_args__ = (
        Index("idx_performance_item", "content_item_id"),
    )

    def __repr__(self) -> str:
        return f"<PostPerformance(id={self.id}, platform={self.platform}, engagement_rate={self.engagement_rate})>"


class BrandConfig(Base):
    """Brand configuration versioning."""

    __tablename__ = "brand_config"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    config: Mapped[dict] = mapped_column(JSONB, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    def __repr__(self) -> str:
        return f"<BrandConfig(id={self.id}, version={self.version}, active={self.active})>"
