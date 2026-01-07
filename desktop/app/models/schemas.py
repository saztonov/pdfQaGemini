"""Pydantic schemas"""
from datetime import datetime
from enum import Enum
from typing import Optional, Any, Literal
from uuid import UUID
from pydantic import BaseModel, Field, field_validator


# ========== Gemini Models ==========
AVAILABLE_MODELS = [
    {
        "name": "gemini-3-flash-preview",
        "display_name": "Flash",
        "thinking_levels": ["low", "medium", "high"],
        "default_thinking": "medium",
        "supports_thinking_budget": True,
    },
    {
        "name": "gemini-3-pro-preview",
        "display_name": "Pro",
        "thinking_levels": ["low", "high"],
        "default_thinking": "high",
        "supports_thinking_budget": True,
    },
]

# Thinking budget presets
THINKING_BUDGET_PRESETS = {
    "low": 512,  # Быстрое рассуждение
    "medium": 2048,  # Средняя глубина
    "high": 8192,  # Глубокое рассуждение
    "max": 16384,  # Максимальная глубина
}

# Модель по умолчанию
DEFAULT_MODEL = "gemini-3-flash-preview"

# Модель -> допустимые thinking levels
MODEL_THINKING_LEVELS: dict[str, list[str]] = {
    m["name"]: m["thinking_levels"] for m in AVAILABLE_MODELS
}

# Модель -> thinking level по умолчанию
MODEL_DEFAULT_THINKING: dict[str, str] = {
    m["name"]: m["default_thinking"] for m in AVAILABLE_MODELS
}


class FileType(str, Enum):
    """Типы файлов в node_files"""

    PDF = "pdf"  # Исходный PDF
    ANNOTATION = "annotation"  # Разметка блоков ({name}_annotation.json)
    OCR_HTML = "ocr_html"  # HTML результат ({name}_ocr.html)
    RESULT_JSON = "result_json"  # Полный результат ({name}_result.json)
    RESULT_MD = "result_md"  # Markdown результат ({name}_document.md)
    CROP = "crop"  # Кропы изображений (в папке crops/)


# Иконки для типов файлов
FILE_TYPE_ICONS = {
    FileType.PDF: "📄",
    FileType.ANNOTATION: "📋",
    FileType.OCR_HTML: "📝",
    FileType.RESULT_JSON: "📊",
    FileType.RESULT_MD: "📝",
    FileType.CROP: "🖼️",
}

# Цвета для типов файлов
FILE_TYPE_COLORS = {
    FileType.PDF: "#FFFFFF",
    FileType.ANNOTATION: "#FF69B4",
    FileType.OCR_HTML: "#FFD700",
    FileType.RESULT_JSON: "#32CD32",
    FileType.RESULT_MD: "#87CEEB",
    FileType.CROP: "#9370DB",
}


# Tree entities
class TreeNode(BaseModel):
    id: UUID
    parent_id: Optional[UUID] = None
    client_id: str = "default"  # Made optional with default
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


# Model outputs - Payload models


class RequestFilesItem(BaseModel):
    """Single item in request_files payload"""
    context_item_id: str
    kind: Literal["crop", "text"]
    reason: str
    priority: Optional[Literal["high", "medium", "low"]] = "medium"
    crop_id: Optional[str] = None


class RequestFilesPayload(BaseModel):
    """Payload for request_files action"""
    items: list[RequestFilesItem] = Field(default_factory=list, min_length=0, max_length=5)


class OpenImagePayload(BaseModel):
    """Payload for open_image action"""
    context_item_id: str
    purpose: Optional[str] = None


class ImageRef(BaseModel):
    """Reference to an image for ROI"""
    context_item_id: str


class SuggestedBboxNorm(BaseModel):
    """Normalized bounding box coordinates"""
    x1: float = Field(ge=0.0, le=1.0)
    y1: float = Field(ge=0.0, le=1.0)
    x2: float = Field(ge=0.0, le=1.0)
    y2: float = Field(ge=0.0, le=1.0)


class RequestRoiPayload(BaseModel):
    """Payload for request_roi action"""
    image_ref: ImageRef
    goal: str
    dpi: Optional[int] = Field(default=400, ge=120, le=800)
    suggested_bbox_norm: Optional[SuggestedBboxNorm] = None


class FinalPayload(BaseModel):
    """Payload for final action"""
    confidence: Literal["low", "medium", "high"]
    used_context_item_ids: list[str] = Field(default_factory=list)


class ModelAction(BaseModel):
    """Model action with typed payload"""
    
    type: Literal["request_files", "open_image", "request_roi", "final"]
    payload: Optional[dict] = None  # Parsed to specific payload type based on type
    note: Optional[str] = None

    def get_request_files_payload(self) -> Optional[RequestFilesPayload]:
        """Parse payload as RequestFilesPayload"""
        if self.type != "request_files" or self.payload is None:
            return None
        try:
            return RequestFilesPayload.model_validate(self.payload)
        except Exception:
            return None

    def get_open_image_payload(self) -> Optional[OpenImagePayload]:
        """Parse payload as OpenImagePayload"""
        if self.type != "open_image" or self.payload is None:
            return None
        try:
            return OpenImagePayload.model_validate(self.payload)
        except Exception:
            return None

    def get_request_roi_payload(self) -> Optional[RequestRoiPayload]:
        """Parse payload as RequestRoiPayload"""
        if self.type != "request_roi" or self.payload is None:
            return None
        try:
            return RequestRoiPayload.model_validate(self.payload)
        except Exception:
            return None

    def get_final_payload(self) -> Optional[FinalPayload]:
        """Parse payload as FinalPayload"""
        if self.type != "final" or self.payload is None:
            return None
        try:
            return FinalPayload.model_validate(self.payload)
        except Exception:
            return None


class ModelReply(BaseModel):
    assistant_text: str
    actions: list[ModelAction] = Field(default_factory=list)
    is_final: bool = False

    @field_validator("assistant_text", mode="before")
    @classmethod
    def text_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            return "Ответ пустой"
        return v
