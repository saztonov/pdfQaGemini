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
        result = await agent.ask_question(
            user_text=user_text,
            file_refs=file_refs or [],
            model=model_name,
            system_prompt=system_prompt,
            thinking_level=thinking_level,
            thinking_budget=thinking_budget,
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

    ctx["supabase_repo"] = SupabaseRepo(
        url=settings.supabase_url,
        key=settings.supabase_key,
    )

    gemini_client = GeminiClient(api_key=settings.gemini_api_key)
    ctx["agent"] = Agent(gemini_client)

    logger.info("arq worker started")


async def shutdown(ctx: dict) -> None:
    """Worker shutdown - cleanup"""
    logger.info("arq worker shutting down...")
    logger.info("arq worker stopped")
