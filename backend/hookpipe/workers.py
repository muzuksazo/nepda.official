"""A·B·C 시나리오 작업자 연결 (WORKER_CONTRACT.md 의 `WORKERS["A"|"B"|"C"]`).

작업자 코드는 `backend/bridge-dev/{a,b,c}` 에 그대로 두고, 여기서는 부르기만 한다.
- A, B: TypeScript → Node 명령으로 실행하고 결과 JSON 을 읽는다.
- C: Python → 같은 프로세스에서 함수로 부른다.
작업자가 실패하면(노드·키 없음, 규칙 오류 등) 넘겨받은 대체 생성기(planner-api)로 넘어간다.
"""

from __future__ import annotations

import importlib
import importlib.util
import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import uuid
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Dict, List, Optional, Tuple

from fastapi import HTTPException

logger = logging.getLogger("hookpipe.workers")

TRACK_BY_TYPE = {
    "A": "A_bgrade_reversal",
    "B": "B_info_hook_offset",
    "C": "C_direct_proof",
}

ScenarioGenerator = Callable[[Dict[str, Any], List[str], str], List[Dict[str, Any]]]
WorkerFn = Callable[[Dict[str, Any], Any], Dict[str, Any]]

_C_IMPORT_LOCK = threading.Lock()
_C_PACKAGE = "hookpipe_c_worker"
# c/.env 에서 서버 프로세스로 가져오는 값. 저장소·구글 설정처럼 서버 설정과 이름이 겹치는 값은 가져오지 않는다.
_C_ENV_KEYS = ("ANTHROPIC_API_KEY", "C_MODEL")
_C_INJECTED: set = set()  # c/.env 에서 가져와 서버 환경에 넣은 키 이름 (Node 작업자에게는 넘기지 않는다)


class WorkerError(RuntimeError):
    """작업자를 부르지 못했거나 쓸 수 있는 시나리오가 나오지 않았을 때."""


def build_worker_input(
    project: Dict[str, Any],
    hook_type: str,
    *,
    round_no: int,
    previous_scenarios: List[Dict[str, Any]],
    count: int = 1,
) -> Dict[str, Any]:
    """코어의 프로젝트 → 작업자 입력(`01_worker-input.scenarios.json` 형태). 빈 값은 넣지 않는다."""
    product = project.get("product") or {}
    info: Dict[str, Any] = {"name": product.get("name") or ""}
    for key in ("call_name", "model", "category", "price_or_offer", "target_audience"):
        value = product.get(key)
        if isinstance(value, str) and value.strip():
            info[key] = value.strip()
    info["verified_facts"] = [str(f).strip() for f in (product.get("verified_facts") or []) if str(f).strip()]
    return {
        "hook_type": hook_type,
        "project_id": str(project["project_id"]),
        "round": max(1, int(round_no)),
        "count": max(1, min(5, int(count))),
        "product_info": info,
        "previous_scenarios": [s for s in previous_scenarios if s.get("type") == hook_type],
    }


def _tail(text: str, lines: int = 8) -> str:
    return "\n".join((text or "").strip().splitlines()[-lines:])


def _node_command(worker_dir: Path) -> List[str]:
    node = shutil.which("node")
    if not node:
        raise WorkerError("node 를 찾지 못했습니다 (A·B 작업자는 Node 22 이상이 필요합니다).")
    if not (worker_dir / "node_modules").is_dir():
        raise WorkerError(
            f"bridge-dev/{worker_dir.name} 에 node_modules 가 없습니다. 그 폴더에서 npm ci 를 먼저 실행해 주세요."
        )
    return [node, "--env-file-if-exists=.env", "--import", "tsx", "src/cli.ts"]


