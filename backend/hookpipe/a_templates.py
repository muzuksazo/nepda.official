"""A 유형 템플릿 오케스트레이터: Neon(기획+5축 비평) × Hydrogen(포맷/수정/실행) + 실물 본편 직접 컷.

템플릿 저장 위치 (설정 HOOK_A_TEMPLATES)
- "storage:templates/a"  서버 저장소(R2)의 그 경로. 배포 기본값.
- 그 밖의 값            로컬 폴더 경로 (개발·테스트용).
위치 아래에 catalog.json 하나와 장면 영상들이 있다.

기본 구조 (`hook_a_ai_landing=False`, 원본 A안 직접 컷):
- Beat 1 (`어긋난 시작`): 미리 만든 템플릿 MP4 (8~10초), `shows_product=False`,
  클립 길이의 85~95%를 채우는 한국어 나레이션 + 2~3개 타임드 자막(`caption_cues`).
- Beat 2 (`패턴 인터럽트`): `hold=True`, `0.3s` 정지 프레임 (`visual="정지"`, 무음/무자막).
- 이후 별도 AI 착지 클립 없이 곧바로 실제 업로드 촬영본(`body.mp4`)으로 컷하며,
  `ad_spec["twist_callback_line"]` 이 본편 첫 문장 반전 콜백으로 이어진다.

옵션 (`hook_a_ai_landing=True`):
- Beat 3 (`담백한 실물 착지`, 3.5~4.5초 단일 컷) 추가.
"""

from __future__ import annotations

import json
import logging
import re
import time
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Set, Tuple

logger = logging.getLogger("hookpipe.a_templates")

STORAGE_SCHEME = "storage:"
DIRECT_MIN_SEC, DIRECT_MAX_SEC = 8.0, 12.0
AI_LANDING_MIN_TOTAL_SEC, AI_LANDING_MAX_TOTAL_SEC = 13.0, 20.0
LANDING_MIN_SEC, LANDING_MAX_SEC = 3.5, 4.5
LEGACY_LANDING_MIN_SEC, LEGACY_LANDING_MAX_SEC = 3.0, 7.0
PAUSE_MIN_SEC, PAUSE_MAX_SEC = 0.18, 0.45
CAPTION_MAX_CHARS = 22
MAX_SYLLABLES_PER_SEC = 6.5
MIN_FRONT_SYLLABLES_PER_SEC = 3.5
MAX_CRITIC_REVISIONS = 2

RESKIN_CLICHES = ("속보입니다", "속보 입니다", "단 한 집만", "온 동네")
PAYOFF_CLICHES = ("딱 좋아요", "가성비 끝장", "가성비도 끝장", "강력 추천", "소개합니다", "꿀팁 공유")
UNVERIFIED_SUPERLATIVES = (
    "완벽 방수",
    "완전 방수",
    "100% 효과",
    "100% 보장",
    "기적의",
    "국내 최초",
    "세계 유일",
    "부작용 제로",
)
EMOJI_RE = re.compile(r"[\U0001F300-\U0001F6FF\U0001F900-\U0001FAFF\u2600-\u27BF]")
TOKEN_SPLIT_RE = re.compile(r"[\s()\[\]·,./!?:;\"'~\-]+")
KOREAN_PARTICLE_SUFFIXES = (
    "으로는",
    "에서는",
    "까지는",
    "부터는",
    "이라도",
    "으로",
    "에서",
    "까지",
    "부터",
    "처럼",
    "보다",
    "에게",
    "한테",
    "하고",
    "이랑",
    "이나",
    "라도",
    "은",
    "는",
    "이",
    "가",
    "을",
    "를",
    "의",
    "에",
    "로",
    "과",
    "와",
    "도",
    "만",
)

# ---------------------------------------------------------------------------
# JSON Schemas (Structured Outputs)
# ---------------------------------------------------------------------------

_LANDING_OBJ_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["duration_sec", "visual", "narration", "caption"],
    "properties": {
        "duration_sec": {"type": "number"},
        "visual": {"type": "string"},
        "narration": {"type": "string"},
        "caption": {"type": "string"},
    },
}

PLAN_SCHEMA_DIRECT: Dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "abstract_law",
        "template_id",
        "bridge_reason",
        "hook_title",
        "replacement_test_note",
        "product_taboo_keywords",
        "front_narration",
        "front_caption_cues",
        "twist_callback_line",
    ],
    "properties": {
        "abstract_law": {"type": "string"},
        "template_id": {"type": "string"},
        "bridge_reason": {"type": "string"},
        "hook_title": {"type": "string"},
        "replacement_test_note": {"type": "string"},
        "product_taboo_keywords": {"type": "array", "items": {"type": "string"}},
        "front_narration": {"type": "string"},
        "front_caption_cues": {"type": "array", "items": {"type": "string"}},
        "twist_callback_line": {"type": "string"},
    },
}

PLAN_SCHEMA_AI_LANDING: Dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [*PLAN_SCHEMA_DIRECT["required"], "landing"],
    "properties": {
        **PLAN_SCHEMA_DIRECT["properties"],
        "landing": _LANDING_OBJ_SCHEMA,
    },
}

# Backwards-compatible legacy schema alias
PICK_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "abstract_law",
        "template_id",
        "hook_title",
        "replacement_test_note",
        "product_taboo_keywords",
        "landing",
    ],
    "properties": {
        "abstract_law": {"type": "string"},
        "template_id": {"type": "string"},
        "hook_title": {"type": "string"},
        "replacement_test_note": {"type": "string"},
        "product_taboo_keywords": {"type": "array", "items": {"type": "string"}},
        "landing": _LANDING_OBJ_SCHEMA,
    },
}

CRITIC_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["passed", "scores", "defects", "fix_instructions"],
    "properties": {
        "passed": {"type": "boolean"},
        "scores": {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "bridge_logic",
                "tone_and_twist",
                "double_zero_spoiler",
                "visual_single_shot",
                "fact_grounding",
            ],
            "properties": {
                "bridge_logic": {"type": "integer"},
                "tone_and_twist": {"type": "integer"},
                "double_zero_spoiler": {"type": "integer"},
                "visual_single_shot": {"type": "integer"},
                "fact_grounding": {"type": "integer"},
            },
        },
        "defects": {"type": "array", "items": {"type": "string"}},
        "fix_instructions": {"type": "string"},
    },
}

# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

