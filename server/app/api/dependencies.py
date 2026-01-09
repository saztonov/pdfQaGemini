"""Dependency injection for API routes"""

from typing import Optional

from app.config import settings
from app.app_settings import get_app_settings
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
    """Get Gemini client instance.

    Uses API key from Supabase settings (loaded at startup).
    """
    global _gemini_client
    if _gemini_client is None:
        app_settings = get_app_settings()
        _gemini_client = GeminiClient(api_key=app_settings.gemini_api_key)
    return _gemini_client


def get_r2_client() -> R2AsyncClient:
    """Get R2 client instance.

    Uses R2 credentials from Supabase settings (loaded at startup).
    """
    global _r2_client
    if _r2_client is None:
        app_settings = get_app_settings()
        _r2_client = R2AsyncClient(
            r2_public_base_url=app_settings.r2_public_url,
            r2_endpoint=app_settings.r2_endpoint,
            r2_bucket=app_settings.r2_bucket_name,
            r2_access_key=app_settings.r2_access_key_id,
            r2_secret_key=app_settings.r2_secret_access_key,
        )
    return _r2_client


def reset_clients():
    """Reset singleton clients (used when settings change)"""
    global _gemini_client, _r2_client
    _gemini_client = None
    _r2_client = None