def _node_env(extra: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    """Node 작업자에게 넘길 환경. C 용으로 넣은 키가 A·B 의 자기 .env 를 가리지 않게 뺀다."""
    env = dict(os.environ)
    for key in _C_INJECTED:
        env.pop(key, None)
    env.update(extra or {})
    return env


def _gemini_llm(settings: Any) -> Optional[str]:
    model = str(getattr(settings, "hook_worker_llm", "") or "").strip()
    return model if model.lower().startswith("gemini") else None


class _SettingsOverlay:
    """요청별 A/B 모델 오버라이드를 공유 Settings 객체 변이 없이 전달하기 위한 얇은 프록시."""

    def __init__(self, base: Any, **overrides: Any) -> None:
        self._base = base
        self._overrides = overrides

    def __getattr__(self, name: str) -> Any:
        if name in self._overrides:
            return self._overrides[name]
        return getattr(self._base, name)


def _settings_with_llm(
    settings: Any,
    *,
    provider: str,
    model: Optional[str],
    explicit: bool,
    on_usage: Optional[Callable[..., None]] = None,
) -> Any:
    return _SettingsOverlay(
        settings,
        _resolved_llm_provider=provider,
        _resolved_llm_model=model,
        _resolved_llm_explicit=explicit,
        _on_usage=on_usage,
    )


def resolve_worker_llm(
    settings: Any,
    *,
    provider: Optional[str] = None,
    model_override: Optional[str] = None,
    explicit: bool = False,
) -> Tuple[str, Optional[str]]:
    """요청별 provider / 세부 model 을 작업자 실행용 (provider, model_id) 로 해석한다."""
    clean_model = str(model_override or "").strip() or None
    if clean_model:
        inferred = "google" if clean_model.lower().startswith("gemini") else "anthropic"
        return inferred, clean_model
    if explicit and provider == "google":
        fallback_gemini = (
            _gemini_llm(settings)
            or str(getattr(settings, "hook_worker_gemini_model", "") or "gemini-4-hydrogen").strip()
            or "gemini-4-hydrogen"
        )
        return "google", fallback_gemini
    if explicit and provider == "anthropic":
        claude_default = str(getattr(settings, "hook_worker_claude_model", "") or "").strip() or None
        return "anthropic", claude_default
    gemini = _gemini_llm(settings)
    if gemini:
        return "google", gemini
    return "anthropic", None


def _run_node(
    cmd: List[str],
    worker_dir: Path,
    timeout: float,
    label: str,
    extra_env: Optional[Dict[str, str]] = None,
) -> subprocess.CompletedProcess:
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(worker_dir),
            env=_node_env(extra_env),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise WorkerError(f"{label} 작업자가 {timeout:.0f}초 안에 끝나지 않았습니다.") from exc
    # 계약: 0 = 통과, 2 = 규칙 위반(결과는 저장됨), 1 = 실행 오류
    if proc.returncode not in (0, 2):
        logger.warning(
            "%s 작업자 실행 오류 (종료 코드 %s):\n%s", label, proc.returncode, _tail(proc.stderr or proc.stdout)
        )
        raise WorkerError(f"{label} 작업자 실행 오류 (종료 코드 {proc.returncode}). 자세한 내용은 서버 로그에 있습니다.")
    if proc.returncode == 2:
        both = (proc.stderr or "") + "\n" + (proc.stdout or "")
        logger.warning("%s 작업자가 규칙 위반을 보고했습니다:\n%s", label, _tail(both, 16))
    return proc


def _mark_violation(response: Any, proc: subprocess.CompletedProcess) -> Any:
    """종료 코드 2(규칙 위반)면 시나리오마다 표시를 남긴다. 어떤 규칙인지는 작업자 출력(서버 로그)에 있다."""
    if proc.returncode == 2 and isinstance(response, dict):
        for item in response.get("scenarios") or []:
            if isinstance(item, dict):
                item["rule_violations"] = ["작업자 규칙 검사에서 위반이 보고되었습니다."]
    return response


def _read_json(path: Path, label: str) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise WorkerError(f"{label} 작업자 결과 파일을 읽지 못했습니다: {path.name} ({exc})") from exc


def run_worker_a(worker_input: Dict[str, Any], settings: Any) -> Dict[str, Any]:
    import time

    worker_dir = Path(settings.hook_workers_dir) / "a"
    cmd = _node_command(worker_dir)
    resolved_provider = getattr(settings, "_resolved_llm_provider", None)
    resolved_model = getattr(settings, "_resolved_llm_model", None)
    extra_env = (
        {"A_MODEL": str(resolved_model)}
        if resolved_provider == "anthropic" and resolved_model
        else None
    )
    t0 = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="hookpipe_a_") as tmp:
        in_path = Path(tmp) / "worker_input.json"
        out_path = Path(tmp) / "scenarios_response.json"
        in_path.write_text(json.dumps(worker_input, ensure_ascii=False), encoding="utf-8")
        proc = _run_node(
            [*cmd, "generate", "--input", str(in_path), "--out", str(out_path)],
            worker_dir,
            float(settings.hook_worker_timeout_sec),
            "A",
            extra_env=extra_env,
        )
        data = _read_json(out_path, "A")
    elapsed_ms = int((time.monotonic() - t0) * 1000)
    on_usage = getattr(settings, "_on_usage", None)
    if callable(on_usage):
        scen_titles = [
            str(s.get("hook_title") or "")
            for s in ((data.get("scenarios") or []) if isinstance(data, dict) else [])
            if isinstance(s, dict) and s.get("hook_title")
        ][:3]
        worker_meta = {"hook_titles": scen_titles} if scen_titles else None
        steps = data.get("steps") if isinstance(data, dict) else None
        if isinstance(steps, list) and steps:
            for st in steps:
                if not isinstance(st, dict):
                    continue
                m_id = str(st.get("model") or resolved_model or "claude-opus-5-5").strip()
                if not m_id or m_id == "-":
                    continue
                on_usage(
                    stage="scenario_a",
                    step_name=str(st.get("step") or "generate"),
                    provider="google" if m_id.lower().startswith("gemini") else "anthropic",
                    model=m_id,
                    input_tokens=int(st.get("inputTokens") or 0),
                    output_tokens=int(st.get("outputTokens") or 0),
                    latency_ms=int(st.get("ms") or 0),
                    metadata=worker_meta,
                )
        else:
            on_usage(
                stage="scenario_a",
                step_name="realtime_pipeline",
                provider="anthropic",
                model=str(resolved_model or "claude-opus-5-5"),
                latency_ms=elapsed_ms,
                metadata=worker_meta,
            )
    return _mark_violation(data, proc)


