import assert from "node:assert/strict";
import http from "node:http";
import test from "node:test";
import { MockLanguageModelV4 } from "ai/test";
import { submitJobToWorker } from "../src/bridge.js";
import type { PlannerConfig } from "../src/config.js";
import { compareProviders, planAdSpec, type ModelResolver } from "../src/planner.js";
import { resolvePlannerModel } from "../src/providers.js";
import { AdSpecSchema, type AdSpec } from "../src/schema.js";
import { createPlannerServer } from "../src/server.js";

function sampleValidSpec(overrides: Partial<AdSpec> = {}): AdSpec {
  return {
    project_id: "test-sponge-b3d",
    output_stem: "ad_A_noir_b3d",
    title: "클레이 누아르 취조 반전",
    visual_style: "blender_clay_diorama",
    mode: "narrative_master",
    track_archetype: "A_bgrade_reversal",
    a_genre_archetype: "noir_interrogation",
    product_taboo_keywords: ["스펀지"],
    hook_window_sec: 9.2,
    framing_mode: "full-bleed",
    disclosure: "ai_assisted",
    source_video: "source/sponge_04_wipe.mp4",
    source_duration: 7.9,
    allow_static_intro: true,
    vo_audio: "audio/vo_master.wav",
    usps: [{ title: "소분 블록 흡수 스펀지", fact_ids: ["F01"] }],
    timeline: [
      {
        id: "H1",
        type: "flow_video",
        flow_unit_id: "A1_b3d",
        flow_ref_id: "R_A1_b3d",
        duration: 5.0,
        flow_ref_prompt: "Clay detective inspecting dry tile floor, zero readable text.",
        flow_video_prompt: "Slow push-in on clay diorama, zero readable text.",
      },
      { id: "STOP", type: "silence_gap", duration: 0.25, audio_owner: "silence" },
      {
        id: "P1",
        type: "source",
        src_start: 1.0,
        src_end: 6.0,
        audio_owner: "mute",
        fact_ids: ["F01"],
      },
    ],
    captions: [
      { start: 0, end: 4.9, text: "물기가 **1초 만에** 사라졌어" },
      { start: 5.3, end: 10.0, text: "비밀은 **소분 스펀지**입니다", is_cta: true },
    ],
    cta: { type: "comment_engagement", copy: "댓글로 확인하세요", fact_ids: ["F01"] },
    ...overrides,
  };
}

function makeMockResolver(specs: { anthropic?: AdSpec; google?: AdSpec }): ModelResolver {
  return (provider, modelId) => {
    const chosen = provider === "anthropic" ? specs.anthropic : specs.google;
    if (!chosen) {
      throw new Error(`Simulated error for ${provider}`);
    }
    const mock = new MockLanguageModelV4({
      provider: `mock.${provider}`,
      modelId: modelId ?? `mock-${provider}-model`,
      doGenerate: async () => ({
        content: [{ type: "text", text: JSON.stringify(chosen) }],
        finishReason: { unified: "stop", raw: undefined },
        usage: {
          inputTokens: { total: 42, noCache: 42, cacheRead: 0, cacheWrite: 0 },
          outputTokens: { total: 88, text: 88, reasoning: 0 },
        },
        warnings: [],
      }),
    });
    return { provider, modelId: modelId ?? `mock-${provider}-model`, model: mock };
  };
}

test("AdSpecSchema validates Blender 3D styles and rejects invalid a_genre_archetype", () => {
  const valid = AdSpecSchema.parse(sampleValidSpec());
  assert.equal(valid.visual_style, "blender_clay_diorama");

  assert.throws(() =>
    AdSpecSchema.parse({
      ...sampleValidSpec(),
      a_genre_archetype: "invalid_genre_name",
    })
  );
});

test("resolvePlannerModel supports Claude + Gemini key fallback and guards missing keys", () => {
  const cRes = resolvePlannerModel("anthropic", {
    config: {
      anthropicApiKey: "sk-ant-test",
      anthropicModel: "claude-sonnet-4-5",
      googleModel: "gemini-3.5-flash",
      workerBaseUrl: "http://127.0.0.1:8080",
      plannerPort: 8787,
    },
  });
  assert.equal(cRes.provider, "anthropic");
  assert.equal(cRes.modelId, "claude-sonnet-4-5");

  const gRes = resolvePlannerModel("google", {
    config: {
      googleApiKey: "AIzaDummyTestKey1234567890",
      anthropicModel: "claude-sonnet-4-5",
      googleModel: "gemini-3.5-flash",
      workerBaseUrl: "http://127.0.0.1:8080",
      plannerPort: 8787,
    },
  });
  assert.equal(gRes.provider, "google");
  assert.equal(gRes.modelId, "gemini-3.5-flash");

  assert.throws(
    () =>
      resolvePlannerModel("anthropic", {
        config: {
          anthropicModel: "claude-sonnet-4-5",
          googleModel: "gemini-3.5-flash",
          workerBaseUrl: "http://127.0.0.1:8080",
          plannerPort: 8787,
        },
      }),
    /ANTHROPIC_API_KEY/
  );
});

test("planAdSpec and compareProviders generate structured specs across Claude and Gemini mocks", async () => {
  const resolver = makeMockResolver({
    anthropic: sampleValidSpec({ project_id: "claude-pick", title: "클로드 느와르" }),
    google: sampleValidSpec({
      project_id: "gemini-pick",
      title: "제미나이 멜로",
      a_genre_archetype: "romance_breakup",
    }),
  });

  const single = await planAdSpec(
    {
      projectId: "sponge-single",
      productFacts: "- [F01] [VERIFIED] 천 원 소분 블록 스펀지",
      sourceVideo: "source/sponge_04_wipe.mp4",
      sourceDuration: 7.9,
      visualStyle: "blender_clay_diorama",
    },
    { provider: "anthropic", modelResolver: resolver }
  );
  assert.equal(single.spec.title, "클로드 느와르");

  const compared = await compareProviders(
    {
      projectId: "sponge-ab",
      productFacts: "- [F01] [VERIFIED] 천 원 소분 블록 스펀지",
      sourceVideo: "source/sponge_04_wipe.mp4",
      sourceDuration: 7.9,
    },
    { modelResolver: resolver }
  );
  assert.equal(compared.anthropic?.spec.a_genre_archetype, "noir_interrogation");
  assert.equal(compared.google?.spec.a_genre_archetype, "romance_breakup");
  assert.match(compared.summaryMarkdown, /mock-anthropic-model/);
  assert.match(compared.summaryMarkdown, /mock-google-model/);
});

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
