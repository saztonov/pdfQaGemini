"""Message operations for Supabase repository"""

import asyncio
from typing import Optional
from datetime import datetime
from uuid import uuid4
from app.models.schemas import Message


class MessageOpsMixin:
    """Mixin for message operations"""

    async def qa_add_message(
        self, conversation_id: str, role: str, content: str, meta: Optional[dict] = None
    ) -> Message:
        """Add message to conversation"""

        def _sync_add():
            client = self._get_client()
            data = {
                "id": str(uuid4()),
                "conversation_id": conversation_id,
                "role": role,
                "content": content,
                "meta": meta or {},
                "created_at": datetime.utcnow().isoformat(),
            }
            response = client.table("qa_messages").insert(data).execute()
            return Message(**response.data[0])

        return await asyncio.to_thread(_sync_add)

    async def qa_list_messages(self, conversation_id: str) -> list[Message]:
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
            return [Message(**row) for row in response.data]

        return await asyncio.to_thread(_sync_list)
