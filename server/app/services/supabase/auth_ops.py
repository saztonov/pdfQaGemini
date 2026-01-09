"""Auth operations for Supabase repository (server-specific)"""

import asyncio
from typing import Optional


class AuthOpsMixin:
    """Mixin for authentication operations (server-specific)"""

    async def get_client_by_token(self, api_token: str) -> Optional[dict]:
        """Get client by API token for authentication"""

        def _sync_get():
            client = self._get_client()
            response = (
                client.table("qa_clients")
                .select("*")
                .eq("api_token", api_token)
                .eq("is_active", True)
                .limit(1)
                .execute()
            )
            return response.data[0] if response.data else None

        return await asyncio.to_thread(_sync_get)
