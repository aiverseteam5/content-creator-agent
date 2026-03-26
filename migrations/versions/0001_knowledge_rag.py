"""Add knowledge_docs and knowledge_chunks tables for RAG pipeline (F12).

Revision ID: 0001_knowledge_rag
Revises:
Create Date: 2026-03-26
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = "0001_knowledge_rag"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Enable pgvector extension (idempotent)
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # knowledge_docs — one row per ingested document
    op.create_table(
        "knowledge_docs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("source_url", sa.Text, nullable=True, unique=True),
        sa.Column("source_type", sa.String(20), nullable=False, server_default="url"),
        sa.Column("chunk_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    # knowledge_chunks — one row per text chunk with its embedding
    op.create_table(
        "knowledge_chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "doc_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("knowledge_docs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("chunk_index", sa.Integer, nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("embedding", Vector(1024), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    # Regular B-tree index on doc_id for fast chunk lookups
    op.create_index("idx_chunks_doc_id", "knowledge_chunks", ["doc_id"])

    # HNSW index for fast cosine similarity search
    op.execute(
        """
        CREATE INDEX idx_chunks_embedding_hnsw
        ON knowledge_chunks
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
        """
    )


def downgrade() -> None:
    op.drop_index("idx_chunks_embedding_hnsw", table_name="knowledge_chunks")
    op.drop_index("idx_chunks_doc_id", table_name="knowledge_chunks")
    op.drop_table("knowledge_chunks")
    op.drop_table("knowledge_docs")