PLAN_SYSTEM = """당신은 바이럴 숏폼 광고 Track A(무맥락 다큐/밈 반전) 수석 기획자입니다.
앞부분은 제품과 무관한 3D 물리 실험/밈 템플릿(8~10초) + 0.3초 정지 인터럽트이고,
그 직후 실제 업로드 촬영본(본편)으로 컷하면서 재치 있는 반전 콜백 한 줄로 제품 실물을 공개합니다.

규칙:
1. abstract_law: 제품·브랜드·카테고리 단어가 0%인 순수 물리/심리 법칙 한 줄.
2. template_id: 목록 중 제품 핵심 기능과 시각적·물리적 연결이 가장 찰떡인 템플릿 ID를 정확히 하나 고릅니다.
   - 중요(금칙어 역설 금지): 제품명 속 일반 명사(예: '테이프', '우산', '컵')가 템플릿 고유 소재와 겹치더라도
     가장 잘 맞는 템플릿을 절대 포기하지 마세요! 대신 Beat 1 나레이션·자막에서만 그 겹치는 단어를
     자연스럽게 바꿔 쓰세요 (예: '테이프' → '접착띠' 또는 '한 겹씩', '우산' → '천막').
3. bridge_reason: 왜 이 템플릿의 물리/상황 법칙이 제품의 검증된 사실(verified_facts)과 자연스럽게 이어지는지 한 줄.
4. front_narration: Beat 1 템플릿 영상 전체(85~95% 길이)를 꽉 채워 읽는 생생한 한국어 다큐/밈 나레이션.
   - 10초 클립 기준 48~62음절(초당 4.5~6.2음절, 최대 6.5음절/초)로 2~3초 공백(dead air)이 생기지 않게 씁니다.
   - 브랜드명·정확한 제품명·제품 카테고리 스포일러 0%.
   - 겹치는 일반 명사(예: '테이프')는 '접착띠' / '한 겹씩' 등으로 바꿔 씁니다.
   - 리스킨 클리셰('속보입니다', '단 한 집만', '온 동네') 금지.
5. front_caption_cues: Beat 1 화면 흐름에 맞춰 전환되는 2~3개의 짧은 한국어 자막 배열.
   - 각 자막은 2줄 이내, 한 줄 22자 이내, 이모지 금지, 제품 스포일러 금지.
6. twist_callback_line: 0.3초 정지 직후 실제 제품 본편 첫 장면에 떨어지는 재치 있고 능청스러운 한국어 한 문장 반전 콜백.
   - 예: "죄송해요, 이거 하나 보여주려고 댐에 접착띠 백 겹 감았습니다." / "사실 물 새는 파이프, 백 겹이나 감을 필요 없어요."
   - 딱딱한 기업체("~습니다" 설명문)와 C안식 스펙 나열('딱 좋아요', '강력 추천', '가성비 끝장', '소개합니다', '꿀팁 공유') 금지.
   - verified_facts에 없는 과장('완벽 방수', '100% 효과', '기적의', '국내 최초' 등) 절대 금지.
7. hook_a_ai_landing=True로 landing 작성이 요청된 경우에만:
   - landing은 3.5~4.5초 단일 컷(한 장소, 한 동작, 분할화면·중간 컷 전환·화면 내 글자/숫자 금지)으로 씁니다."""

CRITIC_SYSTEM = """당신은 숏폼 광고 Track A(무맥락 반전) 전담 비평가(Critic Gate)입니다.
미디어 렌더링 비용이 나가기 전에 시나리오 초안을 5가지 축(각 1~5점)으로 냉정하게 감사하고 JSON으로 판정합니다.

5대 평가 축:
1. bridge_logic (템플릿-제품 브리지 논리):
   - 억지 연결이거나 더 잘 맞는 템플릿을 놓쳤으면 감점/불합격.
   - 예: 방수 테이프인데 댐 균열 템플릿(a_dam_tape_3d)을 놔두고 엉뚱한 도미노를 골랐다면 FAIL.
2. tone_and_twist (Track A 톤 & 반전 펀치):
   - 앞부분은 몰입감 있는 다큐/밈 리듬(공백 없이 85~95% 채움)이고, twist_callback_line은 능청스럽고 재치 있어야 함.
   - 딱딱한 보도/기업체("~습니다" 나열)나 C안식 스펙 나열('딱 좋아요', '강력 추천', '소개합니다')이면 FAIL.
3. double_zero_spoiler (반전 전 Double-Zero 스포일러 검사):
   - Beat 1 나레이션·자막에 브랜드명, 제품명, 제품 카테고리 스포일러가 새면 FAIL.
   - 템플릿 고유 소재와 제품 일반 명사(예: '테이프')가 겹칠 때는 템플릿을 버리지 말고 '접착띠'/'한 겹씩' 등으로 바꿔 쓰도록 지시.
4. visual_single_shot (시각 단일 컷 청결도):
   - 직접 컷 모드(AI landing 없음): Beat 1 나레이션/자막이 템플릿 실제 시각 내용과 정확히 일치하고 Beat 2가 0.3초 정지면 PASS.
   - AI landing 모드: landing.visual이 단일 장소·단일 동작의 한 컷이어야 함(분할화면, 두 장소 이어붙이기, 화면 텍스트/숫자 있으면 FAIL).
5. fact_grounding (검증 사실 근거):
   - twist_callback_line과 landing의 모든 제품 주장이 verified_facts에만 근거해야 함. 미검증 과장/할인/수치 날조 시 FAIL.

판정 기준:
- 모든 축이 4점 이상이고 치명적 결함(deterministic 위반 포함)이 없을 때만 passed=true.
- passed=false일 때는 defects에 구체적 결함을 적고, fix_instructions에 실행자(Hydrogen)가 즉시 고칠 수 있는 정확한 수정 지침을 작성합니다."""

REVISE_SYSTEM = """당신은 Track A 시나리오 정밀 수정·포맷 실행자(Executor)입니다.
비평가(Critic)의 수정 지시와 결정론적 린트 위반 사항을 빠짐없이 반영해 JSON을 보정합니다.

핵심 지침:
- Critic이 템플릿 교체를 명시하지 않았다면 기존 template_id를 유지합니다.
- 템플릿 고유 단어와 제품 일반 명사(예: '테이프')가 겹치면 템플릿을 바꾸지 말고,
  front_narration과 front_caption_cues에서만 자연스럽게 바꿔 쓰세요 (예: '테이프' → '접착띠' / '한 겹씩').
- front_narration은 클립 길이의 85~95%를 채우되 초당 6.5음절 이하로 맞춥니다(공백/dead air 방지).
- front_caption_cues는 2~3개의 타임드 한국어 자막(각 2줄 이내, 한 줄 22자 이내, 이모지 금지).
- twist_callback_line은 능청스럽고 재치 있는 한국어 한 문장(verified_facts 근거, C안식 클리셰·과장 금지).
- AI landing 모드에서는 landing.duration_sec를 3.5~4.5초로 맞추고 visual을 단일 컷으로 유지합니다."""

# Legacy single-shot prompt (preserved for backwards-compatible custom `writer` callers)
PICK_SYSTEM = """당신은 숏폼 광고 Track A(무맥락 반전) 작가입니다.
앞부분은 제품과 무관한 장면(이미 만들어 둔 템플릿)이고, 당신은 1) 제품에 맞는 템플릿을 고르고 2) 마지막 '실물 착지' 장면 하나를 씁니다.
규칙:
- abstract_law: 제품·카테고리·사용 공간 단어가 0% 인 순수 물리·심리 법칙 한 줄을 먼저 뽑습니다.
- template_id: 그 법칙과 가장 잘 이어지는 템플릿을 목록에서 정확히 하나 고릅니다 (목록의 id 그대로).
- landing: 앞부분의 법칙을 받아 실제 제품으로 담백하게 착지하는 장면 하나. 검증된 사실에 있는 내용만 말합니다.
  과장('완벽', '100%', '기적의', '최초'), 가격·할인, 'C안식 스펙 나열'('딱 좋아요', '강력 추천')은 쓰지 않습니다.
  narration 은 자연스러운 구어체 한두 문장, 장면 길이 1초당 6음절 안팎. caption 은 2줄 이내, 한 줄 22자 이내, 이모지 금지.
  visual 에는 화면에 보이는 것만 씁니다. 화면 안 글자·숫자는 넣지 않습니다.
- hook_title: 템플릿 제목을 그대로 쓰거나 다듬습니다.
- replacement_test_note: 왜 앞부분을 다른 제품에도 옮길 수 있는지 한 줄.
- product_taboo_keywords: 제품명·부품명·사용 공간 등 앞부분에 나오면 안 되는 단어."""

