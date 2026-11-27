"""훅 장면 프롬프트(규칙 목록형) → 자체 호스팅 모델이 따를 수 있는 영어 묘사. Claude(또는 Gemini Vertex)가 바꾼다.

- FLUX(첫 프레임): 보이는 것만 묘사한 한 문단. 2026-11-27 실측: 규칙 목록을 그대로 넣자 'RULES / FORBIDDEN'
  목록을 그림 속 깨진 글자로 그려 넣었다.
- MiniMax(이미지→영상): 움직임 위주의 영어 문단. 2026-11-27 실측: 장면 설명·제품 사실의 한글 문장을 넣자
  그 문장을 화면에 글자로 그려 자막과 겹쳤다. MiniMax 는 부정 프롬프트가 없어(CFG 증류) '넣지 않는 것'으로만 막는다.
"""

from __future__ import annotations

import re
from typing import Any, Optional

SYSTEM = """You turn a structured shot specification for a vertical short-video ad into ONE image caption for a text-to-image model (FLUX).

The image model draws every word it reads, so the caption must describe only what is visible:
- Write one paragraph of 70-140 English words, present tense, concrete and visual: subject, its pose and action, setting, composition, camera angle and framing, lighting, colors, materials, rendering style.
- Keep every requirement of the specification, but express it as something you can see. Examples: "keep the bottom third calm" -> "the lower third of the frame is open, empty deep-blue water"; "one vivid red accent for the key detail" -> name the one detail and say it is vivid red; "vertical 9:16, subject in the upper two thirds" -> say where the subject sits in the tall frame.
- Never mention rules, forbidden things, text, letters, subtitles, captions, logos, watermarks or brands, not even to exclude them. Never quote words from the specification. Do not write headings or lists.
- Never describe things that carry writing: labelled diagrams, arrows with words, charts, signs, screens, books, packaging print. Show an idea through real objects and their visible state instead (e.g. an arrow cycle "squeeze -> release -> refill" becomes the object visibly squeezed with droplets pushed out).
- Translate any Korean scene description into English.
- If a product must match reference photos, describe it as "the exact product shown in the reference image" plus its plain visible traits (shape, color), and keep it large and clear.
- If the specification says to keep the same character as a reference image, write "the same character as in the reference image".

Output only the caption."""

MOTION_SYSTEM = """You write the prompt for an image-to-video model that animates a given first frame into one continuous vertical clip of about 5 seconds.

The goal is lots of clear, continuous MOTION, not a still picture:
- Write one paragraph of 60-110 English words, present tense.
- Start from what the first frame already shows (same characters, objects, setting and look) and describe two or three continuous actions in order, with strong physical verbs (walks, bends, squeezes, swings, pours, splashes, spins, lifts).
- Add secondary motion that never stops: water splashing or dripping, cloth and hair moving, particles drifting, light shifting.
- Always include one camera move (slow push-in, orbit, tracking, tilt or crane). Never a locked-off static camera.
- Turn every explanation or change of state into an action you can watch (e.g. "cartilage absorbs fluid" -> "the knee bends and straightens again and again while glossy fluid pulses into the soft cushion").
- Never describe anything that carries writing: diagrams, labels, arrows, charts, signs, screens, books, packaging print. Never quote words. Never use the words text, letter, caption, subtitle, title, label, word or number.
- Sound: only the natural sound effects of the actions. No voices, no speech, no music.
- English only. Do not copy any non-English words from the specification.

Output only the prompt."""

# 영상 모델에 들어가면 안 되는 글자: 출력 가능한 ASCII 밖의 문자(한글 등). 대시·작은따옴표는 영어 문장에 흔해서 둔다.
_NON_ENGLISH = re.compile("[^ -~–—’]")


def _clean(text: str) -> str:
    text = (text or "").strip().strip('"').strip()
    if not text:
        raise RuntimeError("장면 묘사가 비어 있습니다.")
    return text


def ascii_only(text: str) -> str:
    """남은 비영문 글자와 큰따옴표를 지운다 (마지막 안전장치)."""
    cleaned = _NON_ENGLISH.sub(" ", text).replace('"', "")
    return " ".join(cleaned.split())


def _claude_text(client: Any, model: str, system: str, user: str, max_tokens: int) -> str:
    response = client.messages.create(
        model=model, max_tokens=max_tokens, system=system, messages=[{"role": "user", "content": user}]
    )
    if getattr(response, "stop_reason", None) == "refusal":
        raise RuntimeError("Claude 가 장면 묘사 변환을 거절했습니다.")
    return _clean("".join(b.text for b in response.content if getattr(b, "type", "") == "text"))


def claude_caption(spec: str, *, model: str = "claude-opus-5-5", client: Any = None) -> str:
    if client is None:
        import anthropic

        client = anthropic.Anthropic()  # ANTHROPIC_API_KEY
    return _claude_text(client, model, SYSTEM, spec, 1000)


def motion_prompt_for_video(spec: str, *, model: str = "claude-opus-5-5", client: Any = None) -> str:
    """장면 프롬프트 → 이미지→영상 모델(MiniMax)용 영어 움직임 묘사.

    한글·큰따옴표가 섞이면 한 번 다시 쓰게 하고, 그래도 남으면 지운다.
    """
    if client is None:
        import anthropic

        client = anthropic.Anthropic()
    text = _claude_text(client, model, MOTION_SYSTEM, spec, 800)
    if _NON_ENGLISH.search(text) or '"' in text:
        retry = spec + "\n\n(Your last answer contained non-English characters or quoted words. English only, no quotes.)"
        text = _claude_text(client, model, MOTION_SYSTEM, retry, 800)
    return ascii_only(text)


def gemini_caption(spec: str, settings: Any, *, model: Optional[str] = None) -> str:
    """settings 그대로 클라이언트를 만든다: GOOGLE_GENAI_USE_VERTEXAI=true 면 Vertex(WIF), 아니면 API 키."""
    from google.genai import types

    from app.genai_provider import build_genai_client

    client = build_genai_client(settings)  # 변수에 담아 둔다 (요청 도중 닫히지 않게)
    response = client.models.generate_content(
        model=model or str(getattr(settings, "body_llm", "") or "gemini-4-hydrogen"),
        contents=spec,
        config=types.GenerateContentConfig(system_instruction=SYSTEM),
    )
    return _clean(getattr(response, "text", "") or "")


def to_flux_caption(spec: str, *, provider: str = "claude", settings: Any = None, model: Optional[str] = None) -> str:
    """spec: 훅 파이프라인이 영상 모델에 주던 장면 프롬프트 그대로. provider: claude | gemini"""
    if provider == "gemini":
        return gemini_caption(spec, settings, model=model)
    return claude_caption(spec, model=model or "claude-opus-5-5")
