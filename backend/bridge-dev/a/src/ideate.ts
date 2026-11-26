import { generateText, Output, type LanguageModel } from "ai";
import type { ArchetypeDef } from "./archetypes.js";
import { BlindHookDraftSchema, type BlindHookDraft } from "./schema.js";

const IDEATE_SYSTEM_PROMPT = `당신은 Track A(무맥락 반전) 숏폼 훅 작가입니다.
당신에게 제품 정보는 전혀 주어지지 않으며, 추측해서도 안 됩니다.
오직 주어진 '추상 법칙' 1줄과 '장르 원형'만 사용해, 전혀 무관하지만 스크롤을 멈추게 만드는 6~10초짜리 도입부(2~4비트)를 창작하세요.
규칙:
1) 제공된 금칙어(tabooWords)나 생활용품·광고 클리셰("'속보입니다'", "'단 한 집만'", "'온 동네'")를 절대 쓰지 마세요.
2) 마지막 비트는 반드시 '패턴 인터럽트(예: 0.25초 무음 정지 또는 충격 정적)'로 끝내세요.
3) 나레이션은 자연스러운 구어체, 자막(caption)은 한 줄 22자 이내, 2줄 이내, 이모지 금지입니다.
4) 제품 소개나 해결책은 쓰지 마세요(Stage 3에서 결합합니다).`;

/**
 * Stage 2: TRUE BLIND IDEATION
 * ★ 불변 조건: 이 함수는 절대 product_info.name / category / verified_facts를 인자로 받지 않습니다.
 */
export function buildBlindHookPrompt(
  abstractLaw: string,
  archetype: ArchetypeDef,
  tabooWords: string[],
  feedback?: string,
): string {
  const lines = [
    `추상 법칙(이 법칙이 시각적으로 드러나야 함): "${abstractLaw}"`,
    `장르 원형: ${archetype.id} (${archetype.labelKo})`,
    `리텐션 원리: ${archetype.retentionPrinciple}`,
    `기본 비주얼 스타일: ${archetype.defaultVisualStyle}`,
    `안티-클리셰 주의: ${archetype.antiClicheHint}`,
    `절대 사용 금지 어휘(0%): ${tabooWords.length ? tabooWords.join(", ") : "(없음)"}`,
    "",
    "위 추상 법칙과 장르 원형만으로 제품과 무관한 6~10초 무맥락 도입부(pre_twist_beats 2~4개)를 작성하세요.",
    "silence_gap_sec는 0.18~0.32 사이로 설정하세요.",
  ];
  if (feedback) {
    lines.push("", "이전 시도에서 발견된 규칙 위반(반드시 수정하세요):", feedback);
  }
  return lines.join("\n");
}

export async function generateBlindHook(
  abstractLaw: string,
  archetype: ArchetypeDef,
  tabooWords: string[],
  model: LanguageModel,
  feedback?: string,
): Promise<BlindHookDraft> {
  const result = await generateText({
    model,
    system: IDEATE_SYSTEM_PROMPT,
    prompt: buildBlindHookPrompt(abstractLaw, archetype, tabooWords, feedback),
    output: Output.object({ schema: BlindHookDraftSchema }),
    maxOutputTokens: 8000,
  });
  return result.output;
}
