"""FR-007 scenario-aware filming guide builder (`target_body = max(10, 30 - actual_hook)`)."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

_INTERNAL_ID_TOKEN_RE = re.compile(r"^[A-Za-z0-9_.-]+$")
_INTERNAL_ID_PREFIX_RE = re.compile(
    r"^(?:seg|beat|cut|shot|hook|payoff|clip|gap|tpl|scene|frame|twist|intro|outro)\d*$",
    re.IGNORECASE,
)


def _is_internal_id(text: str) -> bool:
    s = str(text or "").strip()
    if not s:
        return True
    if _INTERNAL_ID_TOKEN_RE.fullmatch(s) and ("_" in s or bool(_INTERNAL_ID_PREFIX_RE.fullmatch(s))):
        return True
    return False


def _clean_visual_text(text: Any) -> str:
    cleaned = str(text or "").replace("\\n", "\n").replace("\r", "")
    cleaned = re.sub(r"\*\*(.+?)\*\*", r"\1", cleaned)
    cleaned = re.sub(r"\n+", " ", cleaned)
    return re.sub(r"[ \t]{2,}", " ", cleaned).strip()


def _select_last_hook_visual(beats: List[Dict[str, Any]]) -> str:
    """Pick the last pre-payoff hook beat's human-readable visual/caption, never raw internal IDs."""
    if not beats:
        return ""
    gap_idx = next(
        (idx for idx, b in enumerate(beats) if str(b.get("role") or "").lower() == "silence_gap"),
        None,
    )
    if gap_idx is not None:
        hook_candidates = beats[:gap_idx]
    else:
        non_payoff = [
            b
            for b in beats
            if str(b.get("role") or "").lower() not in {"payoff", "silence_gap", "cta"}
        ]
        hook_candidates = (
            non_payoff
            if non_payoff
            else [b for b in beats if str(b.get("role") or "").lower() != "silence_gap"]
        )
    for beat in reversed(hook_candidates):
        for field in ("visual", "caption", "narration"):
            val = _clean_visual_text(beat.get(field))
            if val and not _is_internal_id(val):
                return val
    return ""


def compute_actual_hook_duration(scenario: Dict[str, Any]) -> float:
    """Compute actual hook duration from scenario beats, falling back to hook_duration_sec."""
    beats = scenario.get("beats") or []
    beat_sum = sum(float(b.get("duration_sec") or 0.0) for b in beats if isinstance(b, dict))
    if beat_sum > 0.0:
        return round(beat_sum, 2)
    hook_dur = float(scenario.get("hook_duration_sec") or 0.0)
    return round(hook_dur, 2) if hook_dur > 0.0 else 12.0


def compute_target_body_duration(scenario: Dict[str, Any]) -> float:
    """Compute body target duration as max(10.0, 30.0 - actual_hook_duration), ignoring stale body_duration_sec."""
    actual_hook = compute_actual_hook_duration(scenario)
    return max(10.0, round(30.0 - actual_hook, 1))


def _fact_index_from_id(fact_id: str, total_facts: int) -> Optional[int]:
    m = re.search(r"(\d+)", str(fact_id or ""))
    if not m:
        return None
    idx = int(m.group(1)) - 1
    return idx if 0 <= idx < total_facts else None


def _prioritize_facts(
    facts: List[str],
    claim_ids: List[str],
) -> List[tuple[str, str]]:
    """Return ordered list of (Fxx_ref, fact_text), prioritizing ad_spec.claim_ids."""
    ordered: List[tuple[str, str]] = []
    used_indices = set()
    for cid in claim_ids:
        idx = _fact_index_from_id(cid, len(facts))
        if idx is not None and idx not in used_indices:
            used_indices.add(idx)
            ordered.append((f"F{idx + 1:02d}", facts[idx]))
    for idx, text in enumerate(facts):
        if idx not in used_indices:
            used_indices.add(idx)
            ordered.append((f"F{idx + 1:02d}", text))
    return ordered


def _allocate_shot_durations(target_sec: float, shot_count: int) -> List[float]:
    if shot_count <= 1:
        return [round(target_sec, 1)]
    weights = [0.25] + [0.50 / max(1, shot_count - 2)] * max(0, shot_count - 2) + [0.25]
    if len(weights) != shot_count:
        weights = [1.0 / shot_count] * shot_count
    durs = [max(2.0, round(target_sec * w, 1)) for w in weights[:-1]]
    rem = round(target_sec - sum(durs), 1)
    if rem < 2.0 and durs:
        # Rebalance proportionally if rounding pushed last shot below 2.0s
        scale = (target_sec - 2.0) / max(0.1, sum(durs))
        durs = [max(1.5, round(d * scale, 1)) for d in durs]
        rem = round(target_sec - sum(durs), 1)
    durs.append(round(rem, 1))
    return durs


