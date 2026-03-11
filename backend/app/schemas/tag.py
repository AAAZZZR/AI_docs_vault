import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TagCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    color: str | None = Field(None, max_length=7)
    description: str | None = None
    parent_id: uuid.UUID | None = None


class TagUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    color: str | None = Field(None, max_length=7)
    description: str | None = None
    parent_id: uuid.UUID | None = None


class TagResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    color: str | None = None
    source: str
    description: str | None = None
    parent_id: uuid.UUID | None = None
    document_count: int = 0
    created_at: datetime