def _worker_vertex_env(settings: Any, profile: Any = None) -> Dict[str, str]:
    """Settings(또는 지정된 VertexProfile)의 Vertex AI / WIF 설정을 Node 작업자 하위 프로세스에 넘긴다."""
    extra: Dict[str, str] = {}
    if profile is not None:
        extra["GOOGLE_GENAI_USE_VERTEXAI"] = "true"
        extra["GOOGLE_CLOUD_PROJECT"] = str(getattr(profile, "project", "") or "").strip()
        extra["GOOGLE_CLOUD_LOCATION"] = str(getattr(profile, "location", "global") or "global").strip() or "global"
        extra["GCP_WORKLOAD_IDENTITY_PROVIDER"] = str(getattr(profile, "wif_provider", "") or "").strip()
        extra["GCP_SERVICE_ACCOUNT_EMAIL"] = str(getattr(profile, "service_account_email", "") or "").strip()
        extra["GOOGLE_VERTEX_API_KEY"] = str(getattr(profile, "vertex_api_key", "") or "").strip()
        return extra
    if getattr(settings, "google_genai_use_vertexai", False) and not os.environ.get("GOOGLE_GENAI_USE_VERTEXAI"):
        extra["GOOGLE_GENAI_USE_VERTEXAI"] = "true"
    mappings = (
        ("google_cloud_project", "GOOGLE_CLOUD_PROJECT"),
        ("google_cloud_location", "GOOGLE_CLOUD_LOCATION"),
        ("gcp_workload_identity_provider", "GCP_WORKLOAD_IDENTITY_PROVIDER"),
        ("gcp_service_account_email", "GCP_SERVICE_ACCOUNT_EMAIL"),
        ("google_vertex_api_key", "GOOGLE_VERTEX_API_KEY"),
    )
    for attr, env_name in mappings:
        if os.environ.get(env_name, "").strip():
            continue
        val = str(getattr(settings, attr, "") or "").strip()
        if val:
            extra[env_name] = val
    return extra


