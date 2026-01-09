"""Cloudflare R2 async client for desktop"""

import sys
import asyncio
import hashlib
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

# Add project root to path for shared imports
project_root = Path(__file__).parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from shared.services.r2_client_base import R2AsyncClientBase
from app.services.cache import CacheManager

logger = logging.getLogger(__name__)


class R2AsyncClient(R2AsyncClientBase):
    """Desktop async client for Cloudflare R2 storage with caching"""

    def __init__(
        self,
        r2_public_base_url: str,
        r2_endpoint: str,
        r2_bucket: str,
        r2_access_key: str,
        r2_secret_key: str,
        local_cache_dir: Path,
        max_concurrent_downloads: int = 5,
    ):
        super().__init__(
            r2_public_base_url=r2_public_base_url,
            r2_endpoint=r2_endpoint,
            r2_bucket=r2_bucket,
            r2_access_key=r2_access_key,
            r2_secret_key=r2_secret_key,
            max_concurrent_downloads=max_concurrent_downloads,
        )
        # Cache (desktop-specific)
        self.cache = CacheManager(local_cache_dir)

    async def download_to_cache(self, url: str, cache_key: Optional[str] = None) -> Path:
        """Download file to cache with streaming. Returns cached file path."""
        # Generate cache key from URL if not provided
        if cache_key is None:
            cache_key = hashlib.sha256(url.encode()).hexdigest()

        logger.info(f"R2AsyncClient.download_to_cache: url={url}, cache_key={cache_key}")

        # Check cache first
        cached_path = self.cache.get_path(cache_key)
        if cached_path:
            logger.info(f"  - File found in cache: {cached_path}")
            return cached_path

        logger.info("  - File not in cache, downloading...")

        # Download with semaphore
        async with self._download_semaphore:
            client = self._get_http_client()

            try:
                # Stream download
                chunks = []
                async with client.stream("GET", url) as response:
                    response.raise_for_status()
                    logger.info(f"  - HTTP status: {response.status_code}")

                    async for chunk in response.aiter_bytes(chunk_size=8192):
                        chunks.append(chunk)

                data = b"".join(chunks)
                logger.info(f"  - Downloaded {len(data)} bytes")

            except Exception as e:
                logger.error(f"  - Download error: {e}", exc_info=True)
                raise

        # Cache
        cached_path = self.cache.put(cache_key, data)
        logger.info(f"  - File cached: {cached_path}")
        return cached_path

    async def save_trace_history(self, client_id: str, traces: list) -> str:
        """Save trace history to R2"""
        try:
            # Serialize traces to JSON
            traces_data = []
            for trace in traces:
                trace_dict = {
                    "id": trace.id,
                    "ts": trace.ts.isoformat() if trace.ts else None,
                    "conversation_id": str(trace.conversation_id),
                    "model": trace.model,
                    "thinking_level": trace.thinking_level,
                    "system_prompt": trace.system_prompt,
                    "user_text": trace.user_text,
                    "input_files": trace.input_files,
                    "response_json": trace.response_json,
                    "parsed_actions": trace.parsed_actions,
                    "latency_ms": trace.latency_ms,
                    "errors": trace.errors,
                    "is_final": trace.is_final,
                    "assistant_text": trace.assistant_text,
                    "full_thoughts": trace.full_thoughts,
                    "input_tokens": trace.input_tokens,
                    "output_tokens": trace.output_tokens,
                    "total_tokens": trace.total_tokens,
                }
                traces_data.append(trace_dict)

            # Create JSON content
            content = json.dumps(traces_data, indent=2, ensure_ascii=False)
            content_bytes = content.encode("utf-8")

            # Save to R2
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            r2_key = f"{client_id}/traces/traces_{timestamp}.json"

            s3_client = self._get_s3_client()
            await asyncio.to_thread(
                s3_client.put_object,
                Bucket=self.bucket,
                Key=r2_key,
                Body=content_bytes,
                ContentType="application/json",
            )

            logger.info(f"Saved {len(traces)} traces to R2: {r2_key}")
            return r2_key

        except Exception as e:
            logger.error(f"Failed to save trace history to R2: {e}", exc_info=True)
            raise

    async def save_chat_file(
        self,
        conversation_id: str,
        file_name: str,
        file_path: Path,
        mime_type: str = "application/octet-stream",
    ) -> str:
        """Save file to chat folder on R2. Returns R2 key."""
        r2_key = f"chats/{conversation_id}/files/{file_name}"
        await self.upload_file(r2_key, file_path, content_type=mime_type)
        return r2_key

    # Prompts storage methods

    async def save_prompt(self, prompt_id: str, prompt_data: dict) -> str:
        """Save prompt to R2 as JSON. Returns R2 key."""
        r2_key = f"prompts/{prompt_id}.json"
        data = json.dumps(prompt_data, ensure_ascii=False, indent=2).encode("utf-8")
        await self.upload_bytes(r2_key, data, content_type="application/json")
        return r2_key

    async def load_prompt(self, prompt_id: str) -> Optional[dict]:
        """Load prompt from R2. Returns prompt data or None if not found."""
        r2_key = f"prompts/{prompt_id}.json"

        try:
            exists = await self.object_exists(r2_key)
            if not exists:
                return None

            data = await self.download_bytes(r2_key)
            return json.loads(data.decode("utf-8"))
        except Exception as e:
            logger.error(f"Error loading prompt: {e}")
            return None

    async def delete_prompt(self, prompt_id: str) -> None:
        """Delete prompt from R2"""

        def _sync_delete():
            s3 = self._get_s3_client()
            r2_key = f"prompts/{prompt_id}.json"
            try:
                s3.delete_object(Bucket=self.bucket, Key=r2_key)
                logger.info(f"Deleted prompt {prompt_id}")
            except Exception as e:
                logger.error(f"Error deleting prompt: {e}")

        await asyncio.to_thread(_sync_delete)
