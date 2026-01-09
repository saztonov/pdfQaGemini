"""Conversation CRUD operations for Supabase repository"""

import asyncio
import logging
from typing import Optional
from datetime import datetime
from uuid import uuid4
from app.models.schemas import Conversation, ConversationWithStats

logger = logging.getLogger(__name__)


class ConversationOpsMixin:
    """Mixin for conversation CRUD operations"""

    async def qa_create_conversation(
        self,
        client_id: str,
        title: str = "",
    ) -> Conversation:
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
            return Conversation(**response.data[0])

        return await asyncio.to_thread(_sync_create)

    async def qa_add_nodes(self, conversation_id: str, node_ids: list[str]) -> None:
        """Add nodes to conversation context (upsert)"""
        if not node_ids:
            return

        def _sync_add():
            client = self._get_client()
            now = datetime.utcnow().isoformat()
            records = [
                {
                    "id": str(uuid4()),
                    "conversation_id": conversation_id,
                    "node_id": node_id,
                    "added_at": now,
                }
                for node_id in node_ids
            ]
            client.table("qa_conversation_nodes").upsert(
                records, on_conflict="conversation_id,node_id"
            ).execute()

        await asyncio.to_thread(_sync_add)

    async def qa_list_conversations(
        self, client_id: str = "default", limit: int = 50
    ) -> list[ConversationWithStats]:
        """List conversations with statistics (optimized with single query)"""

        def _sync_list():
            client = self._get_client()

            # Use RPC function for efficient aggregation
            # If RPC not available, fallback to basic query without stats
            try:
                # Try to use RPC function (if exists)
                response = client.rpc(
                    "qa_list_conversations_with_stats", {"p_client_id": client_id, "p_limit": limit}
                ).execute()

                conversations = []
                for row in response.data:
                    conv_data = {
                        **row,
                        "last_message_at": (
                            datetime.fromisoformat(row["last_message_at"])
                            if row.get("last_message_at")
                            else None
                        ),
                    }
                    conversations.append(ConversationWithStats(**conv_data))

                return conversations

            except Exception as e:
                logger.warning(f"RPC not available, using fallback query: {e}")

                # Fallback: just return conversations without detailed stats
                response = (
                    client.table("qa_conversations")
                    .select("*")
                    .eq("client_id", client_id)
                    .order("updated_at", desc=True)
                    .limit(limit)
                    .execute()
                )

                conversations = []
                for row in response.data:
                    # Basic conversation without stats
                    conv_data = {
                        **row,
                        "message_count": 0,
                        "file_count": 0,
                        "last_message_at": None,
                    }
                    conversations.append(ConversationWithStats(**conv_data))

                return conversations

        return await asyncio.to_thread(_sync_list)

    async def qa_get_conversation(self, conversation_id: str) -> Optional[Conversation]:
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
            if response.data:
                return Conversation(**response.data[0])
            return None

        return await asyncio.to_thread(_sync_get)

    async def qa_update_conversation(
        self,
        conversation_id: str,
        title: Optional[str] = None,
        model_default: Optional[str] = None,
        update_timestamp: bool = True,
    ) -> Conversation:
        """Update conversation"""

        def _sync_update():
            client = self._get_client()
            data = {}

            if update_timestamp:
                data["updated_at"] = datetime.utcnow().isoformat()

            if title is not None:
                data["title"] = title

            if model_default is not None:
                data["model_default"] = model_default

            # If no fields to update except timestamp, still update timestamp
            if not data and update_timestamp:
                data["updated_at"] = datetime.utcnow().isoformat()

            response = (
                client.table("qa_conversations").update(data).eq("id", conversation_id).execute()
            )
            return Conversation(**response.data[0])

        return await asyncio.to_thread(_sync_update)

    async def qa_delete_conversation(self, conversation_id: str) -> None:
        """Delete conversation and all related data"""

        def _sync_delete():
            client = self._get_client()

            # Delete traces
            client.table("qa_model_traces").delete().eq(
                "conversation_id", conversation_id
            ).execute()

            # Delete messages
            client.table("qa_messages").delete().eq("conversation_id", conversation_id).execute()

            # Delete nodes links
            client.table("qa_conversation_nodes").delete().eq(
                "conversation_id", conversation_id
            ).execute()

            # Delete gemini files links
            client.table("qa_conversation_gemini_files").delete().eq(
                "conversation_id", conversation_id
            ).execute()

            # Delete context files
            client.table("qa_conversation_context_files").delete().eq(
                "conversation_id", conversation_id
            ).execute()

            # Delete artifacts
            client.table("qa_artifacts").delete().eq("conversation_id", conversation_id).execute()

            # Delete conversation
            client.table("qa_conversations").delete().eq("id", conversation_id).execute()

        await asyncio.to_thread(_sync_delete)

    async def qa_delete_all_conversations(self, client_id: str = "default") -> None:
        """Delete all conversations and related data for client"""

        def _sync_delete_all():
            client = self._get_client()

            # Get all conversation IDs for this client
            response = (
                client.table("qa_conversations").select("id").eq("client_id", client_id).execute()
            )

            conversation_ids = [row["id"] for row in response.data]

            if not conversation_ids:
                return

            logger.info(f"Удаление {len(conversation_ids)} чатов для client_id={client_id}")

            # Delete all related data for these conversations
            # Using .in_() for batch deletion

            # Delete traces
            client.table("qa_model_traces").delete().in_(
                "conversation_id", conversation_ids
            ).execute()

            # Delete messages
            client.table("qa_messages").delete().in_("conversation_id", conversation_ids).execute()

            # Delete nodes links
            client.table("qa_conversation_nodes").delete().in_(
                "conversation_id", conversation_ids
            ).execute()

            # Delete gemini files links
            client.table("qa_conversation_gemini_files").delete().in_(
                "conversation_id", conversation_ids
            ).execute()

            # Delete context files
            client.table("qa_conversation_context_files").delete().in_(
                "conversation_id", conversation_ids
            ).execute()

            # Delete artifacts
            client.table("qa_artifacts").delete().in_("conversation_id", conversation_ids).execute()

            # Delete all conversations
            client.table("qa_conversations").delete().eq("client_id", client_id).execute()

            logger.info("Удалены все чаты и связанные данные")

        await asyncio.to_thread(_sync_delete_all)

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
