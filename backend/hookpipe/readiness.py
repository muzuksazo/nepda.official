"""서버가 영상 한 편을 끝까지 만들 준비가 됐는지 (과금 없이) 확인한다. GET /health 의 hookpipe 항목.

deep=True 면 무료 호출 두 가지를 더 한다: 저장소에서 A 템플릿 목록 읽기, Gemini 모델 목록에서 설정된 모델 이름 찾기.
키 값은 절대 돌려주지 않고 "있음/없음"만 알린다.
"""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict, List

from .media import MediaError, find_tools

NEEDED_FILTERS = ("subtitles", "loudnorm", "tpad", "concat", "amix", "atempo", "boxblur", "overlay")
DEFAULT_SESSION_SECRET = "dev-insecure-change-me"


def _has_key(settings: Any, attr: str, env: str) -> bool:
    return bool(str(getattr(settings, attr, "") or os.environ.get(env, "")).strip())


def check(settings: Any, storage: Any = None, *, deep: bool = False) -> Dict[str, Any]:
    problems: List[str] = []
    warnings: List[str] = []
    out: Dict[str, Any] = {}

    # ffmpeg
    try:
        tools = find_tools(getattr(settings, "ffmpeg_bin", None), getattr(settings, "ffprobe_bin", None))
        missing = [f for f in NEEDED_FILTERS if not tools.has_filter(f)]
        out["ffmpeg"] = {"path": tools.ffmpeg, "ffprobe": bool(tools.ffprobe), "missing_filters": missing,
                         "libx264": tools.has_encoder("libx264")}
        if missing or not tools.has_encoder("libx264"):
            problems.append(f"ffmpeg 에 필요한 기능이 없습니다: {', '.join(missing) or 'libx264'}")
    except MediaError as exc:
        out["ffmpeg"] = None
        problems.append(str(exc))

    # 글꼴 (자막 굽기)
    fonts = [p for p in ("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc", "C:/Windows/Fonts/malgun.ttf") if Path(p).is_file()]
    out["korean_font"] = bool(fonts)
    if not fonts:
        warnings.append("한글 글꼴(Noto Sans CJK)을 찾지 못했습니다. 자막이 다른 글꼴로 나올 수 있습니다.")

    # 시나리오 작업자
    workers_dir = Path(getattr(settings, "hook_workers_dir", ""))
    node = shutil.which("node")
    workers = {
        "node": bool(node),
        "a": (workers_dir / "a" / "node_modules").is_dir(),
        "b": (workers_dir / "b" / "node_modules").is_dir(),
        "c": (workers_dir / "c" / "src" / "generate.py").is_file(),
    }
    out["workers"] = workers
    if getattr(settings, "hook_worker_mode", "auto") == "auto":
        down = [t.upper() for t in ("a", "b", "c") if not workers[t]] + ([] if node else ["A·B(node 없음)"])
        if down:
            warnings.append(f"작업자를 쓸 수 없는 유형이 있습니다: {', '.join(down)} (planner-api 로 넘어갑니다)")

    # 키 (값은 내보내지 않는다)
    llm = str(getattr(settings, "hook_worker_llm", "") or "")
    keys = {
        "gemini": _has_key(settings, "gemini_api_key", "GEMINI_API_KEY") or bool(getattr(settings, "google_genai_use_vertexai", False)),
        "anthropic": bool(os.environ.get("ANTHROPIC_API_KEY", "").strip()),
        "inworld": _has_key(settings, "inworld_api_key", "INWORLD_API_KEY"),
    }
    out["keys"] = keys
    if not keys["gemini"]:
        problems.append("GEMINI_API_KEY 가 없습니다 (영상·이미지 모델).")
    if getattr(settings, "tts_provider", "gemini") == "inworld" and not (keys["inworld"] and getattr(settings, "inworld_voice_id", None)):
        problems.append("TTS_PROVIDER=inworld 인데 INWORLD_API_KEY 또는 INWORLD_VOICE_ID 가 없습니다.")
    if not llm.startswith("gemini") and not keys["anthropic"]:
        warnings.append("HOOK_WORKER_LLM 이 Gemini 가 아니고 ANTHROPIC_API_KEY 도 없어 B·C 시나리오를 만들 수 없습니다.")
    if getattr(settings, "hook_a_mode", "template") == "realtime" and not keys["anthropic"]:
        warnings.append("A 실시간 생성은 Claude 전용인데 ANTHROPIC_API_KEY 가 없습니다.")

    # 보안 기본값
    if str(getattr(settings, "session_secret", "")) == DEFAULT_SESSION_SECRET:
        problems.append("SESSION_SECRET 이 공개된 기본값입니다. 누구나 로그인 토큰을 만들 수 있습니다.")
    if not getattr(settings, "api_bearer_token", None):
        warnings.append("API_BEARER_TOKEN 이 없어 내부 작업 API(/v1/jobs, /v1/uploads/presign)가 인증 없이 열려 있습니다.")

    out["config"] = {
        "storage_backend": getattr(settings, "storage_backend", None),
        "video_model": getattr(settings, "video_model", None),
        "image_model": getattr(settings, "image_model", None),
        "tts_provider": getattr(settings, "tts_provider", None),
        "hook_worker_llm": llm or None,
        "hook_a_mode": getattr(settings, "hook_a_mode", None),
        "hook_a_templates": getattr(settings, "hook_a_templates", None),
        "hook_render_mode": getattr(settings, "hook_render_mode", None),
    }
    if getattr(settings, "storage_backend", "local") == "local":
        warnings.append("STORAGE_BACKEND=local: 결과 주소가 file:// 라 브라우저에서 열 수 없고, 재배포하면 파일이 사라집니다.")

    if deep:
        out["deep"] = _deep(settings, storage, problems, warnings)

    out["ready"] = not problems
    out["problems"] = problems
    out["warnings"] = warnings
    return out


