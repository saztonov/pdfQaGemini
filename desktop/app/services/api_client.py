"""REST API client for server communication"""

import logging
from typing import Optional
from uuid import UUID

import httpx

logger = logging.getLogger(__name__)


class APIClient:
    """Async HTTP client for server API"""

    def __init__(self, base_url: str, client_id: str = "default"):
        self.base_url = base_url.rstrip("/")
        self.client_id = client_id
        self._client: Optional[httpx.AsyncClient] = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=httpx.Timeout(60.0, connect=10.0),
                headers={"X-Client-ID": self.client_id},
            )
        return self._client

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
    ) -> dict:
        """
        Send message and get job ID for tracking.

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
    ) -> dict:
        """Upload file to Gemini via server"""
        client = self._get_client()
        with open(file_path, "rb") as f:
            files = {"file": f}
            data = {"conversation_id": conversation_id}
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
