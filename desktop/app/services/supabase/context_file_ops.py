"""Context file operations for Supabase repository"""

import asyncio
from typing import Optional
from datetime import datetime


class ContextFileOpsMixin:
    """Mixin for context file operations"""

    async def qa_save_context_file(
        self,
        conversation_id: str,
        node_file_id: str,
        gemini_name: Optional[str] = None,
        gemini_uri: Optional[str] = None,
        status: str = "local",
    ) -> dict:
        """Сохранить файл контекста с его статусом"""

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
        """Загрузить все файлы контекста для диалога"""

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

    async def qa_delete_context_file(self, conversation_id: str, node_file_id: str) -> None:
        """Удалить файл из контекста"""

        def _sync_delete():
            client = self._get_client()
            client.table("qa_conversation_context_files").delete().eq(
                "conversation_id", conversation_id
            ).eq("node_file_id", node_file_id).execute()

        await asyncio.to_thread(_sync_delete)
