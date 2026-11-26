"""문제 장면 생성 영상: Google Gemini Omni (Vertex AI Interactions API, 이미지 → 영상).

Blender 가 렌더한 문제 장면의 첫 프레임을 Omni 에 넘겨, 그 구도 그대로 움직이는 영상을 받는다.
Veo(veo.py)와 달리 3~15초를 1초 단위로 만들 수 있어 10초 훅을 한 번에 생성한다.

호출: POST https://aiplatform.googleapis.com/v1beta1/projects/{프로젝트}/locations/global/interactions  (background 로 접수)
      GET  …/interactions/{id} 로 끝날 때까지 확인 → steps 안의 video(data: base64) 를 저장
인증과 프로젝트 설정은 veo.py 와 같다 (GOOGLE_CLOUD_PROJECT + 서비스 계정 키 또는 gcloud 로그인).
선택: C_OMNI_MODEL(기본 gemini-omni-1.2-flash), C_OMNI_RESOLUTION(기본 720p), C_OMNI_API_VERSION(기본 v1beta1)

확인하지 못한 점: 공식 Vertex 예시는 입력 이미지를 Cloud Storage 주소(gs://)로만 보여 준다. 여기서는 스키마에 있는
인라인 방식(data: base64)으로 보낸다. 거절되면 오류 메시지에 그 사실이 나온다.
같은 첫 프레임·프롬프트·설정이면 assets/cache/omni/ 의 결과를 다시 써서 두 번 과금되지 않는다.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import time
import urllib.error
import urllib.request
from typing import Callable

from . import veo

DEFAULT_MODEL = "gemini-omni-1.2-flash"
MIN_SEC, MAX_SEC = 3, 15
# Omni 는 negative prompt 를 받지 않아 프롬프트 끝에 하지 말 것을 문장으로 붙인다.
AVOID = " Do not show any text, captions, subtitles, logos, watermarks or faces. No slow motion."
DONE = ("completed", "failed", "cancelled", "incomplete")


class OmniError(veo.VeoError):
    pass


def configured() -> bool:
    return veo.configured()


def model() -> str:
    return os.environ.get("C_OMNI_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL


def resolution() -> str:
    return os.environ.get("C_OMNI_RESOLUTION", "720p").strip() or "720p"


def pick_duration(seconds: float) -> int:
    """장면 길이를 덮는 정수 초 (3~15)."""
    return max(MIN_SEC, min(MAX_SEC, int(-(-float(seconds) // 1))))


def _base() -> str:
    version = os.environ.get("C_OMNI_API_VERSION", "v1beta1").strip() or "v1beta1"
    return f"https://aiplatform.googleapis.com/{version}/projects/{veo.project()}/locations/global/interactions"


def _call(method: str, url: str, body: dict | None, token: str) -> dict:
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={"Authorization": "Bearer " + token, "Content-Type": "application/json; charset=utf-8"})
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")
        try:
            parsed = json.loads(detail)
            parsed = parsed[0] if isinstance(parsed, list) else parsed      # 이 주소는 오류를 배열로 감싸 돌려준다
            detail = parsed["error"]["message"]
        except (ValueError, KeyError, TypeError, IndexError):
            detail = detail[:400]
        hint = {400: " 요청 형식이 거절됐습니다. 입력 이미지를 인라인으로 받지 않는 경우일 수 있습니다 (공식 예시는 gs:// 주소만 보여 줍니다).",
                401: " 인증이 만료됐거나 잘못됐습니다.",
                403: " 프로젝트에 결제 계정이 연결되어 있고 Vertex AI(Agent Platform) API 가 켜져 있는지, 계정에 사용 권한이 있는지 확인하세요.",
                404: " 모델 이름(C_OMNI_MODEL)이나 API 버전(C_OMNI_API_VERSION)을 확인하세요.",
                429: " 할당량을 넘었습니다. 잠시 후 다시 실행하세요."}.get(e.code, "")
        raise OmniError(f"Gemini Omni 오류 {e.code}: {detail}{hint}") from e
    except urllib.error.URLError as e:
        raise OmniError(f"Gemini Omni 에 연결하지 못했습니다: {e.reason}") from e


def request_body(prompt: str, image_path: str | None, duration: int) -> dict:
    """image_path 가 있으면 그 프레임에서 시작하는 영상(image_to_video), 없으면 글만으로 만든다(text_to_video)."""
    items = [{"type": "text", "text": prompt + AVOID}]
    if image_path:
        mime = "image/png" if image_path.lower().endswith(".png") else "image/jpeg"
        with open(image_path, "rb") as f:
            items.append({"type": "image", "data": base64.b64encode(f.read()).decode("ascii"), "mime_type": mime})
    return {
        "model": model(),
        "background": True,                      # 접수만 하고 끝날 때까지 따로 확인한다 (생성에 1분 넘게 걸린다)
        "input": items,
        "response_format": [{"type": "video", "delivery": "inline", "aspect_ratio": "9:16", "resolution": resolution(),
                             "duration": f"{duration}s"}],
        "generation_config": {"video_config": {"task": "image_to_video" if image_path else "text_to_video"}},
    }


def find_video(node) -> dict | None:
    """응답 어디에 있든 type 이 video 인 항목을 찾는다 (steps → model_output → content 안에 들어 있다)."""
    if isinstance(node, dict):
        if node.get("type") == "video" and (node.get("data") or node.get("uri")):
            return node
        for v in node.values():
            hit = find_video(v)
            if hit:
                return hit
    elif isinstance(node, list):
        for v in node:
            hit = find_video(v)
            if hit:
                return hit
    return None


def cache_key(prompt: str, image_path: str | None, duration: int) -> str:
    h = hashlib.sha256()
    h.update(open(image_path, "rb").read() if image_path else b"text-only")
    h.update(json.dumps([prompt, AVOID, model(), duration, resolution()]).encode("utf-8"))
    return h.hexdigest()[:16]


def cached(cache_dir: str, template: str, image_path: str | None, seconds: float) -> str | None:
    """이미 만들어 둔 영상이 있으면 그 경로. API 를 부르지 않는다."""
    if template not in veo.PROMPTS or (image_path and not os.path.exists(image_path)):
        return None
    need = pick_duration(seconds)
    for duration in range(need, MAX_SEC + 1):      # 더 긴 영상이 이미 있으면 다시 만들지 않고 그 앞부분을 쓴다
        path = os.path.join(cache_dir, f"{template}_{cache_key(veo.PROMPTS[template], image_path, duration)}.mp4")
        if os.path.exists(path) and os.path.getsize(path) > 10000:
            return path
    return None


def generate(template: str, image_path: str | None, cache_dir: str, seconds: float, *, log: Callable[[str], None] = print,
             poll_sec: float = 8.0, timeout_sec: float = 900.0) -> str:
    """첫 프레임 image_path 에서 시작하는 문제 장면 영상(mp4)을 만들어 경로를 돌려준다. 과금되는 호출이다."""
    if template not in veo.PROMPTS:
        raise OmniError(f"이 템플릿에는 프롬프트가 없습니다: {template} (사용 가능: {', '.join(veo.PROMPTS)})")
    if not configured():
        raise OmniError("GOOGLE_CLOUD_PROJECT 가 없습니다. c/.env 에 Google Cloud 프로젝트 ID 를 넣으세요.")
    hit = cached(cache_dir, template, image_path, seconds)
    if hit:
        return hit
    duration = pick_duration(seconds)
    prompt = veo.PROMPTS[template]
    token = veo.access_token()
    log(f"Gemini Omni 로 문제 장면 생성 중 ({model()}, {duration}초, 과금) …")
    started = time.time()
    for attempt in range(1, 4):
        op = _call("POST", _base(), request_body(prompt, image_path, duration), token)
        while op.get("status") not in DONE:
            name = op.get("id")
            if not name:
                raise OmniError(f"작업 ID 를 받지 못했습니다: {json.dumps(op, ensure_ascii=False)[:300]}")
            if time.time() - started > timeout_sec:
                raise OmniError(f"Omni 생성이 {int(timeout_sec)}초 안에 끝나지 않았습니다 (작업: {name}).")
            time.sleep(poll_sec)
            op = _call("GET", f"{_base()}/{name}", None, token)
        # 같은 요청이 "유료 결제 계정이 필요하다"로 실패했다가 다시 보내면 통과하는 일이 있었다. 그 오류만 두 번까지 다시 보낸다.
        denied = any(isinstance(e, dict) and e.get("code") == "permission_denied" for e in op.get("errors") or [])
        if op.get("status") == "completed" or not denied or attempt == 3:
            break
        log(f"  결제 계정 조건으로 거절됨, 다시 시도 ({attempt}/2)")
        time.sleep(min(poll_sec, 5))
    if op.get("status") != "completed":
        errors = "; ".join(str(e.get("message", e)) if isinstance(e, dict) else str(e) for e in op.get("errors") or [])
        raise OmniError(f"Omni 생성이 끝나지 못했습니다 (상태: {op.get('status')})" + (f": {errors}" if errors else
                        ". 안전 정책에 걸렸을 수 있습니다.") )
    video = find_video(op.get("steps") or op)
    if not video:
        raise OmniError("응답에 영상이 없습니다. 안전 정책에 걸렸을 수 있습니다.")
    if not video.get("data"):
        raise OmniError(f"영상이 파일이 아니라 주소로 왔습니다 ({video.get('uri')}). delivery 를 inline 으로 요청해야 합니다.")
    os.makedirs(cache_dir, exist_ok=True)
    path = os.path.join(cache_dir, f"{template}_{cache_key(prompt, image_path, duration)}.mp4")
    with open(path, "wb") as f:
        f.write(base64.b64decode(video["data"]))
    json.dump({"template": template, "model": model(), "duration_sec": duration, "resolution": resolution(), "prompt": prompt + AVOID,
               "interaction": op.get("id"), "seconds_waited": round(time.time() - started, 1), "usage": op.get("usage")},
              open(path[:-4] + ".json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    log(f"  Omni 완료 ({time.time() - started:.0f}초) → {os.path.relpath(path)}")
    return path
