"""Fresh schema — no auth, tag evolution support

Revision ID: 001
Revises:
Create Date: 2026-03-08

"""
from typing import Sequence, Union

import os

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

_VECTOR_DIM = int(os.environ.get("EMBEDDING_DIMENSIONS", "768"))

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Extensions
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')

    # Enum types
    document_status = postgresql.ENUM(
        "processing", "ready", "error", name="document_status", create_type=False
    )
    tag_source = postgresql.ENUM(
        "auto", "user", "evolved", name="tag_source", create_type=False
    )
    document_status.create(op.get_bind(), checkfirst=True)
    tag_source.create(op.get_bind(), checkfirst=True)

    # Documents (no user_id)
    op.create_table(
        "documents",
        sa.Column("id", sa.Uuid(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("original_filename", sa.String(500), nullable=False),
        sa.Column("pdf_data", sa.LargeBinary(), nullable=True),
        sa.Column("file_size", sa.BigInteger(), nullable=False),
        sa.Column("page_count", sa.Integer(), nullable=True),
        sa.Column("status", document_status, nullable=False, server_default="processing"),
        sa.Column("condensed_note", postgresql.JSONB(), nullable=True),
        sa.Column("global_index_entry", sa.Text(), nullable=True),
        sa.Column("processing_error", sa.Text(), nullable=True),
        sa.Column("processing_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("processing_completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("embedding", Vector(_VECTOR_DIM), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_documents_status", "documents", ["status"])
    op.execute(
        "CREATE INDEX ix_documents_embedding ON documents USING hnsw (embedding vector_cosine_ops)"
    )

    # Tags (no user_id, with embedding)
    op.create_table(
        "tags",
        sa.Column("id", sa.Uuid(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
        sa.Column("color", sa.String(7), nullable=True),
        sa.Column("source", tag_source, nullable=False, server_default="auto"),
        sa.Column("parent_id", sa.Uuid(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("embedding", Vector(_VECTOR_DIM), nullable=True),
        sa.Column("document_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["parent_id"], ["tags.id"], ondelete="SET NULL"),
    )
    op.execute(
        "CREATE INDEX ix_tags_embedding ON tags USING hnsw (embedding vector_cosine_ops)"
    )

    # Document Tags
    op.create_table(
        "document_tags",
        sa.Column("id", sa.Uuid(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("tag_id", sa.Uuid(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("source", tag_source, nullable=False, server_default="auto"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tag_id"], ["tags.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("document_id", "tag_id", name="uq_document_tag"),
    )
    op.create_index("ix_document_tags_document_id", "document_tags", ["document_id"])
    op.create_index("ix_document_tags_tag_id", "document_tags", ["tag_id"])

    # Tag Events (user feedback loop)
    op.create_table(
        "tag_events",
        sa.Column("id", sa.Uuid(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("tag_id", sa.Uuid(), nullable=True),
        sa.Column("document_id", sa.Uuid(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tag_id"], ["tags.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="SET NULL"),
    )

    # Evolution Log
    op.create_table(
        "evolution_log",
        sa.Column("id", sa.Uuid(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("details", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_evolution_log_status", "evolution_log", ["status"])

    # Chat Messages (no user_id, no conversation_id — single stream)
    op.create_table(
        "chat_messages",
        sa.Column("id", sa.Uuid(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("referenced_documents", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("chat_messages")
    op.drop_table("evolution_log")
    op.drop_table("tag_events")
    op.drop_table("document_tags")
    op.drop_table("tags")
    op.drop_table("documents")
    op.execute("DROP TYPE IF EXISTS document_status")
    op.execute("DROP TYPE IF EXISTS tag_source")
