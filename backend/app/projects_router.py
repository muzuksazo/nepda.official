"""NAPDA PRD v0.2 router: Google One Tap auth, projects, scenarios, uploads, quota, deliverables."""

from __future__ import annotations

import json
import os
import random
import re
import shutil
import subprocess
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Query, Request, Response, status

from .auth import (
    SESSION_COOKIE_NAME,
    AuthenticatedUser,
    AuthenticationError,
    issue_session_token,
    verify_google_id_token,
    verify_session_token,
)
from .config import Settings
from .filming_guide_service import build_filming_guide
from .genai_provider import GenAIMediaProvider
from .media_delivery import resolve_media_url
from .paddle_billing import (
    HttpxPaddleApiClient,
    PaddleApiClient,
    PaddleApiError,
    get_credit_packages,
    verify_paddle_webhook_signature,
)
from .pipeline import CampaignRequest, ProductionPipeline
from .product_enrichment import enrich_product_with_source_url
from .project_schemas import (
    AIDisclosureInfo,
    AuthMeResponse,
    AuthUserResponse,
    BillingConfigResponse,
    BillingOrderStatusResponse,
    CompleteUploadsRequest,
    CompleteUploadsResponse,
    CreateCheckoutRequest,
    CreateCheckoutResponse,
    CreateFilmingGuideRequest,
    CreateHookRequest,
    CreateHookResponse,
    CreateProjectRequest,
    CreateRenderRequest,
    CreateRenderResponse,
    CreditPackageResponse,
    DeliverablesResponse,
    DeliverableThumbnail,
    DeliverableVideo,
    EstimateRequest,
    EstimateResponse,
    FilmingGuideResponse,
    FilmingGuideShot,
    GenerateScenariosRequest,
    GenerateScenariosResponse,
    GenerateStoryboardRequest,
    GoogleAuthRequest,
    GoogleAuthResponse,
    HookFiles,
    HookStatusResponse,
    HookTypeMeta,
    HookTypesResponse,
    OutputItem,
    OutputsResponse,
    PaddleWebhookAckResponse,
    ProductInfoRequest,
    ProductInfoResponse,
    ProductInput,
    ProjectDetailResponse,
    ProjectListResponse,
    ProjectSummary,
    QuotaStatus,
    ScenarioBeat,
    ScenarioItem,
    SelectScenarioResponse,
    StageCreditItem,
    StoryboardFrame,
    StoryboardResponse,
    UploadClipMetadata,
    UploadWarning,
    WalletResponse,
)
from .project_store import ProjectStore
from .retention import is_project_expired, sync_project_status_with_job
from .storage import StorageBackend
from .store import JobStore
from .thumbnail_service import generate_project_thumbnail
from .tts_service import build_tts_provider
from .upload_service import validate_and_complete_uploads

GoogleTokenVerifier = Callable[[str, str], AuthenticatedUser]
ScenarioGenerator = Callable[[Dict[str, Any], List[str], str], List[Dict[str, Any]]]
StoryboardGenerator = Callable[[Dict[str, Any], Dict[str, Any], str], List[Dict[str, Any]]]

_TRACK_BY_TYPE = {
    "A": "A_bgrade_reversal",
    "B": "B_info_hook_offset",
    "C": "C_direct_proof",
}

HOOK_TYPE_CATALOG: List[HookTypeMeta] = [
    HookTypeMeta(
        type="A",
        name="제품과 무관한 훅 (A안)",
        track_archetype="A_bgrade_reversal",
        product_relation="제품과 직접 관련 없는 상황·장르로 시작",
        replacement_test="훅만 봐서는 제품을 유추할 수 없으며, 다른 제품 광고의 본편에도 그대로 연결할 수 있음",
        example_hook="어젯밤 밀실 금고에 보관된 흔적이 1초 만에 감쪽같이 사라졌습니다",
    ),
    HookTypeMeta(
        type="B",
        name="약하게 짐작할 수 있는 정보성 훅 (B안)",
        track_archetype="B_info_hook_offset",
        product_relation="자연·물리·생활 원리로 시작해 전환 장면에서 제품과 연결",
        replacement_test="보는 동안은 순수 정보처럼 보이다가, 광고를 다 본 뒤 '아 이런 원리 유사도였구나' 하고 이해되며 전환 장면만 바꾸면 다른 제품에도 이식 가능",
        example_hook="뇌도 심장도 없는데 6억 년 넘게 살아남은 바다의 원시 생명체는 구멍으로 모든 걸 빨아들입니다",
    ),
    HookTypeMeta(
        type="C",
        name="직관적 해결/불편 직격 훅 (C안)",
        track_archetype="C_direct_proof",
        product_relation="타깃이 겪는 불편과 제품 핵심 장점을 첫 컷부터 직결",
        replacement_test="첫 3초 훅만 봐도 어떤 제품/카테고리 광고인지 바로 유추되며 다른 제품 광고로 옮겨 붙이기 어려움",
        example_hook="행주로 닦아도 물자국만 번지고 금방 찝찝해지죠",
    ),
]


def _api_error(
    status_code: int,
    code: str,
    message: str,
    details: Optional[Dict[str, Any]] = None,
) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"error": {"code": code, "message": message, "details": details or {}}},
    )


def _product_to_facts_md(product: Dict[str, Any]) -> str:
    lines = [
        f"# Product Facts — {product.get('name', 'Product')}",
        f"- Category: {product.get('category', 'living')}",
    ]
    if product.get("price_or_offer"):
        lines.append(f"- Offer: {product['price_or_offer']}")
    if product.get("target_audience"):
        lines.append(f"- Target Audience: {product['target_audience']}")
    lines.append("")
    facts = [str(f).strip() for f in (product.get("verified_facts") or []) if str(f).strip()]
    if not facts:
        facts = [f"{product.get('name', '제품')} 실물 시연 기반"]
    for idx, fact in enumerate(facts, start=1):
        lines.append(f"- [F{idx:02d}] [VERIFIED] {fact}")
    return "\n".join(lines) + "\n"


def _probe_local_video(local_path: str) -> Tuple[float, int, int]:
    proc = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration:stream=codec_type,width,height",
            "-of",
            "json",
            local_path,
        ],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {proc.stderr}")
    raw = json.loads(proc.stdout or "{}")
    dur = float((raw.get("format") or {}).get("duration") or 0.0)
    vs = next((s for s in (raw.get("streams") or []) if s.get("codec_type") == "video"), {})
    return dur, int(vs.get("width") or 0), int(vs.get("height") or 0)


def _recommended_framing(w: int, h: int) -> str:
    if w <= 0 or h <= 0:
        return "full-bleed"
    ratio = w / h
    if ratio < 0.72:
        return "full-bleed"
    if ratio <= 0.92:
        return "smart-crop"
    return "blur-bleed"


def _build_default_ad_spec(
    project: Dict[str, Any],
    hook_type: str,
    *,
    source_video: str,
    source_duration: float,
    voice_id: str,
) -> Dict[str, Any]:
    product = project["product"]
    facts = product.get("verified_facts") or ["실물 시연 제품"]
    track = _TRACK_BY_TYPE.get(hook_type, "C_direct_proof")
    pid = project["project_id"]
    first_fact = facts[0][:18]
    safe_dur = max(5.0, float(source_duration or 5.0))
    hook_dur = 9.0
    h1_dur = min(4.5, safe_dur)
    h2_dur = hook_dur - h1_dur
    h2_start = max(0.0, round(safe_dur - h2_dur, 3))
    p1_dur = min(3.5, safe_dur)
    p2_dur = 7.0 - p1_dur
    p2_start = max(0.0, round(safe_dur - p2_dur, 3))
    timeline = [
        {
            "id": f"{hook_type}_hook_01",
            "type": "source",
            "src_start": 0.0,
            "src_end": round(h1_dur, 3),
            "framing": "full-bleed",
            "audio_owner": "mute",
        },
        {
            "id": f"{hook_type}_hook_02",
            "type": "source",
            "src_start": h2_start,
            "src_end": round(h2_start + h2_dur, 3),
            "framing": "full-bleed",
            "audio_owner": "mute",
        },
        {"id": "twist_pause", "type": "silence_gap", "duration": 0.25, "audio_owner": "silence"},
        {
            "id": f"{hook_type}_payoff_01",
            "type": "source",
            "src_start": 0.0,
            "src_end": round(p1_dur, 3),
            "framing": "full-bleed",
            "audio_owner": "mute",
            "fact_ids": ["F01"],
        },
        {
            "id": f"{hook_type}_payoff_02",
            "type": "source",
            "src_start": p2_start,
            "src_end": round(p2_start + p2_dur, 3),
            "framing": "full-bleed",
            "audio_owner": "mute",
            "fact_ids": ["F01"],
        },
    ]
    if hook_type == "A":
        cap1 = "흔적 없이 사라진 미스터리"
        genre_extra: Dict[str, Any] = {
            "a_genre_archetype": "absurd_skit",
            "product_taboo_keywords": [product["name"].split()[0]],
        }
    elif hook_type == "B":
        cap1 = "6억 년 살아남은 구조의 원리"
        genre_extra = {"hook_similarity_score": 0.45}
    else:
        cap1 = f"{product['name']} 실물 확인"
        genre_extra = {}

    return {
        "project_id": f"{pid}-{hook_type}",
        "output_stem": f"napda_{pid}_{hook_type}",
        "title": f"{product['name']} ({hook_type}안)",
        "mode": "narrative_master",
        "track_archetype": track,
        **genre_extra,
        "hook_window_sec": hook_dur,
        "framing_mode": "full-bleed",
        "disclosure": "ai_assisted",
        "source_video": source_video,
        "source_duration": max(source_duration, safe_dur),
        "allow_static_intro": True,
        "vo_audio": f"audio/vo_{voice_id}.wav",
        "usps": [{"title": first_fact, "fact_ids": ["F01"]}],
        "timeline": timeline,
        "captions": [
            {"start": 0.0, "end": 4.4, "text": cap1},
            {"start": 4.5, "end": 8.9, "text": "아무도 몰랐던 구조"},
            {"start": 9.3, "end": 16.0, "text": first_fact, "is_cta": True},
        ],
        "cta": {"type": "comment_engagement", "copy": "어떠신가요?", "fact_ids": ["F01"]},
    }


