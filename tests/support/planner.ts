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

export function sampleValidSpec(overrides: Partial<AdSpec> = {}): AdSpec {
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

export function makeMockResolver(specs: { anthropic?: AdSpec; google?: AdSpec }): ModelResolver {
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
