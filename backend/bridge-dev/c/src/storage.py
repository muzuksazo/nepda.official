"""C 작업자의 결과 파일을 로컬에 두거나 R2에 올리고 임시 다운로드 URL을 발급한다."""
from __future__ import annotations

import mimetypes
import os
from pathlib import Path
from urllib.parse import urlsplit


class StorageError(RuntimeError):
    def __init__(self, message: str, code: str = "STORAGE_UPLOAD_FAILED"):
        super().__init__(message)
        self.code = code


FILE_NAMES = {
    "hook_video": "hook.mp4",
    "tts_audio": "tts.mp3",
    "subtitles_srt": "hook.srt",
    "scenario_json": "scenario.json",
}
CONTENT_TYPES = {
    ".mp4": "video/mp4", ".mp3": "audio/mpeg", ".srt": "application/x-subrip",
    ".json": "application/json", ".png": "image/png",
}


def result_files(out_dir: str) -> dict:
    """이미 렌더한 결과만 다시 올릴 때 쓴다. 작업 캐시나 입력 영상은 포함하지 않는다."""
    root = Path(out_dir)
    files = {field: str(root / name) for field, name in FILE_NAMES.items()}
    missing = [name for name in files.values() if not Path(name).is_file()]
    if missing:
        raise StorageError("결과 파일이 없습니다: " + ", ".join(missing))
    files["storyboard_images"] = [str(p) for p in sorted(root.glob("storyboard_*.png"))]
    return files


def _failure_code(exc: Exception) -> str:
    # SDK 예외 전체에는 요청 정보가 포함될 수 있으므로 오류 코드만 노출한다.
    return str(getattr(exc, "response", {}).get("Error", {}).get("Code") or type(exc).__name__)


