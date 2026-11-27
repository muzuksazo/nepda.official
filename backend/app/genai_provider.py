"""Official google-genai SDK media generation & 05_jobs.json executor.

Replaces local Chrome UI automation (`flow_automator.py`) with server-to-server
calls using `google-genai>=3.0.0`, supporting both AI Studio (`GEMINI_API_KEY`)
and Vertex AI / Workload Identity (`GOOGLE_GENAI_USE_VERTEXAI=true`).
"""

from __future__ import annotations

import base64
from contextvars import ContextVar, Token
import io
import json
import mimetypes
import os
import re
import subprocess
import time
import wave
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

import httpx
from google import genai
from google.auth import exceptions as google_auth_exceptions
from google.auth import identity_pool
from google.genai import types

from .config import Settings


class BudgetExceededError(RuntimeError):
    """Raised when estimated video generation credits exceed max_credits."""


@dataclass
class MediaResult:
    """Metadata for one generated or reused media asset."""

    path: str
    model: str
    interaction_id: Optional[str] = None
    elapsed_sec: float = 0.0
    bytes_written: int = 0
    skipped: bool = False


_REQUEST_VERCEL_OIDC_TOKEN: ContextVar[Optional[str]] = ContextVar(
    "_REQUEST_VERCEL_OIDC_TOKEN",
    default=None,
)


def bind_vercel_oidc_token(token: str) -> Token[Optional[str]]:
    """Bind a per-request Vercel OIDC JWT (from `x-vercel-oidc-token`) to context."""
    return _REQUEST_VERCEL_OIDC_TOKEN.set(token.strip())


def reset_vercel_oidc_token(reset_token: Token[Optional[str]]) -> None:
    """Restore the previous request-scoped Vercel OIDC token binding."""
    _REQUEST_VERCEL_OIDC_TOKEN.reset(reset_token)


def get_active_vercel_oidc_token(token_env_var: str = "VERCEL_OIDC_TOKEN") -> Optional[str]:
    """Return active Vercel OIDC JWT from request context or process environment."""
    from_ctx = _REQUEST_VERCEL_OIDC_TOKEN.get()
    if from_ctx:
        cleaned = from_ctx.strip()
        if cleaned:
            return cleaned
    from_env = os.environ.get(token_env_var, "").strip()
    return from_env or None


class VercelOidcSubjectTokenSupplier(identity_pool.SubjectTokenSupplier):
    """Supply a Vercel OIDC JWT from request header context or environment for GCP WIF."""

    def __init__(self, token_env_var: str = "VERCEL_OIDC_TOKEN") -> None:
        self._token_env_var = token_env_var

    def get_subject_token(self, context: Any, request: Any) -> str:
        """Return the active Vercel OIDC subject token or raise RefreshError."""
        token = get_active_vercel_oidc_token(self._token_env_var)
        if not token:
            raise google_auth_exceptions.RefreshError(
                f"{self._token_env_var} / x-vercel-oidc-token is not set for GCP WIF exchange."
            )
        return token


def build_vercel_wif_credentials(
    provider: str,
    service_account_email: str,
    *,
    token_env_var: str = "VERCEL_OIDC_TOKEN",
) -> identity_pool.Credentials:
    """Create identity_pool Credentials exchanging Vercel OIDC tokens via STS."""
    clean_provider = provider.strip()
    audience = (
        clean_provider
        if clean_provider.startswith("//iam.googleapis.com/")
        else f"//iam.googleapis.com/{clean_provider.lstrip('/')}"
    )
    return identity_pool.Credentials(
        audience=audience,
        subject_token_type="urn:ietf:params:oauth:token-type:jwt",
        token_url="https://sts.googleapis.com/v1/token",
        subject_token_supplier=VercelOidcSubjectTokenSupplier(token_env_var=token_env_var),
        service_account_impersonation_url=(
            "https://iamcredentials.googleapis.com/v1/projects/-/serviceAccounts/"
            f"{service_account_email.strip()}:generateAccessToken"
        ),
        scopes=["https://www.googleapis.com/auth/cloud-platform"],
    )