def _run_worker_b_once(worker_input: Dict[str, Any], settings: Any, worker_dir: Path, cmd: List[str], record: Path, *, profile: Any = None) -> Tuple[Any, Dict[str, Any]]:
    with tempfile.TemporaryDirectory(prefix="hookpipe_b_") as tmp:
        in_path = Path(tmp) / "worker_input.json"
        in_path.write_text(json.dumps(worker_input, ensure_ascii=False), encoding="utf-8")
        gemini = _gemini_llm(settings)
        extra_env = _worker_vertex_env(settings, profile=profile)
        if getattr(settings, "_resolved_llm_explicit", False):
            resolved_model = getattr(settings, "_resolved_llm_model", None)
            extra_env["B_LLM"] = str(resolved_model or "")  # 명시적 anthropic 요청 시 기존 B_LLM 해제 포함
        elif gemini:
            extra_env["B_LLM"] = gemini  # B 의 모든 글 단계를 Gemini 로
        proc = _run_node(
            [*cmd, "generate", str(in_path), "--force"],
            worker_dir,
            float(settings.hook_worker_timeout_sec),
            "B",
            extra_env=extra_env or None,
        )
    data = _read_json(record, "B")
    return proc, data


def run_worker_b(worker_input: Dict[str, Any], settings: Any) -> Dict[str, Any]:
    """B 는 결과를 `b/out/<project_id>/round-<n>.json` 에 회차 기록으로 남긴다 (response 키가 계약 응답)."""
    worker_dir = Path(settings.hook_workers_dir) / "b"
    cmd = _node_command(worker_dir)
    record = worker_dir / "out" / str(worker_input["project_id"]) / f"round-{int(worker_input['round'])}.json"

    gemini = _gemini_llm(settings)
    explicit = bool(getattr(settings, "_resolved_llm_explicit", False))
    explicit_model = str(getattr(settings, "_resolved_llm_model", "") or "").strip()
    using_gemini = (explicit_model.lower().startswith("gemini") if explicit else bool(gemini))

    proc: Any = None
    data: Any = None
    if getattr(settings, "google_genai_use_vertexai", False) and using_gemini and getattr(settings, "gcp_vertex_profiles_json", None):
        from app.genai_provider import (
            get_vertex_profile_pool,
            is_vertex_failover_error,
            parse_vertex_profiles,
        )

        profiles = parse_vertex_profiles(settings)
        if len(profiles) > 1:
            pool = get_vertex_profile_pool()
            mode = str(getattr(settings, "gcp_vertex_routing_mode", "round_robin") or "round_robin")
            cooldown = float(getattr(settings, "gcp_vertex_cooldown_sec", 300.0) or 300.0)
            candidates = pool.ordered_candidates(profiles, mode)
            last_exc: Optional[Exception] = None
            for idx, candidate in enumerate(candidates):
                try:
                    proc, data = _run_worker_b_once(worker_input, settings, worker_dir, cmd, record, profile=candidate)
                    pool.mark_success(candidate)
                    last_exc = None
                    break
                except WorkerError as exc:
                    last_exc = exc
                    if is_vertex_failover_error(exc) and idx + 1 < len(candidates):
                        pool.mark_failure(candidate, exc, cooldown)
                        continue
                    raise
            if last_exc is not None:
                raise last_exc
    if data is None:
        proc, data = _run_worker_b_once(worker_input, settings, worker_dir, cmd, record)
    on_usage = getattr(settings, "_on_usage", None)
    if callable(on_usage) and isinstance(data, dict):
        b_resp = data.get("response") if isinstance(data.get("response"), dict) else {}
        b_titles = [
            str(s.get("hook_title") or "")
            for s in (b_resp.get("scenarios") or [])
            if isinstance(s, dict) and s.get("hook_title")
        ][:3]
        b_meta = {"hook_titles": b_titles} if b_titles else None
        for st in data.get("steps") or []:
            if not isinstance(st, dict):
                continue
            m_id = str(st.get("model") or getattr(settings, "_resolved_llm_model", None) or "claude-opus-5-5").strip()
            if not m_id or m_id == "-":
                continue
            on_usage(
                stage="scenario_b",
                step_name=str(st.get("step") or "step"),
                provider="google" if m_id.lower().startswith("gemini") else "anthropic",
                model=m_id,
                input_tokens=int(st.get("inputTokens") or 0),
                output_tokens=int(st.get("outputTokens") or 0),
                latency_ms=int(st.get("ms") or 0),
                metadata=b_meta,
            )
    response = data.get("response") if isinstance(data, dict) else None
    if not isinstance(response, dict):
        raise WorkerError("B 작업자 회차 기록에 response 가 없습니다.")
    return _mark_violation(response, proc)


