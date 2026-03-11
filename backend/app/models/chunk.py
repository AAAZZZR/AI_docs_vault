"""Document chunks for chunk-level RAG retrieval."""

import uuid
from datetime import datetime
from typing import Optional

from pgvector.sqlalchemy import Vector
import sqlalchemy as sa
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.config import settings
from app.models.base import Base

_VECTOR_DIM = settings.EMBEDDING_DIMENSIONS


class DocumentChunk(Base):
    """A semantic chunk of a document, used for fine-grained RAG retrieval."""

    __tablename__ = "document_chunks"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, server_default=sa.text("gen_random_uuid()")
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    heading: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    page_start: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    page_end: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    token_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    embedding = mapped_column(Vector(_VECTOR_DIM), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationship
    document: Mapped["Document"] = relationship(back_populates="chunks")  # noqa: F821
