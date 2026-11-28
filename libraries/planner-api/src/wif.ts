import fs from "node:fs";

const CLOUD_PLATFORM_SCOPE = "https://www.googleapis.com/auth/cloud-platform";
const STS_TOKEN_URL = "https://sts.googleapis.com/v1/token";
const TOKEN_EXPIRY_BUFFER_MS = 60_000;
const FALLBACK_TTL_MS = 3_000_000;

interface CachedGcpToken {
  accessToken: string;
  expiresAtMs: number;
}

const tokenCache = new Map<string, CachedGcpToken>();

export interface OidcTokenOptions {
  requestToken?: string;
  env?: NodeJS.ProcessEnv;
}

/**
 * Resolve active OIDC JWT from request header, Vercel env, or Modal env/file.
 */
export function getActiveOidcToken(options: OidcTokenOptions = {}): string | undefined {
  const fromReq = options.requestToken?.trim();
  if (fromReq) return fromReq;

  const env = options.env ?? process.env;
  const fromVercelEnv = env.VERCEL_OIDC_TOKEN?.trim();
  if (fromVercelEnv) return fromVercelEnv;

  const modalTokenFile = env.MODAL_IDENTITY_TOKEN_FILE?.trim();
  if (modalTokenFile) {
    try {
      const fromFile = fs.readFileSync(modalTokenFile, "utf8").trim();
      if (fromFile) return fromFile;
    } catch {
      // Fall through to MODAL_IDENTITY_TOKEN if the file is unreadable.
    }
  }

  const fromModalEnv = env.MODAL_IDENTITY_TOKEN?.trim();
  return fromModalEnv || undefined;
}

export function normalizeStsAudience(provider: string): string {
  const trimmed = provider.trim();
  if (trimmed.startsWith("//iam.googleapis.com/")) return trimmed;
  return `//iam.googleapis.com/${trimmed.replace(/^\/+/, "")}`;
}

export interface WifExchangeOptions {
  provider: string;
  serviceAccountEmail: string;
  oidcToken: string;
  fetchImpl?: typeof fetch;
}

/**
 * Exchange an OIDC JWT via GCP STS and impersonate the target Service Account.
 */
export async function exchangeOidcForGcpAccessToken(
  options: WifExchangeOptions
): Promise<CachedGcpToken> {
  const provider = options.provider.trim();
  const serviceAccountEmail = options.serviceAccountEmail.trim();
  if (!provider) throw new Error("GCP_WORKLOAD_IDENTITY_PROVIDER is required for WIF.");
  if (!serviceAccountEmail) throw new Error("GCP_SERVICE_ACCOUNT_EMAIL is required for WIF.");

  const audience = normalizeStsAudience(provider);
  const cacheKey = `${audience}|${serviceAccountEmail}|${options.oidcToken.slice(-16)}`;
  const cached = tokenCache.get(cacheKey);
  if (cached && Date.now() < cached.expiresAtMs - TOKEN_EXPIRY_BUFFER_MS) {
    return cached;
  }

  const fetchFn = options.fetchImpl ?? fetch;
  const stsResp = await fetchFn(STS_TOKEN_URL, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      audience,
      grantType: "urn:ietf:params:oauth:grant-type:token-exchange",
      requestedTokenType: "urn:ietf:params:oauth:token-type:access_token",
      scope: CLOUD_PLATFORM_SCOPE,
      subjectTokenType: "urn:ietf:params:oauth:token-type:jwt",
      subjectToken: options.oidcToken,
    }),
  });
  if (!stsResp.ok) {
    const detail = await stsResp.text();
    throw new Error(`GCP STS token exchange failed (${stsResp.status}): ${detail}`);
  }
  const stsData = (await stsResp.json()) as { access_token?: string };
  if (!stsData.access_token) {
    throw new Error("GCP STS token exchange response did not include access_token.");
  }

  const impersonateUrl =
    `https://iamcredentials.googleapis.com/v1/projects/-/serviceAccounts/` +
    `${encodeURIComponent(serviceAccountEmail)}:generateAccessToken`;
  const iamResp = await fetchFn(impersonateUrl, {
    method: "POST",
    headers: {
      "content-type": "application/json",
      authorization: `Bearer ${stsData.access_token}`,
    },
    body: JSON.stringify({ scope: [CLOUD_PLATFORM_SCOPE] }),
  });
  if (!iamResp.ok) {
    const detail = await iamResp.text();
    throw new Error(`GCP IAM generateAccessToken failed (${iamResp.status}): ${detail}`);
  }
  const iamData = (await iamResp.json()) as { accessToken?: string; expireTime?: string };
  if (!iamData.accessToken) {
    throw new Error("GCP IAM generateAccessToken response did not include accessToken.");
  }

  const parsedExpireMs = iamData.expireTime ? Date.parse(iamData.expireTime) : Number.NaN;
  const result: CachedGcpToken = {
    accessToken: iamData.accessToken,
    expiresAtMs: Number.isFinite(parsedExpireMs) ? parsedExpireMs : Date.now() + FALLBACK_TTL_MS,
  };
  tokenCache.set(cacheKey, result);
  return result;
}

export interface WifAuthClient {
  getAccessToken(): Promise<{ token: string }>;
}

/**
 * Create a lightweight `GoogleAuthOptions.authClient` adapter for `@ai-sdk/google-vertex`.
 */
export function createWifAuthClient(options: {
  provider: string;
  serviceAccountEmail: string;
  requestToken?: string;
  env?: NodeJS.ProcessEnv;
  fetchImpl?: typeof fetch;
}): WifAuthClient {
  return {
    async getAccessToken(): Promise<{ token: string }> {
      const oidcToken = getActiveOidcToken({
        requestToken: options.requestToken,
        env: options.env,
      });
      if (!oidcToken) {
        throw new Error(
          "No OIDC token available (expected x-vercel-oidc-token, VERCEL_OIDC_TOKEN, MODAL_IDENTITY_TOKEN_FILE, or MODAL_IDENTITY_TOKEN)."
        );
      }
      const { accessToken } = await exchangeOidcForGcpAccessToken({
        provider: options.provider,
        serviceAccountEmail: options.serviceAccountEmail,
        oidcToken,
        fetchImpl: options.fetchImpl,
      });
      return { token: accessToken };
    },
  };
}

export function clearWifTokenCache(): void {
  tokenCache.clear();
}
