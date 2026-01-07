"""Background job processor for LLM requests"""

import asyncio
import logging
from datetime import datetime
from typing import Optional
from uuid import UUID

from app.services.agent import Agent
from app.services.supabase_repo import SupabaseRepo
from app.services.gemini_client import GeminiClient
from app.services.r2_async import R2AsyncClient

logger = logging.getLogger(__name__)


class JobProcessor:
    """Processes queued LLM jobs in background"""

    def __init__(
        self,
        supabase_url: str,
        supabase_key: str,
        gemini_api_key: str,
        r2_public_base_url: str,
        r2_endpoint: str,
        r2_bucket: str,
        r2_access_key: str,
        r2_secret_key: str,
        poll_interval: float = 1.0,
    ):
        self.supabase_repo = SupabaseRepo(supabase_url, supabase_key)
        self.gemini_client = GeminiClient(gemini_api_key)
        self.r2_client = R2AsyncClient(
            r2_public_base_url=r2_public_base_url,
            r2_endpoint=r2_endpoint,
            r2_bucket=r2_bucket,
            r2_access_key=r2_access_key,
            r2_secret_key=r2_secret_key,
        )
        self.agent = Agent(self.gemini_client)
        self.poll_interval = poll_interval
        self._running = False
        self._task: Optional[asyncio.Task] = None

    async def start(self):
        """Start the job processor"""
        self._running = True
        self._task = asyncio.create_task(self._process_loop())
        logger.info("Job processor started")

    async def stop(self):
        """Stop the job processor"""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        await self.r2_client.close()
        logger.info("Job processor stopped")

    async def _process_loop(self):
        """Main processing loop - polls for queued jobs"""
        while self._running:
            try:
                # Fetch next queued job
                job = await self.supabase_repo.claim_next_job()

                if job:
                    await self._process_job(job)
                else:
                    # No jobs, wait before checking again
                    await asyncio.sleep(self.poll_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in job processor loop: {e}", exc_info=True)
                await asyncio.sleep(5.0)  # Wait longer on error

    async def _process_job(self, job: dict):
        """Process a single job"""
        job_id = job["id"]
        logger.info(f"Processing job {job_id}")

        try:
            # Call agent
            result = await self.agent.ask_question(
                user_text=job["user_text"],
                file_refs=job.get("file_refs", []),
                model=job["model_name"],
                system_prompt=job.get("system_prompt", ""),
                thinking_level=job.get("thinking_level", "low"),
                thinking_budget=job.get("thinking_budget"),
            )

            # Save assistant message to database
            assistant_msg = await self.supabase_repo.qa_add_message(
                conversation_id=job["conversation_id"],
                role="assistant",
                content=result.assistant_text,
                meta={
                    "model": job["model_name"],
                    "thinking_level": job.get("thinking_level", "low"),
                    "actions": result.actions,
                    "is_final": result.is_final,
                    "input_tokens": result.input_tokens,
                    "output_tokens": result.output_tokens,
                    "total_tokens": result.total_tokens,
                    "latency_ms": result.latency_ms,
                    "job_id": job_id,
                },
            )

            # Job completed successfully
            await self.supabase_repo.complete_job(
                job_id=job_id,
                result_message_id=assistant_msg["id"],
                result_text=result.assistant_text,
                result_actions=result.actions,
                result_is_final=result.is_final,
            )

            # Update conversation timestamp
            await self.supabase_repo.qa_update_conversation(job["conversation_id"])

            logger.info(f"Job {job_id} completed successfully")

        except Exception as e:
            logger.error(f"Job {job_id} failed: {e}", exc_info=True)

            # Check retry count
            retry_count = job.get("retry_count", 0)
            max_retries = job.get("max_retries", 3)

            if retry_count < max_retries:
                # Requeue for retry
                await self.supabase_repo.update_job_status(
                    job_id=job_id,
                    status="queued",
                    retry_count=retry_count + 1,
                    error_message=str(e),
                )
                logger.info(f"Job {job_id} requeued for retry ({retry_count + 1}/{max_retries})")
            else:
                # Mark as failed
                await self.supabase_repo.update_job_status(
                    job_id=job_id,
                    status="failed",
                    error_message=str(e),
                    completed_at=datetime.utcnow(),
                )
                logger.error(f"Job {job_id} failed permanently after {max_retries} retries")
