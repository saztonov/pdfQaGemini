"""Model trace operations for Supabase repository"""

import asyncio
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.trace import ModelTrace


class TraceOpsMixin:
    """Mixin for model trace operations"""

    async def qa_add_trace(self, trace: "ModelTrace") -> dict:
        """Add model trace to database"""

        def _sync_add():
            client = self._get_client()
            data = trace.to_db_dict()
            response = client.table("qa_model_traces").insert(data).execute()
            return response.data[0]

        return await asyncio.to_thread(_sync_add)

    async def qa_list_traces(
        self, client_id: str = "default", limit: int = 200
    ) -> list["ModelTrace"]:
        """List all traces for client (newest first)"""
        from app.services.trace import ModelTrace

        def _sync_list():
            client = self._get_client()
            response = (
                client.table("qa_model_traces")
                .select("*")
                .eq("client_id", client_id)
                .order("ts", desc=True)
                .limit(limit)
                .execute()
            )
            return [ModelTrace.from_db_row(row) for row in response.data]

        return await asyncio.to_thread(_sync_list)

    async def qa_list_traces_by_conversation(
        self, conversation_id: str, limit: int = 100
    ) -> list["ModelTrace"]:
        """List traces for specific conversation (newest first)"""
        from app.services.trace import ModelTrace

        def _sync_list():
            client = self._get_client()
            response = (
                client.table("qa_model_traces")
                .select("*")
                .eq("conversation_id", conversation_id)
                .order("ts", desc=True)
                .limit(limit)
                .execute()
            )
            return [ModelTrace.from_db_row(row) for row in response.data]

        return await asyncio.to_thread(_sync_list)
