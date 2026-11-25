"""Object storage abstraction (local filesystem for dev, S3/R2 for production)."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Protocol

from .config import Settings


class StorageBackend(Protocol):
    def upload_file(self, local_path: str | Path, object_key: str) -> str: ...
    def download_file(self, object_key: str, local_path: str | Path) -> str: ...
    def presign_upload(self, object_key: str, content_type: str = "video/mp4", expires_sec: int = 900) -> str: ...
    def presign_download(self, object_key: str, expires_sec: int = 3600) -> str: ...


class LocalStorageBackend:
    """Dev/test storage backend rooted on the local filesystem."""

    def __init__(self, root_dir: str | Path) -> None:
        self.root = Path(root_dir).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _target(self, object_key: str) -> Path:
        clean = object_key.lstrip("/")
        dest = (self.root / clean).resolve()
        if not str(dest).startswith(str(self.root)):
            raise ValueError(f"Illegal object_key outside storage root: {object_key!r}")
        return dest

    def upload_file(self, local_path: str | Path, object_key: str) -> str:
        dest = self._target(object_key)
        dest.parent.mkdir(parents=True, exist_ok=True)
        src = Path(local_path).resolve()
        if src != dest:
            shutil.copy2(src, dest)
        return dest.as_uri()

    def download_file(self, object_key: str, local_path: str | Path) -> str:
        src = self._target(object_key)
        dest = Path(local_path).resolve()
        dest.parent.mkdir(parents=True, exist_ok=True)
        if src != dest:
            shutil.copy2(src, dest)
        return str(dest)

    def presign_upload(
        self, object_key: str, content_type: str = "video/mp4", expires_sec: int = 900
    ) -> str:
        _ = (content_type, expires_sec)
        dest = self._target(object_key)
        dest.parent.mkdir(parents=True, exist_ok=True)
        return dest.as_uri()

    def presign_download(self, object_key: str, expires_sec: int = 3600) -> str:
        _ = expires_sec
        return self._target(object_key).as_uri()


class S3StorageBackend:
    """S3-compatible backend (Cloudflare R2 / AWS S3 / GCS S3 interop)."""

    def __init__(self, settings: Settings) -> None:
        if not settings.s3_bucket:
            raise ValueError("S3_BUCKET is required when STORAGE_BACKEND=s3")
        import boto3  # lazy import so local dev runs without boto3

        self.bucket = settings.s3_bucket
        self.prefix = settings.s3_prefix.strip("/")
        self.client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint_url or None,
            region_name=settings.s3_region,
            aws_access_key_id=settings.s3_access_key_id,
            aws_secret_access_key=settings.s3_secret_access_key,
        )

    def _full_key(self, object_key: str) -> str:
        clean = object_key.lstrip("/")
        return f"{self.prefix}/{clean}" if self.prefix else clean

    def upload_file(self, local_path: str | Path, object_key: str) -> str:
        key = self._full_key(object_key)
        self.client.upload_file(str(local_path), self.bucket, key)
        return self.presign_download(object_key)

    def download_file(self, object_key: str, local_path: str | Path) -> str:
        dest = Path(local_path).resolve()
        dest.parent.mkdir(parents=True, exist_ok=True)
        self.client.download_file(self.bucket, self._full_key(object_key), str(dest))
        return str(dest)

    def presign_upload(
        self, object_key: str, content_type: str = "video/mp4", expires_sec: int = 900
    ) -> str:
        return self.client.generate_presigned_url(
            "put_object",
            Params={"Bucket": self.bucket, "Key": self._full_key(object_key), "ContentType": content_type},
            ExpiresIn=expires_sec,
        )

    def presign_download(self, object_key: str, expires_sec: int = 3600) -> str:
        return self.client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket, "Key": self._full_key(object_key)},
            ExpiresIn=expires_sec,
        )


def build_storage(settings: Settings) -> StorageBackend:
    if settings.storage_backend == "s3":
        return S3StorageBackend(settings)
    return LocalStorageBackend(Path(settings.work_root) / "_objects")
