"""Kenney zip 에서 GLB 모델, 미리보기 PNG, License 만 꺼낸다 (경로 탈출 방지)."""
import json, os, sys, zipfile

src, dst = sys.argv[1], sys.argv[2]
summary = {}
for name in sorted(os.listdir(src)):
    if not name.endswith('.zip'):
        continue
    pack = name[:-4]
    out = os.path.join(dst, pack)
    os.makedirs(out, exist_ok=True)
    glb = png = 0
    with zipfile.ZipFile(os.path.join(src, name)) as z:
        for info in z.infolist():
            p = info.filename.replace('\\', '/')
            if info.is_dir() or '..' in p or p.startswith('/'):
                continue
            base = os.path.basename(p)
            low = p.lower()
            if low.endswith('.glb'):
                target = os.path.join(out, base)
                glb += 1
            elif low.endswith('.png') and (('preview' in low and '/' in p and 'isometric' not in low) or ('isometric/' in low and low.endswith('_se.png'))):
                os.makedirs(os.path.join(out, 'previews'), exist_ok=True)
                target = os.path.join(out, 'previews', base)
                png += 1
            elif base.lower().startswith('license'):
                target = os.path.join(out, 'License.txt')
            else:
                continue
            with z.open(info) as fsrc, open(target, 'wb') as fdst:
                fdst.write(fsrc.read())
    # GLB 가 텍스처를 외부 파일로 참조하는 팩도 있다 → Textures 폴더도 같이
    with zipfile.ZipFile(os.path.join(src, name)) as z:
        for info in z.infolist():
            p = info.filename.replace('\\', '/')
            low = p.lower()
            if info.is_dir() or '..' in p or p.startswith('/'):
                continue
            if '/glb' in low and low.endswith(('.png', '.jpg')):
                rel = p[low.index('/glb'):].split('/', 2)[-1]
                target = os.path.join(out, rel)
                os.makedirs(os.path.dirname(target), exist_ok=True)
                with z.open(info) as fsrc, open(target, 'wb') as fdst:
                    fdst.write(fsrc.read())
    summary[pack] = {'glb': glb, 'previews': png}
print(json.dumps(summary, indent=1))
print('total glb', sum(v['glb'] for v in summary.values()))
