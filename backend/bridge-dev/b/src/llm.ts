// 모델 이름으로 LLM 공급자를 고른다: "gemini-…" 은 Google(Gemini API, b/.env 의 GEMINI_API_KEY), 나머지는 Anthropic(Claude).
// 단계별 모델은 환경변수로 바꾼다: B_MODEL(시나리오), B_IDEA_MODEL(아이디어), B_SCENE_MODEL(3D 명세·장면 코드),
// B_QA_MODEL(화면 검수), B_RESEARCH_MODEL(제품 조사 — 웹 검색 도구가 Claude 전용이라 Claude 로 둔다).
import { anthropic } from "@ai-sdk/anthropic";
import { createGoogleGenerativeAI } from "@ai-sdk/google";
import type { LanguageModel } from "ai";

let google: ReturnType<typeof createGoogleGenerativeAI> | null = null;

/**
 * B_LLM 하나로 모든 LLM 단계 모델을 바꾼다 (예: B_LLM=gemini-4-hydrogen → Claude API 없이).
 * 켜면 .env 의 단계별 값(B_MODEL 등)보다 우선한다. 한 단계만 다르게 하려면 B_LLM_KEEP=B_QA_MODEL 처럼 그 이름을 적는다.
 */
export function applyLlmSwitch(): void {
  const m = process.env.B_LLM?.trim();
  if (!m) return;
  const keep = new Set((process.env.B_LLM_KEEP ?? "").split(",").map((x) => x.trim()).filter(Boolean));
  for (const k of ["B_MODEL", "B_IDEA_MODEL", "B_SCENE_MODEL", "B_QA_MODEL", "B_BODY_MODEL", "B_RESEARCH_MODEL"]) if (!keep.has(k)) process.env[k] = m;
}

export function isGemini(modelId: string): boolean {
  return /^gemini/i.test(modelId);
}

export function llm(modelId: string): LanguageModel {
  if (isGemini(modelId)) {
    const apiKey = process.env.GEMINI_API_KEY ?? process.env.GOOGLE_GENERATIVE_AI_API_KEY;
    if (!apiKey) throw new Error("b/.env 에 GEMINI_API_KEY 가 필요합니다 (Gemini 모델을 쓰려면).");
    google ??= createGoogleGenerativeAI({ apiKey });
    return google(modelId);
  }
  return anthropic(modelId);
}

export type Step = "idea" | "scenario" | "spec" | "code" | "qa" | "research";
type Level = "minimal" | "low" | "medium" | "high";
/** Gemini 생각 수준 기본값: 생각 토큰이 출력 요금이라 필요한 만큼만. B_GEMINI_THINK_<STEP> 로 바꿈 (예: B_GEMINI_THINK_CODE=high) */
const GEMINI_THINK: Record<Step, Level> = { idea: "low", scenario: "low", spec: "low", code: "medium", qa: "low", research: "low" };

/** 단계별 공급자 옵션: Claude 는 effort, Gemini 는 thinkingLevel */
export function stepOptions(step: Step, claudeEffort: "low" | "medium" | "high") {
  const env = process.env[`B_GEMINI_THINK_${step.toUpperCase()}`]?.trim() as Level | undefined;
  return {
    anthropic: { effort: claudeEffort },
    google: { thinkingConfig: { thinkingLevel: env || GEMINI_THINK[step] } },
  };
}
