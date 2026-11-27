"""Modal deployment for official `black-forest-labs/flux-3-image-klein`.

Supports text-to-image, up to 10 reference images, and bounding-box layout control
using the official Black Forest Labs `flux3` inference package + `flux-3-image-klein-pup`.
"""

from __future__ import annotations

import base64
import io
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import modal

APP_DIR = Path(__file__).resolve().parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from schemas import (  # noqa: E402
    GenerateRequest,
    GenerateResponse,
    build_hf_download_specs,
    decode_reference_images,
    verify_bearer_token,
)


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


APP_NAME = os.environ.get("MODAL_APP_NAME", "napda-flux3-klein").strip() or "napda-flux3-klein"
GPU = os.environ.get("MODAL_FLUX3_GPU", "H100").strip() or "H100"
QUANT = os.environ.get("MODAL_FLUX3_QUANT", "fp8").strip().lower()
if QUANT not in ("", "fp8", "nvfp4"):
    raise ValueError(f"Invalid MODAL_FLUX3_QUANT={QUANT!r}; expected '', 'fp8', or 'nvfp4'.")

ENABLE_PUP = _env_bool("MODAL_FLUX3_ENABLE_PUP", True)
PUP_MEMORY = float(os.environ.get("MODAL_FLUX3_PUP_MEMORY", "0.35"))
OFFLOAD = _env_bool("MODAL_FLUX3_OFFLOAD", False)
SCALEDOWN_SEC = int(os.environ.get("MODAL_FLUX3_SCALEDOWN_SEC", "300"))
MIN_CONTAINERS = int(os.environ.get("MODAL_FLUX3_MIN_CONTAINERS", "0"))
VOLUME_NAME = os.environ.get("MODAL_FLUX3_VOLUME", "flux3-klein-weights").strip() or "flux3-klein-weights"
SECRET_NAME = os.environ.get("MODAL_FLUX3_SECRET", "flux3-klein-secrets").strip() or "flux3-klein-secrets"

if QUANT == "nvfp4":
    FLUX3_INSTALL_CMD = (
        "pip install --no-cache-dir -e '/opt/flux3[nvfp4]' "
        "--extra-index-url https://download.pytorch.org/whl/cu130 "
        "--extra-index-url https://flashinfer.ai/whl/cu130"
    )
else:
    FLUX3_INSTALL_CMD = (
        "pip install --no-cache-dir -e /opt/flux3 "
        "--extra-index-url https://download.pytorch.org/whl/cu130"
    )

image = (
    modal.Image.debian_slim(python_version="3.12")
    .apt_install("git", "libgl1", "libglib2.0-0")
    .pip_install(
        "fastapi[standard]>=0.115.0",
        "pydantic>=2.9.0",
        "huggingface_hub[hf_transfer]>=0.28.0",
        "setuptools>=64",
        "wheel",
    )
    .run_commands(
        "git clone --depth 1 https://github.com/black-forest-labs/flux-3-image-klein.git /opt/flux3",
        FLUX3_INSTALL_CMD,
    )
    .env(
        {
            "WEIGHTS_DIR": "/weights",
            "HF_HUB_ENABLE_HF_TRANSFER": "1",
            "TOKENIZERS_PARALLELISM": "false",
        }
    )
    .add_local_file(str(APP_DIR / "schemas.py"), remote_path="/root/schemas.py")
)

app = modal.App(APP_NAME)
weights_vol = modal.Volume.from_name(VOLUME_NAME, create_if_missing=True)
flux3_secret = modal.Secret.from_name(SECRET_NAME)


def _dir_size_gb(path: Path) -> float:
    if not path.exists():
        return 0.0
    total = sum(p.stat().st_size for p in path.rglob("*") if p.is_file())
    return round(total / (1024**3), 2)


