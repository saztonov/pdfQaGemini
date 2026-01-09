"""Cloudflare R2 async client base class"""

import asyncio
import json
import logging
from pathlib import Path
from typing import Optional

import boto3
import httpx
from botocore.client import Config

logger = logging.getLogger(__name__)


class R2AsyncClientBase:
    """Base async client for Cloudflare R2 storage"""

    def __init__(
        self,
        r2_public_base_url: str,
        r2_endpoint: str,
        r2_bucket: str,
        r2_access_key: str,
        r2_secret_key: str,
        max_concurrent_downloads: int = 5,
    ):
        self.public_base_url = r2_public_base_url.rstrip("/")
        self.endpoint = r2_endpoint
        self.bucket = r2_bucket
        self.access_key = r2_access_key
        self.secret_key = r2_secret_key

        # HTTP client (lazy init)
        self._http_client: Optional[httpx.AsyncClient] = None

        # Semaphore for download concurrency
        self._download_semaphore = asyncio.Semaphore(max_concurrent_downloads)

        # Boto3 client (lazy init, used in threads)
        self._s3_client = None

    def _get_http_client(self) -> httpx.AsyncClient:
        """Lazy init HTTP client"""
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(
                timeout=httpx.Timeout(30.0, connect=10.0),
                limits=httpx.Limits(max_keepalive_connections=10, max_connections=20),
            )
        return self._http_client

    def _get_s3_client(self):
        """Lazy init boto3 S3 client"""
        if self._s3_client is None:
            self._s3_client = boto3.client(
                "s3",
                endpoint_url=self.endpoint,
                aws_access_key_id=self.access_key,
                aws_secret_access_key=self.secret_key,
                region_name="auto",
                config=Config(signature_version="s3v4"),
            )
        return self._s3_client

    def build_public_url(self, r2_key: str) -> str:
        """Build public URL for R2 object"""
        key = r2_key.lstrip("/")
        return f"{self.public_base_url}/{key}"

    async def download_bytes(self, r2_key: str) -> bytes:
        """Download file from R2 as bytes (via public URL)"""
        url = self.build_public_url(r2_key)

        async with self._download_semaphore:
            client = self._get_http_client()
            response = await client.get(url)
            response.raise_for_status()
            return response.content

    async def download_from_url(self, url: str) -> bytes:
        """Download file directly from a URL (for pre-built R2 URLs)"""
        async with self._download_semaphore:
            client = self._get_http_client()
            response = await client.get(url)
            response.raise_for_status()
            return response.content

    async def upload_bytes(
        self, r2_key: str, data: bytes, content_type: str = "application/octet-stream"
    ) -> str:
        """Upload bytes to R2, returns public URL."""

        def _sync_upload():
            s3 = self._get_s3_client()
            s3.put_object(
                Bucket=self.bucket,
                Key=r2_key,
                Body=data,
                ContentType=content_type,
            )

        await asyncio.to_thread(_sync_upload)
        return self.build_public_url(r2_key)

    async def upload_file(
        self, r2_key: str, file_path: Path, content_type: str = "application/octet-stream"
    ) -> str:
        """Upload file to R2, returns public URL."""

        def _sync_upload():
            s3 = self._get_s3_client()
            with open(file_path, "rb") as f:
                s3.put_object(
                    Bucket=self.bucket,
                    Key=r2_key,
                    Body=f,
                    ContentType=content_type,
                )

        await asyncio.to_thread(_sync_upload)
        return self.build_public_url(r2_key)

    async def list_objects(self, prefix: str) -> list[dict]:
        """List objects in R2 by prefix."""

        def _sync_list():
            s3 = self._get_s3_client()
            response = s3.list_objects_v2(
                Bucket=self.bucket,
                Prefix=prefix,
            )
            return response.get("Contents", [])

        return await asyncio.to_thread(_sync_list)

    async def object_exists(self, r2_key: str) -> bool:
        """Check if object exists in R2"""

        def _sync_check():
            s3 = self._get_s3_client()
            try:
                s3.head_object(Bucket=self.bucket, Key=r2_key)
                return True
            except Exception:
                return False

        return await asyncio.to_thread(_sync_check)

    async def delete_object(self, r2_key: str) -> None:
        """Delete object from R2"""

        def _sync_delete():
            s3 = self._get_s3_client()
            s3.delete_object(Bucket=self.bucket, Key=r2_key)

        await asyncio.to_thread(_sync_delete)

    async def close(self):
        """Cleanup resources"""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None

    # Chat storage methods

    async def save_chat_messages(self, conversation_id: str, messages: list[dict]) -> str:
        """Save chat messages to R2 as JSON. Returns R2 key."""
        r2_key = f"chats/{conversation_id}/messages.json"
        data = json.dumps(messages, ensure_ascii=False, indent=2).encode("utf-8")
        await self.upload_bytes(r2_key, data, content_type="application/json")
        return r2_key

    async def load_chat_messages(self, conversation_id: str) -> Optional[list[dict]]:
        """Load chat messages from R2. Returns list of messages or None."""
        r2_key = f"chats/{conversation_id}/messages.json"
        try:
            exists = await self.object_exists(r2_key)
            if not exists:
                return None
            data = await self.download_bytes(r2_key)
            return json.loads(data.decode("utf-8"))
        except Exception as e:
            logger.error(f"Error loading chat messages: {e}")
            return None

    async def delete_chat_folder(self, conversation_id: str) -> None:
        """Delete entire chat folder from R2"""

        def _sync_delete():
            s3 = self._get_s3_client()
            prefix = f"chats/{conversation_id}/"
            response = s3.list_objects_v2(Bucket=self.bucket, Prefix=prefix)
            objects = response.get("Contents", [])
            if objects:
                delete_keys = [{"Key": obj["Key"]} for obj in objects]
                s3.delete_objects(Bucket=self.bucket, Delete={"Objects": delete_keys})
                logger.info(f"Deleted {len(delete_keys)} objects from chat {conversation_id}")

        await asyncio.to_thread(_sync_delete)
