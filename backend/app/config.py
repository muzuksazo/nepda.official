"""Environment-driven settings for the production shortform ad pipeline."""

from __future__ import annotations

from pathlib import Path
from typing import Literal, Optional

from pydantic_settings import BaseSettings, SettingsConfigDict

_PROD_ROOT = Path(__file__).resolve().parents[1]
_REPO_ROOT = _PROD_ROOT.parent
_DEFAULT_SCRIPTS = _REPO_ROOT / "libraries" / "media-tools"


class Settings(BaseSettings):
    """Configuration supporting both AI Studio API Key and GCP Vertex AI / WIF."""

    model_config = SettingsConfigDict(
        env_file=str(_PROD_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Auth: AI Studio (`GEMINI_API_KEY`) or Vertex AI (`GOOGLE_GENAI_USE_VERTEXAI=true`)
    gemini_api_key: Optional[str] = None
    google_genai_use_vertexai: bool = False
    google_cloud_project: Optional[str] = None
    google_cloud_location: str = "us-central1"
    api_bearer_token: Optional[str] = None

    # End-user Google One Tap auth, daily beta quota & upload/retention guardrails
    google_client_id: Optional[str] = None
    session_secret: str = "dev-insecure-change-me"
    session_ttl_days: int = 7
    retention_ttl_days: int = 7
    daily_render_limit: int = 3
    max_upload_file_bytes: int = 100 * 1024 * 1024
    min_upload_total_sec: float = 5.0
    max_upload_total_sec: float = 90.0
    product_info_cache_ttl_sec: int = 3600
    planner_base_url: str = "http://127.0.0.1:8787"

    # Default models (overridable via env vars)
    planner_model: str = "gemini-3.5-flash"
    image_model: str = "gemini-nano-banana-2.1"
    video_model: str = "gemini-omni-flash-preview"  # AI Studio 키로 models.list 에서 확인한 이름 (2026-11-27)
    tts_model: str = "gemini-3.8-flash-tts"
    tts_default_voice: str = "Kore"

    # Concurrency, polling & safety caps
    concurrency: int = 3
    max_video_credits_per_job: int = 180
    poll_interval_sec: float = 5.0
    video_timeout_sec: float = 600.0

    # Local filesystem paths & object storage
    work_root: str = str(_PROD_ROOT / "data" / "jobs")
    output_dir: str = str(_PROD_ROOT / "data" / "outputs")
    db_path: str = str(_PROD_ROOT / "data" / "jobs.db")
    scripts_dir: str = str(_DEFAULT_SCRIPTS)

    storage_backend: Literal["local", "s3"] = "local"
    s3_bucket: Optional[str] = None
    s3_endpoint_url: Optional[str] = None
    s3_region: str = "auto"
    s3_access_key_id: Optional[str] = None
    s3_secret_access_key: Optional[str] = None
    s3_prefix: str = "shortform-ad-studio"

    # Hook video pipeline (backend/hookpipe): A/B/C 시나리오 작업자 → 영상 모델 훅 → 본편 붙이기
    hook_worker_mode: Literal["auto", "off"] = "auto"  # auto: 작업자 호출, 실패하면 planner-api
    hook_workers_dir: str = str(_PROD_ROOT / "bridge-dev")
    hook_assets_dir: str = str(_PROD_ROOT / "data" / "hook_assets")  # 미리 만든 훅 영상(prebuilt_clip)을 두는 곳
    hook_worker_timeout_sec: float = 900.0
    # 시나리오 작업자의 글 모델을 Gemini 로 바꾼다 (예: gemini-4-hydrogen). 비우면 각 트랙 기본(Claude).
    # B 는 B_LLM 스위치로, C 는 hookpipe 가 같은 프롬프트·스키마로 Gemini 를 부른다. A 는 Claude 전용이라 그대로.
    hook_worker_llm: Optional[str] = None
    hook_render_mode: Literal["video_model", "dry_run"] = "video_model"  # dry_run: 과금 호출 없이 scenario.json·hook.srt 만
    hook_max_sec: float = 20.0
    hook_clip_resolution: str = "720p"
    hook_burn_captions: bool = True
    hook_max_clip_sec_per_hook: int = 45  # 훅 하나에서 영상 모델에 요청하는 클립 길이 합 상한(과금 방어)
    body_max_sec: float = 60.0
    ffmpeg_bin: Optional[str] = None
    ffprobe_bin: Optional[str] = None

    @property
    def auth_mode(self) -> str:
        return "vertex_ai" if self.google_genai_use_vertexai else "ai_studio"

    @property
    def resolved_scripts_dir(self) -> Path:
        return Path(self.scripts_dir).expanduser().resolve()
