"""Contract & syntax tests for infra/modal-flux3 deployment scripts."""

from __future__ import annotations

import ast
import base64
import importlib.util
import io
import sys
import unittest
from pathlib import Path

from PIL import Image
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[2]
MODAL_DIR = ROOT / "infra" / "modal-flux3"

_SPEC = importlib.util.spec_from_file_location("flux3_modal_schemas", MODAL_DIR / "schemas.py")
assert _SPEC and _SPEC.loader
schemas = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = schemas
_SPEC.loader.exec_module(schemas)


def _sample_png_b64(color: tuple[int, int, int] = (20, 120, 220)) -> str:
    buf = io.BytesIO()
    Image.new("RGB", (16, 16), color=color).save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


class ModalFlux3ContractTests(unittest.TestCase):
    def test_modal_app_and_client_parse_cleanly_without_deprecated_api(self) -> None:
        for filename in ("schemas.py", "modal_app.py", "client_example.py"):
            src = (MODAL_DIR / filename).read_text(encoding="utf-8")
            ast.parse(src, filename=filename)

        app_src = (MODAL_DIR / "modal_app.py").read_text(encoding="utf-8")
        self.assertIn("@modal.asgi_app()", app_src)
        self.assertIn("scaledown_window=", app_src)
        self.assertNotIn("web_endpoint", app_src)
        self.assertNotIn("container_idle_timeout", app_src)

    def test_generate_request_defaults_and_bounds(self) -> None:
        req = schemas.GenerateRequest(prompt="test prompt")
        self.assertTrue(req.use_pup)
        self.assertTrue(req.safety)
        self.assertEqual(req.output_format, "png")

        with self.assertRaises(ValidationError):
            schemas.GenerateRequest(prompt="", width=32)

        with self.assertRaises(ValidationError):
            schemas.GenerateRequest(prompt="ok", reference_images=["a"] * 11)

    def test_decode_reference_images_accepts_raw_and_data_uri(self) -> None:
        raw_b64 = _sample_png_b64()
        data_uri = f"data:image/png;base64,{raw_b64}"
        imgs = schemas.decode_reference_images([raw_b64, data_uri])
        self.assertEqual(len(imgs), 2)
        self.assertEqual(imgs[0].size, (16, 16))
        self.assertEqual(imgs[1].mode, "RGB")

        with self.assertRaises(ValueError):
            schemas.decode_reference_images(["not_valid_base64!!!"])

        with self.assertRaises(ValueError):
            schemas.decode_reference_images([raw_b64] * 11)

    def test_verify_bearer_token(self) -> None:
        schemas.verify_bearer_token(None, None)
        schemas.verify_bearer_token("Bearer secret-123", "secret-123")

        with self.assertRaises(PermissionError):
            schemas.verify_bearer_token(None, "secret-123")

        with self.assertRaises(PermissionError):
            schemas.verify_bearer_token("Basic abc", "secret-123")

        with self.assertRaises(PermissionError):
            schemas.verify_bearer_token("Bearer wrong", "secret-123")

    def test_build_hf_download_specs(self) -> None:
        fp8_specs = schemas.build_hf_download_specs("fp8", True)
        self.assertEqual(
            [s["repo_id"] for s in fp8_specs],
            [
                "black-forest-labs/flux-3-image-klein",
                "black-forest-labs/flux-3-image-klein-pup",
                "Falconsai/nsfw_image_detection",
            ],
        )
        self.assertIn("variants/fp8r/*", fp8_specs[0]["allow_patterns"])

        bf16_nopup = schemas.build_hf_download_specs("", False)
        self.assertEqual(
            [s["repo_id"] for s in bf16_nopup],
            [
                "black-forest-labs/flux-3-image-klein",
                "Falconsai/nsfw_image_detection",
            ],
        )
        self.assertIn("model.safetensors", bf16_nopup[0]["allow_patterns"])

        nvfp4_specs = schemas.build_hf_download_specs("nvfp4", True)
        self.assertIn("variants/nvfp4/*", nvfp4_specs[0]["allow_patterns"])

        with self.assertRaises(ValueError):
            schemas.build_hf_download_specs("int4", True)


if __name__ == "__main__":
    unittest.main()