def _load_c_env(worker_dir: Path) -> None:
    env_file = worker_dir / ".env"
    if not env_file.is_file():
        return
    try:
        text = env_file.read_text(encoding="utf-8-sig")  # 윈도우 편집기가 붙이는 BOM 허용
    except (OSError, UnicodeError) as exc:
        raise WorkerError(
            f"bridge-dev/c/.env 를 읽지 못했습니다 (UTF-8 로 저장해 주세요): {type(exc).__name__}"
        ) from exc
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if key in _C_ENV_KEYS and value and key not in os.environ:
            os.environ[key] = value
            _C_INJECTED.add(key)


def _import_c_generate(worker_dir: Path) -> Any:
    """`bridge-dev/c/src` 를 별칭 패키지로 불러온다 (폴더 이름에 하이픈이 있어 일반 import 가 안 된다)."""
    with _C_IMPORT_LOCK:
        if _C_PACKAGE not in sys.modules:
            init = worker_dir / "src" / "__init__.py"
            if not init.is_file():
                raise WorkerError(f"C 작업자 코드를 찾지 못했습니다: {init}")
            spec = importlib.util.spec_from_file_location(
                _C_PACKAGE, init, submodule_search_locations=[str(init.parent)]
            )
            if spec is None or spec.loader is None:
                raise WorkerError("C 작업자 패키지를 불러오지 못했습니다.")
            module = importlib.util.module_from_spec(spec)
            sys.modules[_C_PACKAGE] = module
            try:
                spec.loader.exec_module(module)
            except Exception:
                sys.modules.pop(_C_PACKAGE, None)
                raise
        return importlib.import_module(f"{_C_PACKAGE}.generate")


def run_worker_c(worker_input: Dict[str, Any], settings: Any) -> Dict[str, Any]:
    worker_dir = Path(settings.hook_workers_dir) / "c"
    try:
        generate = _import_c_generate(worker_dir)
    except WorkerError:
        raise
    except Exception as exc:
        raise WorkerError(f"C 작업자 코드를 불러오지 못했습니다: {exc}") from exc
    _load_c_env(worker_dir)
    if not worker_input["product_info"].get("verified_facts"):
        raise WorkerError("C 작업자는 검증된 제품 사실(verified_facts)이 1개 이상 필요합니다.")
    if getattr(settings, "_resolved_llm_explicit", False):
        use_gemini = getattr(settings, "_resolved_llm_provider", None) == "google"
        target_model = getattr(settings, "_resolved_llm_model", None)
    else:
        target_model = _gemini_llm(settings)
        use_gemini = bool(target_model)
    if not use_gemini and not os.environ.get("ANTHROPIC_API_KEY"):
        raise WorkerError("ANTHROPIC_API_KEY 가 없습니다 (C 작업자는 Claude 로 시나리오를 만듭니다).")
    gemini_client = None
    if use_gemini and getattr(settings, "google_genai_use_vertexai", False):
        from app.genai_provider import build_genai_client

        gemini_client = build_genai_client(settings)
    try:
        # 글 모델: 요청 오버라이드 또는 HOOK_WORKER_LLM 에 따라 Gemini / Claude 선택
        kwargs: Dict[str, Any] = {
            "model": target_model,
            "gemini_api_key": getattr(settings, "gemini_api_key", None) or None,
            "log": lambda m: logger.info("[C] %s", m),
        }
        if gemini_client is not None:
            kwargs["gemini_client"] = gemini_client
        run = generate.generate_scenarios(worker_input, **kwargs)
    except ModuleNotFoundError as exc:
        raise WorkerError(f"C 작업자에 필요한 패키지가 없습니다: {exc.name} (bridge-dev/c/requirements.txt)") from exc
    except Exception as exc:
        raise WorkerError(f"C 작업자 실행 오류: {exc}") from exc
    on_usage = getattr(settings, "_on_usage", None)
    if callable(on_usage) and isinstance(run, dict):
        c_resp = run.get("response") if isinstance(run.get("response"), dict) else {}
        c_titles = [
            str(s.get("hook_title") or "")
            for s in (c_resp.get("scenarios") or [])
            if isinstance(s, dict) and s.get("hook_title")
        ][:3]
        c_meta = {"hook_titles": c_titles} if c_titles else None
        for st in run.get("steps") or []:
            if not isinstance(st, dict):
                continue
            m_id = str(st.get("model") or target_model or "claude-opus-5-5").strip()
            if not m_id or m_id == "-":
                continue
            on_usage(
                stage="scenario_c",
                step_name=str(st.get("step") or "scenarios"),
                provider="google" if m_id.lower().startswith("gemini") else "anthropic",
                model=m_id,
                input_tokens=int(st.get("inputTokens") or 0),
                output_tokens=int(st.get("outputTokens") or 0),
                latency_ms=int(st.get("ms") or 0),
                metadata=c_meta,
            )
    response = run["response"]
    for item, check in zip(response.get("scenarios") or [], run.get("checks") or []):
        errors = [str(e) for e in (check.get("errors") or [])]
        if errors:
            logger.warning(
                "C 작업자가 규칙 위반을 보고했습니다 (%s): %s", item.get("scenario_id"), "; ".join(errors[:5])
            )
            item["rule_violations"] = errors
    return response


