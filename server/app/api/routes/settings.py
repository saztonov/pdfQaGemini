"""Settings API routes - manage application settings in Supabase

Sensitive values (API keys, secrets) are:
- Stored encrypted in database using AES-256-GCM
- Returned masked to clients (e.g., "AIza***xyz9")
- Only saved when client sends non-masked value (new key)
"""

from typing import Any
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from app.api.dependencies import get_supabase_repo, reset_clients
from app.app_settings import refresh_app_settings
from app.services.crypto import is_sensitive_key, mask_sensitive_value

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


def _is_masked_value(value: str) -> bool:
    """Check if value is a masked placeholder (contains ***)"""
    return isinstance(value, str) and "***" in value


@router.get("", response_model=SettingsResponse)
async def get_all_settings(x_api_token: str = Header(...)):
    """Get all application settings.

    Returns settings with sensitive values masked (e.g., "AIza***xyz9").
    Masked values indicate the field has a value but it's hidden for security.
    """
    repo = get_supabase_repo()

    # Verify token
    client = await repo.get_client_by_token(x_api_token)
    if not client:
        raise HTTPException(status_code=401, detail="Invalid API token")

    # Get settings with masked sensitive values
    masked_settings = await repo.get_settings_masked()

    return SettingsResponse(settings=masked_settings)


@router.get("/{key}")
async def get_setting(key: str, x_api_token: str = Header(...)):
    """Get a single setting value (masked if sensitive)"""
    repo = get_supabase_repo()

    # Verify token
    client = await repo.get_client_by_token(x_api_token)
    if not client:
        raise HTTPException(status_code=401, detail="Invalid API token")

    # Get raw value without decryption for masking
    value = await repo.get_setting(key, decrypt=False)
    if value is None:
        raise HTTPException(status_code=404, detail=f"Setting '{key}' not found")

    # Mask sensitive values
    if is_sensitive_key(key) and value:
        value = mask_sensitive_value(value, key)

    return {"key": key, "value": value}


@router.patch("/{key}")
async def update_setting(
    key: str,
    request: SettingUpdateRequest,
    x_api_token: str = Header(...),
):
    """Update a single setting.

    For sensitive values:
    - If value contains '***', it's ignored (user didn't change it)
    - If value is a new unmasked string, it will be encrypted and saved
    """
    repo = get_supabase_repo()

    # Verify token
    client = await repo.get_client_by_token(x_api_token)
    if not client:
        raise HTTPException(status_code=401, detail="Invalid API token")

    # Skip if masked value (user didn't change it)
    if is_sensitive_key(key) and _is_masked_value(str(request.value)):
        return {"key": key, "updated": False, "reason": "masked_value_skipped"}

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
    """Update multiple settings at once.

    For sensitive values:
    - Masked values (containing '***') are skipped
    - Only new unmasked values are encrypted and saved
    """
    repo = get_supabase_repo()

    # Verify token
    client = await repo.get_client_by_token(x_api_token)
    if not client:
        raise HTTPException(status_code=401, detail="Invalid API token")

    # Filter out masked sensitive values - don't overwrite with masked placeholders
    filtered_settings = {}
    skipped_count = 0

    for key, value in request.settings.items():
        if is_sensitive_key(key) and _is_masked_value(str(value)):
            # Skip masked values - user didn't change them
            skipped_count += 1
            continue
        filtered_settings[key] = value

    # Only update if there's something to update
    updated_count = 0
    if filtered_settings:
        updated_count = await repo.set_settings_batch(filtered_settings)

        # Refresh cached settings and reset clients
        await refresh_app_settings()
        reset_clients()

    return {
        "updated_count": updated_count,
        "skipped_count": skipped_count,
        "total_requested": len(request.settings),
    }
