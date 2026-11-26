import { generateText, Output, type LanguageModel } from "ai";
import {
  BridgePayoffSchema,
  type AbstractLaw,
  type Beat,
  type BlindHookDraft,
  type DraftScenario,
  type ProductInfo,
} from "./schema.js";

const BRIDGE_SYSTEM_PROMPT = `당신은 Track A(무맥락 반전)의 '실물 착지' 작가입니다.
앞선 0~10초 무맥락 훅 뒤에 딱 1개의 담백한 실물 증명 비트(전체 훅 길이 <= 15초, 착지 비중 <= 55%)를 붙이세요.
규칙:
1) 반드시 product_info.verified_facts에 있는 사실만 사용하세요. 미검증 수치나 과장 표현('완벽 방수', '100% 효과', '기적의')을 쓰지 마세요.
2) C안식 스펙 나열('딱 좋아요', '가성비 끝장', '강력 추천') 금지 — 담백한 1문장으로 끝내세요.
3) 자막(caption)은 2줄 이하, 한 줄 22자 이내, 이모지 금지입니다.`;

export function buildBridgePrompt(hook: BlindHookDraft, product: ProductInfo, law: AbstractLaw, feedback?: string): string {
  const preSum = hook.pre_twist_beats.reduce((acc, b) => acc + b.duration_sec, 0);
  const maxPayoff = Math.min(Math.max(1.5, 15 - preSum), Math.max(1.5, (preSum * 0.55) / 0.45));
  const summary = hook.pre_twist_beats
    .map((b) => `  ${b.order}. [${b.role}] (${b.duration_sec}s) 화면="${b.visual}" / 대사="${b.narration}"`)
    .join("\n");
  const lines = [
    `앞선 무맥락 훅 제목: "${hook.hook_title}" (총 ${preSum.toFixed(1)}초, 장르: ${hook.a_genre_archetype})`,
    `추상 법칙: "${law.abstract_law}"`,
    "무맥락 비트 요약:",
    summary,
    "",
    `연결할 실제 제품: ${product.name}`,
    `핵심 검증 사실: ${law.core_verified_fact}`,
    "전체 verified_facts:",
    ...product.verified_facts.map((f) => `- ${f}`),
    "",
    `요청: payoff_beat.duration_sec는 ${Math.min(4.5, maxPayoff).toFixed(1)}초 이하(전체의 55% 이하, 총합 15초 이하)로 작성하고,`,
    "replacement_test_note에 왜 앞선 훅을 다른 제품에도 옮길 수 있는지 1줄로 설명하세요.",
  ];
  if (feedback) {
    lines.push("", "이전 시도 규칙 위반(반드시 수정):", feedback);
  }
  return lines.join("\n");
}

export async function generateBridgeAndAssemble(
  hook: BlindHookDraft,
  product: ProductInfo,
  law: AbstractLaw,
  model: LanguageModel,
  feedback?: string,
): Promise<DraftScenario> {
  const result = await generateText({
    model,
    system: BRIDGE_SYSTEM_PROMPT,
    prompt: buildBridgePrompt(hook, product, law, feedback),
    output: Output.object({ schema: BridgePayoffSchema }),
    maxOutputTokens: 4000,
  });
  const bridge = result.output;

  const preBeats: Beat[] = hook.pre_twist_beats.map((b, idx) => ({
    ...b,
    order: idx + 1,
  }));
  const payoffBeat: Beat = {
    order: preBeats.length + 1,
    role: "담백한 실물 착지",
    duration_sec: bridge.payoff_beat.duration_sec,
    visual: bridge.payoff_beat.visual,
    narration: bridge.payoff_beat.narration,
    caption: bridge.payoff_beat.caption,
  };
  const beats = [...preBeats, payoffBeat];

  const preSum = preBeats.reduce((a, b) => a + b.duration_sec, 0);
  const totalHook = Math.round((preSum + payoffBeat.duration_sec) * 100) / 100;
  const bodyDur = Math.max(12.0, Math.round((30.0 - totalHook) * 100) / 100);

  return {
    hook_title: hook.hook_title,
    hook_duration_sec: totalHook,
    body_duration_sec: bodyDur,
    replacement_test_note: bridge.replacement_test_note,
    beats,
    ad_spec: {
      track_archetype: "A_bgrade_reversal",
      a_genre_archetype: hook.a_genre_archetype,
      abstract_law: law.abstract_law,
      visual_style: hook.visual_style,
      product_taboo_keywords: law.product_taboo_keywords,
      category_taboo_keywords: law.category_taboo_keywords,
      reference_surface_taboo: law.reference_surface_taboo,
      silence_gap_sec: hook.silence_gap_sec,
      pre_twist_ratio: Math.round((preSum / totalHook) * 100) / 100,
      payoff_ratio: Math.round((payoffBeat.duration_sec / totalHook) * 100) / 100,
    },
  };
}
