import type { DraftScenario, ProductInfo } from "./schema.js";

export interface CheckResult {
  errors: string[];
  warnings: string[];
}

const MAX_HOOK_SEC = 15;
const MIN_SILENCE = 0.18;
const MAX_SILENCE = 0.32;
const MIN_PRE_TWIST_RATIO = 0.45;
const MAX_PAYOFF_RATIO = 0.55;
const MAX_CAPTION_CHARS = 22;

const RESKIN_CLICHES = ["속보입니다", "속보 입니다", "단 한 집만", "온 동네"];
const PAYOFF_CLICHES = ["딱 좋아요", "가성비 끝장", "가성비도 끝장", "강력 추천", "소개합니다", "꿀팁 공유"];
const UNVERIFIED_SUPERLATIVES = ["완벽 방수", "완전 방수", "100% 효과", "100% 보장", "기적의", "국내 최초", "세계 유일", "부작용 제로"];
const EMOJI_RE = /[\u{1F300}-\u{1F6FF}\u{1F900}-\u{1FAFF}\u{2600}-\u{27BF}]/u;

/** 제품명에서 반전 전 금지어 토큰을 뽑는다. 숫자가 섞인 토큰은 제외. */
export function productNameTokens(name: string): string[] {
  return name
    .split(/[\s()\[\]·,/]+/)
    .map((t) => t.trim())
    .filter((t) => t.length >= 2 && !/\d/.test(t));
}

/** Track A (무맥락 반전) 규칙을 결정론적으로 검사한다. */
export function checkScenario(s: DraftScenario, product?: ProductInfo): CheckResult {
  const errors: string[] = [];
  const warnings: string[] = [];
  const spec = s.ad_spec;
  const beats = [...s.beats].sort((a, b) => a.order - b.order);

  // 1) 길이 & 비트 구성
  const sum = Math.round(beats.reduce((acc, b) => acc + b.duration_sec, 0) * 100) / 100;
  if (s.hook_duration_sec > MAX_HOOK_SEC) {
    errors.push(`hook_duration_sec ${s.hook_duration_sec}초 > ${MAX_HOOK_SEC}초`);
  }
  if (Math.abs(sum - s.hook_duration_sec) > 0.05) {
    errors.push(`장면 길이 합 ${sum}초 ≠ hook_duration_sec ${s.hook_duration_sec}초`);
  }
  if (beats.length < 3 || beats.length > 5) {
    errors.push(`장면 수 ${beats.length}개 (3~5개여야 함)`);
  }

  // 2) 패턴 인터럽트 무음 정지 & 앞/뒤 비율
  if (spec.silence_gap_sec < MIN_SILENCE || spec.silence_gap_sec > MAX_SILENCE) {
    errors.push(`silence_gap_sec ${spec.silence_gap_sec}s (0.18~0.32s 범위여야 함)`);
  }
  if (spec.pre_twist_ratio < MIN_PRE_TWIST_RATIO) {
    errors.push(`pre_twist_ratio ${spec.pre_twist_ratio} < ${MIN_PRE_TWIST_RATIO} (무맥락 몰입 비중 45% 이상 필요)`);
  }
  if (spec.payoff_ratio > MAX_PAYOFF_RATIO) {
    errors.push(`payoff_ratio ${spec.payoff_ratio} > ${MAX_PAYOFF_RATIO} (반전 뒤 제품 착지 비중 55% 이하)`);
  }

  // 3) Double-Zero 반전 전 금칙어 스캔 (마지막 착지 비트를 제외한 모든 비트 검사)
  const nameTokens = product ? productNameTokens(product.name) : [];
  const tabooSet = new Set(
    [
      ...nameTokens,
      ...spec.product_taboo_keywords,
      ...spec.category_taboo_keywords,
      ...spec.reference_surface_taboo,
    ]
      .map((w) => w.trim().toLowerCase())
      .filter(Boolean),
  );

  const preTwistBeats = beats.slice(0, -1);
  for (const b of preTwistBeats) {
    const surface = `${b.visual} ${b.narration} ${b.caption}`.toLowerCase();
    const hits: string[] = [];
    for (const kw of tabooSet) {
      if (surface.includes(kw)) hits.push(kw);
    }
    if (hits.length) {
      errors.push(`반전 전 장면 ${b.order}에 금칙어/카테고리 누출: ${hits.join(", ")}`);
    }
    const reskinHits = RESKIN_CLICHES.filter((c) => surface.includes(c.toLowerCase()));
    if (reskinHits.length) {
      errors.push(`반전 전 장면 ${b.order}에 리스킨 뉴스 클리셰 사용: ${reskinHits.join(", ")}`);
    }
  }

  // 4) 착지 비트 C안식 스펙 나열 및 과장 문구 차단
  const last = beats[beats.length - 1];
  const factsJoined = (product?.verified_facts ?? []).join(" ");
  if (last) {
    const lastText = `${last.narration} ${last.caption}`;
    for (const cliche of PAYOFF_CLICHES) {
      if (lastText.includes(cliche)) {
        errors.push(`착지 장면 ${last.order}에 C안식 스펙 나열 문구 '${cliche}' 금지`);
      }
    }
    for (const sup of UNVERIFIED_SUPERLATIVES) {
      if (lastText.includes(sup) && !factsJoined.includes(sup)) {
        errors.push(`착지 장면 ${last.order}에 미검증 과장 표현 '${sup}' 포함`);
      }
    }
  }

  // 5) 자막 가독성 & 이모지 금지
  for (const b of beats) {
    const rawText = `${b.narration} ${b.caption}`;
    if (EMOJI_RE.test(rawText)) {
      errors.push(`장면 ${b.order}에 이모지 포함 (이모지 금지)`);
    }
    const lines = b.caption.split("\n");
    if (lines.length > 2) {
      errors.push(`장면 ${b.order} 자막 ${lines.length}줄 (최대 2줄)`);
    }
    for (const ln of lines) {
      const plain = ln.replace(/\*\*(.+?)\*\*/g, "$1").trim();
      if ([...plain].length > MAX_CAPTION_CHARS) {
        errors.push(`장면 ${b.order} 자막 한 줄 ${[...plain].length}자 > ${MAX_CAPTION_CHARS}자 ("${plain}")`);
      }
    }
  }

  if (!s.replacement_test_note.trim()) {
    warnings.push("replacement_test_note가 비어 있습니다.");
  }

  return { errors, warnings };
}

/** 회차 간 중복 장르(리스킨) 방지 검사 */
export function checkAgainstPrevious(s: DraftScenario, previousScenarios: unknown[]): string[] {
  const warningsOrErrs: string[] = [];
  const used = new Set<string>();
  for (const prev of previousScenarios) {
    if (prev && typeof prev === "object") {
      const g = ((prev as Record<string, unknown>).ad_spec as Record<string, unknown> | undefined)?.a_genre_archetype;
      if (typeof g === "string") used.add(g);
    }
  }
  if (used.has(s.ad_spec.a_genre_archetype)) {
    warningsOrErrs.push(`이전 회차와 동일한 장르 '${s.ad_spec.a_genre_archetype}' 반복 사용`);
  }
  return warningsOrErrs;
}
