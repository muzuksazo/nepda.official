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
    "HOOK_RENDERING",
    "HOOK_READY",
    "RENDERING",
    "DELIVERABLE_READY",
    "FAILED",
]
HookStatus = Literal["queued", "running", "done", "failed"]
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
    verified_facts: List[str] = Field(default_factory=list, max_length=20)
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
        return [s.strip() for s in items if isinstance(s, str) and s.strip()]


class ProductInfoRequest(BaseModel):
    product: ProductInput
    source_url: Optional[str] = Field(default=None, max_length=2048)


class ProductInfoResponse(BaseModel):
    product_info_id: str
    product: ProductInput
    cached: bool
    cached_at: str
    expires_at: str


class CreateProjectRequest(BaseModel):
    product: Optional[ProductInput] = None
    selected_types: List[HookType] = Field(..., min_length=1, max_length=3)
    flow_mode: FlowMode = "guide_first"
    product_info_id: Optional[str] = None

    @field_validator("selected_types")
    @classmethod
    def _dedupe_types(cls, vals: List[HookType]) -> List[HookType]:
        seen = []
        for t in vals:
            if t not in seen:
                seen.append(t)
        return seen

    @model_validator(mode="after")
    def _require_product_or_cache_id(self) -> "CreateProjectRequest":
        if self.product is None and not (self.product_info_id and self.product_info_id.strip()):
            raise ValueError("Provide either product or product_info_id")
        return self


class ProjectSummary(BaseModel):
    project_id: str
    status: ProjectStatus
    flow_mode: FlowMode
    product_name: str
    category: ProductCategory
    selected_types: List[HookType]
    selected_scenario_id: Optional[str] = None
    latest_job_id: Optional[str] = None
    thumbnail_url: Optional[str] = None
    is_public: bool = False
    expires_at: str
    created_at: str
    updated_at: str


class ProjectListResponse(BaseModel):
    projects: List[ProjectSummary]
    quota: QuotaStatus
    total: int = 0
    offset: int = 0
    limit: int = 50
    has_more: bool = False
    next_offset: Optional[int] = None


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
    model: Optional[str] = Field(default=None, max_length=120)
    count: int = Field(default=1, ge=1, le=5)


class GenerateScenariosResponse(BaseModel):
    project_id: str
    status: ProjectStatus
    scenarios: List[ScenarioItem]
    round: int = Field(default=1, ge=1)


class SelectScenarioResponse(BaseModel):
    project_id: str
    selected_scenario_id: str


class HookTts(BaseModel):
    enabled: bool = True
    voice: Optional[str] = None


class CreateHookRequest(BaseModel):
    scenario_id: str
    tts: HookTts = Field(default_factory=HookTts)


class CreateHookResponse(BaseModel):
    hook_id: str
    job_id: str
    status: HookStatus


class HookFiles(BaseModel):
    hook_video: Optional[str] = None
    tts_audio: Optional[str] = None
    subtitles_srt: Optional[str] = None
    scenario_json: Optional[str] = None
    storyboard_images: List[str] = Field(default_factory=list)


class HookStatusResponse(BaseModel):
    hook_id: str
    status: HookStatus
    files: HookFiles
    output_dir: Optional[str] = None
    error: Optional[str] = None


class OutputItem(BaseModel):
    hook_id: str
    scenario_id: Optional[str] = None
    output_dir: str
    files: HookFiles = Field(default_factory=HookFiles)
    created_at: Optional[str] = None


class OutputsResponse(BaseModel):
    project_id: str
    outputs: List[OutputItem]


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
    deducted_credits: int = 0
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
    style: str = "invert-box"
    highlight_word: Optional[str] = None
    candidate_image_urls: List[str] = Field(default_factory=list)
    candidate_keys: List[str] = Field(default_factory=list)
    style_previews: Dict[str, str] = Field(default_factory=dict)


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
    is_public: bool = False
    public_caption: Optional[str] = None
    quota: QuotaStatus
    expires_at: str
    created_at: str
    updated_at: str


class PublishProjectRequest(BaseModel):
    is_public: bool
    caption: Optional[str] = Field(default=None, max_length=200)


class PublishProjectResponse(BaseModel):
    project_id: str
    is_public: bool
    caption: Optional[str] = None


class CommunityVideoItem(BaseModel):
    id: str
    project_id: str
    hook_type: HookType
    title: str
    caption: str = ""
    product_name: str
    creator_name: str
    thumbnail_url: Optional[str] = None
    video_url: Optional[str] = None
    like_count: int = 0
    created_at: str


class CommunityVideosResponse(BaseModel):
    items: List[CommunityVideoItem] = Field(default_factory=list)


CreditPackageId = Literal["c30", "c100", "c300"]
BillingOrderStatus = Literal["pending", "completed", "failed", "canceled"]
PaddleEnvironment = Literal["sandbox", "production"]


class CreditPackageResponse(BaseModel):
    id: CreditPackageId
    credits: int
    price: int
    currency: str = "KRW"
    is_popular: bool = False
    paddle_price_id: Optional[str] = None


class BillingConfigResponse(BaseModel):
    provider: Literal["paddle"] = "paddle"
    environment: PaddleEnvironment = "sandbox"
    enabled: bool = False
    client_token: Optional[str] = None
    credits_per_video: int = 12
    packages: List[CreditPackageResponse]


class WalletResponse(BaseModel):
    credits: int
    has_free_video: bool
    free_videos_remaining: int


class CreateCheckoutRequest(BaseModel):
    package_id: CreditPackageId


class CreateCheckoutResponse(BaseModel):
    order_id: str
    package_id: CreditPackageId
    credits: int
    amount_krw: int
    currency: str = "KRW"
    paddle_environment: PaddleEnvironment
    paddle_client_token: str
    paddle_price_id: str
    paddle_transaction_id: str
    checkout_url: Optional[str] = None
    customer_email: Optional[str] = None
    status: BillingOrderStatus


class BillingOrderStatusResponse(BaseModel):
    order_id: str
    package_id: CreditPackageId
    credits: int
    amount_krw: int
    status: BillingOrderStatus
    paddle_transaction_id: Optional[str] = None
    wallet: WalletResponse
    completed_at: Optional[str] = None


class PaddleWebhookAckResponse(BaseModel):
    received: bool = True
    event_id: Optional[str] = None
    event_type: Optional[str] = None
    credited: bool = False
    order_id: Optional[str] = None
