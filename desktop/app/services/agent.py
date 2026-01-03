"""Agent logic - orchestrates Gemini interactions"""
import logging
from typing import Optional, AsyncIterator
from uuid import UUID
import time
from app.services.gemini_client import GeminiClient
from app.services.supabase_repo import SupabaseRepo
from app.services.trace import TraceStore, ModelTrace
from app.models.schemas import ModelReply

logger = logging.getLogger(__name__)


# JSON Schema for ModelReply
MODEL_REPLY_SCHEMA = {
    "type": "object",
    "properties": {
        "assistant_text": {"type": "string", "description": "Текст ответа ассистента"},
        "actions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "type": {
                        "type": "string",
                        "enum": ["request_files", "open_image", "request_roi", "final"],
                    },
                    "payload": {
                        "type": "object",
                        "description": "Данные действия",
                        "properties": {
                            # request_files payload
                            "items": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "context_item_id": {"type": "string"},
                                        "kind": {"type": "string", "enum": ["crop", "text"]},
                                        "reason": {"type": "string"},
                                        "priority": {
                                            "type": "string",
                                            "enum": ["high", "medium", "low"],
                                        },
                                    },
                                },
                            },
                            # open_image payload
                            "context_item_id": {"type": "string"},
                            "r2_key": {"type": "string"},
                            # request_roi payload
                            "image_ref": {
                                "type": "object",
                                "properties": {
                                    "context_item_id": {"type": "string"},
                                },
                            },
                            "goal": {"type": "string"},
                            "dpi": {"type": "integer"},
                            "suggested_bbox_norm": {
                                "type": "object",
                                "properties": {
                                    "x1": {"type": "number"},
                                    "y1": {"type": "number"},
                                    "x2": {"type": "number"},
                                    "y2": {"type": "number"},
                                },
                            },
                        },
                    },
                    "note": {"type": "string", "description": "Опциональная заметка"},
                },
                "required": ["type", "payload"],
            },
        },
        "is_final": {"type": "boolean", "description": "Является ли ответ финальным"},
    },
    "required": ["assistant_text", "actions", "is_final"],
}


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
            system_prompt: System prompt from user settings
            thinking_level: "low", "medium", or "high"
            thinking_budget: Optional max thinking tokens
            media_resolution: Override resolution ("low", "medium", "high")

        Returns:
            ModelReply with assistant text and actions
        """
        # Auto-detect: if any file has is_roi=True, use HIGH resolution
        has_roi = any(fr.get("is_roi", False) for fr in file_refs)
        effective_resolution = media_resolution or ("high" if has_roi else "low")

        logger.info("=== Agent.ask_question ===")
        logger.info(f"  model: {model}")
        logger.info(f"  system_prompt: {len(system_prompt)} chars")
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

        # Create trace with all inputs
        trace = ModelTrace(
            conversation_id=conversation_id,
            model=model,
            thinking_level=thinking_level,
            system_prompt=system_prompt,
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

            # Generate structured response with files
            raw_response = await self.gemini_client.generate_structured(
                model=model,
                system_prompt=system_prompt,
                user_text=user_text,
                file_refs=file_refs,
                schema=MODEL_REPLY_SCHEMA,
                thinking_level=thinking_level,
                thinking_budget=thinking_budget,
                media_resolution=effective_resolution,
            )

            # Calculate latency
            latency_ms = (time.perf_counter() - start_time) * 1000

            # Parse to ModelReply
            reply = ModelReply(**raw_response)

            # Build parsed actions
            parsed_actions = [
                {"type": action.type, "payload": action.payload, "note": action.note}
                for action in reply.actions
            ]

            # Update trace with all outputs
            trace.response_json = raw_response
            trace.parsed_actions = parsed_actions
            trace.latency_ms = latency_ms
            trace.is_final = reply.is_final
            trace.assistant_text = reply.assistant_text

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
