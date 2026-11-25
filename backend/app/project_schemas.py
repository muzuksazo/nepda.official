"""Pydantic v2 request/response contracts for NAPDA PRD v0.2 MVP endpoints."""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

ProductCategory = Literal["living", "kitchen", "stationery"]
HookType = Literal["A", "B", "C"]
FlowMode = Literal["guide_first", "skip_drafts"]
ProjectStatus = Literal[
    "PRODUCT_SAVED",
    "SCENARIOS_READY",
    "STORYBOARD_READY",
    "GUIDE_READY",
    "UPLOADS_READY",
    "RENDERING",
    "DELIVERABLE_READY",
    "FAILED",
]
PlannerProvider = Literal["anthropic", "google"]
RenderResolution = Literal["360p", "720p"]


class GoogleAuthRequest(BaseModel):
    credential: str = Field(..., min_length=1, description="Google One Tap or GIS ID Token (JWT)")


class AuthUserResponse(BaseModel):
    user_id: str
    email: str
    name: Optional[str] = None
    picture: Optional[str] = None


class QuotaStatus(BaseModel):
    daily_limit: int
    used_today: int
    remaining_today: int
    resets_at: str


class GoogleAuthResponse(BaseModel):
    user: AuthUserResponse
    access_token: str
    token_type: Literal["Bearer"] = "Bearer"
    expires_at: str
    quota: QuotaStatus


class AuthMeResponse(BaseModel):
    user: AuthUserResponse
    quota: QuotaStatus


class HookTypeMeta(BaseModel):
    type: HookType
    name: str
    track_archetype: str
    product_relation: str
    replacement_test: str
    example_hook: str


class HookTypesResponse(BaseModel):
    types: List[HookTypeMeta]


