"""문제 장면 생성 영상: MiniMax (Hailuo, MiniMax-H3 계열. 글 또는 첫 프레임 이미지 → 영상).

호출은 MiniMax 영상 생성 V2 REST 이다 (작업 만들기 → 상태 조회 → 영상 내려받기). 초 단위로 과금된다.
  POST https://api.minimax.io/v2/video_generation            → {"task_id": …}
  GET  https://api.minimax.io/v2/query/video_generation/{id} → {"task": {"status": queued|running|succeeded|failed|cancelled, "content": {"url": …}}}

필요한 것:
  - MINIMAX_API_KEY         MiniMax 플랫폼의 API 키 (종량제 결제가 켜져 있어야 MiniMax-H3 계열을 쓸 수 있다)
  - 선택: C_MINIMAX_MODEL(기본 MiniMax-H3), C_MINIMAX_RESOLUTION(기본 768P), MINIMAX_API_BASE(기본 https://api.minimax.io)
          C_MINIMAX_AUDIO=1 이면 소리가 들어간 영상을 받는다 (기본은 무음. 훅 배경음에 섞인다)

Blender 소재를 넘기는 방식은 둘이고 한 요청에 섞을 수 없다 (MiniMax 규칙):
  - 첫 프레임(first_frame)   Blender 가 렌더한 정지 화면에서 그대로 이어지는 영상. 화면이 이미 완성된 장면에 쓴다.
  - 참조(reference_video)    Blender 블록아웃의 플레이블라스트를 구도·카메라·동작 타이밍의 참조로 주고 실사로 새로 그리게 한다.
                             블록아웃 템플릿(TEMPLATES 의 "blockout": True)은 이 방식이 기본이다.
프롬프트는 veo.PROMPTS 를 같이 쓴다. 같은 첫 프레임·프롬프트·설정이면 assets/cache/minimax/ 의 결과를 다시 써서 두 번 과금되지 않는다.
"""
from __future__ import annotations

import base64
import hashlib
import json
import math
import os
import time
import urllib.error
import urllib.request
from typing import Callable

from . import veo

DEFAULT_MODEL = "MiniMax-H3"
DEFAULT_BASE = "https://api.minimax.io"
MIN_SEC, MAX_SEC = 4, 15                      # MiniMax-H3 계열이 받는 길이(초). H3-Max 계열은 5초부터다.
AVOID = " Do not show any text, captions, subtitles, logos, watermarks or faces. No slow motion."
# 참조 영상은 회색 상자로 만든 블록아웃이다. 구도와 동작만 따르고 겉모습은 실사로 바꾸라고 알려 준다.
FOLLOW = (" Follow the camera angle, framing and the timing of the hand movement in reference video 1. The reference is a rough gray-box 3D blockout: "
          "do not copy its blocky look. Render it as photorealistic live-action footage with a real human hand, real materials and natural daylight.")
SOUND = " Natural room sound only: quiet ambience and the small sounds of the objects being handled. No music, no speech."
DONE = ("succeeded", "failed", "cancelled")


class MinimaxError(veo.VeoError):
    pass


def api_key() -> str:
    return os.environ.get("MINIMAX_API_KEY", "").strip()


def configured() -> bool:
    return bool(api_key())


def model() -> str:
    return os.environ.get("C_MINIMAX_MODEL", "").strip() or DEFAULT_MODEL


def resolution() -> str:
    return os.environ.get("C_MINIMAX_RESOLUTION", "").strip() or "768P"


def audio() -> bool:
    return os.environ.get("C_MINIMAX_AUDIO", "").strip().lower() in ("1", "true", "yes", "on")


def pick_duration(seconds: float) -> int:
    low = 5 if "H3-Max" in model() else MIN_SEC
    return max(low, min(MAX_SEC, math.ceil(seconds - 1e-6)))


def _base() -> str:
    return (os.environ.get("MINIMAX_API_BASE", "").strip() or DEFAULT_BASE).rstrip("/")


