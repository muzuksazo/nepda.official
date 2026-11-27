"""FR-011 shared Korean TTS service (Inworld TTS primary + Gemini TTS fallback) & -14 LUFS mastering."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import subprocess
import wave
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol, Sequence

import httpx
import numpy as np

from .config import Settings
from .genai_provider import GenAIMediaProvider

INWORLD_TTS_URL = "https://api.inworld.ai/tts/v1/voice"
TARGET_LUFS = -14.0
TARGET_SR = 48000
TARGET_CH = 2


class TTSError(RuntimeError):
    """Raised when TTS synthesis or audio mastering fails."""


@dataclass(frozen=True)
class WordTiming:
    word: str
    start_sec: float
    end_sec: float


@dataclass(frozen=True)
class TTSAudioResult:
    audio_path: Path
    duration_sec: float
    words: List[WordTiming]
    provider: str
    voice_id: str
    model_id: str
    cached: bool = False


class TTSProvider(Protocol):
    def synthesize(
        self,
        text: str,
        out_wav_path: Path,
        *,
        voice_id: Optional[str] = None,
        speaking_rate: Optional[float] = None,
    ) -> TTSAudioResult: ...


def _wav_duration(path: Path) -> float:
    with wave.open(str(path), "rb") as wf:
        frames = wf.getnframes()
        rate = wf.getframerate() or 1
        return float(frames) / float(rate)


def _trim_wav_silence(raw_wav: bytes, *, threshold: int = 400, keep_sec: float = 0.08) -> tuple[bytes, float]:
    """Trim leading/trailing silence from 16-bit PCM WAV bytes; return (trimmed_wav_bytes, start_trim_sec)."""
    if len(raw_wav) < 44 or raw_wav[:4] != b"RIFF":
        raise TTSError("Expected RIFF WAV bytes from TTS provider")

    import io

    with wave.open(io.BytesIO(raw_wav), "rb") as wf:
        ch = wf.getnchannels()
        sw = wf.getsampwidth()
        rate = wf.getframerate()
        frames_bytes = wf.readframes(wf.getnframes())

    if sw != 2 or not frames_bytes:
        return raw_wav, 0.0

    arr = np.frombuffer(frames_bytes, dtype="<i2").reshape((-1, ch))
    n = arr.shape[0]
    amp = np.max(np.abs(arr), axis=1)
    active = np.flatnonzero(amp > threshold)
    if len(active) == 0:
        return raw_wav, 0.0

    keep = int(round(keep_sec * rate))
    start_idx = max(0, int(active[0]) - keep)
    end_idx = min(n, int(active[-1]) + 1 + keep)
    trimmed = arr[start_idx:end_idx]

    out_buf = io.BytesIO()
    with wave.open(out_buf, "wb") as wf_out:
        wf_out.setnchannels(ch)
        wf_out.setsampwidth(2)
        wf_out.setframerate(rate)
        wf_out.writeframes(trimmed.tobytes())
    return out_buf.getvalue(), round(start_idx / float(rate), 4)


def _parse_word_alignment(
    word_alignment: Dict[str, Any],
    *,
    trim_offset_sec: float = 0.0,
) -> List[WordTiming]:
    words_raw = word_alignment.get("words") or []
    starts = word_alignment.get("wordStartTimeSeconds") or []
    ends = word_alignment.get("wordEndTimeSeconds") or []
    merged: List[List[Any]] = []
    for w, s, e in zip(words_raw, starts, ends):
        token = str(w).strip()
        if not token:
            continue
        st = max(0.0, round(float(s) - trim_offset_sec, 3))
        en = max(st, round(float(e) - trim_offset_sec, 3))
        if merged and all(ch in ",.?!…~" for ch in token):
            merged[-1][0] += token
            merged[-1][2] = max(merged[-1][2], en)
        else:
            merged.append([token, st, en])
    return [WordTiming(word=m[0], start_sec=m[1], end_sec=m[2]) for m in merged]


class InworldTTSProvider:
    """Inworld TTS v1 client (`inworld-tts-2`, speakingRate 1.1, WORD timestamps)."""

    def __init__(
        self,
        settings: Settings,
        *,
        api_key: Optional[str] = None,
        default_voice: Optional[str] = None,
        model_id: Optional[str] = None,
        speaking_rate: Optional[float] = None,
        http_client: Optional[httpx.Client] = None,
    ) -> None:
        self.settings = settings
        self.api_key = (
            api_key
            or settings.inworld_api_key
            or os.environ.get("INWORLD_API_KEY", "")
        ).strip()
        self.default_voice = (
            default_voice
            or os.environ.get("INWORLD_VOICE_ID")
            or os.environ.get("C_TTS_VOICE")
            or settings.inworld_voice_id
        ).strip()
        self.model_id = (
            model_id
            or os.environ.get("INWORLD_MODEL")
            or settings.inworld_model
        ).strip()
        env_rate = os.environ.get("INWORLD_RATE")
        self.speaking_rate = float(
            speaking_rate
            if speaking_rate is not None
            else (env_rate if env_rate else settings.inworld_speaking_rate)
        )
        self._http_client = http_client

    def synthesize(
        self,
        text: str,
        out_wav_path: Path,
        *,
        voice_id: Optional[str] = None,
        speaking_rate: Optional[float] = None,
    ) -> TTSAudioResult:
        clean_text = (text or "").strip()
        if not clean_text:
            raise TTSError("TTS text must not be empty")

        chosen_voice = (voice_id or self.default_voice).strip()
        chosen_rate = float(speaking_rate if speaking_rate is not None else self.speaking_rate)
        cache_key = hashlib.sha256(
            json.dumps(
                {
                    "text": clean_text,
                    "voice": chosen_voice,
                    "model": self.model_id,
                    "rate": chosen_rate,
                },
                ensure_ascii=False,
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest()

        target = Path(out_wav_path)
        meta_path = target.with_suffix(".tts.json")
        if target.is_file() and meta_path.is_file():
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
                if meta.get("cache_key") == cache_key:
                    words = [WordTiming(**w) for w in meta.get("words") or []]
                    return TTSAudioResult(
                        audio_path=target,
                        duration_sec=float(meta["duration_sec"]),
                        words=words,
                        provider="inworld",
                        voice_id=chosen_voice,
                        model_id=self.model_id,
                        cached=True,
                    )
            except Exception:
                pass

        if not self.api_key:
            raise TTSError("INWORLD_API_KEY가 설정되지 않았습니다.")

        payload = {
            "text": clean_text,
            "voiceId": chosen_voice,
            "modelId": self.model_id,
            "language": "ko-KR",
            "timestampType": "WORD",
            "audioConfig": {
                "audioEncoding": "LINEAR16",
                "sampleRateHertz": TARGET_SR,
                "speakingRate": chosen_rate,
            },
            "deliveryMode": "BALANCED",
        }
        headers = {
            "Authorization": f"Basic {self.api_key}",
            "Content-Type": "application/json",
        }

        if self._http_client is not None:
            resp = self._http_client.post(INWORLD_TTS_URL, json=payload, headers=headers)
        else:
            with httpx.Client(timeout=120.0) as client:
                resp = client.post(INWORLD_TTS_URL, json=payload, headers=headers)

        if resp.status_code >= 400:
            raise TTSError(f"Inworld TTS 오류 ({resp.status_code}): {resp.text[:300]}")
        data = resp.json()
        audio_b64 = data.get("audioContent")
        if not audio_b64:
            raise TTSError("Inworld TTS 응답에 audioContent가 없습니다.")

        raw_wav = base64.b64decode(audio_b64)
        trimmed_wav, trim_offset = _trim_wav_silence(raw_wav)
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_suffix(".wav.tmp")
        tmp.write_bytes(trimmed_wav)
        os.replace(tmp, target)

        dur_sec = round(_wav_duration(target), 3)
        wa = (data.get("timestampInfo") or {}).get("wordAlignment") or {}
        words = _parse_word_alignment(wa, trim_offset_sec=trim_offset)
        meta_path.write_text(
            json.dumps(
                {
                    "cache_key": cache_key,
                    "voice": chosen_voice,
                    "model": self.model_id,
                    "duration_sec": dur_sec,
                    "words": [asdict(w) for w in words],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return TTSAudioResult(
            audio_path=target,
            duration_sec=dur_sec,
            words=words,
            provider="inworld",
            voice_id=chosen_voice,
            model_id=self.model_id,
            cached=False,
        )


class GeminiTTSProvider:
    """Fallback TTS provider wrapping `GenAIMediaProvider.generate_tts_beat`."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def synthesize(
        self,
        text: str,
        out_wav_path: Path,
        *,
        voice_id: Optional[str] = None,
        speaking_rate: Optional[float] = None,
    ) -> TTSAudioResult:
        _ = speaking_rate
        provider = GenAIMediaProvider(self.settings)
        chosen_voice = voice_id or self.settings.tts_default_voice
        res = provider.generate_tts_beat(text, out_wav_path, voice_name=chosen_voice, skip_existing=True)
        dur = round(_wav_duration(Path(res.path)), 3)
        return TTSAudioResult(
            audio_path=Path(res.path),
            duration_sec=dur,
            words=[],
            provider="gemini",
            voice_id=chosen_voice,
            model_id=res.model,
            cached=res.skipped,
        )


