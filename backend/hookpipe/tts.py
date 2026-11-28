"""나레이션 공급자 선택. 기본은 Gemini TTS(GenAIMediaProvider), TTS_PROVIDER=inworld 면 Inworld TTS.

Inworld 요청 모양은 C 트랙(bridge-dev/c/src/tts.py)과 B 트랙(b/src/tts-inworld.ts)이 실제로 쓰던 것과 같다.
키는 설정(INWORLD_API_KEY)에서만 읽고 출력하지 않는다.
"""

from __future__ import annotations

import base64
import json
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Optional

INWORLD_URL = "https://api.inworld.ai/tts/v1/voice"


class TtsError(RuntimeError):
    """나레이션을 만들지 못했을 때."""


class InworldTts:
    """GenAIMediaProvider.generate_tts_beat 와 같은 이름·인자로 부를 수 있는 Inworld TTS."""

    extension = ".mp3"

    def __init__(self, settings: Any) -> None:
        self.key = str(getattr(settings, "inworld_api_key", "") or "").strip()
        self.default_voice = str(getattr(settings, "inworld_voice_id", "") or "").strip()
        self.model = str(getattr(settings, "inworld_model", "") or "inworld-tts-2")
        self.rate = float(getattr(settings, "inworld_speaking_rate", 1.1) or 1.1)
        # /renders 의 기본 목소리(Kore 등 Gemini 목소리 이름)가 오면 Inworld 기본 목소리로 바꾼다
        self.gemini_default_voice = str(getattr(settings, "tts_default_voice", "") or "")
        if not self.key:
            raise TtsError("INWORLD_API_KEY 가 없습니다 (TTS_PROVIDER=inworld).")
        if not self.default_voice:
            raise TtsError("INWORLD_VOICE_ID 가 없습니다 (TTS_PROVIDER=inworld).")

    @property
    def label(self) -> str:
        return f"inworld:{self.model}:{self.rate}"

    def voice_for(self, voice: Optional[str]) -> str:
        if not voice or voice == self.gemini_default_voice:
            return self.default_voice
        return voice

    def generate_tts_beat(self, text: str, out_path: str | Path, *, voice_name: Optional[str] = None, **_: Any) -> None:
        body = {
            "text": text,
            "voiceId": self.voice_for(voice_name),
            "modelId": self.model,
            "audioConfig": {"audioEncoding": "MP3", "speakingRate": self.rate},
        }
        request = urllib.request.Request(
            INWORLD_URL,
            data=json.dumps(body).encode("utf-8"),
            method="POST",
            headers={"Authorization": "Basic " + self.key, "Content-Type": "application/json"},
        )
        last: Optional[Exception] = None
        for attempt in range(3):  # 429·5xx 는 잠깐 쉬고 다시
            try:
                with urllib.request.urlopen(request, timeout=120) as resp:
                    data = json.load(resp)
                break
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode("utf-8", "replace")[:300]
                last = TtsError(f"Inworld TTS 오류 {exc.code}: {detail}")
                if exc.code != 429 and exc.code < 500:
                    raise last from exc
            except urllib.error.URLError as exc:
                last = TtsError(f"Inworld TTS 에 연결하지 못했습니다: {exc.reason}")
            time.sleep(2 * (attempt + 1))
        else:
            raise last or TtsError("Inworld TTS 응답이 없습니다.")
        audio = data.get("audioContent")
        if not audio:
            raise TtsError("Inworld TTS 응답에 음성이 없습니다.")
        target = Path(out_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_suffix(target.suffix + ".part")
        tmp.write_bytes(base64.b64decode(audio))
        tmp.replace(target)


class MediaWithTts:
    """영상·이미지는 원래 공급자, 나레이션만 다른 공급자로 보내는 묶음."""

    def __init__(self, media: Any, tts: Any) -> None:
        self._media = media
        self._tts = tts
        self.tts_extension = getattr(tts, "extension", ".wav")
        self.tts_label = getattr(tts, "label", "")

    def generate_tts_beat(self, *args: Any, **kwargs: Any) -> Any:
        return self._tts.generate_tts_beat(*args, **kwargs)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._media, name)