WORKERS: Dict[str, WorkerFn] = {"A": run_worker_a, "B": run_worker_b, "C": run_worker_c}


def normalize_scenarios(
    response: Dict[str, Any], hook_type: str, *, max_hook_sec: float
) -> List[Dict[str, Any]]:
    """작업자 응답 → 코어가 저장하는 시나리오 목록. 형태가 맞지 않거나 길이가 넘는 것은 뺀다."""
    items: List[Dict[str, Any]] = []
    for raw in (response or {}).get("scenarios") or []:
        if not isinstance(raw, dict):
            continue
        beats = [dict(b) for b in (raw.get("beats") or []) if isinstance(b, dict)]
        if not beats or not raw.get("scenario_id") or not raw.get("hook_title"):
            logger.warning("%s 작업자 시나리오에 필수 항목이 없어 뺍니다.", hook_type)
            continue
        try:
            orders = [int(b["order"]) for b in beats]
        except (KeyError, TypeError, ValueError):
            orders = []
        if len(orders) != len(beats) or min(orders) < 1 or len(set(orders)) != len(orders):
            logger.warning(
                "%s 작업자 시나리오 %s: 장면 번호(order)가 없거나 겹쳐 뺍니다.", hook_type, raw.get("scenario_id")
            )
            continue
        beats.sort(key=lambda b: int(b["order"]))
        total = round(sum(float(b.get("duration_sec") or 0.0) for b in beats), 3)
        if total <= 0 or total > float(max_hook_sec) + 0.05:
            logger.warning("%s 작업자 시나리오 %s: 훅 길이 %.1f초가 허용 범위(%.0f초 이하)를 벗어나 뺍니다.",
                           hook_type, raw.get("scenario_id"), total, max_hook_sec)
            continue
        for beat in beats:
            beat.setdefault("role", "beat")
            beat["visual"] = str(beat.get("visual") or "")
            beat["narration"] = str(beat.get("narration") or "")
            beat["caption"] = str(beat.get("caption") or "")
            beat["duration_sec"] = float(beat.get("duration_sec") or 0.0)
            beat["order"] = int(beat.get("order") or 0)
        item = dict(raw)
        violations = item.pop("rule_violations", None)
        # 작업자 ID 는 프로젝트·회차로만 정해져 겹친 요청끼리 같아질 수 있다. 서버가 짧은 꼬리를 붙여 고유하게 만든다.
        worker_id = str(raw["scenario_id"])
        item["scenario_id"] = f"{worker_id}_{uuid.uuid4().hex[:6]}"
        item["type"] = hook_type
        item["beats"] = beats
        item["hook_duration_sec"] = total
        item["body_duration_sec"] = float(raw.get("body_duration_sec") or 0.0)
        item["replacement_test_note"] = str(raw.get("replacement_test_note") or "")
        item["storyboard_frames"] = []
        spec = dict(raw.get("ad_spec") or {})
        spec.setdefault("track_archetype", TRACK_BY_TYPE[hook_type])
        spec["worker_scenario_id"] = worker_id
        if violations:
            spec["rule_violations"] = [str(v) for v in violations]
        item["ad_spec"] = spec
        items.append(item)
    return items