def build_tts_provider(settings: Settings) -> TTSProvider:
    """Select active TTS provider based on `TTS_PROVIDER` (default: inworld)."""
    choice = (os.environ.get("TTS_PROVIDER") or settings.tts_provider or "inworld").strip().lower()
    if choice == "gemini":
        return GeminiTTSProvider(settings)
    return InworldTTSProvider(settings)


def measure_lufs(audio_path: Path) -> Optional[float]:
    """Measure integrated LUFS using ffmpeg ebur128 (macOS-safe, avoids loudnorm)."""
    proc = subprocess.run(
        ["ffmpeg", "-hide_banner", "-i", str(audio_path), "-af", "ebur128", "-vn", "-f", "null", "-"],
        capture_output=True,
        text=True,
    )
    matches = re.findall(
        r"^\s*I:\s*(-?[0-9]+(?:\.[0-9]+)?|inf|-inf)\s+LUFS",
        proc.stderr or "",
        flags=re.MULTILINE,
    )
    if not matches:
        return None
    val_str = matches[-1]
    if "inf" in val_str.lower():
        return None
    val = float(val_str)
    return val if -65.0 <= val <= 0.0 else None


def _decode_pcm_f32(path: Path, *, sample_rate: int = TARGET_SR, channels: int = TARGET_CH) -> np.ndarray:
    proc = subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-v",
            "error",
            "-i",
            str(path),
            "-f",
            "f32le",
            "-acodec",
            "pcm_f32le",
            "-ac",
            str(channels),
            "-ar",
            str(sample_rate),
            "pipe:1",
        ],
        capture_output=True,
    )
    if proc.returncode != 0:
        raise TTSError(f"Audio decode failed for {path}: {proc.stderr.decode('utf-8', 'ignore')}")
    arr = np.frombuffer(proc.stdout, dtype=np.float32)
    frames = len(arr) // channels
    return arr[: frames * channels].reshape((frames, channels))


