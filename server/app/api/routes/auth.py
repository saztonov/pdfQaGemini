"""Auth API routes - client configuration endpoint"""

import logging

from fastapi import APIRouter, HTTPException, Header

from app.api.dependencies import get_supabase_repo
from app.models.schemas import ClientConfigResponse

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/config", response_model=ClientConfigResponse)
async def get_client_config(x_api_token: str = Header(..., description="Client API token (UUID)")):
    """
    Get client configuration by API token.

    Client sends their API token and receives configuration needed for:
    - Connecting to Supabase Realtime
    - Loading files from R2
    - Default model settings

    Secrets like gemini_api_key are NOT returned - all LLM operations go through server.
    """
    repo = get_supabase_repo()

    settings = await repo.get_settings_by_token(x_api_token)

    if not settings:
        logger.warning(f"Invalid API token attempt: {x_api_token[:8]}...")
        raise HTTPException(status_code=401, detail="Invalid API token")

    logger.info(f"Client authenticated: {settings.get('client_id', 'unknown')}")

    return ClientConfigResponse(
        client_id=settings.get("client_id", "default"),
        supabase_url=settings.get("supabase_url", ""),
        supabase_key=settings.get("supabase_anon_key", ""),
        r2_public_base_url=settings.get("r2_public_base_url", ""),
        default_model=settings.get("default_model", "gemini-2.0-flash"),
    )
