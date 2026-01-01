"""Pydantic schemas"""
from datetime import datetime
from enum import Enum
from typing import Optional, Any, Literal
from uuid import UUID
from pydantic import BaseModel, Field, field_validator


class FileType(str, Enum):
    """Типы файлов в node_files"""
    PDF = "pdf"                 # Исходный PDF
    ANNOTATION = "annotation"   # Разметка блоков ({name}_annotation.json)
    OCR_HTML = "ocr_html"       # HTML результат ({name}_ocr.html)
    RESULT_JSON = "result_json" # Полный результат ({name}_result.json)
    CROP = "crop"               # Кропы изображений (в папке crops/)


# Иконки для типов файлов
FILE_TYPE_ICONS = {
    FileType.PDF: "📄",
    FileType.ANNOTATION: "📋",
    FileType.OCR_HTML: "📝",
    FileType.RESULT_JSON: "📊",
    FileType.CROP: "🖼️",
}

# Цвета для типов файлов
FILE_TYPE_COLORS = {
    FileType.PDF: "#FFFFFF",
    FileType.ANNOTATION: "#FF69B4",
    FileType.OCR_HTML: "#FFD700",
    FileType.RESULT_JSON: "#32CD32",
    FileType.CROP: "#9370DB",
}


# Tree entities
class TreeNode(BaseModel):
    id: UUID
    parent_id: Optional[UUID] = None
    client_id: str
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


# Conversation entities
class Conversation(BaseModel):
    id: UUID
    client_id: str
    title: str = ""
    model_default: Optional[str] = None  # deprecated, loaded from API
    created_at: datetime
    updated_at: datetime
    
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


# Context panel
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


# Model outputs
class ModelAction(BaseModel):
    type: Literal["answer", "open_image", "request_roi", "final"]
    payload: dict[str, Any] = Field(default_factory=dict)
    note: Optional[str] = None


class ModelReply(BaseModel):
    assistant_text: str
    actions: list[ModelAction] = Field(default_factory=list)
    is_final: bool = False
    
    @field_validator("assistant_text")
    @classmethod
    def text_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("assistant_text cannot be empty")
        return v
