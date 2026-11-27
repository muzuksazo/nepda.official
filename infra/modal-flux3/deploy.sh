#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_FILE="$SCRIPT_DIR/modal_app.py"
SECRET_NAME="${MODAL_FLUX3_SECRET:-flux3-klein-secrets}"
SKIP_DOWNLOAD=false

for arg in "$@"; do
  case "$arg" in
    --skip-download)
      SKIP_DOWNLOAD=true
      ;;
    -h|--help)
      cat <<EOF
Usage: $(basename "$0") [--skip-download]

Deploys official black-forest-labs/flux-3-image-klein to Modal.
Optional env overrides:
  MODAL_FLUX3_GPU=H100|H200|B200|L40S   (default: H100)
  MODAL_FLUX3_QUANT=fp8|""|nvfp4        (default: fp8; "" = bf16)
  MODAL_FLUX3_ENABLE_PUP=true|false     (default: true)
  MODAL_FLUX3_SCALEDOWN_SEC=300         (default: 300)
  HF_TOKEN=... MODAL_API_TOKEN=...      (if set, creates/updates Modal Secret "$SECRET_NAME")
EOF
      exit 0
      ;;
    *)
      echo "Unknown option: $arg" >&2
      exit 2
      ;;
  esac
done

if ! command -v modal >/dev/null 2>&1; then
  echo "ERROR: 'modal' CLI is not installed. Run: pip install modal && modal setup" >&2
  exit 1
fi

if ! modal profile current >/dev/null 2>&1; then
  echo "ERROR: Modal CLI is not authenticated. Run: modal setup" >&2
  exit 1
fi

if [ -n "${HF_TOKEN:-}" ]; then
  if [ -n "${MODAL_API_TOKEN:-}" ]; then
    modal secret create "$SECRET_NAME" --force \
      "HF_TOKEN=${HF_TOKEN}" \
      "MODAL_API_TOKEN=${MODAL_API_TOKEN}" >/dev/null
  else
    modal secret create "$SECRET_NAME" --force \
      "HF_TOKEN=${HF_TOKEN}" >/dev/null
  fi
  echo "Updated Modal Secret: $SECRET_NAME"
fi

echo "Config: gpu=${MODAL_FLUX3_GPU:-H100} quant=${MODAL_FLUX3_QUANT:-fp8} enable_pup=${MODAL_FLUX3_ENABLE_PUP:-true}"

if [ "$SKIP_DOWNLOAD" = false ]; then
  echo "[1/2] Syncing official weights to Modal Volume (${MODAL_FLUX3_VOLUME:-flux3-klein-weights})..."
  modal run "${APP_FILE}::download_weights"
else
  echo "[1/2] Skipping weight download (--skip-download)."
fi

echo "[2/2] Deploying Modal app (${MODAL_APP_NAME:-napda-flux3-klein})..."
modal deploy "$APP_FILE"

echo "Done. Copy the printed web URL above and test with:"
echo "  python $SCRIPT_DIR/client_example.py --url <MODAL_URL> --prompt \"a red fox in snow\" --out out.png"
