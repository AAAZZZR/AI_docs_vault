import enum
import uuid
from datetime import datetime
from typing import Optional

from pgvector.sqlalchemy import Vector
from sqlalchemy import BigInteger, DateTime, Enum, Integer, LargeBinary, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.config import settings
from app.models.base import Base, TimestampMixin

_VECTOR_DIM = settings.EMBEDDING_DIMENSIONS


class DocumentStatus(str, enum.Enum):
    PROCESSING = "processing"
    READY = "ready"
    ERROR = "error"


class Document(Base, TimestampMixin):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(500), nullable=False)
    pdf_data: Mapped[Optional[bytes]] = mapped_column(LargeBinary, nullable=True)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    page_count: Mapped[Optional[int]] = mapped_column(Integer)
    status: Mapped[DocumentStatus] = mapped_column(
        Enum(DocumentStatus, name="document_status", values_callable=lambda e: [x.value for x in e]),
        default=DocumentStatus.PROCESSING,
        index=True,
        nullable=False,
    )
    condensed_note: Mapped[Optional[dict]] = mapped_column(JSONB)
    global_index_entry: Mapped[Optional[str]] = mapped_column(Text)
    processing_error: Mapped[Optional[str]] = mapped_column(Text)
    processing_started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True)
    )
    processing_completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True)
    )
    embedding = mapped_column(Vector(_VECTOR_DIM), nullable=True)

    # Relationships
    document_tags: Mapped[list["DocumentTag"]] = relationship(  # noqa: F821
        back_populates="document", cascade="all, delete-orphan"
    )