def generate_with_worker(
    hook_type: str,
    project: Dict[str, Any],
    settings: Any,
    *,
    round_no: int,
    previous_scenarios: List[Dict[str, Any]],
    workers: Optional[Dict[str, WorkerFn]] = None,
) -> List[Dict[str, Any]]:
    registry = workers if workers is not None else WORKERS
    worker = registry.get(hook_type)
    if worker is None:
        raise WorkerError(f"{hook_type} 유형 작업자가 등록되어 있지 않습니다.")
    worker_input = build_worker_input(
        project, hook_type, round_no=round_no, previous_scenarios=previous_scenarios
    )
    if not worker_input["product_info"]["name"]:
        raise WorkerError("제품 이름이 비어 있습니다.")
    response = worker(worker_input, settings)
    items = normalize_scenarios(response, hook_type, max_hook_sec=float(settings.hook_max_sec))
    if not items:
        raise WorkerError(f"{hook_type} 작업자가 쓸 수 있는 시나리오를 돌려주지 않았습니다.")
    return items


def template_or_realtime_a(storage: Any, realtime: WorkerFn, *, writer: Any = None) -> WorkerFn:
    """A 유형: 템플릿(앞부분 미리 만든 영상 + 착지 장면만 생성)을 먼저 쓰고, 안 되면 A 작업자로 전부 실시간 생성."""
    from .a_templates import TemplateError, make_template_scenario

    def _run(worker_input: Dict[str, Any], settings: Any) -> Dict[str, Any]:
        if getattr(settings, "_resolved_llm_explicit", False) and getattr(settings, "_resolved_llm_provider", None) == "anthropic":
            return realtime(worker_input, settings)
        if getattr(settings, "hook_a_mode", "template") == "template":
            work = Path(getattr(settings, "work_root", tempfile.gettempdir())) / "a_templates" / str(worker_input["project_id"])
            try:
                return make_template_scenario(
                    worker_input,
                    settings,
                    storage,
                    work,
                    writer=writer,
                    model_override=getattr(settings, "_resolved_llm_model", None),
                )
            except TemplateError as exc:
                logger.warning("A 템플릿을 쓰지 못해 실시간 생성으로 넘어갑니다: %s", exc)
            except Exception:
                logger.exception("A 템플릿 처리 중 예상하지 못한 오류 → 실시간 생성으로 넘어갑니다")
        return realtime(worker_input, settings)

    return _run