def _deep(settings: Any, storage: Any, problems: List[str], warnings: List[str]) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    # A 템플릿 목록 (저장소 읽기 권한 확인을 겸한다)
    if storage is not None and getattr(settings, "hook_a_mode", "template") == "template":
        from .a_templates import TemplateError, load_catalog

        try:
            with tempfile.TemporaryDirectory() as tmp:
                catalog = load_catalog(settings, storage, Path(tmp))
            result["a_templates"] = len(catalog["templates"])
        except TemplateError as exc:
            result["a_templates"] = 0
            warnings.append(f"A 템플릿을 쓸 수 없어 A 는 실시간 생성으로 갑니다: {exc}")
    # 모델 이름 (models.list / Vertex models.get 는 무료 메타데이터 조회)
    try:
        from app.genai_provider import build_genai_client

        client = build_genai_client(settings)
        wanted: Dict[str, str] = {}
        for attr in ("video_model", "image_model", "body_llm", "hook_worker_llm"):
            val = str(getattr(settings, attr, "") or "").strip()
            if val.startswith("gemini"):
                wanted[attr] = val
        if getattr(settings, "tts_provider", "gemini") == "gemini":
            tts_val = str(getattr(settings, "tts_model", "") or "").strip()
            if tts_val:
                wanted["tts_model"] = tts_val

        if getattr(settings, "google_genai_use_vertexai", False):
            # Vertex AI 에서는 client.models.list() 가 커스텀 모델만 반환하므로 publisher 모델을 get 으로 확인한다.
            missing_models: set[str] = set()
            checked: set[str] = set()
            for model_name in wanted.values():
                if model_name in checked:
                    continue
                checked.add(model_name)
                try:
                    client.models.get(model=model_name)
                except Exception as exc:
                    msg = str(exc)
                    if getattr(exc, "code", None) == 404 or "404" in msg or "NOT_FOUND" in msg:
                        missing_models.add(model_name)
                    else:
                        raise
            missing = {k: v for k, v in wanted.items() if v in missing_models}
        else:
            names = {m.name.replace("models/", "") for m in client.models.list()}
            missing = {k: v for k, v in wanted.items() if v and v not in names}

        result["models_missing"] = missing
        for k, v in missing.items():
            problems.append(f"{k}={v} 를 이 키의 모델 목록에서 찾지 못했습니다.")
    except Exception as exc:
        result["models_missing"] = None
        problems.append(f"Gemini 모델 목록을 읽지 못했습니다: {type(exc).__name__}")
    return result
