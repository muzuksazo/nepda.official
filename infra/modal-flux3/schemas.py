"""Pure-Python request schemas, auth/decoding helpers, and HF weight specs for Modal FLUX 3 Klein."""

from __future__ import annotations

import base64
import binascii
import hmac
import io
from typing import Any, Literal

from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel, Field

MAX_REFERENCES = 10
QUANT_VALUES = ("", "fp8", "nvfp4")


class GenerateRequest(BaseModel):
    """HTTP payload for `/v1/generate` using FLUX 3 Image Klein distilled."""

    prompt: str = Field(..., min_length=1, max_length=8000)
    reference_images: list[str] = Field(default_factory=list, max_length=MAX_REFERENCES)
    boxes: list[dict[str, Any]] | None = None
    width: int | None = Field(default=None, ge=64, le=4096)
    height: int | None = Field(default=None, ge=64, le=4096)
    steps: int | None = Field(default=None, ge=1, le=50)
    seed: int | None = None
    use_pup: bool = True
    safety: bool = True
    output_format: Literal["png", "jpeg", "webp"] = "png"


class GenerateResponse(BaseModel):
    """Structured JSON response from `/v1/generate`."""

    image_base64: str
    mime_type: str
    width: int
    height: int
    seed: int
    steps: int
    upsampled: bool
    prompt_used: str
    model: str = "distilled"
    quant: str = "fp8"
    latency_ms: int


def decode_reference_images(
    encoded_images: list[str], max_images: int = MAX_REFERENCES
) -> list[Image.Image]:
    """Decode base64 or data-URI reference images into RGB PIL images."""
    if len(encoded_images) > max_images:
        raise ValueError(f"At most {max_images} reference images are allowed (got {len(encoded_images)}).")

    decoded: list[Image.Image] = []
    for idx, item in enumerate(encoded_images):
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"reference_images[{idx}] must be a non-empty base64 string.")
        raw_b64 = item.strip()
        if raw_b64.startswith("data:"):
            header, sep, body = raw_b64.partition(",")
            if not sep or ";base64" not in header.lower():
                raise ValueError(f"reference_images[{idx}] data URI must be base64-encoded.")
            raw_b64 = body.strip()
        if not raw_b64:
            raise ValueError(f"reference_images[{idx}] has empty base64 payload.")
        try:
            img_bytes = base64.b64decode(raw_b64, validate=True)
            with Image.open(io.BytesIO(img_bytes)) as img:
                decoded.append(img.convert("RGB"))
        except (binascii.Error, UnidentifiedImageError, OSError, ValueError) as exc:
            raise ValueError(f"Invalid reference_images[{idx}]: {exc}") from exc
    return decoded


def verify_bearer_token(authorization: str | None, expected_token: str | None) -> None:
    """Enforce constant-time Bearer authentication when `MODAL_API_TOKEN` is configured."""
    expected = (expected_token or "").strip()
    if not expected:
        return
    if not authorization or not authorization.strip():
        raise PermissionError("Missing Authorization header.")
    scheme, _, token = authorization.strip().partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise PermissionError("Authorization header must use Bearer scheme.")
    if not hmac.compare_digest(token.strip(), expected):
        raise PermissionError("Invalid Bearer token.")


def build_hf_download_specs(quant: str, enable_pup: bool) -> list[dict[str, Any]]:
    """Return Hugging Face repositories and selective file patterns for FLUX 3 Klein."""
    clean_quant = (quant or "").strip().lower()
    if clean_quant not in QUANT_VALUES:
        raise ValueError(f"Unsupported quant '{quant}'; expected one of {QUANT_VALUES}.")

    base_patterns = [
        "ae.safetensors",
        "text_encoder/*",
        "README.md",
        "LICENSE.md",
        "NOTICE.md",
    ]
    if clean_quant == "fp8":
        base_patterns.append("variants/fp8r/*")
    elif clean_quant == "nvfp4":
        base_patterns.append("variants/nvfp4/*")
    else:
        base_patterns.extend(["model.safetensors", "config.json", "manifest.json"])

    specs: list[dict[str, Any]] = [
        {
            "repo_id": "black-forest-labs/flux-3-image-klein",
            "local_subdir": "flux-3-image-klein",
            "allow_patterns": base_patterns,
        }
    ]
    if enable_pup:
        specs.append(
            {
                "repo_id": "black-forest-labs/flux-3-image-klein-pup",
                "local_subdir": "pup",
                "allow_patterns": None,
            }
        )
    # Upstream flux3.generate.Models.__init__ always initializes Safety with nsfw-classifier.
    specs.append(
        {
            "repo_id": "Falconsai/nsfw_image_detection",
            "local_subdir": "nsfw-classifier",
            "allow_patterns": None,
        }
    )
    return specs