PickWriter = Callable[[str, str], Dict[str, Any]]


class TemplateError(RuntimeError):
    """템플릿을 쓸 수 없을 때 (목록 없음, 고르기 실패, 규칙/비평 위반). 호출하는 쪽은 실시간 생성으로 넘어간다."""


# ---------------------------------------------------------------------------
# Catalog loading & asset refs
# ---------------------------------------------------------------------------


def templates_location(settings: Any) -> str:
    value = str(getattr(settings, "hook_a_templates", "") or "").strip()
    return value or f"{STORAGE_SCHEME}templates/a"


def load_catalog(settings: Any, storage: Any, work_dir: Path) -> Dict[str, Any]:
    """catalog.json 을 읽는다. 없거나 비어 있으면 TemplateError."""
    location = templates_location(settings)
    if location.startswith(STORAGE_SCHEME):
        key = f"{location[len(STORAGE_SCHEME):].strip('/')}/catalog.json"
        dest = work_dir / "a_catalog.json"
        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            storage.download_file(key, dest)
        except Exception as exc:
            raise TemplateError(f"A 템플릿 목록을 저장소에서 읽지 못했습니다 ({key}): {type(exc).__name__}") from exc
        path = dest
    else:
        path = Path(location) / "catalog.json"
    try:
        catalog = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        raise TemplateError(f"A 템플릿 목록을 읽지 못했습니다: {exc}") from exc
    templates = [
        t for t in (catalog.get("templates") or []) if isinstance(t, dict) and t.get("template_id") and t.get("beats")
    ]
    if not templates:
        raise TemplateError("A 템플릿 목록이 비어 있습니다.")
    return {"location": location, "templates": templates}


def clip_ref(location: str, clip: str) -> str:
    """템플릿 장면 영상 → 장면의 prebuilt_clip 값 (저장소 키 또는 로컬 절대 경로)."""
    clip = clip.strip().lstrip("/")
    if location.startswith(STORAGE_SCHEME):
        return f"{location[len(STORAGE_SCHEME):].strip('/')}/{clip}"
    return str((Path(location) / clip).resolve())


# ---------------------------------------------------------------------------
# Model resolution & Gemini JSON callers with usage telemetry
# ---------------------------------------------------------------------------


def _is_explicit_override(settings: Any, model_override: Optional[str]) -> bool:
    override = str(model_override or "").strip()
    if not override:
        return False
    if getattr(settings, "_resolved_llm_explicit", False):
        return True
    # Direct callers (tests/tools) passing model_override without workers.py overlay
    resolved_from_overlay = getattr(settings, "_resolved_llm_model", None)
    if resolved_from_overlay is None or str(resolved_from_overlay).strip() != override:
        return True
    return False


def _resolve_planner_model(settings: Any, model_override: Optional[str] = None) -> str:
    if _is_explicit_override(settings, model_override):
        return str(model_override).strip()
    return str(getattr(settings, "hook_planner_llm", "") or "").strip() or "gemini-4-neon"


def _resolve_critic_model(settings: Any) -> str:
    return str(getattr(settings, "hook_critic_llm", "") or "").strip() or "gemini-4-neon"


def _resolve_executor_model(settings: Any, model_override: Optional[str] = None) -> str:
    if _is_explicit_override(settings, model_override):
        return str(model_override).strip()
    return (
        str(getattr(settings, "hook_worker_llm", "") or "").strip()
        or str(getattr(settings, "hook_worker_gemini_model", "") or "").strip()
        or str(getattr(settings, "body_llm", "") or "").strip()
        or "gemini-4-hydrogen"
    )


def _make_gemini_json_caller(
    settings: Any,
    *,
    model_id: str,
    step_name: str,
    schema: Dict[str, Any],
) -> PickWriter:
    def _call(system: str, prompt: str) -> Dict[str, Any]:
        from google.genai import types

        from app.genai_provider import build_genai_client

        client = build_genai_client(settings)  # 변수에 담아 둔다 (요청 도중 닫히지 않게)
        t0 = time.monotonic()
        response = client.models.generate_content(
            model=model_id,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=system,
                response_mime_type="application/json",
                response_json_schema=schema,
            ),
        )
        elapsed_ms = int((time.monotonic() - t0) * 1000)
        text = getattr(response, "text", None) or ""
        on_usage = getattr(settings, "_on_usage", None)
        if callable(on_usage):
            usage = getattr(response, "usage_metadata", None)
            on_usage(
                stage="a_template",
                step_name=step_name,
                provider="google",
                model=model_id,
                input_tokens=int(getattr(usage, "prompt_token_count", 0) or 0),
                output_tokens=int(getattr(usage, "candidates_token_count", 0) or 0),
                cached_tokens=int(getattr(usage, "cached_content_token_count", 0) or 0),
                thinking_tokens=int(getattr(usage, "thoughts_token_count", 0) or 0),
                latency_ms=elapsed_ms,
                metadata={"prompt_preview": prompt[:500], "response_preview": text[:800]},
            )
        try:
            parsed = json.loads(text)
        except ValueError as exc:
            raise TemplateError(f"A 템플릿 {step_name} 응답을 읽지 못했습니다: {text[:200]!r}") from exc
        if not isinstance(parsed, dict):
            raise TemplateError(f"A 템플릿 {step_name} 응답이 JSON 객체가 아닙니다: {text[:200]!r}")
        return parsed

    return _call


def gemini_pick_writer(settings: Any, *, model_override: Optional[str] = None) -> PickWriter:
    """Backwards-compatible single-shot JSON writer for legacy callers."""
    model_id = (
        str(model_override or "").strip()
        or str(getattr(settings, "hook_worker_llm", "") or "").strip()
        or str(getattr(settings, "body_llm", "") or "").strip()
        or "gemini-4-hydrogen"
    )
    return _make_gemini_json_caller(
        settings,
        model_id=model_id,
        step_name="pick_template",
        schema=PICK_SCHEMA,
    )


# ---------------------------------------------------------------------------
# Taboo-Filter Paradox Fix & Text/Syllable Helpers
# ---------------------------------------------------------------------------


def _strip_korean_particle(token: str) -> str:
    t = token.strip().lower()
    if len(t) <= 2:
        return t
    for suffix in KOREAN_PARTICLE_SUFFIXES:
        if t.endswith(suffix) and len(t) - len(suffix) >= 2:
            return t[: -len(suffix)]
    return t


def _tokenize_concept_text(text: str) -> Set[str]:
    tokens: Set[str] = set()
    for raw in TOKEN_SPLIT_RE.split(str(text or "").replace("**", "")):
        tok = raw.strip().lower()
        if len(tok) < 2:
            continue
        tokens.add(tok)
        stem = _strip_korean_particle(tok)
        if len(stem) >= 2:
            tokens.add(stem)
    return tokens


