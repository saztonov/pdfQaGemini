"""Redis queue service using arq"""

import logging
from typing import Optional

from arq import ArqRedis, create_pool
from arq.connections import RedisSettings

from app.config import settings

logger = logging.getLogger(__name__)


class RedisQueue:
    """arq queue wrapper for job enqueuing"""

    def __init__(self):
        self._pool: Optional[ArqRedis] = None

    async def connect(self) -> None:
        """Initialize connection pool"""
        self._pool = await create_pool(
            RedisSettings(
                host=settings.redis_host,
                port=settings.redis_port,
                password=settings.redis_password or None,
                database=settings.redis_db,
            )
        )
        logger.info(f"Redis connected: {settings.redis_host}:{settings.redis_port}")

    async def close(self) -> None:
        """Close connection pool"""
        if self._pool:
            await self._pool.close()
            logger.info("Redis connection closed")

    async def enqueue_llm_job(
        self,
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
    ) -> str:
        """Enqueue LLM processing job"""
        if not self._pool:
            raise RuntimeError("Redis not connected")

        job = await self._pool.enqueue_job(
            "process_llm_job",
            job_id=job_id,
            conversation_id=conversation_id,
            user_text=user_text,
            model_name=model_name,
            system_prompt=system_prompt,
            user_text_template=user_text_template,
            thinking_level=thinking_level,
            thinking_budget=thinking_budget,
            file_refs=file_refs or [],
            context_catalog=context_catalog,
            _job_id=job_id,
            _queue_name="arq:llm_jobs",
        )
        logger.info(f"Job {job_id} enqueued to Redis")
        return job.job_id


_redis_queue: Optional[RedisQueue] = None


def init_redis_queue() -> RedisQueue:
    """Initialize global Redis queue (called once at startup)"""
    global _redis_queue
    _redis_queue = RedisQueue()
    return _redis_queue


def get_redis_queue() -> RedisQueue:
    """Get global Redis queue"""
    if _redis_queue is None:
        raise RuntimeError("Redis queue not initialized")
    return _redis_queue
