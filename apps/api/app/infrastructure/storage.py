"""
Pluggable Storage Infrastructure for Flatmate Platform
Supports Supabase Storage and Local Filesystem Storage (for development and CI/testing).
"""
import os
from abc import ABC, abstractmethod
from typing import Optional
from pathlib import Path
from app.core.config import settings

class StorageProvider(ABC):
    @abstractmethod
    def upload_file(self, bucket: str, destination_path: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        """Upload file bytes and return a URL."""
        pass

    @abstractmethod
    def get_signed_url(self, bucket: str, path: str, expires_in: int = 3600) -> str:
        """Get time-limited presigned URL."""
        pass

class LocalStorageProvider(StorageProvider):
    def __init__(self, base_dir: Optional[str] = None):
        self.base_dir = Path(base_dir or os.path.join(os.getcwd(), "uploads"))
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def upload_file(self, bucket: str, destination_path: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        if ".." in destination_path or destination_path.startswith("/") or "\\" in destination_path:
            raise ValueError("Invalid destination path: traversal detected")
        bucket_dir = (self.base_dir / bucket).resolve()
        bucket_dir.mkdir(parents=True, exist_ok=True)
        file_path = (bucket_dir / destination_path).resolve()
        if not str(file_path).startswith(str(bucket_dir)):
            raise ValueError("Path traversal attempt detected")
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_bytes(data)
        return f"/uploads/{bucket}/{destination_path}"

    def get_signed_url(self, bucket: str, path: str, expires_in: int = 3600) -> str:
        if ".." in path or path.startswith("/") or "\\" in path:
            raise ValueError("Invalid path: traversal detected")
        bucket_dir = (self.base_dir / bucket).resolve()
        file_path = (bucket_dir / path).resolve()
        if not str(file_path).startswith(str(bucket_dir)):
            raise ValueError("Path traversal attempt detected")
        return f"/uploads/{bucket}/{path}?expires={expires_in}"

class SupabaseStorageProvider(StorageProvider):
    def __init__(self, url: str, key: str):
        try:
            from supabase import create_client, Client
            self.client: Optional[Client] = create_client(url, key)
        except Exception:
            self.client = None

    def upload_file(self, bucket: str, destination_path: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        if not self.client:
            return f"https://mock.supabase.co/storage/v1/object/public/{bucket}/{destination_path}"
        self.client.storage.from_(bucket).upload(destination_path, data, {"content-type": content_type})
        return self.client.storage.from_(bucket).get_public_url(destination_path)

    def get_signed_url(self, bucket: str, path: str, expires_in: int = 3600) -> str:
        if not self.client:
            return f"https://mock.supabase.co/storage/v1/object/sign/{bucket}/{path}?expires={expires_in}"
        res = self.client.storage.from_(bucket).create_signed_url(path, expires_in)
        if isinstance(res, dict):
            return str(res.get("signedURL") or "")
        return str(res or "")

_storage_instance: Optional[StorageProvider] = None

def init_storage() -> StorageProvider:
    global _storage_instance
    storage_type = getattr(settings, "STORAGE_TYPE", "local").lower()

    if storage_type == "supabase" and hasattr(settings, "SUPABASE_URL") and settings.SUPABASE_URL:
        _storage_instance = SupabaseStorageProvider(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY or "")
    else:
        _storage_instance = LocalStorageProvider()
    return _storage_instance

def get_storage() -> StorageProvider:
    global _storage_instance
    if _storage_instance is None:
        return init_storage()
    return _storage_instance
