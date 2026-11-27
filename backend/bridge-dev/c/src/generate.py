"""FR-003 시나리오 생성. 백엔드(backend/hookpipe)는 generate_scenarios(input) 를 import 해서 부른다."""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Callable

from .check import check_scenario
from .prompt import SYSTEM, build_user_prompt
from .schema import SCENARIO_SCHEMA, fact_ids, parse_worker_input, to_scenario_item

DEFAULT_MODEL = "claude-opus-5-5"
# 표준 단가(USD / 1M 토큰). 캐시 할인은 반영하지 않은 추정치다.
PRICES = {"claude-opus-5-5": (4.0, 20.0), "claude-sonnet-5-5": (2.0, 10.0), "claude-haiku-5-5": (0.1, 0.5)}


def _scenario_id(project_id: str, round_no: int, index: int) -> str:
    tail = "".join(ch for ch in project_id if ch.isalnum())[-6:] or "proj"
    return f"sc_{tail}_C{round_no}_{index + 1:02d}"


def offline_drafts(inp: dict) -> list[dict]:
    """API 없이 만드는 초안. 문구 품질이 아니라 흐름 확인용이며, 사실 문장을 그대로 읽는다."""
    facts = list(fact_ids(inp["product_info"]).items())
    proof = facts[0]
    benefit = facts[1] if len(facts) > 1 else facts[0]
    short = lambda text: text if len(text) <= 22 else text[:21] + "…"
    drafts = []
    for i in range(inp["count"]):
        drafts.append({
            "hook_title": f"(오프라인 초안 {i + 1}) {short(proof[1])}",
            "selling_point": inp["selling_points"][i % len(inp["selling_points"])]["point"] if inp["selling_points"] else "",
            "replacement_test_note": f"문제 해결 근거가 이 제품의 검증된 사실({proof[0]})이라 다른 제품에 옮겨 붙일 수 없다.",
            "pov_label": "또 같은 일이 생긴 나",
            "claim_ids": sorted({proof[0], benefit[0]}),
            "cta_text": "여러분은 어떻게 쓰고 계세요?",
            "beats": [
                {"order": 1, "role": "문제", "duration_sec": 4.0, "visual": "밝은 실내 POV 문제 상황",
                 "narration": "이거, 또 이렇게 됐어요.", "caption": "또 이렇게 됐어요"},
                {"order": 2, "role": "가장 강한 증명", "duration_sec": 6.0, "visual": f"실물 제품 클로즈업 [{proof[0]}]",
                 "narration": "이렇게 쓰면 바로 해결돼요.", "caption": short(proof[1])},
                {"order": 3, "role": "장점", "duration_sec": 6.0, "visual": f"실물 제품 사용 장면 [{benefit[0]}]",
                 "narration": "쓰는 방법도 간단해요.", "caption": short(benefit[1])},
            ],
        })
    return drafts


def _active_oidc_token() -> str | None:
    """Vercel / Modal OIDC JWT 를 환경변수 또는 토큰 파일에서 읽는다."""
    for env_key in ("VERCEL_OIDC_TOKEN", "MODAL_IDENTITY_TOKEN"):
        val = os.environ.get(env_key, "").strip()
        if val:
            return val
    modal_file = os.environ.get("MODAL_IDENTITY_TOKEN_FILE", "").strip()
    if modal_file:
        try:
            file_tok = Path(modal_file).read_text(encoding="utf-8").strip()
            if file_tok:
                return file_tok
        except OSError:
            pass
    return None


