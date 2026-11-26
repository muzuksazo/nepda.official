"""나레이션 음성. Inworld TTS (비스트리밍, 단어별 타임스탬프 포함).

키는 환경변수 INWORLD_API_KEY 에서만 읽고 출력하지 않는다. 목소리는 요청의 tts.voice → C_TTS_VOICE → 기본값 순.
"""
from __future__ import annotations

import base64
import json
import os
import urllib.error
import urllib.request

URL = "https://api.inworld.ai/tts/v1/voice"
DEFAULT_MODEL = "inworld-tts-2"
DEFAULT_VOICE = "scarlet-mango-0605__gangsangyun"


class TtsError(RuntimeError):
    pass


def available() -> bool:
    return bool(os.environ.get("INWORLD_API_KEY", "").strip())


def default_voice() -> str:
    return os.environ.get("C_TTS_VOICE", DEFAULT_VOICE)


def synthesize(text: str, mp3_path: str, voice: str | None = None) -> list[tuple[str, float, float]]:
    """text 를 mp3 로 저장하고 [(단어, 시작초, 끝초)] 를 돌려준다. 같은 경로에 캐시(.json)가 있으면 다시 부르지 않는다."""
    meta_path = mp3_path[:-4] + ".json"
    voice = voice or default_voice()
    if os.path.exists(mp3_path) and os.path.exists(meta_path):
        meta = json.load(open(meta_path, encoding="utf-8"))
        if meta.get("text") == text and meta.get("voice") == voice:
            return [tuple(w) for w in meta["words"]]
    key = os.environ.get("INWORLD_API_KEY", "").strip()
    if not key:
        raise TtsError("INWORLD_API_KEY 가 없습니다. c/.env 에 넣거나 --no-tts 로 음성 없이 실행하세요.")
    body = {"text": text, "voiceId": voice, "modelId": os.environ.get("C_TTS_MODEL", DEFAULT_MODEL), "timestampType": "WORD",
            "audioConfig": {"speakingRate": 1}, "deliveryMode": "BALANCED"}
    req = urllib.request.Request(URL, data=json.dumps(body).encode("utf-8"), method="POST",
                                 headers={"Authorization": "Basic " + key, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            data = json.load(r)
    except urllib.error.HTTPError as e:
        raise TtsError(f"Inworld TTS 오류 {e.code}: {e.read().decode('utf-8', 'replace')[:300]}") from e
    except urllib.error.URLError as e:
        raise TtsError(f"Inworld TTS 에 연결하지 못했습니다: {e.reason}") from e
    with open(mp3_path, "wb") as f:
        f.write(base64.b64decode(data["audioContent"]))
    wa = (data.get("timestampInfo") or {}).get("wordAlignment") or {}
    words: list[list] = []
    for w, s, e in zip(wa.get("words", []), wa.get("wordStartTimeSeconds", []), wa.get("wordEndTimeSeconds", [])):
        w = w.strip()
        if not w:
            continue
        if words and all(ch in ",.?!…" for ch in w):      # 문장부호는 앞 단어에 붙인다
            words[-1][0] += w
            words[-1][2] = e
        else:
            words.append([w, s, e])
    json.dump({"text": text, "voice": voice, "words": words}, open(meta_path, "w", encoding="utf-8"), ensure_ascii=False)
    return [tuple(w) for w in words]
