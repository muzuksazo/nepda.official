"""A 유형 템플릿: 제품과 무관한 앞부분은 미리 만든 영상을 쓰고, 제품 착지 장면만 요청마다 만든다.

템플릿 저장 위치 (설정 HOOK_A_TEMPLATES)
- "storage:templates/a"  서버 저장소(R2)의 그 경로. 배포 기본값.
- 그 밖의 값            로컬 폴더 경로 (개발·테스트용).
위치 아래에 catalog.json 하나와 장면 영상들이 있다. 템플릿을 만드는 쪽이 따라야 하는 형식:

    catalog.json
    {
      "version": 1,
      "templates": [
        {
          "template_id": "physics_glass_floor_01",
          "abstract_law": "보이는 면적이 줄면 흩어진 것이 한 점으로 모인다",   # 제품·카테고리 단어 없이
          "genre": "extreme_physics_experiment",
          "hook_title": "유리 바닥을 바깥부터 깨면 쇠구슬 3천 개는 어디로 갈까",
          "beats": [                                                         # 제품이 나오지 않는 앞부분 (10~14초 권장)
            {"order": 1, "role": "어긋난 시작", "duration_sec": 4.0, "visual": "...", "narration": "...", "caption": "...",
             "clip": "physics_glass_floor_01/beat_01.mp4"},                  # 위치 기준 상대 경로, 9:16 영상
            {"order": 2, "role": "빌드업", "duration_sec": 4.5, ...},
            {"order": 3, "role": "패턴 인터럽트", "duration_sec": 0.3, "visual": "정지", "narration": "", "caption": "",
             "clip": null}                                                   # 1초 미만 무음 장면은 앞 장면 마지막 화면 정지
          ]
        }
      ]
    }

나레이션은 영상에 넣지 않는다 (목소리를 착지 장면과 맞추려고 요청마다 새로 만든다). 자막도 넣지 않는다.
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("hookpipe.a_templates")

STORAGE_SCHEME = "storage:"
LANDING_MIN_SEC, LANDING_MAX_SEC = 3.0, 7.0
CAPTION_MAX_CHARS = 22
MAX_SYLLABLES_PER_SEC = 7.5

PICK_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["abstract_law", "template_id", "hook_title", "replacement_test_note", "product_taboo_keywords", "landing"],
    "properties": {
        "abstract_law": {"type": "string"},
        "template_id": {"type": "string"},
        "hook_title": {"type": "string"},
        "replacement_test_note": {"type": "string"},
        "product_taboo_keywords": {"type": "array", "items": {"type": "string"}},
        "landing": {
            "type": "object",
            "additionalProperties": False,
            "required": ["duration_sec", "visual", "narration", "caption"],
            "properties": {
                "duration_sec": {"type": "number"},
                "visual": {"type": "string"},
                "narration": {"type": "string"},
                "caption": {"type": "string"},
            },
        },
    },
}

PICK_SYSTEM = """당신은 숏폼 광고 Track A(무맥락 반전) 작가입니다.
앞부분은 제품과 무관한 장면(이미 만들어 둔 템플릿)이고, 당신은 1) 제품에 맞는 템플릿을 고르고 2) 마지막 '실물 착지' 장면 하나를 씁니다.
규칙:
- abstract_law: 제품·카테고리·사용 공간 단어가 0% 인 순수 물리·심리 법칙 한 줄을 먼저 뽑습니다.
- template_id: 그 법칙과 가장 잘 이어지는 템플릿을 목록에서 정확히 하나 고릅니다 (목록의 id 그대로).
- landing: 앞부분의 법칙을 받아 실제 제품으로 담백하게 착지하는 장면 하나. 검증된 사실에 있는 내용만 말합니다.
  과장('완벽', '100%', '기적의', '최초'), 가격·할인, 'C안식 스펙 나열'('딱 좋아요', '강력 추천')은 쓰지 않습니다.
  narration 은 '~습니다'체 한두 문장, 장면 길이 1초당 6음절 안팎. caption 은 2줄 이내, 한 줄 22자 이내, 이모지 금지.
  visual 에는 화면에 보이는 것만 씁니다. 화면 안 글자·숫자는 넣지 않습니다.
