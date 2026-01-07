"""Files API routes"""

import tempfile
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Header

from app.api.dependencies import get_supabase_repo, get_gemini_client
from app.models.schemas import GeminiFileResponse

router = APIRouter()


@router.post("/upload", response_model=GeminiFileResponse)
async def upload_file(
    file: UploadFile = File(...),
    conversation_id: str = Form(...),
    x_client_id: str = Header(default="default"),
):
    """Upload file to Gemini Files API"""
    gemini = get_gemini_client()
    repo = get_supabase_repo()

    # Save uploaded file to temp location
    with tempfile.NamedTemporaryFile(delete=False, suffix=Path(file.filename).suffix) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = Path(tmp.name)

    try:
        # Upload to Gemini
        result = await gemini.upload_file(
            path=tmp_path,
            mime_type=file.content_type,
            display_name=file.filename,
        )

        # Save to database - use original filename, not what Gemini returns
        gemini_file_record = await repo.qa_upsert_gemini_file(
            gemini_name=result["name"],
            gemini_uri=result["uri"],
            display_name=file.filename,  # Use original filename from upload
            mime_type=result["mime_type"],
            size_bytes=result.get("size_bytes"),
            client_id=x_client_id,
        )

        # Attach file to conversation
        if gemini_file_record and conversation_id:
            gemini_file_id = gemini_file_record.get("id")
            if gemini_file_id:
                await repo.qa_attach_gemini_file(
                    conversation_id=conversation_id,
                    gemini_file_id=str(gemini_file_id),
                )

        return GeminiFileResponse(
            gemini_name=result["name"],
            gemini_uri=result["uri"],
            display_name=file.filename,  # Use original filename
            mime_type=result["mime_type"],
            size_bytes=result.get("size_bytes"),
        )

    finally:
        # Cleanup temp file
        tmp_path.unlink(missing_ok=True)


@router.get("/conversation/{conversation_id}", response_model=list[GeminiFileResponse])
async def list_conversation_files(conversation_id: UUID):
    """List all Gemini files attached to conversation"""
    repo = get_supabase_repo()
    files = await repo.qa_get_conversation_files(str(conversation_id))

    return [
        GeminiFileResponse(
            id=f.get("id"),
            gemini_name=f["gemini_name"],
            gemini_uri=f["gemini_uri"],
            display_name=f.get("display_name"),
            mime_type=f["mime_type"],
            size_bytes=f.get("size_bytes"),
        )
        for f in files
    ]


@router.get("", response_model=list[GeminiFileResponse])
async def list_all_files():
    """List all files in Gemini Files API"""
    gemini = get_gemini_client()
    files = await gemini.list_files()

    result = []
    for f in files:
        # Convert expiration_time to ISO string if present
        exp_time = f.get("expiration_time")
        exp_time_str = None
        if exp_time:
            if hasattr(exp_time, "isoformat"):
                exp_time_str = exp_time.isoformat()
            else:
                exp_time_str = str(exp_time)

        result.append(
            GeminiFileResponse(
                gemini_name=f["name"],
                gemini_uri=f["uri"],
                display_name=f.get("display_name"),
                mime_type=f["mime_type"],
                size_bytes=f.get("size_bytes"),
                expiration_time=exp_time_str,
            )
        )
    return result


@router.delete("/{file_name:path}")
async def delete_file(file_name: str):
    """Delete file from Gemini Files API"""
    gemini = get_gemini_client()
    try:
        await gemini.delete_file(file_name)
        return {"status": "deleted"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
