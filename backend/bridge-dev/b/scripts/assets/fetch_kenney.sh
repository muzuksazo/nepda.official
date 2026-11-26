#!/usr/bin/env bash
# Kenney 3D 팩(CC0)을 받아 assets/kenney/<팩>/ 에 GLB·미리보기·License 만 풀어 둔다.
#   bash scripts/assets/fetch_kenney.sh   (b/ 폴더에서)
set -euo pipefail
Z=assets/kenney/_zips; J=$(mktemp); mkdir -p "$Z"
PACKS="furniture-kit food-kit nature-kit space-kit city-kit-commercial city-kit-suburban car-kit survival-kit holiday-kit factory-kit train-kit watercraft-kit building-kit castle-kit fantasy-town-kit prototype-kit toy-car-kit mini-characters pirate-kit graveyard-kit modular-space-kit mini-shop mini-arena"
for n in $PACKS; do
  id=$(curl -sL -c "$J" -b "$J" -A "Mozilla/5.0" "https://kenney.nl/assets/$n" | grep -o "data-download-id='[0-9a-f]*'" | head -1 | cut -d"'" -f2)
  u=$(curl -s -c "$J" -b "$J" -A "Mozilla/5.0" -H "Referer: https://kenney.nl/assets/$n" "https://kenney.nl/download-link/$id" | python -c "import json,sys;print(json.load(sys.stdin).get('url',''))")
  [ -n "$u" ] && curl -sL -A "Mozilla/5.0" -o "$Z/$n.zip" "$u" && echo "$n ok"
done
python -I scripts/assets/kenney_extract.py "$Z" assets/kenney
rm -f "$Z"/*.zip && rmdir "$Z"