def _call(method: str, url: str, body: dict | None) -> dict:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={"Authorization": f"Bearer {api_key()}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        try:
            err = json.loads(raw).get("error") or {}
            message = err.get("message") or raw
        except ValueError:
            message = raw
        hint = {401: " (MINIMAX_API_KEY 를 확인하세요)", 402: " (MiniMax 계정 잔액이 부족합니다)", 429: " (요청 한도. 잠시 뒤 다시 시도하세요)"}.get(e.code, "")
        raise MinimaxError(f"MiniMax 요청 실패 {e.code}: {str(message)[:400]}{hint}") from e
    except urllib.error.URLError as e:
        raise MinimaxError(f"MiniMax 에 연결하지 못했습니다: {e.reason}") from e


def _data_uri(path: str, mime: str) -> str:
    with open(path, "rb") as f:
        return f"data:{mime};base64," + base64.b64encode(f.read()).decode("ascii")


def request_body(prompt: str, image_path: str | None, duration: int, reference_video: str | None = None) -> dict:
    text = prompt + (FOLLOW if reference_video else "") + (SOUND if audio() else "") + AVOID
    content: list[dict] = [{"type": "text", "text": text}]
    body: dict = {"model": model(), "content": content, "resolution": resolution(), "duration": duration, "generate_audio": audio()}
    image_mime = "image/png" if (image_path or "").lower().endswith(".png") else "image/jpeg"
    if reference_video:                                 # 블록아웃 플레이블라스트를 참조로. 첫 프레임과는 같이 쓸 수 없다
        content.append({"type": "video_url", "video_url": {"url": _data_uri(reference_video, "video/mp4")}, "role": "reference_video"})
        body["ratio"] = "9:16"                          # 블록아웃 정지 화면은 참조 이미지로 넣지 않는다 (회색 상자 겉모습을 따라 그릴 수 있다)
    elif image_path:                                    # 첫 프레임이 있으면 화면 비율은 그 이미지를 따른다 (Blender 첫 프레임은 9:16)
        content.append({"type": "image_url", "image_url": {"url": _data_uri(image_path, image_mime)}, "role": "first_frame"})
    else:
        body["ratio"] = "9:16"                          # 글만으로 만들 때는 세로 비율을 직접 정해야 한다
    return body


def cache_key(prompt: str, image_path: str | None, duration: int, reference_video: str | None = None) -> str:
    h = hashlib.sha256()
    h.update(open(image_path, "rb").read() if image_path else b"text-only")
    if reference_video:
        h.update(b"|reference|" + open(reference_video, "rb").read())
    h.update(f"|{prompt}|{model()}|{resolution()}|{duration}|{'audio' if audio() else 'silent'}".encode("utf-8"))
    return h.hexdigest()[:16]


def cached(cache_dir: str, template: str, image_path: str | None, seconds: float, reference_video: str | None = None) -> str | None:
    """이미 만들어 둔 영상이 있으면 그 경로. API 를 부르지 않는다. 더 긴 영상이 있으면 그 앞부분을 쓴다."""
    if template not in veo.PROMPTS or any(p and not os.path.exists(p) for p in (image_path, reference_video)):
        return None
    for duration in range(pick_duration(seconds), MAX_SEC + 1):
        path = os.path.join(cache_dir, f"{template}_{cache_key(veo.PROMPTS[template], image_path, duration, reference_video)}.mp4")
        if os.path.exists(path) and os.path.getsize(path) > 10000:
            return path
    return None


def generate(template: str, image_path: str | None, cache_dir: str, seconds: float, *, log: Callable[[str], None] = print,
             poll_sec: float = 8.0, timeout_sec: float = 900.0, reference_video: str | None = None) -> str:
    """문제 장면 영상(mp4)을 만들어 경로를 돌려준다. 과금되는 호출이다.

    reference_video 가 있으면 그 영상(Blender 플레이블라스트)의 구도·동작을 참조해 새로 그리고, 없고 image_path 가 있으면 그 첫 프레임에서 시작한다.
    """
    if template not in veo.PROMPTS:
        raise MinimaxError(f"이 템플릿에는 프롬프트가 없습니다: {template} (사용 가능: {', '.join(veo.PROMPTS)})")
    hit = cached(cache_dir, template, image_path, seconds, reference_video)          # 이미 만든 영상은 키가 없어도 쓴다
    if hit:
        return hit
    if not configured():
        raise MinimaxError("MINIMAX_API_KEY 가 없습니다. c/.env 에 MiniMax API 키를 넣으세요.")
    duration = pick_duration(seconds)
    prompt = veo.PROMPTS[template]
    how = "Blender 플레이블라스트 참조" if reference_video else ("Blender 첫 프레임" if image_path else "글만")
    log(f"MiniMax 로 문제 장면 생성 중 ({model()}, {resolution()}, {duration}초, {how}, {'소리 포함' if audio() else '무음'}, 과금) …")
    created = _call("POST", f"{_base()}/v2/video_generation", request_body(prompt, image_path, duration, reference_video))
    task_id = created.get("task_id")
    if not task_id:
        raise MinimaxError(f"작업 ID 를 받지 못했습니다: {json.dumps(created, ensure_ascii=False)[:300]}")
    started = time.time()
    task: dict = {}
    while True:
        task = _call("GET", f"{_base()}/v2/query/video_generation/{task_id}", None).get("task") or {}
        if task.get("status") in DONE:
            break
        if time.time() - started > timeout_sec:
            raise MinimaxError(f"MiniMax 생성이 {int(timeout_sec)}초 안에 끝나지 않았습니다 (작업: {task_id}).")
        time.sleep(poll_sec)
    if task.get("status") != "succeeded":
        err = task.get("error") or {}
        raise MinimaxError(f"MiniMax 생성 실패 ({task.get('status')}): {err.get('code', '')} {err.get('message', '')}".strip())
    url = (task.get("content") or {}).get("url")
    if not url:
        raise MinimaxError(f"결과에 영상 주소가 없습니다: {json.dumps(task, ensure_ascii=False)[:300]}")
    os.makedirs(cache_dir, exist_ok=True)
    path = os.path.join(cache_dir, f"{template}_{cache_key(prompt, image_path, duration, reference_video)}.mp4")
    try:                                              # 내려받기 주소는 서명된 주소다. API 키를 붙이지 않는다.
        with urllib.request.urlopen(urllib.request.Request(url), timeout=300) as resp, open(path + ".part", "wb") as out:
            while chunk := resp.read(1 << 16):
                out.write(chunk)
    except (urllib.error.URLError, OSError) as e:
        raise MinimaxError(f"만든 영상을 내려받지 못했습니다: {e}") from e
    os.replace(path + ".part", path)
    with open(os.path.splitext(path)[0] + ".json", "w", encoding="utf-8") as f:
        json.dump({"template": template, "model": model(), "resolution": resolution(), "duration_sec": duration, "task_id": task_id,
                   "input": "reference_video" if reference_video else ("first_frame" if image_path else "text"), "audio": audio(),
                   "usage": task.get("usage"), "prompt": prompt}, f, ensure_ascii=False, indent=2)
    log(f"MiniMax 영상 저장: {path} ({int(time.time() - started)}초 걸림)")
    return path
