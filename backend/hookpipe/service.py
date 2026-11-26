"""코어 라우터(`backend/app/projects_router.py`)가 부르는 진입점.

- process_hook: POST /hooks 의 백그라운드 작업. 훅 하나를 만들어 OUTPUT_DIR/{project_id}/{hook_id}/ 에 둔다.
- process_render: POST /renders 의 백그라운드 작업. 훅(있으면 재사용) 뒤에 올린 본편을 붙여 최종 영상을 만든다.
DB 갱신과 파일 올리기는 코어의 저장소 객체(project_store, job_store, storage)를 그대로 쓴다.
"""

from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .body import attach_body
from .media import MediaTools, find_tools
from .render import HookRenderResult, extract_reference_frames, render_hook, write_scenario_and_srt

logger = logging.getLogger("hookpipe.service")

ProviderFactory = Callable[[Any], Any]

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
    ) -> None:
        self.settings = settings
        self.project_store = project_store
        self.job_store = job_store
        self.storage = storage
        self._provider_factory = provider_factory
        self._tools = tools

    # ---- 공통 도우미 -------------------------------------------------

    def _provider(self) -> Any:
        if self._provider_factory is not None:
            return self._provider_factory(self.settings)
        from app.genai_provider import GenAIMediaProvider  # 늦게 불러와 순환 import 를 피한다

        return GenAIMediaProvider(self.settings)

    def _media(self) -> MediaTools:
        if self._tools is None:
            self._tools = find_tools(
                getattr(self.settings, "ffmpeg_bin", None), getattr(self.settings, "ffprobe_bin", None)
            )
        return self._tools

    def hook_dir(self, project_id: str, hook_id: str) -> Path:
        return Path(self.settings.output_dir).resolve() / project_id / hook_id

    def _upload_clip_paths(self, project: Dict[str, Any], work_dir: Path) -> List[Path]:
        """올린 본편 클립을 촬영 순서(shot_no)대로 로컬 경로로 돌려준다. 저장소에만 있으면 내려받는다."""
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
                if not dest.is_file():
                    self.storage.download_file(key, dest)
            except Exception as exc:
                logger.warning("업로드 클립을 내려받지 못했습니다 (%s): %s", key, exc)
                continue
            if dest.is_file():
                paths.append(dest)
        return paths

    def _render(
        self,
        project: Dict[str, Any],
        scenario: Dict[str, Any],
        out_dir: Path,
        tts: Dict[str, Any],
        progress: Optional[Callable[[str], None]] = None,
    ) -> HookRenderResult:
        media = self._media()
        clips = self._upload_clip_paths(project, out_dir / "_work" / "uploads")
        refs = extract_reference_frames(clips, out_dir / "_work" / "refs", media) if clips else []
        return render_hook(
            scenario,
            project.get("product") or {},
            out_dir,
            provider=self._provider(),
            settings=self.settings,
            tts_enabled=bool(tts.get("enabled", True)),
            voice=tts.get("voice") or None,
            product_refs=refs,
            tools=media,
            progress=progress,
        )

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
            if getattr(self.settings, "hook_render_mode", "video_model") == "dry_run":
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
                files.update(self._render(project, scenario, out_dir, tts or {}).files)
            self.project_store.update_hook(hook_id, status="done", files=files)
            self.project_store.update_project(project_id, status="HOOK_READY")
        except Exception as exc:
            logger.exception("훅 생성 실패 (%s/%s)", project_id, hook_id)
            self.project_store.update_hook(hook_id, status="failed", error=str(exc))
            self.project_store.update_project(project_id, status="FAILED")

    # ---- POST /renders -----------------------------------------------

    def _reusable_hook(self, project_id: str, scenario_id: str) -> Optional[Dict[str, Any]]:
        for hook in self.project_store.list_hooks_for_project(project_id):
            if hook.get("scenario_id") != scenario_id or hook.get("status") != "done":
                continue
            if (hook.get("files") or {}).get("hook_video") and (Path(hook["output_dir"]) / "hook.mp4").is_file():
                return hook
        return None

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
        try:
            project = self.project_store.get_project(project_id)
            if not project:
                raise RuntimeError("프로젝트를 찾을 수 없습니다.")
            store.update_job(job_id, status="RUNNING", stage="HOOK")

            hook = self._reusable_hook(project_id, str(scenario["scenario_id"]))
            if hook:
                hook_id, out_dir = hook["hook_id"], Path(hook["output_dir"])
            else:
                hook_id = f"hook_{uuid.uuid4().hex[:10]}"
                out_dir = self.hook_dir(project_id, hook_id)
                tts = {"enabled": True, "voice": voice}
                self.project_store.create_hook(
                    hook_id=hook_id,
                    project_id=project_id,
                    user_id=user_id,
                    scenario_id=str(scenario["scenario_id"]),
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
                        progress=lambda stage: store.update_job(job_id, stage=f"HOOK:{stage}"),
                    )
                except Exception as exc:
                    self.project_store.update_hook(hook_id, status="failed", error=str(exc))
                    raise
                self.project_store.update_hook(hook_id, status="done", files={**EMPTY_FILES, **result.files})

            store.update_job(job_id, status="RUNNING", stage="BODY")
            media = self._media()
            clips = self._upload_clip_paths(project, out_dir / "_work" / "uploads")
            if not clips:
                raise RuntimeError("붙일 본편 영상을 찾지 못했습니다. 영상을 다시 올려 주세요.")
            guide = project.get("filming_guide") or {}
            target_sec = float(guide.get("target_body_duration_sec") or 0.0)
            limit = min(float(self.settings.body_max_sec), target_sec) if target_sec > 0 else float(self.settings.body_max_sec)
            final_path = out_dir / "final.mp4"
            joined = attach_body(
                out_dir / "hook.mp4", clips, final_path, tools=media, limit_sec=limit, hook_srt=out_dir / "hook.srt"
            )

            prefix = f"projects/{project_id}/renders/{job_id}"
            entry: Dict[str, Any] = {
                "id": hook_id,
                "duration": joined.duration_sec,
                "hook_duration": joined.hook_sec,
                "body_duration": joined.body_sec,
                "lufs": {"final_lufs": joined.lufs},
                "master_mp4": self.storage.upload_file(final_path, f"{prefix}/final.mp4"),
            }
            entry["clean_mp4"] = entry["master_mp4"]
            srt_path = final_path.with_suffix(".srt")
            if srt_path.is_file():
                entry["srt"] = self.storage.upload_file(srt_path, f"{prefix}/final.srt")
            store.update_job(
                job_id,
                status="QC_READY",
                stage="QC_READY",
                artifacts={
                    "pipeline": "hookpipe",
                    "hook_id": hook_id,
                    "rendered": [entry],
                    "thumbnails": [],
                    "warnings": joined.warnings,
                },
            )
            self.project_store.update_project(project_id, status="DELIVERABLE_READY")
        except Exception as exc:
            logger.exception("최종 영상 생성 실패 (%s/%s)", project_id, job_id)
            job = store.get_job(job_id)
            store.update_job(job_id, status="FAILED", stage=(job or {}).get("stage") or "FAILED", error=str(exc))
            self.project_store.update_project(project_id, status="FAILED")
