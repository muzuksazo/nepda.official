import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { geminiProvider, llm, resetGeminiProvider } from "../src/llm.js";
import { clearWifTokenCache, createWifAuthClient, getActiveOidcToken } from "../src/wif.js";

function withEnv(overrides: Record<string, string | undefined>, fn: () => Promise<void> | void): Promise<void> | void {
  const prev = new Map<string, string | undefined>();
  for (const [k, v] of Object.entries(overrides)) {
    prev.set(k, process.env[k]);
    if (v === undefined) delete process.env[k];
    else process.env[k] = v;
  }
  const restore = () => {
    for (const [k, v] of prev.entries()) {
      if (v === undefined) delete process.env[k];
      else process.env[k] = v;
    }
    resetGeminiProvider();
  };
  try {
    const out = fn();
    if (out && typeof (out as Promise<void>).then === "function") {
      return (out as Promise<void>).finally(restore);
    }
    restore();
    return out;
  } catch (err) {
    restore();
    throw err;
  }
}

// 1) OIDC token priority: VERCEL_OIDC_TOKEN > MODAL_IDENTITY_TOKEN_FILE > MODAL_IDENTITY_TOKEN
{
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "napda-b-wif-"));
  const tokFile = path.join(tmpDir, "modal_oidc");
  try {
    fs.writeFileSync(tokFile, "eyJ.modal.file\n", "utf8");
    assert.equal(
      getActiveOidcToken({
        env: { VERCEL_OIDC_TOKEN: "eyJ.vercel", MODAL_IDENTITY_TOKEN_FILE: tokFile, MODAL_IDENTITY_TOKEN: "eyJ.modal" },
      }),
      "eyJ.vercel"
    );
    assert.equal(
      getActiveOidcToken({
        env: { MODAL_IDENTITY_TOKEN_FILE: tokFile, MODAL_IDENTITY_TOKEN: "eyJ.modal" },
      }),
      "eyJ.modal.file"
    );
    assert.equal(
      getActiveOidcToken({
        env: { MODAL_IDENTITY_TOKEN: "eyJ.modal" },
      }),
      "eyJ.modal"
    );
  } finally {
    fs.rmSync(tmpDir, { recursive: true, force: true });
  }
  console.log("OK getActiveOidcToken");
}

// 2) STS -> IAM Credentials exchange with mocked fetch
{
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
        accessToken: "ya29.modal-b-wif",
        expireTime: new Date(Date.now() + 3600_000).toISOString(),
      }),
      { status: 200 }
    );
  };
  const authClient = createWifAuthClient({
    provider: "projects/94766443061/locations/global/workloadIdentityPools/vercel-napda-pool/providers/modal-dltldn333",
    serviceAccountEmail: "napda-vercel-wif@gentle-voltage-464223-h6.iam.gserviceaccount.com",
    env: { MODAL_IDENTITY_TOKEN: "eyJ.modal.jwt" },
    fetchImpl: fakeFetch,
  });
  const first = await authClient.getAccessToken();
  const second = await authClient.getAccessToken();
  assert.equal(first.token, "ya29.modal-b-wif");
  assert.equal(second.token, "ya29.modal-b-wif");
  assert.equal(seenUrls.length, 2, "cached token should avoid repeat STS/IAM calls");
  console.log("OK createWifAuthClient");
}

// 3) llm() & geminiProvider() select Vertex AI WIF without GEMINI_API_KEY
await withEnv(
  {
    GEMINI_API_KEY: undefined,
    GOOGLE_GENERATIVE_AI_API_KEY: undefined,
    GOOGLE_VERTEX_API_KEY: undefined,
    GOOGLE_GENAI_USE_VERTEXAI: "true",
    GOOGLE_CLOUD_PROJECT: "gentle-voltage-464223-h6",
    GOOGLE_CLOUD_LOCATION: "global",
    GCP_WORKLOAD_IDENTITY_PROVIDER:
      "projects/94766443061/locations/global/workloadIdentityPools/vercel-napda-pool/providers/modal-dltldn333",
    GCP_SERVICE_ACCOUNT_EMAIL: "napda-vercel-wif@gentle-voltage-464223-h6.iam.gserviceaccount.com",
    MODAL_IDENTITY_TOKEN: "eyJ.modal.jwt",
  },
  () => {
    resetGeminiProvider();
    const model = llm("gemini-4-hydrogen");
    assert.equal(typeof model, "object");
    assert.equal((model as { modelId?: string }).modelId, "gemini-4-hydrogen");
    assert.match(String((model as { provider?: string }).provider ?? ""), /vertex/i);
    const prov = geminiProvider();
    assert.equal(typeof prov.tools.googleSearch, "function");
    assert.equal(typeof prov.tools.urlContext, "function");
    console.log("OK llm/geminiProvider Vertex WIF");
  }
);
