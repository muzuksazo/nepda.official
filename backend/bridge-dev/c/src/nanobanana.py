"""문제 장면 첫 프레임 다듬기: Google Nano Banana (Gemini 이미지 모델, 이미지 + 글 → 이미지).

Blender 블록아웃 화면을 같은 구도의 실사 사진으로 바꿔, Veo·Omni 에 넘길 첫 프레임으로 쓴다.
호출은 Vertex AI REST 의 generateContent 이고 (한 번에 응답이 온다) 장당 과금된다. 이 모델은 Interactions API 로는 받지 않는다 ("not supported" 로 거절됨).
인증과 프로젝트 설정은 veo.py 와 같다. 선택: C_IMAGE_MODEL(기본 gemini-nano-banana-2.1).
같은 입력 이미지·프롬프트·모델이면 저장해 둔 결과를 다시 쓴다.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import time
from typing import Callable

from . import omni, veo

DEFAULT_MODEL = "gemini-nano-banana-2.1"


# 블록아웃 템플릿별 실사화 지시. 구도와 배치는 그대로 두고 겉모습만 바꾸게 한다.
REFINE = {
    "phone_distract_blockout": (
        "Turn this rough gray-box 3D blockout into a photorealistic photo taken with a smartphone, keeping exactly the same camera angle, framing and layout. "
        "A light oak study desk in natural daylight. An open paper notebook with a few handwritten lines on the left page, a blue pen, "
        "a smartphone with a dark screen lying to the right of the notebook, a silver laptop and a white ceramic mug at the back, a plain white wall. "
        "A real human right hand in a cream knit sweater sleeve rests on the notebook where the blocky hand is. "
        "Realistic materials, soft shadows, shallow depth of field. No text overlays, no logos, no faces."
    ),
}


class ImageError(veo.VeoError):
    pass


def model() -> str:
    return os.environ.get("C_IMAGE_MODEL", "").strip() or DEFAULT_MODEL


def _endpoint() -> str:
    loc = os.environ.get("C_IMAGE_LOCATION", "").strip() or "global"
    host = "aiplatform.googleapis.com" if loc == "global" else f"{loc}-aiplatform.googleapis.com"
    return f"https://{host}/v1/projects/{veo.project()}/locations/{loc}/publishers/google/models/{model()}:generateContent"


def request_body(prompt: str, image_path: str | None) -> dict:
    parts: list[dict] = [{"text": prompt}]
    if image_path:
        mime = "image/png" if image_path.lower().endswith(".png") else "image/jpeg"
        with open(image_path, "rb") as f:
            parts.append({"inlineData": {"mimeType": mime, "data": base64.b64encode(f.read()).decode("ascii")}})
    return {"contents": [{"role": "user", "parts": parts}],
            "generationConfig": {"responseModalities": ["TEXT", "IMAGE"], "imageConfig": {"aspectRatio": "9:16"}}}


def find_image(node) -> dict | None:
    """응답 어디에 있든 이미지 데이터(inlineData)를 찾는다."""
    if isinstance(node, dict):
        inline = node.get("inlineData") or node.get("inline_data")
        if isinstance(inline, dict) and inline.get("data"):
            return inline
        for v in node.values():
            hit = find_image(v)
            if hit:
                return hit
    elif isinstance(node, list):
        for v in node:
            hit = find_image(v)
            if hit:
                return hit
    return None


def cache_path(prompt: str, image_path: str | None, cache_dir: str, name: str) -> str:
    h = hashlib.sha256()
    h.update(open(image_path, "rb").read() if image_path else b"text-only")
    h.update(f"|{prompt}|{model()}".encode("utf-8"))
    return os.path.join(cache_dir, f"{name}_{h.hexdigest()[:16]}.jpg")


def cached(prompt: str, image_path: str | None, cache_dir: str, name: str) -> str | None:
    """이미 만들어 둔 이미지가 있으면 그 경로. API 를 부르지 않는다."""
    if image_path and not os.path.exists(image_path):
        return None
    path = cache_path(prompt, image_path, cache_dir, name)
    return path if os.path.exists(path) and os.path.getsize(path) > 10000 else None


def generate(prompt: str, image_path: str | None, cache_dir: str, name: str, *, log: Callable[[str], None] = print) -> str:
    """이미지(jpg)를 만들어 경로를 돌려준다. image_path 가 있으면 그 화면을 고쳐 그린다. 과금되는 호출이다."""
    path = cache_path(prompt, image_path, cache_dir, name)
    if os.path.exists(path) and os.path.getsize(path) > 10000:
        return path
    if not veo.configured():
        raise ImageError("GOOGLE_CLOUD_PROJECT 가 없습니다. c/.env 에 Google Cloud 프로젝트 ID 를 넣으세요.")
    log(f"Nano Banana 로 첫 프레임 생성 중 ({model()}, 과금) …")
    started = time.time()
    try:
        out = omni._call("POST", _endpoint(), request_body(prompt, image_path), veo.access_token())
    except veo.VeoError as e:
        raise ImageError(str(e).replace("Gemini Omni", "Nano Banana")) from e
    image = find_image(out)
    if not image:
        raise ImageError(f"응답에 이미지가 없습니다: {json.dumps(out, ensure_ascii=False)[:300]}")
    os.makedirs(cache_dir, exist_ok=True)
    with open(path, "wb") as f:
        f.write(base64.b64decode(image["data"]))
    json.dump({"name": name, "model": model(), "prompt": prompt, "response_id": out.get("responseId"), "seconds_waited": round(time.time() - started, 1),
               "usage": out.get("usageMetadata")}, open(path[:-4] + ".json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    log(f"  Nano Banana 완료 ({time.time() - started:.0f}초) → {os.path.relpath(path)}")
    return path