def make_scenario_generator(
    settings: Any,
    project_store: Any,
    *,
    fallback: Optional[ScenarioGenerator] = None,
    workers: Optional[Dict[str, WorkerFn]] = None,
    storage: Any = None,
    template_writer: Any = None,
) -> ScenarioGenerator:
    """코어 라우터에 끼우는 시나리오 생성기. 유형마다 작업자를 부르고, 실패하면 fallback 을 쓴다.

    storage 를 주면 A 는 템플릿(HOOK_A_TEMPLATES)을 먼저 쓴다.
    """
    if storage is not None:
        registry = dict(workers if workers is not None else WORKERS)
        if "A" in registry:
            registry["A"] = template_or_realtime_a(storage, registry["A"], writer=template_writer)
        workers = registry

    def _generate(project: Dict[str, Any], hook_types: List[str], provider: str) -> List[Dict[str, Any]]:
        project_id = str(project["project_id"])
        previous = [*project_store.list_scenarios(project_id), *(project.get("pending_scenarios") or [])]
        round_no = int(project.get("scenario_round") or 0) + 1
        ab_override = project.get("_ab_override") or {}
        explicit = bool(ab_override.get("explicit"))
        resolved_provider, resolved_model = resolve_worker_llm(
            settings,
            provider=ab_override.get("provider") or provider,
            model_override=ab_override.get("model"),
            explicit=explicit,
        )
        def _one(hook_type: str) -> Tuple[List[Dict[str, Any]], Optional[HTTPException]]:
            if getattr(settings, "hook_worker_mode", "auto") == "off":
                if fallback is None:
                    raise _unavailable(hook_type, "작업자 호출이 꺼져 있고(HOOK_WORKER_MODE=off) 대체 생성기도 없습니다.")
                return list(fallback(project, [hook_type], resolved_provider)), None

            def _record_usage(**kw: Any) -> None:
                from app.usage_telemetry import record_usage_safe

                record_usage_safe(
                    project_store,
                    settings,
                    project_id=project_id,
                    user_id=project.get("user_id"),
                    hook_type=hook_type,
                    **kw,
                )

            per_hook_settings = _settings_with_llm(
                settings,
                provider=resolved_provider,
                model=resolved_model,
                explicit=explicit,
                on_usage=_record_usage if hasattr(project_store, "record_api_usage") else None,
            )
            try:
                made = generate_with_worker(
                    hook_type,
                    project,
                    per_hook_settings,
                    round_no=round_no,
                    previous_scenarios=previous,
                    workers=workers,
                )
                for item in made:
                    spec = item.setdefault("ad_spec", {})
                    spec.setdefault("llm_provider", resolved_provider)
                    spec.setdefault("llm_model", resolved_model or "default")
                return made, None
            except WorkerError as exc:
                worker_error = str(exc)
                logger.warning("%s 작업자 실패 → 대체 생성기로 넘어갑니다: %s", hook_type, worker_error)
            except Exception as exc:  # 작업자 쪽의 예상 못 한 오류도 요청 전체를 죽이지 않고 대체 경로로 보낸다
                worker_error = f"예상하지 못한 오류 ({type(exc).__name__})"
                logger.exception("%s 작업자에서 예상하지 못한 오류 → 대체 생성기로 넘어갑니다", hook_type)
            if fallback is None:
                return [], _unavailable(hook_type, worker_error)
            try:
                return list(fallback(project, [hook_type], resolved_provider)), None
            except HTTPException as exc:
                detail = exc.detail if isinstance(exc.detail, dict) else {}
                planner_msg = (detail.get("error") or {}).get("message") or str(exc.detail)
                return [], _unavailable(hook_type, f"{worker_error} / 대체 생성기도 실패: {planner_msg}")

        # 유형마다 작업자가 따로 외부 모델을 기다리므로 동시에 돌린다 (B·C 각 1분이면 합쳐 2분 → 1분).
        # 결과는 요청한 유형 순서대로 모은다.
        types_in_order = list(hook_types)
        if len(types_in_order) > 1:
            with ThreadPoolExecutor(max_workers=len(types_in_order), thread_name_prefix="hook-worker") as pool:
                results = list(pool.map(_one, types_in_order))
        else:
            results = [_one(t) for t in types_in_order]
        out: List[Dict[str, Any]] = []
        failed: List[Any] = []
        for hook_type, (made, failure) in zip(types_in_order, results):
            out.extend(made)
            if failure is not None:
                failed.append((hook_type, failure))
        if failed and not out:
            raise failed[0][1]
        for hook_type, failure in failed:
            # 다른 유형은 이미 (과금해서) 만들었으므로 버리지 않고, 실패한 유형만 빼고 돌려준다
            logger.warning("%s 유형은 만들지 못해 빼고 돌려줍니다: %s", hook_type, failure.detail["error"]["message"])
        return out

    return _generate


def _unavailable(hook_type: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=502,
        detail={
            "error": {
                "code": "HOOK_WORKER_UNAVAILABLE",
                "message": f"{hook_type} 유형 시나리오를 만들지 못했습니다: {message}",
                "details": {"hook_type": hook_type},
            }
        },
    )