class ProductInput(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    category: ProductCategory
    verified_facts: List[str] = Field(..., min_length=1, max_length=20)
    one_liner: Optional[str] = Field(default=None, max_length=240)
    price_or_offer: Optional[str] = Field(default=None, max_length=120)
    target_audience: Optional[str] = Field(default=None, max_length=120)

    @field_validator("name")
    @classmethod
    def _strip_name(cls, v: str) -> str:
        clean = v.strip()
        if not clean:
            raise ValueError("product.name must not be blank")
        return clean

    @field_validator("verified_facts")
    @classmethod
    def _clean_facts(cls, items: List[str]) -> List[str]:
        cleaned = [s.strip() for s in items if isinstance(s, str) and s.strip()]
        if not cleaned:
            raise ValueError("At least 1 non-empty verified_fact is required")
        return cleaned


class CreateProjectRequest(BaseModel):
    product: ProductInput
    selected_types: List[HookType] = Field(..., min_length=1, max_length=3)
    flow_mode: FlowMode = "guide_first"

    @field_validator("selected_types")
    @classmethod
    def _dedupe_types(cls, vals: List[HookType]) -> List[HookType]:
        seen = []
        for t in vals:
            if t not in seen:
                seen.append(t)
        return seen


class ProjectSummary(BaseModel):
    project_id: str
    status: ProjectStatus
    flow_mode: FlowMode
    product_name: str
    category: ProductCategory
    selected_types: List[HookType]
    selected_scenario_id: Optional[str] = None
    latest_job_id: Optional[str] = None
    expires_at: str
    created_at: str
    updated_at: str


class ProjectListResponse(BaseModel):
    projects: List[ProjectSummary]
    quota: QuotaStatus


class ScenarioBeat(BaseModel):
    order: int
    role: str
    duration_sec: float
    visual: str
    narration: str = ""
    caption: str = ""


class StoryboardFrame(BaseModel):
    beat_order: int
    image_url: str
    caption: str = ""


class ScenarioItem(BaseModel):
    scenario_id: str
    type: HookType
    hook_title: str
    hook_duration_sec: float
    body_duration_sec: float
    replacement_test_note: str
    beats: List[ScenarioBeat]
    storyboard_frames: List[StoryboardFrame] = Field(default_factory=list)
    ad_spec: Dict[str, Any] = Field(default_factory=dict)


class GenerateScenariosRequest(BaseModel):
    types: Optional[List[HookType]] = Field(default=None, min_length=1, max_length=3)
    provider: PlannerProvider = "anthropic"


class GenerateScenariosResponse(BaseModel):
    project_id: str
    status: ProjectStatus
    scenarios: List[ScenarioItem]


class GenerateStoryboardRequest(BaseModel):
    visual_style: str = "default"


class StoryboardResponse(BaseModel):
    project_id: str
    scenario_id: str
    status: ProjectStatus
    frames: List[StoryboardFrame]


class CreateFilmingGuideRequest(BaseModel):
    scenario_id: str = Field(..., min_length=1)


class FilmingGuideShot(BaseModel):
    shot_no: int
    title: str
    duration_sec: float
    framing_tip: str
    fact_ref: str


class FilmingGuideResponse(BaseModel):
    project_id: str
    status: ProjectStatus
    selected_scenario_id: str
    target_body_duration_sec: float
    shots: List[FilmingGuideShot]


class EstimateRequest(BaseModel):
    scenario_id: Optional[str] = None
    selected_type: Optional[HookType] = None
    resolution: RenderResolution = "720p"


class StageCreditItem(BaseModel):
    stage: str
    description: str
    estimated_credits: int


class EstimateResponse(BaseModel):
    project_id: str
    resolution: RenderResolution
    total_estimated_credits: int
    stages: List[StageCreditItem]
    quota: QuotaStatus


class UploadClipInput(BaseModel):
    shot_no: int = Field(..., ge=1, le=20)
    object_key: str = Field(..., min_length=1)
    file_size_bytes: Optional[int] = Field(default=None, ge=1)
    duration_sec: Optional[float] = Field(default=None, gt=0.0)
    width: Optional[int] = Field(default=None, ge=1)
    height: Optional[int] = Field(default=None, ge=1)
    local_path: Optional[str] = None


class CompleteUploadsRequest(BaseModel):
    clips: List[UploadClipInput] = Field(..., min_length=1, max_length=20)


class UploadWarning(BaseModel):
    shot_no: int
    code: str
    message: str


class UploadClipMetadata(BaseModel):
    shot_no: int
    object_key: str
    duration_sec: float
    width: int
    height: int
    recommended_framing: str


class CompleteUploadsResponse(BaseModel):
    project_id: str
    status: ProjectStatus
    upload_status: Literal["VALIDATED", "WARNING"]
    total_duration_sec: float
    warnings: List[UploadWarning]
    metadata: List[UploadClipMetadata]


class CreateRenderRequest(BaseModel):
    scenario_id: Optional[str] = None
    skip_drafts: bool = False
    selected_type: Optional[HookType] = None
    voice_id: str = "Kore"
    resolution: RenderResolution = "720p"
    dry_run: bool = False

    @model_validator(mode="after")
    def _validate_target(self) -> "CreateRenderRequest":
        if not self.scenario_id and not (self.skip_drafts and self.selected_type):
            raise ValueError(
                "Provide scenario_id, or set skip_drafts=true with a single selected_type (A|B|C)"
            )
        return self


class CreateRenderResponse(BaseModel):
    project_id: str
    job_id: str
    status: str
    selected_type: HookType
    estimated_credits: int
    quota: QuotaStatus
    expires_at: str


class DeliverableVideo(BaseModel):
    stream_url: Optional[str] = None
    download_url: Optional[str] = None
    clean_download_url: Optional[str] = None
    srt_url: Optional[str] = None
    duration_sec: Optional[float] = None
    width: Optional[int] = None
    height: Optional[int] = None
    lufs: Optional[float] = None


class DeliverableThumbnail(BaseModel):
    image_url: Optional[str] = None
    download_url: Optional[str] = None
    safe_zone_1_1_ok: Optional[bool] = None
    headline_lines: List[str] = Field(default_factory=list)


class AIDisclosureInfo(BaseModel):
    has_ai_generated_media: bool = True
    label_text: str = "AI 연출 포함"
    instagram_guide: str = "인스타그램 게시 시 'AI 정보' 라벨 활성화를 권장합니다."


class DeliverablesResponse(BaseModel):
    project_id: str
    job_id: Optional[str] = None
    status: str
    video: Optional[DeliverableVideo] = None
    thumbnail: Optional[DeliverableThumbnail] = None
    ai_disclosure: AIDisclosureInfo
    expires_at: str


class ProjectDetailResponse(BaseModel):
    project_id: str
    status: ProjectStatus
    flow_mode: FlowMode
    product: ProductInput
    selected_types: List[HookType]
    selected_scenario_id: Optional[str] = None
    scenarios: List[ScenarioItem] = Field(default_factory=list)
    filming_guide: Optional[FilmingGuideResponse] = None
    uploads: Optional[CompleteUploadsResponse] = None
    latest_job_id: Optional[str] = None
    latest_job: Optional[Dict[str, Any]] = None
    quota: QuotaStatus
    expires_at: str
    created_at: str
    updated_at: str