def _extract_template_inherent_words(template: Optional[Dict[str, Any]]) -> Set[str]:
    """템플릿 자체의 시각·스토리 개념에 본래 속한 일반 명사만 추출한다(제품 매칭용 tags 제외)."""
    if not isinstance(template, dict):
        return set()
    chunks: List[str] = [
        str(template.get("hook_title") or ""),
        str(template.get("abstract_law") or ""),
    ]
    for b in template.get("beats") or []:
        if not isinstance(b, dict):
            continue
        chunks.append(str(b.get("visual") or ""))
        chunks.append(str(b.get("narration") or ""))
        chunks.append(str(b.get("caption") or ""))
        raw_cues = b.get("caption_cues")
        if isinstance(raw_cues, list):
            chunks.extend(str(c or "") for c in raw_cues)
    return _tokenize_concept_text(" ".join(chunks))


def _split_taboo_keywords(
    product: Optional[Dict[str, Any]],
    raw_taboo: Sequence[str],
    template: Optional[Dict[str, Any]],
) -> Tuple[List[str], List[str]]:
    """금칙어를 (엄격 스포일러 금칙어, 템플릿 고유 개념과 겹치는 일반 명사)로 분리한다.

    - 브랜드명, 전체 제품명, 복수 단어 제품 표현(예: '방수 테이프'), 템플릿에 없는 제품/카테고리 단어는
      엄격 스포일러(strict_spoilers)로 분류되어 반전 전 누출 시 즉시 차단된다.
    - 템플릿 자체 개념에 원래 들어 있는 단일 일반 명사(예: a_dam_tape_3d 의 '테이프')는
      템플릿 실격 사유로 삼지 않고 overlapping_words 로 분리해 실행자(Hydrogen)가
      Beat 1 나레이션/자막에서 '접착띠' / '한 겹씩' 등으로 바꿔 쓰도록 유도한다.
    """
    inherent = _extract_template_inherent_words(template)
    product_name = str((product or {}).get("name") or "").strip()
    brand_name = str((product or {}).get("brand") or "").strip()
    brand_lower = brand_name.lower()
    product_lower = product_name.lower()

    candidates: List[str] = []
    seen_lower: Set[str] = set()

    def _add_candidate(word: str) -> None:
        w = str(word or "").strip()
        if len(w) < 2:
            return
        wl = w.lower()
        if wl not in seen_lower:
            seen_lower.add(wl)
            candidates.append(w)

    if brand_name:
        _add_candidate(brand_name)
    if product_name:
        _add_candidate(product_name)
    for w in raw_taboo:
        _add_candidate(str(w))

    # Also include 2-word adjacent phrases from product name as strict compound spoilers
    name_parts = [p.strip() for p in TOKEN_SPLIT_RE.split(product_name) if len(p.strip()) >= 2]
    for i in range(len(name_parts) - 1):
        _add_candidate(f"{name_parts[i]} {name_parts[i + 1]}")

    strict_spoilers: List[str] = []
    overlapping_words: List[str] = []

    for w in candidates:
        wl = w.lower()
        is_exact_brand = bool(brand_lower and wl == brand_lower)
        is_exact_product = bool(product_lower and wl == product_lower and len(name_parts) >= 2)
        is_multi_word = bool(re.search(r"\s", w))
        if is_exact_brand or is_exact_product or is_multi_word:
            strict_spoilers.append(w)
            continue
        stem = _strip_korean_particle(wl)
        if wl in inherent or stem in inherent:
            overlapping_words.append(w)
        else:
            strict_spoilers.append(w)

    return strict_spoilers, overlapping_words


def _front_text_for_scan(scenario: Dict[str, Any]) -> str:
    parts: List[str] = []
    for b in scenario.get("beats") or []:
        if not isinstance(b, dict):
            continue
        if b.get("shows_product") is True or str(b.get("role") or "") == "담백한 실물 착지":
            continue
        parts.append(str(b.get("narration") or ""))
        parts.append(str(b.get("caption") or ""))
        raw_cues = b.get("caption_cues")
        if isinstance(raw_cues, list):
            parts.extend(str(c or "") for c in raw_cues)
    return " ".join(parts)


def _overlapping_leaks_in_front(scenario: Dict[str, Any], overlapping_words: Sequence[str]) -> List[str]:
    if not overlapping_words:
        return []
    front_lower = _front_text_for_scan(scenario).lower()
    return [w for w in overlapping_words if w and len(w) >= 2 and w.lower() in front_lower]


def _hangul_syllable_count(text: str) -> int:
    return len(re.findall(r"[가-힣]", str(text or "")))


def _effective_syllable_count(text: str) -> int:
    """한국어 발화 음절 수 근사치 (한글 음절 + 숫자/단위 발화 음절)."""
    s = str(text or "")
    hangul = len(re.findall(r"[가-힣]", s))
    num_units = re.findall(r"\d+(?:[a-zA-Z%]+)?", s)
    extra = sum(min(5, max(1, len(tok))) for tok in num_units)
    return hangul + extra


def _clean_caption_lines(raw: str) -> str:
    cleaned = str(raw or "").replace("**", "").strip()
    lines = [ln.strip() for ln in cleaned.splitlines() if ln.strip()]
    return "\n".join(lines)


def _clean_caption_cues(raw_cues: Any) -> List[str]:
    if not isinstance(raw_cues, list):
        return []
    out: List[str] = []
    for item in raw_cues:
        c = _clean_caption_lines(str(item or ""))
        if c:
            out.append(c)
    return out


# ---------------------------------------------------------------------------
# Prompt Builders
# ---------------------------------------------------------------------------


def _format_template_catalog_lines(templates: List[Dict[str, Any]]) -> List[str]:
    lines: List[str] = []
    for t in templates:
        front = sum(float(b.get("duration_sec") or 0) for b in t["beats"])
        story = " / ".join(str(b.get("narration") or "").strip() for b in t["beats"] if b.get("narration"))
        cues: List[str] = []
        for b in t["beats"]:
            if isinstance(b.get("caption_cues"), list) and b["caption_cues"]:
                cues.extend(str(c).replace("\n", " ").strip() for c in b["caption_cues"] if str(c).strip())
            elif b.get("caption"):
                cues.append(str(b["caption"]).replace("\n", " ").strip())
        preview = story[:160] if story else " / ".join(cues)[:160]
        tags = [str(x).strip() for x in (t.get("tags") or []) if str(x).strip()][:8]
        tag_str = f" | 태그: {', '.join(tags)}" if tags else ""
        lines.append(
            f"- {t['template_id']} | 법칙: {t.get('abstract_law', '')} | 장르: {t.get('genre', '')} | "
            f"{front:.1f}초 | 제목: {t.get('hook_title', '')}{tag_str} | 내용: {preview}"
        )
    return lines


