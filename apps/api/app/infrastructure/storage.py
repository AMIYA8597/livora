"""
Pluggable Storage Infrastructure for Flatmate Platform
Supports Supabase Storage and Local Filesystem Storage (for development and CI/testing).
"""
import os
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
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

    def delete_prefix(self, bucket: str, prefix: str) -> int:
        """Delete every file under `prefix` ("<owner>/"). Returns how many were removed."""
        raise NotImplementedError


def _safe_prefix(prefix: str) -> str:
    if not prefix.endswith("/") or ".." in prefix or prefix.startswith("/") or "\\" in prefix or prefix.count("/") != 1:
        raise ValueError("Prefix must be a single top-level folder like '<id>/'")
    return prefix

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

    def delete_prefix(self, bucket: str, prefix: str) -> int:
        import shutil

        folder = (self.base_dir / bucket / _safe_prefix(prefix)).resolve()
        bucket_dir = (self.base_dir / bucket).resolve()
        if not str(folder).startswith(str(bucket_dir)) or not folder.is_dir():
            return 0
        count = sum(1 for f in folder.rglob("*") if f.is_file())
        shutil.rmtree(folder)
        return count

class StorageConfigurationError(RuntimeError):
    """Raised when the configured storage backend cannot be used."""


LOCAL_STORAGE_ENVIRONMENTS = {"development", "test", "ci", "local"}


class SupabaseStorageProvider(StorageProvider):
    def __init__(self, url: str, key: str):
        if not url or not key:
            raise StorageConfigurationError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required for Supabase storage")
        try:
            from supabase import create_client, Client
            self.client: Client = create_client(url, key)
        except Exception as exc:  # pragma: no cover - depends on SDK/network
            raise StorageConfigurationError(f"Failed to initialise Supabase storage client: {exc}") from exc

    def upload_file(self, bucket: str, destination_path: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        self.client.storage.from_(bucket).upload(destination_path, data, {"content-type": content_type})
        return str(self.client.storage.from_(bucket).get_public_url(destination_path))

    def list_buckets(self) -> Dict[str, Dict[str, Any]]:
        out: Dict[str, Dict[str, Any]] = {}
        for b in self.client.storage.list_buckets():
            get = (lambda k: b.get(k)) if isinstance(b, dict) else (lambda k: getattr(b, k, None))
            out[str(get("id") or get("name"))] = {
                "public": bool(get("public")),
                "file_size_limit": get("file_size_limit"),
                "allowed_mime_types": get("allowed_mime_types"),
            }
        return out

    def verify_buckets(self) -> None:
        """
        Refuse to run when the hosted buckets contradict the registry: a private bucket that is
        public would expose KYC documents and chat files to anyone with the URL.
        """
        from app.infrastructure.storage_buckets import bucket_registry

        actual = self.list_buckets()
        problems = []
        for spec in bucket_registry().values():
            found = actual.get(spec.physical)
            if found is None:
                problems.append(f"bucket '{spec.physical}' ({spec.logical}) does not exist")
            elif found["public"] and not spec.public:
                problems.append(f"bucket '{spec.physical}' ({spec.logical}) must be PRIVATE but is public")
        if problems:
            raise StorageConfigurationError(
                "Storage buckets are misconfigured: " + "; ".join(problems)
                + ". Run scripts/provision_storage.py --apply."
            )

    def get_signed_url(self, bucket: str, path: str, expires_in: int = 3600) -> str:
        res = self.client.storage.from_(bucket).create_signed_url(path, expires_in)
        url = res.get("signedURL") or res.get("signedUrl") if isinstance(res, dict) else res
        if not url:
            raise StorageConfigurationError(f"Supabase returned no signed URL for {bucket}/{path}")
        return str(url)

    def delete_prefix(self, bucket: str, prefix: str) -> int:
        folder = _safe_prefix(prefix).rstrip("/")
        store = self.client.storage.from_(bucket)
        removed = 0
        for _ in range(1000):  # list returns pages of up to 100; uploads sit directly in the folder
            entries = store.list(folder, {"limit": 100}) or []
            paths = [f"{folder}/{e['name']}" for e in entries if isinstance(e, dict) and e.get("id")]
            if not paths:
                return removed
            store.remove(paths)
            removed += len(paths)
        return removed

_storage_instance: Optional[StorageProvider] = None

def init_storage() -> StorageProvider:
    """
    Build the storage backend. Never silently degrades: local disk is only allowed in
    development/test environments, and a broken Supabase configuration fails startup.
    """
    global _storage_instance
    storage_type = (settings.STORAGE_TYPE or "local").lower()
    environment = (settings.ENVIRONMENT or "development").lower()

    if storage_type == "supabase":
        provider = SupabaseStorageProvider(settings.SUPABASE_URL or "", settings.SUPABASE_SERVICE_ROLE_KEY or "")
        provider.verify_buckets()
        _storage_instance = provider
    elif storage_type == "local":
        if environment not in LOCAL_STORAGE_ENVIRONMENTS:
            raise StorageConfigurationError(
                f"Local filesystem storage is not allowed in '{environment}'. Set STORAGE_TYPE=supabase."
            )
        _storage_instance = LocalStorageProvider()
    else:
        raise StorageConfigurationError(f"Unknown STORAGE_TYPE '{storage_type}'")
    return _storage_instance

def get_storage() -> StorageProvider:
    global _storage_instance
    if _storage_instance is None:
        return init_storage()
    return _storage_instance
