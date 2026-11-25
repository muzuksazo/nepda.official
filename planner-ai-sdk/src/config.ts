/** Runtime configuration for the Vercel AI SDK multi-provider planner. */

export interface PlannerConfig {
  anthropicApiKey?: string;
  googleApiKey?: string;
  anthropicModel: string;
  googleModel: string;
  workerBaseUrl: string;
  workerBearerToken?: string;
  plannerPort: number;
}

export function loadConfig(env: NodeJS.ProcessEnv = process.env): PlannerConfig {
  const rawPort = Number.parseInt(env.PLANNER_PORT ?? "8787", 10);
  return {
    anthropicApiKey: env.ANTHROPIC_API_KEY?.trim() || undefined,
    googleApiKey:
      env.GOOGLE_GENERATIVE_AI_API_KEY?.trim() ||
      env.GEMINI_API_KEY?.trim() ||
      undefined,
    anthropicModel: env.ANTHROPIC_MODEL?.trim() || "claude-sonnet-4-5",
    googleModel: env.GOOGLE_PLANNER_MODEL?.trim() || "gemini-3.5-flash",
    workerBaseUrl: (env.WORKER_BASE_URL?.trim() || "http://127.0.0.1:8080").replace(/\/+$/, ""),
    workerBearerToken: env.WORKER_BEARER_TOKEN?.trim() || undefined,
    plannerPort: Number.isFinite(rawPort) && rawPort > 0 ? rawPort : 8787,
  };
}
