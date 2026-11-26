#!/usr/bin/env bash
# Poly Haven 스튜디오 조명(HDRI, CC0) 1k 를 assets/polyhaven/hdri/ 에 받는다.
set -euo pipefail
D=assets/polyhaven/hdri; mkdir -p "$D"
for id in brown_photostudio_02 studio_small_09 photo_studio_loft_hall studio_country_hall cyclorama_hard_light monochrome_studio_02; do
  url=$(curl -s "https://api.polyhaven.com/files/$id" | python -c "import json,sys;print(json.load(sys.stdin)['hdri']['1k']['hdr']['url'])")
  curl -s -o "$D/${id}_1k.hdr" "$url" && echo "$id ok"
done