def _catalog_prompt(
    product: Dict[str, Any],
    templates: List[Dict[str, Any]],
    feedback: Optional[str],
    *,
    ai_landing: bool = True,
) -> str:
    facts = [str(f) for f in (product.get("verified_facts") or []) if str(f).strip()]
    lines = [
        f"제품: {product.get('name', '')}",
        "검증된 사실:",
        *[f"- [F{i:02d}] {f}" for i, f in enumerate(facts, 1)],
        "",
        "템플릿 목록 (앞부분, 제품 없음):",
        *_format_template_catalog_lines(templates),
        "",
    ]
    if ai_landing:
        lines.append(
            f"착지 장면 길이는 {LANDING_MIN_SEC:g}~{LANDING_MAX_SEC:g}초 단일 컷이고, "
            f"앞부분과 합쳐 {AI_LANDING_MIN_TOTAL_SEC:g}~{AI_LANDING_MAX_TOTAL_SEC:g}초가 되게 합니다."
        )
    else:
        lines.append(
            f"직접 컷 모드(AI 착지 클립 없음): 앞부분 템플릿 + 0.3초 정지({DIRECT_MIN_SEC:g}~{DIRECT_MAX_SEC:g}초) 뒤 "
            "실제 촬영본 본편으로 바로 컷합니다. Beat 1 나레이션(85~95% 길이, <=6.5음절/초), "
            "2~3개 타임드 자막(front_caption_cues), 재치 있는 반전 콜백(twist_callback_line)을 작성하세요."
        )
    if feedback:
        lines += ["", "직전 결과가 아래 규칙을 어겼습니다. 고쳐서 다시 써 주세요:", feedback]
    return "\n".join(lines)


def _plan_prompt(product: Dict[str, Any], templates: List[Dict[str, Any]], *, ai_landing: bool) -> str:
    facts = [str(f) for f in (product.get("verified_facts") or []) if str(f).strip()]
    lines = [
        f"제품명: {product.get('name', '')}",
    ]
    if product.get("brand"):
        lines.append(f"브랜드: {product.get('brand')}")
    if product.get("category"):
        lines.append(f"카테고리: {product.get('category')}")
    lines += [
        "검증된 사실 (verified_facts — 이 밖의 주장·수치·과장 금지):",
        *[f"- [F{i:02d}] {f}" for i, f in enumerate(facts, 1)],
        "",
        "사용 가능한 Track A 템플릿 목록:",
        *_format_template_catalog_lines(templates),
        "",
        "출력 모드:",
    ]
    if ai_landing:
        lines.append(
            f"- AI 착지 클립 포함 모드 (`hook_a_ai_landing=True`): Beat 1 나레이션/자막(2~3개) + "
            f"twist_callback_line + {LANDING_MIN_SEC:g}~{LANDING_MAX_SEC:g}초 단일 컷 landing을 작성하세요. "
            f"(총 훅 길이 {AI_LANDING_MIN_TOTAL_SEC:g}~{AI_LANDING_MAX_TOTAL_SEC:g}초)"
        )
    else:
        lines.append(
            f"- 실물 본편 직접 컷 모드 (`hook_a_ai_landing=False`): AI 착지 클립을 만들지 않습니다. "
            f"템플릿 Beat 1(85~95% 채운 나레이션 + 2~3개 타임드 front_caption_cues) + 0.3초 정지({DIRECT_MIN_SEC:g}~{DIRECT_MAX_SEC:g}초) 뒤 "
            "실제 촬영본 본편 첫 대사로 이어지는 재치 있는 twist_callback_line 한 문장을 작성하세요."
        )
    return "\n".join(lines)


