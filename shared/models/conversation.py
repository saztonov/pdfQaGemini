"""Conversation entities"""

from datetime import datetime
from typing import Any, Literal, Optional
from uuid import UUID
from pydantic import BaseModel, Field, field_validator


class Conversation(BaseModel):
    id: UUID
    client_id: str
    title: str = ""
    model_default: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ConversationWithStats(BaseModel):
    """Conversation with additional statistics"""

    id: UUID
    client_id: str
    title: str = ""
    model_default: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    message_count: int = 0
    file_count: int = 0
    last_message_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class Message(BaseModel):
    id: UUID
    conversation_id: UUID
    role: Literal["user", "assistant", "tool", "system"]
    content: str
    meta: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime

    @field_validator("content")
    @classmethod
    def content_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("content cannot be empty")
        return v

    class Config:
        from_attributes = True
