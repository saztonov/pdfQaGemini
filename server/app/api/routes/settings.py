"""Settings API routes - manage application settings in Supabase"""

from typing import Any
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from app.api.dependencies import get_supabase_repo, reset_clients
from app.app_settings import refresh_app_settings

router = APIRouter()


class SettingValue(BaseModel):
    """Single setting value"""

    value: Any


class SettingsResponse(BaseModel):
    """All settings response"""

    settings: dict[str, Any]


class SettingUpdateRequest(BaseModel):
    """Request to update a single setting"""

    value: Any


class SettingsBatchUpdateRequest(BaseModel):
    """Request to update multiple settings"""

    settings: dict[str, Any]


@router.get("", response_model=SettingsResponse)
async def get_all_settings(x_api_token: str = Header(...)):
    """Get all application settings.

    Returns settings that are safe to expose to clients.
    Sensitive settings (API keys, secrets) are masked.
    """
    repo = get_supabase_repo()

    # Verify token
    client = await repo.get_client_by_token(x_api_token)
    if not client:
        raise HTTPException(status_code=401, detail="Invalid API token")

    all_settings = await repo.get_all_settings()

    # Mask sensitive values for response
    safe_settings = {}
    sensitive_keys = {"gemini_api_key", "r2_secret_access_key", "r2_access_key_id"}

    for key, value in all_settings.items():
        if key in sensitive_keys and value:
            # Mask sensitive values - show only last 4 chars
            safe_settings[key] = "****" + str(value)[-4:] if len(str(value)) > 4 else "****"
        else:
            safe_settings[key] = value

    return SettingsResponse(settings=safe_settings)


@router.get("/{key}")
async def get_setting(key: str, x_api_token: str = Header(...)):
    """Get a single setting value"""
    repo = get_supabase_repo()

    # Verify token
    client = await repo.get_client_by_token(x_api_token)
    if not client:
        raise HTTPException(status_code=401, detail="Invalid API token")

    value = await repo.get_setting(key)
    if value is None:
        raise HTTPException(status_code=404, detail=f"Setting '{key}' not found")

    # Mask sensitive values
    sensitive_keys = {"gemini_api_key", "r2_secret_access_key", "r2_access_key_id"}
    if key in sensitive_keys and value:
        value = "****" + str(value)[-4:] if len(str(value)) > 4 else "****"

    return {"key": key, "value": value}


@router.patch("/{key}")
async def update_setting(
    key: str,
    request: SettingUpdateRequest,
    x_api_token: str = Header(...),
):
    """Update a single setting"""
    repo = get_supabase_repo()

    # Verify token
    client = await repo.get_client_by_token(x_api_token)
    if not client:
        raise HTTPException(status_code=401, detail="Invalid API token")

    success = await repo.set_setting(key, request.value)
    if not success:
        raise HTTPException(status_code=404, detail=f"Setting '{key}' not found")

    # Refresh cached settings and reset clients
    await refresh_app_settings()
    reset_clients()

    return {"key": key, "updated": True}


@router.patch("")
async def update_settings_batch(
    request: SettingsBatchUpdateRequest,
    x_api_token: str = Header(...),
):
    """Update multiple settings at once"""
    repo = get_supabase_repo()

    # Verify token
    client = await repo.get_client_by_token(x_api_token)
    if not client:
        raise HTTPException(status_code=401, detail="Invalid API token")

    updated_count = await repo.set_settings_batch(request.settings)

    # Refresh cached settings and reset clients
    await refresh_app_settings()
    reset_clients()

    return {"updated_count": updated_count, "total_requested": len(request.settings)}
