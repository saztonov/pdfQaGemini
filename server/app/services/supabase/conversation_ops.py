"""Conversation operations for Supabase repository (server)"""

import asyncio
import logging
from typing import Optional
from datetime import datetime
from uuid import uuid4

logger = logging.getLogger(__name__)


class ConversationOpsMixin:
    """Mixin for conversation CRUD operations"""

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

    async def qa_list_conversations(
        self, client_id: str = "default", limit: int = 50
    ) -> list[dict]:
        """List conversations with statistics"""

        def _sync_list():
            client = self._get_client()
            try:
                response = client.rpc(
                    "qa_list_conversations_with_stats",
                    {"p_client_id": client_id, "p_limit": limit},
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
