// 모델 이름으로 LLM 공급자를 고른다: "gemini-…" 은 Google(Gemini API, b/.env 의 GEMINI_API_KEY), 나머지는 Anthropic(Claude).
// 단계별 모델은 환경변수로 바꾼다: B_MODEL(시나리오), B_IDEA_MODEL(아이디어), B_SCENE_MODEL(3D 명세·장면 코드),
// B_QA_MODEL(화면 검수), B_RESEARCH_MODEL(제품 조사 — 웹 검색 도구가 Claude 전용이라 Claude 로 둔다).
import { anthropic } from "@ai-sdk/anthropic";
import { createGoogleGenerativeAI } from "@ai-sdk/google";
import type { LanguageModel } from "ai";

let google: ReturnType<typeof createGoogleGenerativeAI> | null = null;

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