def _build_vertex_client(http_options: Any) -> Any:
    """GOOGLE_GENAI_USE_VERTEXAI=true 일 때 Modal/Vercel WIF, Express API 키, 또는 ADC로 Client를 만든다."""
    from google import genai

    project = os.environ.get("GOOGLE_CLOUD_PROJECT", "").strip()
    location = os.environ.get("GOOGLE_CLOUD_LOCATION", "global").strip() or "global"
    provider = os.environ.get("GCP_WORKLOAD_IDENTITY_PROVIDER", "").strip()
    sa_email = os.environ.get("GCP_SERVICE_ACCOUNT_EMAIL", "").strip()
    vertex_api_key = os.environ.get("GOOGLE_VERTEX_API_KEY", "").strip()
    oidc_token = _active_oidc_token()

    if project and provider and sa_email and oidc_token:
        from google.auth import exceptions as google_auth_exceptions
        from google.auth import identity_pool

        class _OidcSupplier(identity_pool.SubjectTokenSupplier):
            def get_subject_token(self, context: Any, request: Any) -> str:
                tok = _active_oidc_token()
                if not tok:
                    raise google_auth_exceptions.RefreshError(
                        "OIDC token is not set for GCP WIF exchange."
                    )
                return tok

        audience = (
            provider
            if provider.startswith("//iam.googleapis.com/")
            else f"//iam.googleapis.com/{provider.lstrip('/')}"
        )
        creds = identity_pool.Credentials(
            audience=audience,
            subject_token_type="urn:ietf:params:oauth:token-type:jwt",
            token_url="https://sts.googleapis.com/v1/token",
            subject_token_supplier=_OidcSupplier(),
            service_account_impersonation_url=(
                "https://iamcredentials.googleapis.com/v1/projects/-/serviceAccounts/"
                f"{sa_email}:generateAccessToken"
            ),
            scopes=["https://www.googleapis.com/auth/cloud-platform"],
        )
        return genai.Client(
            vertexai=True,
            project=project,
            location=location,
            credentials=creds,
            http_options=http_options,
        )
    if vertex_api_key:
        return genai.Client(
            vertexai=True,
            api_key=vertex_api_key,
            http_options=http_options,
        )
    if not project:
        raise RuntimeError(
            "GOOGLE_CLOUD_PROJECT 또는 GOOGLE_VERTEX_API_KEY 가 필요합니다 (Vertex AI)."
        )
    return genai.Client(
        vertexai=True,
        project=project,
        location=location,
        http_options=http_options,
    )


def _call_gemini(
    inp: dict,
    model: str,
    violations: list[str] | None,
    api_key: str | None,
    client: Any = None,
) -> tuple[list[dict], dict]:
    """Claude 와 같은 프롬프트·출력 스키마로 Gemini 를 부른다 (google-genai 필요)."""
    from google import genai
    from google.genai import types

    started = time.time()
    # 변수에 담아 둔다: 한 줄로 쓰면 요청 도중 클라이언트가 닫힌다.
    # 503(사용량 폭주)·429·5xx 는 잠깐 쉬었다 다시 부르고, 응답 없는 요청은 3분에 끊는다.
    http_options = types.HttpOptions(timeout=180_000, retry_options=types.HttpRetryOptions(attempts=4))
    if client is None:
        use_vertex = os.environ.get("GOOGLE_GENAI_USE_VERTEXAI", "").strip().lower() in {"1", "true", "yes"}
        if use_vertex:
            client = _build_vertex_client(http_options)
        else:
            key = api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
            if not key:
                raise RuntimeError("GEMINI_API_KEY 가 없습니다 (Gemini 로 시나리오를 만들려면).")
            client = genai.Client(
                api_key=key,
                http_options=http_options,
            )
    response = client.models.generate_content(
        model=model,
        contents=build_user_prompt(inp, violations),
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM,
            response_mime_type="application/json",
            response_json_schema=SCENARIO_SCHEMA,
        ),
    )
    text = getattr(response, "text", None) or ""
    try:
        drafts = json.loads(text)["scenarios"]
    except (ValueError, KeyError, TypeError) as exc:
        raise RuntimeError(f"Gemini 응답을 시나리오 JSON 으로 읽지 못했습니다: {text[:200]!r}") from exc
    usage = getattr(response, "usage_metadata", None)
    step = {
        "step": "scenarios" if not violations else "scenarios(retry)",
        "model": model,
        "inputTokens": getattr(usage, "prompt_token_count", None),
        "outputTokens": getattr(usage, "candidates_token_count", None),
        "costUsd": None,
        "ms": int((time.time() - started) * 1000),
    }
    return drafts, step