def _load_track_a_manifest_entries(settings: Settings) -> List[Dict[str, Any]]:
    """Load validated Track A visual template metadata entries from configured or default dirs."""
    dirs: List[Path] = []
    if settings.track_a_template_dir and settings.track_a_template_dir.strip():
        dirs.append(Path(settings.track_a_template_dir).expanduser().resolve())
    dirs.append((Path(__file__).resolve().parents[1] / "data" / "templates" / "track_a").resolve())

    entries: List[Dict[str, Any]] = []
    seen_dirs: set[Path] = set()
    for d in dirs:
        if d in seen_dirs or not d.is_dir():
            continue
        seen_dirs.add(d)
        manifest_path = d / "manifest.json"
        if not manifest_path.is_file():
            continue
        try:
            raw = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(raw, list):
            continue
        for item in raw:
            if not isinstance(item, dict):
                continue
            fname = str(item.get("filename") or "").strip()
            if not fname:
                continue
            video_path = (d / fname).resolve()
            if not video_path.is_file():
                continue
            enriched = dict(item)
            enriched["path"] = str(video_path)
            entries.append(enriched)
    return entries


def _unescape_newlines(text: Any) -> str:
    """Normalize double-escaped JSON newlines (`\\n`) into real newlines."""
    return str(text or "").replace("\\n", "\n")


def _clean_caption_display(text: Any) -> str:
    """Flatten caption newlines and strip emphasis markers for UI cards."""
    cleaned = _unescape_newlines(text).replace("\r", "")
    cleaned = re.sub(r"\*\*(.+?)\*\*", r"\1", cleaned)
    cleaned = re.sub(r"\n+", " ", cleaned)
    return re.sub(r"[ \t]{2,}", " ", cleaned).strip()


def _default_scenario_generator(settings: Settings) -> ScenarioGenerator:
    def _generate(project: Dict[str, Any], hook_types: List[str], provider: str) -> List[Dict[str, Any]]:
        product = project["product"]
        facts_md = _product_to_facts_md(product)
        manifest_entries = _load_track_a_manifest_entries(settings)
        tpl_entry = manifest_entries[0] if manifest_entries else None
        scenarios: List[Dict[str, Any]] = []
        with httpx.Client(timeout=60.0) as client:
            for ht in hook_types:
                track = _TRACK_BY_TYPE[ht]
                try:
                    name_tokens = [
                        tok.strip()
                        for tok in re.split(r"[\s,./()\-]+", str(product.get("name") or ""))
                        if len(tok.strip()) >= 2
                    ]
                    forbidden_clause = (
                        f" Strictly forbid these words before silence_gap: {', '.join(name_tokens)}."
                        if name_tokens
                        else ""
                    )
                    if ht == "A" and tpl_entry:
                        tpl_dur = float(tpl_entry.get("duration_sec") or 9.88)
                        tpl_summary = str(tpl_entry.get("visual_summary") or "").strip()
                        extra_notes = (
                            f"Narrative Track A (16-18s total): {tpl_dur:.2f}s hook_window_sec pre-prepared "
                            f"3D physics template opener ({tpl_summary}) "
                            "-> 0.25s silence_gap twist -> 6.5-7.0s product payoff from source cuts "
                            "(payoff <= 45% of total runtime). "
                            "Never mention product or category words before silence_gap."
                            f"{forbidden_clause}"
                        )
                    elif ht == "A":
                        extra_notes = (
                            "Narrative Track A (16-18s total): 9.0s hook_window_sec pre-prepared visual template opener "
                            "-> 0.25s silence_gap twist -> 6.5-7.0s product payoff from source cuts (payoff <= 45% of total runtime). "
                            "Never mention product or category words before silence_gap."
                            f"{forbidden_clause}"
                        )
                    else:
                        extra_notes = ""
                    resp = client.post(
                        f"{settings.planner_base_url.rstrip('/')}/v1/plan",
                        json={
                            "provider": provider,
                            "request": {
                                "projectId": f"{project['project_id']}-{ht}",
                                "productFacts": facts_md,
                                "sourceVideo": "source/pending_upload.mp4",
                                "sourceDuration": 15.0,
                                "trackArchetype": track,
                                "visualStyle": "blender_3d_cutaway" if ht == "B" else "blender_clay_diorama",
                                **({"extraNotes": extra_notes} if extra_notes else {}),
                            },
                        },
                    )
                    resp.raise_for_status()
                except Exception as exc:
                    raise _api_error(
                        status.HTTP_502_BAD_GATEWAY,
                        "PLANNER_UNAVAILABLE",
                        f"기획 서버({settings.planner_base_url}) 응답에 실패했습니다: {exc}",
                    ) from exc

                data = resp.json()
                spec = data.get("spec") or {}
                if ht == "A" and tpl_entry:
                    spec["track_a_template_id"] = str(tpl_entry.get("id") or "")
                    spec["a_genre_archetype"] = str(tpl_entry.get("a_genre_archetype") or "mock_documentary")
                caps = spec.get("captions") or []
                for c in caps:
                    if isinstance(c, dict) and "text" in c:
                        c["text"] = _unescape_newlines(c.get("text"))
                tl = spec.get("timeline") or []
                beats = [
                    {
                        "order": i + 1,
                        "role": seg.get("type", "beat"),
                        "duration_sec": float(seg.get("duration") or 5.0),
                        "visual": seg.get("flow_ref_prompt") or seg.get("id") or "촬영 장면",
                        "narration": caps[i]["text"] if i < len(caps) else "",
                        "caption": caps[i]["text"] if i < len(caps) else "",
                    }
                    for i, seg in enumerate(tl)
                ]
                meta = next(m for m in HOOK_TYPE_CATALOG if m.type == ht)
                scenarios.append(
                    {
                        "scenario_id": f"scn_{ht}_{uuid.uuid4().hex[:6]}",
                        "type": ht,
                        "hook_title": spec.get("title") or f"{product['name']} {ht}안",
                        "hook_duration_sec": float(spec.get("hook_window_sec") or 9.0),
                        "body_duration_sec": 15.0,
                        "replacement_test_note": meta.replacement_test,
                        "beats": beats,
                        "storyboard_frames": [],
                        "ad_spec": spec,
                    }
                )
        return scenarios

    return _generate