def build_genai_client(settings: Settings) -> genai.Client:
    """Create a `google.genai.Client` configured for AI Studio or Vertex AI / WIF."""
    if settings.google_genai_use_vertexai:
        has_wif = bool(
            settings.gcp_workload_identity_provider
            and settings.gcp_service_account_email
            and get_active_vercel_oidc_token()
        )
        if settings.google_vertex_api_key and not has_wif:
            return genai.Client(
                vertexai=True,
                api_key=settings.google_vertex_api_key,
            )
        if not settings.google_cloud_project:
            raise ValueError(
                "GOOGLE_CLOUD_PROJECT is required when GOOGLE_GENAI_USE_VERTEXAI=true"
            )
        if has_wif:
            creds = build_vercel_wif_credentials(
                settings.gcp_workload_identity_provider,
                settings.gcp_service_account_email,
            )
            return genai.Client(
                vertexai=True,
                project=settings.google_cloud_project,
                location=settings.google_cloud_location,
                credentials=creds,
            )
        return genai.Client(
            vertexai=True,
            project=settings.google_cloud_project,
            location=settings.google_cloud_location,
        )
    if not settings.gemini_api_key:
        raise ValueError(
            "GEMINI_API_KEY is required unless GOOGLE_GENAI_USE_VERTEXAI=true"
        )
    return genai.Client(api_key=settings.gemini_api_key)


def _sanitize_gcp_label_value(raw: str) -> str:
    """Normalize a string to a valid GCP billing label value (`[a-z0-9_-]`, <=63 chars)."""
    cleaned = re.sub(r"[^a-z0-9_-]+", "-", raw.strip().lower()).strip("-_")
    return cleaned[:63]


def _vertex_request_labels(settings: Settings, component: str) -> Optional[Dict[str, str]]:
    """Return GCP billing labels when running on Vertex AI, else None for AI Studio."""
    if not settings.google_genai_use_vertexai:
        return None
    app_label = _sanitize_gcp_label_value(settings.gcp_billing_app_label or "")
    if not app_label:
        return None
    labels: Dict[str, str] = {"app": app_label}
    comp_label = _sanitize_gcp_label_value(component)
    if comp_label:
        labels["component"] = comp_label
    return labels


def _require_interactions(client: Any) -> Any:
    interactions_api = getattr(client, "interactions", None)
    if interactions_api is None:
        raise RuntimeError(
            "Installed google-genai SDK lacks client.interactions; "
            'upgrade via `pip install -U "google-genai>=3.0.0"`.'
        )
    return interactions_api


def _parse_pcm_rate(mime_type: Optional[str], default: int = 24000) -> int:
    if not mime_type:
        return default
    m = re.search(r"rate=(\d+)", mime_type, flags=re.IGNORECASE)
    if m:
        rate = int(m.group(1))
        if 8000 <= rate <= 192000:
            return rate
    return default


def _pcm_to_wav_bytes(
    pcm_bytes: bytes,
    *,
    sample_rate: int = 24000,
    channels: int = 1,
    sample_width: int = 2,
) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sample_width)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_bytes)
    return buf.getvalue()


def _decode_payload_bytes(data: Any) -> bytes:
    if isinstance(data, (bytes, bytearray)):
        return bytes(data)
    if isinstance(data, str):
        return base64.b64decode(data)
    raise TypeError(f"Unsupported binary payload type: {type(data)!r}")


def _download_uri(uri: str, api_key: Optional[str] = None) -> bytes:
    headers = {"x-goog-api-key": api_key} if api_key else {}
    with httpx.Client(timeout=120.0, follow_redirects=True) as http:
        resp = http.get(uri, headers=headers)
        resp.raise_for_status()
        return resp.content


