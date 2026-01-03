"""Agent logic - orchestrates Gemini interactions"""
import json
import logging
from typing import Optional, AsyncIterator
from uuid import UUID
import time
from pydantic import ValidationError
from app.services.gemini_client import GeminiClient
from app.services.supabase_repo import SupabaseRepo
from app.services.trace import TraceStore, ModelTrace
from app.models.schemas import ModelReply, ModelAction

logger = logging.getLogger(__name__)


# ========== PROMPT TEMPLATES ==========
# Эти шаблоны экспортируются для использования в UI "Управление промтами"

# Дефолтный System Prompt если пользователь не выбрал промпт
DEFAULT_SYSTEM_PROMPT = ""

# User Text шаблон для build_user_prompt (контекст + вопрос)
USER_TEXT_TEMPLATE = """Вопрос пользователя:
{question}

context_catalog (используй только эти id; если нужен кроп — запроси через request_files):
{context_catalog_json}

Требование:
- Если можно ответить по тексту — ответь сразу.
- Если нужны чертежи/размеры — запроси конкретные context_item_id кропов.
"""


def build_user_prompt(question: str, context_catalog_json: str, user_text_template: str = "") -> str:
    """Build user prompt with question and context catalog.
    
    Args:
        question: User question
        context_catalog_json: JSON string with available context items
        user_text_template: Optional custom template (from prompt settings)
    """
    if user_text_template and "{question}" in user_text_template:
        # Используем пользовательский шаблон
        return user_text_template.format(
            question=question,
            context_catalog_json=context_catalog_json,
        )
    # Дефолтный формат
    return USER_TEXT_TEMPLATE.format(
        question=question,
        context_catalog_json=context_catalog_json,
    )


# ========== JSON SCHEMAS ==========
# Строгая схема с oneOf для типизированных action
MODEL_REPLY_SCHEMA_STRICT = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "assistant_text": {"type": "string"},
        "is_final": {"type": "boolean"},
        "actions": {
            "type": "array",
            "items": {
                "oneOf": [
                    # --- request_files ---
                    {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "type": {"const": "request_files"},
                            "payload": {
                                "type": "object",
                                "additionalProperties": False,
                                "properties": {
                                    "items": {
                                        "type": "array",
                                        "minItems": 1,
                                        "maxItems": 5,
                                        "items": {
                                            "type": "object",
                                            "additionalProperties": False,
                                            "properties": {
                                                "context_item_id": {"type": "string"},
                                                "kind": {"type": "string", "enum": ["crop", "text"]},
                                                "reason": {"type": "string"},
                                                "priority": {"type": "string", "enum": ["high", "medium", "low"]},
                                                "crop_id": {"type": "string"},
                                            },
                                            "required": ["context_item_id", "kind", "reason"],
                                        },
                                    },
                                },
                                "required": ["items"],
                            },
                            "note": {"type": "string"},
                        },
                        "required": ["type", "payload"],
                    },
                    # --- open_image ---
                    {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "type": {"const": "open_image"},
                            "payload": {
                                "type": "object",
                                "additionalProperties": False,
                                "properties": {
                                    "context_item_id": {"type": "string"},
                                    "purpose": {"type": "string"},
                                },
                                "required": ["context_item_id"],
                            },
                            "note": {"type": "string"},
                        },
                        "required": ["type", "payload"],
                    },
                    # --- request_roi ---
                    {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "type": {"const": "request_roi"},
                            "payload": {
                                "type": "object",
                                "additionalProperties": False,
                                "properties": {
                                    "image_ref": {
                                        "type": "object",
                                        "additionalProperties": False,
                                        "properties": {
                                            "context_item_id": {"type": "string"},
                                        },
                                        "required": ["context_item_id"],
                                    },
                                    "goal": {"type": "string"},
                                    "dpi": {"type": "integer", "minimum": 120, "maximum": 800},
                                    "suggested_bbox_norm": {
                                        "type": "object",
                                        "additionalProperties": False,
                                        "properties": {
                                            "x1": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                                            "y1": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                                            "x2": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                                            "y2": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                                        },
                                        "required": ["x1", "y1", "x2", "y2"],
                                    },
                                },
                                "required": ["image_ref", "goal"],
                            },
                            "note": {"type": "string"},
                        },
                        "required": ["type", "payload"],
                    },
                    # --- final ---
                    {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "type": {"const": "final"},
                            "payload": {
                                "type": "object",
                                "additionalProperties": False,
                                "properties": {
                                    "confidence": {"type": "string", "enum": ["low", "medium", "high"]},
                                    "used_context_item_ids": {"type": "array", "items": {"type": "string"}},
                                },
                                "required": ["confidence", "used_context_item_ids"],
                            },
                            "note": {"type": "string"},
                        },
                        "required": ["type", "payload"],
                    },
                ],
            },
        },
    },
    "required": ["assistant_text", "actions", "is_final"],
}

# Простая схема (fallback)
MODEL_REPLY_SCHEMA_SIMPLE = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "assistant_text": {"type": "string"},
        "is_final": {"type": "boolean"},
        "actions": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "type": {"type": "string", "enum": ["request_files", "open_image", "request_roi", "final"]},
                    "payload": {"type": "object"},
                    "note": {"type": "string"},
                },
                "required": ["type", "payload"],
            },
        },
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
