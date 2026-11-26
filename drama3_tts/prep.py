"""CPU-only prep for app.py: reference transcripts and model weights. No GPU needed."""
import json
from pathlib import Path

import modal

from app import MODEL_DIR, MODEL_REPO, MODEL_REV, TRANSCRIPTS, VOICE_DIR, VOICES, _to_wav

app = modal.App("napda-drama3-prep")
weights = modal.Volume.from_name("drama3-weights", create_if_missing=True)

light_image = modal.Image.debian_slim(python_version="3.12").pip_install(
    "huggingface_hub>=1.0", "faster-whisper==1.2.1"
).add_local_python_source("app")

@app.function(image=light_image, cpu=8, memory=16384, timeout=1800)
def asr(clips: dict[str, bytes]) -> dict[str, dict]:
    import io
    import wave

    import numpy as np
    from faster_whisper import WhisperModel

    model = WhisperModel("large-v3", device="cpu", compute_type="int8", cpu_threads=8)
    out = {}
    for name, data in clips.items():
        # 16 kHz mono 16-bit WAV in; decode here rather than through PyAV.
        with wave.open(io.BytesIO(data)) as w:
            pcm = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
        audio = pcm.astype(np.float32) / 32768.0
        segs, info = model.transcribe(audio, beam_size=5, vad_filter=True)
        text = " ".join(s.text.strip() for s in segs).strip()
        out[name] = {"language": info.language, "prob": round(info.language_probability, 3),
                     "duration": round(info.duration, 2), "text": text}
        print(name, out[name], flush=True)
    return out


@app.function(image=light_image, volumes={"/models": weights}, timeout=3600)
def fetch_weights() -> str:
    from huggingface_hub import snapshot_download

    snapshot_download(MODEL_REPO, revision=MODEL_REV, local_dir=MODEL_DIR, max_workers=16)
    weights.commit()
    files = sorted(p for p in Path(MODEL_DIR).iterdir() if p.is_file())
    total = sum(p.stat().st_size for p in files)
    return f"{len(files)} files, {total / 1e9:.1f} GB in {MODEL_DIR}"


@app.local_entrypoint()
def transcribe():
    clips = {v: _to_wav(VOICE_DIR / v, rate=16000) for v in VOICES}
    res = asr.remote(clips)
    TRANSCRIPTS.write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(res, ensure_ascii=False, indent=2))


@app.local_entrypoint()
def download():
    print(fetch_weights.remote())