def _extract_interaction_media(
    interaction: Any,
    kind: str,
    *,
    api_key: Optional[str] = None,
) -> Tuple[bytes, Optional[str]]:
    """Extract binary media from an Interaction object (output_* or outputs[])."""
    attr_name = f"output_{kind}"
    candidates: List[Any] = []
    direct = getattr(interaction, attr_name, None)
    if direct is not None:
        candidates.append(direct)

    outputs = getattr(interaction, "outputs", None)
    if isinstance(outputs, list):
        for item in outputs:
            itype = getattr(item, "type", None) or (item.get("type") if isinstance(item, dict) else None)
            imime = getattr(item, "mime_type", None) or (item.get("mime_type") if isinstance(item, dict) else None)
            if itype == kind or (isinstance(imime, str) and imime.startswith(f"{kind}/")):
                candidates.append(item)

    for cand in candidates:
        data = cand.get("data") if isinstance(cand, dict) else getattr(cand, "data", None)
        mime = cand.get("mime_type") if isinstance(cand, dict) else getattr(cand, "mime_type", None)
        uri = cand.get("uri") if isinstance(cand, dict) else getattr(cand, "uri", None)
        if data is not None:
            return _decode_payload_bytes(data), mime
        if uri:
            return _download_uri(str(uri), api_key=api_key), mime

    errors = getattr(interaction, "errors", None)
    raise RuntimeError(
        f"Interaction {getattr(interaction, 'id', None)!r} completed without {kind} output "
        f"(errors={errors!r})"
    )


def _image_part_dict(path: str) -> Dict[str, Any]:
    mime, _ = mimetypes.guess_type(path)
    if not mime or not mime.startswith("image/"):
        mime = "image/png"
    raw = Path(path).read_bytes()
    return {
        "type": "image",
        "data": base64.b64encode(raw).decode("ascii"),
        "mime_type": mime,
    }


def _atomic_write(out_path: Path, data: bytes) -> int:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_path.with_suffix(out_path.suffix + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, out_path)
    return len(data)


