"""Conversations API routes"""

from uuid import UUID

from fastapi import APIRouter, HTTPException, Header

from app.api.dependencies import get_supabase_repo
from app.models.schemas import (
    ConversationResponse,
    CreateConversationRequest,
    UpdateConversationRequest,
)

router = APIRouter()


@router.post("", response_model=ConversationResponse)
async def create_conversation(
    request: CreateConversationRequest,
    x_client_id: str = Header(default="default"),
):
    """Create new conversation"""
    repo = get_supabase_repo()
    conv = await repo.qa_create_conversation(
        client_id=x_client_id,
        title=request.title,
    )
    return ConversationResponse(
        id=conv["id"],
        client_id=conv["client_id"],
        title=conv["title"],
        created_at=conv["created_at"],
        updated_at=conv["updated_at"],
        message_count=0,
        file_count=0,
    )


@router.get("", response_model=list[ConversationResponse])
async def list_conversations(
    limit: int = 50,
    x_client_id: str = Header(default="default"),
):
    """List conversations"""
    repo = get_supabase_repo()
    conversations = await repo.qa_list_conversations(client_id=x_client_id, limit=limit)

    return [
        ConversationResponse(
            id=c["id"],
            client_id=c["client_id"],
            title=c["title"],
            created_at=c["created_at"],
            updated_at=c["updated_at"],
            message_count=c.get("message_count", 0),
            file_count=c.get("file_count", 0),
            last_message_at=c.get("last_message_at"),
        )
        for c in conversations
    ]


@router.get("/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(conversation_id: UUID):
    """Get conversation by ID"""
    repo = get_supabase_repo()
    conv = await repo.qa_get_conversation(str(conversation_id))

    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    return ConversationResponse(
        id=conv["id"],
        client_id=conv["client_id"],
        title=conv["title"],
        created_at=conv["created_at"],
        updated_at=conv["updated_at"],
    )


@router.patch("/{conversation_id}", response_model=ConversationResponse)
async def update_conversation(
    conversation_id: UUID,
    request: UpdateConversationRequest,
):
    """Update conversation"""
    repo = get_supabase_repo()
    conv = await repo.qa_update_conversation(
        conversation_id=str(conversation_id),
        title=request.title,
    )

    return ConversationResponse(
        id=conv["id"],
        client_id=conv["client_id"],
        title=conv["title"],
        created_at=conv["created_at"],
        updated_at=conv["updated_at"],
    )


@router.delete("/{conversation_id}")
async def delete_conversation(conversation_id: UUID):
    """Delete conversation and all related data"""
    repo = get_supabase_repo()
    await repo.qa_delete_conversation(str(conversation_id))
    return {"status": "deleted"}
