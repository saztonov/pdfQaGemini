"""User prompts operations for Supabase repository"""

import asyncio
from typing import Optional
from datetime import datetime
from uuid import uuid4


class PromptsOpsMixin:
    """Mixin for user prompts operations"""

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
        r2_key: Optional[str] = None,
        client_id: str = "default",
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
            if response.data:
                return response.data[0]
            return None

        return await asyncio.to_thread(_sync_get)
