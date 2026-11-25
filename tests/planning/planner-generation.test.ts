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
