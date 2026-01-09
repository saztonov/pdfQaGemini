"""Agent logic - orchestrates Gemini interactions"""

import sys
from pathlib import Path
import logging
from typing import Optional, AsyncIterator
from uuid import UUID
import time

# Add project root to path for shared imports
_project_root = Path(__file__).resolve().parents[3]
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from pydantic import ValidationError
from app.services.gemini_client import GeminiClient
from app.services.supabase_repo import SupabaseRepo
from app.services.trace import TraceStore, ModelTrace
from app.models.schemas import ModelReply, ModelAction
from app.ui.settings_dialog import SettingsDialog

# Import from shared
from shared.agent_core import (
    DEFAULT_SYSTEM_PROMPT,
    USER_TEXT_TEMPLATE,
    build_user_prompt,
    MODEL_REPLY_SCHEMA_STRICT,
    MODEL_REPLY_SCHEMA_SIMPLE,
)

logger = logging.getLogger(__name__)

# Re-export for backward compatibility
__all__ = [
    "DEFAULT_SYSTEM_PROMPT",
    "USER_TEXT_TEMPLATE",
    "build_user_prompt",
    "MODEL_REPLY_SCHEMA_STRICT",
    "MODEL_REPLY_SCHEMA_SIMPLE",
    "Agent",
]


