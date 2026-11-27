import assert from 'node:assert/strict';

const base = new URL(process.env.FRONTEND_URL || 'https://napda.vercel.app');
assert.equal(base.protocol, 'https:', 'Deployment URL must use HTTPS');
assert.ok(
  base.hostname === 'napda.vercel.app' ||
    base.hostname === 'napda-frontend.vercel.app' ||
    (base.hostname.startsWith('napda-frontend-') && base.hostname.endsWith('.vercel.app')),
  'Unexpected frontend deployment hostname',
);

async function request(path, status, contentType) {
  const url = new URL(path, base);
  assert.equal(url.origin, base.origin, 'Checks must stay on the frontend origin');
  const response = await fetch(url, { signal: AbortSignal.timeout(30_000) });
  assert.equal(response.status, status, `${path}: HTTP ${response.status}`);
  assert.ok(response.headers.get('content-type')?.includes(contentType), `${path}: wrong content type`);
  return response;
}

// Read-only checks; never create sessions, projects, payments or generated videos.
async function verify() {
  const html = await (await request('/', 200, 'text/html')).text();
  assert.match(html, /id=["']root["']/, 'React root is missing');
  const scripts = [...html.matchAll(/<script\b[^>]*\bsrc=["']([^"']+)["']/g)]
    .map((match) => match[1]).filter((src) => src.startsWith('/assets/'));
  assert.ok(scripts.length, 'Built frontend JavaScript is missing');
  for (const src of scripts) await request(src, 200, 'javascript');
  const health = await (await request('/health', 200, 'application/json')).json();
  assert.equal(health.status, 'ok', 'Backend health check failed');
  await request('/v1/auth/me', 401, 'application/json');
}

for (let attempt = 1; ; attempt++) {
  try {
    await verify();
    console.log(`Frontend assets and API proxy passed: ${base.origin}`);
    break;
  } catch (error) {
    if (attempt === 3) throw error;
    console.error(`Attempt ${attempt}/3 failed: ${error.message}`);
    await new Promise((resolve) => setTimeout(resolve, 5_000));
  }
}
