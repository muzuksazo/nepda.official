"""Fish Audio Drama 3 voice-clone TTS on Modal (ephemeral `modal run`, nothing deployed).

  modal run prep.py::transcribe  # CPU: Whisper transcripts of the reference clips -> transcripts.json
  modal run prep.py::download    # CPU: weights -> Modal Volume (one time)
  modal run app.py               # GPU: synthesize TEXT in each reference voice -> out/*.wav
"""
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import modal

HERE = Path(__file__).parent
VOICE_DIR = HERE.parent
VOICES = ["1차.wav", "돋이 Edition.wav", "이시우.m4a", "탑동 19.m4a"]
TRANSCRIPTS = HERE / "transcripts.json"
OUT_DIR = HERE / "out"
DEFAULT_TEXT = (
    "안녕하세요. 지금 들으시는 목소리는 드라마 쓰리 모델로 합성한 음성입니다. "
    "바쁜 아침, 딱 삼 분이면 충분해요. 오늘도 냅다 시작해 볼까요?"
)

MODEL_REPO = "fishaudio/drama-3"
MODEL_REV = "78e5ab79e49aa9a25abe8799eff2c4d73a1c3216"
MODEL_DIR = "/models/drama-3"

app = modal.App("napda-drama3-tts")
weights = modal.Volume.from_name("drama3-weights", create_if_missing=True)

serve_image = (
    modal.Image.from_registry("hongccc/sglang-omni:dev", add_python="3.12")
    .entrypoint([])
    .run_commands(
        "git clone --depth 1 https://github.com/sgl-project/sglang-omni.git /opt/sglang-omni",
        "cd /opt/sglang-omni && uv pip install --python /opt/sglang/bin/python "
        "--prerelease=allow -e '.[fishaudio]'",
        "ls /opt/sglang/bin | grep -i omni; cd /opt/sglang-omni && git rev-parse HEAD",
    )
)


def _to_wav(src: Path, rate: int = 44100) -> bytes:
    """Local: normalise a reference clip to mono 16-bit WAV (44.1 kHz by default)."""
    with tempfile.TemporaryDirectory() as td:
        dst = Path(td) / "ref.wav"
        subprocess.run(
            ["ffmpeg", "-y", "-v", "error", "-i", str(src), "-ac", "1", "-ar", str(rate),
             "-c:a", "pcm_s16le", str(dst)],
            check=True,
        )
        return dst.read_bytes()


@app.function(image=serve_image, gpu="H100", volumes={"/models": weights},
              timeout=3600, memory=65536, cpu=8)
def synth(refs: dict[str, dict], text: str) -> dict:
    """refs: name -> {"wav": bytes, "text": transcript}. Returns name -> wav bytes (+ log on failure)."""
    import urllib.error
    import urllib.request

    ref_dir = Path("/tmp/refs")
    ref_dir.mkdir(exist_ok=True)
    log_path = Path("/tmp/server.log")
    subprocess.run("nvidia-smi --query-gpu=name,memory.total --format=csv", shell=True)
    t0 = time.time()
    with log_path.open("w") as log:
        proc = subprocess.Popen(
            ["/opt/sglang/bin/sgl-omni", "serve", "--model-path", MODEL_DIR, "--port", "8000"],
            stdout=log, stderr=subprocess.STDOUT,
        )

    def tail(n=120):
        return "\n".join(log_path.read_text(errors="replace").splitlines()[-n:])

    ready = False
    while time.time() - t0 < 2400:
        if proc.poll() is not None:
            break
        try:
            with urllib.request.urlopen("http://127.0.0.1:8000/health", timeout=5) as r:
                if r.status == 200:
                    ready = True
                    break
        except Exception:
            pass
        time.sleep(5)
        if int(time.time() - t0) % 60 < 5:
            print(f"[{int(time.time() - t0)}s] waiting for server…", flush=True)
    if not ready:
        proc.kill()
        return {"error": f"server not ready (exit={proc.poll()})", "log": tail(200)}
    print(f"server ready after {time.time() - t0:.0f}s", flush=True)

    results: dict = {"startup_s": round(time.time() - t0), "audio": {}, "meta": {}}
    for i, (name, ref) in enumerate(refs.items()):
        ref_path = ref_dir / f"ref{i}.wav"
        ref_path.write_bytes(ref["wav"])
        body = json.dumps({
            "input": text,
            "response_format": "wav",
            "references": [{"audio_path": str(ref_path), "text": ref["text"]}],
        }).encode()
        req = urllib.request.Request("http://127.0.0.1:8000/v1/audio/speech", data=body,
                                     headers={"Content-Type": "application/json"})
        t1 = time.time()
        try:
            with urllib.request.urlopen(req, timeout=900) as r:
                audio = r.read()
                results["audio"][name] = audio
                results["meta"][name] = {"sec": round(time.time() - t1, 1), "bytes": len(audio),
                                         "sample_rate": r.headers.get("X-Sample-Rate")}
        except urllib.error.HTTPError as e:
            results["meta"][name] = {"error": f"HTTP {e.code}: {e.read()[:2000].decode(errors='replace')}"}
        except Exception as e:  # noqa: BLE001
            results["meta"][name] = {"error": repr(e)}
        print(name, results["meta"][name], flush=True)
    if any("error" in m for m in results["meta"].values()):
        results["log"] = tail(150)
    proc.terminate()
    return results


@app.local_entrypoint()
def tts(text: str = DEFAULT_TEXT, only: str = ""):
    tr = json.loads(TRANSCRIPTS.read_text(encoding="utf-8"))
    names = [v for v in VOICES if not only or v == only]
    refs = {v: {"wav": _to_wav(VOICE_DIR / v), "text": tr[v]["text"]} for v in names}
    res = synth.remote(refs, text)
    if "error" in res:
        print("FAILED:", res["error"], "\n", res["log"])
        sys.exit(1)
    OUT_DIR.mkdir(exist_ok=True)
    for name, audio in res["audio"].items():
        out = OUT_DIR / f"{Path(name).stem}_drama3.wav"
        out.write_bytes(audio)
        print("saved", out)
    print(json.dumps({"startup_s": res["startup_s"], **res["meta"]}, ensure_ascii=False, indent=2))
    if "log" in res:
        print(res["log"])