class DeliveryStorage:
    def __init__(self):
        self.backend = os.environ.get("C_STORAGE_BACKEND", os.environ.get("STORAGE_BACKEND", "local")).strip().lower()
        self.root = Path(os.environ.get("OUTPUT_DIR", "output")).resolve()
        if self.backend not in ("local", "s3"):
            raise StorageError("STORAGE_BACKEND는 local 또는 s3여야 합니다.", "STORAGE_CONFIG_ERROR")
        self.client = None
        if self.backend == "local":
            return
        required = ("S3_BUCKET", "S3_ENDPOINT_URL", "S3_ACCESS_KEY_ID", "S3_SECRET_ACCESS_KEY")
        values = {key: os.environ.get(key, "").strip() for key in required}
        missing = [key for key, value in values.items() if not value]
        if missing:
            raise StorageError("c/.env에 R2 설정이 필요합니다: " + ", ".join(missing), "STORAGE_CONFIG_ERROR")
        self.bucket = values["S3_BUCKET"]
        self.prefix = os.environ.get("S3_PREFIX", "shortform-ad-studio/C").strip("/")
        try:
            self.expires_sec = int(os.environ.get("S3_URL_EXPIRES_SEC", "3600"))
            if not 60 <= self.expires_sec <= 604800:
                raise ValueError
        except ValueError as exc:
            raise StorageError("S3_URL_EXPIRES_SEC는 60~604800 사이의 초 단위 정수여야 합니다.", "STORAGE_CONFIG_ERROR") from exc
        try:
            import boto3
            from botocore.config import Config
        except ImportError as exc:
            raise StorageError("R2를 쓰려면 pip install -r requirements.txt를 실행하세요.", "STORAGE_CONFIG_ERROR") from exc
        try:
            self.client = boto3.client(
                "s3", endpoint_url=values["S3_ENDPOINT_URL"],
                region_name=os.environ.get("S3_REGION", "auto"),
                aws_access_key_id=values["S3_ACCESS_KEY_ID"],
                aws_secret_access_key=values["S3_SECRET_ACCESS_KEY"],
                config=Config(signature_version="s3v4", s3={"addressing_style": "path"},
                              request_checksum_calculation="when_required", response_checksum_validation="when_required",
                              connect_timeout=10, read_timeout=60, retries={"mode": "standard", "max_attempts": 3}),
            )
        except Exception as exc:
            raise StorageError(f"R2 클라이언트 설정 실패 ({_failure_code(exc)})", "STORAGE_CONFIG_ERROR") from exc

    def check_connection(self) -> None:
        """객체 내용을 받거나 변경하지 않고 연결과 버킷 읽기 권한만 확인한다."""
        if self.backend == "s3":
            try:
                self.client.list_objects_v2(Bucket=self.bucket, Prefix=self.prefix + "/" if self.prefix else "", MaxKeys=1)
            except Exception as exc:
                raise StorageError(f"R2 연결 확인 실패 ({_failure_code(exc)})", "STORAGE_CONNECTION_FAILED") from exc

    def _key_for(self, path: str) -> tuple[Path, str]:
        local = Path(path).resolve()
        try:
            relative = local.relative_to(self.root).as_posix()
        except ValueError as exc:
            raise StorageError("OUTPUT_DIR 밖의 파일은 R2에 올릴 수 없습니다.") from exc
        if not local.is_file():
            raise StorageError(f"결과 파일이 없습니다: {local.name}")
        return local, f"{self.prefix}/{relative}" if self.prefix else relative

    def publish_files(self, files: dict) -> dict:
        """로컬 경로를 s3:// 참조로 바꾼다. 임시 URL은 응답을 보낼 때 새로 발급한다."""
        if self.backend == "local":
            return dict(files)
        paths = [files[field] for field in FILE_NAMES if files.get(field)] + list(files.get("storyboard_images", []))
        # 모든 경로를 먼저 확인해 잘못된 입력 때문에 일부 파일만 업로드되는 일을 막는다.
        planned = {path: self._key_for(path) for path in paths}
        published = {}
        for path, (local, key) in planned.items():
            content_type = CONTENT_TYPES.get(local.suffix.lower()) or mimetypes.guess_type(local.name)[0] or "application/octet-stream"
            try:
                self.client.upload_file(str(local), self.bucket, key, ExtraArgs={"ContentType": content_type})
            except Exception as exc:
                raise StorageError(f"R2 업로드 실패: {local.name} ({_failure_code(exc)}). 로컬 결과는 보존했습니다.") from exc
            published[path] = f"s3://{self.bucket}/{key}"
        out = dict(files)
        for field in FILE_NAMES:
            if files.get(field):
                out[field] = published[files[field]]
        if "storyboard_images" in files:
            out["storyboard_images"] = [published[path] for path in files["storyboard_images"]]
        return out

    def publish_storyboard(self, frames: list[dict]) -> list[dict]:
        files = self.publish_files({"storyboard_images": [frame["image_url"] for frame in frames]})
        return [{**frame, "image_url": path} for frame, path in zip(frames, files["storyboard_images"])]

    def download_url(self, path: str) -> str:
        if not path.startswith("s3://"):
            return path
        ref = urlsplit(path)
        if self.backend != "s3" or ref.netloc != self.bucket:
            raise StorageError("결과 파일의 R2 버킷 설정이 현재 설정과 다릅니다.", "STORAGE_CONFIG_ERROR")
        try:
            return self.client.generate_presigned_url(
                "get_object", Params={"Bucket": self.bucket, "Key": ref.path.lstrip("/")}, ExpiresIn=self.expires_sec,
            )
        except Exception as exc:
            raise StorageError(f"R2 다운로드 링크 발급 실패 ({_failure_code(exc)})", "STORAGE_URL_FAILED") from exc

    def download_files(self, files: dict) -> dict:
        out = dict(files)
        for field in FILE_NAMES:
            if files.get(field):
                out[field] = self.download_url(files[field])
        if "storyboard_images" in files:
            out["storyboard_images"] = [self.download_url(path) for path in files["storyboard_images"]]
        return out
