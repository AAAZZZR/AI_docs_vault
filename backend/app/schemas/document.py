import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class UploadResponse(BaseModel):
    document_id: uuid.UUID
    status: str


class TagInDocument(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    color: str | None = None
    source: str
    confidence: float | None = None


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    original_filename: str
    file_size: int
    page_count: int | None = None
    status: str
    global_index_entry: str | None = None
    condensed_note: dict | None = None
    tags: list[TagInDocument] = []
    created_at: datetime
    updated_at: datetime


class DocumentListResponse(BaseModel):
    documents: list[DocumentResponse]
    total: int
    page: int
    page_size: int


class DocumentDetailResponse(DocumentResponse):
    has_pdf: bool = False
