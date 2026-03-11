import enum
import uuid
from datetime import datetime
from typing import Optional

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.config import settings
from app.models.base import Base, TimestampMixin

_VECTOR_DIM = settings.EMBEDDING_DIMENSIONS


class TagSource(str, enum.Enum):
    AUTO = "auto"
    USER = "user"
    EVOLVED = "evolved"


class Tag(Base, TimestampMixin):
    __tablename__ = "tags"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    color: Mapped[Optional[str]] = mapped_column(String(7))
    source: Mapped[TagSource] = mapped_column(
        Enum(TagSource, name="tag_source"), default=TagSource.AUTO, nullable=False
    )
    parent_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("tags.id", ondelete="SET NULL")
    )
    description: Mapped[Optional[str]] = mapped_column(Text)
    embedding = mapped_column(Vector(_VECTOR_DIM), nullable=True)
    document_count: Mapped[int] = mapped_column(
        Integer, server_default="0", nullable=False
    )

    # Relationships
    document_tags: Mapped[list["DocumentTag"]] = relationship(
        back_populates="tag", cascade="all, delete-orphan"
    )


class DocumentTag(Base, TimestampMixin):
    __tablename__ = "document_tags"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tag_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tags.id", ondelete="CASCADE"), nullable=False, index=True
    )
    confidence: Mapped[Optional[float]] = mapped_column(Float)
    source: Mapped[TagSource] = mapped_column(
        Enum(TagSource, name="tag_source", create_type=False),
        default=TagSource.AUTO,
        nullable=False,
    )

    # Relationships
    document: Mapped["Document"] = relationship(back_populates="document_tags")  # noqa: F821
    tag: Mapped["Tag"] = relationship(back_populates="document_tags")


class TagEvent(Base):
    """Records user feedback actions on tags for evolution learning."""
    __tablename__ = "tag_events"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    tag_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("tags.id", ondelete="SET NULL")
    )
    document_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("documents.id", ondelete="SET NULL")
    )
    metadata_: Mapped[Optional[dict]] = mapped_column("metadata", JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class EvolutionLog(Base):
    """Tracks tag evolution operations (merge, split, reparent, etc.)."""
    __tablename__ = "evolution_log"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    details: Mapped[dict] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), server_default="pending", nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
