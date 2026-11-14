from typing import Optional
from pydantic import BaseModel

class UploadResponse(BaseModel):
    url: str
    file_url: Optional[str] = None
    bucket: str
    path: str
    content_type: str
    size_bytes: int
    object_id: Optional[str] = None
    purpose: Optional[str] = None
    resource_id: Optional[str] = None
    is_private: bool = False

class SignedUrlRequest(BaseModel):
    bucket: str
    path: str
    expires_in: Optional[int] = 3600

class SignedUrlResponse(BaseModel):
    signed_url: str
    expires_in: int
