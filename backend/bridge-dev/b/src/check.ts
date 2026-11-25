import type { DraftScenario, ProductInfoSchema } from "./schema.js";
import type { z } from "zod";

type ProductInfo = z.infer<typeof ProductInfoSchema>;

export interface CheckResult {
  errors: string[];
  warnings: string[];
}

const SIM_MIN = 0.4;
const SIM_MAX = 0.6;
const ADJ_MIN = 0.7;
/** B 훅 길이: 15~20초 안에서 내용에 맞게 (공통 문서의 15초 이하와 다름, B 전용) */
const MIN_HOOK_SEC = 15;
const MAX_HOOK_SEC = 20;
const CAPTION_LINE_WARN = 10;
const REVEAL_MAX_CHARS = 35;
const ANCHOR_WARN_CHARS = 30;
const SYLLABLES_PER_SEC = 7; // Edge TTS +25% 기준 대략치
const PAS_OPENERS =["하는 이유", "쏟아본 적", "바꿨어요"];

/** 제품명에서 반전 전 금지어를 뽑는다. 숫자가 섞인 토큰(60분 등)은 제외. */
export function productNameTokens(name: string): string[] {
  return name
    .split(/[\s()\[\]·,/]+/)
    .map((t) => t.trim())
    .filter((t) => t.length >= 2 && !/\d/.test(t));
}

