import { createAnthropic } from "@ai-sdk/anthropic";
import { createGoogleGenerativeAI } from "@ai-sdk/google";
import { createGoogleVertex } from "@ai-sdk/google-vertex";
import type { LanguageModel } from "ai";
import { loadConfig, type PlannerConfig } from "./config.js";
import { createWifAuthClient, getActiveOidcToken } from "./wif.js";

export type PlannerProviderName = "anthropic" | "google";

/**
 * Resolve a Vercel AI SDK LanguageModel for either Anthropic Claude or Google Gemini.
 * For Google, prefers OIDC WIF (`GCP_WORKLOAD_IDENTITY_PROVIDER` + `GCP_SERVICE_ACCOUNT_EMAIL` + OIDC token)
 * when configured, then Vertex AI Express (`GOOGLE_VERTEX_API_KEY`), then AI Studio (`GEMINI_API_KEY`).
 */
export function resolvePlannerModel(
  provider: PlannerProviderName,
  options: {
    modelId?: string;
    config?: PlannerConfig;
    oidcToken?: string;
    env?: NodeJS.ProcessEnv;
    fetchImpl?: typeof fetch;
  } = {}
): { model: LanguageModel; modelId: string; provider: PlannerProviderName } {
  const cfg = options.config ?? loadConfig(options.env);

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
    const modelId = options.modelId?.trim() || cfg.googleModel;
    const oidcToken = getActiveOidcToken({
      requestToken: options.oidcToken,
      env: options.env,
    });
    if (
      cfg.googleCloudProject &&
      cfg.gcpWorkloadIdentityProvider &&
      cfg.gcpServiceAccountEmail &&
      oidcToken
    ) {
      const authClient = createWifAuthClient({
        provider: cfg.gcpWorkloadIdentityProvider,
        serviceAccountEmail: cfg.gcpServiceAccountEmail,
        requestToken: options.oidcToken,
        env: options.env,
        fetchImpl: options.fetchImpl,
      });
      const vertex = createGoogleVertex({
        apiKey: "",
        project: cfg.googleCloudProject,
        location: cfg.googleCloudLocation || "global",
        googleAuthOptions: { authClient: authClient as never },
      });
      return { provider, modelId, model: vertex(modelId) };
    }
    if (cfg.googleVertexApiKey) {
      const vertex = createGoogleVertex({ apiKey: cfg.googleVertexApiKey });
      return { provider, modelId, model: vertex(modelId) };
    }
    if (cfg.googleApiKey) {
      const google = createGoogleGenerativeAI({ apiKey: cfg.googleApiKey });
      return { provider, modelId, model: google(modelId) };
    }
    throw new Error(
      "WIF (GOOGLE_CLOUD_PROJECT + GCP_WORKLOAD_IDENTITY_PROVIDER + GCP_SERVICE_ACCOUNT_EMAIL + OIDC token), GOOGLE_VERTEX_API_KEY, GOOGLE_GENERATIVE_AI_API_KEY, or GEMINI_API_KEY is required when provider='google'"
    );
  }

  throw new Error(`Unsupported planner provider: ${String(provider)}`);
}
