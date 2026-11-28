import assert from "node:assert/strict";
import fs from "node:fs";
import http from "node:http";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { MockLanguageModelV4 } from "ai/test";
import { submitJobToWorker } from "../../libraries/planner-api/src/bridge.js";
import type { PlannerConfig } from "../../libraries/planner-api/src/config.js";
import { compareProviders, planAdSpec, type ModelResolver } from "../../libraries/planner-api/src/planner.js";
import { resolvePlannerModel } from "../../libraries/planner-api/src/providers.js";
import { AdSpecSchema, type AdSpec } from "../../libraries/planner-api/src/schema.js";
import { createPlannerServer } from "../../libraries/planner-api/src/server.js";
import {
  clearWifTokenCache,
  createWifAuthClient,
  getActiveOidcToken,
} from "../../libraries/planner-api/src/wif.js";

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

  const vtxRes = resolvePlannerModel("google", {
    config: {
      googleVertexApiKey: "AQ.DummyVertexTestKey123456",
      anthropicModel: "claude-sonnet-4-5",
      googleModel: "gemini-2.5-flash",
      workerBaseUrl: "http://127.0.0.1:8080",
      plannerPort: 8787,
    },
  });
  assert.equal(vtxRes.provider, "google");
  assert.equal(vtxRes.modelId, "gemini-2.5-flash");

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
  assert.throws(
    () =>
      resolvePlannerModel("google", {
        config: {
          anthropicModel: "claude-sonnet-4-5",
          googleModel: "gemini-3.5-flash",
          workerBaseUrl: "http://127.0.0.1:8080",
          plannerPort: 8787,
        },
      }),
    /GOOGLE_VERTEX_API_KEY/
  );
});

test("getActiveOidcToken resolves request header > Vercel env > Modal file > Modal env", () => {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "napda-oidc-"));
  const tokFile = path.join(tmpDir, "modal_oidc");
  try {
    fs.writeFileSync(tokFile, "eyJ.modal.file\n", "utf8");
    assert.equal(
      getActiveOidcToken({
        requestToken: "eyJ.req.hdr",
        env: { VERCEL_OIDC_TOKEN: "eyJ.vercel", MODAL_IDENTITY_TOKEN_FILE: tokFile },
      }),
      "eyJ.req.hdr"
    );
    assert.equal(
      getActiveOidcToken({
        env: { VERCEL_OIDC_TOKEN: "eyJ.vercel", MODAL_IDENTITY_TOKEN_FILE: tokFile },
      }),
      "eyJ.vercel"
    );
    assert.equal(
      getActiveOidcToken({
        env: { MODAL_IDENTITY_TOKEN_FILE: tokFile, MODAL_IDENTITY_TOKEN: "eyJ.modal.env" },
      }),
      "eyJ.modal.file"
    );
    assert.equal(
      getActiveOidcToken({
        env: { MODAL_IDENTITY_TOKEN: "eyJ.modal.env" },
      }),
      "eyJ.modal.env"
    );
  } finally {
    fs.rmSync(tmpDir, { recursive: true, force: true });
  }
});

test("resolvePlannerModel supports Vercel & Modal OIDC WIF with STS+IAM exchange and /health reporting", async () => {
  clearWifTokenCache();
  const seenUrls: string[] = [];
  const fakeFetch: typeof fetch = async (input) => {
    const url = typeof input === "string" ? input : input.toString();
    seenUrls.push(url);
    if (url === "https://sts.googleapis.com/v1/token") {
      return new Response(JSON.stringify({ access_token: "sts.tok" }), { status: 200 });
    }
    return new Response(
      JSON.stringify({
        accessToken: "ya29.wif-aisdk-token",
        expireTime: new Date(Date.now() + 3600_000).toISOString(),
      }),
      { status: 200 }
    );
  };

  const wifConfig: PlannerConfig = {
    googleCloudProject: "gentle-voltage-464223-h6",
    googleCloudLocation: "global",
    gcpWorkloadIdentityProvider:
      "projects/94766443061/locations/global/workloadIdentityPools/vercel-napda-pool/providers/modal-dltldn333",
    gcpServiceAccountEmail: "napda-vercel-wif@gentle-voltage-464223-h6.iam.gserviceaccount.com",
    anthropicModel: "claude-sonnet-4-5",
    googleModel: "gemini-3.5-flash",
    workerBaseUrl: "http://127.0.0.1:8080",
    plannerPort: 8787,
  };

  const resolved = resolvePlannerModel("google", {
    config: wifConfig,
    env: { MODAL_IDENTITY_TOKEN: "eyJ.modal.wif.jwt" },
    fetchImpl: fakeFetch,
  });
  assert.equal(resolved.provider, "google");
  assert.equal(resolved.modelId, "gemini-3.5-flash");

  const authClient = createWifAuthClient({
    provider: wifConfig.gcpWorkloadIdentityProvider!,
    serviceAccountEmail: wifConfig.gcpServiceAccountEmail!,
    env: { MODAL_IDENTITY_TOKEN: "eyJ.modal.wif.jwt" },
    fetchImpl: fakeFetch,
  });
  const first = await authClient.getAccessToken();
  const second = await authClient.getAccessToken();
  assert.equal(first.token, "ya29.wif-aisdk-token");
  assert.equal(second.token, "ya29.wif-aisdk-token");
  assert.equal(seenUrls.length, 2, "cached WIF access token should skip repeat STS+IAM round-trip");

  const srv = createPlannerServer({ config: wifConfig });
  await new Promise<void>((resolve) => srv.listen(0, "127.0.0.1", resolve));
  try {
    const addr = srv.address();
    assert.ok(addr && typeof addr === "object");
    const resp = await fetch(`http://127.0.0.1:${addr.port}/health`, {
      headers: { "x-vercel-oidc-token": "eyJ.req.header" },
    });
    const health = (await resp.json()) as {
      providers: { google: boolean };
      googleAuthMode: string;
    };
    assert.equal(health.providers.google, true);
    assert.equal(health.googleAuthMode, "vertex_wif");
  } finally {
    await new Promise<void>((resolve) => srv.close(() => resolve()));
  }
});