def _write_pcm16_wav(out_path: Path, samples: np.ndarray, *, sample_rate: int = TARGET_SR) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    pcm = np.clip(samples * 32767.0, -32767, 32767).astype("<i2")
    with wave.open(str(out_path), "wb") as wf:
        wf.setnchannels(pcm.shape[1])
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm.tobytes())


def normalize_audio_lufs(
    in_path: Path,
    out_wav: Path,
    *,
    target_lufs: float = TARGET_LUFS,
    sample_rate: int = TARGET_SR,
    channels: int = TARGET_CH,
) -> Dict[str, Optional[float]]:
    """Convert to 48kHz stereo WAV and normalize loudness to target LUFS via ebur128 + alimiter."""
    out_wav.parent.mkdir(parents=True, exist_ok=True)
    pre_wav = out_wav.with_suffix(".pre.wav")
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-v",
            "error",
            "-i",
            str(in_path),
            "-ar",
            str(sample_rate),
            "-ac",
            str(channels),
            "-c:a",
            "pcm_s16le",
            str(pre_wav),
        ],
        check=True,
        capture_output=True,
    )
    measured = measure_lufs(pre_wav)
    if measured is None:
        os.replace(pre_wav, out_wav)
        return {"input_lufs": None, "applied_gain_db": 0.0, "final_lufs": None}

    diff_db = max(-24.0, min(28.0, float(target_lufs) - measured))
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-v",
            "error",
            "-i",
            str(pre_wav),
            "-af",
            f"volume={diff_db:.2f}dB,alimiter=limit=0.82:level=disabled",
            "-ar",
            str(sample_rate),
            "-ac",
            str(channels),
            "-c:a",
            "pcm_s16le",
            str(out_wav),
        ],
        check=True,
        capture_output=True,
    )
    pre_wav.unlink(missing_ok=True)
    final_i = measure_lufs(out_wav)
    return {
        "input_lufs": round(measured, 2),
        "applied_gain_db": round(diff_db, 2),
        "final_lufs": round(final_i, 2) if final_i is not None else None,
    }


