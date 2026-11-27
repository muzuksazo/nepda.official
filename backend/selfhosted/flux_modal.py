"""FLUX klein 이미지 생성 (Modal H100, 공식 저장소 코드 그대로). Gemini 이미지 모델 대신 쓰려고 시험 중.

2026-11-27 측정: 768x1376 글→이미지 8초, 참고 이미지 편집 21초. 단 첫 실행 모델 적재 476초(프롬프트 보강 vLLM 컴파일).
알려진 문제: 사진→점토 스타일 편집이 거의 안 바뀜(원본과 비슷). 가중치 52GB(약관 동의 계정의 HF_TOKEN 필요).
라이선스: FLUX Kommunity License — 연매출 US$5M 미만이면 결과물 상업 이용 가능.

    modal run backend/selfhosted/flux_modal.py::download                       # CPU 로 가중치 받기 (Volume flux-models, 1회, HF 토큰 필요)
    modal run backend/selfhosted/flux_modal.py::generate_cli --jobs jobs.json --out-dir out
      jobs.json: [{"name": "a", "prompt": "...", "image": "ref.png"(선택), "width": 768, "height": 1376, "seed": 1}]
"""

import json
import time
from pathlib import Path, PurePosixPath

import modal

WEIGHTS = PurePosixPath("/weights")  # Windows 에서도 읽히는 파일이라 리눅스 경로로 고정
REPO_DIR = PurePosixPath("/opt/flux3")
REPOS = [
    ("black-forest-labs/flux-3-image-klein", "flux-3-image-klein", ["variants/*"]),
    ("black-forest-labs/flux-3-image-klein-pup", "pup", []),
    ("Falconsai/nsfw_image_detection", "nsfw-classifier", []),
]

weights = modal.Volume.from_name("flux-models", create_if_missing=True)
hf = modal.Secret.from_name("napda-backend")  # 안에 HF_TOKEN (모델 약관 동의한 계정)

image = (
    # vLLM(프롬프트 보강)이 실행 중 nvcc 로 커널을 컴파일한다 → CUDA 개발용 이미지
    modal.Image.from_registry("nvidia/cuda:13.0.0-devel-ubuntu24.04", add_python="3.12")
    .apt_install("git", "libgl1", "libglib2.0-0")
    .run_commands(f"git clone --depth 1 https://github.com/black-forest-labs/flux-3-image-klein {REPO_DIR}")
    .run_commands(f"pip install {REPO_DIR} --extra-index-url https://download.pytorch.org/whl/cu130")
    .pip_install("huggingface_hub")
    # vLLM 컴파일 결과를 볼륨에 남겨 두 번째 실행부터 준비 시간을 줄인다 (첫 실행 476초)
    .env({"WEIGHTS_DIR": str(WEIGHTS), "CUDA_HOME": "/usr/local/cuda", "VLLM_CACHE_ROOT": f"{WEIGHTS}/.vllm_cache"})
)

app = modal.App("napda-flux", image=image)


@app.function(volumes={str(WEIGHTS): weights}, secrets=[hf], cpu=4, memory=8192, timeout=3600)
def download() -> None:
    from huggingface_hub import snapshot_download

    for repo, sub, exclude in REPOS:
        t0 = time.time()
        snapshot_download(repo, local_dir=str(WEIGHTS / sub), ignore_patterns=exclude or None)
        size = sum(f.stat().st_size for f in Path(str(WEIGHTS / sub)).rglob("*") if f.is_file())
        print(f"받음 {repo} {size / 1e9:.1f}GB {time.time() - t0:.0f}초", flush=True)
        weights.commit()


@app.function(gpu="H100", volumes={str(WEIGHTS): weights}, memory=65536, timeout=3600)
def render(jobs: list, refs: dict) -> dict:
    import io

    from PIL import Image

    from flux3.generate import Models, generate
    from flux3.pipeline import WEIGHTS as W, dit_path

    t0 = time.time()
    models = Models({"distilled": str(dit_path("distilled"))}, pup=str(W / "pup"), pup_memory=0.35)
    print(f"[모델 적재] {time.time() - t0:.0f}초", flush=True)
    out = {}
    for job in jobs:
        images = [Image.open(io.BytesIO(refs[job["image"]])).convert("RGB")] if job.get("image") else []
        t1 = time.time()
        img, record = generate(models, "distilled", job["prompt"], images=images, seed=job.get("seed", 1),
                               width=job.get("width"), height=job.get("height"))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        out[job["name"]] = buf.getvalue()
        upsampled = (record or {}).get("prompt") if isinstance(record, dict) else None
        print(f"[{job['name']}] {time.time() - t1:.1f}초 {img.size} 보강된 프롬프트: {str(upsampled)[:300]}", flush=True)
    weights.commit()  # vLLM 컴파일 캐시 저장
    return out


@app.local_entrypoint()
def generate_cli(jobs: str, out_dir: str = "out") -> None:
    spec = json.loads(Path(jobs).read_text(encoding="utf-8"))
    base = Path(jobs).parent
    refs = {j["image"]: (base / j["image"]).read_bytes() for j in spec if j.get("image")}
    t0 = time.time()
    result = render.remote(spec, refs)
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    for name, data in result.items():
        (Path(out_dir) / f"{name}.png").write_bytes(data)
    print(f"[끝] {len(result)}장 → {out_dir} 전체 {time.time() - t0:.0f}초")
