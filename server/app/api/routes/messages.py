"""Messages API routes"""

from uuid import UUID

from fastapi import APIRouter, Header

from app.api.dependencies import get_supabase_repo
from app.services.redis_queue import get_redis_queue
from app.models.schemas import (
    MessageResponse,
    SendMessageRequest,
    SendMessageResponse,
    JobResponse,
)

router = APIRouter()


@router.get("/conversations/{conversation_id}/messages", response_model=list[MessageResponse])
async def list_messages(conversation_id: UUID):
    """List all messages in conversation"""
    repo = get_supabase_repo()
    messages = await repo.qa_list_messages(str(conversation_id))

    return [
        MessageResponse(
            id=m["id"],
            conversation_id=m["conversation_id"],
            role=m["role"],
            content=m["content"],
            meta=m.get("meta", {}),
            created_at=m["created_at"],
        )
        for m in messages
    ]


@router.post("/conversations/{conversation_id}/messages", response_model=SendMessageResponse)
async def send_message(
    conversation_id: UUID,
    request: SendMessageRequest,
    x_client_id: str = Header(default="default"),
):
    """
    Send a message and create an LLM job.

    This endpoint:
    1. Saves the user message to the database
    2. Creates a job for background LLM processing
    3. Returns immediately with user message and job info

    The client should subscribe to Supabase Realtime for job status updates.
    """
    repo = get_supabase_repo()

    # 1. Save user message
    user_msg = await repo.qa_add_message(
        conversation_id=str(conversation_id),
        role="user",
        content=request.user_text,
        meta={
            "file_refs": request.file_refs,
            "model_name": request.model_name,
            "thinking_level": request.thinking_level,
        },
    )

    # 2. Create job for LLM processing
    job = await repo.create_job(
        conversation_id=str(conversation_id),
        client_id=x_client_id,
        user_text=request.user_text,
        model_name=request.model_name,
        system_prompt=request.system_prompt,
        user_text_template=request.user_text_template,
        thinking_level=request.thinking_level,
        thinking_budget=request.thinking_budget,
        file_refs=request.file_refs,
        context_catalog=request.context_catalog,
    )

    # 3. Enqueue job to Redis for processing
    redis_queue = get_redis_queue()
    await redis_queue.enqueue_llm_job(
        job_id=job["id"],
        conversation_id=str(conversation_id),
        user_text=request.user_text,
        model_name=request.model_name,
        system_prompt=request.system_prompt,
        user_text_template=request.user_text_template,
        thinking_level=request.thinking_level,
        thinking_budget=request.thinking_budget,
        file_refs=request.file_refs,
        context_catalog=request.context_catalog,
    )

    # 4. Update conversation timestamp
    await repo.qa_update_conversation(str(conversation_id))

    return SendMessageResponse(
        user_message=MessageResponse(
            id=user_msg["id"],
            conversation_id=user_msg["conversation_id"],
            role=user_msg["role"],
            content=user_msg["content"],
            meta=user_msg.get("meta", {}),
            created_at=user_msg["created_at"],
        ),
        job=JobResponse(
            id=job["id"],
            conversation_id=job["conversation_id"],
            status=job["status"],
            progress=job.get("progress", 0.0),
            created_at=job["created_at"],
        ),
    )
