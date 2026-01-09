"""Job operations for Supabase repository (server-specific)"""

import asyncio
from typing import Optional
from datetime import datetime
from uuid import uuid4


class JobOpsMixin:
    """Mixin for job queue operations (server-specific)"""

    async def create_job(
        self,
        conversation_id: str,
        client_id: str,
        user_text: str,
        model_name: str,
        system_prompt: str = "",
        user_text_template: str = "",
        thinking_level: str = "low",
        thinking_budget: Optional[int] = None,
        file_refs: Optional[list[dict]] = None,
    ) -> dict:
        """Create new LLM job"""

        def _sync_create():
            client = self._get_client()
            now = datetime.utcnow().isoformat()
            job_id = str(uuid4())
            data = {
                "id": job_id,
                "conversation_id": conversation_id,
                "client_id": client_id,
                "user_text": user_text,
                "system_prompt": system_prompt,
                "user_text_template": user_text_template,
                "model_name": model_name,
                "thinking_level": thinking_level,
                "thinking_budget": thinking_budget,
                "file_refs": file_refs or [],
                "status": "queued",
                "created_at": now,
                "updated_at": now,
            }
            response = client.table("qa_jobs").insert(data).execute()
            return response.data[0]

        return await asyncio.to_thread(_sync_create)

    async def claim_next_job(self) -> Optional[dict]:
        """Atomically claim next queued job for processing"""

        def _sync_claim():
            client = self._get_client()
            now = datetime.utcnow().isoformat()

            # Find oldest queued job and update to processing atomically
            # Note: This is a simplified version - for high concurrency you'd use
            # a proper queue system or PostgreSQL advisory locks

            # First get the oldest queued job
            response = (
                client.table("qa_jobs")
                .select("*")
                .eq("status", "queued")
                .order("created_at")
                .limit(1)
                .execute()
            )

            if not response.data:
                return None

            job = response.data[0]
            job_id = job["id"]

            # Try to claim it by updating status
            # In production, you'd want to use a transaction or RPC
            update_response = (
                client.table("qa_jobs")
                .update({"status": "processing", "started_at": now, "updated_at": now})
                .eq("id", job_id)
                .eq("status", "queued")  # Only if still queued
                .execute()
            )

            if update_response.data:
                return update_response.data[0]
            return None

        return await asyncio.to_thread(_sync_claim)

    async def update_job_status(
        self,
        job_id: str,
        status: str,
        error_message: Optional[str] = None,
        retry_count: Optional[int] = None,
        started_at: Optional[datetime] = None,
        completed_at: Optional[datetime] = None,
    ) -> dict:
        """Update job status"""

        def _sync_update():
            client = self._get_client()
            data = {
                "status": status,
                "updated_at": datetime.utcnow().isoformat(),
            }

            if error_message is not None:
                data["error_message"] = error_message
            if retry_count is not None:
                data["retry_count"] = retry_count
            if started_at is not None:
                data["started_at"] = started_at.isoformat()
            if completed_at is not None:
                data["completed_at"] = completed_at.isoformat()

            response = client.table("qa_jobs").update(data).eq("id", job_id).execute()
            return response.data[0]

        return await asyncio.to_thread(_sync_update)

    async def complete_job(
        self,
        job_id: str,
        result_message_id: str,
        result_text: str,
        result_actions: list[dict],
        result_is_final: bool,
    ) -> dict:
        """Mark job as completed with results"""

        def _sync_complete():
            client = self._get_client()
            now = datetime.utcnow().isoformat()
            data = {
                "status": "completed",
                "result_message_id": result_message_id,
                "result_text": result_text,
                "result_actions": result_actions,
                "result_is_final": result_is_final,
                "completed_at": now,
                "updated_at": now,
            }
            response = client.table("qa_jobs").update(data).eq("id", job_id).execute()
            return response.data[0]

        return await asyncio.to_thread(_sync_complete)

    async def get_job(self, job_id: str) -> Optional[dict]:
        """Get job by ID"""

        def _sync_get():
            client = self._get_client()
            response = client.table("qa_jobs").select("*").eq("id", job_id).limit(1).execute()
            return response.data[0] if response.data else None

        return await asyncio.to_thread(_sync_get)

    async def list_jobs(
        self,
        conversation_id: Optional[str] = None,
        client_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> list[dict]:
        """List jobs with optional filters"""

        def _sync_list():
            client = self._get_client()
            query = client.table("qa_jobs").select("*")

            if conversation_id:
                query = query.eq("conversation_id", conversation_id)
            if client_id:
                query = query.eq("client_id", client_id)
            if status:
                query = query.eq("status", status)

            response = query.order("created_at", desc=True).limit(limit).execute()
            return response.data

        return await asyncio.to_thread(_sync_list)
