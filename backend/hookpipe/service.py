"""코어 라우터(`backend/app/projects_router.py`)가 부르는 진입점.

- process_hook: POST /hooks 의 백그라운드 작업. 훅 하나를 만들어 OUTPUT_DIR/{project_id}/{hook_id}/ 에 둔다.
- process_render: POST /renders 의 백그라운드 작업. 훅(있으면 재사용) 뒤에 올린 본편을 붙여 최종 영상을 만든다.
DB 갱신과 파일 올리기는 코어의 저장소 객체(project_store, job_store, storage)를 그대로 쓴다.

과금 방어:
- 같은 시나리오·같은 목소리의 완성된 훅은 다시 만들지 않는다.
- 같은 시나리오의 훅 생성은 한 번에 하나만 돈다 (겹친 요청은 기다렸다가 완성본을 쓴다).
- 받은 클립·음성은 시나리오 단위 폴더에 모아 둬서, 중간에 실패한 뒤 다시 요청해도 이미 받은 것은 다시 사지 않는다.
"""

from __future__ import annotations

import hashlib
import logging
import shutil
import threading
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from .body import attach_body
from .media import MediaTools, find_tools
from .body_edit import ScriptWriter, body_cache_key, make_body
from .selfhosted import SelfHostedMedia
from .render import HookRenderResult, _subtitle_style, extract_reference_frames, render_hook, write_scenario_and_srt
from .tts import InworldTts, MediaWithTts

logger = logging.getLogger("hookpipe.service")

ProviderFactory = Callable[[Any], Any]
ACTIVE_HOOK_MAX_AGE = timedelta(minutes=30)  # 이보다 오래 queued/running 인 훅은 멈춘 것으로 본다

EMPTY_FILES: Dict[str, Any] = {
    "hook_video": None,
    "tts_audio": None,
    "subtitles_srt": None,
    "scenario_json": None,
    "storyboard_images": [],
}


def is_worker_scenario(scenario: Optional[Dict[str, Any]]) -> bool:
    """A·B·C 작업자가 만든 시나리오인지. planner-api 시나리오는 ad_spec 에 timeline 이 있어 기존 경로로 간다."""
    if not scenario:
        return False
    spec = scenario.get("ad_spec") or {}
    return bool(scenario.get("beats")) and not spec.get("timeline")


