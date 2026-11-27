// 모델 이름으로 LLM 공급자를 고른다: "gemini-…" 은 Google(Vertex AI/WIF 또는 AI Studio GEMINI_API_KEY), 나머지는 Anthropic(Claude).
// 단계별 모델은 환경변수로 바꾼다: B_MODEL(시나리오), B_IDEA_MODEL(아이디어), B_SCENE_MODEL(3D 명세·장면 코드),
// B_QA_MODEL(화면 검수), B_RESEARCH_MODEL(제품 조사 — Gemini 사용 시 google_search 도구 포함).
import { anthropic } from "@ai-sdk/anthropic";
import { createGoogleGenerativeAI } from "@ai-sdk/google";
import { createGoogleVertex } from "@ai-sdk/google-vertex";
import type { LanguageModel } from "ai";
import { createWifAuthClient, getActiveOidcToken } from "./wif.js";

export type GeminiProvider =
  | ReturnType<typeof createGoogleGenerativeAI>
  | ReturnType<typeof createGoogleVertex>;

let cachedGoogleKey: string | null = null;
let google: GeminiProvider | null = null;

export function resetGeminiProvider(): void {
  cachedGoogleKey = null;
  google = null;
}

function isVertexEnabled(): boolean {
  const raw = (process.env.GOOGLE_GENAI_USE_VERTEXAI ?? "").trim().toLowerCase();
  return raw === "1" || raw === "true" || raw === "yes";
}

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

/** Gemini 공급자 (검색 같은 Google 도구를 쓸 때). Vertex AI(WIF) 또는 AI Studio를 자동 선택한다. */
export function geminiProvider(): GeminiProvider {
  if (isVertexEnabled()) {
    const project = process.env.GOOGLE_CLOUD_PROJECT?.trim();
    const location = process.env.GOOGLE_CLOUD_LOCATION?.trim() || "global";
    const provider = process.env.GCP_WORKLOAD_IDENTITY_PROVIDER?.trim();
    const saEmail = process.env.GCP_SERVICE_ACCOUNT_EMAIL?.trim();
    const vertexApiKey = process.env.GOOGLE_VERTEX_API_KEY?.trim();
    const hasWif = Boolean(provider && saEmail && project && getActiveOidcToken());

    if (hasWif && provider && saEmail && project) {
      const cacheKey = `vertex-wif:${project}:${location}:${provider}:${saEmail}`;
      if (!google || cachedGoogleKey !== cacheKey) {
        const authClient = createWifAuthClient({ provider, serviceAccountEmail: saEmail });
        google = createGoogleVertex({
          apiKey: "",
          project,
          location,
          googleAuthOptions: { authClient: authClient as never },
        });
        cachedGoogleKey = cacheKey;
      }
      return google;
    }

    if (vertexApiKey) {
      const cacheKey = `vertex-key:${project ?? ""}:${location}`;
      if (!google || cachedGoogleKey !== cacheKey) {
        google = createGoogleVertex({
          apiKey: vertexApiKey,
          ...(project ? { project } : {}),
          location,
        });
        cachedGoogleKey = cacheKey;
      }
      return google;
    }

    if (project) {
      const cacheKey = `vertex-adc:${project}:${location}`;
      if (!google || cachedGoogleKey !== cacheKey) {
        google = createGoogleVertex({
          apiKey: "",
          project,
          location,
        });
        cachedGoogleKey = cacheKey;
      }
      return google;
    }

    throw new Error(
      "GOOGLE_GENAI_USE_VERTEXAI=true 일 때 GOOGLE_CLOUD_PROJECT 또는 GOOGLE_VERTEX_API_KEY 가 필요합니다."
    );
  }

  const apiKey = process.env.GEMINI_API_KEY ?? process.env.GOOGLE_GENERATIVE_AI_API_KEY;
  if (!apiKey) throw new Error("b/.env 에 GEMINI_API_KEY 가 필요합니다 (Gemini 모델을 쓰려면).");
  const cacheKey = `studio:${apiKey.slice(-8)}`;
  if (!google || cachedGoogleKey !== cacheKey) {
    google = createGoogleGenerativeAI({ apiKey });
    cachedGoogleKey = cacheKey;
  }
  return google;
}

export function llm(modelId: string): LanguageModel {
  if (isGemini(modelId)) {
    return geminiProvider()(modelId);
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