def _critic_prompt(
    product: Dict[str, Any],
    template: Dict[str, Any],
    choices: List[Dict[str, Any]],
    scenario: Dict[str, Any],
    plan: Dict[str, Any],
    *,
    ai_landing: bool,
    det_errors: List[str],
    overlap_leaks: List[str],
) -> str:
    facts = [str(f) for f in (product.get("verified_facts") or []) if str(f).strip()]
    lines = [
        f"제품명: {product.get('name', '')}",
        "검증된 사실 (verified_facts):",
        *[f"- [F{i:02d}] {f}" for i, f in enumerate(facts, 1)],
        "",
        f"모드: {'AI 착지 클립 포함(3-beat)' if ai_landing else '실물 본편 직접 컷(2-beat, AI 착지 없음)'}",
        f"선택된 템플릿: {template.get('template_id')} — {template.get('hook_title')} (법칙: {template.get('abstract_law')})",
        "후보 템플릿 목록:",
        *_format_template_catalog_lines(choices),
        "",
        "초안 시나리오 요약:",
        json.dumps(
            {
                "template_id": plan.get("template_id"),
                "abstract_law": plan.get("abstract_law"),
                "bridge_reason": plan.get("bridge_reason"),
                "twist_callback_line": scenario.get("ad_spec", {}).get("twist_callback_line"),
                "hook_duration_sec": scenario.get("hook_duration_sec"),
                "beats": [
                    {
                        "order": b.get("order"),
                        "role": b.get("role"),
                        "duration_sec": b.get("duration_sec"),
                        "shows_product": b.get("shows_product"),
                        "hold": b.get("hold"),
                        "visual": b.get("visual"),
                        "narration": b.get("narration"),
                        "caption": b.get("caption"),
                        "caption_cues": b.get("caption_cues"),
                    }
                    for b in scenario.get("beats") or []
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
    ]
    if det_errors:
        lines += ["", "결정론적 린트 위반 (반드시 해결 필요):", *[f"- {e}" for e in det_errors]]
    if overlap_leaks:
        lines += [
            "",
            "템플릿 고유 단어와 제품 일반 명사 겹침 (템플릿은 유지하되 Beat 1 나레이션/자막에서 바꿔쓰기 필요):",
            f"- 겹치는 단어: {', '.join(overlap_leaks)} (예: 테이프 → 접착띠 / 한 겹씩)",
        ]
    return "\n".join(lines)


def _revise_prompt(
    product: Dict[str, Any],
    choices: List[Dict[str, Any]],
    current_plan: Dict[str, Any],
    template: Optional[Dict[str, Any]],
    *,
    det_errors: List[str],
    critic_verdict: Optional[Dict[str, Any]],
    overlap_leaks: List[str],
    ai_landing: bool,
) -> str:
    facts = [str(f) for f in (product.get("verified_facts") or []) if str(f).strip()]
    lines = [
        f"제품명: {product.get('name', '')}",
        "검증된 사실 (verified_facts):",
        *[f"- [F{i:02d}] {f}" for i, f in enumerate(facts, 1)],
        "",
        "사용 가능한 템플릿 목록:",
        *_format_template_catalog_lines(choices),
        "",
        "현재 초안 JSON:",
        json.dumps(current_plan, ensure_ascii=False, indent=2),
        "",
    ]
    if template is not None:
        front_dur = sum(float(b.get("duration_sec") or 0) for b in template["beats"] if b.get("clip"))
        if front_dur > 0:
            target_min = int(round(front_dur * 4.5))
            target_max = int(round(front_dur * 6.2))
            lines.append(
                f"선택 템플릿 Beat 1 길이: {front_dur:.2f}초 → front_narration 목표 길이: 약 {target_min}~{target_max}음절 "
                f"(85~95% 채움, 최대 {MAX_SYLLABLES_PER_SEC:g}음절/초)."
            )
    if det_errors:
        lines += ["", "결정론적 규칙 위반 (모두 수정 필수):", *[f"- {e}" for e in det_errors]]
    if overlap_leaks:
        lines += [
            "",
            "겹치는 템플릿 소재 단어 바꿔쓰기 지시 (템플릿 ID는 그대로 유지!):",
            f"- Beat 1 front_narration 및 front_caption_cues 에서 [{', '.join(overlap_leaks)}] 단어를 "
            "자연스럽게 바꿔 쓰세요 (예: '테이프' → '접착띠' 또는 '한 겹씩').",
        ]
    if critic_verdict:
        defects = [str(d) for d in (critic_verdict.get("defects") or []) if str(d).strip()]
        fix_inst = str(critic_verdict.get("fix_instructions") or "").strip()
        if defects:
            lines += ["", "비평가(Critic) 지적 결함:", *[f"- {d}" for d in defects]]
        if fix_inst:
            lines += ["", f"비평가(Critic) 수정 지시:\n{fix_inst}"]
    lines += [
        "",
        f"모드: {'AI 착지 클립 포함(landing 3.5~4.5초 단일 컷 필수)' if ai_landing else '실물 본편 직접 컷(landing 없음, twist_callback_line 필수)'}.",
        "위 모든 결함을 수정한 완전한 JSON을 반환하세요.",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Deterministic Validation (`_violations`)
# ---------------------------------------------------------------------------


def _infer_ai_landing(scenario: Dict[str, Any]) -> bool:
    ad_spec = scenario.get("ad_spec") or {}
    if isinstance(ad_spec.get("ai_landing"), bool):
        return bool(ad_spec["ai_landing"])
    beats = scenario.get("beats") or []
    if beats and isinstance(beats[-1], dict):
        last = beats[-1]
        if last.get("shows_product") is True or str(last.get("role") or "") == "담백한 실물 착지":
            return True
    return False


def _check_caption_format(text: str, label: str, errors: List[str]) -> None:
    if EMOJI_RE.search(text):
        errors.append(f"{label}: 이모지 사용 금지.")
    lines = text.split("\n")
    if len(lines) > 2:
        errors.append(f"{label}: 자막은 2줄 이내여야 합니다 (현재 {len(lines)}줄).")
    for ln in lines:
        plain = ln.replace("**", "").strip()
        if len(plain) > CAPTION_MAX_CHARS:
            errors.append(f"{label}: 자막 한 줄은 {CAPTION_MAX_CHARS}자 이내여야 합니다 ('{plain}').")


def _violations(
    scenario: Dict[str, Any],
    taboo: List[str],
    *,
    ai_landing: Optional[bool] = None,
    template: Optional[Dict[str, Any]] = None,
    product: Optional[Dict[str, Any]] = None,
    legacy_landing_bounds: bool = False,
) -> List[str]:
    """Track A 템플릿 시나리오의 결정론적 규칙·린트 위반 목록을 반환한다."""
    errors: List[str] = []
    use_ai_landing = _infer_ai_landing(scenario) if ai_landing is None else bool(ai_landing)
    beats = list(scenario.get("beats") or [])
    if not beats:
        return ["시나리오에 장면(beats)이 없습니다."]

    total = sum(float(b.get("duration_sec") or 0.0) for b in beats)
    facts_joined = " ".join(str(f) for f in ((product or {}).get("verified_facts") or []))

    # 1) Total duration & beat structure
    if use_ai_landing:
        if not (AI_LANDING_MIN_TOTAL_SEC - 1e-6 <= total <= AI_LANDING_MAX_TOTAL_SEC + 1e-6):
            errors.append(
                f"훅 길이는 {AI_LANDING_MIN_TOTAL_SEC:g}~{AI_LANDING_MAX_TOTAL_SEC:g}초여야 합니다 (현재 {total:.1f}초)."
            )
        if len(beats) < 3:
            errors.append(f"AI 착지 모드에서는 최소 3개 장면이 필요합니다 (현재 {len(beats)}개).")
        landing = beats[-1]
        lmin = LEGACY_LANDING_MIN_SEC if legacy_landing_bounds else LANDING_MIN_SEC
        lmax = LEGACY_LANDING_MAX_SEC if legacy_landing_bounds else LANDING_MAX_SEC
        if not (lmin - 1e-6 <= float(landing.get("duration_sec") or 0.0) <= lmax + 1e-6):
            errors.append(f"착지 장면은 {lmin:g}~{lmax:g}초여야 합니다.")
        if not str(landing.get("visual") or "").strip():
            errors.append("착지 장면의 visual 묘사가 비어 있습니다.")
        if not str(landing.get("narration") or "").strip():
            errors.append("착지 장면의 나레이션이 비어 있습니다.")
    else:
        if not (DIRECT_MIN_SEC - 1e-6 <= total <= DIRECT_MAX_SEC + 1e-6):
            errors.append(
                f"직접 컷 훅 길이는 {DIRECT_MIN_SEC:g}~{DIRECT_MAX_SEC:g}초여야 합니다 (현재 {total:.1f}초)."
            )
        if len(beats) < 2:
            errors.append(f"직접 컷 훅은 최소 2개 장면(템플릿 + 정지)이 필요합니다 (현재 {len(beats)}개).")
        if any(b.get("shows_product") is True or str(b.get("role") or "") == "담백한 실물 착지" for b in beats):
            errors.append("직접 컷 모드(hook_a_ai_landing=False)에는 AI 착지 장면(Beat 3)을 넣지 않습니다.")
        pause_beat = beats[-1]
        p_dur = float(pause_beat.get("duration_sec") or 0.0)
        if not (PAUSE_MIN_SEC - 1e-6 <= p_dur <= PAUSE_MAX_SEC + 1e-6) or not pause_beat.get("hold"):
            errors.append("마지막 장면은 0.3초 정지 인터럽트(hold=True)여야 합니다.")
        if str(pause_beat.get("narration") or "").strip() or str(pause_beat.get("caption") or "").strip():
            errors.append("정지 인터럽트(Beat 2)는 나레이션과 자막이 비어 있어야 합니다.")

    # 2) Per-beat caption, caption_cues, narration pacing & emoji checks
    for b in beats:
        order = b.get("order")
        dur = float(b.get("duration_sec") or 0.0)
        narr = str(b.get("narration") or "")
        cap = str(b.get("caption") or "")
        is_hold = bool(b.get("hold")) or (dur < 1.0 and not narr.strip() and not b.get("prebuilt_clip"))

        if EMOJI_RE.search(narr):
            errors.append(f"장면 {order}: 나레이션에 이모지 사용 금지.")
        if cap:
            _check_caption_format(cap, f"장면 {order}", errors)

        raw_cues = b.get("caption_cues")
        if isinstance(raw_cues, list) and raw_cues:
            for idx, cue in enumerate(raw_cues, 1):
                _check_caption_format(str(cue or ""), f"장면 {order} 자막 큐 {idx}", errors)
        elif (not use_ai_landing) and (not is_hold) and b.get("prebuilt_clip") and dur >= 6.0:
            errors.append(f"장면 {order}: 템플릿 클립({dur:.1f}초)에는 2~3개의 타임드 자막(caption_cues)이 필요합니다.")

        if (not use_ai_landing) and (not is_hold) and b.get("prebuilt_clip") and dur >= 6.0:
            if not isinstance(raw_cues, list) or not (2 <= len(raw_cues) <= 3):
                if isinstance(raw_cues, list) and raw_cues:
                    errors.append(f"장면 {order}: caption_cues 는 2~3개여야 합니다 (현재 {len(raw_cues)}개).")

        if dur > 0 and not is_hold:
            hangul_syl = _hangul_syllable_count(narr)
            if hangul_syl / dur > MAX_SYLLABLES_PER_SEC:
                errors.append(
                    f"장면 {order}: 나레이션이 장면 길이에 비해 깁니다 ({hangul_syl / dur:.1f}음절/초 > {MAX_SYLLABLES_PER_SEC:g})."
                )
            # Dead-air guard on long single prebuilt beat in direct-cut / orchestrated mode
            if (not use_ai_landing) and b.get("prebuilt_clip") and dur >= 6.0:
                eff_syl = _effective_syllable_count(narr)
                if eff_syl / dur < MIN_FRONT_SYLLABLES_PER_SEC:
                    errors.append(
                        f"장면 {order}: 나레이션이 너무 짧아 무음 공백(dead air)이 생깁니다 "
                        f"({eff_syl / dur:.1f}음절/초 < {MIN_FRONT_SYLLABLES_PER_SEC:g}). 템플릿 길이의 85~95%를 채우세요."
                    )

    # 3) Pre-twist cliché & Double-Zero spoiler check (Taboo-Filter Paradox fixed!)
    front_text = _front_text_for_scan(scenario)
    front_lower = front_text.lower()
    for cliche in RESKIN_CLICHES:
        if cliche.lower() in front_lower:
            errors.append(f"앞부분(반전 전)에 리스킨 뉴스 클리셰 '{cliche}' 사용 금지.")

    strict_spoilers, _overlapping = _split_taboo_keywords(product, taboo, template)
    leaked = [w for w in strict_spoilers if w and len(w) >= 2 and w.lower() in front_lower]
    if leaked:
        errors.append(f"앞부분(반전 전)에 제품 스포일러가 포함되었습니다: {', '.join(leaked[:3])}.")

    # 4) Payoff / twist_callback_line cliché & unverified superlative lints
    ad_spec = scenario.get("ad_spec") or {}
    callback_line = str(ad_spec.get("twist_callback_line") or "").strip()
    if (not use_ai_landing) and (not legacy_landing_bounds):
        if not callback_line:
            errors.append("직접 컷 모드에서는 본편 시작용 반전 콜백(twist_callback_line)이 필수입니다.")
        elif EMOJI_RE.search(callback_line):
            errors.append("twist_callback_line 에 이모지 사용 금지.")

    payoff_texts: List[Tuple[str, str]] = []
    if callback_line:
        payoff_texts.append(("twist_callback_line", callback_line))
    if use_ai_landing and beats:
        last = beats[-1]
        payoff_texts.append((f"착지 장면 {last.get('order')}", f"{last.get('narration', '')} {last.get('caption', '')}"))

    for label, text in payoff_texts:
        for cliche in PAYOFF_CLICHES:
            if cliche in text:
                errors.append(f"{label}에 C안식 스펙 나열 클리셰 '{cliche}' 사용 금지.")
        for sup in UNVERIFIED_SUPERLATIVES:
            if sup in text and sup not in facts_joined:
                errors.append(f"{label}에 검증되지 않은 과장 표현 '{sup}' 포함.")

    return errors


# ---------------------------------------------------------------------------
# Scenario Assembly
# ---------------------------------------------------------------------------


def _assemble(
    worker_input: Dict[str, Any],
    location: str,
    template: Dict[str, Any],
    picked: Dict[str, Any],
    *,
    ai_landing: bool = False,
) -> Dict[str, Any]:
    front = sorted(template["beats"], key=lambda b: int(b.get("order") or 0))
    prebuilt_indices = [i for i, b in enumerate(front) if b.get("clip")]
    single_front_clip = len(prebuilt_indices) == 1

    planned_front_narration = str(picked.get("front_narration") or "").strip()
    planned_front_cues = _clean_caption_cues(picked.get("front_caption_cues"))

    beats: List[Dict[str, Any]] = []
    has_pause = False

    for idx, b in enumerate(front):
        dur = float(b.get("duration_sec") or 0.0)
        is_clip = bool(b.get("clip"))
        is_pause = (not is_clip) and (bool(b.get("hold")) or dur < 1.0)
        if is_pause:
            has_pause = True
            beat: Dict[str, Any] = {
                "order": len(beats) + 1,
                "role": str(b.get("role") or "패턴 인터럽트"),
                "hold": True,
                "duration_sec": round(dur or 0.3, 2),
                "visual": str(b.get("visual") or "정지") or "정지",
                "narration": "",
                "caption": "",
                "shows_product": False,
            }
            beats.append(beat)
            continue

        narration = str(b.get("narration") or "")
        cues = _clean_caption_cues(b.get("caption_cues"))
        caption = _clean_caption_lines(str(b.get("caption") or ""))

        if single_front_clip and idx == prebuilt_indices[0]:
            if planned_front_narration:
                narration = planned_front_narration
            if planned_front_cues:
                cues = planned_front_cues
                caption = cues[0]
            elif cues and not caption:
                caption = cues[0]

        beat = {
            "order": len(beats) + 1,
            "role": str(b.get("role") or "어긋난 시작"),
            "duration_sec": round(dur, 2),
            "visual": str(b.get("visual") or ""),
            "narration": narration,
            "caption": caption,
            "shows_product": False,
        }
        if cues:
            beat["caption_cues"] = cues
        if is_clip:
            beat["prebuilt_clip"] = clip_ref(location, str(b["clip"]))
        beats.append(beat)

    if not has_pause:
        beats.append(
            {
                "order": len(beats) + 1,
                "role": "패턴 인터럽트",
                "hold": True,
                "duration_sec": 0.3,
                "visual": "정지",
                "narration": "",
                "caption": "",
                "shows_product": False,
            }
        )

    landing_sec = 0.0
    if ai_landing:
        landing = picked.get("landing") or {}
        landing_sec = round(float(landing.get("duration_sec") or 4.0), 2)
        beats.append(
            {
                "order": len(beats) + 1,
                "role": "담백한 실물 착지",
                "duration_sec": landing_sec,
                "visual": str(landing.get("visual") or ""),
                "narration": str(landing.get("narration") or ""),
                "caption": _clean_caption_lines(str(landing.get("caption") or "")),
                "shows_product": True,
            }
        )

    total = round(sum(float(b["duration_sec"]) for b in beats), 2)
    front_sec = round(total - landing_sec, 2)
    pause = next((b for b in beats if b.get("hold") or (float(b.get("duration_sec") or 0) < 1.0 and not b.get("narration"))), None)
    chosen_tid = str(template["template_id"])
    abstract_law = str(picked.get("abstract_law") or template.get("abstract_law") or "").strip()
    twist_callback_line = str(picked.get("twist_callback_line") or "").strip()

    return {
        "scenario_id": f"sc_{str(worker_input['project_id'])[-6:]}_A{int(worker_input.get('round', 1))}_{uuid.uuid4().hex[:4]}",
        "round": int(worker_input.get("round", 1)),
        "type": "A",
        "hook_title": str(picked.get("hook_title") or template.get("hook_title") or ""),
        "hook_duration_sec": total,
        "body_duration_sec": 0.0,
        "replacement_test_note": str(picked.get("replacement_test_note") or ""),
        "beats": beats,
        "ad_spec": {
            "track_archetype": "A_bgrade_reversal",
            "source": "template",
            "template_id": chosen_tid,
            "track_a_template_id": chosen_tid,
            "a_genre_archetype": template.get("genre"),
            "abstract_law": abstract_law,
            "bridge_reason": str(picked.get("bridge_reason") or "").strip(),
            "twist_callback_line": twist_callback_line,
            "product_taboo_keywords": [str(w) for w in picked.get("product_taboo_keywords") or []],
            "silence_gap_sec": float(pause["duration_sec"]) if pause else None,
            "ai_landing": bool(ai_landing),
            "pre_twist_ratio": round(front_sec / total, 3) if total else None,
            "payoff_ratio": round(landing_sec / total, 3) if total else None,
        },
    }


# ---------------------------------------------------------------------------
# Main Entrypoint: Tiered Orchestrator (Neon Plan+Critic -> Hydrogen Revise)
# ---------------------------------------------------------------------------


def make_template_scenario(
    worker_input: Dict[str, Any],
    settings: Any,
    storage: Any,
    work_dir: Path,
    *,
    writer: Optional[PickWriter] = None,
    planner: Optional[PickWriter] = None,
    critic: Optional[PickWriter] = None,
    executor: Optional[PickWriter] = None,
    model_override: Optional[str] = None,
    max_attempts: int = 2,
    max_revisions: int = MAX_CRITIC_REVISIONS,
) -> Dict[str, Any]:
    """제품 → (Neon 기획 → Neon 5축 비평 → 필요 시 Hydrogen 수정, 최대 2회) → {scenarios: [ScenarioItem]}."""
    catalog = load_catalog(settings, storage, work_dir)
    templates = {t["template_id"]: t for t in catalog["templates"]}
    product = worker_input["product_info"]
    if not product.get("verified_facts"):
        raise TemplateError("착지 장면을 쓰려면 검증된 제품 사실(verified_facts)이 필요합니다.")

    used: Set[str] = set()
    for prev in worker_input.get("previous_scenarios") or []:
        if not isinstance(prev, dict):
            continue
        spec = prev.get("ad_spec") or {}
        for key in ("template_id", "track_a_template_id"):
            val = str(spec.get(key) or "").strip()
            if val:
                used.add(val)
    choices = [t for t in catalog["templates"] if t["template_id"] not in used] or catalog["templates"]

    # Backwards-compatible fast path for legacy callers/tests passing a single `writer` callable
    if writer is not None and planner is None and critic is None and executor is None:
        has_flag = hasattr(settings, "hook_a_ai_landing")
        ai_landing = bool(getattr(settings, "hook_a_ai_landing")) if has_flag else True
        legacy_bounds = not has_flag
        feedback: Optional[str] = None
        errors: List[str] = []
        for _ in range(max(1, max_attempts)):
            picked = writer(PICK_SYSTEM, _catalog_prompt(product, choices, feedback, ai_landing=ai_landing))
            template = templates.get(str(picked.get("template_id") or ""))
            if template is None:
                feedback = f"- 목록에 없는 template_id 입니다: {picked.get('template_id')!r}"
                continue
            scenario = _assemble(worker_input, catalog["location"], template, picked, ai_landing=ai_landing)
            taboo = [str(w) for w in picked.get("product_taboo_keywords") or []] + [str(product.get("name", ""))]
            errors = _violations(
                scenario,
                taboo,
                ai_landing=ai_landing,
                template=template,
                product=product,
                legacy_landing_bounds=legacy_bounds,
            )
            if not errors:
                return {"scenarios": [scenario]}
            feedback = "\n".join(f"- {e}" for e in errors)
        raise TemplateError("템플릿으로 규칙에 맞는 시나리오를 만들지 못했습니다: " + (feedback or "; ".join(errors)))

    # Tiered 3-Stage Orchestrator: Plan (Neon) -> Critic Gate (Neon) -> Execute/Revise (Hydrogen, max 2 revisions)
    ai_landing = bool(getattr(settings, "hook_a_ai_landing", False))
    plan_schema = PLAN_SCHEMA_AI_LANDING if ai_landing else PLAN_SCHEMA_DIRECT

    planner_model = _resolve_planner_model(settings, model_override)
    critic_model = _resolve_critic_model(settings)
    executor_model = _resolve_executor_model(settings, model_override)

    plan_fn = planner or _make_gemini_json_caller(
        settings,
        model_id=planner_model,
        step_name="plan_template",
        schema=plan_schema,
    )
    critic_fn = critic or _make_gemini_json_caller(
        settings,
        model_id=critic_model,
        step_name="critic_gate",
        schema=CRITIC_SCHEMA,
    )
    exec_fn = executor or _make_gemini_json_caller(
        settings,
        model_id=executor_model,
        step_name="execute_revise",
        schema=plan_schema,
    )

    # Stage 1: Plan (Neon)
    current_plan = plan_fn(PLAN_SYSTEM, _plan_prompt(product, choices, ai_landing=ai_landing))
    last_errors: List[str] = []
    revisions_cap = max(0, int(max_revisions))

    for rev in range(revisions_cap + 1):
        tid = str(current_plan.get("template_id") or "").strip()
        template = templates.get(tid)
        det_errors: List[str] = []
        overlap_leaks: List[str] = []
        scenario: Optional[Dict[str, Any]] = None
        verdict: Optional[Dict[str, Any]] = None
        critic_passed = False

        if template is None:
            det_errors = [f"목록에 없는 template_id 입니다: {tid!r}"]
        else:
            scenario = _assemble(worker_input, catalog["location"], template, current_plan, ai_landing=ai_landing)
            taboo = [str(w) for w in current_plan.get("product_taboo_keywords") or []] + [str(product.get("name", ""))]
            det_errors = _violations(
                scenario,
                taboo,
                ai_landing=ai_landing,
                template=template,
                product=product,
            )
            _, overlapping_words = _split_taboo_keywords(product, taboo, template)
            overlap_leaks = _overlapping_leaks_in_front(scenario, overlapping_words)

            # Stage 2: Critic Gate (Neon)
            verdict = critic_fn(
                CRITIC_SYSTEM,
                _critic_prompt(
                    product,
                    template,
                    choices,
                    scenario,
                    current_plan,
                    ai_landing=ai_landing,
                    det_errors=det_errors,
                    overlap_leaks=overlap_leaks,
                ),
            )
            critic_passed = bool(verdict.get("passed"))
            defects = [str(d) for d in (verdict.get("defects") or []) if str(d).strip()]
            scenario["ad_spec"]["critic_verdict"] = {
                "passed": critic_passed,
                "scores": dict(verdict.get("scores") or {}),
                "defects": defects,
                "revisions": rev,
            }
            if not critic_passed:
                last_errors = [*det_errors, *(defects or [str(verdict.get("fix_instructions") or "비평 게이트 불합격")])]
            else:
                last_errors = list(det_errors)

        needs_paraphrase = bool(overlap_leaks) and rev < revisions_cap
        if template is not None and not det_errors and critic_passed and not needs_paraphrase:
            return {"scenarios": [scenario]}

        if rev >= revisions_cap:
            break

        # Stage 3: Execute / Revise (Hydrogen)
        current_plan = exec_fn(
            REVISE_SYSTEM,
            _revise_prompt(
                product,
                choices,
                current_plan,
                template,
                det_errors=det_errors,
                critic_verdict=verdict,
                overlap_leaks=overlap_leaks,
                ai_landing=ai_landing,
            ),
        )

    summary = "; ".join(last_errors[:5]) if last_errors else "비평 게이트 또는 규칙 검증 통과 실패"
    raise TemplateError(f"템플릿 오케스트레이터가 최대 수정 횟수({revisions_cap}회) 내에 통과하지 못했습니다: {summary}")
