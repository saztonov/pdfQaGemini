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
    # Token usage
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    total_tokens: Optional[int] = None

    class Config:
        from_attributes = True


class TraceStore:
    """In-memory trace storage with R2 backup"""

    def __init__(self, maxsize: int = 200, r2_client=None, client_id: str = "default"):
        self.maxsize = maxsize
        self._traces: deque[ModelTrace] = deque(maxlen=maxsize)
        self.r2_client = r2_client
        self.client_id = client_id
        self._save_counter = 0
        self._save_interval = 10  # Save to R2 every 10 traces

    def add(self, trace: ModelTrace):
        """Add trace to store and auto-save to R2"""
        self._traces.append(trace)
        
        # Auto-save to R2 periodically
        self._save_counter += 1
        if self.r2_client and self._save_counter >= self._save_interval:
            self._save_counter = 0
            import asyncio
            asyncio.create_task(self._save_to_r2())

    async def _save_to_r2(self):
        """Save traces to R2"""
        if not self.r2_client:
            return
        try:
            traces = self.list()
            if traces:
                await self.r2_client.save_trace_history(self.client_id, traces)
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to auto-save traces to R2: {e}")

    async def save_to_r2(self):
        """Manually save traces to R2"""
        await self._save_to_r2()

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
