"""Poly Pizza 에서 키워드별 상위 모델(GLB)을 받고, 제목·작가·라이선스를 catalog.json 에 남긴다."""
import concurrent.futures as cf
import html
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

OUT = sys.argv[1]
PER = int(sys.argv[2]) if len(sys.argv) > 2 else 3
UA = {"User-Agent": "Mozilla/5.0"}
KEYWORDS = [
    "prism", "light bulb", "lamp", "candle", "clock", "hourglass", "stopwatch", "calendar", "globe", "telescope",
    "microscope", "magnifying glass", "compass", "map", "book", "scroll", "paper", "pen", "pencil", "ruler",
    "apple", "bread", "coffee", "cup", "bottle", "coin", "money", "gold", "trophy", "key", "lock", "gear",
    "battery", "magnet", "lightning", "rocket", "planet", "sun", "moon", "star", "cloud", "umbrella", "fire",
    "computer", "laptop", "phone", "camera", "television", "radio", "car", "bicycle", "airplane", "ship", "train",
    "house", "factory", "tree", "flower", "chair", "desk", "bed", "piano", "guitar", "paint brush", "flask",
    "test tube", "beaker", "dna", "brain", "heart", "tooth", "pill", "syringe", "thermometer", "scale",
    "wheel", "watch", "arrow", "trash can", "box",
]


def get(url, timeout=30):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def search(kw):
    page = get("https://poly.pizza/search/" + urllib.parse.quote(kw)).decode("utf-8", "ignore")
    ids = []
    for m in re.findall(r'/m/([A-Za-z0-9_-]{6,})', page):
        if m not in ids:
            ids.append(m)
    return ids[:PER]


def model_info(mid):
    page = get(f"https://poly.pizza/m/{mid}").decode("utf-8", "ignore")
    glb = re.search(r'https://static\.poly\.pizza/[0-9a-f-]+\.glb', page)
    title = re.search(r"<title>(.*?)</title>", page, re.S)
    t = html.unescape(title.group(1)).split(" - ")[0].strip() if title else mid
    author = re.search(r"Free 3D Model By (.*?) - Poly Pizza", html.unescape(title.group(1))) if title else None
    lic = "CC0" if re.search(r"CC0|Public Domain", page) else ("CC-BY" if "Creative Commons Attribution" in page else "unknown")
    return {"id": mid, "title": t, "author": author.group(1).strip() if author else "", "license": lic,
            "url": f"https://poly.pizza/m/{mid}", "glb": glb.group(0) if glb else None}


def safe(s):
    return re.sub(r"[^A-Za-z0-9]+", "_", s).strip("_")[:40] or "model"


def main():
    os.makedirs(OUT, exist_ok=True)
    catalog_path = os.path.join(OUT, "catalog.json")
    catalog = json.load(open(catalog_path, encoding="utf-8")) if os.path.exists(catalog_path) else {}
    seen = {m["id"] for items in catalog.values() for m in items}
    for kw in KEYWORDS:
        if kw in catalog:
            continue
        try:
            ids = [i for i in search(kw) if i not in seen]
        except Exception as e:  # noqa: BLE001
            print(f"[skip] {kw}: search {e}")
            continue
        items = []
        def one(mid):
            info = model_info(mid)
            if not info["glb"]:
                return None
            fname = f"{safe(kw)}__{safe(info['title'])}__{mid}.glb"
            data = get(info["glb"], timeout=60)
            if data[:4] != b"glTF":
                return None
            open(os.path.join(OUT, fname), "wb").write(data)
            info.update(file=fname, bytes=len(data))
            return info
        with cf.ThreadPoolExecutor(3) as ex:
            for r in ex.map(lambda m: (lambda: one(m))() if True else None, ids):
                if r:
                    items.append(r)
                    seen.add(r["id"])
        catalog[kw] = items
        json.dump(catalog, open(catalog_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"{kw}: {len(items)} " + ", ".join(f"{i['title']}({i['license']})" for i in items), flush=True)
        time.sleep(0.3)
    n = sum(len(v) for v in catalog.values())
    print(f"done: {n} models")


if __name__ == "__main__":
    main()
