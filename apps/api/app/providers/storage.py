from pathlib import Path

import aiofiles

from app.core.config import get_settings
from app.providers.base import StorageProvider


class LocalStorageProvider(StorageProvider):
    def __init__(self, root: str | None = None):
        settings = get_settings()
        self.root = Path(root or settings.storage_root)
        self.root.mkdir(parents=True, exist_ok=True)
        for sub in ("originals", "processed", "audio"):
            (self.root / sub).mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        path = (self.root / key).resolve()
        if not str(path).startswith(str(self.root.resolve())):
            raise ValueError("Invalid storage key")
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    async def save(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        path = self._path(key)
        async with aiofiles.open(path, "wb") as f:
            await f.write(data)
        return key

    async def open_path(self, key: str) -> Path:
        return self._path(key)

    async def url_for(self, key: str, expires_seconds: int = 3600) -> str:
        # Served via authenticated API route in MVP
        return f"/api/v1/storage/{key}"

    async def delete(self, key: str) -> None:
        path = self._path(key)
        if path.exists():
            path.unlink()


class S3StorageProvider(StorageProvider):
    """Production adapter stub — configure AWS credentials via env."""

    def __init__(self) -> None:
        settings = get_settings()
        if not settings.s3_bucket:
            raise RuntimeError("S3_BUCKET is required for S3 storage")
        self.bucket = settings.s3_bucket
        # boto3 client would be initialized here

    async def save(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        raise NotImplementedError("Install boto3 and wire S3 uploads for production")

    async def open_path(self, key: str) -> Path:
        raise NotImplementedError("S3 objects are streamed, not local paths")

    async def url_for(self, key: str, expires_seconds: int = 3600) -> str:
        raise NotImplementedError("Generate presigned URLs in production")

    async def delete(self, key: str) -> None:
        raise NotImplementedError
