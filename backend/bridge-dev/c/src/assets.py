"""문제 장면에 쓰는 무료 3D 에셋 내려받기. 전부 CC0 이고 저장소에는 커밋하지 않는다(assets/ 는 .gitignore).

- Poly Haven (https://polyhaven.com, CC0): 테이블 나무 텍스처, 실내 HDRI, 소매 원단, 소품 모델
- Blender Human Base Meshes (https://www.blender.org/download/demo-files/, CC0): 손 모델

에셋이 없어도 장면은 단순한 기본 도형으로 만들어진다. 받아 두면 더 사실적으로 나온다.
"""
from __future__ import annotations

import json
import os
import urllib.request
import zipfile
from typing import Callable

USER_AGENT = "napda-hook-c-worker/0.1"
POLYHAVEN_API = "https://api.polyhaven.com/files/"
HUMAN_BASE_URL = "https://download.blender.org/demo/asset-bundles/human-base-meshes/human-base-meshes-bundle-v1.4.1.zip"

# 이름 → (종류, Poly Haven ID). blender_scene.py 가 같은 이름으로 찾는다.
POLYHAVEN = {
    "table_wood": ("texture", "oak_wood_planks"),
    "sleeve_fabric": ("texture", "jersey_melange"),
    "room_hdri": ("hdri", "poly_haven_studio"),
    "prop_vase": ("model", "ceramic_vase_01"),
    "prop_plant": ("model", "potted_plant_04"),
}
TEXTURE_MAPS = {"Diffuse": "diff", "Rough": "rough", "nor_gl": "nor_gl"}


def assets_dir() -> str:
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.environ.get("C_ASSETS_DIR") or os.path.join(here, "assets")


def _download(url: str, path: str) -> None:
    if os.path.exists(path) and os.path.getsize(path) > 0:
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    tmp = path + ".part"
    with urllib.request.urlopen(req, timeout=300) as r, open(tmp, "wb") as f:
        while chunk := r.read(1 << 20):
            f.write(chunk)
    os.replace(tmp, path)


def _files(asset_id: str) -> dict:
    req = urllib.request.Request(POLYHAVEN_API + asset_id, headers={"User-Agent": USER_AGENT})
    return json.load(urllib.request.urlopen(req, timeout=60))


def fetch_all(log: Callable[[str], None] = print, resolution: str = "2k") -> str:
    root = assets_dir()
    for name, (kind, asset_id) in POLYHAVEN.items():
        target = os.path.join(root, "polyhaven", name)
        log(f"Poly Haven {asset_id} ({kind}) → {target}")
        files = _files(asset_id)
        if kind == "hdri":
            _download(files["hdri"][resolution]["hdr"]["url"], os.path.join(target, "env.hdr"))
        elif kind == "texture":
            for key, short in TEXTURE_MAPS.items():
                _download(files[key][resolution]["jpg"]["url"], os.path.join(target, f"{short}.jpg"))
        else:
            blend = files["blend"]["1k"]["blend"]
            _download(blend["url"], os.path.join(target, "model.blend"))
            for rel, item in (blend.get("include") or {}).items():
                _download(item["url"], os.path.join(target, *rel.split("/")))
    hand_dir = os.path.join(root, "human_base")
    blend_path = os.path.join(hand_dir, "human_base_meshes_bundle.blend")
    if not os.path.exists(blend_path):
        log(f"Blender Human Base Meshes (약 50MB) → {hand_dir}")
        zip_path = os.path.join(hand_dir, "bundle.zip")
        _download(HUMAN_BASE_URL, zip_path)
        with zipfile.ZipFile(zip_path) as z:
            member = next(n for n in z.namelist() if n.endswith("human_base_meshes_bundle.blend"))
            with z.open(member) as src, open(blend_path, "wb") as dst:
                while chunk := src.read(1 << 20):
                    dst.write(chunk)
        os.remove(zip_path)
    log("에셋 준비 완료")
    return root
