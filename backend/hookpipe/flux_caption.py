"""훅 장면 프롬프트(규칙 목록형) → FLUX 가 그릴 수 있는 장면 묘사 한 문단. Claude 또는 Gemini(Vertex) 가 바꾼다.

2026-11-27 실측: 같은 규칙 목록을 FLUX klein(보강 모델 끔)에 그대로 넣자 'RULES / FORBIDDEN' 목록을
그림 속 깨진 글자로 그려 넣었다. FLUX 는 '보이는 것'만 묘사한 문장을 그림으로 바꾼다.
"""

from __future__ import annotations

from typing import Any, Optional

SYSTEM = """You turn a structured shot specification for a vertical short-video ad into ONE image caption for a text-to-image model (FLUX).

The image model draws every word it reads, so the caption must describe only what is visible:
- Write one paragraph of 70-140 English words, present tense, concrete and visual: subject, its pose and action, setting, composition, camera angle and framing, lighting, colors, materials, rendering style.
- Keep every requirement of the specification, but express it as something you can see. Examples: "keep the bottom third calm" -> "the lower third of the frame is open, empty deep-blue water"; "one vivid red accent for the key detail" -> name the one detail and say it is vivid red; "vertical 9:16, subject in the upper two thirds" -> say where the subject sits in the tall frame.
- Never mention rules, forbidden things, text, letters, subtitles, captions, logos, watermarks or brands, not even to exclude them. Never quote words from the specification. Do not write headings or lists.
- Translate any Korean scene description into English.
- If a product must match reference photos, describe it as "the exact product shown in the reference image" plus its plain visible traits (shape, color), and keep it large and clear.
- If the specification says to keep the same character as a reference image, write "the same character as in the reference image".

Output only the caption."""


def _clean(text: str) -> str:
    text = (text or "").strip().strip('"').strip()
    if not text:
        raise RuntimeError("장면 묘사가 비어 있습니다.")
    return text


def claude_caption(spec: str, *, model: str = "claude-opus-5-5", client: Any = None) -> str:
    if client is None:
        import anthropic

        client = anthropic.Anthropic()  # ANTHROPIC_API_KEY
    response = client.messages.create(
        model=model, max_tokens=1000, system=SYSTEM, messages=[{"role": "user", "content": spec}]
    )
    if getattr(response, "stop_reason", None) == "refusal":
        raise RuntimeError("Claude 가 장면 묘사 변환을 거절했습니다.")
    return _clean("".join(b.text for b in response.content if getattr(b, "type", "") == "text"))


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
