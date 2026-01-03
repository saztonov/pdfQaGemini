"""Tracing for model calls"""
from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4
from collections import deque
from pydantic import BaseModel, Field


class ModelTrace(BaseModel):
    """Single model call trace"""

    id: str = Field(default_factory=lambda: str(uuid4()))
    ts: datetime = Field(default_factory=datetime.utcnow)
    conversation_id: UUID
    model: str
    thinking_level: str
    system_prompt: str
    user_text: str
    input_files: list[dict] = Field(default_factory=list)  # {name, uri, mime_type}
    response_json: Optional[dict] = None
    parsed_actions: list[dict] = Field(default_factory=list)
    latency_ms: Optional[float] = None
    errors: list[str] = Field(default_factory=list)
    is_final: bool = False
    # Full response data (no truncation)
    assistant_text: str = ""
    full_thoughts: str = ""

    class Config:
        from_attributes = True


class TraceStore:
    """In-memory trace storage"""

    def __init__(self, maxsize: int = 200):
        self.maxsize = maxsize
        self._traces: deque[ModelTrace] = deque(maxlen=maxsize)

    def add(self, trace: ModelTrace):
        """Add trace to store"""
        self._traces.append(trace)

    def list(self) -> list[ModelTrace]:
        """List all traces (newest first)"""
        return list(reversed(self._traces))

    def get(self, trace_id: str) -> Optional[ModelTrace]:
        """Get trace by ID"""
        for trace in self._traces:
            if trace.id == trace_id:
                return trace
        return None

    def clear(self):
        """Clear all traces"""
        self._traces.clear()

    def count(self) -> int:
        """Get trace count"""
        return len(self._traces)
