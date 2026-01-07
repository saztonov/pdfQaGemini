"""Auth API routes - client configuration endpoint"""

import logging

from fastapi import APIRouter, HTTPException, Header

from app.api.dependencies import get_supabase_repo
from app.config import settings
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

    Server settings (Supabase URL/Key, R2 public URL) come from server .env
    Client-specific settings (client_id, default_model) come from qa_clients table.

    Secrets like gemini_api_key, r2_credentials are NOT returned - all operations go through server.
    """
    repo = get_supabase_repo()

    # Look up client by token
    client_record = await repo.get_client_by_token(x_api_token)

    if not client_record:
        logger.warning(f"Invalid API token attempt: {x_api_token[:8]}...")
        raise HTTPException(status_code=401, detail="Invalid API token")

    client_id = client_record.get("client_id", "default")
    # Use client's default_model if set, otherwise server's default
    default_model = client_record.get("default_model") or settings.default_model

    logger.info(f"Client authenticated: {client_id}")

    return ClientConfigResponse(
        client_id=client_id,
        supabase_url=settings.supabase_url,
        supabase_key=settings.supabase_key,  # anon key for Realtime
        r2_public_base_url=settings.r2_public_base_url,
        default_model=default_model,
    )
