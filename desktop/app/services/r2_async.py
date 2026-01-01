"""Cloudflare R2 async client"""
import asyncio
import hashlib
from pathlib import Path
from typing import Optional
import httpx
import boto3
from botocore.client import Config
from app.services.cache import CacheManager


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
        
        # Check cache first
        cached_path = self.cache.get_path(cache_key)
        if cached_path:
            return cached_path
        
        # Download with semaphore
        async with self._download_semaphore:
            client = self._get_http_client()
            
            # Stream download
            chunks = []
            async with client.stream("GET", url) as response:
                response.raise_for_status()
                
                async for chunk in response.aiter_bytes(chunk_size=8192):
                    chunks.append(chunk)
            
            data = b"".join(chunks)
        
        # Cache
        cached_path = self.cache.put(cache_key, data)
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