class GenAIMediaProvider:
    """Async-capable wrapper over `google-genai` for planning, images, video & TTS."""

    def __init__(self, settings: Settings, client: Optional[Any] = None) -> None:
        self.settings = settings
        self.client = client if client is not None else build_genai_client(settings)

    def generate_reference_image(
        self,
        prompt: str,
        out_path: str | Path,
        *,
        aspect_ratio: str = "9:16",
        anchor_paths: Optional[Sequence[str | Path]] = None,
        image_size: str = "1K",
        mime_type: str = "image/png",
        skip_existing: bool = True,
    ) -> MediaResult:
        target = Path(out_path)
        if skip_existing and target.exists() and target.stat().st_size > 0:
            return MediaResult(
                path=str(target),
                model=self.settings.image_model,
                bytes_written=target.stat().st_size,
                skipped=True,
            )

        interactions = _require_interactions(self.client)
        inputs: List[Dict[str, Any]] = [{"type": "text", "text": prompt}]
        for ap in anchor_paths or []:
            ap_str = str(ap)
            if os.path.exists(ap_str):
                inputs.append(_image_part_dict(ap_str))

        t0 = time.monotonic()
        interaction = interactions.create(
            model=self.settings.image_model,
            input=inputs if len(inputs) > 1 else prompt,
            response_format={
                "type": "image",
                "aspect_ratio": aspect_ratio,
                "image_size": image_size,
                "mime_type": mime_type,
            },
            store=True,
        )
        raw, _ = _extract_interaction_media(
            interaction, "image", api_key=self.settings.gemini_api_key
        )
        written = _atomic_write(target, raw)
        return MediaResult(
            path=str(target),
            model=self.settings.image_model,
            interaction_id=getattr(interaction, "id", None),
            elapsed_sec=round(time.monotonic() - t0, 3),
            bytes_written=written,
        )

    def generate_video_clip(
        self,
        prompt: str,
        out_path: str | Path,
        *,
        aspect_ratio: str = "9:16",
        duration_sec: int = 5,
        resolution: str = "720p",
        reference_paths: Optional[Sequence[str | Path]] = None,
        first_frame_path: Optional[str | Path] = None,
        last_frame_path: Optional[str | Path] = None,
        skip_existing: bool = True,
        sleep_fn: Callable[[float], None] = time.sleep,
    ) -> MediaResult:
        target = Path(out_path)
        if skip_existing and target.exists() and target.stat().st_size > 0:
            return MediaResult(
                path=str(target),
                model=self.settings.video_model,
                bytes_written=target.stat().st_size,
                skipped=True,
            )

        interactions = _require_interactions(self.client)
        clamped_dur = max(3, min(15, int(duration_sec)))
        inputs: List[Dict[str, Any]] = [{"type": "text", "text": prompt}]
        attached: List[str] = []
        for candidate in [first_frame_path, *(reference_paths or []), last_frame_path]:
            if candidate:
                cstr = str(candidate)
                if cstr not in attached and os.path.exists(cstr):
                    attached.append(cstr)
                    inputs.append(_image_part_dict(cstr))

        t0 = time.monotonic()
        interaction = interactions.create(
            model=self.settings.video_model,
            input=inputs if len(inputs) > 1 else prompt,
            response_format={
                "type": "video",
                "aspect_ratio": aspect_ratio,
                "duration": f"{clamped_dur}s",
                "resolution": resolution,
            },
            background=True,
            store=True,
        )
        iid = getattr(interaction, "id", None)
        deadline = t0 + float(self.settings.video_timeout_sec)

        while getattr(interaction, "status", None) not in {"completed", "failed", "cancelled"}:
            if time.monotonic() >= deadline:
                raise TimeoutError(
                    f"Video interaction {iid!r} timed out after {self.settings.video_timeout_sec}s"
                )
            sleep_fn(float(self.settings.poll_interval_sec))
            if not iid:
                raise RuntimeError("Background video interaction returned no id to poll")
            interaction = interactions.get(id=iid)

        status = getattr(interaction, "status", None)
        if status in {"failed", "cancelled"}:
            raise RuntimeError(
                f"Video interaction {iid!r} ended with status={status!r}, "
                f"errors={getattr(interaction, 'errors', None)!r}"
            )

        raw, _ = _extract_interaction_media(
            interaction, "video", api_key=self.settings.gemini_api_key
        )
        written = _atomic_write(target, raw)
        return MediaResult(
            path=str(target),
            model=self.settings.video_model,
            interaction_id=iid,
            elapsed_sec=round(time.monotonic() - t0, 3),
            bytes_written=written,
        )

    def generate_tts_beat(
        self,
        text: str,
        out_wav_path: str | Path,
        *,
        voice_name: Optional[str] = None,
        style_prompt: Optional[str] = None,
        skip_existing: bool = True,
    ) -> MediaResult:
        target = Path(out_wav_path)
        if skip_existing and target.exists() and target.stat().st_size > 0:
            return MediaResult(
                path=str(target),
                model=self.settings.tts_model,
                bytes_written=target.stat().st_size,
                skipped=True,
            )

        chosen_voice = voice_name or self.settings.tts_default_voice
        prompt_text = f"[{style_prompt.strip()}] {text}" if style_prompt else text
        t0 = time.monotonic()
        response = self.client.models.generate_content(
            model=self.settings.tts_model,
            contents=prompt_text,
            config=types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=types.SpeechConfig(
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=chosen_voice)
                    )
                ),
                labels=_vertex_request_labels(self.settings, "tts"),
            ),
        )

        audio_bytes: Optional[bytes] = None
        audio_mime: Optional[str] = None
        for cand in getattr(response, "candidates", None) or []:
            content = getattr(cand, "content", None)
            for part in getattr(content, "parts", None) or []:
                inline = getattr(part, "inline_data", None)
                if inline is not None and getattr(inline, "data", None) is not None:
                    audio_bytes = _decode_payload_bytes(inline.data)
                    audio_mime = getattr(inline, "mime_type", None)
                    break
            if audio_bytes is not None:
                break

        if not audio_bytes:
            raise RuntimeError("TTS response contained no inline audio payload")

        is_wav = audio_bytes[:4] == b"RIFF" or (
            isinstance(audio_mime, str) and "wav" in audio_mime.lower()
        )
        wav_bytes = (
            audio_bytes
            if is_wav and audio_bytes[:4] == b"RIFF"
            else _pcm_to_wav_bytes(
                audio_bytes,
                sample_rate=_parse_pcm_rate(audio_mime, default=24000),
            )
        )
        written = _atomic_write(target, wav_bytes)
        return MediaResult(
            path=str(target),
            model=self.settings.tts_model,
            elapsed_sec=round(time.monotonic() - t0, 3),
            bytes_written=written,
        )

    def plan_ad_spec(
        self,
        product_facts: str,
        source_meta: Dict[str, Any],
        contact_sheet_path: str | Path,
        *,
        track_archetype: str = "A_bgrade_reversal",
        past_archetypes: Optional[Sequence[str]] = None,
    ) -> Dict[str, Any]:
        """Generate a schema-compliant 05_ad_spec JSON using the multimodal planner."""
        avoid_list = sorted({a for a in (past_archetypes or []) if a})
        system_note = (
            "You are a Korean shortform performance-ad director. Output strict JSON ONLY "
            "matching 05_ad_spec.json fields (`project_id`, `title`, `mode`, `track_archetype`, "
            "`a_genre_archetype`, `hook_window_sec`, `framing_mode`, `disclosure`, `source_video`, "
            "`source_duration`, `usps`, `timeline`, `captions`, `cta`). Ground every product "
            "claim strictly in verified [Fxx] lines from 00_product_facts.md. "
            "Do NOT reskin any past `a_genre_archetype`: avoid="
            + json.dumps(avoid_list, ensure_ascii=False)
        )
        contents: List[Any] = [
            f"Track archetype: {track_archetype}\n"
            f"Source metadata:\n{json.dumps(source_meta, ensure_ascii=False)}\n\n"
            f"Product facts ledger:\n{product_facts}\n",
        ]
        cs_path = Path(contact_sheet_path)
        if cs_path.exists():
            contents.append(
                types.Part.from_bytes(data=cs_path.read_bytes(), mime_type="image/png")
            )

        resp = self.client.models.generate_content(
            model=self.settings.planner_model,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=system_note,
                response_mime_type="application/json",
                labels=_vertex_request_labels(self.settings, "planner"),
            ),
        )
        raw_text = (getattr(resp, "text", None) or "").strip()
        if not raw_text:
            raise RuntimeError("Planner returned empty JSON output")
        return json.loads(raw_text)


