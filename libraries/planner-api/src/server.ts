import http, { type IncomingMessage, type ServerResponse } from "node:http";
import { pathToFileURL } from "node:url";
import { loadConfig, type PlannerConfig } from "./config.js";
import { submitJobToWorker } from "./bridge.js";
import {
  compareProviders,
  planAdSpec,
  type ModelResolver,
  type PlanRequest,
} from "./planner.js";
import { resolvePlannerModel, type PlannerProviderName } from "./providers.js";
import { getActiveOidcToken } from "./wif.js";

function sendJson(res: ServerResponse, statusCode: number, body: unknown): void {
  const raw = JSON.stringify(body);
  res.writeHead(statusCode, {
    "content-type": "application/json; charset=utf-8",
    "content-length": Buffer.byteLength(raw),
  });
  res.end(raw);
}

async function readJsonBody(req: IncomingMessage): Promise<Record<string, unknown>> {
  const chunks: Buffer[] = [];
  let total = 0;
  for await (const chunk of req) {
    const buf = Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk);
    total += buf.length;
    if (total > 2_000_000) {
      throw new Error("Request body exceeds 2MB limit");
    }
    chunks.push(buf);
  }
  const text = Buffer.concat(chunks).toString("utf8").trim();
  if (!text) return {};
  return JSON.parse(text) as Record<string, unknown>;
}

export interface PlannerServerDeps {
  config?: PlannerConfig;
  modelResolver?: ModelResolver;
  fetchImpl?: typeof fetch;
}

export function createPlannerServer(deps: PlannerServerDeps = {}): http.Server {
  const cfg = deps.config ?? loadConfig();

  return http.createServer(async (req, res) => {
    const url = new URL(req.url ?? "/", `http://${req.headers.host ?? "localhost"}`);
    const method = (req.method ?? "GET").toUpperCase();

    try {
      const rawOidc = req.headers["x-vercel-oidc-token"];
      const reqOidcToken =
        typeof rawOidc === "string"
          ? rawOidc.trim()
          : Array.isArray(rawOidc)
            ? rawOidc[0]?.trim()
            : undefined;
      const effectiveResolver: ModelResolver | undefined =
        deps.modelResolver ??
        (reqOidcToken
          ? (p, m) => resolvePlannerModel(p, { modelId: m, config: cfg, oidcToken: reqOidcToken })
          : undefined);
      const hasWifConfig = Boolean(
        cfg.googleCloudProject &&
          cfg.gcpWorkloadIdentityProvider &&
          cfg.gcpServiceAccountEmail &&
          getActiveOidcToken({ requestToken: reqOidcToken })
      );

      if (method === "GET" && url.pathname === "/health") {
        return sendJson(res, 200, {
          status: "ok",
          providers: {
            anthropic: Boolean(cfg.anthropicApiKey),
            google: Boolean(hasWifConfig || cfg.googleVertexApiKey || cfg.googleApiKey),
          },
          googleAuthMode: hasWifConfig
            ? "vertex_wif"
            : cfg.googleVertexApiKey
              ? "vertex_api_key"
              : cfg.googleApiKey
                ? "ai_studio"
                : "none",
          models: {
            anthropic: cfg.anthropicModel,
            google: cfg.googleModel,
          },
          workerBaseUrl: cfg.workerBaseUrl,
        });
      }

      if (method === "POST" && url.pathname === "/v1/plan") {
        const body = await readJsonBody(req);
        const provider = (body.provider as PlannerProviderName | undefined) ?? "anthropic";
        const planReq = body.request as PlanRequest | undefined;
        if (!planReq?.projectId || !planReq?.productFacts || !planReq?.sourceVideo) {
          return sendJson(res, 400, {
            error: "request.{projectId, productFacts, sourceVideo, sourceDuration} are required",
          });
        }
        const result = await planAdSpec(planReq, {
          provider,
          modelId: typeof body.modelId === "string" ? body.modelId : undefined,
          config: cfg,
          modelResolver: effectiveResolver,
        });
        return sendJson(res, 200, result);
      }

      if (method === "POST" && url.pathname === "/v1/compare") {
        const body = await readJsonBody(req);
        const planReq = (body.request as PlanRequest | undefined) ?? (body as unknown as PlanRequest);
        if (!planReq?.projectId || !planReq?.productFacts || !planReq?.sourceVideo) {
          return sendJson(res, 400, {
            error: "projectId, productFacts, sourceVideo, sourceDuration are required",
          });
        }
        const compared = await compareProviders(planReq, {
          anthropicModel: typeof body.anthropicModel === "string" ? body.anthropicModel : undefined,
          googleModel: typeof body.googleModel === "string" ? body.googleModel : undefined,
          config: cfg,
          modelResolver: effectiveResolver,
        });
        return sendJson(res, 200, compared);
      }

      if (method === "POST" && url.pathname === "/v1/plan-and-render") {
        const body = await readJsonBody(req);
        const provider = (body.provider as PlannerProviderName | undefined) ?? "anthropic";
        const planReq = body.request as PlanRequest | undefined;
        if (!planReq?.projectId || !planReq?.productFacts || !planReq?.sourceVideo) {
          return sendJson(res, 400, {
            error: "request.{projectId, productFacts, sourceVideo, sourceDuration} are required",
          });
        }
        const planned = await planAdSpec(planReq, {
          provider,
          modelId: typeof body.modelId === "string" ? body.modelId : undefined,
          config: cfg,
          modelResolver: effectiveResolver,
        });
        const job = await submitJobToWorker(
          {
            campaignId: (body.campaignId as string | undefined) || planReq.projectId,
            specData: planned.spec,
            factsMarkdown: planReq.productFacts,
            sourceVideo: planReq.sourceVideo,
            resolution: (body.resolution as "360p" | "720p" | undefined) ?? "720p",
            dryRun: Boolean(body.dryRun ?? true),
            maxCredits: typeof body.maxCredits === "number" ? body.maxCredits : undefined,
          },
          { config: cfg, fetchImpl: deps.fetchImpl }
        );
        return sendJson(res, 202, { planned, workerJob: job });
      }

      return sendJson(res, 404, { error: `Not found: ${method} ${url.pathname}` });
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      return sendJson(res, 500, { error: message });
    }
  });
}

const isEntrypoint =
  typeof process !== "undefined" &&
  Array.isArray(process.argv) &&
  process.argv[1] &&
  import.meta.url === pathToFileURL(process.argv[1]).href;

if (isEntrypoint) {
  const cfg = loadConfig();
  const server = createPlannerServer({ config: cfg });
  server.listen(cfg.plannerPort, "127.0.0.1", () => {
    console.log(
      `[planner-ai-sdk] listening on http://127.0.0.1:${cfg.plannerPort} -> worker=${cfg.workerBaseUrl}`
    );
  });
}
