"""Object storage abstraction (local filesystem for dev, S3/R2 for production)."""

from __future__ import annotations

import mimetypes
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Protocol

from .config import Settings


@dataclass(frozen=True)
class ObjectMetadata:
    """Minimal object metadata returned by StorageBackend.head_object."""

    size_bytes: int
    content_type: Optional[str] = None


class StorageBackend(Protocol):
    def upload_file(self, local_path: str | Path, object_key: str) -> str: ...
    def download_file(self, object_key: str, local_path: str | Path) -> str: ...
    def presign_upload(self, object_key: str, content_type: str = "video/mp4", expires_sec: int = 900) -> str: ...
    def presign_download(self, object_key: str, expires_sec: int = 3600) -> str: ...
    def head_object(self, object_key: str) -> Optional[ObjectMetadata]: ...
    def delete_object(self, object_key: str) -> bool: ...
    def resolve_local_path(self, object_key: str) -> Optional[Path]: ...


class LocalStorageBackend:
    """Dev/test storage backend rooted on the local filesystem."""

    def __init__(self, root_dir: str | Path) -> None:
        self.root = Path(root_dir).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _target(self, object_key: str) -> Path:
        clean = object_key.lstrip("/")
        dest = (self.root / clean).resolve()
        if dest != self.root and not dest.is_relative_to(self.root):
            raise ValueError(f"Illegal object_key outside storage root: {object_key!r}")
        return dest

    def local_path_for(self, object_key: str) -> Path:
        return self._target(object_key)

    def resolve_local_path(self, object_key: str) -> Optional[Path]:
        try:
            dest = self._target(object_key)
        except ValueError:
            return None
        return dest if dest.is_file() else None

    def head_object(self, object_key: str) -> Optional[ObjectMetadata]:
        target = self.resolve_local_path(object_key)
        if not target:
            return None
        ctype, _ = mimetypes.guess_type(str(target))
        return ObjectMetadata(size_bytes=target.stat().st_size, content_type=ctype)

    def delete_object(self, object_key: str) -> bool:
        target = self.resolve_local_path(object_key)
        if not target:
            return False
        target.unlink(missing_ok=True)
        return True

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

    def __init__(
        self,
        settings: Settings,
        *,
        bucket: Optional[str] = None,
        endpoint_url: Optional[str] = None,
        region: Optional[str] = None,
        access_key_id: Optional[str] = None,
        secret_access_key: Optional[str] = None,
        prefix: Optional[str] = None,
    ) -> None:
        resolved_bucket = (bucket if bucket is not None else settings.s3_bucket) or ""
        resolved_bucket = resolved_bucket.strip()
        if not resolved_bucket:
            raise ValueError("S3_BUCKET is required when STORAGE_BACKEND=s3 or r2")
        import boto3  # lazy import so local dev runs without boto3

        self.bucket = resolved_bucket
        raw_prefix = prefix if prefix is not None else settings.s3_prefix
        self.prefix = (raw_prefix or "").strip("/")
        raw_endpoint = endpoint_url if endpoint_url is not None else settings.s3_endpoint_url
        endpoint = (raw_endpoint or "").strip().rstrip("/")
        # R2 대시보드의 "S3 API" 주소는 끝에 버킷 이름이 붙어 있다. 그대로 쓰면 모든 경로 앞에 버킷 이름이 한 번 더 붙는다
        if endpoint.endswith("/" + self.bucket):
            endpoint = endpoint[: -len(self.bucket) - 1]
        self.client = boto3.client(
            "s3",
            endpoint_url=endpoint or None,
            region_name=(region if region is not None else settings.s3_region) or "auto",
            aws_access_key_id=access_key_id if access_key_id is not None else settings.s3_access_key_id,
            aws_secret_access_key=secret_access_key if secret_access_key is not None else settings.s3_secret_access_key,
        )

    def _full_key(self, object_key: str) -> str:
        clean = object_key.lstrip("/")
        return f"{self.prefix}/{clean}" if self.prefix else clean

    def resolve_local_path(self, object_key: str) -> Optional[Path]:
        _ = object_key
        return None

    def head_object(self, object_key: str) -> Optional[ObjectMetadata]:
        try:
            resp = self.client.head_object(Bucket=self.bucket, Key=self._full_key(object_key))
        except Exception as exc:
            code = str((getattr(exc, "response", {}) or {}).get("Error", {}).get("Code") or "")
            if code in {"404", "NoSuchKey", "NotFound"}:
                return None
            # Check botocore HTTP status if available
            meta = (getattr(exc, "response", {}) or {}).get("ResponseMetadata", {})
            if meta.get("HTTPStatusCode") == 404:
                return None
            raise
        return ObjectMetadata(
            size_bytes=int(resp.get("ContentLength") or 0),
            content_type=resp.get("ContentType"),
        )

    def delete_object(self, object_key: str) -> bool:
        try:
            self.client.delete_object(Bucket=self.bucket, Key=self._full_key(object_key))
            return True
        except Exception:
            return False

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
    if settings.storage_backend in ("s3", "r2"):  # R2 도 S3 호환 API 로 접속한다
        return S3StorageBackend(settings)
    return LocalStorageBackend(Path(settings.work_root) / "_objects")


def build_hook_a_storage(settings: Settings, fallback: StorageBackend) -> StorageBackend:
    """Build dedicated private R2 backend for Track A templates when HOOK_A_R2_BUCKET is set."""
    bucket = str(getattr(settings, "hook_a_r2_bucket", None) or "").strip()
    if not bucket:
        return fallback
    return S3StorageBackend(
        settings,
        bucket=bucket,
        endpoint_url=getattr(settings, "hook_a_r2_endpoint_url", None) or "",
        region=getattr(settings, "hook_a_r2_region", None) or "auto",
        access_key_id=getattr(settings, "hook_a_r2_access_key_id", None) or "",
        secret_access_key=getattr(settings, "hook_a_r2_secret_access_key", None) or "",
        prefix=getattr(settings, "hook_a_r2_prefix", None) or "",
    )