def synthesize_body_narration(
    lines: Sequence[Dict[str, str]],
    work_dir: Path,
    provider: TTSProvider,
    *,
    voice_id: Optional[str] = None,
    speaking_rate: Optional[float] = None,
    inter_gap_sec: float = 0.22,
) -> Dict[str, Any]:
    """Synthesize body narration lines, concatenate at 48kHz stereo, and master to -14.0 LUFS."""
    if not lines:
        raise TTSError("At least one narration line is required")

    tts_dir = Path(work_dir) / "tts"
    tts_dir.mkdir(parents=True, exist_ok=True)

    pcm_chunks: List[np.ndarray] = []
    segments: List[Dict[str, Any]] = []
    t_cur = 0.0
    gap_samples = max(0, int(round(inter_gap_sec * TARGET_SR)))

    for idx, line in enumerate(lines):
        narration = str(line.get("narration") or "").strip()
        caption = str(line.get("caption") or narration).strip()
        if not narration:
            continue
        seg_wav = tts_dir / f"seg_{idx + 1:02d}.wav"
        res = provider.synthesize(
            narration,
            seg_wav,
            voice_id=voice_id,
            speaking_rate=speaking_rate,
        )
        arr = _decode_pcm_f32(res.audio_path, sample_rate=TARGET_SR, channels=TARGET_CH)
        seg_dur = round(arr.shape[0] / float(TARGET_SR), 3)
        t_end = round(t_cur + seg_dur, 3)

        segments.append(
            {
                "index": idx + 1,
                "narration": narration,
                "caption": caption,
                "start_sec": round(t_cur, 3),
                "end_sec": t_end,
                "duration_sec": seg_dur,
                "words": [asdict(w) for w in res.words],
            }
        )
        pcm_chunks.append(arr)
        t_cur = t_end
        if idx < len(lines) - 1 and gap_samples > 0:
            pcm_chunks.append(np.zeros((gap_samples, TARGET_CH), dtype=np.float32))
            t_cur = round(t_cur + (gap_samples / float(TARGET_SR)), 3)

    if not pcm_chunks:
        raise TTSError("No non-empty narration lines were synthesized")

    raw_master = Path(work_dir) / "body_vo_raw.wav"
    master_wav = Path(work_dir) / "body_vo.wav"
    _write_pcm16_wav(raw_master, np.concatenate(pcm_chunks, axis=0), sample_rate=TARGET_SR)
    lufs_info = normalize_audio_lufs(raw_master, master_wav, target_lufs=TARGET_LUFS)
    raw_master.unlink(missing_ok=True)

    return {
        "wav_path": master_wav,
        "duration_sec": round(_wav_duration(master_wav), 3),
        "lufs": lufs_info,
        "segments": segments,
    }
