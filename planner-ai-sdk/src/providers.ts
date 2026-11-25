import { createAnthropic } from "@ai-sdk/anthropic";
import { createGoogleGenerativeAI } from "@ai-sdk/google";
import type { LanguageModel } from "ai";
import { loadConfig, type PlannerConfig } from "./config.js";

export type PlannerProviderName = "anthropic" | "google";

/**
 * Resolve a Vercel AI SDK LanguageModel for either Anthropic Claude or Google Gemini.
 * Accepts `GOOGLE_GENERATIVE_AI_API_KEY` or `GEMINI_API_KEY` so a single key works across both SDKs.
 */
export function resolvePlannerModel(
  provider: PlannerProviderName,
  options: { modelId?: string; config?: PlannerConfig } = {}
): { model: LanguageModel; modelId: string; provider: PlannerProviderName } {
  const cfg = options.config ?? loadConfig();

  if (provider === "anthropic") {
    if (!cfg.anthropicApiKey) {
      throw new Error(
        "ANTHROPIC_API_KEY is required when provider='anthropic'"
      );
    }
    const modelId = options.modelId?.trim() || cfg.anthropicModel;
    const anthropic = createAnthropic({ apiKey: cfg.anthropicApiKey });
    return { provider, modelId, model: anthropic(modelId) };
  }

  if (provider === "google") {
    if (!cfg.googleApiKey) {
      throw new Error(
        "GOOGLE_GENERATIVE_AI_API_KEY or GEMINI_API_KEY is required when provider='google'"
      );
    }
    const modelId = options.modelId?.trim() || cfg.googleModel;
    const google = createGoogleGenerativeAI({ apiKey: cfg.googleApiKey });
    return { provider, modelId, model: google(modelId) };
  }

  throw new Error(`Unsupported planner provider: ${String(provider)}`);
}
