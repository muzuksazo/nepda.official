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
    video_model: str = "gemini-omni-1.2-flash"
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

    @property
    def auth_mode(self) -> str:
        return "vertex_ai" if self.google_genai_use_vertexai else "ai_studio"

    @property
    def resolved_scripts_dir(self) -> Path:
        return Path(self.scripts_dir).expanduser().resolve()
