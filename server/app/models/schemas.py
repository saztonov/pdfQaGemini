"""API request/response schemas"""

from datetime import datetime
from typing import Optional, Literal
from uuid import UUID

from pydantic import BaseModel, Field


# === Request Schemas ===


class SendMessageRequest(BaseModel):
    """Request to send a message and create an LLM job"""

    user_text: str
    system_prompt: str = ""
    user_text_template: str = ""
    model_name: str = "gemini-2.0-flash"
    thinking_level: Literal["low", "medium", "high"] = "low"
    thinking_budget: Optional[int] = None
    file_refs: list[dict] = Field(default_factory=list)


class CreateConversationRequest(BaseModel):
    """Request to create new conversation"""

    title: str = ""


class UpdateConversationRequest(BaseModel):
    """Request to update conversation"""

    title: Optional[str] = None


class CreatePromptRequest(BaseModel):
    """Request to create new prompt"""

    title: str
    system_prompt: str = ""
    user_text: str = ""


class UpdatePromptRequest(BaseModel):
    """Request to update prompt"""

    title: Optional[str] = None
    system_prompt: Optional[str] = None
    user_text: Optional[str] = None


# === Response Schemas ===


class ConversationResponse(BaseModel):
    """Conversation response"""

    id: UUID
    client_id: str
    title: str
    created_at: datetime
    updated_at: datetime
    message_count: int = 0
    file_count: int = 0
    last_message_at: Optional[datetime] = None


class MessageResponse(BaseModel):
    """Message response"""

    id: UUID
    conversation_id: UUID
    role: Literal["user", "assistant", "system", "tool"]
    content: str
    meta: dict = Field(default_factory=dict)
    created_at: datetime


class JobResponse(BaseModel):
    """Job status response"""

    id: UUID
    conversation_id: UUID
    status: Literal["queued", "processing", "completed", "failed"]
    progress: float = 0.0
    result_text: Optional[str] = None
    result_actions: list[dict] = Field(default_factory=list)
    result_is_final: bool = False
    error_message: Optional[str] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class SendMessageResponse(BaseModel):
    """Response after sending message - includes job ID for tracking"""

    user_message: MessageResponse
    job: JobResponse


class GeminiFileResponse(BaseModel):
    """Gemini file info response"""

    id: Optional[UUID] = None
    gemini_name: str
    gemini_uri: str
    display_name: Optional[str] = None
    mime_type: str
    size_bytes: Optional[int] = None
    token_count: Optional[int] = None  # Token count from tiktoken
    expiration_time: Optional[str] = None  # ISO format datetime


class PromptResponse(BaseModel):
    """Prompt response"""

    id: UUID
    client_id: str
    title: str
    system_prompt: str
    user_text: str
    created_at: datetime
    updated_at: datetime


class HealthResponse(BaseModel):
    """Health check response"""

    status: str
    version: str
    job_processor: str


class ErrorResponse(BaseModel):
    """Error response"""

    detail: str


class ClientConfigResponse(BaseModel):
    """Client configuration response - returned after token authentication"""

    client_id: str
    supabase_url: str
    supabase_key: str
    r2_public_base_url: str
    default_model: str = "gemini-2.0-flash"
