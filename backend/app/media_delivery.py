"""Canonical object_key builders, signed local media tokens, HTTP Range streaming & URL resolution."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import mimetypes
import re
import time
import uuid
from pathlib import Path
from typing import Optional, Tuple
from urllib.parse import quote, unquote, urlparse

from fastapi import HTTPException, Response, status

from .config import Settings
from .storage import LocalStorageBackend, StorageBackend


class MediaTokenError(ValueError):
    """Raised when a signed media access token is malformed, invalid, or expired."""


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64url_decode(val: str) -> bytes:
    pad = "=" * (-len(val) % 4)
    return base64.urlsafe_b64decode(val + pad)


def sanitize_object_key(object_key: str) -> str:
    """Normalize a storage object key and block path traversal."""
    clean = (object_key or "").strip().replace("\\", "/").lstrip("/")
    if not clean or ".." in clean.split("/"):
        raise ValueError(f"Illegal object_key: {object_key!r}")
    return clean


def upload_object_key(user_id: str, project_id: str, shot_no: int, filename: str) -> str:
    ext = Path(filename or "clip.mp4").suffix.lower() or ".mp4"
    if not re.fullmatch(r"\.[a-z0-9]{1,8}", ext):
        ext = ".mp4"
    return f"uploads/{user_id}/{project_id}/shot_{int(shot_no):02d}_{uuid.uuid4().hex[:8]}{ext}"


def storyboard_object_key(project_id: str, scenario_id: str, order: int) -> str:
    return f"projects/{project_id}/storyboards/{scenario_id}/storyboard_{int(order):02d}.png"


def hook_object_key(project_id: str, hook_id: str, filename: str) -> str:
    return f"projects/{project_id}/hooks/{hook_id}/{Path(filename).name}"


def body_object_key(project_id: str, body_id: str, filename: str) -> str:
    return f"projects/{project_id}/body/{body_id}/{Path(filename).name}"


def render_object_key(project_id: str, job_id: str, filename: str) -> str:
    return f"projects/{project_id}/renders/{job_id}/{Path(filename).name}"


def thumbnail_object_key(project_id: str, thumb_id: str, filename: str = "cover.png") -> str:
    return f"projects/{project_id}/thumbnails/{thumb_id}/{Path(filename).name}"


def issue_media_token(
    object_key: str,
    secret: str,
    *,
    ttl_sec: int = 3600,
    filename: Optional[str] = None,
    now_epoch: Optional[int] = None,
) -> str:
    """Issue a short-lived HMAC-SHA256 token authorizing read/stream of a single object_key."""
    clean_key = sanitize_object_key(object_key)
    if not secret:
        raise ValueError("session_secret must not be empty")
    now_ts = int(now_epoch if now_epoch is not None else time.time())
    payload = {
        "k": clean_key,
        "exp": now_ts + max(1, int(ttl_sec)),
    }
    if filename:
        payload["fn"] = Path(filename).name
    body = _b64url_encode(json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))
    sig = hmac.new(secret.encode("utf-8"), body.encode("ascii"), hashlib.sha256).digest()
    return f"{body}.{_b64url_encode(sig)}"


def verify_media_token(
    token: str,
    secret: str,
    *,
    now_epoch: Optional[int] = None,
) -> Tuple[str, Optional[str]]:
    """Validate signature & expiration of a media token; return (object_key, filename)."""
    if not token or "." not in token:
        raise MediaTokenError("Malformed media token")
    body, sig_b64 = token.split(".", 1)
    expected_sig = _b64url_encode(
        hmac.new(secret.encode("utf-8"), body.encode("ascii"), hashlib.sha256).digest()
    )
    if not hmac.compare_digest(sig_b64, expected_sig):
        raise MediaTokenError("Invalid media token signature")
    try:
        payload = json.loads(_b64url_decode(body).decode("utf-8"))
    except Exception as exc:
        raise MediaTokenError("Corrupt media token payload") from exc

    cur_ts = int(now_epoch if now_epoch is not None else time.time())
    if int(payload.get("exp") or 0) <= cur_ts:
        raise MediaTokenError("Media token expired")

    raw_key = str(payload.get("k") or "")
    try:
        clean_key = sanitize_object_key(raw_key)
    except ValueError as exc:
        raise MediaTokenError(str(exc)) from exc
    fn = payload.get("fn")
    return clean_key, (str(fn) if fn else None)


def extract_object_key(ref: Optional[str], storage: StorageBackend) -> Optional[str]:
    """Extract a relative storage object_key from either a plain key or a LocalStorage file:// URI."""
    if not ref or not isinstance(ref, str):
        return None
    val = ref.strip()
    if not val:
        return None
    if val.startswith("file://"):
        parsed = urlparse(val)
        file_path = Path(unquote(parsed.path)).resolve()
        root = getattr(storage, "root", None)
        if root is not None:
            root_path = Path(root).resolve()
            if file_path.is_relative_to(root_path):
                return file_path.relative_to(root_path).as_posix()
        return None
    if "://" in val or val.startswith("/"):
        return None
    try:
        return sanitize_object_key(val)
    except ValueError:
        return None


