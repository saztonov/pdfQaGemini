"""Cloudflare R2 async client"""
import asyncio
import hashlib
import logging
from pathlib import Path
from typing import Optional
import httpx
import boto3
from botocore.client import Config
from app.services.cache import CacheManager

logger = logging.getLogger(__name__)


class R2AsyncClient:
    """Async client for Cloudflare R2 storage"""
    
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
        self.public_base_url = r2_public_base_url.rstrip("/")
        self.endpoint = r2_endpoint
        self.bucket = r2_bucket
        self.access_key = r2_access_key
        self.secret_key = r2_secret_key
        
        # Cache
        self.cache = CacheManager(local_cache_dir)
        
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
                config=Config(signature_version="s3v4"),
            )
        return self._s3_client
    
    def build_public_url(self, r2_key: str) -> str:
        """Build public URL for R2 object"""
        key = r2_key.lstrip("/")
        return f"{self.public_base_url}/{key}"
    
    async def download_to_cache(self, url: str, cache_key: Optional[str] = None) -> Path:
        """
        Download file to cache with streaming.
        Returns cached file path.
        """
        # Generate cache key from URL if not provided
        if cache_key is None:
            cache_key = hashlib.sha256(url.encode()).hexdigest()
        
        logger.info(f"R2AsyncClient.download_to_cache: url={url}, cache_key={cache_key}")
        
        # Check cache first
        cached_path = self.cache.get_path(cache_key)
        if cached_path:
            logger.info(f"  - Файл найден в кэше: {cached_path}")
            return cached_path
        
        logger.info(f"  - Файл не в кэше, скачивание...")
        
        # Download with semaphore
        async with self._download_semaphore:
            client = self._get_http_client()
            
            try:
                # Stream download
                chunks = []
                async with client.stream("GET", url) as response:
                    response.raise_for_status()
                    logger.info(f"  - HTTP статус: {response.status_code}")
                    
                    async for chunk in response.aiter_bytes(chunk_size=8192):
                        chunks.append(chunk)
                
                data = b"".join(chunks)
                logger.info(f"  - Скачано {len(data)} байт")
            
            except Exception as e:
                logger.error(f"  - ✗ Ошибка скачивания: {e}", exc_info=True)
                raise
        
        # Cache
        cached_path = self.cache.put(cache_key, data)
        logger.info(f"  - ✓ Файл сохранен в кэш: {cached_path}")
        return cached_path
    
    async def upload_bytes(
        self,
        r2_key: str,
        data: bytes,
        content_type: str = "application/octet-stream"
    ) -> str:
        """
        Upload bytes to R2, returns public URL.
        Uses boto3 in thread to not block UI.
        """
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
        self,
        r2_key: str,
        file_path: Path,
        content_type: str = "application/octet-stream"
    ) -> str:
        """
        Upload file to R2, returns public URL.
        Uses boto3 in thread to not block UI.
        """
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
    
    async def download_bytes(self, r2_key: str) -> bytes:
        """Download file from R2 as bytes (via public URL)"""
        url = self.build_public_url(r2_key)
        
        async with self._download_semaphore:
            client = self._get_http_client()
            response = await client.get(url)
            response.raise_for_status()
            return response.content
    
    async def list_objects(self, prefix: str) -> list[dict]:
        """
        List objects in R2 by prefix.
        Returns list of dicts with 'Key', 'Size', 'LastModified'
        """
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
            except:
                return False
        
        return await asyncio.to_thread(_sync_check)
    
    async def close(self):
        """Cleanup resources"""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None
    
    # Chat storage methods
    
    async def save_chat_messages(self, conversation_id: str, messages: list[dict]) -> str:
        """
        Save chat messages to R2 as JSON.
        Returns R2 key.
        """
        import json
        
        r2_key = f"chats/{conversation_id}/messages.json"
        data = json.dumps(messages, ensure_ascii=False, indent=2).encode("utf-8")
        
        await self.upload_bytes(r2_key, data, content_type="application/json")
        return r2_key
    
    async def load_chat_messages(self, conversation_id: str) -> Optional[list[dict]]:
        """
        Load chat messages from R2.
        Returns list of messages or None if not found.
        """
        import json
        
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
    
    async def save_chat_file(
        self,
        conversation_id: str,
        file_name: str,
        file_path: Path,
        mime_type: str = "application/octet-stream"
    ) -> str:
        """
        Save file to chat folder on R2.
        Returns R2 key.
        """
        r2_key = f"chats/{conversation_id}/files/{file_name}"
        await self.upload_file(r2_key, file_path, content_type=mime_type)
        return r2_key
    
    async def delete_chat_folder(self, conversation_id: str) -> None:
        """Delete entire chat folder from R2"""
        def _sync_delete():
            s3 = self._get_s3_client()
            
            # List all objects in chat folder
            prefix = f"chats/{conversation_id}/"
            response = s3.list_objects_v2(Bucket=self.bucket, Prefix=prefix)
            
            # Delete all objects
            objects = response.get("Contents", [])
            if objects:
                delete_keys = [{"Key": obj["Key"]} for obj in objects]
                s3.delete_objects(
                    Bucket=self.bucket,
                    Delete={"Objects": delete_keys}
                )
                logger.info(f"Deleted {len(delete_keys)} objects from chat {conversation_id}")
        
        await asyncio.to_thread(_sync_delete)
    
    # Prompts storage methods
    
    async def save_prompt(self, prompt_id: str, prompt_data: dict) -> str:
        """
        Save prompt to R2 as JSON.
        Returns R2 key.
        """
        import json
        
        r2_key = f"prompts/{prompt_id}.json"
        data = json.dumps(prompt_data, ensure_ascii=False, indent=2).encode("utf-8")
        
        await self.upload_bytes(r2_key, data, content_type="application/json")
        return r2_key
    
    async def load_prompt(self, prompt_id: str) -> Optional[dict]:
        """
        Load prompt from R2.
        Returns prompt data or None if not found.
        """
        import json
        
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