def _default_storyboard_generator(
    settings: Settings, storage: StorageBackend
) -> StoryboardGenerator:
    def _extract_track_a_storyboard(
        project: Dict[str, Any], scenario: Dict[str, Any]
    ) -> Optional[List[Dict[str, Any]]]:
        manifest_entries = _load_track_a_manifest_entries(settings)
        tpl_id = str((scenario.get("ad_spec") or {}).get("track_a_template_id") or "").strip()
        tpl_entry = next(
            (e for e in manifest_entries if tpl_id and e.get("id") == tpl_id),
            manifest_entries[0] if manifest_entries else None,
        )
        if not tpl_entry:
            return None
        tpl_path = Path(str(tpl_entry.get("path") or ""))
        if not tpl_path.is_file():
            return None

        tpl_dur = float(tpl_entry.get("duration_sec") or 9.8)
        try:
            probe = subprocess.run(
                [
                    "ffprobe",
                    "-v",
                    "error",
                    "-show_entries",
                    "format=duration",
                    "-of",
                    "default=nw=1:nk=1",
                    str(tpl_path),
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            probed_dur = float((probe.stdout or "").strip() or "0")
            if probed_dur > 0.5:
                tpl_dur = probed_dur
        except Exception:
            pass

        out_dir = (
            Path(settings.work_root).resolve()
            / project["project_id"]
            / "storyboards"
            / scenario["scenario_id"]
        )
        out_dir.mkdir(parents=True, exist_ok=True)

        non_silence = [
            b for b in (scenario.get("beats") or []) if b.get("role") != "silence_gap"
        ]
        raw_caps = [
            _clean_caption_display(b.get("caption") or b.get("narration") or b.get("visual") or "")
            for b in non_silence
        ]
        default_hook_caps = [
            _clean_caption_display(x) for x in (tpl_entry.get("default_hook_captions") or []) if str(x).strip()
        ]
        cut_captions: List[str] = []
        for idx in range(4):
            if idx < len(raw_caps) and raw_caps[idx]:
                cut_captions.append(raw_caps[idx])
            elif idx < len(default_hook_caps) and default_hook_caps[idx]:
                cut_captions.append(default_hook_caps[idx])
            elif idx == 3:
                cut_captions.append("반전 후 실제 제품 핵심 효과가 이어집니다")
            else:
                cut_captions.append(f"3D 물리 훅 장면 {idx + 1}")

        frames: List[Dict[str, Any]] = []
        ratios = (0.12, 0.38, 0.66, 0.90)
        for idx, ratio in enumerate(ratios, start=1):
            ts = round(max(0.1, min(tpl_dur - 0.15, tpl_dur * ratio)), 2)
            img_path = out_dir / f"frame_{idx:02d}.png"
            subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-ss",
                    f"{ts:.2f}",
                    "-i",
                    str(tpl_path),
                    "-frames:v",
                    "1",
                    "-vf",
                    "scale=540:675:force_original_aspect_ratio=increase,crop=540:675",
                    str(img_path),
                ],
                capture_output=True,
                check=True,
            )
            obj_key = (
                f"projects/{project['project_id']}/storyboards/"
                f"{scenario['scenario_id']}/frame_{idx:02d}.png"
            )
            storage.upload_file(img_path, obj_key)
            url = resolve_media_url(obj_key, storage=storage, settings=settings) or obj_key
            frames.append(
                {
                    "beat_order": idx,
                    "image_url": url,
                    "caption": cut_captions[idx - 1],
                }
            )
        return frames

    def _generate(
        project: Dict[str, Any], scenario: Dict[str, Any], visual_style: str
    ) -> List[Dict[str, Any]]:
        if str(scenario.get("type") or "").upper() == "A":
            track_a_frames = _extract_track_a_storyboard(project, scenario)
            if track_a_frames:
                return track_a_frames

        provider = GenAIMediaProvider(settings)
        out_dir = (
            Path(settings.work_root).resolve()
            / project["project_id"]
            / "storyboards"
            / scenario["scenario_id"]
        )
        frames: List[Dict[str, Any]] = []
        hook_beats = [b for b in scenario.get("beats") or [] if b.get("role") != "silence_gap"][:3]
        for beat in hook_beats:
            order = int(beat.get("order") or len(frames) + 1)
            img_path = out_dir / f"frame_{order:02d}.png"
            prompt = (
                f"{beat.get('visual', 'Clean storyboard scene')}. "
                f"Style: {visual_style}. Zero readable text, no subtitles, no watermarks."
            )
            provider.generate_reference_image(prompt, img_path, skip_existing=True)
            obj_key = (
                f"projects/{project['project_id']}/storyboards/"
                f"{scenario['scenario_id']}/frame_{order:02d}.png"
            )
            storage.upload_file(img_path, obj_key)
            url = resolve_media_url(obj_key, storage=storage, settings=settings) or obj_key
            frames.append(
                {
                    "beat_order": order,
                    "image_url": url,
                    "caption": _clean_caption_display(beat.get("caption", "")),
                }
            )
        return frames

    return _generate


