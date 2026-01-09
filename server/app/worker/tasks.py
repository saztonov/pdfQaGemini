"""arq task definitions for LLM processing with agentic loop.

Reference documentation:
- Gemini SDK: https://googleapis.github.io/python-genai/
- R2 S3 API: https://developers.cloudflare.com/r2/api/s3/api/
"""

import logging
from datetime import datetime
from typing import Optional

from app.services.supabase_repo import SupabaseRepo
from app.services.gemini_client import GeminiClient
from app.services.r2_async import R2AsyncClient
from app.services.agent import Agent, build_user_prompt
from app.services.agentic_processor import AgenticProcessor, AgenticContext
from app.config import settings

logger = logging.getLogger(__name__)


async def process_llm_job(
    ctx: dict,
    job_id: str,
    conversation_id: str,
    user_text: str,
    model_name: str,
    system_prompt: str = "",
    user_text_template: str = "",
    thinking_level: str = "low",
    thinking_budget: Optional[int] = None,
    file_refs: Optional[list[dict]] = None,
    context_catalog: str = "",
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

        # Check if agentic loop is available (requires R2 client and context_catalog)
        agentic_processor: Optional[AgenticProcessor] = ctx.get("agentic_processor")

        if agentic_processor and context_catalog:
            # Use agentic loop for full processing
            logger.info("Using agentic loop with context_catalog")

            agentic_ctx = AgenticContext(
                conversation_id=conversation_id,
                user_text=user_text,
                system_prompt=system_prompt,
                user_text_template=user_text_template,
                model_name=model_name,
                thinking_level=thinking_level,
                thinking_budget=thinking_budget,
                file_refs=file_refs or [],
                context_catalog=context_catalog,
                history=history_simple,
            )

            loop_result = await agentic_processor.run_agentic_loop(agentic_ctx)

            assistant_msg = await repo.qa_add_message(
                conversation_id=conversation_id,
                role="assistant",
                content=loop_result.assistant_text,
                meta={
                    "model": model_name,
                    "thinking_level": thinking_level,
                    "actions": loop_result.actions,
                    "is_final": loop_result.is_final,
                    "input_tokens": loop_result.total_input_tokens,
                    "output_tokens": loop_result.total_output_tokens,
                    "total_tokens": loop_result.total_tokens,
                    "latency_ms": loop_result.latency_ms,
                    "job_id": job_id,
                    "iterations": loop_result.iterations,
                    "files_loaded": loop_result.files_loaded,
                },
            )

            await repo.complete_job(
                job_id=job_id,
                result_message_id=assistant_msg["id"],
                result_text=loop_result.assistant_text,
                result_actions=loop_result.actions,
                result_is_final=loop_result.is_final,
            )

        else:
            # Fallback: single call without agentic loop
            logger.info("Using single-shot mode (no agentic loop)")

            agent: Agent = ctx["agent"]

            # Format user prompt with context_catalog if provided
            formatted_user_text = user_text
            if context_catalog:
                formatted_user_text = build_user_prompt(
                    question=user_text,
                    context_catalog_json=context_catalog,
                    user_text_template=user_text_template,
                )

            result = await agent.ask_question(
                user_text=formatted_user_text,
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
            "is_final": assistant_msg.get("meta", {}).get("is_final", True),
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
    """Worker startup - initialize services including agentic processor"""
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
    ctx["gemini_client"] = gemini_client

    agent = Agent(gemini_client)
    ctx["agent"] = agent

    # Load R2 settings and initialize R2 client for agentic loop
    r2_public_url = await repo.get_setting("r2_public_url", "")
    r2_account_id = await repo.get_setting("r2_account_id", "")
    r2_access_key_id = await repo.get_setting("r2_access_key_id", "")
    r2_secret_access_key = await repo.get_setting("r2_secret_access_key", "")
    r2_bucket_name = await repo.get_setting("r2_bucket_name", "")

    if r2_public_url and r2_account_id and r2_access_key_id and r2_bucket_name:
        r2_endpoint = f"https://{r2_account_id}.r2.cloudflarestorage.com"

        r2_client = R2AsyncClient(
            r2_public_base_url=r2_public_url,
            r2_endpoint=r2_endpoint,
            r2_bucket=r2_bucket_name,
            r2_access_key=r2_access_key_id,
            r2_secret_key=r2_secret_access_key,
        )
        ctx["r2_client"] = r2_client

        # Create agentic processor
        agentic_processor = AgenticProcessor(
            gemini_client=gemini_client,
            r2_client=r2_client,
            agent=agent,
        )
        ctx["agentic_processor"] = agentic_processor

        logger.info("Agentic processor initialized with R2 client")
    else:
        logger.warning(
            "R2 settings not configured - agentic loop will not be available. "
            "Missing: r2_public_url, r2_account_id, r2_access_key_id, or r2_bucket_name"
        )

    logger.info("arq worker started")


async def shutdown(ctx: dict) -> None:
    """Worker shutdown - cleanup resources"""
    logger.info("arq worker shutting down...")

    # Close R2 client if initialized
    r2_client = ctx.get("r2_client")
    if r2_client:
        await r2_client.close()
        logger.info("R2 client closed")

    logger.info("arq worker stopped")