def build_filming_guide(project: Dict[str, Any], scenario: Dict[str, Any]) -> Dict[str, Any]:
    """Generate a scenario-aligned shot-by-shot filming guide for the body segment."""
    product = project["product"]
    product_name = str(product.get("name") or "제품").strip()
    raw_facts = [str(f).strip() for f in (product.get("verified_facts") or []) if str(f).strip()]
    if not raw_facts:
        raw_facts = [f"{product_name} 핵심 실물 시연"]

    hook_type = str(scenario.get("type") or "C").upper()
    beats = [b for b in (scenario.get("beats") or []) if isinstance(b, dict)]
    ad_spec = scenario.get("ad_spec") or {}
    claim_ids = [str(c) for c in (ad_spec.get("claim_ids") or []) if c]
    cta_obj = ad_spec.get("cta") if isinstance(ad_spec.get("cta"), dict) else {}
    cta_text = str(cta_obj.get("text") or cta_obj.get("copy") or "").strip()
    first_mention_beat = ad_spec.get("product_first_mention_beat")

    ordered_facts = _prioritize_facts(raw_facts, claim_ids)
    last_hook_visual = _select_last_hook_visual(beats)
    hook_title = str(scenario.get("hook_title") or "").strip()

    target_body_sec = compute_target_body_duration(scenario)

    # Build 3~4 shots depending on verified_facts count
    shot_templates: List[Dict[str, str]] = []
    if hook_type == "A":
        tip_intro = (
            f"세로 9:16 고정 구도. 훅('{hook_title[:24]}') 반전 직후 화면 전환이 튀지 않게 "
            f"{product_name} 실물 전체 모습을 톤을 낮춰 담백하게 보여주세요."
        )
        title_intro = f"{product_name} 반전 직후 실물 등장"
    elif hook_type == "B":
        beat_hint = f" (장면 {first_mention_beat} 전환 연동)" if first_mention_beat else ""
        tip_intro = (
            f"세로 9:16 클로즈업{beat_hint}. 앞선 원리 설명과 닮은 {product_name}의 핵심 구조가 "
            f"한눈에 겹쳐 보이도록 손/부품 위치를 맞춰 찍어주세요."
        )
        title_intro = f"{product_name} 핵심 구조 매치 컷"
    else:
        tip_intro = (
            "세로 9:16 밝은 조명. 문제 상황 직후 가장 확실한 실물 동작 증명이 바로 시작되도록 "
            "제품 작동 모습을 흔들림 없이 찍어주세요."
        )
        title_intro = f"{product_name} 문제 해결 첫 증명 컷"

    if last_hook_visual:
        tip_intro += f" (직전 훅 구도 참고: {last_hook_visual[:36]})"

    f0_ref, f0_txt = ordered_facts[0]
    shot_templates.append(
        {
            "title": title_intro,
            "framing_tip": tip_intro,
            "fact_ref": f0_ref,
        }
    )

    demo_facts = ordered_facts[:2] if len(ordered_facts) >= 2 else ordered_facts[:1]
    for d_idx, (f_ref, f_txt) in enumerate(demo_facts):
        prefix = "핵심 동작 증명" if (hook_type == "C" and d_idx == 0) else "실물 특징 시연"
        shot_templates.append(
            {
                "title": f"{prefix} — {f_txt[:28]}",
                "framing_tip": (
                    f"'{f_txt[:40]}' 특징이 실제 사용 중 선명히 드러나게 1.5~2배 가까이 클로즈업하고 "
                    "손이 제품을 가리지 않게 촬영해 주세요."
                ),
                "fact_ref": f_ref,
            }
        )

    last_ref, last_txt = ordered_facts[-1]
    closing_tip = "사용 후 깔끔해진 결과 상태와 제품 전체 실루엣을 2초 이상 정지감 있게 담아주세요."
    if cta_text:
        closing_tip += f" (마무리 유도 문구 '{cta_text[:28]}'에 어울리는 여백 확보)"
    shot_templates.append(
        {
            "title": f"사용 결과 및 마무리 — {last_txt[:24]}",
            "framing_tip": closing_tip,
            "fact_ref": last_ref,
        }
    )

    # Cap to 5 shots max per spec
    shot_templates = shot_templates[:5]
    durations = _allocate_shot_durations(target_body_sec, len(shot_templates))

    shots = [
        {
            "shot_no": idx + 1,
            "title": tpl["title"],
            "duration_sec": durations[idx],
            "framing_tip": tpl["framing_tip"],
            "fact_ref": tpl["fact_ref"],
        }
        for idx, tpl in enumerate(shot_templates)
    ]

    return {
        "project_id": project["project_id"],
        "status": "GUIDE_READY",
        "selected_scenario_id": scenario["scenario_id"],
        "target_body_duration_sec": round(sum(s["duration_sec"] for s in shots), 1),
        "shots": shots,
    }
