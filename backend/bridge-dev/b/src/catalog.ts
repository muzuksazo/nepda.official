// 받아 둔 에셋(b/assets) 카탈로그와 검색. 서버 없이 파일 이름·제목으로 찾는다 (약 2,600개라 충분히 빠르다).
//   - 물건: Kenney 3D 팩(CC0) + Poly Pizza(모델마다 CC0/CC-BY)
//   - 인물: Quaternius 직업 캐릭터(CC0, 2~3등신, 동작 17개)
//   - 조명: Poly Haven HDRI(CC0)
// 3D 명세 단계는 물건을 영어 검색어로 적고(assets[].query), 코드가 여기서 실제 파일을 골라 장면 코드 프롬프트에 넘긴다.
import { existsSync, readdirSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const ASSETS = join(dirname(fileURLToPath(import.meta.url)), "../assets");

export interface AssetItem {
  /** 장면 코드에서 쓰는 경로 (예: bassets/kenney/furniture-kit/desk.glb) */
  file: string;
  name: string;
  tokens: string[];
  pack: string;
  license: "CC0" | "CC-BY" | "unknown";
  author?: string;
  url?: string;
}

/** Kenney 팩별 내용 (3D 명세 프롬프트에 넣는 요약) */
export const PACK_THEMES: Record<string, string> = {
  "building-kit": "집 벽·창문·문·지붕 조각",
  "car-kit": "자동차·트럭·버스·구급차·경찰차",
  "castle-kit": "성벽·탑·문·깃발",
  "city-kit-commercial": "상가·고층 건물",
  "city-kit-suburban": "주택·울타리·길",
  "factory-kit": "공장 컨베이어·기계·파이프·톱니",
  "fantasy-town-kit": "중세 마을 건물·우물·분수·랜턴",
  "food-kit": "음식·과일·채소·빵·음료·주방 도구 (200개)",
  "furniture-kit": "실내 가구·가전·창문 벽·러그·전등",
  "graveyard-kit": "묘지·울타리·돌",
  "holiday-kit": "눈 덮인 오두막·트리·선물",
  "mini-arena": "경기장·트로피·조각상",
  "mini-characters": "단순한 인물 인형·휠체어·짐",
  "mini-shop": "가게 진열대·과일·캔",
  "modular-space-kit": "우주 기지 복도·방",
  "nature-kit": "나무·풀·꽃·바위·절벽·버섯·다리·텐트·캠프 (329개)",
  "pirate-kit": "해적선·보트·상자·야자수·대포·성",
  "prototype-kit": "단순 블록·계단·벽(시제품용)",
  "space-kit": "우주선·로켓·위성·행성 지형·우주인 장비",
  "survival-kit": "캠핑 도구·통·도끼·모닥불",
  "toy-car-kit": "장난감 자동차·트랙",
  "train-kit": "기차·선로·역",
  "watercraft-kit": "보트·배·부표·부두",
};

/** 직업 캐릭터 (이야기 주인공으로 쓴다). 파일: bassets/uacp/<이름>.gltf */
export function characterNames(): string[] {
  const d = join(ASSETS, "quaternius/uacp");
  return existsSync(d) ? readdirSync(d).filter((f) => f.endsWith(".gltf")).map((f) => f.slice(0, -5)).sort() : [];
}

export function hdris(): string[] {
  const d = join(ASSETS, "polyhaven/hdri");
  return existsSync(d) ? readdirSync(d).filter((f) => f.endsWith(".hdr")).sort() : [];
}

function tokenize(s: string): string[] {
  return s
    .replace(/([a-z])([A-Z])/g, "$1 $2")
    .toLowerCase()
    .split(/[^a-z0-9]+/)
    .filter((t) => t.length > 1 && !/^\d+$/.test(t) && !/^[a-z]$/.test(t));
}

let cached: AssetItem[] | null = null;
export function loadCatalog(): AssetItem[] {
  if (cached) return cached;
  const items: AssetItem[] = [];
  const kd = join(ASSETS, "kenney");
  if (existsSync(kd))
    for (const pack of readdirSync(kd)) {
      const pd = join(kd, pack);
      if (!existsSync(pd)) continue;
      for (const f of readdirSync(pd).filter((x) => x.endsWith(".glb"))) {
        const name = f.slice(0, -4);
        items.push({ file: `bassets/kenney/${pack}/${f}`, name, tokens: tokenize(name), pack, license: "CC0" });
      }
    }
  const cp = join(ASSETS, "polypizza/catalog.json");
  if (existsSync(cp)) {
    const cat = JSON.parse(readFileSync(cp, "utf8")) as Record<string, { title: string; license: string; author?: string; url?: string; file?: string }[]>;
    for (const [kw, list] of Object.entries(cat))
      for (const m of list) {
        if (!m.file) continue;
        const lic = m.license === "CC0" ? "CC0" : m.license === "CC-BY" ? "CC-BY" : "unknown";
        items.push({ file: `bassets/polypizza/${m.file}`, name: m.title, tokens: [...new Set([...tokenize(m.title), ...tokenize(kw)])], pack: "polypizza", license: lic, author: m.author, url: m.url });
      }
  }
  cached = items;
  return items;
}

/** 영어 검색어 → 맞는 물건 (점수순). 이름 낱말이 겹칠수록, CC0일수록, 이름이 짧을수록(기본형) 위로 */
export function searchAssets(query: string, k = 3, opts: { packs?: string[] } = {}): AssetItem[] {
  const q = tokenize(query);
  if (!q.length) return [];
  const scored: { a: AssetItem; s: number }[] = [];
  for (const a of loadCatalog()) {
    if (opts.packs && !opts.packs.includes(a.pack)) continue;
    let s = 0;
    for (const t of q) {
      if (a.tokens.includes(t)) s += 2;
      else if (a.tokens.some((x) => x.startsWith(t) || t.startsWith(x))) s += 1;
      else if (t.endsWith("s") && a.tokens.includes(t.slice(0, -1))) s += 2;
    }
    if (s <= 0) continue;
    // 첫 검색어(핵심 명사)가 맞아야 높은 점수
    if (a.tokens.some((x) => x === q[0] || x === q[0].replace(/s$/, ""))) s += 1.5;
    if (a.license === "CC0") s += 0.3;
    s -= Math.max(0, a.tokens.length - q.length) * 0.15; // 수식어가 많은 변형보다 기본형
    scored.push({ a, s });
  }
  return scored.sort((x, y) => y.s - x.s).slice(0, k).map((x) => x.a);
}

/** 3D 명세 프롬프트에 넣는 에셋 요약 (어떤 종류의 물건이 있는지) */
export function catalogSummary(): string {
  const items = loadCatalog();
  const packs = Object.entries(PACK_THEMES)
    .map(([p, t]) => `- ${p}: ${t}`)
    .join("\n");
  const pp = [...new Set(items.filter((a) => a.pack === "polypizza").map((a) => a.name.toLowerCase()))].slice(0, 120).join(", ");
  return `물건 모델 (영어 검색어로 찾음):\n${packs}\n- polypizza(단품): ${pp}\n인물 캐릭터(bassets/uacp/<이름>.gltf): ${characterNames().join(", ")}`;
}
