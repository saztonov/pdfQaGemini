"""Model output schemas - actions and payloads"""

from typing import Literal, Optional
from pydantic import BaseModel, Field, field_validator


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
    """Model action with typed payload - supports both nested and flat schemas"""

    type: Literal["request_files", "open_image", "request_roi", "final"]
    # Legacy nested payload
    payload: Optional[dict] = None
    # Flat schema fields (Gemini 3 compatible)
    items: Optional[list[dict]] = None  # request_files
    context_item_id: Optional[str] = None  # open_image
    purpose: Optional[str] = None  # open_image
    image_context_item_id: Optional[str] = None  # request_roi
    goal: Optional[str] = None  # request_roi
    dpi: Optional[int] = None  # request_roi
    bbox_x1: Optional[float] = None  # request_roi
    bbox_y1: Optional[float] = None  # request_roi
    bbox_x2: Optional[float] = None  # request_roi
    bbox_y2: Optional[float] = None  # request_roi
    confidence: Optional[str] = None  # final
    used_context_item_ids: Optional[list[str]] = None  # final
    note: Optional[str] = None

    def get_request_files_payload(self) -> Optional[RequestFilesPayload]:
        """Parse payload as RequestFilesPayload (supports both schemas)"""
        if self.type != "request_files":
            return None
        try:
            # Flat schema - items at top level
            if self.items is not None:
                return RequestFilesPayload(items=self.items)
            # Legacy nested schema
            if self.payload is not None:
                return RequestFilesPayload.model_validate(self.payload)
            return None
        except Exception:
            return None

    def get_open_image_payload(self) -> Optional[OpenImagePayload]:
        """Parse payload as OpenImagePayload (supports both schemas)"""
        if self.type != "open_image":
            return None
        try:
            # Flat schema - fields at top level
            if self.context_item_id is not None:
                return OpenImagePayload(
                    context_item_id=self.context_item_id,
                    purpose=self.purpose,
                )
            # Legacy nested schema
            if self.payload is not None:
                return OpenImagePayload.model_validate(self.payload)
            return None
        except Exception:
            return None

    def get_request_roi_payload(self) -> Optional[RequestRoiPayload]:
        """Parse payload as RequestRoiPayload (supports both schemas)"""
        if self.type != "request_roi":
            return None
        try:
            # Flat schema - fields at top level
            if self.image_context_item_id is not None:
                bbox = None
                if all(
                    v is not None for v in [self.bbox_x1, self.bbox_y1, self.bbox_x2, self.bbox_y2]
                ):
                    bbox = SuggestedBboxNorm(
                        x1=self.bbox_x1,
                        y1=self.bbox_y1,
                        x2=self.bbox_x2,
                        y2=self.bbox_y2,
                    )
                return RequestRoiPayload(
                    image_ref=ImageRef(context_item_id=self.image_context_item_id),
                    goal=self.goal or "",
                    dpi=self.dpi or 400,
                    suggested_bbox_norm=bbox,
                )
            # Legacy nested schema
            if self.payload is not None:
                return RequestRoiPayload.model_validate(self.payload)
            return None
        except Exception:
            return None

    def get_final_payload(self) -> Optional[FinalPayload]:
        """Parse payload as FinalPayload (supports both schemas)"""
        if self.type != "final":
            return None
        try:
            # Flat schema - fields at top level
            if self.confidence is not None:
                return FinalPayload(
                    confidence=self.confidence,
                    used_context_item_ids=self.used_context_item_ids or [],
                )
            # Legacy nested schema
            if self.payload is not None:
                return FinalPayload.model_validate(self.payload)
            return None
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