def resolve_media_url(
    ref: Optional[str],
    *,
    storage: StorageBackend,
    settings: Settings,
    download: bool = False,
    filename: Optional[str] = None,
    expires_sec: Optional[int] = None,
    base_url: str = "",
) -> Optional[str]:
    """Resolve an object_key / file:// URI / external URL into a fresh client-usable URL."""
    if not ref or not isinstance(ref, str):
        return None
    val = ref.strip()
    if not val:
        return None
    if val.startswith(("http://", "https://")):
        return val

    ttl = max(60, int(expires_sec or getattr(settings, "media_url_ttl_sec", 3600)))
    key = extract_object_key(val, storage)
    if key is None:
        return val

    if settings.storage_backend in ("s3", "r2") and not isinstance(storage, LocalStorageBackend):
        return storage.presign_download(key, expires_sec=ttl)

    token = issue_media_token(
        key,
        settings.session_secret,
        ttl_sec=ttl,
        filename=filename or Path(key).name,
    )
    prefix = base_url.rstrip("/")
    suffix = "?download=1" if download else ""
    return f"{prefix}/v1/media/{token}{suffix}"


def _guess_media_type(file_path: Path) -> str:
    ext = file_path.suffix.lower()
    if ext == ".mp4":
        return "video/mp4"
    if ext == ".png":
        return "image/png"
    if ext in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if ext == ".webp":
        return "image/webp"
    if ext == ".wav":
        return "audio/wav"
    if ext == ".mp3":
        return "audio/mpeg"
    if ext == ".srt":
        return "text/plain; charset=utf-8"
    if ext == ".json":
        return "application/json; charset=utf-8"
    guessed, _ = mimetypes.guess_type(str(file_path))
    return guessed or "application/octet-stream"


def _parse_range_header(range_header: str, file_size: int) -> Tuple[int, int]:
    m = re.fullmatch(r"bytes=(\d*)-(\d*)", range_header.strip(), flags=re.IGNORECASE)
    if not m or (not m.group(1) and not m.group(2)):
        raise ValueError("Invalid Range header")
    if file_size <= 0:
        raise ValueError("Empty file cannot satisfy byte range")

    start_str, end_str = m.group(1), m.group(2)
    if start_str:
        start = int(start_str)
        end = int(end_str) if end_str else (file_size - 1)
    else:
        suffix_len = int(end_str)
        if suffix_len <= 0:
            raise ValueError("Zero suffix length")
        start = max(0, file_size - suffix_len)
        end = file_size - 1

    if start >= file_size or end < start:
        raise ValueError("Requested range not satisfiable")
    end = min(end, file_size - 1)
    return start, end


def build_range_file_response(
    file_path: Path,
    range_header: Optional[str],
    *,
    download: bool = False,
    filename: Optional[str] = None,
) -> Response:
    """Build a 200 OK or 206 Partial Content HTTP response for a local media file."""
    if not file_path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Media file not found")

    file_size = file_path.stat().st_size
    media_type = _guess_media_type(file_path)
    dl_name = Path(filename or file_path.name).name
    headers = {"Accept-Ranges": "bytes"}
    if download:
        headers["Content-Disposition"] = f"attachment; filename*=UTF-8''{quote(dl_name)}"

    if range_header:
        try:
            start, end = _parse_range_header(range_header, file_size)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_416_RANGE_NOT_SATISFIABLE,
                detail=str(exc),
                headers={"Content-Range": f"bytes */{file_size}"},
            ) from exc
        length = end - start + 1
        with file_path.open("rb") as fh:
            fh.seek(start)
            chunk = fh.read(length)
        headers["Content-Range"] = f"bytes {start}-{end}/{file_size}"
        headers["Content-Length"] = str(len(chunk))
        return Response(
            content=chunk,
            status_code=status.HTTP_206_PARTIAL_CONTENT,
            media_type=media_type,
            headers=headers,
        )

    raw = file_path.read_bytes()
    headers["Content-Length"] = str(len(raw))
    return Response(
        content=raw,
        status_code=status.HTTP_200_OK,
        media_type=media_type,
        headers=headers,
    )