class HookPipeline:
    def __init__(
        self,
        settings: Any,
        project_store: Any,
        job_store: Any,
        storage: Any,
        *,
        provider_factory: Optional[ProviderFactory] = None,
        tools: Optional[MediaTools] = None,
        body_writer: Optional[ScriptWriter] = None,
        selfhosted_media: Any = None,
    ) -> None:
        self.settings = settings
        self._body_writer = body_writer
        self.project_store = project_store
        self.job_store = job_store
        self.storage = storage
        self._provider_factory = provider_factory
        self._tools = tools
        self._selfhosted_media = selfhosted_media  # 테스트에서 가짜 FLUX·MiniMax 를 넣는다
        self._locks: Dict[Tuple[str, str], threading.Lock] = {}
        self._locks_guard = threading.Lock()

    # ---- 공통 도우미 -------------------------------------------------

    def _provider(self) -> Any:
        if self._provider_factory is not None:
            media = self._provider_factory(self.settings)
        else:
            from app.genai_provider import GenAIMediaProvider  # 늦게 불러와 순환 import 를 피한다

            media = GenAIMediaProvider(self.settings)
        if getattr(self.settings, "tts_provider", "gemini") == "inworld":
            return MediaWithTts(media, InworldTts(self.settings))
        return media

    def _media(self) -> MediaTools:
        if self._tools is None:
            self._tools = find_tools(
                getattr(self.settings, "ffmpeg_bin", None), getattr(self.settings, "ffprobe_bin", None)
            )
        return self._tools

    def _lock(self, project_id: str, scenario_id: str) -> threading.Lock:
        with self._locks_guard:
            return self._locks.setdefault((project_id, scenario_id), threading.Lock())

    def is_dry_run(self) -> bool:
        return getattr(self.settings, "hook_render_mode", "video_model") == "dry_run"

    def uses_video_model(self, scenario: Optional[Dict[str, Any]]) -> bool:
        """이 시나리오로 훅을 만들면 과금 호출이 나가는지."""
        return is_worker_scenario(scenario) and not self.is_dry_run()

    def hook_dir(self, project_id: str, hook_id: str) -> Path:
        return Path(self.settings.output_dir).resolve() / project_id / hook_id

    def cache_dir(self, project_id: str, scenario_id: str) -> Path:
        safe = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in scenario_id) or "scenario"
        return Path(self.settings.output_dir).resolve() / project_id / "_cache" / safe

    def _tts_key(self, tts: Optional[Dict[str, Any]]) -> Tuple[bool, Optional[str]]:
        tts = tts or {}
        enabled = bool(tts.get("enabled", True))
        voice = (tts.get("voice") or getattr(self.settings, "tts_default_voice", None)) if enabled else None
        return enabled, voice

    def resolve_asset(self, ref: str, work_dir: Path) -> Optional[Path]:
        """미리 만든 훅 소재(`prebuilt_clip` 등)의 위치. HOOK_ASSETS_DIR 아래의 상대 경로이거나 저장소 키다.

        HOOK_ASSETS_DIR 밖을 가리키는 경로(절대 경로, ../)는 받지 않는다.
        """
        base = Path(getattr(self.settings, "hook_assets_dir", "")).resolve()
        roots = [base]
        templates = str(getattr(self.settings, "hook_a_templates", "") or "")
        if templates and not templates.startswith("storage:"):
            roots.append(Path(templates).resolve())  # A 템플릿을 로컬 폴더에 둔 경우 (개발·테스트)
        try:
            local = (base / ref).resolve()
        except (OSError, ValueError):
            local = None
        if local is not None and any(local.is_relative_to(root) for root in roots):
            if local.is_file():
                return local
        elif local is not None:
            return None
        dest = work_dir / f"{hashlib.sha1(ref.encode('utf-8')).hexdigest()[:12]}{Path(ref).suffix or '.mp4'}"
        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            self.storage.download_file(ref, dest)
        except Exception as exc:
            logger.warning("미리 만든 소재를 찾지 못했습니다 (%s): %s", ref, exc)
            return None
        return dest if dest.is_file() else None

    def _upload_clip_paths(self, project: Dict[str, Any], work_dir: Path) -> List[Path]:
        """올린 본편 클립을 촬영 순서(shot_no)대로 로컬 경로로 돌려준다. 저장소에만 있으면 매번 새로 내려받는다."""
        uploads = project.get("uploads") or {}
        clips = sorted(uploads.get("clips") or [], key=lambda c: int(c.get("shot_no") or 0))
        paths: List[Path] = []
        for index, clip in enumerate(clips, start=1):
            local = clip.get("local_path")
            if local and Path(local).is_file():
                paths.append(Path(local))
                continue
            key = clip.get("object_key")
            if not key:
                continue
            suffix = Path(str(key)).suffix or ".mp4"
            dest = work_dir / f"upload_{index:02d}{suffix}"
            try:
                dest.unlink(missing_ok=True)  # 예전에 받은 파일을 다시 쓰지 않는다 (다시 올린 영상 반영)
                self.storage.download_file(key, dest)
            except Exception as exc:
                logger.warning("업로드 클립을 내려받지 못했습니다 (%s): %s", key, exc)
                continue
            if dest.is_file():
                paths.append(dest)
        return paths

    def _usage_cb(
        self,
        project: Dict[str, Any],
        *,
        hook_type: Optional[str] = None,
        job_id: Optional[str] = None,
    ) -> Optional[Callable[..., None]]:
        if not hasattr(self.project_store, "record_api_usage"):
            return None
        pid = str(project.get("project_id") or "")
        uid = project.get("user_id")

        def _cb(**kw: Any) -> None:
            from app.usage_telemetry import record_usage_safe

            record_usage_safe(
                self.project_store,
                self.settings,
                project_id=pid,
                user_id=uid,
                job_id=job_id,
                hook_type=hook_type,
                **kw,
            )

        return _cb

    def _render(
        self,
        project: Dict[str, Any],
        scenario: Dict[str, Any],
        out_dir: Path,
        tts: Dict[str, Any],
        clips: List[Path],
        progress: Optional[Callable[[str], None]] = None,
        job_id: Optional[str] = None,
    ) -> HookRenderResult:
        media = self._media()
        enabled, voice = self._tts_key(tts)
        if self._selfhosted(scenario):
            # 자체 모델: 콘티 스틸컷을 첫 프레임으로 MiniMax 가 장면 클립을 만들고, 조립은 미리 만든 클립처럼 한다
            scenario = self._selfhosted_clips(project, scenario, job_id or out_dir.name, progress)
            refs = []
        else:
            refs = extract_reference_frames(clips, out_dir / "_work" / "refs", media) if clips else []
        return render_hook(
            scenario,
            project.get("product") or {},
            out_dir,
            provider=self._provider(),
            settings=self.settings,
            tts_enabled=enabled,
            voice=voice,
            product_refs=refs,
            tools=media,
            cache_dir=self.cache_dir(str(project["project_id"]), str(scenario.get("scenario_id") or "scenario")),
            resolve_asset=lambda ref: self.resolve_asset(ref, out_dir / "_work" / "assets"),
            progress=progress,
            on_usage=self._usage_cb(
                project,
                hook_type=str(scenario.get("type") or "") or None,
                job_id=job_id,
            ),
        )

    def _selfhosted(self, scenario: Dict[str, Any]) -> bool:
        if getattr(self.settings, "hook_media_engine", "gemini") != "selfhosted":
            return False
        if str(scenario.get("type") or "").upper() == "A":
            return False  # A 는 템플릿 클립 + 착지 장면 (기존 길)
        return True

    def _selfhosted_clips(
        self,
        project: Dict[str, Any],
        scenario: Dict[str, Any],
        job_key: str,
        progress: Optional[Callable[[str], None]] = None,
    ) -> Dict[str, Any]:
        """콘티 스틸컷(저장소) + 움직임 묘사로 장면 클립을 만들어 각 장면의 prebuilt_clip 으로 넣은 시나리오 사본을 돌려준다.

        콘티가 없거나 일부 장면이 빠졌으면 그 자리에서 스틸컷부터 만든다.
        """
        import copy

        engine = self._selfhosted_media or SelfHostedMedia(self.settings)
        self._selfhosted_media = engine
        sc = copy.deepcopy(scenario)
        beats = [b for b in sc.get("beats") or [] if isinstance(b, dict)]
        safe = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in job_key) or "job"
        rel_dir = Path("selfhosted") / str(project.get("project_id") or "p") / safe
        work = Path(getattr(self.settings, "hook_assets_dir", "")).resolve() / rel_dir
        work.mkdir(parents=True, exist_ok=True)

        stills: Dict[int, Tuple[bytes, str]] = {}
        for frame in sc.get("storyboard_frames") or []:
            if not isinstance(frame, dict) or not frame.get("object_key") or not frame.get("motion_prompt"):
                continue
            order = int(frame.get("beat_order") or 0)
            dest = work / f"still{order}.png"
            try:
                self.storage.download_file(str(frame["object_key"]), dest)
                stills[order] = (dest.read_bytes(), str(frame["motion_prompt"]))
            except Exception as exc:
                logger.warning("콘티 스틸컷을 받지 못했습니다 (%s): %s", frame.get("object_key"), exc)
        if any(int(b.get("order") or 0) not in stills for b in beats):
            if progress:
                progress("STORYBOARD")
            for item in engine.storyboard(sc, project.get("product") or {}):
                stills.setdefault(int(item["beat_order"]), (item["png"], item.get("motion_prompt") or ""))

        items: List[Tuple[bytes, str, float]] = []
        orders: List[int] = []
        for beat in beats:
            order = int(beat.get("order") or 0)
            if order in stills:
                png, motion = stills[order]
                items.append((png, motion, float(beat.get("duration_sec") or 4.0)))
                orders.append(order)
        if progress:
            progress(f"CLIP 1/{len(items)}")
        made = engine.clips(items)
        by_order = dict(zip(orders, made))
        for beat in beats:
            data = by_order.get(int(beat.get("order") or 0))
            if data:
                name = f"clip{int(beat.get('order') or 0)}.mp4"
                (work / name).write_bytes(data)
                beat["prebuilt_clip"] = (rel_dir / name).as_posix()
        return sc

    def _publish_hook_files(self, project_id: str, hook_id: str, out_dir: Path, files: Dict[str, Any]) -> Dict[str, str]:
        """훅 결과를 저장소에 올린다. 키: projects/{project_id}/hooks/{hook_id}/{파일 이름} (팀 합의 2026-11-27).

        콘티 이미지는 projects/{project_id}/storyboards/{scenario_id}/ 가 정본이라 여기서는 올리지 않는다.
        실패해도 훅 자체는 서버 디스크에 있으므로 경고만 남긴다.
        """
        keys: Dict[str, str] = {}
        for name in [files.get("hook_video"), files.get("tts_audio"), files.get("subtitles_srt"), files.get("scenario_json")]:
            if not name or not (out_dir / name).is_file():
                continue
            key = f"projects/{project_id}/hooks/{hook_id}/{name}"
            try:
                self.storage.upload_file(out_dir / name, key)
                keys[name] = key
            except Exception as exc:
                logger.warning("훅 파일을 저장소에 올리지 못했습니다 (%s): %s", key, exc)
        return keys

    def _shared_body(self, project: Dict[str, Any], clips: List[Path], voice: Optional[str], job_id: str) -> Tuple[Path, Optional[Path], List[str]]:
        """A·B·C 공용 본편. FR-009 결과(project.body)가 있으면 그것을, 없으면 촬영본으로 10초 본편을 만든다(한 번만)."""
        body = project.get("body") or {}
        # FR-009 본편 (app/body_pipeline.py, POST /v1/projects/{id}/body) 의 manifest: object_keys.body_video / body_srt
        keys = body.get("object_keys") or {}
        body = {**body, "video_key": body.get("video_key") or keys.get("body_video"),
                "srt_key": body.get("srt_key") or keys.get("body_srt")}
        project = {**project, "body": body}
        given = body.get("video_path")
        if not given and body.get("video_key"):
            dest = Path(self.settings.output_dir).resolve() / str(project["project_id"]) / "_renders" / job_id / "body_in.mp4"
            dest.parent.mkdir(parents=True, exist_ok=True)
            try:
                self.storage.download_file(body["video_key"], dest)
                given = str(dest)
            except Exception as exc:
                logger.warning("FR-009 본편을 내려받지 못해 직접 만듭니다 (%s): %s", body.get("video_key"), exc)
        if given and Path(given).is_file():
            return Path(given), self._body_srt(project, Path(given).parent), []
        project_id = str(project["project_id"])
        key = body_cache_key(clips, project.get("product") or {}, self.settings)
        body_dir = Path(self.settings.output_dir).resolve() / project_id / "_body" / key
        body_settings = self.settings
        usage_cb = self._usage_cb(project, job_id=job_id)
        if usage_cb is not None:
            from .workers import _SettingsOverlay

            body_settings = _SettingsOverlay(self.settings, _on_usage=usage_cb)
        with self._lock(project_id, "_body"):
            made = make_body(
                clips,
                project.get("product") or {},
                body_dir,
                provider=self._provider(),
                settings=body_settings,
                tools=self._media(),
                writer=self._body_writer,
                voice=voice,
                subtitle_style=_subtitle_style(),
            )
        for name in ("body.mp4", "body.srt"):
            try:
                self.storage.upload_file(body_dir / name, f"projects/{project_id}/body/{key}/{name}")
            except Exception as exc:
                logger.warning("본편 파일을 저장소에 올리지 못했습니다 (%s): %s", name, exc)
        return made.video, made.srt, made.warnings

    def _body_srt(self, project: Dict[str, Any], work_dir: Path) -> Optional[Path]:
        """FR-009 가 만든 본편 자막. project.body.srt_key(저장소 키) 또는 project.body.srt_path 가 있으면 쓴다."""
        body = project.get("body") or {}
        local = body.get("srt_path")
        if local and Path(local).is_file():
            return Path(local)
        key = body.get("srt_key")
        if not key:
            return None
        dest = work_dir / "body.srt"
        try:
            self.storage.download_file(key, dest)
        except Exception as exc:
            logger.warning("본편 자막을 내려받지 못했습니다 (%s): %s", key, exc)
            return None
        return dest if dest.is_file() else None

    # ---- 훅 재사용 ---------------------------------------------------

    def _is_active(self, hook: Dict[str, Any]) -> bool:
        if hook.get("status") not in ("queued", "running"):
            return False
        try:
            updated = datetime.fromisoformat(str(hook.get("updated_at")))
        except ValueError:
            return False
        if updated.tzinfo is None:
            updated = updated.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) - updated < ACTIVE_HOOK_MAX_AGE

    def find_existing_hook(
        self,
        project_id: str,
        scenario_id: str,
        tts: Optional[Dict[str, Any]],
        *,
        include_active: bool = False,
    ) -> Optional[Dict[str, Any]]:
        """같은 시나리오·같은 목소리 설정으로 이미 만든 훅(include_active 면 만드는 중인 훅도)."""
        wanted = self._tts_key(tts)
        for hook in self.project_store.list_hooks_for_project(project_id):
            if hook.get("scenario_id") != scenario_id or self._tts_key(hook.get("tts")) != wanted:
                continue
            if hook.get("status") == "done":
                if (hook.get("files") or {}).get("hook_video") and (Path(hook["output_dir"]) / "hook.mp4").is_file():
                    return hook
            elif include_active and self._is_active(hook):
                return hook
        return None

    # ---- POST /hooks -------------------------------------------------

    def process_hook(
        self,
        project_id: str,
        hook_id: str,
        scenario: Dict[str, Any],
        out_dir: Path,
        tts: Optional[Dict[str, Any]] = None,
    ) -> None:
        try:
            self.project_store.update_hook(hook_id, status="running")
            files = dict(EMPTY_FILES)
            if not self.uses_video_model(scenario):
                # dry_run 이거나 planner-api 시나리오: 과금 호출 없이 scenario.json 과 자막만 쓴다
                files.update(write_scenario_and_srt(scenario, out_dir))
                files["storyboard_images"] = [
                    str(f["image_url"])
                    for f in (scenario.get("storyboard_frames") or [])
                    if isinstance(f, dict) and f.get("image_url")
                ]
            else:
                project = self.project_store.get_project(project_id)
                if not project:
                    raise RuntimeError("프로젝트를 찾을 수 없습니다.")
                with self._lock(project_id, str(scenario.get("scenario_id"))):
                    clips = self._upload_clip_paths(project, out_dir / "_work" / "uploads")
                    files.update(self._render(project, scenario, out_dir, tts or {}, clips).files)
                self._publish_hook_files(project_id, hook_id, out_dir, files)
                shutil.rmtree(out_dir / "_work" / "uploads", ignore_errors=True)
            self.project_store.update_hook(hook_id, status="done", files=files)
            self.project_store.update_project(project_id, status="HOOK_READY")
        except Exception as exc:
            logger.exception("훅 생성 실패 (%s/%s)", project_id, hook_id)
            self.project_store.update_hook(hook_id, status="failed", error=str(exc) or type(exc).__name__)
            self.project_store.update_project(project_id, status="FAILED")

    # ---- POST /renders -----------------------------------------------

    def process_render(
        self,
        project_id: str,
        job_id: str,
        user_id: str,
        scenario: Dict[str, Any],
        voice: Optional[str] = None,
    ) -> None:
        """훅 + 본편 → 최종 영상. 결과는 기존 /deliverables 가 읽는 모양(artifacts.rendered[0])으로 남긴다."""
        store = self.job_store
        job_dir: Optional[Path] = None
        try:
            project = self.project_store.get_project(project_id)
            if not project:
                raise RuntimeError("프로젝트를 찾을 수 없습니다.")
            scenario_id = str(scenario["scenario_id"])
            tts = {"enabled": True, "voice": voice}
            store.update_job(job_id, status="RUNNING", stage="UPLOADS")

            # 본편 파일을 먼저 확보한다: 못 찾으면 훅에 돈을 쓰기 전에 멈춘다
            job_dir = Path(self.settings.output_dir).resolve() / project_id / "_renders" / job_id
            clips = self._upload_clip_paths(project, job_dir / "uploads")
            if not clips:
                raise RuntimeError("붙일 본편 영상을 찾지 못했습니다. 영상을 다시 올려 주세요.")

            store.update_job(job_id, status="RUNNING", stage="HOOK")
            with self._lock(project_id, scenario_id):
                hook = self.find_existing_hook(project_id, scenario_id, tts)
                if hook:
                    hook_id, out_dir = hook["hook_id"], Path(hook["output_dir"])
                else:
                    hook_id = f"hook_{uuid.uuid4().hex[:10]}"
                    out_dir = self.hook_dir(project_id, hook_id)
                    self.project_store.create_hook(
                        hook_id=hook_id,
                        project_id=project_id,
                        user_id=user_id,
                        scenario_id=scenario_id,
                        job_id=job_id,
                        tts=tts,
                        output_dir=str(out_dir),
                        status="running",
                    )
                    try:
                        result = self._render(
                            project,
                            scenario,
                            out_dir,
                            tts,
                            clips,
                            progress=lambda stage: store.update_job(job_id, stage=f"HOOK:{stage}"),
                            job_id=job_id,
                        )
                    except Exception as exc:
                        self.project_store.update_hook(hook_id, status="failed", error=str(exc) or type(exc).__name__)
                        raise
                    self.project_store.update_hook(hook_id, status="done", files={**EMPTY_FILES, **result.files})
                    self._publish_hook_files(project_id, hook_id, out_dir, result.files)

            store.update_job(job_id, status="RUNNING", stage="BODY")
            # 본편: A·B·C 공용 10초 편집본 (나레이션·자막 포함). 같은 프로젝트의 다른 유형 훅도 같은 본편을 쓴다
            body_video, body_srt, body_warnings = self._shared_body(project, clips, voice, job_id)
            # 최종 파일은 작업마다 다른 폴더에 쓴다 (같은 훅으로 겹쳐 만들어도 서로 덮어쓰지 않는다)
            final_path = job_dir / "final.mp4"
            joined = attach_body(
                out_dir / "hook.mp4",
                [body_video],
                final_path,
                tools=self._media(),
                limit_sec=float(self.settings.body_max_sec),
                hook_srt=out_dir / "hook.srt",
                body_srt=body_srt,
            )
            joined.warnings = [*body_warnings, *joined.warnings]

            # 저장소 키 (팀 합의 2026-11-27): projects/{project_id}/renders/{job_id}/{master.mp4|clean.mp4|final.srt}
            # clean.mp4(자막 없는 판)는 아직 만들지 않는다. 그때까지는 master 를 같이 가리킨다.
            prefix = f"projects/{project_id}/renders/{job_id}"
            entry: Dict[str, Any] = {
                "id": hook_id,
                "duration": joined.duration_sec,
                "hook_duration": joined.hook_sec,
                "body_duration": joined.body_sec,
                "lufs": {"final_lufs": joined.lufs},
                "master_key": f"{prefix}/master.mp4",
                "master_mp4": self.storage.upload_file(final_path, f"{prefix}/master.mp4"),
            }
            entry["clean_key"] = entry["master_key"]
            entry["clean_mp4"] = entry["master_mp4"]
            srt_path = final_path.with_suffix(".srt")
            if srt_path.is_file():
                entry["srt_key"] = f"{prefix}/final.srt"
                entry["srt"] = self.storage.upload_file(srt_path, entry["srt_key"])
            store.update_job(
                job_id,
                status="QC_READY",
                stage="QC_READY",
                artifacts={
                    "pipeline": "hookpipe",
                    "hook_id": hook_id,
                    "local_dir": str(job_dir),
                    "rendered": [entry],
                    "thumbnails": [],
                    "warnings": joined.warnings,
                },
            )
            self.project_store.update_project(project_id, status="DELIVERABLE_READY")
        except Exception as exc:
            logger.exception("최종 영상 생성 실패 (%s/%s)", project_id, job_id)
            job = store.get_job(job_id)
            store.update_job(
                job_id,
                status="FAILED",
                stage=(job or {}).get("stage") or "FAILED",
                error=str(exc) or type(exc).__name__,
            )
            self.project_store.update_project(project_id, status="FAILED")
        finally:
            if job_dir is not None:
                # 내려받은 업로드 사본과 중간 본편은 지운다 (최종 파일은 남긴다)
                shutil.rmtree(job_dir / "uploads", ignore_errors=True)
                (job_dir / "final_body.mp4").unlink(missing_ok=True)
