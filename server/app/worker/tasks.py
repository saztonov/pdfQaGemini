"""arq task definitions for LLM processing"""

import logging
from datetime import datetime
from typing import Optional

from app.services.supabase_repo import SupabaseRepo
from app.services.gemini_client import GeminiClient
from app.services.agent import Agent
from app.config import settings

logger = logging.getLogger(__name__)


async def process_llm_job(
    ctx: dict,
    job_id: str,
    conversation_id: str,
    user_text: str,
    model_name: str,
    system_prompt: str = "",
    thinking_level: str = "low",
    thinking_budget: Optional[int] = None,
    file_refs: Optional[list[dict]] = None,
) -> dict:
    """
    Process LLM job - called by arq worker.
    Returns dict with result or raises exception for retry.
    """
    logger.info(f"Processing job {job_id} for conversation {conversation_id}")

    repo: SupabaseRepo = ctx["supabase_repo"]
    agent: Agent = ctx["agent"]

    await repo.update_job_status(
        job_id=job_id,
        status="processing",
        started_at=datetime.utcnow(),
    )

    try:
        # Load conversation history for multi-turn context
        # Get max_history_pairs from Supabase settings
        max_history_pairs = await repo.get_setting("max_history_pairs", 5)
        all_messages = await repo.qa_list_messages(conversation_id)
        # Filter only user/assistant messages and take last N pairs
        history_filtered = [
            m for m in all_messages if m.get("role") in ("user", "assistant")
        ]
        history = history_filtered[-(max_history_pairs * 2):] if max_history_pairs > 0 else []
        # Simplify format for API
        history_simple = [
            {"role": msg["role"], "content": msg["content"]} for msg in history
        ]
        logger.info(
            f"Loaded {len(history_simple)} history messages for conversation {conversation_id} "
            f"(max_pairs={max_history_pairs})"
        )

        result = await agent.ask_question(
            user_text=user_text,
            file_refs=file_refs or [],
            model=model_name,
            system_prompt=system_prompt,
            thinking_level=thinking_level,
            thinking_budget=thinking_budget,
            history=history_simple,
        )

        assistant_msg = await repo.qa_add_message(
            conversation_id=conversation_id,
            role="assistant",
            content=result.assistant_text,
            meta={
                "model": model_name,
                "thinking_level": thinking_level,
                "actions": result.actions,
                "is_final": result.is_final,
                "input_tokens": result.input_tokens,
                "output_tokens": result.output_tokens,
                "total_tokens": result.total_tokens,
                "latency_ms": result.latency_ms,
                "job_id": job_id,
            },
        )

        await repo.complete_job(
            job_id=job_id,
            result_message_id=assistant_msg["id"],
            result_text=result.assistant_text,
            result_actions=result.actions,
            result_is_final=result.is_final,
        )

        await repo.qa_update_conversation(conversation_id)

        logger.info(f"Job {job_id} completed successfully")

        return {
            "job_id": job_id,
            "message_id": assistant_msg["id"],
            "is_final": result.is_final,
        }

    except Exception as e:
        logger.error(f"Job {job_id} failed: {e}", exc_info=True)
        await repo.update_job_status(
            job_id=job_id,
            status="failed",
            error_message=str(e),
            completed_at=datetime.utcnow(),
        )
        raise


async def startup(ctx: dict) -> None:
    """Worker startup - initialize services"""
    logger.info("arq worker starting up...")

    # Initialize Supabase repo (uses infrastructure settings from .env)
    repo = SupabaseRepo(
        url=settings.supabase_url,
        key=settings.supabase_key,
    )
    ctx["supabase_repo"] = repo

    # Load Gemini API key from Supabase settings
    gemini_api_key = await repo.get_setting("gemini_api_key", "")
    if not gemini_api_key:
        logger.warning("gemini_api_key not configured in Supabase settings!")

    gemini_client = GeminiClient(api_key=gemini_api_key)
    ctx["agent"] = Agent(gemini_client)

    logger.info("arq worker started")


async def shutdown(ctx: dict) -> None:
    """Worker shutdown - cleanup"""
    logger.info("arq worker shutting down...")
    logger.info("arq worker stopped")
