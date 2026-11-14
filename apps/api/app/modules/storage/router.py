"""
Authenticated Storage Router
Exposes secure POST /upload and GET /signed-url endpoints.
"""
from typing import Optional
from fastapi import APIRouter, Depends, UploadFile, File, Form, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.modules.users.models import User
from app.modules.storage.schemas import UploadResponse, SignedUrlResponse
from app.modules.storage.service import StorageService

router = APIRouter(prefix="/storage", tags=["File Storage & Uploads"])

@router.post("/upload", response_model=UploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_file(
    file: UploadFile = File(...),
    bucket: str = Form("properties"),
    purpose: Optional[str] = Form(None),
    resource_id: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    content_type = file.content_type or "application/octet-stream"
    content = await file.read()

    service = StorageService(db=db)
    return await service.upload_file(
        current_user=current_user,
        file_bytes=content,
        content_type=content_type,
        filename=file.filename,
        bucket=bucket,
        purpose=purpose,
        resource_id=resource_id,
    )

@router.get("/signed-url", response_model=SignedUrlResponse)
async def get_presigned_url(
    bucket: str = Query(...),
    path: str = Query(...),
    expires_in: int = Query(3600, ge=60, le=86400),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = StorageService(db=db)
    signed_url = service.get_signed_url(
        current_user=current_user,
        bucket=bucket,
        path=path,
        expires_in=expires_in,
    )
    return SignedUrlResponse(
        signed_url=signed_url,
        expires_in=expires_in,
    )
