"""Dynamic application settings loaded from Supabase

This module provides cached access to application settings stored in qa_app_settings table.
Settings are loaded once at startup and can be refreshed on demand.
"""

import logging
from typing import Any, Optional
from dataclasses import dataclass, field

from app.config import settings as infra_settings

logger = logging.getLogger(__name__)

# Cached settings instance
_app_settings: Optional["AppSettings"] = None


@dataclass
class AppSettings:
    """Application settings loaded from Supabase"""

    # Gemini API
    gemini_api_key: str = ""
    default_model: str = "gemini-3-flash-preview"

    # R2 Storage
    r2_account_id: str = ""
    r2_access_key_id: str = ""
    r2_secret_access_key: str = ""
    r2_bucket_name: str = ""
    r2_public_url: str = ""

    # Chat settings
    max_history_pairs: int = 5

    # Worker settings
    worker_max_jobs: int = 10
    worker_job_timeout: int = 300
    worker_max_retries: int = 3

    # Raw settings dict for access to any key
    _raw: dict = field(default_factory=dict)

    @property
    def r2_endpoint(self) -> str:
        """Build R2 endpoint from account_id"""
        if self.r2_account_id:
            return f"https://{self.r2_account_id}.r2.cloudflarestorage.com"
        return ""

    def get(self, key: str, default: Any = None) -> Any:
        """Get any setting by key"""
        return self._raw.get(key, default)


async def load_app_settings() -> AppSettings:
    """Load settings from Supabase and cache them"""
    global _app_settings

    from app.services.supabase_repo import SupabaseRepo

    logger.info("Loading application settings from Supabase...")

    repo = SupabaseRepo(
        url=infra_settings.supabase_url,
        key=infra_settings.supabase_key,
    )

    raw_settings = await repo.get_all_settings()
    logger.info(f"Loaded {len(raw_settings)} settings from Supabase")

    _app_settings = AppSettings(
        gemini_api_key=raw_settings.get("gemini_api_key", ""),
        default_model=raw_settings.get("default_model", "gemini-3-flash-preview"),
        r2_account_id=raw_settings.get("r2_account_id", ""),
        r2_access_key_id=raw_settings.get("r2_access_key_id", ""),
        r2_secret_access_key=raw_settings.get("r2_secret_access_key", ""),
        r2_bucket_name=raw_settings.get("r2_bucket_name", ""),
        r2_public_url=raw_settings.get("r2_public_url", ""),
        max_history_pairs=raw_settings.get("max_history_pairs", 5),
        worker_max_jobs=raw_settings.get("worker_max_jobs", 10),
        worker_job_timeout=raw_settings.get("worker_job_timeout", 300),
        worker_max_retries=raw_settings.get("worker_max_retries", 3),
        _raw=raw_settings,
    )

    return _app_settings


def get_app_settings() -> AppSettings:
    """Get cached app settings. Must call load_app_settings() first."""
    if _app_settings is None:
        raise RuntimeError(
            "App settings not loaded. Call load_app_settings() at startup."
        )
    return _app_settings


async def refresh_app_settings() -> AppSettings:
    """Reload settings from Supabase"""
    return await load_app_settings()
