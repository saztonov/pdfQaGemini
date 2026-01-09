"""Agent logic - orchestrates Gemini interactions (server version)"""

import sys
from pathlib import Path
import logging
import time
from typing import Optional
from dataclasses import dataclass

from pydantic import ValidationError

from app.services.gemini_client import GeminiClient

# Add project root to path for shared imports
_project_root = Path(__file__).resolve().parents[3]
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

# Import from shared
from shared.agent_core import (
    DEFAULT_SYSTEM_PROMPT,
    USER_TEXT_TEMPLATE,
    build_user_prompt,
    MODEL_REPLY_SCHEMA_STRICT,
    MODEL_REPLY_SCHEMA_SIMPLE,
)
from shared.models import ModelAction, ModelReply

logger = logging.getLogger(__name__)

# Re-export for backward compatibility
__all__ = [
    "DEFAULT_SYSTEM_PROMPT",
    "USER_TEXT_TEMPLATE",
    "build_user_prompt",
    "MODEL_REPLY_SCHEMA_STRICT",
    "MODEL_REPLY_SCHEMA_SIMPLE",
    "Agent",
    "AgentResult",
    "ModelAction",
    "ModelReply",
]


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
        history: Optional[list[dict]] = None,
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
            history: Previous messages for multi-turn context.
                     Format: [{"role": "user"|"assistant", "content": "..."}]

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
        logger.info(f"  history: {len(history) if history else 0} messages")
        logger.info(f"  user_text length: {len(user_text)}")
        # Log if context_catalog appears in user_text
        has_context_catalog = "context_catalog" in user_text.lower()
        logger.info(f"  contains 'context_catalog': {has_context_catalog}")
        if has_context_catalog:
            logger.info(f"  user_text preview (first 800 chars): {user_text[:800]}...")

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
                    history=history,
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
                    history=history,
                    thinking_level=thinking_level,
                    thinking_budget=thinking_budget,
                    media_resolution=effective_resolution,
                )

            latency_ms = (time.perf_counter() - start_time) * 1000
            usage = raw_response.pop("_usage", {})

            # Log raw response actions for debugging
            raw_actions = raw_response.get("actions", [])
            logger.info(f"  raw_response actions count: {len(raw_actions)}")
            for i, act in enumerate(raw_actions):
                logger.info(f"    action[{i}]: type={act.get('type')}, has_items={bool(act.get('items'))}, items_count={len(act.get('items', []))}")

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

            # Build parsed actions - include both legacy payload and flat schema fields
            for action in reply.actions:
                action_dict = {"type": action.type}
                # Legacy nested payload
                if action.payload is not None:
                    action_dict["payload"] = action.payload
                if action.note is not None:
                    action_dict["note"] = action.note
                # Flat schema fields for request_files
                if action.items is not None:
                    action_dict["items"] = action.items
                # Flat schema fields for open_image
                if action.context_item_id is not None:
                    action_dict["context_item_id"] = action.context_item_id
                if action.purpose is not None:
                    action_dict["purpose"] = action.purpose
                # Flat schema fields for request_roi
                if action.image_context_item_id is not None:
                    action_dict["image_context_item_id"] = action.image_context_item_id
                if action.goal is not None:
                    action_dict["goal"] = action.goal
                if action.dpi is not None:
                    action_dict["dpi"] = action.dpi
                if action.bbox_x1 is not None:
                    action_dict["bbox_x1"] = action.bbox_x1
                if action.bbox_y1 is not None:
                    action_dict["bbox_y1"] = action.bbox_y1
                if action.bbox_x2 is not None:
                    action_dict["bbox_x2"] = action.bbox_x2
                if action.bbox_y2 is not None:
                    action_dict["bbox_y2"] = action.bbox_y2
                # Flat schema fields for final
                if action.confidence is not None:
                    action_dict["confidence"] = action.confidence
                if action.used_context_item_ids is not None:
                    action_dict["used_context_item_ids"] = action.used_context_item_ids
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
