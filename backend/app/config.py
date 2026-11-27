"""Environment-driven settings for the production shortform ad pipeline."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal, Optional

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

_PROD_ROOT = Path(__file__).resolve().parents[1]
_REPO_ROOT = _PROD_ROOT.parent
_DEFAULT_SCRIPTS = _REPO_ROOT / "libraries" / "media-tools"
_IS_VERCEL = bool(os.environ.get("VERCEL"))
_DEFAULT_DATA_ROOT = Path("/tmp/napda") if _IS_VERCEL else (_PROD_ROOT / "data")


class Settings(BaseSettings):
    """Configuration supporting both AI Studio API Key and GCP Vertex AI / WIF."""

    model_config = SettingsConfigDict(
        env_file=str(_PROD_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    # Auth: AI Studio (`GEMINI_API_KEY`) or Vertex AI (`GOOGLE_GENAI_USE_VERTEXAI=true`)
    gemini_api_key: Optional[str] = None
    google_genai_use_vertexai: bool = False
    google_cloud_project: Optional[str] = None
    google_cloud_location: str = "us-central1"
    gcp_workload_identity_provider: Optional[str] = None
    gcp_service_account_email: Optional[str] = None
    gcp_billing_app_label: str = "napda"
    api_bearer_token: Optional[str] = None

    # End-user Google One Tap auth, daily beta quota & upload/retention guardrails
    google_client_id: Optional[str] = None
    session_secret: str = "dev-insecure-change-me"
    session_ttl_days: int = 7
    session_cookie_secure: bool = False
    cors_origins: str = "https://napda.vercel.app,http://localhost:5173,http://127.0.0.1:5173,http://localhost:4173,http://127.0.0.1:4173"
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
    # 나레이션 공급자(tts_provider, inworld_*)는 아래 'Shared TTS' 에 있다 (app/tts_service.py 와 hookpipe 가 같이 쓴다)

    # Concurrency, polling & safety caps
    concurrency: int = 3
    max_video_credits_per_job: int = 180
    poll_interval_sec: float = 5.0
    video_timeout_sec: float = 600.0
    # Gemini 요청 하나의 최대 대기 시간 (초). 응답 없는 호출이 작업 전체를 멈추지 않게 한다
    genai_request_timeout_sec: float = 180.0

    # Local filesystem paths & object storage
    work_root: str = str(_DEFAULT_DATA_ROOT / "jobs")
    output_dir: str = str(_DEFAULT_DATA_ROOT / "outputs")
    db_path: str = str(_DEFAULT_DATA_ROOT / "jobs.db")
    scripts_dir: str = str(_DEFAULT_SCRIPTS)

    # Object storage
    # local | s3 | r2 (r2 는 s3 와 같다: Cloudflare R2 도 S3 방식으로 접속한다. S3_* 값에 R2 엔드포인트와 키를 넣는다)
    storage_backend: Literal["local", "s3", "r2"] = "local"
    # 환경변수 이름은 S3_… 와 R2_… 둘 다 받는다 (예: R2_BUCKET 또는 S3_BUCKET)
    s3_bucket: Optional[str] = Field(default=None, validation_alias=AliasChoices("s3_bucket", "r2_bucket"))
    s3_endpoint_url: Optional[str] = Field(default=None, validation_alias=AliasChoices("s3_endpoint_url", "r2_endpoint_url"))
    s3_region: str = Field(default="auto", validation_alias=AliasChoices("s3_region", "r2_region"))
    s3_access_key_id: Optional[str] = Field(default=None, validation_alias=AliasChoices("s3_access_key_id", "r2_access_key_id"))
    s3_secret_access_key: Optional[str] = Field(
        default=None, validation_alias=AliasChoices("s3_secret_access_key", "r2_secret_access_key")
    )
    s3_prefix: str = Field(default="shortform-ad-studio", validation_alias=AliasChoices("s3_prefix", "r2_prefix"))

    # Hook video pipeline (backend/hookpipe): A/B/C 시나리오 작업자 → 영상 모델 훅 → 본편 붙이기
    hook_worker_mode: Literal["auto", "off"] = "auto"  # auto: 작업자 호출, 실패하면 planner-api
    hook_workers_dir: str = str(_PROD_ROOT / "bridge-dev")
    hook_assets_dir: str = str(_PROD_ROOT / "data" / "hook_assets")  # 미리 만든 훅 영상(prebuilt_clip)을 두는 곳
    # A 유형: template(앞부분은 미리 만든 템플릿, 착지 장면만 생성. 템플릿이 없으면 realtime 으로) | realtime
    hook_a_mode: Literal["template", "realtime"] = "template"
    # A 템플릿 위치: "storage:<경로>" 면 서버 저장소(R2)의 그 경로, 아니면 로컬 폴더. 형식은 hookpipe/a_templates.py
    hook_a_templates: str = "storage:templates/a"
    hook_worker_timeout_sec: float = 900.0
    # 시나리오 작업자의 글 모델을 Gemini 로 바꾼다 (예: gemini-4-hydrogen). 비우면 각 트랙 기본(Claude).
    # B 는 B_LLM 스위치로, C 는 hookpipe 가 같은 프롬프트·스키마로 Gemini 를 부른다. A 는 Claude 전용이라 그대로.
    hook_worker_llm: Optional[str] = None
    hook_render_mode: Literal["video_model", "dry_run"] = "video_model"  # dry_run: 과금 호출 없이 scenario.json·hook.srt 만
    hook_max_sec: float = 20.0
    hook_clip_resolution: str = "720p"
    hook_max_clip_sec_per_hook: int = 45  # 훅 하나에서 영상 모델에 요청하는 클립 길이 합 상한(과금 방어)
    body_max_sec: float = 60.0
    body_target_sec: float = 10.0  # A·B·C 공용 본편 길이 (팀 결정 2026-11-27)
    body_llm: str = "gemini-4-hydrogen"  # 본편 대본·컷 고르기 (촬영본 프레임을 보는 글 모델)
    ffmpeg_bin: Optional[str] = None
    ffprobe_bin: Optional[str] = None

    # Paddle Billing (Sandbox by default)
    paddle_environment: Literal["sandbox", "production"] = "sandbox"
    paddle_api_base_url: Optional[str] = None
    paddle_api_key: Optional[str] = None
    paddle_client_token: Optional[str] = None
    paddle_webhook_secret: Optional[str] = None
    paddle_account_email: str = "dudnjsckrgo@gmail.com"
    paddle_price_c30: Optional[str] = None
    paddle_price_c100: Optional[str] = None
    paddle_price_c300: Optional[str] = None
    paddle_webhook_tolerance_sec: int = 300
    credits_per_video: int = 12
    initial_free_videos: int = 1

    # Shared TTS, body pipeline, upload validation & media delivery
    tts_provider: Literal["inworld", "gemini"] = "inworld"
    inworld_api_key: Optional[str] = None
    inworld_voice_id: str = "scarlet-mango-0605__gangsangyun"
    inworld_model: str = "inworld-tts-2"
    inworld_speaking_rate: float = 1.1
    hook_burn_captions: bool = True
    require_uploaded_object_exists: bool = False
    media_url_ttl_sec: int = 3600

    @property
    def auth_mode(self) -> str:
        return "vertex_ai" if self.google_genai_use_vertexai else "ai_studio"

    @property
    def resolved_scripts_dir(self) -> Path:
        return Path(self.scripts_dir).expanduser().resolve()

    @property
    def resolved_paddle_api_base_url(self) -> str:
        if self.paddle_api_base_url and self.paddle_api_base_url.strip():
            return self.paddle_api_base_url.strip().rstrip("/")
        return (
            "https://sandbox-api.paddle.com"
            if self.paddle_environment == "sandbox"
            else "https://api.paddle.com"
        )
