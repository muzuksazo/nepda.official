#!/usr/bin/env python3
"""Download real CC0 / open-source 3D assets for Zack D.-style Jet Umbrella short."""

from __future__ import annotations

import json
import os
import urllib.request

ROOT = "/Users/yun-yeowon/workspace/ad-studio/zackd-jet-umbrella"
ASSETS = os.path.join(ROOT, "assets")
HEADERS = {"User-Agent": "Antigravity-JetUmbrella-Studio/1.0"}


def _get_json(url: str) -> dict:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.loads(r.read().decode("utf-8"))


def _download(url: str, dst: str) -> int:
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if os.path.exists(dst) and os.path.getsize(dst) > 1024:
        return os.path.getsize(dst)
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=60) as r:
        data = r.read()
    with open(dst, "wb") as f:
        f.write(data)
    return len(data)


def fetch_polyhaven_gltf(asset_id: str, res: str = "1k") -> str:
    data = _get_json(f"https://api.polyhaven.com/files/{asset_id}")
    gltf_entry = data["gltf"][res]["gltf"]
    base_dir = os.path.join(ASSETS, asset_id)
    main_name = os.path.basename(gltf_entry["url"])
    main_path = os.path.join(base_dir, main_name)
    sz = _download(gltf_entry["url"], main_path)
    inc = gltf_entry.get("include", {})
    for rel_path, info in inc.items():
        _download(info["url"], os.path.join(base_dir, rel_path))
    print(f"[asset] PolyHaven glTF {asset_id}: {main_path} ({sz}B + {len(inc)} includes)")
    return main_path


def fetch_polyhaven_hdri(asset_id: str = "derelict_airfield_02", res: str = "2k") -> str:
    data = _get_json(f"https://api.polyhaven.com/files/{asset_id}")
    hdri_res = data["hdri"][res]
    fmt = "hdr" if "hdr" in hdri_res else ("exr" if "exr" in hdri_res else next(iter(hdri_res)))
    url = hdri_res[fmt]["url"]
    dst = os.path.join(ASSETS, f"{asset_id}_{res}.{fmt}")
    sz = _download(url, dst)
    print(f"[asset] PolyHaven HDRI {asset_id}: {dst} ({sz}B)")
    return dst


def fetch_polyhaven_pbr_asphalt(asset_id: str = "asphalt_pit_lane", res: str = "2k") -> None:
    data = _get_json(f"https://api.polyhaven.com/files/{asset_id}")
    mapping = [
        ("Diffuse", "asphalt_diff"),
        ("Rough", "asphalt_rough"),
        ("nor_gl", "asphalt_nor"),
    ]
    for key, out_stem in mapping:
        res_dict = data[key][res]
        fmt = "jpg" if "jpg" in res_dict else ("png" if "png" in res_dict else next(iter(res_dict)))
        url = res_dict[fmt]["url"]
        dst = os.path.join(ASSETS, f"{out_stem}.{fmt}")
        sz = _download(url, dst)
        print(f"[asset] PolyHaven PBR {asset_id}.{key}: {dst} ({sz}B)")


def main() -> None:
    os.makedirs(ASSETS, exist_ok=True)
    a350_path = os.path.join(ASSETS, "A350_nologo.glb")
    sz = _download(
        "https://raw.githubusercontent.com/amvlab/aircraft-models/main/models/A350_nologo.glb",
        a350_path,
    )
    print(f"[asset] A350_nologo.glb: {a350_path} ({sz}B)")

    fetch_polyhaven_hdri("derelict_airfield_02", "2k")
    fetch_polyhaven_pbr_asphalt("asphalt_pit_lane", "2k")
    for model_id in ("Barrel_01", "concrete_road_barrier", "vintage_suitcase"):
        fetch_polyhaven_gltf(model_id, "1k")


if __name__ == "__main__":
    main()
