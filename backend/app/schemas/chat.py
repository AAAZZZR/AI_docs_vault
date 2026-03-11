import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ChatMessageRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=10000)
    tag_filter: list[uuid.UUID] | None = None


class ChatMessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    role: str
    content: str
    referenced_documents: list | None = None
    created_at: datetime
