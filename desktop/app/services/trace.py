"""Tracing for model calls"""
import logging
from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4
from collections import deque
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ModelTrace(BaseModel):
    """Single model call trace"""

    id: str = Field(default_factory=lambda: str(uuid4()))
    ts: datetime = Field(default_factory=datetime.utcnow)
    conversation_id: UUID
    client_id: str = "default"
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
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        from_attributes = True

    def to_db_dict(self) -> dict:
        """Convert to dictionary for database insertion"""
        return {
            "id": self.id,
            "ts": self.ts.isoformat(),
            "conversation_id": str(self.conversation_id),
            "client_id": self.client_id,
            "model": self.model,
            "thinking_level": self.thinking_level,
            "system_prompt": self.system_prompt,
            "user_text": self.user_text,
            "input_files": self.input_files,
            "response_json": self.response_json,
            "parsed_actions": self.parsed_actions,
            "latency_ms": self.latency_ms,
            "errors": self.errors,
            "is_final": self.is_final,
            "assistant_text": self.assistant_text,
            "full_thoughts": self.full_thoughts,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_db_row(cls, row: dict) -> "ModelTrace":
        """Create ModelTrace from database row"""
        ts = row["ts"]
        if isinstance(ts, str):
            ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))

        created_at = row.get("created_at", row["ts"])
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))

        conv_id = row["conversation_id"]
        if isinstance(conv_id, str):
            conv_id = UUID(conv_id)

        return cls(
            id=str(row["id"]),
            ts=ts,
            conversation_id=conv_id,
            client_id=row.get("client_id", "default"),
            model=row["model"],
            thinking_level=row["thinking_level"],
            system_prompt=row.get("system_prompt", ""),
            user_text=row["user_text"],
            input_files=row.get("input_files") or [],
            response_json=row.get("response_json"),
            parsed_actions=row.get("parsed_actions") or [],
            latency_ms=row.get("latency_ms"),
            errors=row.get("errors") or [],
            is_final=row.get("is_final", False),
            assistant_text=row.get("assistant_text", ""),
            full_thoughts=row.get("full_thoughts", ""),
            input_tokens=row.get("input_tokens"),
            output_tokens=row.get("output_tokens"),
            total_tokens=row.get("total_tokens"),
            created_at=created_at,
        )


class TraceStore:
    """Trace storage with Supabase persistence"""

    def __init__(self, maxsize: int = 200, supabase_repo=None, client_id: str = "default"):
        self.maxsize = maxsize
        self._traces: deque[ModelTrace] = deque(maxlen=maxsize)
        self.supabase_repo = supabase_repo
        self.client_id = client_id
        self._loaded_from_db = False

    def add(self, trace: ModelTrace):
        """Add trace to store and persist to Supabase"""
        # Ensure client_id is set
        if not trace.client_id or trace.client_id == "default":
            trace.client_id = self.client_id

        self._traces.append(trace)

        # Persist to Supabase asynchronously
        if self.supabase_repo:
            import asyncio

            asyncio.create_task(self._save_to_db(trace))

    async def _save_to_db(self, trace: ModelTrace):
        """Save single trace to Supabase"""
        if not self.supabase_repo:
            return
        try:
            await self.supabase_repo.qa_add_trace(trace)
            logger.debug(f"Trace saved to DB: {trace.id}")
        except Exception as e:
            logger.error(f"Failed to save trace to DB: {e}")

    async def load_from_db(self, limit: int = 200):
        """Load traces from Supabase on startup"""
        if not self.supabase_repo or self._loaded_from_db:
            return

        try:
            traces = await self.supabase_repo.qa_list_traces(
                client_id=self.client_id, limit=limit
            )
            # Clear and reload (traces come newest first, we want oldest first in deque)
            self._traces.clear()
            for trace in reversed(traces):
                self._traces.append(trace)
            self._loaded_from_db = True
            logger.info(f"Loaded {len(traces)} traces from DB")
        except Exception as e:
            logger.error(f"Failed to load traces from DB: {e}")

    async def load_for_conversation(self, conversation_id: str) -> list[ModelTrace]:
        """Load traces for specific conversation"""
        if not self.supabase_repo:
            # Return from memory if no DB
            return [t for t in self._traces if str(t.conversation_id) == conversation_id]

        try:
            return await self.supabase_repo.qa_list_traces_by_conversation(conversation_id)
        except Exception as e:
            logger.error(f"Failed to load traces for conversation: {e}")
            return []

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
        """Clear in-memory traces only (DB traces preserved)"""
        self._traces.clear()

    def count(self) -> int:
        """Get trace count"""
        return len(self._traces)
