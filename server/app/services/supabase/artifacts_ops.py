"""Artifacts operations for Supabase repository (server)"""

import asyncio
from typing import Optional
from datetime import datetime
from uuid import uuid4


class ArtifactsOpsMixin:
    """Mixin for artifacts operations"""

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