class Agent:
    """Main agent orchestrator for Q&A"""

    def __init__(
        self,
        gemini_client: GeminiClient,
        supabase_repo: SupabaseRepo,
        trace_store: Optional[TraceStore] = None,
    ):
        self.gemini_client = gemini_client
        self.supabase_repo = supabase_repo
        self.trace_store = trace_store

    async def ask_question(
        self,
        conversation_id: UUID,
        user_text: str,
        file_refs: list[dict],
        model: str,
        system_prompt: str = "",
        thinking_level: str = "low",
        thinking_budget: Optional[int] = None,
        media_resolution: Optional[str] = None,
    ) -> ModelReply:
        """
        Ask question to Gemini with structured output (non-streaming).

        Args:
            conversation_id: Conversation UUID
            user_text: User question
            file_refs: List of dicts with 'uri', 'mime_type', optional 'is_roi' keys
            model: Model name (required)
            system_prompt: System prompt from user settings (from Prompts dialog)
            thinking_level: "low", "medium", or "high"
            thinking_budget: Optional max thinking tokens
            media_resolution: Override resolution ("low", "medium", "high")

        Returns:
            ModelReply with assistant text and actions
        """
        # Auto-detect: if any file has is_roi=True, use HIGH resolution
        has_roi = any(fr.get("is_roi", False) for fr in file_refs)
        effective_resolution = media_resolution or ("high" if has_roi else "low")

        # Use provided system_prompt or default
        effective_system_prompt = system_prompt or DEFAULT_SYSTEM_PROMPT

        logger.info("=== Agent.ask_question ===")
        logger.info(f"  model: {model}")
        logger.info(f"  system_prompt: {len(effective_system_prompt)} chars")
        logger.info(f"  thinking_level: {thinking_level}")
        logger.info(f"  thinking_budget: {thinking_budget}")
        logger.info(f"  file_refs count: {len(file_refs)}, has_roi: {has_roi}")
        logger.info(f"  media_resolution: {effective_resolution}")
        for i, fr in enumerate(file_refs[:3]):
            logger.info(
                f"    [{i}] uri={fr.get('uri')}, mime={fr.get('mime_type')}, is_roi={fr.get('is_roi', False)}"
            )

        start_time = time.perf_counter()
        raw_response = None
        parsed_actions = []
        used_simple_schema = False

        # Load conversation history BEFORE saving new message
        # Get max_history_pairs from server config (loaded from Supabase via server)
        server_config = SettingsDialog.get_server_config()
        max_history_pairs = int(server_config.get("max_history_pairs", 5))

        all_messages = await self.load_conversation_history(conversation_id)
        # Filter only user/assistant messages and take last N pairs
        history_filtered = [
            m for m in all_messages if m["role"] in ("user", "assistant")
        ]
        history = history_filtered[-(max_history_pairs * 2):] if max_history_pairs > 0 else []
        # Simplify format for API
        history_simple = [
            {"role": msg["role"], "content": msg["content"]} for msg in history
        ]
        logger.info(f"  history: {len(history_simple)} messages loaded (max_pairs={max_history_pairs})")

        # Create trace with all inputs
        trace = ModelTrace(
            conversation_id=conversation_id,
            model=model,
            thinking_level=thinking_level,
            system_prompt=effective_system_prompt,
            user_text=user_text,
            input_files=file_refs,
        )

        try:
            # Save user message
            await self.supabase_repo.qa_add_message(
                conversation_id=str(conversation_id),
                role="user",
                content=user_text,
                meta={
                    "file_refs": file_refs,
                    "model": model,
                },
            )

            # Try STRICT schema first, fallback to SIMPLE
            try:
                raw_response = await self.gemini_client.generate_structured(
                    model=model,
                    system_prompt=effective_system_prompt,
                    user_text=user_text,
                    file_refs=file_refs,
                    schema=MODEL_REPLY_SCHEMA_STRICT,
                    history=history_simple,
                    thinking_level=thinking_level,
                    thinking_budget=thinking_budget,
                    media_resolution=effective_resolution,
                )
            except Exception as strict_err:
                logger.warning(f"STRICT schema failed, trying SIMPLE: {strict_err}")
                used_simple_schema = True
                raw_response = await self.gemini_client.generate_structured(
                    model=model,
                    system_prompt=effective_system_prompt,
                    user_text=user_text,
                    file_refs=file_refs,
                    schema=MODEL_REPLY_SCHEMA_SIMPLE,
                    history=history_simple,
                    thinking_level=thinking_level,
                    thinking_budget=thinking_budget,
                    media_resolution=effective_resolution,
                )

            # Calculate latency
            latency_ms = (time.perf_counter() - start_time) * 1000

            # Extract usage metadata
            usage = raw_response.pop("_usage", {})

            # Validate and parse to ModelReply
            try:
                reply = ModelReply.model_validate(raw_response)
            except ValidationError as val_err:
                logger.error(f"Pydantic validation failed: {val_err}")
                # Return fallback reply asking for files
                reply = ModelReply(
                    assistant_text="Не удалось разобрать ответ модели. Попробуйте переформулировать вопрос.",
                    actions=[
                        ModelAction(
                            type="request_files",
                            payload={"items": []},
                            note="Ошибка валидации ответа",
                        )
                    ],
                    is_final=False,
                )
                trace.errors.append(f"Validation error: {val_err}")

            # Build parsed actions for trace
            parsed_actions = []
            for action in reply.actions:
                action_dict = {"type": action.type}
                if action.payload is not None:
                    action_dict["payload"] = action.payload
                if action.note is not None:
                    action_dict["note"] = action.note
                parsed_actions.append(action_dict)

            # Update trace with all outputs
            trace.response_json = raw_response
            trace.parsed_actions = parsed_actions
            trace.latency_ms = latency_ms
            trace.is_final = reply.is_final
            trace.assistant_text = reply.assistant_text
            trace.input_tokens = usage.get("input_tokens")
            trace.output_tokens = usage.get("output_tokens")
            trace.total_tokens = usage.get("total_tokens")

            # Save assistant message
            await self.supabase_repo.qa_add_message(
                conversation_id=str(conversation_id),
                role="assistant",
                content=reply.assistant_text,
                meta={
                    "model": model,
                    "thinking_level": thinking_level,
                    "file_refs": file_refs,
                    "actions": parsed_actions,
                    "is_final": reply.is_final,
                    "trace_id": trace.id,
                    "used_simple_schema": used_simple_schema,
                    "input_tokens": usage.get("input_tokens"),
                    "output_tokens": usage.get("output_tokens"),
                    "total_tokens": usage.get("total_tokens"),
                },
            )

            # Store trace
            if self.trace_store:
                self.trace_store.add(trace)

            return reply

        except Exception as e:
            # Record error with raw_response if available
            trace.errors.append(str(e))
            trace.latency_ms = (time.perf_counter() - start_time) * 1000
            if raw_response:
                trace.response_json = raw_response
            trace.parsed_actions = parsed_actions

            if self.trace_store:
                self.trace_store.add(trace)

            raise

    async def load_conversation_history(self, conversation_id: UUID) -> list[dict]:
        """Load conversation message history"""
        messages = await self.supabase_repo.qa_list_messages(str(conversation_id))

        return [
            {
                "id": str(msg.id),
                "role": msg.role,
                "content": msg.content,
                "meta": msg.meta,
                "created_at": msg.created_at,
            }
            for msg in messages
        ]

    async def ask_stream(
        self,
        conversation_id: UUID,
        user_text: str,
        file_refs: list[dict],
        model: str,
        thinking_level: str = "medium",
        thinking_budget: Optional[int] = None,
        system_prompt: str = "",
    ) -> AsyncIterator[dict]:
        """
        Ask question with streaming response including thoughts.

        Yields dicts with:
            - type: "thought" | "text" | "done" | "error"
            - content: str

        Args:
            conversation_id: Conversation UUID
            user_text: User question
            file_refs: List of dicts with 'uri' and 'mime_type'
            model: Model name
            thinking_level: "low", "medium", or "high"
            thinking_budget: Optional max thinking tokens
            system_prompt: System prompt from user settings
        """
        logger.info("=== Agent.ask_stream ===")
        logger.info(f"  model: {model}, thinking: {thinking_level}, budget: {thinking_budget}")
        logger.info(f"  file_refs count: {len(file_refs)}")
        logger.info(f"  system_prompt: {len(system_prompt)} chars")

        # Create trace with all inputs
        trace = ModelTrace(
            conversation_id=conversation_id,
            model=model,
            thinking_level=thinking_level,
            system_prompt=system_prompt,
            user_text=user_text,
            input_files=file_refs,
        )

        start_time = time.perf_counter()

        # Save user message
        await self.supabase_repo.qa_add_message(
            conversation_id=str(conversation_id),
            role="user",
            content=user_text,
            meta={
                "file_refs": file_refs,
                "model": model,
                "thinking_level": thinking_level,
            },
        )

        full_thought = ""
        full_answer = ""
        usage = {}

        try:
            async for chunk in self.gemini_client.generate_stream_with_thoughts(
                model=model,
                system_prompt=system_prompt,
                user_text=user_text,
                file_refs=file_refs,
                thinking_level=thinking_level,
                thinking_budget=thinking_budget,
            ):
                chunk_type = chunk.get("type", "")
                content = chunk.get("content", "")

                if chunk_type == "thought":
                    full_thought += content
                    yield {"type": "thought", "content": content}
                elif chunk_type == "text":
                    full_answer += content
                    yield {"type": "text", "content": content}
                elif chunk_type == "usage":
                    usage = chunk.get("usage", {})

            # Calculate latency
            latency_ms = (time.perf_counter() - start_time) * 1000

            # Update trace with all outputs
            trace.response_json = {
                "assistant_text": full_answer,
                "thoughts": full_thought,
            }
            trace.parsed_actions = []
            trace.latency_ms = latency_ms
            trace.is_final = True
            trace.assistant_text = full_answer
            trace.full_thoughts = full_thought
            trace.input_tokens = usage.get("input_tokens")
            trace.output_tokens = usage.get("output_tokens")
            trace.total_tokens = usage.get("total_tokens")

            # Save assistant message
            await self.supabase_repo.qa_add_message(
                conversation_id=str(conversation_id),
                role="assistant",
                content=full_answer,
                meta={
                    "model": model,
                    "thinking_level": thinking_level,
                    "latency_ms": latency_ms,
                    "trace_id": trace.id,
                    "input_tokens": usage.get("input_tokens"),
                    "output_tokens": usage.get("output_tokens"),
                    "total_tokens": usage.get("total_tokens"),
                },
            )

            # Store trace
            if self.trace_store:
                self.trace_store.add(trace)

            yield {"type": "done", "content": full_answer}

        except Exception as e:
            # Record error
            trace.errors.append(str(e))
            trace.latency_ms = (time.perf_counter() - start_time) * 1000

            if self.trace_store:
                self.trace_store.add(trace)

            logger.error(f"ask_stream error: {e}", exc_info=True)
            yield {"type": "error", "content": str(e)}
