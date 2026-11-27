"""MiniMax-H3 이미지→영상 (Modal H100, ComfyUI 공식 노드). Gemini 영상 모델 대신 쓰려고 시험 중.

2026-11-27 측정: 576x1024 5초(124프레임)+소리, 20스텝 — H100 132초(생성 71초), B200 116초. 클립당 약 15~20센트.
모델(Comfy-Org/MiniMax-H3) 약 40GB 는 Modal Volume minimax-models 에 받아 둔다. 첫 프레임 이미지가 필요하다.
라이선스: MiniMax H3 Community License — 결과물 상업 이용은 별도 라이선스 필요(내부 시연은 무관).

    modal run backend/selfhosted/minimax_modal.py::download            # CPU 로 모델 받기 (Volume minimax-models, 1회)
    modal run backend/selfhosted/minimax_modal.py::generate --image first.png --prompt "..." --out out.mp4
"""

import json
import subprocess
import time
import urllib.request
from pathlib import Path, PurePosixPath

import modal

REPO = "Comfy-Org/MiniMax-H3"
FILES = {
    "diffusion_models": "diffusion_models/minimax_h3_fl2va_pruned_int8_convrot.safetensors",
    "text_encoders": "text_encoders/qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors",
    "vae": "vae/minimax_h3_video_vae_int8_convrot.safetensors",
    "vae_audio": "vae/minimax_h3_audio_vae_fp32.safetensors",
}
MODELS = PurePosixPath("/models")  # 이 파일은 Windows 에서도 읽히므로 리눅스 경로로 고정
COMFY = PurePosixPath("/opt/ComfyUI")  # /root 는 Modal 이 실행 스크립트를 올리며 가린다

models = modal.Volume.from_name("minimax-models", create_if_missing=True)

image = (
    modal.Image.debian_slim(python_version="3.12")
    .apt_install("git", "ffmpeg", "libgl1", "libglib2.0-0")
    .pip_install("torch", "torchvision", "torchaudio", index_url="https://download.pytorch.org/whl/cu130")
    .run_commands(f"git clone --depth 1 https://github.com/comfyanonymous/ComfyUI {COMFY}")
    .run_commands(f"pip install -r {COMFY}/requirements.txt")
    .pip_install("huggingface_hub[hf_transfer]")
    .env({"HF_HUB_ENABLE_HF_TRANSFER": "1"})
)

app = modal.App("napda-minimax", image=image)


@app.function(volumes={str(MODELS): models}, cpu=4, memory=8192, timeout=3600)
def download() -> None:
    from huggingface_hub import hf_hub_download

    for name in FILES.values():
        target = Path(str(MODELS / name))
        if target.exists() and target.stat().st_size > 0:
            print("있음", name, f"{target.stat().st_size / 1e9:.1f}GB", flush=True)
            continue
        t0 = time.time()
        hf_hub_download(REPO, name, local_dir=str(MODELS))
        print("받음", name, f"{target.stat().st_size / 1e9:.1f}GB {time.time() - t0:.0f}초", flush=True)
        models.commit()


def _link_models() -> None:
    missing = [n for n in FILES.values() if not Path(str(MODELS / n)).exists()]
    if missing:
        raise RuntimeError(f"모델 파일 없음(다운로드 다시 필요): {missing}")
    for sub in ("diffusion_models", "text_encoders", "vae"):
        dst = Path(str(COMFY)) / "models" / sub
        dst.mkdir(parents=True, exist_ok=True)
        for f in Path(str(MODELS / sub)).glob("*.safetensors"):
            link = dst / f.name
            if not link.exists():
                link.symlink_to(f)