def build_projects_router(
    settings: Settings,
    project_store: ProjectStore,
    job_store: JobStore,
    storage: StorageBackend,
    pipeline: ProductionPipeline,
    executor: ThreadPoolExecutor,
    *,
    google_token_verifier: Optional[GoogleTokenVerifier] = None,
    scenario_generator: Optional[ScenarioGenerator] = None,
    storyboard_generator: Optional[StoryboardGenerator] = None,
    paddle_client: Optional[PaddleApiClient] = None,
) -> APIRouter:
    """Build `/v1/auth/*`, `/v1/billing/*`, `/v1/hook-types`, and `/v1/projects/*` routes."""
    router = APIRouter()
    verify_google = google_token_verifier or verify_google_id_token
    gen_scenarios = scenario_generator or _default_scenario_generator(settings)
    gen_storyboard = storyboard_generator or _default_storyboard_generator(settings, storage)
    paddle = paddle_client or HttpxPaddleApiClient(settings)

    def _quota(user_id: str) -> QuotaStatus:
        now = datetime.now(timezone.utc)
        used = project_store.count_user_renders_today(user_id, now=now)
        resets = (now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)).isoformat()
        limit = max(1, int(settings.daily_render_limit))
        return QuotaStatus(
            daily_limit=limit,
            used_today=used,
            remaining_today=max(0, limit - used),
            resets_at=resets,
        )

    def require_user(
        request: Request,
        authorization: Optional[str] = Header(default=None),
    ) -> AuthenticatedUser:
        token: Optional[str] = None
        if authorization and authorization.startswith("Bearer "):
            token = authorization[len("Bearer ") :].strip()
        if not token:
            token = request.cookies.get(SESSION_COOKIE_NAME)
        if not token:
            raise _api_error(
                status.HTTP_401_UNAUTHORIZED,
                "UNAUTHORIZED",
                "로그인이 필요합니다. Google 계정으로 로그인해 주세요.",
            )
        try:
            return verify_session_token(token, settings.session_secret)
        except AuthenticationError as exc:
            raise _api_error(status.HTTP_401_UNAUTHORIZED, "UNAUTHORIZED", str(exc)) from exc

    def _get_owned_project(project_id: str, user: AuthenticatedUser) -> Dict[str, Any]:
        proj = project_store.get_project(project_id, user_id=user.user_id)
        if not proj:
            raise _api_error(
                status.HTTP_404_NOT_FOUND,
                "PROJECT_NOT_FOUND",
                "프로젝트를 찾을 수 없거나 접근 권한이 없습니다.",
            )
        if is_project_expired(proj):
            raise _api_error(
                status.HTTP_410_GONE,
                "PROJECT_EXPIRED",
                "보관 기간(7일)이 만료된 프로젝트입니다.",
            )
        return proj

    def _resolve_track_a_template(template_id: Optional[str] = None) -> Optional[Path]:
        """Resolve a pre-prepared Track A opener MP4 from manifest, URLs, dir, or defaults."""
        manifest_entries = _load_track_a_manifest_entries(settings)
        if template_id:
            for entry in manifest_entries:
                if entry.get("id") == template_id:
                    return Path(entry["path"])

        raw_urls = [u.strip() for u in (settings.track_a_template_urls or "").split(",") if u.strip()]
        if raw_urls:
            cache_dir = Path("/tmp/napda_templates")
            cache_dir.mkdir(parents=True, exist_ok=True)
            chosen_url = random.choice(raw_urls)
            fname = Path(chosen_url.split("?", 1)[0]).name or "track_a_tpl.mp4"
            cached = cache_dir / fname
            if not cached.exists():
                with httpx.Client(timeout=30.0, follow_redirects=True) as client:
                    dl = client.get(chosen_url)
                    dl.raise_for_status()
                    cached.write_bytes(dl.content)
            return cached

        if manifest_entries:
            return Path(manifest_entries[0]["path"])

        candidates: List[Path] = []
        if settings.track_a_template_dir and settings.track_a_template_dir.strip():
            d = Path(settings.track_a_template_dir).expanduser().resolve()
            if d.is_dir():
                candidates.extend(sorted(d.glob("*.mp4")))
        default_dir = Path(__file__).resolve().parents[1] / "data" / "templates" / "track_a"
        if default_dir.is_dir():
            candidates.extend(sorted(default_dir.glob("*.mp4")))
        return random.choice(candidates) if candidates else None

    def _prepare_track_a_template_spec(
        raw_spec: Dict[str, Any],
        *,
        template_mp4: Path,
        source_mp4: Path,
        source_dur: float,
        jid: str,
    ) -> Tuple[Dict[str, Any], str]:
        """Swap Track A hook cuts to pre-prepared template clip + synthesize Inworld Korean VO."""
        tmp_dir = Path("/tmp/napda_track_a") / jid
        tmp_dir.mkdir(parents=True, exist_ok=True)
        staged_tpl = tmp_dir / "template_hook_a.mp4"
        staged_src = tmp_dir / "source_product.mp4"
        shutil.copy2(template_mp4, staged_tpl)
        shutil.copy2(source_mp4, staged_src)

        def _seg_dur(seg: Dict[str, Any]) -> float:
            if seg.get("type") == "source" and "src_start" in seg and "src_end" in seg:
                spd = float(seg.get("speed") or 1.0)
                return max(0.05, (float(seg["src_end"]) - float(seg["src_start"])) / max(spd, 0.01))
            return max(0.05, float(seg.get("duration") or 1.0))

        tpl_dur, _, _ = _probe_local_video(str(staged_tpl))
        if tpl_dur <= 0.0:
            tpl_dur = 9.0

        spec = json.loads(json.dumps(raw_spec))
        spec["mode"] = "narrative_master"
        spec["track_archetype"] = "A_bgrade_reversal"
        spec["source_video"] = str(staged_src)
        spec["source_duration"] = float(source_dur)
        spec["disclosure"] = "ai_assisted"
        spec["allow_static_intro"] = True
        spec.setdefault("a_genre_archetype", "mock_documentary")
        spec["caption_style"] = "reels_kinetic"
        spec["caption_y"] = 1245
        spec["highlight_color"] = "#FFE047"

        target_pre = round(min(max(tpl_dur, 8.0), 10.5), 2) if tpl_dur >= 8.0 else round(max(tpl_dur, 5.0), 2)
        pre_dur = round(min(target_pre, tpl_dur), 2)
        pre_segs: List[Dict[str, Any]] = [
            {
                "id": "tpl_hook_1",
                "type": "video",
                "path": str(staged_tpl),
                "src_start": 0.0,
                "duration": pre_dur,
                "framing": "full-bleed",
                "audio_owner": "vo",
            }
        ]

        target_post = round(min(max(4.0, source_dur), 7.2), 2)
        s_start = 0.0
        s_end = round(min(max(source_dur, 0.5), target_post), 2)
        post_segs: List[Dict[str, Any]] = [
            {
                "id": "payoff_1",
                "type": "source",
                "src_start": s_start,
                "src_end": s_end,
                "framing": "full-bleed",
                "audio_owner": "vo",
                "fact_ids": ["F01"],
            }
        ]
        gap_seg = {
            "id": "twist_gap",
            "type": "silence_gap",
            "duration": 0.25,
            "audio_owner": "silence",
            "framing": "full-bleed",
        }
        spec["timeline"] = pre_segs + [gap_seg] + post_segs
        spec["hook_window_sec"] = round(pre_dur, 2)
        total_dur = round(sum(_seg_dur(s) for s in spec["timeline"]), 2)

        bgm_act1 = "/Library/Audio/Apple Loops/Apple/01 Hip Hop/Distant Memories Piano.caf"
        bgm_act2 = "/Library/Audio/Apple Loops/Apple/09 Disco Funk/Sky Lounge Electric Piano 01.caf"
        sfx_impact = "/Library/Audio/Apple Loops/Apple/Final Cut Pro Sound Effects/Impacts & Crashes/Impact Hit Reverb 03.caf"
        if not spec.get("bgm_timeline") and os.path.exists(bgm_act1) and os.path.exists(bgm_act2):
            spec["bgm_timeline"] = [
                {
                    "start": 0.0,
                    "end": round(pre_dur, 2),
                    "stems": [bgm_act1],
                    "gain_db": -16.0,
                    "fade_in": 0.05,
                    "fade_out": 0.03,
                    "stem_offset_sec": 0.0,
                },
                {
                    "start": round(pre_dur + 0.25, 2),
                    "end": total_dur,
                    "stems": [bgm_act2],
                    "gain_db": -15.0,
                    "fade_in": 0.04,
                    "fade_out": 0.45,
                    "stem_offset_sec": 0.0,
                },
            ]
        if not spec.get("sfx_events") and os.path.exists(sfx_impact):
            spec["sfx_events"] = [
                {
                    "time": round(pre_dur, 2),
                    "file": sfx_impact,
                    "trim_start": 0.53,
                    "duration": 0.26,
                    "gain_db": -12.0,
                    "fade_in": 0.005,
                    "fade_out": 0.05,
                }
            ]

        orig_tl = list(raw_spec.get("timeline") or [])
        orig_gap_start = 0.0
        found_orig_gap = False
        for seg in orig_tl:
            if seg.get("type") == "silence_gap":
                found_orig_gap = True
                break
            orig_gap_start += _seg_dur(seg)

        caps = list(spec.get("captions") or [])
        if caps:
            orig_end = max(float(c.get("end") or 0.1) for c in caps)
            remapped = []
            if found_orig_gap and 0.1 < orig_gap_start < orig_end:
                pre_caps = [c for c in caps if float(c.get("start", 0.0)) < orig_gap_start]
                post_caps = [c for c in caps if float(c.get("start", 0.0)) >= orig_gap_start]
                pre_span = max(pre_caps[-1]["end"] if pre_caps else orig_gap_start, orig_gap_start, 0.1)
                post_base = float(post_caps[0]["start"]) if post_caps else orig_gap_start
                post_span = max(orig_end - post_base, 0.1)
                post_target_dur = max(total_dur - (pre_dur + 0.25), 0.5)
                for c in pre_caps:
                    st_t = round(min(pre_dur - 0.4, max(0.0, float(c.get("start", 0.0)) * (pre_dur / pre_span))), 2)
                    en_t = round(min(pre_dur, max(st_t + 0.4, float(c.get("end", pre_span)) * (pre_dur / pre_span))), 2)
                    item = dict(c)
                    item["start"], item["end"] = st_t, en_t
                    remapped.append(item)
                for c in post_caps:
                    rel_s = max(0.0, float(c.get("start", post_base)) - post_base)
                    rel_e = max(rel_s + 0.4, float(c.get("end", orig_end)) - post_base)
                    st_t = round(min(total_dur - 0.4, pre_dur + 0.25 + rel_s * (post_target_dur / post_span)), 2)
                    en_t = round(min(total_dur, max(st_t + 0.4, pre_dur + 0.25 + rel_e * (post_target_dur / post_span))), 2)
                    item = dict(c)
                    item["start"], item["end"] = st_t, en_t
                    remapped.append(item)
            else:
                factor = total_dur / max(orig_end, 0.1)
                for c in caps:
                    st_t = round(min(total_dur - 0.5, max(0.0, float(c.get("start", 0.0)) * factor)), 2)
                    en_t = round(min(total_dur, max(st_t + 0.5, float(c.get("end", 1.0)) * factor)), 2)
                    item = dict(c)
                    item["start"] = st_t
                    item["end"] = en_t
                    remapped.append(item)
            spec["captions"] = remapped

        manifest_entries = _load_track_a_manifest_entries(settings)
        tpl_id = spec.get("track_a_template_id")
        matched_entry = next(
            (e for e in manifest_entries if tpl_id and e.get("id") == tpl_id),
            None,
        )
        raw_default_caps = list((matched_entry or {}).get("default_hook_captions") or [])
        if raw_default_caps and (spec.get("reference_surface_taboo") or []):
            tpl_caption_corpus = " ".join(str(x) for x in raw_default_caps).lower()
            spec["reference_surface_taboo"] = [
                kw
                for kw in (spec.get("reference_surface_taboo") or [])
                if str(kw).strip().lower() not in tpl_caption_corpus
            ]

        taboo_words = [
            str(w).strip().lower()
            for w in (
                list(spec.get("product_taboo_keywords") or [])
                + list(spec.get("category_taboo_keywords") or [])
                + list(spec.get("reference_surface_taboo") or [])
            )
            if len(str(w).strip()) >= 2
        ]
        if taboo_words and (spec.get("captions") or []):
            cur_caps = list(spec.get("captions") or [])
            pre_caps = [c for c in cur_caps if float(c.get("start", 0.0)) < pre_dur]
            post_caps = [c for c in cur_caps if float(c.get("start", 0.0)) >= pre_dur]

            def _cue_surface_lower(cue: Dict[str, Any]) -> str:
                plain_txt = re.sub(r"\*\*(.+?)\*\*", r"\1", str(cue.get("text") or ""))
                return " ".join(
                    p
                    for p in (
                        plain_txt,
                        str(cue.get("pop_badge") or ""),
                        str(cue.get("header_tag") or ""),
                    )
                    if p
                ).lower()

            has_taboo = any(
                any(tw in _cue_surface_lower(c) for tw in taboo_words)
                for c in pre_caps
                if float(c.get("start", 0.0)) < pre_dur - 0.05
            )
            if has_taboo:
                raw_defaults = raw_default_caps or [
                    "1cm 도미노를 2배씩 키워\n**스무 개만** 세우면,",
                    "마지막 조각은 **아파트 50층**\n높이가 됩니다",
                    "지면에 닿는 순간, 반경 1km\n**지반이 흔들립니다**",
                ]
                sanitized_defaults: List[str] = []
                for ln in raw_defaults:
                    clean_ln = str(ln)
                    for tw in taboo_words:
                        clean_ln = re.sub(re.escape(tw), "", clean_ln, flags=re.IGNORECASE)
                    clean_ln = re.sub(r"[ \t]{2,}", " ", clean_ln).strip()
                    if clean_ln:
                        sanitized_defaults.append(clean_ln)
                if not sanitized_defaults:
                    sanitized_defaults = ["상상을 뛰어넘는\n**놀라운 장면**"]
                step_dur = pre_dur / max(1, len(sanitized_defaults))
                badge_txt = "3D 물리 실험"
                badge_safe = not any(tw in badge_txt.lower() for tw in taboo_words)
                clean_pre_caps: List[Dict[str, Any]] = []
                for idx_c, txt_c in enumerate(sanitized_defaults):
                    s_c = round(idx_c * step_dur, 2)
                    e_c = round(
                        min(
                            pre_dur,
                            (idx_c + 1) * step_dur - (0.04 if idx_c < len(sanitized_defaults) - 1 else 0.0),
                        ),
                        2,
                    )
                    if e_c <= s_c:
                        e_c = round(min(pre_dur, s_c + 0.4), 2)
                    cap_item: Dict[str, Any] = {"start": s_c, "end": e_c, "text": txt_c}
                    if idx_c == 0 and badge_safe:
                        cap_item["pop_badge"] = badge_txt
                    clean_pre_caps.append(cap_item)
                spec["captions"] = clean_pre_caps + post_caps

        for cap_c in spec.get("captions") or []:
            if isinstance(cap_c, dict) and "text" in cap_c:
                cap_c["text"] = _unescape_newlines(cap_c.get("text"))

        plain_lines = [
            re.sub(r"\*\*(.+?)\*\*", r"\1", str(c.get("text") or "")).replace("\n", " ").strip()
            for c in (spec.get("captions") or [])
        ]
        narration_text = " ".join(ln for ln in plain_lines if ln) or "지금 바로 확인해 보세요."
        vo_wav = tmp_dir / "vo_master.wav"
        tts = build_tts_provider(settings)
        tts.synthesize(narration_text, vo_wav)
        spec["vo_audio"] = str(vo_wav)
        return spec, str(staged_src)

    def _run_job_bg(
        req: CampaignRequest,
        jid: str,
        *,
        user_id: Optional[str] = None,
        refunded_credits: int = 0,
    ) -> None:
        try:
            pipeline.run_campaign(req, job_id=jid)
        except Exception as exc:
            job = job_store.get_job(jid)
            if job and job.get("status") != "FAILED":
                job_store.update_job(jid, status="FAILED", error=str(exc))
        finally:
            job = job_store.get_job(jid)
            if job and job.get("status") == "FAILED" and user_id and refunded_credits > 0:
                project_store.refund_wallet_credits(user_id, refunded_credits)

    def _run_track_a_template_bg(
        req: CampaignRequest,
        jid: str,
        template_mp4: Path,
        src_key: Optional[str],
        src_dur: float,
        *,
        user_id: Optional[str] = None,
        refunded_credits: int = 0,
    ) -> None:
        try:
            src_path = Path(req.source_video) if (req.source_video and os.path.exists(req.source_video)) else None
            if src_path is None and src_key:
                resolve_local = getattr(storage, "resolve_local_path", None)
                src_path = resolve_local(src_key) if callable(resolve_local) else None
                if src_path is None:
                    dl_tmp = Path("/tmp/napda_track_a") / jid / "downloaded_source.mp4"
                    dl_tmp.parent.mkdir(parents=True, exist_ok=True)
                    storage.download_file(src_key, dl_tmp)
                    src_path = dl_tmp
            if src_path is not None and src_path.exists() and req.spec_data is not None:
                job_store.update_job(jid, status="RUNNING", stage="PLANNING")
                prepared_spec, staged_src = _prepare_track_a_template_spec(
                    req.spec_data,
                    template_mp4=template_mp4,
                    source_mp4=src_path,
                    source_dur=src_dur,
                    jid=jid,
                )
                req.spec_data = prepared_spec
                req.source_video = staged_src
                req.source_object_key = None
            pipeline.run_campaign(req, job_id=jid)
        except Exception as exc:
            job = job_store.get_job(jid)
            if job and job.get("status") != "FAILED":
                job_store.update_job(jid, status="FAILED", error=str(exc))
        finally:
            job = job_store.get_job(jid)
            if job and job.get("status") == "FAILED" and user_id and refunded_credits > 0:
                project_store.refund_wallet_credits(user_id, refunded_credits)

    @router.post("/v1/auth/google", response_model=GoogleAuthResponse, tags=["Auth"])
    def auth_google(body: GoogleAuthRequest, response: Response) -> GoogleAuthResponse:
        try:
            user = verify_google(body.credential, settings.google_client_id or "")
        except AuthenticationError as exc:
            raise _api_error(status.HTTP_401_UNAUTHORIZED, "INVALID_GOOGLE_TOKEN", str(exc)) from exc

        project_store.upsert_user(user)
        token, expires_at = issue_session_token(
            user, settings.session_secret, ttl_days=settings.session_ttl_days
        )
        response.set_cookie(
            key=SESSION_COOKIE_NAME,
            value=token,
            max_age=settings.session_ttl_days * 86400,
            path="/",
            httponly=True,
            samesite="lax",
            secure=settings.session_cookie_secure,
        )
        return GoogleAuthResponse(
            user=AuthUserResponse(**user.__dict__),
            access_token=token,
            expires_at=expires_at,
            quota=_quota(user.user_id),
        )

    @router.post("/v1/auth/logout", status_code=status.HTTP_204_NO_CONTENT, tags=["Auth"])
    def auth_logout(response: Response) -> Response:
        response.delete_cookie(
            SESSION_COOKIE_NAME,
            path="/",
            httponly=True,
            samesite="lax",
            secure=settings.session_cookie_secure,
        )
        response.status_code = status.HTTP_204_NO_CONTENT
        return response

    @router.get("/v1/auth/me", response_model=AuthMeResponse, tags=["Auth"])
    def auth_me(user: AuthenticatedUser = Depends(require_user)) -> AuthMeResponse:
        return AuthMeResponse(user=AuthUserResponse(**user.__dict__), quota=_quota(user.user_id))

    @router.get("/v1/hook-types", response_model=HookTypesResponse, tags=["Planning"])
    def list_hook_types() -> HookTypesResponse:
        return HookTypesResponse(types=HOOK_TYPE_CATALOG)

    @router.post(
        "/v1/product-info",
        response_model=ProductInfoResponse,
        tags=["Projects"],
    )
    def create_product_info(
        body: ProductInfoRequest,
        user: AuthenticatedUser = Depends(require_user),
    ) -> ProductInfoResponse:
        enriched_product = enrich_product_with_source_url(
            body.product.model_dump(),
            body.source_url,
        )
        entry = project_store.upsert_product_info_cache(
            user.user_id,
            product=enriched_product,
            source_url=body.source_url,
            ttl_sec=settings.product_info_cache_ttl_sec,
        )
        return ProductInfoResponse(
            product_info_id=entry["product_info_id"],
            product=ProductInput(**entry["product"]),
            cached=bool(entry["cached"]),
            cached_at=entry["cached_at"],
            expires_at=entry["expires_at"],
        )

    @router.post(
        "/v1/projects",
        status_code=status.HTTP_201_CREATED,
        response_model=ProjectSummary,
        tags=["Projects"],
    )
    def create_project(
        body: CreateProjectRequest,
        user: AuthenticatedUser = Depends(require_user),
    ) -> ProjectSummary:
        if body.product_info_id and body.product_info_id.strip():
            cached_info = project_store.get_product_info(user.user_id, body.product_info_id.strip())
            if not cached_info:
                raise _api_error(
                    status.HTTP_404_NOT_FOUND,
                    "PRODUCT_INFO_NOT_FOUND",
                    "제품 정보를 찾을 수 없거나 캐시가 만료되었습니다.",
                )
            product_payload = cached_info["product"]
        else:
            assert body.product is not None
            product_payload = body.product.model_dump()

        pid = f"prj_{uuid.uuid4().hex[:12]}"
        proj = project_store.create_project(
            pid,
            user.user_id,
            product=product_payload,
            selected_types=list(body.selected_types),
            flow_mode=body.flow_mode,
            retention_ttl_days=settings.retention_ttl_days,
        )
        return ProjectSummary(
            project_id=proj["project_id"],
            status=proj["status"],
            flow_mode=proj["flow_mode"],
            product_name=proj["product"]["name"],
            category=proj["product"]["category"],
            selected_types=proj["selected_types"],
            selected_scenario_id=proj["selected_scenario_id"],
            latest_job_id=proj["latest_job_id"],
            expires_at=proj["expires_at"],
            created_at=proj["created_at"],
            updated_at=proj["updated_at"],
        )

    @router.get("/v1/projects", response_model=ProjectListResponse, tags=["Projects"])
    def list_projects(
        limit: int = Query(default=50, ge=1, le=100),
        offset: int = Query(default=0, ge=0),
        user: AuthenticatedUser = Depends(require_user),
    ) -> ProjectListResponse:
        total = project_store.count_projects_for_user(user.user_id)
        rows = project_store.list_projects_for_user(user.user_id, limit=limit, offset=offset)
        summaries = [
            ProjectSummary(
                project_id=r["project_id"],
                status=r["status"],
                flow_mode=r["flow_mode"],
                product_name=r["product"]["name"],
                category=r["product"]["category"],
                selected_types=r["selected_types"],
                selected_scenario_id=r["selected_scenario_id"],
                latest_job_id=r["latest_job_id"],
                expires_at=r["expires_at"],
                created_at=r["created_at"],
                updated_at=r["updated_at"],
            )
            for r in rows
        ]
        has_more = (offset + len(rows)) < total
        next_offset = (offset + len(rows)) if has_more else None
        return ProjectListResponse(
            projects=summaries,
            quota=_quota(user.user_id),
            total=total,
            offset=offset,
            limit=limit,
            has_more=has_more,
            next_offset=next_offset,
        )

    @router.get("/v1/projects/{project_id}", response_model=ProjectDetailResponse, tags=["Projects"])
    def get_project(
        project_id: str,
        user: AuthenticatedUser = Depends(require_user),
    ) -> ProjectDetailResponse:
        proj = sync_project_status_with_job(_get_owned_project(project_id, user), job_store, project_store)
        scns = [ScenarioItem(**s) for s in project_store.list_scenarios(project_id)]
        latest_job = job_store.get_job(proj["latest_job_id"]) if proj.get("latest_job_id") else None
        fg = FilmingGuideResponse(**proj["filming_guide"]) if proj.get("filming_guide") else None
        up = CompleteUploadsResponse(**proj["uploads"]) if proj.get("uploads") else None
        return ProjectDetailResponse(
            project_id=proj["project_id"],
            status=proj["status"],
            flow_mode=proj["flow_mode"],
            product=ProductInput(**proj["product"]),
            selected_types=proj["selected_types"],
            selected_scenario_id=proj.get("selected_scenario_id"),
            scenarios=scns,
            filming_guide=fg,
            uploads=up,
            latest_job_id=proj.get("latest_job_id"),
            latest_job=latest_job,
            quota=_quota(user.user_id),
            expires_at=proj["expires_at"],
            created_at=proj["created_at"],
            updated_at=proj["updated_at"],
        )

    @router.post(
        "/v1/projects/{project_id}/scenarios",
        response_model=GenerateScenariosResponse,
        tags=["Planning"],
    )
    def generate_scenarios(
        project_id: str,
        body: GenerateScenariosRequest,
        user: AuthenticatedUser = Depends(require_user),
    ) -> GenerateScenariosResponse:
        proj = _get_owned_project(project_id, user)
        target_types = list(dict.fromkeys(body.types or proj["selected_types"]))
        seen_ids = {s["scenario_id"] for s in project_store.list_scenarios(project_id)}
        new_items: List[Dict[str, Any]] = []
        for _ in range(body.count):
            batch = gen_scenarios(proj, target_types, body.provider)
            for item in batch:
                cand = dict(item)
                sid = str(cand.get("scenario_id") or f"scn_{cand.get('type', 'A')}_{uuid.uuid4().hex[:6]}")
                if sid in seen_ids:
                    sid = f"{sid}_{uuid.uuid4().hex[:6]}"
                cand["scenario_id"] = sid
                seen_ids.add(sid)
                new_items.append(cand)
        saved, round_num = project_store.append_scenarios(project_id, new_items)
        updated = project_store.update_project(project_id, status="SCENARIOS_READY")
        return GenerateScenariosResponse(
            project_id=project_id,
            status=updated["status"],
            scenarios=[ScenarioItem(**s) for s in saved],
            round=round_num,
        )

    @router.post(
        "/v1/projects/{project_id}/scenarios/{scenario_id}/select",
        response_model=SelectScenarioResponse,
        tags=["Planning"],
    )
    def select_scenario(
        project_id: str,
        scenario_id: str,
        user: AuthenticatedUser = Depends(require_user),
    ) -> SelectScenarioResponse:
        _ = _get_owned_project(project_id, user)
        scn = project_store.get_scenario(project_id, scenario_id)
        if not scn:
            raise _api_error(status.HTTP_404_NOT_FOUND, "SCENARIO_NOT_FOUND", "시나리오를 찾을 수 없습니다.")
        project_store.update_project(project_id, selected_scenario_id=scenario_id)
        return SelectScenarioResponse(project_id=project_id, selected_scenario_id=scenario_id)

    @router.post(
        "/v1/projects/{project_id}/scenarios/{scenario_id}/storyboard",
        response_model=StoryboardResponse,
        tags=["Planning"],
    )
    def generate_storyboard(
        project_id: str,
        scenario_id: str,
        body: GenerateStoryboardRequest,
        user: AuthenticatedUser = Depends(require_user),
    ) -> StoryboardResponse:
        proj = _get_owned_project(project_id, user)
        scn = project_store.get_scenario(project_id, scenario_id)
        if not scn:
            raise _api_error(status.HTTP_404_NOT_FOUND, "SCENARIO_NOT_FOUND", "시나리오를 찾을 수 없습니다.")
        frames = gen_storyboard(proj, scn, body.visual_style)
        project_store.update_scenario_storyboard(project_id, scenario_id, frames)
        updated = project_store.update_project(project_id, status="STORYBOARD_READY")
        return StoryboardResponse(
            project_id=project_id,
            scenario_id=scenario_id,
            status=updated["status"],
            frames=[StoryboardFrame(**f) for f in frames],
        )

    @router.post(
        "/v1/projects/{project_id}/filming-guide",
        response_model=FilmingGuideResponse,
        tags=["Filming Guide"],
    )
    def create_filming_guide(
        project_id: str,
        body: CreateFilmingGuideRequest,
        user: AuthenticatedUser = Depends(require_user),
    ) -> FilmingGuideResponse:
        proj = _get_owned_project(project_id, user)
        scn = project_store.get_scenario(project_id, body.scenario_id)
        if not scn:
            raise _api_error(status.HTTP_404_NOT_FOUND, "SCENARIO_NOT_FOUND", "선택한 시나리오가 없습니다.")

        guide_payload = build_filming_guide(proj, scn)
        target_dur = guide_payload["target_body_duration_sec"]
        shots = guide_payload["shots"]
        project_store.update_project(
            project_id,
            status="GUIDE_READY",
            selected_scenario_id=body.scenario_id,
            filming_guide=guide_payload,
        )
        return FilmingGuideResponse(
            project_id=project_id,
            status="GUIDE_READY",
            selected_scenario_id=body.scenario_id,
            target_body_duration_sec=target_dur,
            shots=[FilmingGuideShot(**s) for s in shots],
        )

    @router.post(
        "/v1/projects/{project_id}/estimate",
        response_model=EstimateResponse,
        tags=["Credits"],
    )
    def estimate_credits(
        project_id: str,
        body: EstimateRequest,
        user: AuthenticatedUser = Depends(require_user),
    ) -> EstimateResponse:
        _ = _get_owned_project(project_id, user)
        hook_cr = 10 if body.resolution == "360p" else 30
        stages = [
            StageCreditItem(stage="hook_video", description="앞 훅 영상 2컷 생성 (각 5초)", estimated_credits=hook_cr),
            StageCreditItem(stage="narration_tts", description="한국어 숏폼 TTS 내레이션", estimated_credits=2),
            StageCreditItem(stage="assembly_thumbnail", description="FFmpeg 본편 연결 및 썸네일", estimated_credits=0),
        ]
        return EstimateResponse(
            project_id=project_id,
            resolution=body.resolution,
            total_estimated_credits=sum(s.estimated_credits for s in stages),
            stages=stages,
            quota=_quota(user.user_id),
        )

    @router.post(
        "/v1/projects/{project_id}/uploads/complete",
        response_model=CompleteUploadsResponse,
        tags=["Uploads"],
    )
    def complete_uploads(
        project_id: str,
        body: CompleteUploadsRequest,
        user: AuthenticatedUser = Depends(require_user),
    ) -> CompleteUploadsResponse:
        proj = _get_owned_project(project_id, user)
        payload = validate_and_complete_uploads(
            proj,
            body.clips,
            storage=storage,
            settings=settings,
        )
        project_store.update_project(project_id, status="UPLOADS_READY", uploads=payload)
        return CompleteUploadsResponse(**payload)

    @router.post(
        "/v1/projects/{project_id}/renders",
        status_code=status.HTTP_202_ACCEPTED,
        response_model=CreateRenderResponse,
        tags=["Generation"],
    )
    def create_render(
        project_id: str,
        body: CreateRenderRequest,
        user: AuthenticatedUser = Depends(require_user),
    ) -> CreateRenderResponse:
        proj = _get_owned_project(project_id, user)
        quota_before = _quota(user.user_id)
        if quota_before.remaining_today <= 0:
            raise _api_error(
                status.HTTP_429_TOO_MANY_REQUESTS,
                "DAILY_QUOTA_EXCEEDED",
                f"무료 베타 일일 생성 한도({quota_before.daily_limit}회)를 모두 사용했습니다.",
                quota_before.model_dump(),
            )

        uploads = proj.get("uploads")
        if not uploads or not (uploads.get("clips") or []):
            raise _api_error(
                status.HTTP_400_BAD_REQUEST,
                "INVALID_STATE",
                "영상을 생성하기 전에 원본 본편 영상을 업로드해 주세요.",
            )

        first_clip = uploads["clips"][0]
        src_local = first_clip.get("local_path")
        src_key = first_clip.get("object_key")
        if not src_local and src_key:
            resolve_local = getattr(storage, "resolve_local_path", None)
            resolved = resolve_local(src_key) if callable(resolve_local) else None
            if resolved and resolved.exists():
                src_local = str(resolved)
        src_dur = float(uploads.get("total_duration_sec") or 12.0)

        scn_id = body.scenario_id or proj.get("selected_scenario_id")
        if body.skip_drafts and body.selected_type:
            chosen_type = body.selected_type
            spec_data = _build_default_ad_spec(
                proj,
                chosen_type,
                source_video=src_local or src_key,
                source_duration=src_dur,
                voice_id=body.voice_id,
            )
        elif scn_id:
            scn = project_store.get_scenario(project_id, scn_id)
            if not scn:
                raise _api_error(status.HTTP_404_NOT_FOUND, "SCENARIO_NOT_FOUND", "시나리오를 찾을 수 없습니다.")
            chosen_type = scn["type"]
            spec_data = dict(scn.get("ad_spec") or {})
            if not spec_data:
                spec_data = _build_default_ad_spec(
                    proj,
                    chosen_type,
                    source_video=src_local or src_key,
                    source_duration=src_dur,
                    voice_id=body.voice_id,
                )
            else:
                spec_data["source_video"] = src_local or spec_data.get("source_video") or src_key
                spec_data["source_duration"] = src_dur
        else:
            raise _api_error(
                status.HTTP_400_BAD_REQUEST,
                "INVALID_STATE",
                "scenario_id 또는 skip_drafts + selected_type을 지정해 주세요.",
            )

        tpl_path = (
            _resolve_track_a_template(spec_data.get("track_a_template_id"))
            if (chosen_type == "A" and not body.dry_run)
            else None
        )
        deducted_credits = 0
        if not body.dry_run and settings.credits_per_video > 0:
            wallet = project_store.get_or_create_wallet(
                user.user_id, default_free_videos=settings.initial_free_videos
            )
            if wallet["credits"] >= settings.credits_per_video:
                if project_store.deduct_wallet_credits(user.user_id, settings.credits_per_video):
                    deducted_credits = settings.credits_per_video

        jid = f"job_{uuid.uuid4().hex[:12]}"
        req = CampaignRequest(
            campaign_id=project_id,
            source_video=src_local,
            source_object_key=None if src_local else src_key,
            facts_markdown=_product_to_facts_md(proj["product"]),
            spec_data=spec_data,
            track_archetype=_TRACK_BY_TYPE[chosen_type],
            resolution=body.resolution,
            clean_copy=True,
            dry_run=body.dry_run,
            skip_cross_campaign_reskin=(tpl_path is not None),
        )
        job_store.create_job(jid, project_id, req.__dict__, status="QUEUED", stage="QUEUED")
        project_store.record_render_usage(user.user_id, project_id, jid)
        project_store.update_project(project_id, status="RENDERING", latest_job_id=jid)
        if tpl_path is not None:
            executor.submit(
                _run_track_a_template_bg,
                req,
                jid,
                tpl_path,
                src_key,
                src_dur,
                user_id=user.user_id,
                refunded_credits=deducted_credits,
            )
        else:
            executor.submit(
                _run_job_bg,
                req,
                jid,
                user_id=user.user_id,
                refunded_credits=deducted_credits,
            )

        est_cr = 12 if body.resolution == "360p" else 32
        return CreateRenderResponse(
            project_id=project_id,
            job_id=jid,
            status="QUEUED",
            selected_type=chosen_type,
            estimated_credits=est_cr,
            quota=_quota(user.user_id),
            expires_at=proj["expires_at"],
        )

    @router.get(
        "/v1/projects/{project_id}/deliverables",
        response_model=DeliverablesResponse,
        tags=["Delivery"],
    )
    def get_deliverables(
        project_id: str,
        user: AuthenticatedUser = Depends(require_user),
    ) -> DeliverablesResponse:
        proj = sync_project_status_with_job(_get_owned_project(project_id, user), job_store, project_store)
        jid = proj.get("latest_job_id")
        if not jid:
            raise _api_error(
                status.HTTP_404_NOT_FOUND,
                "NO_RENDER_JOB",
                "아직 생성된 영상 작업이 없습니다.",
            )
        job = job_store.get_job(jid)
        if not job:
            raise _api_error(status.HTTP_404_NOT_FOUND, "JOB_NOT_FOUND", "작업 정보를 찾을 수 없습니다.")

        arts = job.get("artifacts") or {}
        rendered = arts.get("rendered") or []
        first_r = rendered[0] if rendered else None
        video = None
        if first_r:
            lufs_obj = first_r.get("lufs") or {}
            master_ref = first_r.get("master_mp4")
            clean_ref = first_r.get("clean_mp4")
            srt_ref = first_r.get("srt")
            video = DeliverableVideo(
                stream_url=resolve_media_url(master_ref, storage=storage, settings=settings),
                download_url=resolve_media_url(
                    master_ref, storage=storage, settings=settings, download=True, filename="napda_master.mp4"
                ),
                clean_download_url=resolve_media_url(
                    clean_ref, storage=storage, settings=settings, download=True, filename="napda_clean.mp4"
                ),
                srt_url=resolve_media_url(
                    srt_ref, storage=storage, settings=settings, download=True, filename="napda_subtitles.srt"
                ),
                duration_sec=first_r.get("duration"),
                width=1080,
                height=1920,
                lufs=lufs_obj.get("final_lufs"),
            )

        thumbs = arts.get("thumbnails") or []
        thumb = None
        if thumbs:
            t0 = thumbs[0]
            t_ref = t0.get("url")
            thumb = DeliverableThumbnail(
                image_url=resolve_media_url(t_ref, storage=storage, settings=settings),
                download_url=resolve_media_url(
                    t_ref, storage=storage, settings=settings, download=True, filename="cover.png"
                ),
                safe_zone_1_1_ok=t0.get("safe_zone_ok"),
                headline_lines=list(t0.get("headline_lines") or []),
            )
        else:
            stored_thumb = proj.get("thumbnail")
            if stored_thumb is None and job["status"] == "QC_READY":
                sel_id = proj.get("selected_scenario_id")
                scn = project_store.get_scenario(project_id, sel_id) if sel_id else None
                stored_thumb = generate_project_thumbnail(
                    proj,
                    storage=storage,
                    settings=settings,
                    scenario=scn,
                    job=job,
                )
                project_store.update_project(project_id, thumbnail=stored_thumb)
            if stored_thumb:
                t_key = stored_thumb.get("object_key")
                thumb = DeliverableThumbnail(
                    image_url=resolve_media_url(t_key, storage=storage, settings=settings),
                    download_url=resolve_media_url(
                        t_key, storage=storage, settings=settings, download=True, filename="cover.png"
                    ),
                    safe_zone_1_1_ok=stored_thumb.get("safe_zone_1_1_ok"),
                    headline_lines=list(stored_thumb.get("headline_lines") or []),
                )
        return DeliverablesResponse(
            project_id=project_id,
            job_id=jid,
            status=job["status"],
            video=video,
            thumbnail=thumb,
            ai_disclosure=AIDisclosureInfo(),
            expires_at=proj["expires_at"],
        )

    def _process_hook_bg(project_id: str, hook_id: str, scenario: Dict[str, Any], out_dir: Path) -> None:
        try:
            project_store.update_hook(hook_id, status="running")
            out_dir.mkdir(parents=True, exist_ok=True)
            scenario_file = out_dir / "scenario.json"
            scenario_file.write_text(json.dumps(scenario, ensure_ascii=False, indent=2), encoding="utf-8")

            srt_lines: List[str] = []
            t_cur = 0.0
            cap_idx = 1
            for beat in scenario.get("beats") or []:
                dur = float(beat.get("duration_sec") or 3.0)
                cap_text = str(beat.get("caption") or beat.get("narration") or "").strip()
                if cap_text:
                    t_end = t_cur + dur
                    s_h, s_m, s_s = int(t_cur // 3600), int((t_cur % 3600) // 60), t_cur % 60
                    e_h, e_m, e_s = int(t_end // 3600), int((t_end % 3600) // 60), t_end % 60
                    srt_lines.append(
                        f"{cap_idx}\n"
                        f"{s_h:02d}:{s_m:02d}:{s_s:06.3f}".replace(".", ",")
                        + " --> "
                        + f"{e_h:02d}:{e_m:02d}:{e_s:06.3f}".replace(".", ",")
                        + f"\n{cap_text}\n"
                    )
                    cap_idx += 1
                t_cur += dur
            srt_file = out_dir / "subtitles.srt"
            srt_file.write_text("\n".join(srt_lines), encoding="utf-8")

            sb_urls = [
                str(f["image_url"])
                for f in (scenario.get("storyboard_frames") or [])
                if isinstance(f, dict) and f.get("image_url")
            ]
            files_payload = HookFiles(
                subtitles_srt="subtitles.srt",
                scenario_json="scenario.json",
                storyboard_images=sb_urls,
            ).model_dump()
            project_store.update_hook(hook_id, status="done", files=files_payload)
            project_store.update_project(project_id, status="HOOK_READY")
        except Exception as exc:
            project_store.update_hook(hook_id, status="failed", error=str(exc))
            project_store.update_project(project_id, status="FAILED")

    @router.post(
        "/v1/projects/{project_id}/hooks",
        status_code=status.HTTP_202_ACCEPTED,
        response_model=CreateHookResponse,
        tags=["Hooks"],
    )
    def create_hook(
        project_id: str,
        body: CreateHookRequest,
        background_tasks: BackgroundTasks,
        user: AuthenticatedUser = Depends(require_user),
    ) -> CreateHookResponse:
        proj = _get_owned_project(project_id, user)
        scn = project_store.get_scenario(project_id, body.scenario_id)
        if not scn:
            raise _api_error(status.HTTP_404_NOT_FOUND, "SCENARIO_NOT_FOUND", "시나리오를 찾을 수 없습니다.")
        if proj.get("selected_scenario_id") != body.scenario_id:
            raise _api_error(
                status.HTTP_409_CONFLICT,
                "INVALID_STATE",
                "선택된 시나리오만 훅 생성을 요청할 수 있습니다. 먼저 시나리오를 선택해 주세요.",
            )

        hook_id = f"hook_{uuid.uuid4().hex[:10]}"
        job_id = f"job_{uuid.uuid4().hex[:12]}"
        out_dir = Path(settings.output_dir).resolve() / project_id / hook_id
        project_store.create_hook(
            hook_id=hook_id,
            project_id=project_id,
            user_id=user.user_id,
            scenario_id=body.scenario_id,
            job_id=job_id,
            tts=body.tts.model_dump(),
            output_dir=str(out_dir),
            status="queued",
        )
        project_store.update_project(project_id, status="HOOK_RENDERING", latest_job_id=job_id)
        background_tasks.add_task(_process_hook_bg, project_id, hook_id, scn, out_dir)
        return CreateHookResponse(hook_id=hook_id, job_id=job_id, status="queued")

    @router.get(
        "/v1/projects/{project_id}/hooks/{hook_id}",
        response_model=HookStatusResponse,
        tags=["Hooks"],
    )
    def get_hook(
        project_id: str,
        hook_id: str,
        user: AuthenticatedUser = Depends(require_user),
    ) -> HookStatusResponse:
        _ = _get_owned_project(project_id, user)
        hook = project_store.get_hook(project_id, hook_id)
        if not hook:
            raise _api_error(status.HTTP_404_NOT_FOUND, "HOOK_NOT_FOUND", "훅 작업을 찾을 수 없습니다.")
        return HookStatusResponse(
            hook_id=hook["hook_id"],
            status=hook["status"],
            files=HookFiles(**hook["files"]),
            output_dir=hook.get("output_dir"),
            error=hook.get("error"),
        )

    @router.get(
        "/v1/projects/{project_id}/outputs",
        response_model=OutputsResponse,
        tags=["Hooks"],
    )
    def list_outputs(
        project_id: str,
        user: AuthenticatedUser = Depends(require_user),
    ) -> OutputsResponse:
        _ = _get_owned_project(project_id, user)
        hooks = project_store.list_hooks_for_project(project_id)
        items = [
            OutputItem(
                hook_id=h["hook_id"],
                scenario_id=h.get("scenario_id"),
                output_dir=h["output_dir"],
                files=HookFiles(**(h.get("files") or {})),
                created_at=h.get("created_at"),
            )
            for h in hooks
        ]
        return OutputsResponse(project_id=project_id, outputs=items)

    def _wallet_response(user_id: str) -> WalletResponse:
        wallet = project_store.get_or_create_wallet(
            user_id, default_free_videos=settings.initial_free_videos
        )
        return WalletResponse(
            credits=wallet["credits"],
            has_free_video=wallet["has_free_video"],
            free_videos_remaining=wallet["free_videos_remaining"],
        )

    @router.get("/v1/billing/config", response_model=BillingConfigResponse, tags=["Billing"])
    def get_billing_config() -> BillingConfigResponse:
        packages = get_credit_packages(settings)
        client_token = (settings.paddle_client_token or "").strip() or None
        api_key_ready = bool((settings.paddle_api_key or "").strip())
        has_price = any(p.paddle_price_id for p in packages)
        enabled = bool(api_key_ready and client_token and has_price)
        return BillingConfigResponse(
            provider="paddle",
            environment=settings.paddle_environment,
            enabled=enabled,
            client_token=client_token,
            credits_per_video=settings.credits_per_video,
            packages=[
                CreditPackageResponse(
                    id=p.id,  # type: ignore[arg-type]
                    credits=p.credits,
                    price=p.price,
                    currency=p.currency,
                    is_popular=p.is_popular,
                    paddle_price_id=p.paddle_price_id,
                )
                for p in packages
            ],
        )

    @router.get("/v1/billing/wallet", response_model=WalletResponse, tags=["Billing"])
    def get_wallet(user: AuthenticatedUser = Depends(require_user)) -> WalletResponse:
        return _wallet_response(user.user_id)

    @router.post("/v1/billing/checkout", response_model=CreateCheckoutResponse, tags=["Billing"])
    def create_billing_checkout(
        body: CreateCheckoutRequest,
        user: AuthenticatedUser = Depends(require_user),
    ) -> CreateCheckoutResponse:
        packages = {p.id: p for p in get_credit_packages(settings)}
        pkg = packages.get(body.package_id)
        if not pkg:
            raise _api_error(status.HTTP_404_NOT_FOUND, "PACKAGE_NOT_FOUND", "크레딧 묶음을 찾을 수 없습니다.")

        client_token = (settings.paddle_client_token or "").strip()
        api_key = (settings.paddle_api_key or "").strip()
        if not client_token or not pkg.paddle_price_id or (not api_key and paddle_client is None):
            raise _api_error(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "BILLING_NOT_CONFIGURED",
                "Paddle Sandbox 결제 설정이 아직 완료되지 않았습니다.",
            )

        order_id = f"ord_{uuid.uuid4().hex[:12]}"
        try:
            txn = paddle.create_transaction(
                price_id=pkg.paddle_price_id,
                custom_data={
                    "order_id": order_id,
                    "user_id": user.user_id,
                    "package_id": pkg.id,
                    "credits": pkg.credits,
                },
                customer_email=user.email,
            )
        except PaddleApiError as exc:
            raise _api_error(exc.status_code, "PADDLE_API_ERROR", str(exc), exc.detail) from exc

        txn_id = str(txn["id"])
        checkout_obj = txn.get("checkout")
        checkout_url = checkout_obj.get("url") if isinstance(checkout_obj, dict) else None
        order = project_store.create_billing_order(
            order_id=order_id,
            user_id=user.user_id,
            package_id=pkg.id,
            credits=pkg.credits,
            amount_krw=pkg.price,
            currency=pkg.currency,
            paddle_price_id=pkg.paddle_price_id,
            paddle_transaction_id=txn_id,
        )
        return CreateCheckoutResponse(
            order_id=order["order_id"],
            package_id=order["package_id"],
            credits=order["credits"],
            amount_krw=order["amount_krw"],
            currency=order["currency"],
            paddle_environment=settings.paddle_environment,
            paddle_client_token=client_token,
            paddle_price_id=pkg.paddle_price_id,
            paddle_transaction_id=txn_id,
            checkout_url=checkout_url,
            customer_email=user.email,
            status=order["status"],
        )

    @router.get("/v1/billing/orders/{order_id}", response_model=BillingOrderStatusResponse, tags=["Billing"])
    def get_billing_order(
        order_id: str,
        sync: bool = Query(default=True),
        user: AuthenticatedUser = Depends(require_user),
    ) -> BillingOrderStatusResponse:
        order = project_store.get_billing_order(order_id, user_id=user.user_id)
        if not order:
            raise _api_error(status.HTTP_404_NOT_FOUND, "ORDER_NOT_FOUND", "결제 주문을 찾을 수 없습니다.")

        if (
            order["status"] == "pending"
            and sync
            and order.get("paddle_transaction_id")
            and ((settings.paddle_api_key or "").strip() or paddle_client is not None)
        ):
            try:
                txn = paddle.get_transaction(order["paddle_transaction_id"])
            except PaddleApiError:
                txn = None
            if isinstance(txn, dict):
                custom_data = txn.get("custom_data") if isinstance(txn.get("custom_data"), dict) else {}
                custom_oid = custom_data.get("order_id") if custom_data else None
                txn_status = str(txn.get("status") or "").lower()
                if custom_oid in (None, order["order_id"]):
                    if txn_status in {"completed", "paid"}:
                        updated, _, _ = project_store.complete_billing_order_atomic(
                            order_id=order["order_id"],
                            paddle_transaction_id=order["paddle_transaction_id"],
                            default_free_videos=settings.initial_free_videos,
                        )
                        if updated:
                            order = updated
                    elif txn_status == "canceled":
                        updated = project_store.mark_billing_order_status(
                            order_id=order["order_id"],
                            status="canceled",
                        )
                        if updated:
                            order = updated

        return BillingOrderStatusResponse(
            order_id=order["order_id"],
            package_id=order["package_id"],
            credits=order["credits"],
            amount_krw=order["amount_krw"],
            status=order["status"],
            paddle_transaction_id=order.get("paddle_transaction_id"),
            wallet=_wallet_response(user.user_id),
            completed_at=order.get("completed_at"),
        )

    @router.post("/v1/billing/webhooks/paddle", response_model=PaddleWebhookAckResponse, tags=["Billing"])
    async def handle_paddle_webhook(
        request: Request,
        paddle_signature: Optional[str] = Header(default=None, alias="Paddle-Signature"),
    ) -> PaddleWebhookAckResponse:
        secret = (settings.paddle_webhook_secret or "").strip()
        if not secret:
            raise _api_error(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "WEBHOOK_NOT_CONFIGURED",
                "Paddle 웹훅 시크릿이 설정되지 않았습니다.",
            )

        raw_body = await request.body()
        if not verify_paddle_webhook_signature(
            raw_body,
            paddle_signature,
            secret,
            tolerance_sec=settings.paddle_webhook_tolerance_sec,
        ):
            raise _api_error(
                status.HTTP_401_UNAUTHORIZED,
                "INVALID_WEBHOOK_SIGNATURE",
                "Paddle 웹훅 서명 검증에 실패했습니다.",
            )

        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except Exception as exc:
            raise _api_error(status.HTTP_400_BAD_REQUEST, "INVALID_JSON", "잘못된 JSON 본문입니다.") from exc

        event_id = payload.get("event_id")
        event_type = payload.get("event_type")
        data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
        txn_id = data.get("id")
        custom_data = data.get("custom_data") if isinstance(data.get("custom_data"), dict) else {}
        order_id = custom_data.get("order_id")
        raw_text = raw_body.decode("utf-8", errors="replace")

        if event_type in {"transaction.completed", "transaction.paid"}:
            updated, credited, _ = project_store.complete_billing_order_atomic(
                order_id=order_id,
                paddle_transaction_id=txn_id,
                event_id=event_id,
                event_type=event_type,
                payload_json=raw_text,
                default_free_videos=settings.initial_free_videos,
            )
            return PaddleWebhookAckResponse(
                received=True,
                event_id=event_id,
                event_type=event_type,
                credited=credited,
                order_id=(updated or {}).get("order_id") or order_id,
            )

        if event_type in {"transaction.payment_failed", "transaction.canceled"}:
            target_status = "failed" if event_type == "transaction.payment_failed" else "canceled"
            updated = project_store.mark_billing_order_status(
                order_id=order_id,
                paddle_transaction_id=txn_id,
                status=target_status,
                event_id=event_id,
                event_type=event_type,
                payload_json=raw_text,
            )
            return PaddleWebhookAckResponse(
                received=True,
                event_id=event_id,
                event_type=event_type,
                credited=False,
                order_id=(updated or {}).get("order_id") or order_id,
            )

        return PaddleWebhookAckResponse(
            received=True,
            event_id=event_id,
            event_type=event_type,
            credited=False,
            order_id=order_id,
        )

    return router
