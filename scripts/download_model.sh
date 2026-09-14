#!/usr/bin/env bash
set -euo pipefail

mkdir -p assets
MODEL_URL="${MODEL_URL:-https://raw.githubusercontent.com/hpfrei/body-anatomy-3d-viewer/main/public/body.glb}"

echo "Downloading complete anatomy model..."
curl -L --fail --retry 3 --output assets/body.glb "$MODEL_URL"

echo "Downloaded:"
ls -lh assets/body.glb
