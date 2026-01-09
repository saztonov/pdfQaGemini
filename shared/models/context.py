"""Context panel entities"""

from typing import Literal, Optional
from uuid import UUID
from pydantic import BaseModel, field_validator


class ContextItem(BaseModel):
    id: str  # UUID or custom id
    title: str
    node_id: Optional[UUID] = None
    node_file_id: Optional[UUID] = None
    r2_key: Optional[str] = None
    url: Optional[str] = None
    mime_type: str
    status: Literal["local", "downloaded", "uploaded"] = "local"
    gemini_name: Optional[str] = None
    gemini_uri: Optional[str] = None

    @field_validator("title")
    @classmethod
    def title_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("title cannot be empty")
        return v
