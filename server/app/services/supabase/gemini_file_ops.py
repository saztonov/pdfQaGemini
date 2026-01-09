"""Gemini file operations for Supabase repository (server)"""

import asyncio
import logging
from typing import Optional
from datetime import datetime
from uuid import uuid4

logger = logging.getLogger(__name__)


class GeminiFileOpsMixin:
    """Mixin for Gemini file operations"""

    async def qa_upsert_gemini_file(
        self,
        gemini_name: str,
        gemini_uri: str,
        display_name: str,
        mime_type: str,
        client_id: str = "default",
        size_bytes: Optional[int] = None,
        token_count: Optional[int] = None,
        sha256: Optional[str] = None,
        source_node_file_id: Optional[str] = None,
        source_r2_key: Optional[str] = None,
        expires_at: Optional[str] = None,
        crop_index: Optional[list] = None,
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
                "token_count": token_count,
                "sha256": sha256,
                "source_node_file_id": source_node_file_id,
                "source_r2_key": source_r2_key,
                "expires_at": expires_at,
                "crop_index": crop_index,
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

    async def qa_delete_gemini_file_by_name(self, gemini_name: str) -> None:
        """Delete Gemini file and its links from database by gemini_name"""

        def _sync_delete():
            client = self._get_client()

            # First get the file ID
            response = (
                client.table("qa_gemini_files")
                .select("id")
                .eq("gemini_name", gemini_name)
                .limit(1)
                .execute()
            )

            if response.data:
                file_id = response.data[0]["id"]

                # Delete links from qa_conversation_gemini_files
                client.table("qa_conversation_gemini_files").delete().eq(
                    "gemini_file_id", file_id
                ).execute()

                # Delete the file record itself
                client.table("qa_gemini_files").delete().eq("id", file_id).execute()

                logger.info(f"Deleted Gemini file from DB: {gemini_name}")

        await asyncio.to_thread(_sync_delete)
