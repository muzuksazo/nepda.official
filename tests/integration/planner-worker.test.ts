import assert from "node:assert/strict";
import http from "node:http";
import test from "node:test";
import { MockLanguageModelV4 } from "ai/test";
import { submitJobToWorker } from "../../libraries/planner-api/src/bridge.js";
import type { PlannerConfig } from "../../libraries/planner-api/src/config.js";
import { compareProviders, planAdSpec, type ModelResolver } from "../../libraries/planner-api/src/planner.js";
import { resolvePlannerModel } from "../../libraries/planner-api/src/providers.js";
import { AdSpecSchema, type AdSpec } from "../../libraries/planner-api/src/schema.js";
import { createPlannerServer } from "../../libraries/planner-api/src/server.js";

import { sampleValidSpec, makeMockResolver } from "../support/planner.js";

test("createPlannerServer and bridge hand off inline spec_data to Python google-genai worker", async () => {
  const workerCalls: Array<{ path: string; body: Record<string, unknown>; auth?: string }> = [];
  const mockWorker = http.createServer(async (req, res) => {
    const chunks: Buffer[] = [];
    for await (const c of req) chunks.push(Buffer.isBuffer(c) ? c : Buffer.from(c));
    const parsed = chunks.length ? JSON.parse(Buffer.concat(chunks).toString("utf8")) : {};
    workerCalls.push({
      path: req.url ?? "",
      body: parsed,
      auth: req.headers.authorization,
    });
    const out = JSON.stringify({
      job_id: "job_worker_mock_01",
      status: "QUEUED",
      campaign_id: parsed.campaign_id,
    });
    res.writeHead(202, { "content-type": "application/json" });
    res.end(out);
  });

  await new Promise<void>((resolve) => mockWorker.listen(0, "127.0.0.1", resolve));
  const workerAddr = mockWorker.address() as { port: number };

  const cfg: PlannerConfig = {
    anthropicApiKey: "sk-ant-mock",
    googleApiKey: "AIzaMockKey",
    anthropicModel: "claude-sonnet-4-5",
    googleModel: "gemini-3.5-flash",
    workerBaseUrl: `http://127.0.0.1:${workerAddr.port}`,
    workerBearerToken: "worker-secret-token",
    plannerPort: 0,
  };

  const plannerServer = createPlannerServer({
    config: cfg,
    modelResolver: makeMockResolver({
      anthropic: sampleValidSpec({ project_id: "e2e-handoff", visual_style: "blender_3d_cutaway" }),
      google: sampleValidSpec(),
    }),
  });
  await new Promise<void>((resolve) => plannerServer.listen(0, "127.0.0.1", resolve));
  const plannerAddr = plannerServer.address() as { port: number };
  const baseUrl = `http://127.0.0.1:${plannerAddr.port}`;

  try {
    const hResp = await fetch(`${baseUrl}/health`);
    assert.equal(hResp.status, 200);
    const hJson = (await hResp.json()) as Record<string, unknown>;
    assert.equal(hJson.status, "ok");

    const prResp = await fetch(`${baseUrl}/v1/plan-and-render`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        provider: "anthropic",
        campaignId: "sponge-handoff-01",
        dryRun: true,
        request: {
          projectId: "sponge-handoff-01",
          productFacts: "- [F01] [VERIFIED] 천 원 소분 블록 스펀지",
          sourceVideo: "source/sponge_04_wipe.mp4",
          sourceDuration: 7.9,
          visualStyle: "blender_3d_cutaway",
        },
      }),
    });
    assert.equal(prResp.status, 202);
    const prJson = (await prResp.json()) as {
      planned: { spec: AdSpec };
      workerJob: { job_id: string };
    };
    assert.equal(prJson.workerJob.job_id, "job_worker_mock_01");
    assert.equal(workerCalls.length, 1);
    assert.equal(workerCalls[0].path, "/v1/jobs");
    assert.equal(workerCalls[0].auth, "Bearer worker-secret-token");
    assert.equal((workerCalls[0].body.spec_data as AdSpec).visual_style, "blender_3d_cutaway");

    // Direct submitJobToWorker check
    const direct = await submitJobToWorker(
      {
        campaignId: "direct-check",
        specData: sampleValidSpec(),
        factsMarkdown: "- [F01] [VERIFIED] test",
        dryRun: true,
      },
      { config: cfg }
    );
    assert.equal(direct.job_id, "job_worker_mock_01");
  } finally {
    await new Promise<void>((resolve) => plannerServer.close(() => resolve()));
    await new Promise<void>((resolve) => mockWorker.close(() => resolve()));
  }
});
