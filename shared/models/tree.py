"""Tree entities"""

from typing import Any, Optional
from uuid import UUID
from pydantic import BaseModel, Field


class TreeNode(BaseModel):
    id: UUID
    parent_id: Optional[UUID] = None
    client_id: str = "default"
    node_type: str
    name: str
    code: Optional[str] = None
    version: int
    status: str
    attributes: dict[str, Any] = Field(default_factory=dict)
    sort_order: int = 0

    class Config:
        from_attributes = True


class NodeFile(BaseModel):
    id: UUID
    node_id: UUID
    file_type: str
    r2_key: str
    file_name: str
    file_size: int
    mime_type: str
    metadata: dict[str, Any] = Field(default_factory=dict)

    class Config:
        from_attributes = True
