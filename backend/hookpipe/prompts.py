"""시나리오 장면(beat) → 영상 모델 프롬프트. 유형별 화면 톤과 제품 장면 판정을 담는다."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

# 작업자가 장면 설명에 붙이는 꼬리표: B 의 [포커스: 전체], C 의 [F02] 같은 근거 번호. 영상 모델에는 넘기지 않는다.
_TAG_RE = re.compile(r"\[[^\[\]]{1,24}\]")


def clean_visual(text: Any) -> str:
    return re.sub(r"\s{2,}", " ", _TAG_RE.sub(" ", str(text or ""))).strip()

COMMON_RULES = """RULES (apply to every shot):
- Framing: vertical 9:16. Main subject in the UPPER two thirds of the frame. Keep the bottom third calm (subtitles go there).
- Camera: one continuous shot with gentle movement. No cuts inside the clip.
- FORBIDDEN: any readable text, letters, words, numbers or digits anywhere in the frame (no subtitles, captions, speech bubbles, signs, labels, title cards); watermarks; logos; real brand marks. Subtitles are added later by the editor.
- Keep the same look, palette and main character across all shots of this story.
- Never show blood, wounds, organs, bones inside the body or anatomical cutaways; show the outside of the body or an everyday analogy instead.
- Audio: rich natural sound effects and ambient foley matching the on-screen action; NO speech, NO human voice, NO narration, NO singing."""

STYLE_BY_TYPE: Dict[str, str] = {
    "A": "LOOK: cinematic genre short film, strong mood lighting, shallow depth of field. Commit fully to the genre of the story.",
    # 2026-11-27: 'soft clay' 를 쓰면 모델이 점토 인형처럼만 그렸다 → 블렌더로 모델링·렌더링한 3D 톤으로
    "B": (
        "LOOK: stylized 3D render as if modeled and rendered in Blender (Cycles) on a small diorama stage: clean "
        "bevelled geometry, physically based materials (glossy plastic, glass, brushed metal, polished wood), soft "
        "global illumination with gentle ambient occlusion, warm window light. NOT clay, NOT photorealistic. "
        "One vivid red accent for the key detail."
    ),
    "C": (
        "LOOK: realistic everyday footage shot on a smartphone in a bright home, natural light, "
        "believable hands and props. Honest and plain, not glossy advertising."
    ),
}


def style_text(scenario: Dict[str, Any]) -> str:
    """유형 기본 톤 + 시나리오가 직접 정한 visual_style(있으면)."""
    hook_type = str(scenario.get("type") or "C")
    base = STYLE_BY_TYPE.get(hook_type, STYLE_BY_TYPE["C"])
    own = str((scenario.get("ad_spec") or {}).get("visual_style") or "").strip()
    # blender_3d_physics 같은 렌더러 이름은 영상 모델에 뜻이 없어 넘기지 않는다
    if own.lower().startswith(("blender_", "flow_", "remotion", "three")):
        own = ""
    if own:
        base = f"{base}\nSTYLE REQUESTED BY THE SCENARIO: {own}"
    return f"{base}\n{COMMON_RULES}"


def ordered_beats(scenario: Dict[str, Any]) -> List[Dict[str, Any]]:
    beats = [b for b in (scenario.get("beats") or []) if isinstance(b, dict)]
    return sorted(beats, key=lambda b: int(b.get("order") or 0))


def product_beat_orders(scenario: Dict[str, Any]) -> List[int]:
    """제품이 화면에 나와야 하는 장면 번호.

    B: ad_spec.product_first_mention_beat 부터. C: '문제' 장면을 뺀 전부. A·그 밖: 마지막 장면.
    """
    beats = ordered_beats(scenario)
    if not beats:
        return []
    orders = [int(b.get("order") or 0) for b in beats]
    spec = scenario.get("ad_spec") or {}
    first = spec.get("product_first_mention_beat")
    if isinstance(first, (int, float)) and not isinstance(first, bool) and int(first) in orders:
        return [o for o in orders if o >= int(first)]
    if str(scenario.get("type")) == "C":
        picked = [
            int(b.get("order") or 0)
            for b in beats
            if "문제" not in str(b.get("role") or "") and "problem" not in str(b.get("role") or "").lower()
        ]
        return picked or [orders[-1]]
    return [orders[-1]]


_INSIDE_RE = re.compile(r"(내부\s*)?(단면도?|절개|해부)(\s*시각화)?|cross[- ]?section|cutaway|anatom\w*", re.IGNORECASE)
_OUTSIDE_RULE = "Show everything from the outside: no cutaway, cross-section, x-ray or anatomical interior view."


def soften_prompt(prompt: str) -> str:
    """영상 모델이 거절한 장면용: 몸속 단면·해부 묘사를 바깥에서 본 장면으로 바꾼다. 바꿀 것이 없으면 그대로."""
    if not _INSIDE_RE.search(prompt):
        return prompt
    return _INSIDE_RE.sub("바깥에서 본 모습", prompt) + "\n" + _OUTSIDE_RULE


def _story(scenario: Dict[str, Any]) -> str:
    spec = scenario.get("ad_spec") or {}
    return str(spec.get("story_seed") or scenario.get("hook_title") or "")


def reference_image_prompt(scenario: Dict[str, Any]) -> str:
    return (
        f"{style_text(scenario)}\n"
        f"A single style and character reference frame for this story: {_story(scenario)}. "
        "Show the main character (or main object) of the story, full body, centered in the upper two thirds, plain background."
    )


def beat_prompt(
    scenario: Dict[str, Any],
    beat: Dict[str, Any],
    index: int,
    total: int,
    *,
    product: Optional[Dict[str, Any]] = None,
    shows_product: bool = False,
    has_product_reference: bool = False,
    has_style_reference: bool = False,
) -> str:
    lines = [
        style_text(scenario),
        f"STORY (told over {total} shots): {_story(scenario)}",
        f"THIS SHOT ({index}/{total}): {clean_visual(beat.get('visual'))}",
    ]
    scene3d = beat.get("scene3d") or {}
    if isinstance(scene3d, dict):
        if scene3d.get("fact_shown"):
            lines.append(f"What the viewer must understand: {scene3d['fact_shown']}")
        motions = [m for m in (scene3d.get("motion") or []) if isinstance(m, dict) and m.get("action")]
        if motions:
            ordered = sorted(motions, key=lambda m: m.get("from", 0))
            lines.append("Motion to show: " + "; ".join(str(m["action"]) for m in ordered))
    if shows_product and product:
        name = product.get("call_name") or product.get("name") or ""
        facts = [str(f) for f in (product.get("verified_facts") or []) if str(f).strip()]
        if has_product_reference:
            lines.append(
                f'PRODUCT IN THIS SHOT: "{name}". It must look EXACTLY like the product in the reference photos '
                "(same shape, colors, label design). Do not invent a different product. Keep it large and clearly visible."
            )
        else:
            lines.append(f'PRODUCT IN THIS SHOT: "{name}". Show it large and clearly, as the facts below describe it.')
        if facts:
            lines.append(
                "Product facts (do not show anything that contradicts them):\n" + "\n".join(f"- {f}" for f in facts[:8])
            )
    elif has_style_reference:
        lines.append("Keep the same main character, look and palette as the reference image.")
    # 나레이션 문장은 넣지 않는다: '글자로 그리지 말라'고 해도 영상 모델이 문장을 깨진 한글 자막으로 그려 넣었다 (2026-11-27 실측)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 자체 호스팅 모델용 (FLUX klein 첫 프레임 → MiniMax-H3 움직임). 규칙은 위와 같고 모양만 각 모델에 맞춘다.
# FLUX 는 규칙 목록보다 '한 장면을 묘사한 문장'을 잘 따르고, MiniMax 는 첫 프레임에서 무엇이 움직이는지만 들으면 된다.
# ---------------------------------------------------------------------------

FRAME_LOOK_BY_TYPE: Dict[str, str] = {
    "A": "A cinematic film still with strong moody lighting and shallow depth of field.",
    # 2026-11-27: '손으로 빚은 점토'를 쓰면 FLUX 가 지나치게 점토 인형처럼 그렸다 → 매끈한 3D 애니메이션 톤으로
    "B": (
        "A stylized 3D render as if modeled and rendered in Blender with Cycles: clean bevelled geometry, physically "
        "based materials (glossy plastic, glass, brushed metal, polished wood), soft global illumination and gentle "
        "ambient occlusion, a small diorama-like stage, warm window light, calm natural palette. Not clay, no "
        "fingerprints or sculpting marks. The one part that explains the idea is highlighted in vivid red; do not add "
        "any other red objects. Not photorealistic."
    ),
    "C": (
        "A realistic vertical smartphone photo taken at home in bright natural daylight: plain, honest, "
        "believable hands and everyday props, slight phone-camera look, not glossy advertising."
    ),
}

FRAME_LAYOUT = (
    "Vertical 9:16 frame. The main subject sits in the upper two thirds; the bottom third is calm, simple "
    "background with nothing important in it. No text, letters, numbers, captions, signs, labels, logos or watermarks anywhere."
)

MOTION_RULES = (
    "One continuous shot that starts exactly from the given first frame, keeping the same look, characters, "
    "colors and layout; no cuts, no scene change. Smooth, readable motion. Keep the bottom third of the frame calm. "
    "No text or captions appear at any time. Sound: natural ambient sound effects only — no speech, no voice, no singing, no music."
)


def _look(scenario: Dict[str, Any]) -> str:
    hook_type = str(scenario.get("type") or "C")
    look = FRAME_LOOK_BY_TYPE.get(hook_type, FRAME_LOOK_BY_TYPE["C"])
    own = str((scenario.get("ad_spec") or {}).get("visual_style") or "").strip()
    if own and not own.lower().startswith(("blender_", "flow_", "remotion", "three")):
        look = f"{look} Style notes: {own}."
    return look


def _motions(beat: Dict[str, Any]) -> List[str]:
    scene3d = beat.get("scene3d") or {}
    if not isinstance(scene3d, dict):
        return []
    moves = [m for m in (scene3d.get("motion") or []) if isinstance(m, dict) and m.get("action")]
    return [str(m["action"]) for m in sorted(moves, key=lambda m: m.get("from", 0))]


def first_frame_prompt(
    scenario: Dict[str, Any],
    beat: Dict[str, Any],
    *,
    product: Optional[Dict[str, Any]] = None,
    shows_product: bool = False,
    has_product_reference: bool = False,
) -> str:
    """FLUX 첫 프레임: 이 장면이 시작하는 순간 한 장. 장면 설명(한국어 그대로)과 유형별 화면 톤을 한 문단으로."""
    parts = [
        _look(scenario),
        f"The opening moment of this shot: {clean_visual(beat.get('visual'))}.",
    ]
    fact = (beat.get("scene3d") or {}).get("fact_shown") if isinstance(beat.get("scene3d"), dict) else None
    if fact:
        parts.append(f"The image should make this clear at a glance: {fact}.")
    if shows_product and product:
        name = product.get("call_name") or product.get("name") or "the product"
        if has_product_reference:
            parts.append(
                f"The product ({name}) from the reference photo appears large and clearly visible, with exactly the same "
                "shape, color, size and surface as in the photo; do not redesign it. Everything around it follows the look above."
            )
        else:
            facts = "; ".join(str(f) for f in (product.get("verified_facts") or [])[:4] if str(f).strip())
            parts.append(f"The product ({name}) appears large and clearly visible." + (f" It is: {facts}." if facts else ""))
    parts.append(FRAME_LAYOUT)
    return " ".join(parts)


def motion_prompt(scenario: Dict[str, Any], beat: Dict[str, Any], *, shows_product: bool = False) -> str:
    """MiniMax 움직임: 첫 프레임에서 무엇이 어떻게 움직이는지. 나레이션 문장은 넣지 않는다 (말소리·자막이 생긴다)."""
    parts = [_look(scenario), f"What happens in this shot: {clean_visual(beat.get('visual'))}."]
    moves = _motions(beat)
    if moves:
        parts.append("Motion, in order: " + "; then ".join(moves) + ".")
    if shows_product:
        parts.append("The product keeps exactly the same shape and color as in the first frame and stays clearly visible.")
    parts.append(MOTION_RULES)
    return " ".join(parts)