def _call_claude(inp: dict, model: str, violations: list[str] | None) -> tuple[list[dict], dict]:
    import anthropic

    client = anthropic.Anthropic()
    started = time.time()
    try:
        # 안전 분류기가 요청을 거절했을 때 서버가 다른 모델로 이어 가도록 fallbacks 를 켠다.
        response = client.beta.messages.create(
            model=model,
            max_tokens=16000,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            system=SYSTEM,
            output_config={"effort": "high", "format": {"type": "json_schema", "schema": SCENARIO_SCHEMA}},
            messages=[{"role": "user", "content": build_user_prompt(inp, violations)}],
        )
    except anthropic.AuthenticationError as e:
        raise RuntimeError("Claude API 인증에 실패했습니다. ANTHROPIC_API_KEY 를 확인하세요.") from e
    except anthropic.RateLimitError as e:
        raise RuntimeError("Claude API 사용량 한도에 걸렸습니다. 잠시 후 다시 실행하세요.") from e
    except anthropic.APIStatusError as e:
        raise RuntimeError(f"Claude API 오류 {e.status_code}: {e.message}") from e
    except anthropic.APIConnectionError as e:
        raise RuntimeError("Claude API 에 연결하지 못했습니다. 네트워크를 확인하세요.") from e

    if response.stop_reason == "refusal":
        raise RuntimeError("모델이 이 요청을 거절했습니다 (stop_reason: refusal). 제품 정보와 문구를 확인하세요.")
    if response.stop_reason == "max_tokens":
        raise RuntimeError("응답이 max_tokens 에서 잘렸습니다. count 를 줄여 다시 실행하세요.")
    text = "".join(block.text for block in response.content if block.type == "text")
    drafts = json.loads(text)["scenarios"]
    price_in, price_out = PRICES.get(model, (None, None))
    usage = response.usage
    step = {
        "step": "scenarios" if not violations else "scenarios(retry)",
        "model": response.model,
        "inputTokens": usage.input_tokens,
        "outputTokens": usage.output_tokens,
        "costUsd": None if price_in is None else round((usage.input_tokens * price_in + usage.output_tokens * price_out) / 1e6, 4),
        "ms": int((time.time() - started) * 1000),
    }
    return drafts, step


def generate_scenarios(data: dict, *, offline: bool = False, max_attempts: int = 2, model: str | None = None,
                       gemini_api_key: str | None = None, gemini_client: Any = None,
                       log: Callable[[str], None] = lambda m: None) -> dict:
    """입력(01_worker-input) → { response: {project_id, status, round, scenarios[]}, checks[], steps[] }.

    model: 글 모델. 비우면 C_MODEL → claude-opus-5-5. "gemini-…" 면 Gemini 로 부른다 (같은 프롬프트·스키마).
    offline=True 면 모델을 부르지 않고 사실 문장으로 초안을 만든다 (과금 없음, 흐름 확인용).
    """
    inp = parse_worker_input(data)
    model = model or os.environ.get("C_MODEL", DEFAULT_MODEL)
    use_gemini = model.lower().startswith("gemini")
    steps: list[dict] = []
    violations: list[str] | None = None
    scenarios: list[dict] = []
    checks: list[dict] = []
    for attempt in range(1, max(1, max_attempts) + 1):
        if offline:
            drafts = offline_drafts(inp)
        else:
            log(f"{'Gemini' if use_gemini else 'Claude'} 호출 ({model}, 시도 {attempt})…")
            if use_gemini:
                drafts, step = _call_gemini(inp, model, violations, gemini_api_key, client=gemini_client)
            else:
                drafts, step = _call_claude(inp, model, violations)
            steps.append(step)
        scenarios = [to_scenario_item(d, scenario_id=_scenario_id(inp["project_id"], inp["round"], i), round_no=inp["round"])
                     for i, d in enumerate(drafts[: inp["count"]])]
        checks = [check_scenario(s, inp["product_info"]) for s in scenarios]
        violations = [f"{s['hook_title']}: {e}" for s, c in zip(scenarios, checks) for e in c["errors"]]
        if not violations or offline:
            break
        log(f"규칙 위반 {len(violations)}건 → 다시 생성")
    return {
        "response": {"project_id": inp["project_id"], "status": "SCENARIOS_READY", "round": inp["round"], "scenarios": scenarios},
        "checks": checks,
        "steps": steps,
        "product_name": inp["product_info"]["name"],
        "offline": offline,
    }
