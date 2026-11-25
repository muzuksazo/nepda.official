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

test("AdSpecSchema accepts brainrot mechanism archetypes and defaults new taboo arrays", () => {
  const defaulted = AdSpecSchema.parse({
    ...sampleValidSpec(),
    a_genre_archetype: "brainrot_hypnosis",
  });
  assert.equal(defaulted.a_genre_archetype, "brainrot_hypnosis");
  assert.deepEqual(defaulted.category_taboo_keywords, []);
  assert.deepEqual(defaulted.reference_surface_taboo, []);

  const populated = AdSpecSchema.parse({
    ...sampleValidSpec(),
    a_genre_archetype: "deadpan_rhythmic_loop",
    category_taboo_keywords: ["욕실", "물기"],
    reference_surface_taboo: ["소다팝", "나사"],
  });
  assert.deepEqual(populated.category_taboo_keywords, ["욕실", "물기"]);
  assert.deepEqual(populated.reference_surface_taboo, ["소다팝", "나사"]);
});
