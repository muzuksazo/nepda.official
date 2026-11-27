"""Environment-driven settings for the production shortform ad pipeline."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal, Optional

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
    )

    # Auth: AI Studio (`GEMINI_API_KEY`) or Vertex AI (`GOOGLE_GENAI_USE_VERTEXAI=true`)
    gemini_api_key: Optional[str] = None
    google_vertex_api_key: Optional[str] = None
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
    video_model: str = "gemini-omni-1.2-flash"
    tts_model: str = "gemini-3.8-flash-tts"
    tts_default_voice: str = "Kore"

    # Concurrency, polling & safety caps
    concurrency: int = 3
    max_video_credits_per_job: int = 180
    poll_interval_sec: float = 5.0
    video_timeout_sec: float = 600.0

    # Local filesystem paths & object storage
    work_root: str = str(_DEFAULT_DATA_ROOT / "jobs")
    output_dir: str = str(_DEFAULT_DATA_ROOT / "outputs")
    db_path: str = str(_DEFAULT_DATA_ROOT / "jobs.db")
    scripts_dir: str = str(_DEFAULT_SCRIPTS)

    # Object storage (local | s3)
    storage_backend: Literal["local", "s3"] = "local"
    s3_bucket: Optional[str] = None
    s3_endpoint_url: Optional[str] = None
    s3_region: str = "auto"
    s3_access_key_id: Optional[str] = None
    s3_secret_access_key: Optional[str] = None
    s3_prefix: str = "shortform-ad-studio"

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
    track_a_template_dir: Optional[str] = None
    track_a_template_urls: Optional[str] = None

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
