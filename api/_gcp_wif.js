'use strict';

/**
 * Vercel OIDC -> GCP Workload Identity Federation (WIF) helper for Serverless Functions.
 *
 * Exchanges Vercel's short-lived OIDC JWT (`x-vercel-oidc-token` header or
 * `VERCEL_OIDC_TOKEN` env var) at GCP STS and impersonates the target service
 * account via IAM Credentials `generateAccessToken`, without static JSON keys.
 */

const CLOUD_PLATFORM_SCOPE = 'https://www.googleapis.com/auth/cloud-platform';
const STS_TOKEN_URL = 'https://sts.googleapis.com/v1/token';
const TOKEN_EXPIRY_BUFFER_MS = 60_000;
const FALLBACK_TTL_MS = 3_000_000;

/** @type {Map<string, { accessToken: string, expiresAtMs: number }>} */
const tokenCache = new Map();

function readHeaderCaseInsensitive(headers, targetName) {
  if (!headers || typeof headers !== 'object') return '';
  const direct = headers[targetName];
  if (typeof direct === 'string' && direct.trim()) return direct.trim();
  const lowerTarget = targetName.toLowerCase();
  for (const [key, value] of Object.entries(headers)) {
    if (key.toLowerCase() === lowerTarget && typeof value === 'string' && value.trim()) {
      return value.trim();
    }
  }
  return '';
}

function getVercelOidcToken(req) {
  const fromHeader = readHeaderCaseInsensitive(req && req.headers, 'x-vercel-oidc-token');
  if (fromHeader) return fromHeader;

  const fromEnv =
    typeof process.env.VERCEL_OIDC_TOKEN === 'string'
      ? process.env.VERCEL_OIDC_TOKEN.trim()
      : '';
  if (fromEnv) return fromEnv;

  throw new Error(
    'Missing Vercel OIDC token: expected x-vercel-oidc-token header or VERCEL_OIDC_TOKEN env var.'
  );
}

function normalizeStsAudience(provider) {
  const trimmed = String(provider || '').trim();
  if (trimmed.startsWith('//iam.googleapis.com/')) return trimmed;
  return `//iam.googleapis.com/${trimmed.replace(/^\/+/, '')}`;
}

async function getGcpAccessToken({
  req,
  provider = process.env.GCP_WORKLOAD_IDENTITY_PROVIDER,
  serviceAccountEmail = process.env.GCP_SERVICE_ACCOUNT_EMAIL,
} = {}) {
  if (!provider || !String(provider).trim()) {
    throw new Error('GCP_WORKLOAD_IDENTITY_PROVIDER is required.');
  }
  if (!serviceAccountEmail || !String(serviceAccountEmail).trim()) {
    throw new Error('GCP_SERVICE_ACCOUNT_EMAIL is required.');
  }

  const audience = normalizeStsAudience(provider);
  const cleanEmail = String(serviceAccountEmail).trim();
  const cacheKey = `${audience}|${cleanEmail}`;

  const cached = tokenCache.get(cacheKey);
  if (cached && Date.now() < cached.expiresAtMs - TOKEN_EXPIRY_BUFFER_MS) {
    return cached.accessToken;
  }

  const oidcToken = getVercelOidcToken(req);

  const stsResponse = await fetch(STS_TOKEN_URL, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      audience,
      grantType: 'urn:ietf:params:oauth:grant-type:token-exchange',
      requestedTokenType: 'urn:ietf:params:oauth:token-type:access_token',
      scope: CLOUD_PLATFORM_SCOPE,
      subjectTokenType: 'urn:ietf:params:oauth:token-type:jwt',
      subjectToken: oidcToken,
    }),
  });

  if (!stsResponse.ok) {
    const detail = await stsResponse.text();
    throw new Error(`GCP STS token exchange failed (${stsResponse.status}): ${detail}`);
  }

  const stsData = await stsResponse.json();
  const stsToken = stsData && stsData.access_token;
  if (!stsToken) {
    throw new Error('GCP STS token exchange response did not include access_token.');
  }

  const impersonateUrl =
    `https://iamcredentials.googleapis.com/v1/projects/-/serviceAccounts/` +
    `${encodeURIComponent(cleanEmail)}:generateAccessToken`;

  const iamResponse = await fetch(impersonateUrl, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${stsToken}`,
    },
    body: JSON.stringify({ scope: [CLOUD_PLATFORM_SCOPE] }),
  });

  if (!iamResponse.ok) {
    const detail = await iamResponse.text();
    throw new Error(`GCP IAM generateAccessToken failed (${iamResponse.status}): ${detail}`);
  }

  const iamData = await iamResponse.json();
  const accessToken = iamData && iamData.accessToken;
  if (!accessToken) {
    throw new Error('GCP IAM generateAccessToken response did not include accessToken.');
  }

  const parsedExpireMs = iamData.expireTime ? Date.parse(iamData.expireTime) : NaN;
  const expiresAtMs = Number.isFinite(parsedExpireMs)
    ? parsedExpireMs
    : Date.now() + FALLBACK_TTL_MS;

  tokenCache.set(cacheKey, { accessToken, expiresAtMs });
  return accessToken;
}

function buildVertexUrl({
  project = process.env.GOOGLE_CLOUD_PROJECT,
  location = process.env.GOOGLE_CLOUD_LOCATION || 'us-central1',
  model,
  action = 'generateContent',
} = {}) {
  if (!project || !String(project).trim()) {
    throw new Error('GOOGLE_CLOUD_PROJECT is required.');
  }
  if (!model || !String(model).trim()) {
    throw new Error('Vertex AI model is required.');
  }
  const cleanProject = String(project).trim();
  const cleanLocation = String(location || 'us-central1').trim();
  const cleanModel = String(model).trim();
  const cleanAction = String(action || 'generateContent').trim();
  const host =
    cleanLocation === 'global'
      ? 'aiplatform.googleapis.com'
      : `${cleanLocation}-aiplatform.googleapis.com`;

  return (
    `https://${host}/v1/projects/${encodeURIComponent(cleanProject)}` +
    `/locations/${encodeURIComponent(cleanLocation)}` +
    `/publishers/google/models/${encodeURIComponent(cleanModel)}:${encodeURIComponent(cleanAction)}`
  );
}

function withVertexLabels(payload = {}, extraLabels = {}) {
  const rawApp = (process.env.GCP_BILLING_APP_LABEL || 'napda')
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9_-]+/g, '-')
    .replace(/^[-_]+|[-_]+$/g, '')
    .slice(0, 63);
  const baseLabels = rawApp ? { app: rawApp } : {};
  return {
    ...payload,
    labels: {
      ...baseLabels,
      ...(extraLabels || {}),
      ...((payload && payload.labels) || {}),
    },
  };
}

module.exports = {
  getVercelOidcToken,
  getGcpAccessToken,
  buildVertexUrl,
  withVertexLabels,
};
