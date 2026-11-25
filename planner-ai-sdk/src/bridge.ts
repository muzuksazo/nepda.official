import { loadConfig, type PlannerConfig } from "./config.js";
import type { AdSpec } from "./schema.js";

export interface SubmitWorkerJobInput {
  campaignId: string;
  specData: AdSpec;
  factsMarkdown: string;
  sourceVideo?: string;
  sourceObjectKey?: string;
  resolution?: "360p" | "720p";
  dryRun?: boolean;
  maxCredits?: number;
}

export interface WorkerJobSubmission {
  job_id: string;
  status: string;
  campaign_id: string;
}

function buildHeaders(config: PlannerConfig): Record<string, string> {
  const headers: Record<string, string> = { "content-type": "application/json" };
  if (config.workerBearerToken) {
    headers.authorization = `Bearer ${config.workerBearerToken}`;
  }
  return headers;
}

export async function checkWorkerHealth(
  options: { config?: PlannerConfig; fetchImpl?: typeof fetch } = {}
): Promise<Record<string, unknown>> {
  const cfg = options.config ?? loadConfig();
  const f = options.fetchImpl ?? fetch;
  const resp = await f(`${cfg.workerBaseUrl}/health`, {
    method: "GET",
    headers: buildHeaders(cfg),
  });
  if (!resp.ok) {
    throw new Error(`Worker health check failed (${resp.status}): ${await resp.text()}`);
  }
  return (await resp.json()) as Record<string, unknown>;
}

export async function submitJobToWorker(
  input: SubmitWorkerJobInput,
  options: { config?: PlannerConfig; fetchImpl?: typeof fetch } = {}
): Promise<WorkerJobSubmission> {
  const cfg = options.config ?? loadConfig();
  const f = options.fetchImpl ?? fetch;
  const resp = await f(`${cfg.workerBaseUrl}/v1/jobs`, {
    method: "POST",
    headers: buildHeaders(cfg),
    body: JSON.stringify({
      campaign_id: input.campaignId,
      spec_data: input.specData,
      facts_markdown: input.factsMarkdown,
      source_video: input.sourceVideo,
      source_object_key: input.sourceObjectKey,
      track_archetype: input.specData.track_archetype,
      resolution: input.resolution ?? "720p",
      dry_run: input.dryRun ?? false,
      max_credits: input.maxCredits,
    }),
  });
  if (!resp.ok) {
    throw new Error(`Worker submit failed (${resp.status}): ${await resp.text()}`);
  }
  return (await resp.json()) as WorkerJobSubmission;
}

export async function getWorkerJob(
  jobId: string,
  options: { config?: PlannerConfig; fetchImpl?: typeof fetch } = {}
): Promise<Record<string, unknown>> {
  const cfg = options.config ?? loadConfig();
  const f = options.fetchImpl ?? fetch;
  const resp = await f(`${cfg.workerBaseUrl}/v1/jobs/${encodeURIComponent(jobId)}`, {
    method: "GET",
    headers: buildHeaders(cfg),
  });
  if (!resp.ok) {
    throw new Error(`Worker job lookup failed (${resp.status}): ${await resp.text()}`);
  }
  return (await resp.json()) as Record<string, unknown>;
}
