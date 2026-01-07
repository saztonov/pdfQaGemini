"""Supabase repository - async data access for server"""

import asyncio
import logging
from typing import Optional
from datetime import datetime
from uuid import uuid4

from supabase import create_client, Client

logger = logging.getLogger(__name__)


class SupabaseRepo:
    """Async Supabase data access layer for server"""

    def __init__(self, url: str, key: str):
        logger.info(f"Initializing SupabaseRepo: url={url[:30]}...")
        self.url = url
        self.key = key
        self._client: Optional[Client] = None

    def _get_client(self) -> Client:
        """Lazy init Supabase client"""
        if self._client is None:
            logger.info("Creating Supabase client...")
            self._client = create_client(self.url, self.key)
            logger.info("Supabase client created")
        return self._client

    # ==================== Tree operations ====================

    async def fetch_roots(self, client_id: str = "default") -> list[dict]:
        """Fetch root tree nodes"""

        def _sync_fetch():
            client = self._get_client()
            response = (
                client.table("tree_nodes")
                .select("*")
                .is_("parent_id", "null")
                .order("sort_order")
                .order("name")
                .execute()
            )
            return response.data

        return await asyncio.to_thread(_sync_fetch)

    async def fetch_children(self, parent_id: str) -> list[dict]:
        """Fetch child nodes for given parent"""

        def _sync_fetch():
            client = self._get_client()
            response = (
                client.table("tree_nodes")
                .select("*")
                .eq("parent_id", parent_id)
                .order("sort_order")
                .order("name")
                .execute()
            )
            return response.data

        return await asyncio.to_thread(_sync_fetch)

    async def get_descendant_documents(
        self, client_id: str, root_ids: list[str], node_types: Optional[list[str]] = None
    ) -> list[dict]:
        """Get descendant nodes via RPC"""

        def _sync_fetch():
            client = self._get_client()
            params = {
                "p_client_id": client_id or "default",
                "p_root_ids": root_ids,
            }
            if node_types:
                params["p_node_types"] = node_types

            response = client.rpc("qa_get_descendants", params).execute()
            cid = client_id or "default"
            return [{**row, "client_id": cid} for row in response.data]

        return await asyncio.to_thread(_sync_fetch)

    async def fetch_node_files(self, node_ids: list[str]) -> list[dict]:
        """Fetch files for multiple nodes (chunked)"""
        if not node_ids:
            return []

        def _sync_fetch(chunk: list[str]):
            client = self._get_client()
            response = client.table("node_files").select("*").in_("node_id", chunk).execute()
            return response.data

        chunk_size = 200
        chunks = [node_ids[i : i + chunk_size] for i in range(0, len(node_ids), chunk_size)]

        tasks = [asyncio.to_thread(_sync_fetch, chunk) for chunk in chunks]
        results = await asyncio.gather(*tasks)

        all_files = []
        for result in results:
            all_files.extend(result)
        return all_files

    async def fetch_node_files_single(self, node_id: str) -> list[dict]:
        """Fetch files for single node"""

        def _sync_fetch():
            client = self._get_client()
            response = (
                client.table("node_files")
                .select("*")
                .eq("node_id", node_id)
                .order("file_type")
                .execute()
            )
            return response.data

        return await asyncio.to_thread(_sync_fetch)

    async def fetch_document_bundle_files(self, document_node_id: str) -> dict:
        """Fetch bundle files for document node"""

        def _sync_fetch():
            client = self._get_client()
            response = (
                client.table("node_files").select("*").eq("node_id", document_node_id).execute()
            )
            files = response.data

            text_types = {"ocr_html", "result_json", "pdf"}
            return {
                "text_files": [f for f in files if f.get("file_type") in text_types],
                "crop_files": [f for f in files if f.get("file_type") == "crop"],
                "annotation_files": [f for f in files if f.get("file_type") == "annotation"],
            }

        return await asyncio.to_thread(_sync_fetch)

    # ==================== QA Conversations ====================

    async def qa_create_conversation(self, client_id: str, title: str = "") -> dict:
        """Create new conversation"""

        def _sync_create():
            client = self._get_client()
            now = datetime.utcnow().isoformat()
            data = {
                "id": str(uuid4()),
                "client_id": client_id,
                "title": title,
                "created_at": now,
                "updated_at": now,
            }
            response = client.table("qa_conversations").insert(data).execute()
            return response.data[0]

        return await asyncio.to_thread(_sync_create)

    async def qa_list_conversations(self, client_id: str = "default", limit: int = 50) -> list[dict]:
        """List conversations with statistics"""

        def _sync_list():
            client = self._get_client()
            try:
                response = client.rpc(
                    "qa_list_conversations_with_stats", {"p_client_id": client_id, "p_limit": limit}
                ).execute()
                return response.data
            except Exception as e:
                logger.warning(f"RPC not available, using fallback: {e}")
                response = (
                    client.table("qa_conversations")
                    .select("*")
                    .eq("client_id", client_id)
                    .order("updated_at", desc=True)
                    .limit(limit)
                    .execute()
                )
                return [
                    {**row, "message_count": 0, "file_count": 0, "last_message_at": None}
                    for row in response.data
                ]

        return await asyncio.to_thread(_sync_list)

    async def qa_get_conversation(self, conversation_id: str) -> Optional[dict]:
        """Get conversation by ID"""

        def _sync_get():
            client = self._get_client()
            response = (
                client.table("qa_conversations")
                .select("*")
                .eq("id", conversation_id)
                .limit(1)
                .execute()
            )
            return response.data[0] if response.data else None

        return await asyncio.to_thread(_sync_get)

    async def qa_update_conversation(
        self,
        conversation_id: str,
        title: Optional[str] = None,
        model_default: Optional[str] = None,
    ) -> dict:
        """Update conversation"""

        def _sync_update():
            client = self._get_client()
            data = {"updated_at": datetime.utcnow().isoformat()}

            if title is not None:
                data["title"] = title
            if model_default is not None:
                data["model_default"] = model_default

            response = (
                client.table("qa_conversations").update(data).eq("id", conversation_id).execute()
            )
            return response.data[0]

        return await asyncio.to_thread(_sync_update)

    async def qa_delete_conversation(self, conversation_id: str) -> None:
        """Delete conversation and all related data"""

        def _sync_delete():
            client = self._get_client()

            # Delete in order due to foreign keys
            client.table("qa_jobs").delete().eq("conversation_id", conversation_id).execute()
            client.table("qa_messages").delete().eq("conversation_id", conversation_id).execute()
            client.table("qa_conversation_nodes").delete().eq(
                "conversation_id", conversation_id
            ).execute()
            client.table("qa_conversation_gemini_files").delete().eq(
                "conversation_id", conversation_id
            ).execute()
            client.table("qa_conversation_context_files").delete().eq(
                "conversation_id", conversation_id
            ).execute()
            client.table("qa_artifacts").delete().eq("conversation_id", conversation_id).execute()
            client.table("qa_conversations").delete().eq("id", conversation_id).execute()

        await asyncio.to_thread(_sync_delete)

    # ==================== QA Messages ====================

    async def qa_add_message(
        self, conversation_id: str, role: str, content: str, meta: Optional[dict] = None
    ) -> dict:
        """Add message to conversation"""

        def _sync_add():
            client = self._get_client()
            msg_id = str(uuid4())
            data = {
                "id": msg_id,
                "conversation_id": conversation_id,
                "role": role,
                "content": content,
                "meta": meta or {},
                "created_at": datetime.utcnow().isoformat(),
            }
            response = client.table("qa_messages").insert(data).execute()
            return response.data[0]

        return await asyncio.to_thread(_sync_add)

    async def qa_list_messages(self, conversation_id: str) -> list[dict]:
        """List messages in conversation"""

        def _sync_list():
            client = self._get_client()
            response = (
                client.table("qa_messages")
                .select("*")
                .eq("conversation_id", conversation_id)
                .order("created_at")
                .execute()
            )
            return response.data

        return await asyncio.to_thread(_sync_list)

    # ==================== QA Jobs ====================

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

    # ==================== Gemini Files ====================

    async def qa_upsert_gemini_file(
        self,
        gemini_name: str,
        gemini_uri: str,
        display_name: str,
        mime_type: str,
        client_id: str = "default",
        size_bytes: Optional[int] = None,
        sha256: Optional[str] = None,
        source_node_file_id: Optional[str] = None,
        source_r2_key: Optional[str] = None,
        expires_at: Optional[str] = None,
    ) -> dict:
        """Upsert Gemini File cache entry"""

        def _sync_upsert():
            client = self._get_client()
            now = datetime.utcnow().isoformat()
            data = {
                "client_id": client_id,
                "gemini_name": gemini_name,
                "gemini_uri": gemini_uri,
                "display_name": display_name,
                "mime_type": mime_type,
                "size_bytes": size_bytes,
                "sha256": sha256,
                "source_node_file_id": source_node_file_id,
                "source_r2_key": source_r2_key,
                "expires_at": expires_at,
                "updated_at": now,
            }
            response = (
                client.table("qa_gemini_files").upsert(data, on_conflict="gemini_name").execute()
            )
            return response.data[0]

        return await asyncio.to_thread(_sync_upsert)

    async def qa_attach_gemini_file(self, conversation_id: str, gemini_file_id: str) -> None:
        """Attach Gemini file to conversation"""

        def _sync_attach():
            client = self._get_client()
            data = {
                "id": str(uuid4()),
                "conversation_id": conversation_id,
                "gemini_file_id": gemini_file_id,
                "added_at": datetime.utcnow().isoformat(),
            }
            client.table("qa_conversation_gemini_files").upsert(
                data, on_conflict="conversation_id,gemini_file_id"
            ).execute()

        await asyncio.to_thread(_sync_attach)

    async def qa_get_conversation_files(self, conversation_id: str) -> list[dict]:
        """Get all Gemini files attached to conversation"""

        def _sync_get():
            client = self._get_client()
            response = (
                client.table("qa_conversation_gemini_files")
                .select("*, qa_gemini_files(*)")
                .eq("conversation_id", conversation_id)
                .execute()
            )

            files = []
            for row in response.data:
                gemini_file = row.get("qa_gemini_files")
                if gemini_file:
                    files.append(gemini_file)
            return files

        return await asyncio.to_thread(_sync_get)

    # ==================== Context Files ====================

    async def qa_save_context_file(
        self,
        conversation_id: str,
        node_file_id: str,
        gemini_name: Optional[str] = None,
        gemini_uri: Optional[str] = None,
        status: str = "local",
    ) -> dict:
        """Save context file with status"""

        def _sync_save():
            client = self._get_client()
            data = {
                "conversation_id": conversation_id,
                "node_file_id": node_file_id,
                "gemini_name": gemini_name,
                "gemini_uri": gemini_uri,
                "status": status,
                "uploaded_at": datetime.utcnow().isoformat() if status == "uploaded" else None,
            }
            response = (
                client.table("qa_conversation_context_files")
                .upsert(data, on_conflict="conversation_id,node_file_id")
                .execute()
            )
            return response.data[0]

        return await asyncio.to_thread(_sync_save)

    async def qa_load_context_files(self, conversation_id: str) -> list[dict]:
        """Load all context files for conversation"""

        def _sync_load():
            client = self._get_client()
            response = (
                client.table("qa_conversation_context_files")
                .select("*, node_files(*)")
                .eq("conversation_id", conversation_id)
                .execute()
            )
            return response.data

        return await asyncio.to_thread(_sync_load)

    # ==================== Artifacts ====================

    async def qa_add_artifact(
        self,
        conversation_id: str,
        artifact_type: str,
        r2_key: str,
        file_name: str,
        mime_type: str,
        file_size: int,
        metadata: Optional[dict] = None,
    ) -> dict:
        """Add artifact to conversation"""

        def _sync_add():
            client = self._get_client()
            data = {
                "id": str(uuid4()),
                "conversation_id": conversation_id,
                "artifact_type": artifact_type,
                "r2_key": r2_key,
                "file_name": file_name,
                "mime_type": mime_type,
                "file_size": file_size,
                "metadata": metadata or {},
                "created_at": datetime.utcnow().isoformat(),
            }
            response = client.table("qa_artifacts").insert(data).execute()
            return response.data[0]

        return await asyncio.to_thread(_sync_add)

    # ==================== User Prompts ====================

    async def prompts_list(self, client_id: str = "default") -> list[dict]:
        """List all prompts for client"""

        def _sync_list():
            client = self._get_client()
            response = (
                client.table("user_prompts")
                .select("*")
                .eq("client_id", client_id)
                .order("created_at", desc=True)
                .execute()
            )
            return response.data

        return await asyncio.to_thread(_sync_list)

    async def prompts_create(
        self,
        title: str,
        system_prompt: str,
        user_text: str,
        client_id: str = "default",
        r2_key: Optional[str] = None,
    ) -> dict:
        """Create new prompt"""

        def _sync_create():
            client = self._get_client()
            now = datetime.utcnow().isoformat()
            data = {
                "id": str(uuid4()),
                "client_id": client_id,
                "title": title,
                "system_prompt": system_prompt,
                "user_text": user_text,
                "r2_key": r2_key,
                "created_at": now,
                "updated_at": now,
            }
            response = client.table("user_prompts").insert(data).execute()
            return response.data[0]

        return await asyncio.to_thread(_sync_create)

    async def prompts_update(
        self,
        prompt_id: str,
        title: Optional[str] = None,
        system_prompt: Optional[str] = None,
        user_text: Optional[str] = None,
        r2_key: Optional[str] = None,
    ) -> dict:
        """Update prompt"""

        def _sync_update():
            client = self._get_client()
            data = {"updated_at": datetime.utcnow().isoformat()}

            if title is not None:
                data["title"] = title
            if system_prompt is not None:
                data["system_prompt"] = system_prompt
            if user_text is not None:
                data["user_text"] = user_text
            if r2_key is not None:
                data["r2_key"] = r2_key

            response = client.table("user_prompts").update(data).eq("id", prompt_id).execute()
            return response.data[0]

        return await asyncio.to_thread(_sync_update)

    async def prompts_delete(self, prompt_id: str) -> None:
        """Delete prompt"""

        def _sync_delete():
            client = self._get_client()
            client.table("user_prompts").delete().eq("id", prompt_id).execute()

        await asyncio.to_thread(_sync_delete)

    async def prompts_get(self, prompt_id: str) -> Optional[dict]:
        """Get single prompt by ID"""

        def _sync_get():
            client = self._get_client()
            response = (
                client.table("user_prompts").select("*").eq("id", prompt_id).limit(1).execute()
            )
            return response.data[0] if response.data else None

        return await asyncio.to_thread(_sync_get)

    # ==================== Settings / Auth ====================

    async def get_settings_by_token(self, api_token: str) -> Optional[dict]:
        """Get settings by API token for client authentication"""

        def _sync_get():
            client = self._get_client()
            response = (
                client.table("qa_settings")
                .select("*")
                .eq("api_token", api_token)
                .limit(1)
                .execute()
            )
            return response.data[0] if response.data else None

        return await asyncio.to_thread(_sync_get)