def _graph(image_name: str, prompt: str, width: int, height: int, length: int, steps: int, seed: int) -> dict:
    """공식 템플릿(video_minimax_h3_i2v.json) 서브그래프를 API 형식으로 옮긴 것 (turbo 끔)."""
    return {
        "1": {"class_type": "UNETLoader", "inputs": {"unet_name": Path(FILES["diffusion_models"]).name, "weight_dtype": "default"}},
        "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": Path(FILES["text_encoders"]).name, "type": "minimax", "device": "default"}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": Path(FILES["vae"]).name}},
        "4": {"class_type": "VAELoader", "inputs": {"vae_name": Path(FILES["vae_audio"]).name}},
        "5": {"class_type": "LoadImage", "inputs": {"image": image_name}},
        "6": {"class_type": "MiniMaxH3ImageToVideo", "inputs": {
            "clip": ["2", 0], "vae": ["3", 0], "first_frame": ["5", 0],
            "prompt": prompt, "width": width, "height": height, "length": length}},
        "7": {"class_type": "RandomNoise", "inputs": {"noise_seed": seed}},
        "8": {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "res_multistep"}},
        "9": {"class_type": "BasicScheduler", "inputs": {"model": ["1", 0], "scheduler": "simple", "steps": steps, "denoise": 1.0}},
        "10": {"class_type": "BasicGuider", "inputs": {"model": ["1", 0], "conditioning": ["6", 0]}},
        "11": {"class_type": "SamplerCustomAdvanced", "inputs": {
            "noise": ["7", 0], "guider": ["10", 0], "sampler": ["8", 0], "sigmas": ["9", 0], "latent_image": ["6", 1]}},
        "12": {"class_type": "VAEDecode", "inputs": {"samples": ["11", 0], "vae": ["3", 0]}},
        "13": {"class_type": "VAEDecodeAudio", "inputs": {"samples": ["11", 0], "vae": ["4", 0]}},
        "14": {"class_type": "CreateVideo", "inputs": {"images": ["12", 0], "audio": ["13", 0], "fps": 24}},
        "15": {"class_type": "SaveVideo", "inputs": {"video": ["14", 0], "filename_prefix": "napda/clip", "format": "auto", "codec": "auto"}},
    }


def _call(path: str, body: dict | None = None) -> dict:
    req = urllib.request.Request(f"http://127.0.0.1:8188{path}",
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read() or b"{}")


@app.function(gpu="H100", volumes={str(MODELS): models}, memory=65536, timeout=3600)
def render(image_bytes: bytes, prompt: str, width: int, height: int, length: int, steps: int, seed: int) -> bytes:
    _link_models()
    comfy = Path(str(COMFY))
    (comfy / "input").mkdir(exist_ok=True)
    (comfy / "input" / "first.png").write_bytes(image_bytes)
    t0 = time.time()
    log = open("/tmp/comfy.log", "w")
    proc = subprocess.Popen(["python", "main.py", "--listen", "127.0.0.1", "--port", "8188"], cwd=str(COMFY), stdout=log, stderr=subprocess.STDOUT)
    try:
        for _ in range(600):
            if proc.poll() is not None:
                raise RuntimeError("ComfyUI 가 시작하지 못함: " + Path("/tmp/comfy.log").read_text()[-3000:])
            try:
                _call("/system_stats")
                break
            except Exception:
                time.sleep(1)
        else:
            raise RuntimeError("ComfyUI 가 10분 안에 뜨지 않음")
        print(f"[ComfyUI 준비] {time.time() - t0:.0f}초", flush=True)
        try:
            pid = _call("/prompt", {"prompt": _graph("first.png", prompt, width, height, length, steps, seed)})["prompt_id"]
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"그래프 거절: {exc.read().decode()[:3000]}") from exc
        t1 = time.time()
        while True:
            hist = _call(f"/history/{pid}")
            if pid in hist:
                status = hist[pid].get("status", {})
                if status.get("status_str") == "error":
                    raise RuntimeError(f"생성 실패: {json.dumps(status.get('messages'), ensure_ascii=False)[-3000:]}")
                if status.get("completed"):
                    break
            if proc.poll() is not None:
                raise RuntimeError("ComfyUI 가 종료됨: " + Path("/tmp/comfy.log").read_text()[-3000:])
            time.sleep(3)
        print(f"[생성] {time.time() - t1:.0f}초 (모델 적재 포함)", flush=True)
        outs = [p for p in (comfy / "output" / "napda").glob("clip*.mp4")]
        return max(outs, key=lambda p: p.stat().st_mtime).read_bytes()
    finally:
        print(Path("/tmp/comfy.log").read_text()[-2500:], flush=True)
        proc.terminate()


@app.local_entrypoint()
def generate(image: str, prompt: str, out: str = "minimax_clip.mp4", width: int = 480, height: int = 864,
             seconds: float = 4.0, steps: int = 20, seed: int = 1) -> None:
    frames = max(5, round(seconds * 24))
    length = frames + (5 - frames % 17) % 17  # 템플릿과 같은 17k+5 규칙
    t0 = time.time()
    data = render.remote(Path(image).read_bytes(), prompt, width, height, length, steps, seed)
    Path(out).write_bytes(data)
    print(f"[끝] {out} {len(data) / 1e6:.1f}MB 프레임={length} 전체 {time.time() - t0:.0f}초")
