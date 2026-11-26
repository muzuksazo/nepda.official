"""b/assets 안의 받은 에셋을 한 장짜리 HTML 갤러리로 (Kenney 미리보기 PNG + Poly Pizza 썸네일 + 라이선스)."""
import html
import json
import os
import re
import sys
import urllib.request

A = sys.argv[1]  # b/assets
UA = {"User-Agent": "Mozilla/5.0"}


def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
        return r.read()


# Poly Pizza: 제목·작가가 비어 있으면 페이지 og 태그로 채우고 썸네일(jpg)을 받는다
pp = os.path.join(A, "polypizza")
cat_path = os.path.join(pp, "catalog.json")
cat = json.load(open(cat_path, encoding="utf-8"))
os.makedirs(os.path.join(pp, "thumbs"), exist_ok=True)
for kw, items in cat.items():
    for m in items:
        if m["title"] == m["id"] or not m.get("author"):
            try:
                page = get(m["url"]).decode("utf-8", "ignore")
                t = re.search(r'og:title" content="([^"]+)"', page)
                if t:
                    full = html.unescape(t.group(1))
                    m["title"] = full.split(" - ")[0].strip()
                    by = re.search(r"By (.+?)(?: - |$)", full)
                    if by:
                        m["author"] = by.group(1).strip()
            except Exception:  # noqa: BLE001
                pass
        thumb = os.path.join(pp, "thumbs", m["id"] + ".jpg")
        if m.get("glb") and not os.path.exists(thumb):
            try:
                open(thumb, "wb").write(get(m["glb"].replace(".glb", ".jpg")))
            except Exception:  # noqa: BLE001
                pass
json.dump(cat, open(cat_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

cards = []
for kw, items in cat.items():
    for m in items:
        lic = m["license"]
        cards.append(
            f'<figure><img loading="lazy" src="polypizza/thumbs/{m["id"]}.jpg"><figcaption><b>{html.escape(kw)}</b> · {html.escape(m["title"])}'
            f'<br><span class="lic {"cc0" if lic == "CC0" else "by"}">{lic}</span> {html.escape(m.get("author", ""))}</figcaption></figure>'
        )
kenney = []
kd = os.path.join(A, "kenney")
for pack in sorted(os.listdir(kd)):
    pv = os.path.join(kd, pack, "previews")
    if not os.path.isdir(pv):
        continue
    files = sorted(os.listdir(pv))
    imgs = "".join(f'<img loading="lazy" title="{html.escape(f[:-4])}" src="kenney/{pack}/previews/{html.escape(f)}">' for f in files)
    kenney.append(f"<details><summary>{pack} <small>({len(files)}개)</small></summary><div class='grid small'>{imgs}</div></details>")
hd = sorted(os.listdir(os.path.join(A, "polyhaven", "hdri")))

page = f"""<!doctype html><html lang="ko"><head><meta charset="utf-8"><title>B 에셋 미리보기</title>
<style>
body{{font-family:system-ui,sans-serif;background:#141418;color:#eee;margin:24px}}
h2{{margin-top:32px}} small{{color:#999}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:10px}}
.grid.small{{grid-template-columns:repeat(auto-fill,minmax(90px,1fr))}}
figure{{margin:0;background:#1f1f25;border-radius:8px;overflow:hidden}} figure img{{width:100%;aspect-ratio:1;object-fit:cover;background:#2a2a31}}
figcaption{{font-size:12px;padding:6px}} .grid.small img{{width:100%;background:#2a2a31;border-radius:6px}}
.lic{{font-size:11px;padding:1px 5px;border-radius:4px}} .cc0{{background:#2d6a3e}} .by{{background:#7a5a18}}
details{{margin:6px 0}} summary{{cursor:pointer;font-weight:600}}
</style></head><body>
<h1>B 에셋 미리보기</h1>
<p>Poly Pizza {sum(len(v) for v in cat.values())}개 · Kenney {sum(len(os.listdir(os.path.join(kd, p, 'previews'))) for p in os.listdir(kd) if os.path.isdir(os.path.join(kd, p, 'previews')))}개 · Poly Haven 조명 {len(hd)}개.
<span class="lic cc0">CC0</span> 표시 없이 사용 가능 · <span class="lic by">CC-BY</span> 영상 설명 등에 작가 표기 필요</p>
<h2>Poly Pizza (키워드별 물건)</h2><div class="grid">{''.join(cards)}</div>
<h2>Kenney 3D 팩 (모두 CC0)</h2>{''.join(kenney)}
<h2>Poly Haven 조명 (CC0)</h2><p>{', '.join(hd)}</p>
</body></html>"""
open(os.path.join(A, "gallery.html"), "w", encoding="utf-8").write(page)
print("gallery written", len(cards), "poly pizza cards")
