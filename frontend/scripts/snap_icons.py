"""Stratis 아이콘 경로를 24px 격자에 맞춘다 (선 굵기 2px의 중심이 정수 좌표에 오도록).
일반 모니터(1배율)에서 선이 픽셀 칸 사이에 걸쳐 자글자글해 보이는 것을 막는다.
- 가로/세로 직선의 양 끝 → 같은 정수로
- 곡선 끝점에서 접선이 수평/수직이면(원·둥근 모서리의 꼭대기·옆) 그 축만 정수로
- 끝점이 움직이면 그 끝점에 붙은 곡선 손잡이도 같은 만큼 옮겨 곡선 모양을 지킨다
사용:
  python3 scripts/snap_icons.py 'M3.27 8.23L19.88 2.47...'   새 아이콘 경로 하나를 맞춰 출력
  python3 scripts/snap_icons.py src/ui/icons/index.tsx out.json   파일 안 경로를 모두 맞춰 JSON으로 (확인용)
"""
import json, re, sys


TOK = re.compile(r'[MLHVCZ]|-?\d*\.?\d+(?:e-?\d+)?')


class P:
    __slots__ = ('x', 'y', 'tx', 'ty')

    def __init__(self, x, y):
        self.x, self.y, self.tx, self.ty = x, y, None, None


def parse(d):
    toks = TOK.findall(d)
    i, cmd = 0, None
    pool = {}

    def point(x, y):
        key = (round(x, 3), round(y, 3))
        if key not in pool:
            pool[key] = P(x, y)
        return pool[key]

    segs = []  # (type, start, [cp1, cp2], end)
    cur = start = None
    while i < len(toks):
        t = toks[i]
        if re.fullmatch(r'[MLHVCZ]', t):
            cmd = t
            i += 1
            if cmd == 'Z':
                segs.append(('Z', cur, None, start))
                cur = start
            continue
        if cmd == 'M':
            cur = start = point(float(toks[i]), float(toks[i + 1])); i += 2
            segs.append(('M', None, None, cur)); cmd = 'L'
        elif cmd == 'L':
            p = point(float(toks[i]), float(toks[i + 1])); i += 2
            segs.append(('L', cur, None, p)); cur = p
        elif cmd == 'H':
            p = point(float(toks[i]), cur.y); i += 1
            segs.append(('L', cur, None, p)); cur = p
        elif cmd == 'V':
            p = point(cur.x, float(toks[i])); i += 1
            segs.append(('L', cur, None, p)); cur = p
        elif cmd == 'C':
            c1 = [float(toks[i]), float(toks[i + 1])]
            c2 = [float(toks[i + 2]), float(toks[i + 3])]
            p = point(float(toks[i + 4]), float(toks[i + 5])); i += 6
            segs.append(('C', cur, [c1, c2], p)); cur = p
    return segs, list(pool.values())


def want(p, axis, target):
    attr = 't' + axis
    if getattr(p, attr) is None:
        setattr(p, attr, target)


def snap(d):
    segs, pts = parse(d)
    # 1) 가로/세로 직선
    for typ, a, cps, b in segs:
        if typ not in ('L', 'Z') or a is None or a is b:
            continue
        dx, dy = abs(a.x - b.x), abs(a.y - b.y)
        if dy < 0.35 and dx > 0.8:
            t = round((a.y + b.y) / 2)
            want(a, 'y', t); want(b, 'y', t)
        if dx < 0.35 and dy > 0.8:
            t = round((a.x + b.x) / 2)
            want(a, 'x', t); want(b, 'x', t)
    # 2) 곡선 끝의 수평/수직 접선
    for typ, a, cps, b in segs:
        if typ != 'C':
            continue
        for p, c in ((a, cps[0] if (cps[0][0], cps[0][1]) != (a.x, a.y) else cps[1]), (b, cps[1] if (cps[1][0], cps[1][1]) != (b.x, b.y) else cps[0])):
            tx, ty = c[0] - p.x, c[1] - p.y
            if abs(ty) <= 0.08 * abs(tx) and abs(tx) > 0.05:
                want(p, 'y', round(p.y))
            if abs(tx) <= 0.08 * abs(ty) and abs(ty) > 0.05:
                want(p, 'x', round(p.x))
    # 3) 옮기기
    delta = {}
    for p in pts:
        dx = (p.tx - p.x) if p.tx is not None else 0.0
        dy = (p.ty - p.y) if p.ty is not None else 0.0
        delta[id(p)] = (dx, dy)
    def moved(p):
        dx, dy = delta[id(p)]
        return p.x + dx, p.y + dy
    def fmt(v):
        s = f'{v:.4f}'.rstrip('0').rstrip('.')
        return '0' if s in ('-0', '') else s
    outd = []
    for typ, a, cps, b in segs:
        if typ == 'M':
            x, y = moved(b); outd.append(f'M{fmt(x)} {fmt(y)}')
        elif typ == 'L':
            x, y = moved(b); outd.append(f'L{fmt(x)} {fmt(y)}')
        elif typ == 'Z':
            outd.append('Z')
        else:
            ax, ay = delta[id(a)]; bx, by = delta[id(b)]
            c1 = (cps[0][0] + ax, cps[0][1] + ay)
            c2 = (cps[1][0] + bx, cps[1][1] + by)
            x, y = moved(b)
            outd.append(f'C{fmt(c1[0])} {fmt(c1[1])} {fmt(c2[0])} {fmt(c2[1])} {fmt(x)} {fmt(y)}')
    moved_count = sum(1 for p in pts if delta[id(p)] != (0.0, 0.0))
    return ''.join(outd), moved_count, len(pts)


if sys.argv[1].lstrip().startswith('M'):
    print(snap(sys.argv[1])[0])
    sys.exit(0)

src, out = sys.argv[1], sys.argv[2]
text = open(src, encoding='utf-8').read()
result = {}
for m in re.finditer(r"^  (\w+): \{\n(.*?)^  \},", text, re.M | re.S):
    name, body = m.group(1), m.group(2)
    entry = {}
    for key in ('d', 'detail'):
        mm = re.search(rf"^    {key}: '([^']*)'", body, re.M)
        if mm:
            new, moved, total = snap(mm.group(1))
            entry[key] = {'old': mm.group(1), 'new': new, 'moved': moved, 'total': total}
    result[name] = entry
json.dump(result, open(out, 'w'), ensure_ascii=False, indent=1)
for name, e in result.items():
    print(name, {k: f"{v['moved']}/{v['total']}" for k, v in e.items()})
