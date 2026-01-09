"""Message operations for Supabase repository (server)"""

import asyncio
from typing import Optional
from datetime import datetime
from uuid import uuid4


class MessageOpsMixin:
    """Mixin for message operations"""

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