@app.function(
    image=image,
    volumes={"/weights": weights_vol},
    secrets=[flux3_secret],
    timeout=3600,
)
def download_weights(
    quant: str = QUANT,
    enable_pup: bool = ENABLE_PUP,
) -> dict[str, Any]:
    """Download official BFL FLUX 3 Klein, optional Prompt Upsampler, and NSFW classifier into Modal Volume."""
    from huggingface_hub import snapshot_download

    hf_token = (os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_HUB_TOKEN") or "").strip()
    if not hf_token:
        raise RuntimeError(
            "HF_TOKEN is missing in Modal secret. Accept the license at "
            "https://huggingface.co/black-forest-labs/flux-3-image-klein and add HF_TOKEN to the secret."
        )

    specs = build_hf_download_specs(quant=quant, enable_pup=enable_pup)
    results: list[dict[str, Any]] = []
    weights_root = Path("/weights")
    weights_root.mkdir(parents=True, exist_ok=True)

    for spec in specs:
        local_dir = weights_root / spec["local_subdir"]
        snapshot_download(
            repo_id=spec["repo_id"],
            local_dir=str(local_dir),
            allow_patterns=spec["allow_patterns"],
            token=hf_token,
        )
        results.append(
            {
                "repo_id": spec["repo_id"],
                "local_dir": str(local_dir),
                "size_gb": _dir_size_gb(local_dir),
            }
        )

    weights_vol.commit()
    return {
        "volume": VOLUME_NAME,
        "quant": quant or "bf16",
        "enable_pup": enable_pup,
        "downloaded": results,
    }


@app.cls(
    image=image,
    gpu=GPU,
    volumes={"/weights": weights_vol},
    secrets=[flux3_secret],
    scaledown_window=SCALEDOWN_SEC,
    min_containers=MIN_CONTAINERS,
    timeout=600,
)
class Flux3KleinService:
    """Persistent GPU container serving official FLUX 3 Image Klein distilled + PUP."""

    @modal.enter()
    def load_models(self) -> None:
        os.environ.setdefault("WEIGHTS_DIR", "/weights")
        weights_vol.reload()

        from flux3.generate import Models
        from flux3.pipeline import WEIGHTS, dit_path

        dit = str(dit_path("distilled", QUANT))
        if not Path(dit).exists():
            raise RuntimeError(
                f"Model weights not found at {dit}. Run `modal run infra/modal-flux3/modal_app.py::download_weights` first."
            )

        pup_dir = str(WEIGHTS / "pup") if ENABLE_PUP else None
        if pup_dir and not Path(pup_dir).exists():
            raise RuntimeError(
                f"Prompt Upsampler weights not found at {pup_dir}. Run download_weights with MODAL_FLUX3_ENABLE_PUP=true."
            )

        self.models = Models(
            {"distilled": dit},
            pup=pup_dir,
            pup_memory=PUP_MEMORY,
            offload=OFFLOAD,
        )

    @modal.method()
    def run_generate(self, payload: dict[str, Any]) -> dict[str, Any]:
        from flux3.generate import generate
        from flux3.safety import exif

        req = GenerateRequest.model_validate(payload)
        refs = decode_reference_images(req.reference_images)

        t0 = time.perf_counter()
        image_out, record = generate(
            self.models,
            "distilled",
            req.prompt,
            refs,
            boxes=req.boxes,
            width=req.width,
            height=req.height,
            steps=req.steps,
            guidance=None,
            seed=req.seed,
            pup=req.use_pup and self.models.upsampler is not None,
            safety=req.safety,
        )
        latency_ms = int((time.perf_counter() - t0) * 1000)

        fmt = req.output_format.upper()
        mime_map = {"PNG": "image/png", "JPEG": "image/jpeg", "WEBP": "image/webp"}
        save_kwargs: dict[str, Any] = {}
        if fmt in ("PNG", "JPEG", "WEBP"):
            save_kwargs["exif"] = exif("distilled")
        if fmt == "JPEG":
            save_kwargs["quality"] = 95
            image_out = image_out.convert("RGB")
        elif fmt == "WEBP":
            save_kwargs["quality"] = 92

        buf = io.BytesIO()
        image_out.save(buf, format=fmt, **save_kwargs)
        encoded = base64.b64encode(buf.getvalue()).decode("ascii")

        return GenerateResponse(
            image_base64=encoded,
            mime_type=mime_map[fmt],
            width=int(record["width"]),
            height=int(record["height"]),
            seed=int(record["seed"]),
            steps=int(record["steps"]),
            upsampled=bool(record["upsampled"]),
            prompt_used=str(record["prompt"]),
            model="distilled",
            quant=QUANT or "bf16",
            latency_ms=latency_ms,
        ).model_dump()

    @modal.asgi_app()
    def web(self):
        from fastapi import FastAPI, Header, HTTPException, status

        api = FastAPI(title="FLUX 3 Image Klein Modal API", version="1.0.0")

        @api.get("/health")
        def health() -> dict[str, Any]:
            return {
                "status": "ok",
                "model": "black-forest-labs/flux-3-image-klein",
                "checkpoint": "distilled",
                "gpu": GPU,
                "quant": QUANT or "bf16",
                "upsampler_loaded": self.models.upsampler is not None,
                "license": "FLUX Kommunity License v1.0",
            }

        @api.post("/v1/generate", response_model=GenerateResponse)
        def generate_endpoint(
            req: GenerateRequest,
            authorization: str | None = Header(default=None),
        ) -> dict[str, Any]:
            from flux3.generate import Refused

            try:
                verify_bearer_token(authorization, os.environ.get("MODAL_API_TOKEN"))
            except PermissionError as exc:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

            try:
                return self.run_generate.local(req.model_dump())
            except Refused as exc:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Blocked by safety filter: {exc}",
                ) from exc
            except ValueError as exc:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=str(exc),
                ) from exc

        return api


@app.local_entrypoint()
def main(
    prompt: str = "Studio product photo of a minimalist ceramic pour-over coffee dripper on warm travertine stone, soft morning window light",
    out: str = "flux3_out.png",
    images: str = "",
    boxes_path: str = "",
    width: int = 0,
    height: int = 0,
    steps: int = 0,
    seed: int = -1,
    no_pup: bool = False,
    unsafe: bool = False,
    download_only: bool = False,
) -> None:
    """Quick CLI smoke test via `modal run infra/modal-flux3/modal_app.py`."""
    if download_only:
        summary = download_weights.remote(quant=QUANT, enable_pup=ENABLE_PUP)
        print(json.dumps(summary, indent=2, ensure_ascii=False))
        return

    ref_b64: list[str] = []
    if images.strip():
        for raw_path in images.split(","):
            p = Path(raw_path.strip()).expanduser().resolve()
            ref_b64.append(base64.b64encode(p.read_bytes()).decode("ascii"))

    boxes = json.loads(Path(boxes_path).read_text(encoding="utf-8")) if boxes_path.strip() else None
    payload: dict[str, Any] = {
        "prompt": prompt,
        "reference_images": ref_b64,
        "boxes": boxes,
        "width": width or None,
        "height": height or None,
        "steps": steps or None,
        "seed": None if seed < 0 else seed,
        "use_pup": not no_pup,
        "safety": not unsafe,
        "output_format": "png",
    }

    res = Flux3KleinService().run_generate.remote(payload)
    out_file = Path(out).expanduser().resolve()
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_bytes(base64.b64decode(res["image_base64"]))
    meta = {k: v for k, v in res.items() if k != "image_base64"}
    out_file.with_suffix(".json").write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Saved {out_file} ({meta['width']}x{meta['height']}, {meta['latency_ms']} ms)")
