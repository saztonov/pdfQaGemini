"""Dependency injection for API routes"""

from typing import Optional

from app.config import settings
from app.services.supabase_repo import SupabaseRepo
from app.services.gemini_client import GeminiClient
from app.services.r2_async import R2AsyncClient

# Singleton instances
_supabase_repo: Optional[SupabaseRepo] = None
_gemini_client: Optional[GeminiClient] = None
_r2_client: Optional[R2AsyncClient] = None


def get_supabase_repo() -> SupabaseRepo:
    """Get Supabase repository instance"""
    global _supabase_repo
    if _supabase_repo is None:
        _supabase_repo = SupabaseRepo(
            url=settings.supabase_url,
            key=settings.supabase_key,
        )
    return _supabase_repo


def get_gemini_client() -> GeminiClient:
    """Get Gemini client instance"""
    global _gemini_client
    if _gemini_client is None:
        _gemini_client = GeminiClient(api_key=settings.gemini_api_key)
    return _gemini_client


def get_r2_client() -> R2AsyncClient:
    """Get R2 client instance"""
    global _r2_client
    if _r2_client is None:
        _r2_client = R2AsyncClient(
            r2_public_base_url=settings.r2_public_base_url,
            r2_endpoint=settings.r2_endpoint,
            r2_bucket=settings.r2_bucket,
            r2_access_key=settings.r2_access_key,
            r2_secret_key=settings.r2_secret_key,
        )
    return _r2_client
