"""Agent logic - orchestrates Gemini interactions (server version)"""

import logging
import time
from typing import Optional
from dataclasses import dataclass, field

from pydantic import ValidationError, BaseModel

from app.services.gemini_client import GeminiClient

logger = logging.getLogger(__name__)


# ========== PROMPT TEMPLATES ==========


DEFAULT_SYSTEM_PROMPT = ""

USER_TEXT_TEMPLATE = """Вопрос пользователя:
{question}

context_catalog (используй только эти id; если нужен кроп — запроси через request_files):
{context_catalog_json}

Требование:
- Если можно ответить по тексту — ответь сразу.
- Если нужны чертежи/размеры — запроси конкретные context_item_id кропов.
"""


def build_user_prompt(
    question: str, context_catalog_json: str, user_text_template: str = ""
) -> str:
    """Build user prompt with question and context catalog."""
    if user_text_template and "{question}" in user_text_template:
        return user_text_template.format(
            question=question,
            context_catalog_json=context_catalog_json,
        )
    return USER_TEXT_TEMPLATE.format(
        question=question,
        context_catalog_json=context_catalog_json,
    )


# ========== JSON SCHEMAS ==========

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
                                                "kind": {
                                                    "type": "string",
                                                    "enum": ["crop", "text"],
                                                },
                                                "reason": {"type": "string"},
                                                "priority": {
                                                    "type": "string",
                                                    "enum": ["high", "medium", "low"],
                                                },
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
                                            "x1": {
                                                "type": "number",
                                                "minimum": 0.0,
                                                "maximum": 1.0,
                                            },
                                            "y1": {
                                                "type": "number",
                                                "minimum": 0.0,
                                                "maximum": 1.0,
                                            },
                                            "x2": {
                                                "type": "number",
                                                "minimum": 0.0,
                                                "maximum": 1.0,
                                            },
                                            "y2": {
                                                "type": "number",
                                                "minimum": 0.0,
                                                "maximum": 1.0,
                                            },
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
                    {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "type": {"const": "final"},
                            "payload": {
                                "type": "object",
                                "additionalProperties": False,
                                "properties": {
                                    "confidence": {
                                        "type": "string",
                                        "enum": ["low", "medium", "high"],
                                    },
                                    "used_context_item_ids": {
                                        "type": "array",
                                        "items": {"type": "string"},
                                    },
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
                    "type": {
                        "type": "string",
                        "enum": ["request_files", "open_image", "request_roi", "final"],
                    },
                    "payload": {"type": "object"},
                    "note": {"type": "string"},
                },
                "required": ["type", "payload"],
            },
        },
    },
    "required": ["assistant_text", "actions", "is_final"],
}


# ========== PYDANTIC MODELS ==========


class ModelAction(BaseModel):
    """Single model action"""

    type: str
    payload: Optional[dict] = None
    note: Optional[str] = None


class ModelReply(BaseModel):
    """Model structured reply"""

    assistant_text: str
    actions: list[ModelAction] = field(default_factory=list)
    is_final: bool = False


@dataclass
class AgentResult:
    """Result from agent.ask_question()"""

    assistant_text: str
    actions: list[dict]
    is_final: bool
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    latency_ms: Optional[float] = None


class Agent:
    """Main agent orchestrator for Q&A (server version)"""

    def __init__(self, gemini_client: GeminiClient):
        self.gemini_client = gemini_client

    async def ask_question(
        self,
        user_text: str,
        file_refs: list[dict],
        model: str,
        system_prompt: str = "",
        thinking_level: str = "low",
        thinking_budget: Optional[int] = None,
        media_resolution: Optional[str] = None,
    ) -> AgentResult:
        """
        Ask question to Gemini with structured output.

        Args:
            user_text: User question
            file_refs: List of dicts with 'uri', 'mime_type', optional 'is_roi' keys
            model: Model name
            system_prompt: System prompt
            thinking_level: "low", "medium", or "high"
            thinking_budget: Optional max thinking tokens
            media_resolution: Override resolution ("low", "medium", "high")

        Returns:
            AgentResult with assistant text, actions, and metadata
        """
        # Auto-detect: if any file has is_roi=True, use HIGH resolution
        has_roi = any(fr.get("is_roi", False) for fr in file_refs)
        effective_resolution = media_resolution or ("high" if has_roi else "low")
        effective_system_prompt = system_prompt or DEFAULT_SYSTEM_PROMPT

        logger.info("=== Agent.ask_question ===")
        logger.info(f"  model: {model}")
        logger.info(f"  thinking_level: {thinking_level}")
        logger.info(f"  file_refs count: {len(file_refs)}, has_roi: {has_roi}")
        logger.info(f"  media_resolution: {effective_resolution}")

        start_time = time.perf_counter()
        raw_response = None
        parsed_actions = []

        try:
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

            latency_ms = (time.perf_counter() - start_time) * 1000
            usage = raw_response.pop("_usage", {})

            # Validate and parse to ModelReply
            try:
                reply = ModelReply.model_validate(raw_response)
            except ValidationError as val_err:
                logger.error(f"Pydantic validation failed: {val_err}")
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

            # Build parsed actions
            for action in reply.actions:
                action_dict = {"type": action.type}
                if action.payload is not None:
                    action_dict["payload"] = action.payload
                if action.note is not None:
                    action_dict["note"] = action.note
                parsed_actions.append(action_dict)

            return AgentResult(
                assistant_text=reply.assistant_text,
                actions=parsed_actions,
                is_final=reply.is_final,
                input_tokens=usage.get("input_tokens"),
                output_tokens=usage.get("output_tokens"),
                total_tokens=usage.get("total_tokens"),
                latency_ms=latency_ms,
            )

        except Exception as e:
            logger.error(f"Agent.ask_question error: {e}", exc_info=True)
            raise
