"""Minimal client for calling the deployed Modal FLUX 3 Image Klein HTTP API."""

from __future__ import annotations

import argparse
import base64
import json
import os
import urllib.error
import urllib.request
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True, help="Modal web app base URL (no trailing slash)")
    parser.add_argument("--token", default=os.environ.get("MODAL_API_TOKEN", ""), help="Bearer token")
    parser.add_argument("--prompt", default="", help="Text prompt (required unless --health)")
    parser.add_argument("--image", action="append", default=[], help="Reference image path (max 10)")
    parser.add_argument("--boxes", default="", help="Optional JSON file containing bounding boxes")
    parser.add_argument("--width", type=int, default=None)
    parser.add_argument("--height", type=int, default=None)
    parser.add_argument("--steps", type=int, default=None)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--no-pup", action="store_true", help="Disable server Prompt Upsampler")
    parser.add_argument("--no-safety", action="store_true", help="Disable server safety check")
    parser.add_argument("--format", choices=["png", "jpeg", "webp"], default="png")
    parser.add_argument("--out", default="flux3_result.png")
    parser.add_argument("--health", action="store_true", help="Call GET /health only")
    args = parser.parse_args()

    base = args.url.rstrip("/")
    if args.health:
        with urllib.request.urlopen(f"{base}/health", timeout=30) as resp:
            print(resp.read().decode("utf-8"))
        return

    if not args.prompt.strip():
        raise SystemExit("--prompt is required unless --health is passed.")

    refs = [base64.b64encode(Path(p).expanduser().read_bytes()).decode("ascii") for p in args.image]
    boxes = json.loads(Path(args.boxes).read_text(encoding="utf-8")) if args.boxes else None
    body = {
        "prompt": args.prompt,
        "reference_images": refs,
        "boxes": boxes,
        "width": args.width,
        "height": args.height,
        "steps": args.steps,
        "seed": args.seed,
        "use_pup": not args.no_pup,
        "safety": not args.no_safety,
        "output_format": args.format,
    }
    headers = {"Content-Type": "application/json"}
    if args.token.strip():
        headers["Authorization"] = f"Bearer {args.token.strip()}"

    req = urllib.request.Request(
        f"{base}/v1/generate",
        data=json.dumps(body).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            result = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as err:
        detail = err.read().decode("utf-8", errors="replace")
        raise SystemExit(f"HTTP {err.code}: {detail}") from err

    out_path = Path(args.out).expanduser().resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(base64.b64decode(result["image_base64"]))
    meta = {k: v for k, v in result.items() if k != "image_base64"}
    print(json.dumps({"saved": str(out_path), **meta}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
