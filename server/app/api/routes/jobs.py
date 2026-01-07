"""Jobs API routes"""

from uuid import UUID
from typing import Optional

from fastapi import APIRouter, HTTPException, Header

from app.api.dependencies import get_supabase_repo
from app.models.schemas import JobResponse

router = APIRouter()


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(job_id: UUID):
    """Get job status by ID"""
    repo = get_supabase_repo()
    job = await repo.get_job(str(job_id))

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return JobResponse(
        id=job["id"],
        conversation_id=job["conversation_id"],
        status=job["status"],
        progress=job.get("progress", 0.0),
        result_text=job.get("result_text"),
        result_actions=job.get("result_actions", []),
        result_is_final=job.get("result_is_final", False),
        error_message=job.get("error_message"),
        created_at=job["created_at"],
        started_at=job.get("started_at"),
        completed_at=job.get("completed_at"),
    )


@router.get("", response_model=list[JobResponse])
async def list_jobs(
    conversation_id: Optional[UUID] = None,
    status: Optional[str] = None,
    limit: int = 50,
    x_client_id: str = Header(default="default"),
):
    """List jobs with optional filters"""
    repo = get_supabase_repo()
    jobs = await repo.list_jobs(
        conversation_id=str(conversation_id) if conversation_id else None,
        client_id=x_client_id,
        status=status,
        limit=limit,
    )

    return [
        JobResponse(
            id=j["id"],
            conversation_id=j["conversation_id"],
            status=j["status"],
            progress=j.get("progress", 0.0),
            result_text=j.get("result_text"),
            result_actions=j.get("result_actions", []),
            result_is_final=j.get("result_is_final", False),
            error_message=j.get("error_message"),
            created_at=j["created_at"],
            started_at=j.get("started_at"),
            completed_at=j.get("completed_at"),
        )
        for j in jobs
    ]


@router.post("/{job_id}/retry", response_model=JobResponse)
async def retry_job(job_id: UUID):
    """Retry a failed job"""
    repo = get_supabase_repo()
    job = await repo.get_job(str(job_id))

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job["status"] != "failed":
        raise HTTPException(status_code=400, detail="Only failed jobs can be retried")

    # Reset job status to queued
    updated_job = await repo.update_job_status(
        job_id=str(job_id),
        status="queued",
        error_message=None,
    )

    return JobResponse(
        id=updated_job["id"],
        conversation_id=updated_job["conversation_id"],
        status=updated_job["status"],
        progress=0.0,
        created_at=updated_job["created_at"],
    )
