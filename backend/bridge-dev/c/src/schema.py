"""C 훅 작업자 입출력 형태 (01_worker-input, ScenarioItem) 와 간단한 검증.

외부 의존성 없이 dict 로 다룬다. 필드 정의의 기준은 ../api-guide.md 와 contracts/openapi.json 이다.
"""
from __future__ import annotations

HOOK_TYPE = "C"
MAX_HOOK_SEC = 15.0
MIN_BEATS, MAX_BEATS = 3, 5


class InputError(ValueError):
    pass


def fact_ids(product_info: dict) -> dict[str, str]:
    """verified_facts 순서대로 F01, F02 … 를 붙인다. (근거 ID 는 이 순서가 기준)"""
    return {f"F{i:02d}": text for i, text in enumerate(product_info.get("verified_facts", []), 1)}


def parse_worker_input(data: dict) -> dict:
    """01_worker-input.scenarios.json 형태를 확인하고 기본값을 채워 돌려준다."""
    if not isinstance(data, dict):
        raise InputError("입력은 JSON 객체여야 합니다.")
    if data.get("hook_type", HOOK_TYPE) != HOOK_TYPE:
        raise InputError(f'hook_type 은 "{HOOK_TYPE}" 여야 합니다.')
    product = data.get("product_info")
    if not isinstance(product, dict) or not product.get("name"):
        raise InputError("product_info.name 이 필요합니다.")
    facts = product.get("verified_facts")
    if not isinstance(facts, list) or not facts or not all(isinstance(f, str) and f.strip() for f in facts):
        raise InputError("product_info.verified_facts 에 검증된 사실이 1개 이상 필요합니다.")
    if not data.get("project_id"):
        raise InputError("project_id 가 필요합니다.")
    assets = data.get("assets") or {}
    if not isinstance(assets, dict):
        raise InputError("assets 는 객체여야 합니다.")
    return {
        "hook_type": HOOK_TYPE,
        "project_id": str(data["project_id"]),
        "round": int(data.get("round", 1)),
        "count": max(1, min(10, int(data.get("count", 1)))),
        "product_info": product,
        "previous_scenarios": list(data.get("previous_scenarios") or []),
        # 가이드의 제안 인터페이스에 없는 확장 필드. 영상에 쓸 실물 소재와 문제 장면 템플릿을 알려 준다.
        "assets": {
            "product_footage": assets.get("product_footage"),      # 실물 제품 영상 경로 (증명 장면에 사용)
            "problem_template": assets.get("problem_template"),    # 생성 문제 장면 템플릿 이름 (예: spill_diffuser)
        },
    }


# Claude 구조화 출력에 쓰는 JSON 스키마. 길이 합·장면 수 같은 규칙은 check.py 가 검사한다.
SCENARIO_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["scenarios"],
    "properties": {
        "scenarios": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["hook_title", "replacement_test_note", "pov_label", "beats", "claim_ids", "cta_text"],
                "properties": {
                    "hook_title": {"type": "string"},
                    "replacement_test_note": {"type": "string"},
                    "pov_label": {"type": "string"},
                    "claim_ids": {"type": "array", "items": {"type": "string"}},
                    "cta_text": {"type": "string"},
                    "beats": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["order", "role", "duration_sec", "visual", "narration", "caption"],
                            "properties": {
                                "order": {"type": "integer"},
                                "role": {"type": "string"},
                                "duration_sec": {"type": "number"},
                                "visual": {"type": "string"},
                                "narration": {"type": "string"},
                                "caption": {"type": "string"},
                            },
                        },
                    },
                },
            },
        }
    },
}


def to_scenario_item(draft: dict, *, scenario_id: str, round_no: int, body_duration_sec: float = 0.0) -> dict:
    """모델(또는 오프라인 초안)이 준 초안을 ScenarioItem 으로 만든다."""
    beats = []
    for i, b in enumerate(sorted(draft["beats"], key=lambda x: x.get("order", 0)), 1):
        beats.append({
            "order": i,
            "role": str(b["role"]).strip(),
            "duration_sec": round(float(b["duration_sec"]), 2),
            "visual": str(b["visual"]).strip(),
            "narration": str(b["narration"]).strip(),
            "caption": str(b["caption"]).strip(),
        })
    return {
        "scenario_id": scenario_id,
        "round": round_no,
        "type": HOOK_TYPE,
        "hook_title": str(draft["hook_title"]).strip(),
        "hook_duration_sec": round(sum(b["duration_sec"] for b in beats), 2),
        "body_duration_sec": float(body_duration_sec),
        "replacement_test_note": str(draft["replacement_test_note"]).strip(),
        "beats": beats,
        "ad_spec": {
            "track_archetype": "C_direct_proof",
            "claim_ids": sorted(set(draft.get("claim_ids") or [])),
            "proof_first": True,
            "cta": {"type": "comment_engagement", "text": str(draft.get("cta_text", "")).strip()},
            "disclosure": "ai_assisted",
            "pov_label": str(draft.get("pov_label", "")).strip(),
        },
    }
