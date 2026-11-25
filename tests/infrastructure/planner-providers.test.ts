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