def _extract_anchor_frame(source_video: str, time_sec: float, out_path: Path) -> int:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg",
        "-y",
        "-v",
        "error",
        "-ss",
        f"{max(0.0, float(time_sec)):.3f}",
        "-i",
        source_video,
        "-frames:v",
        "1",
        str(out_path),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0 or not out_path.exists():
        raise RuntimeError(f"Anchor frame extraction failed ({out_path}): {proc.stderr}")
    return out_path.stat().st_size


def execute_jobs_file(
    jobs_path: str | Path,
    project_dir: str | Path,
    provider: GenAIMediaProvider,
    *,
    source_video: Optional[str] = None,
    concurrency: int = 3,
    max_credits: Optional[int] = None,
    skip_existing: bool = True,
    only_unit_ids: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    """Execute a 05_jobs.json manifest via google-genai instead of Chrome Flow."""
    proj = Path(project_dir).resolve()
    jobs_data = json.loads(Path(jobs_path).read_text(encoding="utf-8"))
    default_ar = jobs_data.get("aspect_ratio") or "9:16"
    default_res = jobs_data.get("resolution") or "720p"

    asset_paths: Dict[str, str] = {}
    anchor_reports: List[Dict[str, Any]] = []
    for a in jobs_data.get("anchors") or []:
        aid = a["id"]
        rel = a.get("file") or f"refs/{aid}.png"
        apath = (proj / rel).resolve()
        if not apath.exists():
            if not source_video:
                raise FileNotFoundError(
                    f"Anchor {aid} missing at {apath} and no source_video provided"
                )
            size = _extract_anchor_frame(source_video, float(a.get("time_sec", 0.0)), apath)
            anchor_reports.append({"id": aid, "path": str(apath), "bytes_written": size, "skipped": False})
        else:
            anchor_reports.append({"id": aid, "path": str(apath), "bytes_written": apath.stat().st_size, "skipped": True})
        asset_paths[aid] = str(apath)

    refs = list(jobs_data.get("references") or [])
    ref_reports: List[Dict[str, Any]] = []
    if refs:
        with ThreadPoolExecutor(max_workers=max(1, int(concurrency))) as pool:
            futs = {}
            for r in refs:
                rid = r["id"]
                out_file = proj / (r.get("file") or f"refs/{rid}.png")
                att = [asset_paths[aid] for aid in (r.get("attach_ids") or []) if aid in asset_paths]
                ar = (r.get("settings") or {}).get("aspect_ratio") or default_ar
                fut = pool.submit(
                    provider.generate_reference_image,
                    r["prompt"],
                    out_file,
                    aspect_ratio=ar,
                    anchor_paths=att,
                    skip_existing=skip_existing,
                )
                futs[fut] = rid
            for fut in as_completed(futs):
                rid = futs[fut]
                res = fut.result()
                asset_paths[rid] = res.path
                ref_reports.append({"id": rid, **asdict(res)})

    all_units = list(jobs_data.get("units") or [])
    if only_unit_ids is not None:
        wanted = set(only_unit_ids)
        target_units = [u for u in all_units if u.get("id") in wanted]
    else:
        target_units = all_units

    est_total = sum(int(u.get("est_credits") or 0) for u in target_units)
    if max_credits is not None and est_total > int(max_credits):
        raise BudgetExceededError(
            f"Estimated credits {est_total} exceed max_credits cap {int(max_credits)}"
        )

    unit_reports: List[Dict[str, Any]] = []
    if target_units:
        with ThreadPoolExecutor(max_workers=max(1, int(concurrency))) as pool:
            futs = {}
            for u in target_units:
                uid = u["id"]
                settings_map = u.get("settings") or {}
                out_rel = (u.get("outputs") or [f"clips/{uid}_t1.mp4"])[0]
                out_file = proj / out_rel
                ref_ids = list(u.get("reference_ids") or [])
                ref_paths = [asset_paths[rid] for rid in ref_ids if rid in asset_paths]
                first_p = asset_paths.get(u.get("first_frame") or "")
                last_p = asset_paths.get(u.get("last_frame") or "")
                fut = pool.submit(
                    provider.generate_video_clip,
                    u["prompt"],
                    out_file,
                    aspect_ratio=settings_map.get("aspect_ratio") or default_ar,
                    duration_sec=int(settings_map.get("duration_sec") or 5),
                    resolution=settings_map.get("resolution") or default_res,
                    reference_paths=ref_paths,
                    first_frame_path=first_p,
                    last_frame_path=last_p,
                    skip_existing=skip_existing,
                )
                futs[fut] = (uid, int(u.get("est_credits") or 0))
            for fut in as_completed(futs):
                uid, est_cr = futs[fut]
                res = fut.result()
                unit_reports.append({"id": uid, "est_credits": est_cr, **asdict(res)})

    tts_beats = list(jobs_data.get("tts_beats") or [])
    tts_reports: List[Dict[str, Any]] = []
    if tts_beats:
        with ThreadPoolExecutor(max_workers=max(1, int(concurrency))) as pool:
            futs = {}
            for b in tts_beats:
                bid = b.get("id") or "VO"
                out_file = proj / (b.get("file") or f"audio/{bid}.wav")
                fut = pool.submit(
                    provider.generate_tts_beat,
                    b["text"],
                    out_file,
                    voice_name=b.get("voice_name"),
                    style_prompt=b.get("style_prompt"),
                    skip_existing=skip_existing,
                )
                futs[fut] = bid
            for fut in as_completed(futs):
                bid = futs[fut]
                res = fut.result()
                tts_reports.append({"id": bid, **asdict(res)})

    report = {
        "project_id": jobs_data.get("project_id", ""),
        "auth_mode": provider.settings.auth_mode,
        "anchors": sorted(anchor_reports, key=lambda x: x["id"]),
        "references": sorted(ref_reports, key=lambda x: x["id"]),
        "units": sorted(unit_reports, key=lambda x: x["id"]),
        "tts_beats": sorted(tts_reports, key=lambda x: x["id"]),
        "total_est_credits": est_total,
    }
    report_path = proj / "generation_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report
