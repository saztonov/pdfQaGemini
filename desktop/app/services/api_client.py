"""REST API client for server communication"""

import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


class APIClient:
    """Async HTTP client for server API"""

    def __init__(self, base_url: str, client_id: str = "default", api_token: str = ""):
        self.base_url = base_url.rstrip("/")
        self.client_id = client_id
        self.api_token = api_token
        self._client: Optional[httpx.AsyncClient] = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            headers = {"X-Client-ID": self.client_id}
            if self.api_token:
                headers["X-API-Token"] = self.api_token
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=httpx.Timeout(60.0, connect=10.0),
                headers=headers,
            )
        return self._client

    @staticmethod
    async def fetch_config(server_url: str, api_token: str) -> dict:
        """
        Fetch client configuration from server using API token.
        This is a static method used before APIClient is fully initialized.

        Returns config dict with: client_id, supabase_url, supabase_key,
        r2_public_base_url, default_model

        Raises httpx.HTTPStatusError on 401 (invalid token) or other errors.
        """
        async with httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=10.0)) as client:
            response = await client.get(
                f"{server_url.rstrip('/')}/api/v1/auth/config",
                headers={"X-API-Token": api_token},
            )
            response.raise_for_status()
            return response.json()

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None

    # === Health ===

    async def health_check(self) -> dict:
        """Check server health"""
        client = self._get_client()
        response = await client.get("/api/v1/health")
        response.raise_for_status()
        return response.json()

    # === Conversations ===

    async def list_conversations(self, limit: int = 50) -> list[dict]:
        """List conversations"""
        client = self._get_client()
        response = await client.get("/api/v1/conversations", params={"limit": limit})
        response.raise_for_status()
        return response.json()

    async def create_conversation(self, title: str = "") -> dict:
        """Create new conversation"""
        client = self._get_client()
        response = await client.post(
            "/api/v1/conversations",
            json={"title": title},
        )
        response.raise_for_status()
        return response.json()

    async def get_conversation(self, conversation_id: str) -> dict:
        """Get conversation by ID"""
        client = self._get_client()
        response = await client.get(f"/api/v1/conversations/{conversation_id}")
        response.raise_for_status()
        return response.json()

    async def update_conversation(self, conversation_id: str, title: str) -> dict:
        """Update conversation title"""
        client = self._get_client()
        response = await client.patch(
            f"/api/v1/conversations/{conversation_id}",
            json={"title": title},
        )
        response.raise_for_status()
        return response.json()

    async def delete_conversation(self, conversation_id: str) -> None:
        """Delete conversation"""
        client = self._get_client()
        response = await client.delete(f"/api/v1/conversations/{conversation_id}")
        response.raise_for_status()

    # === Messages ===

    async def list_messages(self, conversation_id: str) -> list[dict]:
        """List all messages in conversation"""
        client = self._get_client()
        response = await client.get(f"/api/v1/conversations/{conversation_id}/messages")
        response.raise_for_status()
        return response.json()

    async def send_message(
        self,
        conversation_id: str,
        user_text: str,
        system_prompt: str = "",
        user_text_template: str = "",
        model_name: str = "gemini-2.0-flash",
        thinking_level: str = "low",
        thinking_budget: Optional[int] = None,
        file_refs: Optional[list[dict]] = None,
        context_catalog: str = "",
    ) -> dict:
        """
        Send message and get job ID for tracking.

        Args:
            context_catalog: JSON string with available context items for agentic requests

        Returns dict with 'user_message' and 'job' keys.
        """
        client = self._get_client()
        response = await client.post(
            f"/api/v1/conversations/{conversation_id}/messages",
            json={
                "user_text": user_text,
                "system_prompt": system_prompt,
                "user_text_template": user_text_template,
                "model_name": model_name,
                "thinking_level": thinking_level,
                "thinking_budget": thinking_budget,
                "file_refs": file_refs or [],
                "context_catalog": context_catalog,
            },
        )
        response.raise_for_status()
        return response.json()

    # === Jobs ===

    async def get_job(self, job_id: str) -> dict:
        """Get job status by ID"""
        client = self._get_client()
        response = await client.get(f"/api/v1/jobs/{job_id}")
        response.raise_for_status()
        return response.json()

    async def list_jobs(
        self,
        conversation_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> list[dict]:
        """List jobs with optional filters"""
        client = self._get_client()
        params = {"limit": limit}
        if conversation_id:
            params["conversation_id"] = conversation_id
        if status:
            params["status"] = status
        response = await client.get("/api/v1/jobs", params=params)
        response.raise_for_status()
        return response.json()

    async def retry_job(self, job_id: str) -> dict:
        """Retry failed job"""
        client = self._get_client()
        response = await client.post(f"/api/v1/jobs/{job_id}/retry")
        response.raise_for_status()
        return response.json()

    # === Files ===

    async def upload_file(
        self,
        file_path: str,
        conversation_id: str,
        file_name: str = None,
        mime_type: str = None,
        source_r2_key: str = None,
        crop_index: list[dict] = None,
    ) -> dict:
        """Upload file to Gemini via server

        Args:
            crop_index: List of crop definitions with context_item_id, r2_key, r2_url
                       Will be used to build context_catalog for agentic requests
        """
        import json
        import mimetypes
        from pathlib import Path

        client = self._get_client()
        path = Path(file_path)

        # Use provided file_name or fall back to path name
        actual_name = file_name or path.name

        # Auto-detect mime_type if not provided
        if mime_type is None:
            detected, _ = mimetypes.guess_type(actual_name)
            mime_type = detected or "application/octet-stream"

        with open(file_path, "rb") as f:
            # Pass explicit filename and mime_type in tuple format
            files = {"file": (actual_name, f, mime_type)}
            data = {"conversation_id": conversation_id}
            if source_r2_key:
                data["source_r2_key"] = source_r2_key
            if crop_index:
                data["crop_index"] = json.dumps(crop_index, ensure_ascii=False)
            response = await client.post("/api/v1/files/upload", files=files, data=data)
        response.raise_for_status()
        return response.json()

    async def list_gemini_files(self) -> list[dict]:
        """List all files in Gemini Files API"""
        client = self._get_client()
        response = await client.get("/api/v1/files")
        response.raise_for_status()
        return response.json()

    async def list_conversation_files(self, conversation_id: str) -> list[dict]:
        """List files attached to conversation"""
        client = self._get_client()
        response = await client.get(f"/api/v1/files/conversation/{conversation_id}")
        response.raise_for_status()
        return response.json()

    async def delete_file(self, file_name: str) -> None:
        """Delete file from Gemini"""
        client = self._get_client()
        response = await client.delete(f"/api/v1/files/{file_name}")
        response.raise_for_status()

    # === Prompts ===

    async def list_prompts(self) -> list[dict]:
        """List all prompts"""
        client = self._get_client()
        response = await client.get("/api/v1/prompts")
        response.raise_for_status()
        return response.json()

    async def create_prompt(
        self,
        title: str,
        system_prompt: str = "",
        user_text: str = "",
    ) -> dict:
        """Create new prompt"""
        client = self._get_client()
        response = await client.post(
            "/api/v1/prompts",
            json={
                "title": title,
                "system_prompt": system_prompt,
                "user_text": user_text,
            },
        )
        response.raise_for_status()
        return response.json()

    async def get_prompt(self, prompt_id: str) -> dict:
        """Get prompt by ID"""
        client = self._get_client()
        response = await client.get(f"/api/v1/prompts/{prompt_id}")
        response.raise_for_status()
        return response.json()

    async def update_prompt(
        self,
        prompt_id: str,
        title: Optional[str] = None,
        system_prompt: Optional[str] = None,
        user_text: Optional[str] = None,
    ) -> dict:
        """Update prompt"""
        client = self._get_client()
        data = {}
        if title is not None:
            data["title"] = title
        if system_prompt is not None:
            data["system_prompt"] = system_prompt
        if user_text is not None:
            data["user_text"] = user_text
        response = await client.patch(f"/api/v1/prompts/{prompt_id}", json=data)
        response.raise_for_status()
        return response.json()

    async def delete_prompt(self, prompt_id: str) -> None:
        """Delete prompt"""
        client = self._get_client()
        response = await client.delete(f"/api/v1/prompts/{prompt_id}")
        response.raise_for_status()

    # === Settings ===

    async def get_settings(self) -> dict:
        """Get all application settings from server"""
        client = self._get_client()
        response = await client.get("/api/v1/settings")
        response.raise_for_status()
        return response.json().get("settings", {})

    async def update_setting(self, key: str, value) -> bool:
        """Update a single setting"""
        client = self._get_client()
        response = await client.patch(f"/api/v1/settings/{key}", json={"value": value})
        response.raise_for_status()
        return response.json().get("updated", False)

    async def update_settings_batch(self, settings: dict) -> int:
        """Update multiple settings at once"""
        client = self._get_client()
        response = await client.patch("/api/v1/settings", json={"settings": settings})
        response.raise_for_status()
        return response.json().get("updated_count", 0)
