"""문제 장면 생성 영상: Google Veo (Vertex AI, 이미지 → 영상).

Blender 가 렌더한 문제 장면의 첫 프레임을 Veo 에 넘겨, 그 구도 그대로 움직이는 영상을 받는다.
호출은 Vertex AI REST (predictLongRunning → fetchPredictOperation) 이고 초 단위로 과금된다.

필요한 것:
  - GOOGLE_CLOUD_PROJECT     Google Cloud 프로젝트 ID (결제 연결 + Vertex AI API 사용 설정)
  - 인증                      서비스 계정 키(GOOGLE_APPLICATION_CREDENTIALS) 또는 `gcloud auth application-default login`
  - 선택: GOOGLE_CLOUD_LOCATION(기본 us-central1), C_VEO_MODEL(기본 veo-3.1-fast-generate-001)
같은 첫 프레임·프롬프트·설정이면 assets/cache/veo/ 의 결과를 다시 써서 두 번 과금되지 않는다.
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

DEFAULT_MODEL = "veo-3.1-fast-generate-001"
DEFAULT_LOCATION = "us-central1"
DURATIONS = (4, 6, 8)                     # Veo 3.1 이 받는 길이(초)
SCOPE = "https://www.googleapis.com/auth/cloud-platform"

# 템플릿별 프롬프트. Veo 는 영어 프롬프트만 받는다. 첫 프레임(Blender)에 이미 있는 것에서 무엇이 움직이는지를 쓴다.
PROMPTS = {
    "spill_diffuser": (
        "Handheld smartphone footage, bright daylight living room, slightly shaky, casual and unpolished. "
        "A person's hand and forearm in a light sweater sleeve sweeps in from the side and accidentally knocks over "
        "the glass reed diffuser bottle on the wooden table. The bottle tips over onto its side, the reed sticks scatter, "
        "and amber liquid pours out of the bottle's neck and spreads into a puddle across the table. "
        "The camera stays on the fallen bottle and the growing puddle. Realistic physics, natural light."
    ),
    "cat_spill_diffuser": (
        "Handheld smartphone footage, bright daylight living room, slightly shaky, casual and unpolished. "
        "A fluffy grey tabby cat steps in from the right side of the frame, looks at the glass reed diffuser bottle on the wooden table, "
        "and deliberately bats it with one paw. The bottle tips over onto its side, the reed sticks scatter, "
        "and amber liquid pours out of the bottle neck and spreads into a puddle across the table. The cat calmly watches the mess. "
        "Realistic fur and physics, natural light, vertical video."
    ),
    "spray_panic": (
        "Handheld smartphone POV, bright daylight living room, frantic and comedic, casual and unpolished. "
        "A hand holding a pink aerosol air-freshener can rushes into the frame and sprays long bursts in every direction above the wooden table. "
        "A thick white mist quickly fills the room and hangs in the air. The camera shakes as if the person is in a hurry. "
        "Realistic, natural light, vertical video."
    ),
    "carry_drip": (
        "Handheld smartphone POV, bright daylight living room, casual and unpolished. "
        "A hand reaches in, picks up the glass reed diffuser bottle from the wooden table and carries it away while it tilts. "
        "Amber liquid dribbles out of the bottle neck and leaves a trail of drops and a small puddle across the table. "
        "Realistic physics, natural light, vertical video."
    ),
    "reed_flip": (
        "Close handheld smartphone footage, bright daylight living room, casual and unpolished. "
        "Two hands reach in, pull the reed sticks out of the glass diffuser bottle and flip them upside down. "
        "Amber oil drips from the wet ends of the sticks onto the fingers and onto the wooden table, leaving oily spots. "
        "The hand shakes off the oil in annoyance. Realistic, natural light, vertical video."
    ),
    "evaporate_diffuser": (
        "Time-lapse over several days, locked-off smartphone camera on a shelf, bright living room, casual and unpolished. "
        "A clear glass reed diffuser bottle on a wooden table, a strip of masking tape marks the original liquid level. "
        "The amber liquid inside steadily evaporates and its level sinks far below the tape until only a thin layer is left "
        "at the bottom, while the reed sticks dry out and turn pale. Sunlight and shadows sweep across the table as days pass. "
        "The bottle and the tape do not move. Realistic, natural light."
    ),
    "closet_musty": (
        "Handheld smartphone POV in a small bright bedroom on a humid rainy day, casual and unpolished phone footage. "
        "A white wardrobe door swings open toward the camera. Inside, clothes hang tightly packed on a rail. No people. "
        "A faint grey-green musty haze drifts out from between the clothes toward the camera, and the camera recoils slightly. "
        "Realistic, natural window light, vertical video."
    ),
    "phone_distract": "Handheld smartphone POV looking down at a bright tidy study desk in daylight, casual and unpolished phone footage. "
                      "An open notebook and a pen lie on the desk. A hand puts the pen down, picks up a smartphone lying next to the notebook "
                      "and starts scrolling with the thumb. The phone screen shows only soft blurred colorful shapes. The notebook stays untouched. "
                      "Realistic, natural window light, vertical video.",
    "drain_smell": (
        "Handheld smartphone POV stepping into a small tiled bathroom just as the light flickers on, casual and unpolished. "
        "Wavy, cartoonish yellow-green stink fumes rise from the round metal floor drain and drift upward. "
        "The camera flinches and pulls back from the smell, then holds on the drain. Bright, flat bathroom lighting."
    ),
}
NEGATIVE = "text, captions, subtitles, logos, watermark, brand names, faces, cartoon, slow motion"


class VeoError(RuntimeError):
    pass


def project() -> str:
    return (os.environ.get("GOOGLE_CLOUD_PROJECT") or os.environ.get("GCLOUD_PROJECT") or "").strip()


def configured() -> bool:
    """Veo 를 쓸 설정이 되어 있는가 (프로젝트 ID 가 있는가). 인증은 호출할 때 확인한다."""
    return bool(project())


def model() -> str:
    return os.environ.get("C_VEO_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL


def location() -> str:
    return os.environ.get("GOOGLE_CLOUD_LOCATION", DEFAULT_LOCATION).strip() or DEFAULT_LOCATION


def pick_duration(seconds: float) -> int:
    """장면 길이를 덮는 가장 짧은 Veo 길이."""
    return next((d for d in DURATIONS if d >= seconds - 1e-6), DURATIONS[-1])


def access_token() -> str:
    """Google Cloud 액세스 토큰. 토큰과 키는 출력하지 않는다."""
    token = os.environ.get("GOOGLE_ACCESS_TOKEN", "").strip()      # 예: gcloud auth print-access-token (1시간짜리)
    if token:
        return token
    try:
        import google.auth
        import google.auth.exceptions
        import google.auth.transport.requests
    except ImportError as e:
        raise VeoError("google-auth 가 없습니다. `pip install -r requirements.txt` 를 실행하세요.") from e
    try:
        creds, _ = google.auth.default(scopes=[SCOPE])
        creds.refresh(google.auth.transport.requests.Request())
    except google.auth.exceptions.GoogleAuthError as e:
        raise VeoError("Google Cloud 인증 정보를 찾지 못했습니다. 서비스 계정 키 경로를 GOOGLE_APPLICATION_CREDENTIALS 에 넣거나 "
                       f"`gcloud auth application-default login` 을 실행하세요. ({type(e).__name__})") from e
    return creds.token


def _endpoint(method: str) -> str:
    loc = location()
    host = "aiplatform.googleapis.com" if loc == "global" else f"{loc}-aiplatform.googleapis.com"
    return f"https://{host}/v1/projects/{project()}/locations/{loc}/publishers/google/models/{model()}:{method}"


def _post(url: str, body: dict, token: str) -> dict:
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"), method="POST",
                                 headers={"Authorization": "Bearer " + token, "Content-Type": "application/json; charset=utf-8"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")
        try:
            detail = json.loads(detail)["error"]["message"]
        except (ValueError, KeyError, TypeError):
            detail = detail[:300]
        hint = {401: " 인증이 만료됐거나 잘못됐습니다.",
                403: " 프로젝트에 결제 계정이 연결되어 있고 Vertex AI API 가 켜져 있는지, 계정에 Vertex AI 사용자 권한이 있는지 확인하세요.",
                404: " 모델 이름(C_VEO_MODEL)과 지역(GOOGLE_CLOUD_LOCATION)을 확인하세요.",
                429: " 할당량을 넘었습니다. 잠시 후 다시 실행하세요."}.get(e.code, "")
        raise VeoError(f"Vertex AI 오류 {e.code}: {detail}{hint}") from e
    except urllib.error.URLError as e:
        raise VeoError(f"Vertex AI 에 연결하지 못했습니다: {e.reason}") from e


def request_body(prompt: str, image_path: str | None, duration: int) -> dict:
    """image_path 가 None 이면 첫 프레임 없이 글만으로 만든다."""
    instance: dict = {"prompt": prompt}
    if image_path:
        with open(image_path, "rb") as f:
            instance["image"] = {"bytesBase64Encoded": base64.b64encode(f.read()).decode("ascii"),
                                 "mimeType": "image/png" if image_path.lower().endswith(".png") else "image/jpeg"}
    params = {"aspectRatio": "9:16", "durationSeconds": duration, "sampleCount": 1, "negativePrompt": NEGATIVE,
              "generateAudio": os.environ.get("C_VEO_AUDIO", "").strip() in ("1", "true", "yes")}
    if os.environ.get("C_VEO_RESOLUTION", "").strip():
        params["resolution"] = os.environ["C_VEO_RESOLUTION"].strip()        # 720p(기본) · 1080p
    return {"instances": [instance], "parameters": params}


def cache_key(prompt: str, image_path: str | None, duration: int) -> str:
    h = hashlib.sha256()
    h.update(open(image_path, "rb").read() if image_path else b"text-only")
    h.update(json.dumps([prompt, NEGATIVE, model(), duration, os.environ.get("C_VEO_RESOLUTION", ""),
                         os.environ.get("C_VEO_AUDIO", "")]).encode("utf-8"))
    return h.hexdigest()[:16]


def cached(cache_dir: str, template: str, image_path: str | None, seconds: float) -> str | None:
    """이미 만들어 둔 영상이 있으면 그 경로. API 를 부르지 않는다."""
    if template not in PROMPTS or (image_path and not os.path.exists(image_path)):
        return None
    path = os.path.join(cache_dir, f"{template}_{cache_key(PROMPTS[template], image_path, pick_duration(seconds))}.mp4")
    return path if os.path.exists(path) and os.path.getsize(path) > 10000 else None


def generate(template: str, image_path: str | None, cache_dir: str, seconds: float, *, log: Callable[[str], None] = print,
             poll_sec: float = 10.0, timeout_sec: float = 900.0) -> str:
    """첫 프레임 image_path 에서 시작하는 문제 장면 영상(mp4)을 만들어 경로를 돌려준다. 과금되는 호출이다."""
    if template not in PROMPTS:
        raise VeoError(f"이 템플릿에는 Veo 프롬프트가 없습니다: {template} (사용 가능: {', '.join(PROMPTS)})")
    if not configured():
        raise VeoError("GOOGLE_CLOUD_PROJECT 가 없습니다. c/.env 에 Google Cloud 프로젝트 ID 를 넣으세요.")
    hit = cached(cache_dir, template, image_path, seconds)
    if hit:
        return hit
    duration = pick_duration(seconds)
    prompt = PROMPTS[template]
    token = access_token()
    log(f"Veo 로 문제 장면 생성 중 ({model()}, {duration}초, 과금) …")
    op = _post(_endpoint("predictLongRunning"), request_body(prompt, image_path, duration), token)
    name = op.get("name")
    if not name:
        raise VeoError(f"작업 이름을 받지 못했습니다: {json.dumps(op, ensure_ascii=False)[:300]}")
    started = time.time()
    while not op.get("done"):
        if time.time() - started > timeout_sec:
            raise VeoError(f"Veo 생성이 {int(timeout_sec)}초 안에 끝나지 않았습니다 (작업: {name}).")
        time.sleep(poll_sec)
        op = _post(_endpoint("fetchPredictOperation"), {"operationName": name}, token)
    if op.get("error"):
        raise VeoError(f"Veo 생성 실패: {op['error'].get('message', op['error'])}")
    res = op.get("response") or {}
    videos = res.get("videos") or []
    if not videos:
        reasons = "; ".join(str(r) for r in res.get("raiMediaFilteredReasons") or [])
        raise VeoError("Veo 가 영상을 돌려주지 않았습니다" + (f" (안전 필터: {reasons})" if reasons else
                                                    f" (필터된 수 {res.get('raiMediaFilteredCount', 0)})") + ".")
    data = videos[0].get("bytesBase64Encoded")
    if not data:
        raise VeoError(f"응답에 영상 데이터가 없습니다 (gcsUri: {videos[0].get('gcsUri')}). storageUri 없이 호출해야 합니다.")
    os.makedirs(cache_dir, exist_ok=True)
    path = os.path.join(cache_dir, f"{template}_{cache_key(prompt, image_path, duration)}.mp4")
    with open(path, "wb") as f:
        f.write(base64.b64decode(data))
    json.dump({"template": template, "model": model(), "duration_sec": duration, "prompt": prompt, "operation": name,
               "seconds_waited": round(time.time() - started, 1)},
              open(path[:-4] + ".json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    log(f"  Veo 완료 ({time.time() - started:.0f}초) → {os.path.relpath(path)}")
    return path