- hook_title: 템플릿 제목을 그대로 쓰거나 다듬습니다.
- replacement_test_note: 왜 앞부분을 다른 제품에도 옮길 수 있는지 한 줄.
- product_taboo_keywords: 제품명·부품명·사용 공간 등 앞부분에 나오면 안 되는 단어."""

PickWriter = Callable[[str, str], Dict[str, Any]]


class TemplateError(RuntimeError):
    """템플릿을 쓸 수 없을 때 (목록 없음, 고르기 실패, 규칙 위반). 호출하는 쪽은 실시간 생성으로 넘어간다."""


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
    templates = [t for t in (catalog.get("templates") or []) if isinstance(t, dict) and t.get("template_id") and t.get("beats")]
    if not templates:
        raise TemplateError("A 템플릿 목록이 비어 있습니다.")
    return {"location": location, "templates": templates}


def clip_ref(location: str, clip: str) -> str:
    """템플릿 장면 영상 → 장면의 prebuilt_clip 값 (저장소 키 또는 로컬 절대 경로)."""
    clip = clip.strip().lstrip("/")
    if location.startswith(STORAGE_SCHEME):
        return f"{location[len(STORAGE_SCHEME):].strip('/')}/{clip}"
    return str((Path(location) / clip).resolve())


def _catalog_prompt(product: Dict[str, Any], templates: List[Dict[str, Any]], feedback: Optional[str]) -> str:
    facts = [str(f) for f in (product.get("verified_facts") or []) if str(f).strip()]
    lines = [
        f"제품: {product.get('name', '')}",
        "검증된 사실:",
        *[f"- [F{i:02d}] {f}" for i, f in enumerate(facts, 1)],
        "",
        "템플릿 목록 (앞부분, 제품 없음):",
    ]
    for t in templates:
        front = sum(float(b.get("duration_sec") or 0) for b in t["beats"])
        story = " / ".join(str(b.get("narration") or "").strip() for b in t["beats"] if b.get("narration"))
        lines.append(f"- {t['template_id']} | 법칙: {t.get('abstract_law', '')} | 장르: {t.get('genre', '')} | "
                     f"{front:.1f}초 | 제목: {t.get('hook_title', '')} | 내용: {story[:160]}")
    lines += ["", f"착지 장면 길이는 {LANDING_MIN_SEC:g}~{LANDING_MAX_SEC:g}초이고, 앞부분과 합쳐 15~20초가 되게 합니다."]
    if feedback:
        lines += ["", "직전 결과가 아래 규칙을 어겼습니다. 고쳐서 다시 써 주세요:", feedback]
    return "\n".join(lines)


def gemini_pick_writer(settings: Any) -> PickWriter:
    def _write(system: str, prompt: str) -> Dict[str, Any]:
        from google.genai import types

        from app.genai_provider import build_genai_client

        client = build_genai_client(settings)  # 변수에 담아 둔다 (요청 도중 닫히지 않게)
        response = client.models.generate_content(
            model=str(getattr(settings, "hook_worker_llm", "") or getattr(settings, "body_llm", "") or "gemini-4-hydrogen"),
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=system, response_mime_type="application/json", response_json_schema=PICK_SCHEMA
            ),
        )
        text = getattr(response, "text", None) or ""
        try:
            return json.loads(text)
        except ValueError as exc:
            raise TemplateError(f"템플릿 고르기 응답을 읽지 못했습니다: {text[:200]!r}") from exc

    return _write


def _violations(scenario: Dict[str, Any], taboo: List[str]) -> List[str]:
    errors: List[str] = []
    beats = scenario["beats"]
    total = sum(float(b["duration_sec"]) for b in beats)
    if not (15.0 - 1e-6 <= total <= 20.0 + 1e-6):
        errors.append(f"훅 길이는 15~20초여야 합니다 (현재 {total:.1f}초).")
    landing = beats[-1]
    if not (LANDING_MIN_SEC - 1e-6 <= float(landing["duration_sec"]) <= LANDING_MAX_SEC + 1e-6):
        errors.append(f"착지 장면은 {LANDING_MIN_SEC:g}~{LANDING_MAX_SEC:g}초여야 합니다.")
    for b in beats:
        lines = str(b.get("caption") or "").split("\n")
        if len(lines) > 2 or any(len(line) > CAPTION_MAX_CHARS for line in lines):
            errors.append(f"장면 {b['order']}: 자막은 2줄 이내, 한 줄 {CAPTION_MAX_CHARS}자 이내여야 합니다.")
        syllables = len(re.findall(r"[가-힣]", str(b.get("narration") or "")))
        if b["duration_sec"] and syllables / float(b["duration_sec"]) > MAX_SYLLABLES_PER_SEC:
            errors.append(f"장면 {b['order']}: 나레이션이 장면 길이에 비해 깁니다.")
    front_text = " ".join(f"{b.get('narration', '')} {b.get('caption', '')}" for b in beats[:-1])
    leaked = [w for w in taboo if w and len(w) >= 2 and w in front_text]
    if leaked:
        errors.append(f"앞부분(템플릿)에 제품 단어가 들어 있습니다: {', '.join(leaked[:3])}. 다른 템플릿을 고르세요.")
    return errors


def make_template_scenario(
    worker_input: Dict[str, Any],
    settings: Any,
    storage: Any,
    work_dir: Path,
    *,
    writer: Optional[PickWriter] = None,
    max_attempts: int = 2,
) -> Dict[str, Any]:
    """제품 → (템플릿 고르기 + 착지 장면) → 작업자 응답 모양 {scenarios: [ScenarioItem]}."""
    catalog = load_catalog(settings, storage, work_dir)
    templates = {t["template_id"]: t for t in catalog["templates"]}
    product = worker_input["product_info"]
    if not product.get("verified_facts"):
        raise TemplateError("착지 장면을 쓰려면 검증된 제품 사실(verified_facts)이 필요합니다.")
    write = writer or gemini_pick_writer(settings)
    used = {s.get("ad_spec", {}).get("template_id") for s in worker_input.get("previous_scenarios") or []}
    choices = [t for t in catalog["templates"] if t["template_id"] not in used] or catalog["templates"]
    feedback: Optional[str] = None
    errors: List[str] = []
    for _ in range(max(1, max_attempts)):
        picked = write(PICK_SYSTEM, _catalog_prompt(product, choices, feedback))
        template = templates.get(str(picked.get("template_id") or ""))
        if template is None:
            feedback = f"- 목록에 없는 template_id 입니다: {picked.get('template_id')!r}"
            continue
        scenario = _assemble(worker_input, catalog["location"], template, picked)
        taboo = [str(w) for w in picked.get("product_taboo_keywords") or []] + [str(product.get("name", ""))]
        errors = _violations(scenario, taboo)
        if not errors:
            return {"scenarios": [scenario]}
        feedback = "\n".join(f"- {e}" for e in errors)
    raise TemplateError("템플릿으로 규칙에 맞는 시나리오를 만들지 못했습니다: " + (feedback or "; ".join(errors)))


def _assemble(worker_input: Dict[str, Any], location: str, template: Dict[str, Any], picked: Dict[str, Any]) -> Dict[str, Any]:
    front = sorted(template["beats"], key=lambda b: int(b.get("order") or 0))
    beats: List[Dict[str, Any]] = []
    for b in front:
        beat = {
            "order": len(beats) + 1,
            "role": str(b.get("role") or ""),
            "duration_sec": float(b.get("duration_sec") or 0.0),
            "visual": str(b.get("visual") or ""),
            "narration": str(b.get("narration") or ""),
            "caption": str(b.get("caption") or ""),
        }
        if b.get("clip"):
            beat["prebuilt_clip"] = clip_ref(location, str(b["clip"]))
        beats.append(beat)
    landing = picked.get("landing") or {}
    beats.append({
        "order": len(beats) + 1,
        "role": "담백한 실물 착지",
        "duration_sec": round(float(landing.get("duration_sec") or 4.0), 2),
        "visual": str(landing.get("visual") or ""),
        "narration": str(landing.get("narration") or ""),
        "caption": str(landing.get("caption") or ""),
    })
    total = round(sum(b["duration_sec"] for b in beats), 2)
    front_sec = total - beats[-1]["duration_sec"]
    pause = next((b for b in front if float(b.get("duration_sec") or 0) < 1.0 and not b.get("narration")), None)
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
            "template_id": template["template_id"],
            "a_genre_archetype": template.get("genre"),
            "abstract_law": str(picked.get("abstract_law") or template.get("abstract_law") or ""),
            "product_taboo_keywords": [str(w) for w in picked.get("product_taboo_keywords") or []],
            "silence_gap_sec": float(pause["duration_sec"]) if pause else None,
            "pre_twist_ratio": round(front_sec / total, 3) if total else None,
            "payoff_ratio": round(beats[-1]["duration_sec"] / total, 3) if total else None,
        },
    }
