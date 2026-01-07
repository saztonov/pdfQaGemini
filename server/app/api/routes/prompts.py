"""Prompts API routes"""

from uuid import UUID

from fastapi import APIRouter, HTTPException, Header

from app.api.dependencies import get_supabase_repo
from app.models.schemas import (
    PromptResponse,
    CreatePromptRequest,
    UpdatePromptRequest,
)

router = APIRouter()


@router.get("", response_model=list[PromptResponse])
async def list_prompts(x_client_id: str = Header(default="default")):
    """List all prompts for client"""
    repo = get_supabase_repo()
    prompts = await repo.prompts_list(client_id=x_client_id)

    return [
        PromptResponse(
            id=p["id"],
            client_id=p["client_id"],
            title=p["title"],
            system_prompt=p["system_prompt"],
            user_text=p["user_text"],
            created_at=p["created_at"],
            updated_at=p["updated_at"],
        )
        for p in prompts
    ]


@router.post("", response_model=PromptResponse)
async def create_prompt(
    request: CreatePromptRequest,
    x_client_id: str = Header(default="default"),
):
    """Create new prompt"""
    repo = get_supabase_repo()
    prompt = await repo.prompts_create(
        title=request.title,
        system_prompt=request.system_prompt,
        user_text=request.user_text,
        client_id=x_client_id,
    )

    return PromptResponse(
        id=prompt["id"],
        client_id=prompt["client_id"],
        title=prompt["title"],
        system_prompt=prompt["system_prompt"],
        user_text=prompt["user_text"],
        created_at=prompt["created_at"],
        updated_at=prompt["updated_at"],
    )


@router.get("/{prompt_id}", response_model=PromptResponse)
async def get_prompt(prompt_id: UUID):
    """Get prompt by ID"""
    repo = get_supabase_repo()
    prompt = await repo.prompts_get(str(prompt_id))

    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")

    return PromptResponse(
        id=prompt["id"],
        client_id=prompt["client_id"],
        title=prompt["title"],
        system_prompt=prompt["system_prompt"],
        user_text=prompt["user_text"],
        created_at=prompt["created_at"],
        updated_at=prompt["updated_at"],
    )


@router.patch("/{prompt_id}", response_model=PromptResponse)
async def update_prompt(prompt_id: UUID, request: UpdatePromptRequest):
    """Update prompt"""
    repo = get_supabase_repo()
    prompt = await repo.prompts_update(
        prompt_id=str(prompt_id),
        title=request.title,
        system_prompt=request.system_prompt,
        user_text=request.user_text,
    )

    return PromptResponse(
        id=prompt["id"],
        client_id=prompt["client_id"],
        title=prompt["title"],
        system_prompt=prompt["system_prompt"],
        user_text=prompt["user_text"],
        created_at=prompt["created_at"],
        updated_at=prompt["updated_at"],
    )


@router.delete("/{prompt_id}")
async def delete_prompt(prompt_id: UUID):
    """Delete prompt"""
    repo = get_supabase_repo()
    await repo.prompts_delete(str(prompt_id))
    return {"status": "deleted"}