/** B 유형 규칙(b/README.md "시나리오 생성 시 지켜야 할 유형 규칙")을 코드로 확인한다. */
export function checkScenario(s: DraftScenario, product: ProductInfo): CheckResult {
  const errors: string[] = [];
  const warnings: string[] = [];
  const spec = s.ad_spec;
  const beats = [...s.beats].sort((a, b) => a.order - b.order);

  // 길이
  const sum = Math.round(beats.reduce((acc, b) => acc + b.duration_sec, 0) * 100) / 100;
  if (s.hook_duration_sec < MIN_HOOK_SEC || s.hook_duration_sec > MAX_HOOK_SEC)
    errors.push(`hook_duration_sec ${s.hook_duration_sec}초 (${MIN_HOOK_SEC}~${MAX_HOOK_SEC}초여야 함)`);
  if (Math.abs(sum - s.hook_duration_sec) > 0.05) errors.push(`장면 길이 합 ${sum}초 ≠ hook_duration_sec ${s.hook_duration_sec}초`);
  if (beats.length < 3 || beats.length > 5) errors.push(`장면 수 ${beats.length}개 (3~5개여야 함)`);

  // 시작 유사도
  const h = spec.hook_similarity_score;
  if (h < SIM_MIN || h > SIM_MAX) errors.push(`hook_similarity_score ${h} (0.40~0.60이어야 함)`);

  // 브리지 경로: [시작, 브리지 1..2]
  const path = spec.bridge_path;
  const bridges = path.length - 1;
  if (bridges < 1 || bridges > 2) errors.push(`브리지 ${bridges}개 (1~2개여야 함, bridge_path = [시작, 브리지...])`);
  if (path[0] && Math.abs(path[0].sim_to_anchor - h) > 0.001)
    warnings.push(`bridge_path[0].sim_to_anchor ${path[0].sim_to_anchor} ≠ hook_similarity_score ${h}`);
  // 이야기 모드: 발단과 첫 전개는 비슷할 수 있다 → 전체로 올라가면 통과, 단계 사이 정체·소폭 하락은 경고
  if (path.length >= 2) {
    const first = path[0].sim_to_anchor, last = path[path.length - 1].sim_to_anchor;
    if (last - first < 0.1)
      errors.push(`이야기가 앵커 쪽으로 다가가지 않음: 발단 ${first} → 마지막 전개 ${last} (0.1 이상 올라야 함)`);
    for (let i = 1; i < path.length; i++)
      if (path[i].sim_to_anchor < path[i - 1].sim_to_anchor)
        warnings.push(`앵커 유사도가 잠깐 내려감: "${path[i - 1].word}"(${path[i - 1].sim_to_anchor}) → "${path[i].word}"(${path[i].sim_to_anchor})`);
  }
  if (path.length && beats.length !== path.length + 1)
    warnings.push(`장면 ${beats.length}개가 경로(시작+브리지 ${bridges}개+반전 = ${path.length + 1}개)와 다름`);
  if (spec.adjacent_min_sim < ADJ_MIN) errors.push(`adjacent_min_sim ${spec.adjacent_min_sim} (0.70 이상이어야 함)`);

  // 제품명 첫 등장 = 반전 장면(마지막)
  const last = beats[beats.length - 1];
  if (last && spec.product_first_mention_beat !== last.order)
    errors.push(`product_first_mention_beat ${spec.product_first_mention_beat} ≠ 마지막 장면 ${last.order}`);
  const taboo = [...new Set([...productNameTokens(product.name), ...spec.product_taboo_keywords])].filter(Boolean);
  for (const b of beats) {
    if (b.order >= spec.product_first_mention_beat) continue;
    const text = `${b.narration} ${b.caption}`;
    const hits = taboo.filter((w) => text.includes(w));
    if (hits.length) errors.push(`장면 ${b.order}에 반전 전 금지어: ${hits.join(", ")}`);
  }
  if (last && !productNameTokens(product.name).some((w) => last.narration.includes(w)))
    errors.push(`반전 장면 나레이션에 제품 이름이 없음`);

  // 반전 템플릿: "<제품>은 <특징>합니다. 그래서 <제품>이 뭐냐고요?"
  if (last) {
    const sentences = last.narration.split(/(?<=[.!?])\s+/).map((x) => x.trim()).filter(Boolean);
    const [feature, question] = sentences;
    if (sentences.length !== 2 || !question || !/^그래서 .+뭐냐고요\?$/.test(question))
      errors.push(`반전 나레이션 템플릿 위반: "<제품>은 <특징>합니다. 그래서 <제품>이 뭐냐고요?" 두 문장이어야 함`);
    if (feature) {
      const len = [...feature.replace(/\s/g, "")].length;
      if (len > REVEAL_MAX_CHARS) errors.push(`반전 특징 문장 ${len}자 (공백 제외 ${REVEAL_MAX_CHARS}자 이내, 핵심 특징 하나만)`);
      if (!/니다\.?$/.test(feature)) errors.push(`반전 특징 문장이 '~합니다'로 끝나지 않음`);
      if (/^그래서/.test(feature)) warnings.push(`반전 특징 문장은 "그래서" 없이 제품명으로 시작`);
    }
  }
  if ([...spec.anchor.replace(/\s/g, "")].length > ANCHOR_WARN_CHARS)
    warnings.push(`앵커(핵심 특징)가 김: ${[...spec.anchor.replace(/\s/g, "")].length}자`);
  for (const b of beats) {
    const len = [...b.narration.replace(/[\s.,!?]/g, "")].length;
    if (len > b.duration_sec * SYLLABLES_PER_SEC)
      warnings.push(`장면 ${b.order} 나레이션 ${len}자가 ${b.duration_sec}초에 비해 김 (TTS가 장면을 넘길 수 있음)`);
  }

  // 시작 장면
  const first = beats[0];
  if (first) {
    const pas = PAS_OPENERS.filter((p) => first.narration.includes(p) || first.caption.includes(p));
    if (pas.length) errors.push(`시작 장면에 PAS형 도입: ${pas.join(", ")}`);
    // 지식 설명형 평서문으로 시작 ("뉴턴은 ~했습니다."), 질문형 금지
    const opener = first.narration.trim().split(/(?<=[.!?])\s+/)[0] ?? "";
    if (/\?/.test(opener) || /알고 계셨|아시나요|아세요|일까요/.test(opener))
      errors.push(`시작이 질문형임: "${opener}" (지식 설명 평서문 "<주어>는 ~했습니다."로)`);
    if (!/\d/.test(first.caption) && !/[일이삼사오육칠팔구십백천만]/.test(first.narration))
      warnings.push(`시작 장면에 숫자가 안 보임`);
  }

  // 나레이션·자막
  for (const b of beats) {
    const isReveal = last && b.order === last.order; // 반전은 "뭐냐고요?"로 끝남 (위에서 따로 검사)
    if (!isReveal && !/니다[.!?]?$/.test(b.narration.trim())) errors.push(`장면 ${b.order} 나레이션이 '~습니다'체로 끝나지 않음`);
    if (/\d/.test(b.narration)) warnings.push(`장면 ${b.order} 나레이션에 아라비아 숫자 (한글로 읽히게 써야 함)`);
    const lines = b.caption.split("\n");
    if (lines.length > 2) errors.push(`장면 ${b.order} 자막 ${lines.length}줄 (2줄 이내)`);
    for (const line of lines)
      if ([...line].length > CAPTION_LINE_WARN) warnings.push(`장면 ${b.order} 자막 한 줄이 김: "${line}"`);
  }

  // 3D 장면 (Remotion + React Three Fiber로 옮길 수 있는지)
  const FORBIDDEN_3D = [/drei/i, /gltf|glb|\.obj\b|fbx/i, /텍스처|texture/i, /TextGeometry|3D 글자|글자를 띄|문구가 떠/i];
  for (const b of beats) {
    const sc = b.scene3d;
    if (!sc) continue; // 3D 명세는 컷 단계에서 만든다
    if (sc.objects.length < 1 || sc.objects.length > 4) errors.push(`장면 ${b.order} 3D 오브젝트 ${sc.objects.length}개 (1~4개)`);
    if (sc.motion.length < 2) errors.push(`장면 ${b.order} 움직임 ${sc.motion.length}단계 (2단계 이상)`);
    else {
      const start = Math.min(...sc.motion.map((m) => m.from));
      const end = Math.max(...sc.motion.map((m) => m.to));
      if (start > 0.2 || end < 0.8) errors.push(`장면 ${b.order} 움직임이 장면 전체를 덮지 않음 (${start}~${end})`);
    }
    const text3d = JSON.stringify(sc.objects) + JSON.stringify(sc.motion);
    const bad = FORBIDDEN_3D.filter((r) => r.test(text3d)).map(String);
    if (bad.length) errors.push(`장면 ${b.order} 3D에 쓸 수 없는 요소: ${bad.join(", ")}`);
    const reds = sc.objects.map((o) => o.color.toLowerCase()).filter((c) => /^#(?:e|f)[0-9a-f](?:[0-4][0-9a-f]){2}$/.test(c));
    const offAccent = reds.filter((c) => c !== "#e8322a" && c !== "#ff3b30");
    if (offAccent.length) warnings.push(`장면 ${b.order} 강조색이 #e8322a가 아님: ${offAccent.join(", ")}`);
    if (/\d/.test(b.caption) && !sc.counter) warnings.push(`장면 ${b.order} 자막에 숫자가 있는데 counter가 없음`);
  }

  // 사실 출처
  for (const f of spec.fact_sources)
    if (f.status.includes("확인 필요")) warnings.push(`출처 확인 필요: ${f.claim}`);

  return { errors, warnings };
}

/** 앞선 회차와 같은 시작 소재를 쓰면 경고. */
export function checkAgainstPrevious(s: DraftScenario, previous: unknown[]): string[] {
  const start = s.ad_spec.bridge_path[0]?.word;
  if (!start) return [];
  const used = previous
    .map((p) => (p as { ad_spec?: { bridge_path?: { word?: string }[] } })?.ad_spec?.bridge_path?.[0]?.word)
    .filter((w): w is string => typeof w === "string");
  return used.includes(start) ? [`앞선 회차와 같은 시작 소재: ${start}`] : [];
}
