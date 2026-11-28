// 로컬 풀스택 E2E 녹화: E2E-L08(위저드 예외·크레딧 부족 복귀) · E2E-L10(업로드 ffprobe 검증) · E2E-L12(썸네일 안전 영역·서명 URL Range)
// 실행: node tests/e2e_scripts/run_local_l08_l10_l12.mjs   (일부만: ONLY=08_local,12_local — L10·L12 는 L08 의 충전·완료 영상에 의존)
// 격리: 백엔드 :18084 · 프론트 :15177 · 목 플래너 :18789 · 임시 DB/출력 폴더. 과금 호출 없음(HOOK_WORKER_MODE=off, 목 플래너, Track A 로컬 템플릿).
// 결제는 Paddle Sandbox 결제창에서 Paddle 공개 테스트 카드(4242…)로 진행한다. backend/.env 의 PADDLE_* 샌드박스 값이 필요하다.
// 결과: tests/e2e_recordings/<이름>.mp4 + shots/<이름>/*.webp, 요약 JSON 은 E2E_ARTIFACT_DIR(기본: OS 임시 폴더).
import { spawn, spawnSync } from 'node:child_process';
import { existsSync, mkdirSync, mkdtempSync, rmSync, statSync, writeFileSync } from 'node:fs';
import { createServer } from 'node:http';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { chromium } from '../../frontend/node_modules/playwright/index.mjs';

const REPO_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..');
const ARTIFACT_DIR = process.env.E2E_ARTIFACT_DIR || path.join(tmpdir(), 'napda-e2e-artifacts');
const RECORDINGS_DIR = path.join(REPO_ROOT, 'tests', 'e2e_recordings');
const SHOTS_DIR = path.join(RECORDINGS_DIR, 'shots');
const TRACK_A_TEMPLATE_DIR = path.join(REPO_ROOT, 'backend', 'data', 'templates', 'track_a');
const RAW_VIDEO_DIR = path.join(ARTIFACT_DIR, 'scratch', 'raw_video_slow');
const THUMBS_DIR = path.join(ARTIFACT_DIR, 'scratch', 'thumbs_slow');

const BACKEND_PORT = 18084;
const FRONTEND_PORT = 15177;
const PLANNER_PORT = 18789;
const BACKEND_URL = `http://127.0.0.1:${BACKEND_PORT}`;
const FRONTEND_URL = `http://127.0.0.1:${FRONTEND_PORT}`;
const PLANNER_URL = `http://127.0.0.1:${PLANNER_PORT}`;
const PROD_URL = 'https://napda.vercel.app';
const VIEWPORT = { width: 432, height: 932 };

const FORBIDDEN_TEXT_TOKENS = ['payoff_1', 'twist_gap', '이 도마', '도마왕', 'OQ-', 'FR-', '미정', '예시 값'];

mkdirSync(RECORDINGS_DIR, { recursive: true });
mkdirSync(SHOTS_DIR, { recursive: true });
mkdirSync(RAW_VIDEO_DIR, { recursive: true });
mkdirSync(THUMBS_DIR, { recursive: true });

function assert(cond, msg) {
  if (!cond) throw new Error(`Assertion failed: ${msg}`);
}

async function assertNoForbiddenText(page, label, extraForbidden = []) {
  const text = await page.locator('body').innerText();
  for (const token of [...FORBIDDEN_TEXT_TOKENS, ...extraForbidden]) {
    assert(!text.includes(token), `[${label}] Forbidden text leak detected: "${token}"`);
  }
  return text;
}

async function waitForHttp(url, timeoutMs = 30000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      const res = await fetch(url);
      if (res.ok) return res;
    } catch {
      // Wait for startup
    }
    await new Promise((r) => setTimeout(r, 400));
  }
  throw new Error(`Timed out waiting for ${url}`);
}

function runPythonHelper(pyCode) {
  const proc = spawnSync(path.join(REPO_ROOT, '.venv/bin/python'), ['-c', pyCode], {
    cwd: REPO_ROOT,
    env: process.env,
    encoding: 'utf8',
  });
  if (proc.status !== 0) {
    throw new Error(`Python helper failed (${proc.status}): ${proc.stderr || proc.stdout}`);
  }
  return proc.stdout.trim();
}

function killTree(child) {
  if (!child || child.killed || child.pid === undefined) return;
  try {
    process.kill(-child.pid, 'SIGTERM');
  } catch {
    try {
      child.kill('SIGTERM');
    } catch {
      // ignore
    }
  }
}

/**
 * R2-06: Generate a visually rich animated studio product-demo MP4 (720x1280, 8.5s)
 * showing a sunlit countertop PVA sponge wiping away a glistening water spill (no solid navy test bars).
 */
function makeStudioProductDemoMp4(outPath, durationSec = 8.5) {
  runPythonHelper(`
import math, subprocess
from PIL import Image, ImageDraw, ImageFont

W, H = 720, 1280
FPS = 15
TOTAL_FRAMES = int(round(${durationSec} * FPS))
FONT_PATH = "/System/Library/Fonts/AppleSDGothicNeo.ttc"
f_badge = ImageFont.truetype(FONT_PATH, 26, index=6)
f_title = ImageFont.truetype(FONT_PATH, 46, index=6)
f_sub = ImageFont.truetype(FONT_PATH, 28, index=4)

# Pre-build sunlit stone countertop background
bg = Image.new("RGB", (W, H), (242, 238, 230))
bg_draw = ImageDraw.Draw(bg)
for y in range(H):
    t = y / H
    if t < 0.42:
        # Warm cream tiled backsplash wall
        r = int(248 - 14 * t)
        g = int(244 - 16 * t)
        b = int(236 - 18 * t)
    else:
        # Light terrazzo kitchen countertop surface
        u = (t - 0.42) / 0.58
        r = int(234 - 24 * u)
        g = int(231 - 24 * u)
        b = int(226 - 22 * u)
    bg_draw.line([(0, y), (W, y)], fill=(r, g, b))

# Subtle backsplash tile grid lines
for x in range(0, W, 120):
    bg_draw.line([(x, 0), (x, int(H * 0.42))], fill=(230, 224, 214), width=2)
for y in range(0, int(H * 0.42), 110):
    bg_draw.line([(0, y), (W, y)], fill=(230, 224, 214), width=2)
bg_draw.line([(0, int(H * 0.42)), (W, int(H * 0.42))], fill=(200, 194, 184), width=4)

# Soft sunlight beam diagonal
sun = Image.new("RGBA", (W, H), (0, 0, 0, 0))
sd = ImageDraw.Draw(sun)
sd.polygon([(0, 0), (460, 0), (W, 740), (220, 740)], fill=(255, 252, 235, 38))
bg = Image.alpha_composite(bg.convert("RGBA"), sun).convert("RGB")

# Background decorative ceramic mug & plant pot on counter
bg_d = ImageDraw.Draw(bg)
bg_d.rounded_rectangle([520, 390, 650, 565], radius=24, fill=(214, 224, 210), outline=(185, 198, 180), width=3)
bg_d.ellipse([540, 310, 635, 420], fill=(116, 162, 108))
bg_d.ellipse([505, 335, 585, 415], fill=(96, 145, 92))
bg_d.rounded_rectangle([70, 440, 175, 555], radius=20, fill=(250, 248, 244), outline=(215, 210, 202), width=3)

cmd = [
    "ffmpeg", "-y",
    "-f", "rawvideo", "-vcodec", "rawvideo",
    "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
    "-f", "lavfi", "-i", f"anullsrc=r=44100:cl=stereo:d=${durationSec}",
    "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", "-r", "30",
    "-c:a", "aac", "-shortest",
    "${outPath.replace(/\\/g, '\\\\')}",
]
proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)

for i in range(TOTAL_FRAMES):
    p = i / max(1, TOTAL_FRAMES - 1)
    frame = bg.copy().convert("RGBA")
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)

    # Ease-in-out sponge swipe progress (starts at p=0.12, finishes wiping water by p=0.72)
    wipe = max(0.0, min(1.0, (p - 0.12) / 0.60))
    wipe_ease = 0.5 - 0.5 * math.cos(math.pi * wipe)

    # Water spill puddle shrinks smoothly as PVA sponge glides across
    puddle_left = int(95 + 470 * wipe_ease)
    puddle_right = 610
    if puddle_right - puddle_left > 24:
        od.ellipse([puddle_left, 720, puddle_right, 930], fill=(82, 178, 238, 150), outline=(165, 224, 255, 200), width=4)
        # Water specular highlights
        hl_w = max(16, int((puddle_right - puddle_left) * 0.35))
        od.ellipse([puddle_left + 26, 752, puddle_left + 26 + hl_w, 796], fill=(235, 250, 255, 165))

    # Clean dry sparkle trail behind sponge
    if wipe_ease > 0.18:
        sparkle_alpha = int(220 * min(1.0, (wipe_ease - 0.18) / 0.35))
        for sx, sy, sr in [(175, 790, 20), (280, 860, 15), (390, 775, 22), (485, 845, 17)]:
            if sx < puddle_left - 25:
                od.line([(sx - sr, sy), (sx + sr, sy)], fill=(255, 255, 255, sparkle_alpha), width=4)
                od.line([(sx, sy - sr), (sx, sy + sr)], fill=(255, 255, 255, sparkle_alpha), width=4)

    # 3D-styled PVA sponge block gliding across countertop
    sp_x = int(75 + 410 * wipe_ease)
    sp_y = int(705 + 14 * math.sin(p * math.pi * 4))
    # Drop shadow
    od.rounded_rectangle([sp_x + 12, sp_y + 135, sp_x + 215, sp_y + 185], radius=24, fill=(60, 56, 48, 65))
    # Sponge side body (deep golden yellow)
    od.rounded_rectangle([sp_x, sp_y + 28, sp_x + 205, sp_y + 165], radius=26, fill=(236, 188, 38, 255), outline=(196, 148, 18, 255), width=3)
    # Sponge top face (bright PVA yellow with micro-pores)
    od.rounded_rectangle([sp_x, sp_y, sp_x + 205, sp_y + 128], radius=26, fill=(252, 214, 72, 255), outline=(218, 172, 32, 255), width=3)
    for px in range(sp_x + 24, sp_x + 190, 26):
        for py in range(sp_y + 22, sp_y + 112, 24):
            od.ellipse([px, py, px + 7, py + 7], fill=(224, 176, 36, 180))
    # Ridged grooves on PVA sponge
    for gy in range(sp_y + 24, sp_y + 115, 28):
        od.line([(sp_x + 14, gy), (sp_x + 191, gy)], fill=(235, 186, 42, 130), width=3)

    # Studio product badge at top
    od.rounded_rectangle([54, 108, 344, 162], radius=27, fill=(24, 24, 24, 215))
    od.text((82, 121), "3초 초흡수 테스트", fill=(214, 255, 63, 255), font=f_badge)
    od.text((54, 188), "초흡수 PVA 물걸레 스펀지", fill=(28, 28, 28, 240), font=f_title)
    status_lbl = "물기 잔여량 0% · 한 번에 싹 흡수" if wipe_ease > 0.82 else f"실시간 물기 흡수율 {int(wipe_ease * 100)}%"
    od.text((54, 252), status_lbl, fill=(75, 80, 88, 235), font=f_sub)

    comp = Image.alpha_composite(frame, overlay).convert("RGB")
    proc.stdin.write(comp.tobytes())

proc.stdin.close()
stderr = proc.stderr.read().decode("utf-8", errors="replace")
ret = proc.wait()
if ret != 0:
    raise RuntimeError(f"ffmpeg studio demo failed ({ret}): {stderr}")
print("STUDIO_DEMO_OK")
`);
}

function transcodeToMp4(webmPath, mp4Path) {
  const proc = spawnSync(
    'ffmpeg',
    [
      '-y',
      '-i',
      webmPath,
      '-c:v',
      'libx264',
      '-preset',
      'fast',
      '-crf',
      '23',
      '-pix_fmt',
      'yuv420p',
      '-movflags',
      '+faststart',
      mp4Path,
    ],
    { encoding: 'utf8' },
  );
  if (proc.status !== 0) {
    throw new Error(`ffmpeg transcode failed: ${proc.stderr}`);
  }
  const probe = spawnSync(
    'ffprobe',
    ['-v', 'error', '-show_entries', 'format=duration,size:stream=codec_name,width,height', '-of', 'json', mp4Path],
    { encoding: 'utf8' },
  );
  if (probe.status !== 0) {
    throw new Error(`ffprobe failed: ${probe.stderr}`);
  }
  const info = JSON.parse(probe.stdout);
  return {
    duration_sec: Number(Number(info.format?.duration || 0).toFixed(2)),
    size_bytes: statSync(mp4Path).size,
    size_kb: Math.max(1, Math.round(statSync(mp4Path).size / 1024)),
    codec: info.streams?.[0]?.codec_name || 'unknown',
    width: info.streams?.[0]?.width || 0,
    height: info.streams?.[0]?.height || 0,
  };
}

function convertPngToWebp(pngPath, webpPath) {
  runPythonHelper(`
from PIL import Image
im = Image.open("${pngPath.replace(/\\/g, '\\\\')}").convert("RGB")
im.save("${webpPath.replace(/\\/g, '\\\\')}", format="WEBP", quality=86, method=6)
`);
}

async function addLocalSessionCookie(context, token) {
  await context.addCookies([
    {
      name: 'napda_session',
      value: token,
      url: FRONTEND_URL,
      httpOnly: true,
      sameSite: 'Lax',
    },
  ]);
}

/**
 * R2-01: Align Track A mock planner strictly with backend/data/templates/track_a/manifest.json (a_domino_docu_3d).
 * 3 pre-gap 3D domino physics beats (zero water/product words before silence_gap) -> 0.25s silence_gap -> 6.5s product payoff.
 */
function startMockPlannerServer() {
  const server = createServer((req, res) => {
    if (req.method === 'POST' && req.url === '/v1/plan') {
      let body = '';
      req.on('data', (chunk) => {
        body += chunk;
      });
      req.on('end', () => {
        let parsed = {};
        try {
          parsed = JSON.parse(body || '{}');
        } catch {
          parsed = {};
        }
        const pid = parsed?.request?.projectId || 'prj_e2e-A';
        const safeStem = pid.replace(/[^a-zA-Z0-9_-]/g, '_');
        const spec = {
          project_id: pid,
          output_stem: `napda_${safeStem}`,
          title: '50층 거대 도미노 물리 실험',
          mode: 'narrative_master',
          track_archetype: 'A_bgrade_reversal',
          a_genre_archetype: 'mock_documentary',
          track_a_template_id: 'a_domino_docu_3d',
          hook_window_sec: 9.88,
          framing_mode: 'full-bleed',
          disclosure: 'ai_assisted',
          source_video: 'source/pending_upload.mp4',
          source_duration: 16.6,
          allow_static_intro: true,
          product_taboo_keywords: ['스펀지', '물걸레', '물기'],
          usps: [{ title: '물기 즉시 흡수', fact_ids: ['F01'] }],
          timeline: [
            {
              id: 'hook_01',
              type: 'video',
              src_start: 0.0,
              duration: 3.3,
              framing: 'full-bleed',
              audio_owner: 'vo',
              flow_ref_prompt: '사막 위 1cm 회색 3D 도미노가 2배씩 커지며 연쇄적으로 쓰러지는 장면',
            },
            {
              id: 'hook_02',
              type: 'video',
              src_start: 3.3,
              duration: 3.3,
              framing: 'full-bleed',
              audio_owner: 'vo',
              flow_ref_prompt: '아파트 50층 높이 거대 3D 도미노 기둥이 모래먼지를 일으키며 기울어지는 장면',
            },
            {
              id: 'hook_03',
              type: 'video',
              src_start: 6.6,
              duration: 3.28,
              framing: 'full-bleed',
              audio_owner: 'vo',
              flow_ref_prompt: '거대 3D 도미노가 사막 지면에 닿으며 반경 1km 흙먼지 충격파가 퍼지는 클라이맥스',
            },
            {
              id: 'twist_gap',
              type: 'silence_gap',
              duration: 0.25,
              audio_owner: 'silence',
              framing: 'full-bleed',
            },
            {
              id: 'payoff_1',
              type: 'source',
              src_start: 0.0,
              src_end: 6.5,
              framing: 'full-bleed',
              audio_owner: 'vo',
              fact_ids: ['F01'],
            },
          ],
          captions: [
            { start: 0.1, end: 3.2, text: '1cm 도미노를 2배씩 키워\n스무 개만 세우면,' },
            { start: 3.4, end: 6.5, text: '마지막 조각은 아파트 50층\n높이가 됩니다' },
            { start: 6.7, end: 9.8, text: '지면에 닿는 순간, 반경 1km\n지반이 흔들립니다' },
            { start: 10.2, end: 16.5, text: '물기 즉시 흡수, 댓글로 링크 받기', is_cta: true },
          ],
          cta: { type: 'comment_dm', copy: '댓글로 링크 받기', fact_ids: ['F01'] },
        };
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ spec }));
      });
      return;
    }
    res.writeHead(404);
    res.end();
  });
  return new Promise((resolve) => {
    server.listen(PLANNER_PORT, '127.0.0.1', () => resolve(server));
  });
}

async function main() {
  assert(
    existsSync(path.join(TRACK_A_TEMPLATE_DIR, 'manifest.json')),
    `TRACK_A_TEMPLATE_DIR missing manifest.json: ${TRACK_A_TEMPLATE_DIR}`,
  );

  const tempRoot = mkdtempSync(path.join(tmpdir(), 'napda-e2e-rest-'));
  const workRoot = path.join(tempRoot, 'jobs');
  const outputDir = path.join(tempRoot, 'outputs');
  const dbPath = path.join(tempRoot, 'jobs.db');

  // R2-06: Realistic studio product demo MP4 with product-authentic filename
  const pvaDemoMp4 = path.join(tempRoot, 'pva_sponge_demo.mp4');
  makeStudioProductDemoMp4(pvaDemoMp4, 8.5);

  let plannerServer;
  let backendProc;
  let frontendProc;
  let browser;
  const featureResults = [];
  let backendLogs = '';

  try {
    plannerServer = await startMockPlannerServer();

    backendProc = spawn(
      path.join(REPO_ROOT, '.venv/bin/python'),
      [
        '-m',
        'uvicorn',
        'app.server:app',
        '--app-dir',
        'backend',
        '--host',
        '127.0.0.1',
        '--port',
        String(BACKEND_PORT),
        '--timeout-keep-alive',
        '60',
      ],
      {
        cwd: REPO_ROOT,
        detached: true,
        stdio: ['ignore', 'pipe', 'pipe'],
        env: {
          ...process.env,
          WORK_ROOT: workRoot,
          OUTPUT_DIR: outputDir,
          DB_PATH: dbPath,
          PLANNER_BASE_URL: PLANNER_URL,
          HOOK_WORKER_MODE: 'off',
          HOOK_RENDER_MODE: 'dry_run',
          TRACK_A_TEMPLATE_DIR,
          SESSION_COOKIE_SECURE: 'false',
          CORS_ORIGINS: `${FRONTEND_URL},http://localhost:${FRONTEND_PORT}`,
        },
      },
    );
    backendProc.stdout?.on('data', (d) => {
      backendLogs = (backendLogs + d.toString()).slice(-6000);
    });
    backendProc.stderr?.on('data', (d) => {
      backendLogs = (backendLogs + d.toString()).slice(-6000);
    });

    frontendProc = spawn(
      'npm',
      ['--prefix', 'frontend', 'run', 'dev', '--', '--host', '127.0.0.1', '--port', String(FRONTEND_PORT), '--strictPort'],
      {
        cwd: REPO_ROOT,
        detached: true,
        stdio: ['ignore', 'pipe', 'pipe'],
        env: {
          ...process.env,
          VITE_PROXY_TARGET: BACKEND_URL,
          VITE_API_BASE_URL: '',
        },
      },
    );
    frontendProc.stdout?.resume();
    frontendProc.stderr?.resume();

    await waitForHttp(`${BACKEND_URL}/health`, 30000);
    await waitForHttp(`${FRONTEND_URL}/health`, 30000);

    // Seed primary 0-credit user (with R2-04 real thumbnails for p1 & p2),
    // real DB-backed community A/B/C showcase items (R2-03),
    // and run BUG-08 0-credit 402 guard check using an isolated 0-credit user.
    const seedOut = runPythonHelper(
      `
import io, json, pathlib, sys, urllib.error, urllib.request
from PIL import Image
sys.path.insert(0, 'backend')
from app.auth import AuthenticatedUser, issue_session_token
from app.config import Settings
from app.project_store import ProjectStore

s = Settings()
user = AuthenticatedUser(user_id="e2e-user-001", email="e2e@napda.kr", name="냅다 E2E 테스터")
token, _ = issue_session_token(user, s.session_secret, ttl_days=1)

guard_user = AuthenticatedUser(user_id="e2e-guard-000", email="guard@napda.kr", name="크레딧 가드 테스터")
guard_token, _ = issue_session_token(guard_user, s.session_secret, ttl_days=1)

creators = [
    AuthenticatedUser(user_id="creator-living", email="living@napda.kr", name="리빙스튜디오"),
    AuthenticatedUser(user_id="creator-home", email="home@napda.kr", name="자취꿀팁연구소"),
    AuthenticatedUser(user_id="creator-clean", email="clean@napda.kr", name="생활용품리뷰"),
]
creator_tokens = {}

store = ProjectStore("${dbPath.replace(/\\/g, '\\\\')}")
store.upsert_user(user)
store.upsert_user(guard_user)
for c in creators:
    store.upsert_user(c)
    ct, _ = issue_session_token(c, s.session_secret, ttl_days=1)
    creator_tokens[c.user_id] = ct

def api(method, path_url, payload=None, tok=token):
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(
        "${BACKEND_URL}" + path_url,
        data=data,
        headers={"Cookie": f"napda_session={tok}", "Content-Type": "application/json"},
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        try:
            body = json.loads(raw)
        except Exception:
            body = {"raw": raw}
        return e.code, body

def upload_asset_png(tok, uid, pid, webp_rel):
    src_path = pathlib.Path("frontend/src/assets/thumbnails") / webp_rel
    im = Image.open(src_path).convert("RGB")
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    png_bytes = buf.getvalue()
    obj_key = f"uploads/{uid}/{pid}/seed_cover.png"
    st_pre, pre = api("POST", "/v1/uploads/presign", {
        "object_key": obj_key,
        "content_type": "image/png",
    }, tok=tok)
    assert st_pre == 200, f"presign png failed: {st_pre} {pre}"
    put_url = pre["upload_url"]
    if put_url.startswith("/"):
        put_url = "${BACKEND_URL}" + put_url
    put_req = urllib.request.Request(
        put_url,
        data=png_bytes,
        headers={"Cookie": f"napda_session={tok}", "Content-Type": "image/png"},
        method="PUT",
    )
    with urllib.request.urlopen(put_req, timeout=15) as pr:
        assert pr.status in (200, 201, 204), f"put png failed: {pr.status}"
    return pre["object_key"]

_, bw = api("GET", "/v1/billing/wallet")

# R2-04: Seed p1 (in-progress); scenarios + storyboard are generated async right after so mock planner isn't blocked by spawnSync
_, p1 = api("POST", "/v1/projects", {
    "product": {"name": "초흡수 PVA 물걸레 스펀지", "category": "living", "verified_facts": ["물기 즉시 흡수"]},
    "selected_types": ["A"],
    "flow_mode": "guide_first",
})

# R2-04 & R3: Seed p2 (completed) with canonical Storybook Figma white-label dam-tape style + highlight_word (zero gray scrim)
_, p2 = api("POST", "/v1/projects", {
    "product": {"name": "매직 방수 댐 테이프", "category": "living", "verified_facts": ["실리콘 방수"]},
    "selected_types": ["B"],
    "flow_mode": "guide_first",
})
p2_key = upload_asset_png(token, "e2e-user-001", p2["project_id"], "dam-tape-bulge.webp")
st_t2, t2 = api("POST", f"/v1/projects/{p2['project_id']}/thumbnail", {
    "headline_lines": ["댐 균열 테이프 100겹", "몇 초 버틸까?"],
    "highlight_word": "100겹",
    "style": "white-label",
    "source_image_key": p2_key,
})
assert st_t2 == 200 and t2.get("image_url"), f"p2 thumbnail failed: {st_t2} {t2}"
store.update_project(p2["project_id"], status="DELIVERABLE_READY")

# R2-03 & R3: Seed 6 real DB-backed public community videos (2 A, 2 B, 2 C) showcasing ALL 4 canonical Storybook Figma styles
community_seeds = [
    ("creator-living", "A", "초경량 방풍 우산", ["시속 300km 강풍 버팀"], "jet-umbrella-v1.webp", ["시속 300km 제트엔진", "뒤에서 우산을 펴면?"], "white-label", "300km", None, "시속 300km 제트엔진 앞에서도 안 뒤집히는 방풍 우산"),
    ("creator-home", "A", "진공 보온 텀블러", ["24시간 얼음 유지"], "ps2-eoljukah-v3.webp", ["영하 15도 서울 카페", "전원 '얼죽아' 생존 미션"], "invert-box", "얼죽아", None, "영하 15도 한파에도 얼음이 그대로 유지되는 진공 텀블러"),
    ("creator-clean", "B", "매직 방수 댐 테이프", ["실리콘 즉시 방수"], "dam-tape-bulge.webp", ["댐 균열 테이프 100겹", "몇 초 버틸까?"], "white-label", "100겹", None, "누수 틈새 한 번에 막는 실리콘 방수 댐 테이프"),
    ("creator-living", "B", "초강력 실리콘 실란트", ["욕실 곰팡이 차단"], "dam-tape-ragdoll.webp", ["POV: 100톤 수압 댐 균열을", "테이프 100겹으로 막아보다가", "통째로 날아간 나"], "pov-bar", "100겹", None, "수압 테스트까지 버티는 초강력 욕실 방수 실란트"),
    ("creator-clean", "C", "피에브 에어워셔", ["냄새 분자 분해"], "piev-studio-fullshot.webp", ["피에브", "에어워셔"], "serif-outline", None, "냄새 덮지 말고 잡으세요!", "냄새 덮지 말고 공기를 바로 씻어내는 에어워셔"),
    ("creator-home", "C", "무소음 휴대용 목풍기", ["저소음 3단 강풍"], "ps2-subway-hero.webp", ["POV: 한국 드라마 보고 왔는데", "출근길 서울 2호선에", "처음 타버린 나"], "pov-bar", "2호선", None, "출근길 2호선에서도 조용하고 시원한 휴대용 목풍기"),
]
seeded_community_ids = []
for uid, htype, pname, facts, asset_file, hlines, style, hi_word, badge_txt, cap in community_seeds:
    ctok = creator_tokens[uid]
    st_cp, cp = api("POST", "/v1/projects", {
        "product": {"name": pname, "category": "living", "verified_facts": facts},
        "selected_types": [htype],
        "flow_mode": "guide_first",
    }, tok=ctok)
    assert st_cp == 201, f"community project failed: {st_cp} {cp}"
    cpid = cp["project_id"]
    ckey = upload_asset_png(ctok, uid, cpid, asset_file)
    thumb_payload = {
        "headline_lines": hlines,
        "style": style,
        "source_image_key": ckey,
    }
    if hi_word:
        thumb_payload["highlight_word"] = hi_word
    if badge_txt:
        thumb_payload["badge"] = badge_txt
    st_ct, ct_body = api("POST", f"/v1/projects/{cpid}/thumbnail", thumb_payload, tok=ctok)
    assert st_ct == 200 and ct_body.get("image_url"), f"community thumb failed: {st_ct} {ct_body}"
    assert ct_body.get("safe_zone_1_1_ok") is True, f"community thumb safe zone failed for {pname}/{style}: {ct_body}"
    store.update_project(cpid, status="DELIVERABLE_READY")
    st_pub, pub_body = api("PATCH", f"/v1/projects/{cpid}/publish", {
        "is_public": True,
        "caption": cap,
    }, tok=ctok)
    assert st_pub == 200 and pub_body.get("is_public") is True, f"community publish failed: {st_pub} {pub_body}"
    seeded_community_ids.append(cpid)

# Verify GET /v1/community/videos returns all 6 real DB items
st_cv, cv = api("GET", "/v1/community/videos")
assert st_cv == 200 and len(cv.get("items", [])) == 6, f"expected 6 community items, got {st_cv} {cv}"

# BUG-08 check: 0-credit user direct POST /v1/projects/{pid}/renders -> HTTP 402 INSUFFICIENT_CREDITS
_, gw = api("GET", "/v1/billing/wallet", tok=guard_token)
assert gw["credits"] == 0, f"guard user expected 0 credits, got {gw}"
st_gp, gp = api("POST", "/v1/projects", {
    "product": {"name": "무크레딧 가드 테스트 제품", "category": "living", "verified_facts": ["가드 검증"]},
    "selected_types": ["A"],
    "flow_mode": "guide_first",
}, tok=guard_token)
assert st_gp == 201, f"guard project create failed: {st_gp} {gp}"
gpid = gp["project_id"]
st_pre, pre = api("POST", "/v1/uploads/presign", {
    "object_key": f"uploads/e2e-guard-000/{gpid}/shot_01.mp4",
    "content_type": "video/mp4",
}, tok=guard_token)
assert st_pre == 200, f"guard presign failed: {st_pre} {pre}"
clip_bytes = pathlib.Path("${pvaDemoMp4.replace(/\\/g, '\\\\')}").read_bytes()
put_url = pre["upload_url"]
if put_url.startswith("/"):
    put_url = "${BACKEND_URL}" + put_url
put_req = urllib.request.Request(
    put_url,
    data=clip_bytes,
    headers={"Cookie": f"napda_session={guard_token}", "Content-Type": "video/mp4"},
    method="PUT",
)
with urllib.request.urlopen(put_req, timeout=15) as pr:
    assert pr.status in (200, 201, 204), f"guard put failed: {pr.status}"
st_cmp, cmp_body = api("POST", f"/v1/projects/{gpid}/uploads/complete", {
    "clips": [{"shot_no": 1, "object_key": pre["object_key"], "file_size_bytes": len(clip_bytes)}],
}, tok=guard_token)
assert st_cmp == 200, f"guard upload complete failed: {st_cmp} {cmp_body}"
st_rnd, rnd_body = api("POST", f"/v1/projects/{gpid}/renders", {
    "selected_type": "A",
    "skip_drafts": True,
    "resolution": "720p",
    "dry_run": False,
}, tok=guard_token)
assert st_rnd == 402, f"BUG-08 expected 402 for 0-credit render, got {st_rnd}: {rnd_body}"
assert "INSUFFICIENT_CREDITS" in json.dumps(rnd_body, ensure_ascii=False), f"BUG-08 expected INSUFFICIENT_CREDITS, got {rnd_body}"

print(json.dumps({
    "cookie_token": token,
    "initial_credits": bw["credits"],
    "in_progress_id": p1["project_id"],
    "completed_id": p2["project_id"],
    "community_count": len(seeded_community_ids),
    "bug08_guard_status": st_rnd,
}, ensure_ascii=False))
`,
    );
    const seed = JSON.parse(seedOut);
    assert(seed.initial_credits === 0, 'expected initial credits 0');
    assert(seed.bug08_guard_status === 402, 'expected BUG-08 402 guard check to pass');
    assert(seed.community_count === 6, 'expected 6 real DB community items');

    // R2-04: Async call to generate p1 scenarios + storyboard (so Node event loop serves mock planner freely)
    const p1ScnRes = await fetch(`${BACKEND_URL}/v1/projects/${seed.in_progress_id}/scenarios`, {
      method: 'POST',
      headers: {
        Cookie: `napda_session=${seed.cookie_token}`,
        'Content-Type': 'application/json',
        Connection: 'close',
      },
      body: JSON.stringify({ types: ['A'], count: 1 }),
    });
    assert(p1ScnRes.status === 200, `p1 scenarios expected 200, got ${p1ScnRes.status}`);
    const p1ScnJson = await p1ScnRes.json();
    const p1ScnId = p1ScnJson.scenarios?.[0]?.scenario_id;
    assert(Boolean(p1ScnId), 'p1 missing scenario_id');
    const p1SbRes = await fetch(`${BACKEND_URL}/v1/projects/${seed.in_progress_id}/scenarios/${p1ScnId}/storyboard`, {
      method: 'POST',
      headers: {
        Cookie: `napda_session=${seed.cookie_token}`,
        'Content-Type': 'application/json',
        Connection: 'close',
      },
      body: JSON.stringify({ visual_style: 'blender_clay_diorama' }),
    });
    assert(p1SbRes.status === 200, `p1 storyboard expected 200, got ${p1SbRes.status}`);
    const p1SbJson = await p1SbRes.json();
    assert(p1SbJson.frames?.length === 4, `p1 storyboard expected 4 frames, got ${p1SbJson.frames?.length}`);
    console.log('[PASS] BUG-08 0-credit render guard -> HTTP 402 INSUFFICIENT_CREDITS (+6 real DB community items & R2-04 thumbnails seeded)');

    try {
      browser = await chromium.launch({ headless: true, channel: 'chrome' });
    } catch {
      browser = await chromium.launch({ headless: true });
    }

    async function recordFeature(name, scopeOrigin, fn, opts = {}) {
      const featureRawDir = path.join(RAW_VIDEO_DIR, name);
      const featureShotsDir = path.join(SHOTS_DIR, name);
      rmSync(featureRawDir, { recursive: true, force: true });
      rmSync(featureShotsDir, { recursive: true, force: true });
      mkdirSync(featureRawDir, { recursive: true });
      mkdirSync(featureShotsDir, { recursive: true });

      const mp4Path = path.join(RECORDINGS_DIR, `${name}.mp4`);
      const thumbPath = path.join(THUMBS_DIR, `${name}.png`);
      rmSync(thumbPath, { force: true });
      const pageErrors = [];
      const httpErrors = [];
      const shots = [];

      const context = await browser.newContext({
        viewport: VIEWPORT,
        locale: 'ko-KR',
        recordVideo: { dir: featureRawDir, size: VIEWPORT },
      });
      const page = await context.newPage();
      const video = page.video();

      page.on('pageerror', (err) => pageErrors.push(String(err)));
      page.on('response', (res) => {
        const url = res.url();
        if (!url.startsWith(scopeOrigin)) return;
        const status = res.status();
        let pathname = '';
        try {
          pathname = new URL(url).pathname;
        } catch {
          pathname = url;
        }
        // Intentional unauth /v1/auth/me 401 checks are allowed
        if (status === 401 && pathname === '/v1/auth/me') return;
        // Ignore headless Chromium automatic favicon probe if missing
        if (status === 404 && pathname === '/favicon.ico') return;
        if (opts.allowResponse && opts.allowResponse(res, pathname)) return;
        if (status >= 500 || (pathname.startsWith('/v1/') && status >= 400)) {
          httpErrors.push(`${status} ${res.request().method()} ${url}`);
        }
      });

      async function captureShot(slug, label, isPoster = false) {
        const tmpPng = path.join(THUMBS_DIR, `${name}__${slug}.png`);
        const webpPath = path.join(featureShotsDir, `${slug}.webp`);
        await page.screenshot({ path: tmpPng });
        convertPngToWebp(tmpPng, webpPath);
        if (isPoster || !existsSync(thumbPath)) {
          await page.screenshot({ path: thumbPath });
        }
        shots.push({ label, src: `./recordings/shots/${name}/${slug}.webp` });
      }

      const started = Date.now();
      let details = {};
      let status = 'pass';
      let errorMessage = null;

      try {
        details = (await fn({ context, page, captureShot, dwell: (ms = 1800) => page.waitForTimeout(ms) })) || {};
        assert(pageErrors.length === 0, `pageerror detected: ${pageErrors.join(' | ')}`);
        assert(httpErrors.length === 0, `unexpected HTTP >= 400 / 5xx response detected: ${httpErrors.join(' | ')}`);
      } catch (err) {
        status = 'fail';
        errorMessage = err instanceof Error ? err.stack || err.message : String(err);
      } finally {
        await page.waitForTimeout(900).catch(() => {});
        if (!existsSync(thumbPath)) {
          await page.screenshot({ path: thumbPath }).catch(() => {});
        }
        await page.close().catch(() => {});
        await context.close().catch(() => {});
      }

      const webmPath = video ? await video.path() : null;
      let mediaMeta = null;
      if (webmPath && existsSync(webmPath)) {
        mediaMeta = transcodeToMp4(webmPath, mp4Path);
      }

      const result = {
        name,
        status,
        elapsed_ms: Date.now() - started,
        mp4: mp4Path,
        thumb: thumbPath,
        shots,
        media: mediaMeta,
        pageErrors,
        httpErrors,
        details,
        error: errorMessage,
      };
      featureResults.push(result);
      console.log(`[${status.toUpperCase()}] ${name} -> ${mediaMeta?.duration_sec ?? '?'}s, ${shots.length} shots (${mp4Path})`);
      if (status === 'fail') {
        throw new Error(`Feature ${name} failed: ${errorMessage}`);
      }
    }

    async function assertProjectCardsHaveRealThumbnails(page, label) {
      const emptyCount = await page.locator('.n-project__thumb.is-empty').count();
      assert(emptyCount === 0, `[${label}] R2-04: found ${emptyCount} empty placeholder green cube(s) on project cards`);
      const thumbs = page.locator('.n-project__thumb img');
      const count = await thumbs.count();
      assert(count >= 1, `[${label}] R2-04: expected >= 1 real project card thumbnail img`);
      for (let i = 0; i < count; i += 1) {
        await thumbs.nth(i).scrollIntoViewIfNeeded();
      }
      await thumbs.first().scrollIntoViewIfNeeded();
      await page.waitForFunction(
        () => {
          const imgs = Array.from(document.querySelectorAll('.n-project__thumb img'));
          return (
            imgs.length >= 1 &&
            imgs.every(
              (img) =>
                img.getAttribute('src')?.includes('/v1/media/') &&
                img.complete &&
                img.naturalWidth > 0,
            )
          );
        },
        { timeout: 15000 },
      );
    }

    // ===================== 남은 공용 TODO (L08 · L10 · L12) =====================
    const ONLY = (process.env.ONLY || '').split(',').filter(Boolean);
    const want = (n) => ONLY.length === 0 || ONLY.some((o) => n.includes(o));
    const cookieHeader = { Cookie: `napda_session=${seed.cookie_token}` };
    const state = { completedProjectId: null };

    function makeClip(outPath, sec, size = '720x1280') {
      const p = spawnSync('ffmpeg', ['-y', '-f', 'lavfi', '-i', `testsrc2=size=${size}:rate=15:duration=${sec}`, '-c:v', 'libx264', '-pix_fmt', 'yuv420p', outPath], { encoding: 'utf8' });
      if (p.status !== 0) throw new Error(`makeClip failed: ${p.stderr}`);
    }
    const shortClip = path.join(tempRoot, 'too_short_2s.mp4');
    makeClip(shortClip, 2);
    const spoofClip = path.join(tempRoot, 'not_a_video.mp4');
    writeFileSync(spoofClip, 'this is plain text pretending to be an mp4\n'.repeat(200));

    async function dumpOnFail(page, label, fn) {
      try {
        return await fn();
      } catch (e) {
        const txt = await page.locator('body').innerText().catch(() => '');
        const btns = await page.getByRole('button').allInnerTexts().catch(() => []);
        console.error(`--- [${label}] SCREEN TEXT ---\n${txt.slice(0, 1500)}\n--- BUTTONS: ${JSON.stringify(btns)}`);
        await page.screenshot({ path: path.join(ARTIFACT_DIR, `fail_${label}.png`) }).catch(() => {});
        throw e;
      }
    }

    function sendSignedWebhook(checkoutBody, eventId, userId = 'e2e-user-001') {
      return JSON.parse(
        runPythonHelper(`
import hashlib, hmac, json, sys, time, urllib.request
sys.path.insert(0, 'backend')
from app.config import Settings
s = Settings()
payload = {"event_id": "${eventId}", "event_type": "transaction.completed", "data": {"id": "${checkoutBody.paddle_transaction_id}", "status": "completed", "custom_data": {"order_id": "${checkoutBody.order_id}", "user_id": "${userId}", "package_id": "c100"}}}
raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
ts = str(int(time.time()))
sig = hmac.new(s.paddle_webhook_secret.strip().encode("utf-8"), f"{ts}:".encode("ascii") + raw, hashlib.sha256).hexdigest()
req = urllib.request.Request("${BACKEND_URL}/v1/billing/webhooks/paddle", data=raw, headers={"Content-Type": "application/json", "Paddle-Signature": f"ts={ts};h1={sig}"}, method="POST")
with urllib.request.urlopen(req, timeout=15) as r:
    ack = json.loads(r.read().decode("utf-8"))
w_req = urllib.request.Request("${BACKEND_URL}/v1/billing/wallet", headers={"Cookie": "napda_session=${seed.cookie_token}"})
with urllib.request.urlopen(w_req, timeout=15) as wr:
    wallet = json.loads(wr.read().decode("utf-8"))
print(json.dumps({"ack": ack, "credits": wallet["credits"]}))
`),
      );
    }


    // Paddle Sandbox 결제창(오버레이)에서 Paddle 이 공개한 테스트 카드로 결제를 끝낸다
    async function payInPaddleSandbox(page, dwell, captureShot) {
      const sel = 'iframe[name^="paddle"], iframe[src*="paddle"]';
      await page.locator(sel).first().waitFor({ state: 'visible', timeout: 25000 });
      const f = page.frameLocator(sel).first();
      const tid = (id) => f.locator(`[data-testid="${id}"]`);
      const dumpFrame = async (label) => {
        const fr = page.frames().find((x) => /paddle/.test(x.url()));
        const ids = fr ? await fr.evaluate(() => [...document.querySelectorAll('[data-testid]')].map((e) => `${e.tagName.toLowerCase()}:${e.getAttribute('data-testid')}`)).catch(() => []) : [];
        const txt = fr ? await fr.evaluate(() => document.body.innerText.slice(0, 800)).catch(() => '') : '';
        console.error(`--- PADDLE FRAME [${label}] url=${fr?.url()}\nTESTIDS=${JSON.stringify(ids)}\nTEXT=${txt}\nFRAMES=${JSON.stringify(page.frames().map((x) => x.url().slice(0, 90)))}`);
      };
      try {
        await f.locator('input, button').first().waitFor({ state: 'visible', timeout: 25000 });
        await dwell(1500);
        // 1단계: 이메일·국가·우편번호
        const email = tid('authenticationEmailInput');
        if (await email.isVisible().catch(() => false)) {
          if (!(await email.inputValue())) await email.fill('e2e@napda.kr');
          const zip = tid('postcodeInput');
          if (await zip.isVisible().catch(() => false)) await zip.fill('06236');
          await dwell(800);
          await tid('combinedAuthenticationLocationFormSubmitButton').click();
        }
        // 2단계: 카드
        await tid('cardNumberInput').waitFor({ state: 'visible', timeout: 25000 });
        await tid('cardNumberInput').fill('4242 4242 4242 4242');
        await tid('cardholderNameInput').fill('NAPDA E2E');
        await tid('expiryDateField').fill('12/30');
        await tid('cardVerificationValueInput').fill('100');
        await dwell(1500);
        await captureShot('03b_paddle_test_card', 'Paddle Sandbox 테스트 카드');
        await tid('cardPaymentFormSubmitButton').click();
        return { method: 'test_card' };
      } catch (e) {
        await dumpFrame('pay_failed');
        throw e;
      }
    }

    // 1/8 → 5/8 까지 (A 유형, 목 플래너) 진행하고 6/8 업로드 화면에서 멈춘다
    async function wizardToUpload(page, { name, intro, capture, dwell }) {
      await page.getByRole('button', { name: '영상 만들기' }).first().click();
      await page.getByRole('heading', { name: '제품 정보' }).waitFor({ state: 'visible' });
      await page.getByLabel('제품 이름').fill(name);
      await page.getByLabel('한 줄 소개').fill(intro);
      await page.getByRole('radio', { name: '자취' }).click();
      await dwell(1200);
      if (capture) await capture('product');
      await page.getByRole('button', { name: '다음' }).click();
      await page.getByRole('heading', { name: '유형 선택' }).waitFor({ state: 'visible' });
      await dwell(1200);
      if (capture) await capture('hook');
      const scnP = page.waitForResponse((r) => r.url().includes('/scenarios') && r.request().method() === 'POST', { timeout: 30000 });
      await page.getByRole('button', { name: '시나리오 글 보기' }).click();
      assert((await scnP).status() === 200, 'scenarios expected 200');
      await page.getByText(/50층 거대 도미노 물리 실험/).waitFor({ state: 'visible', timeout: 15000 });
      await dwell(1400);
      if (capture) await capture('scenario');
      const sbP = page.waitForResponse((r) => r.url().includes('/storyboard') && r.request().method() === 'POST', { timeout: 40000 });
      await page.getByRole('button', { name: '그림으로 보기' }).click();
      assert((await sbP).status() === 200, 'storyboard expected 200');
      await page.getByRole('heading', { name: '그림 콘티' }).waitFor({ state: 'visible', timeout: 10000 });
      await page.waitForFunction(() => { const i = [...document.querySelectorAll('ol img')]; return i.length === 4 && i.every((x) => x.complete && x.naturalWidth > 0); }, { timeout: 20000 });
      await dwell(1400);
      if (capture) await capture('storyboard');
      const gP = page.waitForResponse((r) => r.url().includes('/filming-guide') && r.request().method() === 'POST', { timeout: 20000 });
      await page.getByRole('button', { name: '촬영 가이드 받기' }).click();
      assert((await gP).status() === 200, 'filming-guide expected 200');
      await page.getByRole('heading', { name: '촬영 가이드' }).waitFor({ state: 'visible' });
      await page.waitForFunction(() => document.querySelectorAll('.n-shimmer').length === 0, { timeout: 10000 });
      await dwell(1400);
      if (capture) await capture('guide');
      await page.getByRole('button', { name: '찍은 영상 올리기' }).click();
      await page.getByRole('heading', { name: '영상 올리기' }).waitFor({ state: 'visible' });
    }

    async function waitRenderDone(page, dwell) {
      const viewBtn = page.getByRole('button', { name: '영상 보러 가기' });
      await viewBtn.waitFor({ state: 'visible', timeout: 120000 });
      await dwell(1400);
      await viewBtn.click();
      await page.getByRole('heading', { name: '짜잔, 영상 나왔어요' }).waitFor({ state: 'visible', timeout: 15000 });
      await page.locator('video').first().waitFor({ state: 'visible', timeout: 15000 });
    }

    // ---------- E2E-L08: 8단계 위저드 예외 · 크레딧 부족 → 충전 → 복귀 ----------
    if (want('08_local_wizard_8step')) await recordFeature('08_local_wizard_8step', FRONTEND_URL, async ({ context, page, captureShot, dwell }) => dumpOnFail(page, 'L08', async () => {
      await addLocalSessionCookie(context, seed.cookie_token);
      let projectId = null;
      page.on('response', async (res) => {
        try {
          if (res.request().method() === 'POST' && new URL(res.url()).pathname === '/v1/projects' && res.status() === 201) projectId = (await res.json()).project_id;
        } catch { /* ignore */ }
      });
      await page.goto(`${FRONTEND_URL}/`, { waitUntil: 'networkidle' });
      const badge = page.getByRole('button', { name: /남은 크레딧/ });
      await badge.waitFor({ state: 'visible' });
      assert((await badge.innerText()).includes('0'), 'L08 expects 0 starting credits');
      await dwell(1000);

      // 예외 1: 필수 입력이 비면 "다음" 이 잠긴다
      await page.getByRole('button', { name: '영상 만들기' }).first().click();
      await page.getByRole('heading', { name: '제품 정보' }).waitFor({ state: 'visible' });
      const nextBtn = page.getByRole('button', { name: '다음' });
      const emptyDisabled = await nextBtn.isDisabled();
      await dwell(1200);
      await captureShot('01_empty_guard', '1/8 빈 입력 · 다음 잠김');
      await page.getByLabel('제품 이름').fill('초흡수 PVA 물걸레 스펀지');
      await page.getByLabel('한 줄 소개').fill('물기를 순식간에 빨아들이는 3초 흡수력');
      await page.getByRole('radio', { name: '자취' }).click();
      assert(await nextBtn.isEnabled(), 'L08: 다음 should enable after required input');
      await nextBtn.click();
      await page.getByRole('heading', { name: '유형 선택' }).waitFor({ state: 'visible' });

      // 예외 2: 뒤로 갔다 와도 입력이 남아 있다
      await page.getByRole('button', { name: '이전' }).click();
      await page.getByRole('heading', { name: '제품 정보' }).waitFor({ state: 'visible' });
      assert((await page.getByLabel('제품 이름').inputValue()) === '초흡수 PVA 물걸레 스펀지', 'L08: product name must persist after back');
      await dwell(1000);
      await page.getByRole('button', { name: '다음' }).click();
      await page.getByRole('heading', { name: '유형 선택' }).waitFor({ state: 'visible' });
      await dwell(1000);

      const scnP = page.waitForResponse((r) => r.url().includes('/scenarios') && r.request().method() === 'POST', { timeout: 30000 });
      await page.getByRole('button', { name: '시나리오 글 보기' }).click();
      assert((await scnP).status() === 200, 'scenarios expected 200');
      await page.getByText(/50층 거대 도미노 물리 실험/).waitFor({ state: 'visible', timeout: 15000 });
      await dwell(1200);
      const sbP = page.waitForResponse((r) => r.url().includes('/storyboard') && r.request().method() === 'POST', { timeout: 40000 });
      await page.getByRole('button', { name: '그림으로 보기' }).click();
      assert((await sbP).status() === 200, 'storyboard expected 200');
      await page.getByRole('heading', { name: '그림 콘티' }).waitFor({ state: 'visible', timeout: 10000 });
      await dwell(1200);
      await page.getByRole('button', { name: '촬영 가이드 받기' }).click();
      await page.getByRole('heading', { name: '촬영 가이드' }).waitFor({ state: 'visible' });
      await page.waitForFunction(() => document.querySelectorAll('.n-shimmer').length === 0, { timeout: 10000 });
      await dwell(1200);
      await page.getByRole('button', { name: '찍은 영상 올리기' }).click();
      await page.getByRole('heading', { name: '영상 올리기' }).waitFor({ state: 'visible' });

      // 예외 3: 영상을 고르기 전에는 만들기 버튼이 잠긴다
      const createBtn = page.getByRole('button', { name: '훅 붙여서 만들기' });
      assert(await createBtn.isDisabled(), 'L08: create must be disabled before picking a file');
      await page.locator('input[type="file"]').setInputFiles(pvaDemoMp4);
      await page.getByText('pva_sponge_demo.mp4').waitFor({ state: 'visible', timeout: 5000 });
      await page.getByText(/보유 0/).waitFor({ state: 'visible', timeout: 5000 });
      await dwell(1200);

      // 크레딧 부족: 서버에 올리기 전에 시트로 막고 충전으로 잇는다
      let rendersCalled = 0;
      page.on('request', (rq) => { if (rq.url().includes('/renders') && rq.method() === 'POST') rendersCalled += 1; });
      await createBtn.click();
      const sheet = page.getByRole('alertdialog');
      await sheet.waitFor({ state: 'visible', timeout: 5000 });
      const sheetText = await sheet.innerText();
      assert(sheetText.includes('크레딧이 조금 모자라요'), `L08: shortfall sheet title missing: ${sheetText}`);
      assert(/필요\s*12/.test(sheetText) && /보유\s*0/.test(sheetText), `L08: shortfall numbers wrong: ${sheetText}`);
      await dwell(1600);
      await captureShot('02_shortfall_sheet', '6/8 크레딧 부족 안내');
      await sheet.getByRole('button', { name: '나중에' }).click();
      await sheet.waitFor({ state: 'hidden', timeout: 5000 });
      await page.getByText('pva_sponge_demo.mp4').waitFor({ state: 'visible' });
      assert(rendersCalled === 0, 'L08: render must not be requested while short on credits');
      await dwell(900);
      await createBtn.click();
      await sheet.waitFor({ state: 'visible', timeout: 5000 });
      await sheet.getByRole('button', { name: '충전하고 만들기' }).click();

      await page.getByText('크레딧 채우고, 냅다 만들어요').waitFor({ state: 'visible' });
      await page.getByRole('radio', { name: /100 크레딧/ }).click({ force: true });
      await dwell(1400);
      await captureShot('03_charge', '크레딧 충전 (부족분 안내)');
      const coP = page.waitForResponse((r) => r.url().includes('/v1/billing/checkout') && r.request().method() === 'POST', { timeout: 20000 });
      await page.getByRole('button', { name: /12,900원 결제하기/ }).click();
      const coRes = await coP;
      assert(coRes.status() === 200, `checkout expected 200, got ${coRes.status()}`);
      const coBody = await coRes.json();
      const pay = await payInPaddleSandbox(page, dwell, captureShot);
      // 로컬에는 Paddle 실웹훅이 닿지 않으므로, 주문 동기화로 적립되지 않으면 서명 웹훅으로 적립한다
      let creditedBy = 'order_sync';
      const doneHeading = page.getByRole('heading', { name: '충전 완료!' });
      for (let i = 0; i < 30; i += 1) {
        if (await doneHeading.isVisible().catch(() => false)) break;
        if (i === 4) {
          const w = await (await fetch(`${BACKEND_URL}/v1/billing/wallet`, { headers: cookieHeader })).json();
          if (w.credits === 0) {
            const wh = sendSignedWebhook(coBody, 'evt_e2e_l08_001');
            assert(wh.ack?.received === true && wh.credits === 100, `L08: credits must become 100, got ${JSON.stringify(wh)}`);
            creditedBy = 'signed_webhook';
          }
        }
        await page.waitForTimeout(1500);
      }
      const resumeBtn = page.getByRole('button', { name: '영상 만들러 가기' });
      const resumedVia = `paddle_${pay.method}+${creditedBy}`;
      await doneHeading.waitFor({ state: 'visible', timeout: 20000 });
      // Paddle 결제 성공 창이 앱 화면 위에 남는다 → 사용자가 직접 닫아야 한다 (발견 사항으로 기록)
      const overlay = page.locator('iframe.paddle-frame-overlay');
      const overlayStays = await overlay.isVisible().catch(() => false);
      if (overlayStays) {
        await dwell(1500);
        await captureShot('03c_paddle_success_overlay', 'Paddle 결제 성공 창 (닫아야 진행)');
        const pf = page.frameLocator('iframe.paddle-frame-overlay');
        const fr = page.frames().find((x) => /paddle/.test(x.url()));
        const ids = fr ? await fr.evaluate(() => [...document.querySelectorAll('button,[role=button],a')].map((e) => `${e.tagName.toLowerCase()}|${e.getAttribute('data-testid')}|${e.getAttribute('aria-label')}|${(e.innerText || '').trim().slice(0, 30)}`)).catch(() => []) : [];
        console.log('PADDLE SUCCESS BUTTONS', JSON.stringify(ids));
        const closeBtn = pf.locator('[data-testid*="lose" i], button[aria-label*="lose" i], button[aria-label*="닫"]').first();
        await closeBtn.click({ timeout: 8000 });
        await overlay.waitFor({ state: 'detached', timeout: 10000 }).catch(() => overlay.waitFor({ state: 'hidden', timeout: 5000 }));
      }
      state.paddleOverlayStays = overlayStays;
      await dwell(1600);
      await captureShot('04_charge_done', '충전 완료 · 영상 만들러 가기');
      await resumeBtn.click();
      await page.getByRole('heading', { name: '영상 올리기' }).waitFor({ state: 'visible', timeout: 10000 });
      await page.getByText('pva_sponge_demo.mp4').waitFor({ state: 'visible', timeout: 5000 });
      await page.getByText(/보유 100/).waitFor({ state: 'visible', timeout: 10000 });
      await dwell(1600);
      await captureShot('05_resume_upload', '6/8 복귀 · 영상 유지 · 보유 100');

      const rP = page.waitForResponse((r) => r.url().includes('/renders') && r.request().method() === 'POST', { timeout: 30000 });
      await createBtn.click();
      const rRes = await rP;
      assert(rRes.status() === 202, `renders expected 202, got ${rRes.status()}`);
      const rBody = await rRes.json();
      assert(rBody.deducted_credits === 12, `L08: expected 12 credits deducted, got ${rBody.deducted_credits}`);
      await page.waitForTimeout(1500);
      await captureShot('06_generating', '영상 만드는 중');
      await waitRenderDone(page, dwell);
      await dwell(2000);
      await captureShot('07_review', '7/8 영상 확인', true);
      const wRes = await fetch(`${BACKEND_URL}/v1/billing/wallet`, { headers: cookieHeader });
      const wallet = await wRes.json();
      assert(wallet.credits === 88, `L08: wallet expected 88 after render, got ${wallet.credits}`);
      state.completedProjectId = projectId;
      return { empty_next_disabled: emptyDisabled, shortfall_sheet: true, renders_before_charge: rendersCalled - 1, resumed_via: resumedVia, deducted: rBody.deducted_credits, wallet_after: wallet.credits, project_id: projectId };
    }));

    // ---------- E2E-L10: 제품 정보 · 촬영 가이드 · Presign 업로드 ffprobe 검증 ----------
    if (want('10_local_upload_guide')) await recordFeature('10_local_upload_guide', FRONTEND_URL, async ({ context, page, captureShot, dwell }) => dumpOnFail(page, 'L10', async () => {
      await addLocalSessionCookie(context, seed.cookie_token);
      // API 계약 검증 (FR-001 · 002 · 007 · 009)
      const api = async (method, p, body, raw) => {
        const res = await fetch(`${BACKEND_URL}${p}`, { method, headers: { ...cookieHeader, ...(raw ? raw.headers : { 'Content-Type': 'application/json' }) }, body: raw ? raw.body : body ? JSON.stringify(body) : undefined });
        let json = null;
        try { json = await res.json(); } catch { /* empty */ }
        return { status: res.status, json };
      };
      const product = { name: '초흡수 PVA 물걸레 스펀지', category: 'living', verified_facts: ['물기 즉시 흡수'] };
      const pi1 = await api('POST', '/v1/product-info', { product });
      assert(pi1.status === 200 && pi1.json.product_info_id, `product-info expected 200: ${JSON.stringify(pi1)}`);
      const pi2 = await api('POST', '/v1/product-info', { product });
      assert(pi2.status === 200 && pi2.json.cached === true && pi2.json.product_info_id === pi1.json.product_info_id, `product-info 2nd call should hit cache: ${JSON.stringify(pi2.json)}`);
      const prj = await api('POST', '/v1/projects', { product, selected_types: ['A'], flow_mode: 'guide_first' });
      assert(prj.status === 201, `project create expected 201: ${JSON.stringify(prj)}`);
      const pid = prj.json.project_id;
      const putClip = async (file, shotNo) => {
        const pre = await api('POST', '/v1/uploads/presign', { object_key: `uploads/e2e-user-001/${pid}/shot_${String(shotNo).padStart(2, '0')}_${path.basename(file)}`, content_type: 'video/mp4' });
        assert(pre.status === 200 && pre.json.upload_url, `presign expected 200: ${JSON.stringify(pre)}`);
        const { readFileSync } = await import('node:fs');
        const bytes = readFileSync(file);
        const url = pre.json.upload_url.startsWith('/') ? `${BACKEND_URL}${pre.json.upload_url}` : pre.json.upload_url;
        const put = await fetch(url, { method: 'PUT', headers: { ...cookieHeader, 'Content-Type': 'video/mp4' }, body: bytes });
        assert([200, 201, 204].includes(put.status), `PUT expected 2xx, got ${put.status}`);
        return api('POST', `/v1/projects/${pid}/uploads/complete`, { clips: [{ shot_no: shotNo, object_key: pre.json.object_key, file_size_bytes: bytes.length }] });
      };
      const badShort = await putClip(shortClip, 1);
      assert(badShort.status === 400 && JSON.stringify(badShort.json).includes('INVALID_UPLOAD_LIMIT'), `2s clip expected 400 INVALID_UPLOAD_LIMIT: ${JSON.stringify(badShort)}`);
      const badSpoof = await putClip(spoofClip, 1);
      assert(badSpoof.status === 400 && JSON.stringify(badSpoof.json).includes('INVALID_UPLOAD_MEDIA'), `spoofed mp4 expected 400 INVALID_UPLOAD_MEDIA: ${JSON.stringify(badSpoof)}`);
      const good = await putClip(pvaDemoMp4, 1);
      assert(good.status === 200 && good.json.status === 'UPLOADS_READY', `valid clip expected UPLOADS_READY: ${JSON.stringify(good)}`);
      const noAuth = await fetch(`${BACKEND_URL}/v1/uploads/presign`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ object_key: `uploads/x/${pid}/a.mp4`, content_type: 'video/mp4' }) });
      const foreign = await api('POST', '/v1/uploads/presign', { object_key: `uploads/someone-else/${pid}/a.mp4`, content_type: 'video/mp4' });

      // UI: 촬영 가이드 → 2초짜리 영상 → 막힘 → 다른 영상 → 통과
      await page.goto(`${FRONTEND_URL}/`, { waitUntil: 'networkidle' });
      await page.getByRole('button', { name: /남은 크레딧/ }).waitFor({ state: 'visible' });
      await dwell(900);
      let n = 0;
      const cap = async (slug) => {
        if (slug === 'product') { n = 1; await captureShot('01_product', '1/8 제품 정보'); }
        if (slug === 'guide') { await captureShot('02_guide', '5/8 촬영 가이드'); }
      };
      await wizardToUpload(page, { name: '초흡수 PVA 물걸레 스펀지', intro: '물기를 순식간에 빨아들이는 3초 흡수력', capture: cap, dwell });
      await page.locator('input[type="file"]').setInputFiles(shortClip);
      await page.getByText('too_short_2s.mp4').waitFor({ state: 'visible', timeout: 5000 });
      await dwell(1400);
      await captureShot('03_short_clip_picked', '6/8 2초 영상 선택');
      const cP = page.waitForResponse((r) => r.url().includes('/uploads/complete') && r.request().method() === 'POST', { timeout: 30000 });
      await page.getByRole('button', { name: '훅 붙여서 만들기' }).click();
      const cRes = await cP;
      assert(cRes.status() === 400, `UI short clip: uploads/complete expected 400, got ${cRes.status()}`);
      await page.getByRole('heading', { name: '이 영상으론 못 굽겠어요' }).waitFor({ state: 'visible', timeout: 15000 });
      const failText = await page.locator('body').innerText();
      await dwell(2000);
      await captureShot('04_rejected', '길이 미달 · 업로드 거절', true);
      await page.getByRole('button', { name: '다른 영상 올리기' }).click();
      await page.getByRole('heading', { name: '영상 올리기' }).waitFor({ state: 'visible', timeout: 10000 });
      await page.locator('input[type="file"]').setInputFiles(pvaDemoMp4);
      await page.getByText('pva_sponge_demo.mp4').waitFor({ state: 'visible', timeout: 5000 });
      await dwell(1400);
      const c2P = page.waitForResponse((r) => r.url().includes('/uploads/complete') && r.request().method() === 'POST', { timeout: 30000 });
      const r2P = page.waitForResponse((r) => r.url().includes('/renders') && r.request().method() === 'POST', { timeout: 40000 });
      await page.getByRole('button', { name: '훅 붙여서 만들기' }).click();
      const c2 = await c2P;
      assert(c2.status() === 200, `valid clip uploads/complete expected 200, got ${c2.status()}`);
      const c2Body = await c2.json();
      assert((await r2P).status() === 202, 'renders expected 202 after valid upload');
      await page.waitForTimeout(1500);
      await captureShot('05_accepted_generating', '정상 영상 통과 · 만드는 중');
      await waitRenderDone(page, dwell);
      await dwell(1800);
      await captureShot('06_review', '7/8 영상 확인');
      return {
        product_info_cached_2nd: pi2.json.cached, short_clip_api: badShort.status, spoof_api: badSpoof.status, valid_status: good.json.status, valid_upload_status: good.json.upload_status,
        presign_unauth: noAuth.status, presign_foreign_prefix: foreign.status, ui_fail_text_has_detail: failText.includes('초'), ui_total_duration_sec: c2Body.total_duration_sec ?? null,
      };
    }), { allowResponse: (res, pathname) => res.status() === 400 && pathname.endsWith('/uploads/complete') });

    // ---------- E2E-L12: 썸네일 안전 영역 · 서명 URL Range 스트리밍 · 변조 차단 ----------
    if (want('12_local_media_delivery')) await recordFeature('12_local_media_delivery', FRONTEND_URL, async ({ context, page, captureShot, dwell }) => dumpOnFail(page, 'L12', async () => {
      await addLocalSessionCookie(context, seed.cookie_token);
      const mediaStatuses = [];
      page.on('response', (res) => { try { const u = new URL(res.url()); if (u.pathname.startsWith('/v1/media/')) mediaStatuses.push({ s: res.status(), ct: res.headers()['content-type'] || '', range: res.request().headers()['range'] || '' }); } catch { /* ignore */ } });
      let pid = state.completedProjectId;
      if (!pid) {
        const list = await (await fetch(`${BACKEND_URL}/v1/projects`, { headers: cookieHeader })).json();
        const items = list.items || list.projects || [];
        console.log('L12 project list statuses:', items.map((i) => `${i.project_id}:${i.status}`).join(', '));
        pid = items.find((i) => /DELIVER|READY|DONE|COMPLETE/.test(i.status) && i.latest_job_id)?.project_id;
      }
      assert(Boolean(pid), 'L12 needs a completed project');
      const del = await (await fetch(`${BACKEND_URL}/v1/projects/${pid}/deliverables`, { headers: cookieHeader })).json();
      const vUrl = del.video?.stream_url || del.video?.download_url;
      assert(Boolean(vUrl), `L12: deliverable video url missing: ${JSON.stringify(del).slice(0, 400)}`);
      const full = vUrl.startsWith('http') ? vUrl : `${BACKEND_URL}${vUrl}`;
      // 서명 URL 은 쿠키 없이도 열려야 한다 (토큰이 권한)
      const whole = await fetch(full);
      const wholeLen = Number(whole.headers.get('content-length') || 0);
      await whole.arrayBuffer();
      const part = await fetch(full, { headers: { Range: 'bytes=0-1023' } });
      const partBuf = await part.arrayBuffer();
      assert(part.status === 206 && partBuf.byteLength === 1024, `Range expected 206/1024B, got ${part.status}/${partBuf.byteLength}`);
      assert((part.headers.get('content-range') || '').startsWith('bytes 0-1023/'), `Content-Range wrong: ${part.headers.get('content-range')}`);
      const tail = await fetch(full, { headers: { Range: 'bytes=-500' } });
      const tailLen = (await tail.arrayBuffer()).byteLength;
      const beyond = await fetch(full, { headers: { Range: `bytes=${wholeLen + 10}-` } });
      const u = new URL(full);
      const tok = decodeURIComponent(u.pathname.split('/v1/media/')[1]);
      const flip = (s, i) => s.slice(0, i) + (s[i] === 'A' ? 'B' : 'A') + s.slice(i + 1);
      const tamperedSig = await fetch(`${u.origin}/v1/media/${encodeURIComponent(flip(tok, tok.length - 3))}`);
      const tamperedBody = await fetch(`${u.origin}/v1/media/${encodeURIComponent(flip(tok, 6))}`);
      assert(tamperedSig.status === 403 && tamperedBody.status === 403, `tampered tokens expected 403, got ${tamperedSig.status}/${tamperedBody.status}`);

      // 썸네일 4종 서버 렌더 + 1:1 안전 영역
      const styles = ['pov-bar', 'serif-outline', 'white-label', 'invert-box'];
      const thumbs = {};
      for (const style of styles) {
        const r = await fetch(`${BACKEND_URL}/v1/projects/${pid}/thumbnail`, { method: 'POST', headers: { ...cookieHeader, 'Content-Type': 'application/json' }, body: JSON.stringify({ headline_lines: ['3초 만에', '물기 순삭'], highlight_word: '순삭', style }) });
        const j = await r.json();
        assert(r.status === 200 && j.image_url, `thumbnail ${style} expected 200: ${JSON.stringify(j).slice(0, 300)}`);
        assert(j.safe_zone_1_1_ok === true, `thumbnail ${style} safe zone failed: ${JSON.stringify(j.warnings)}`);
        const img = await fetch(j.image_url.startsWith('http') ? j.image_url : `${BACKEND_URL}${j.image_url}`);
        const bytes = (await img.arrayBuffer()).byteLength;
        assert(img.status === 200 && (img.headers.get('content-type') || '').includes('image/png') && bytes > 10240, `thumbnail ${style} PNG invalid: ${img.status} ${bytes}`);
        thumbs[style] = { w: j.width, h: j.height, bytes };
      }

      // UI: 내 영상 → 완료 영상 열기 → 재생(Range) → 썸네일 안전 영역
      await page.goto(`${FRONTEND_URL}/`, { waitUntil: 'networkidle' });
      await page.getByRole('button', { name: /남은 크레딧/ }).waitFor({ state: 'visible' });
      await dwell(1200);
      await captureShot('01_home', '홈 · 완료 영상');
      const card = page.locator('.n-project-wrap').filter({ hasText: '완료' }).filter({ hasText: '초흡수 PVA' }).first();
      await card.scrollIntoViewIfNeeded();
      await card.getByRole('button').first().click();
      // 완료 영상은 8/8 썸네일 화면으로 열린다
      await page.getByRole('heading', { name: '썸네일·내려받기' }).waitFor({ state: 'visible', timeout: 15000 });
      await page.waitForFunction(() => { const i = [...document.querySelectorAll('.n-thumb-option__frame img')]; return i.length >= 4 && i.every((x) => x.complete && x.naturalWidth > 0); }, { timeout: 20000 });
      await page.getByRole('textbox', { name: '썸네일 글자' }).fill('3초 만에 물기 순삭');
      await page.waitForFunction(() => [...document.querySelectorAll('.n-thumb-option__frame')].every((f) => f.textContent?.includes('물기 순삭')), { timeout: 5000 });
      await dwell(1600);
      await captureShot('02_thumbnail_styles', '8/8 썸네일 4종');
      const sz = page.getByRole('switch', { name: '안전 영역 보기' });
      await sz.click();
      assert((await sz.getAttribute('aria-checked')) === 'true', 'L12: safe zone toggle should be on');
      await page.getByText('넘으면 안 되는 릴스 UI 영역').first().waitFor({ state: 'visible', timeout: 5000 });
      const overflow = await page.evaluate(() => [...document.querySelectorAll('.n-thumb-option__frame')].map((f) => f.scrollWidth - f.clientWidth));
      assert(overflow.every((d) => d <= 2), `L12: thumbnail text overflows frame: ${overflow}`);
      await dwell(2000);
      await captureShot('03_safe_zone_on', '안전 영역 보기 켬');
      // 썸네일 내려받기 → 서명 URL PNG
      const tP = page.waitForResponse((r) => r.url().includes('/thumbnail') && r.request().method() === 'POST', { timeout: 30000 });
      await page.getByRole('button', { name: '썸네일 내려받기' }).click();
      const tRes = await tP;
      const tJson = await tRes.json();
      assert(tRes.status() === 200 && tJson.safe_zone_1_1_ok === true, `L12: UI thumbnail download failed safe zone: ${JSON.stringify(tJson).slice(0, 500)}`);
      await page.getByRole('button', { name: '썸네일 내려받기' }).waitFor({ state: 'visible', timeout: 15000 });
      await sz.click();
      await dwell(900);

      // 이전 → 7/8 영상 확인에서 실제 재생 (브라우저가 Range 로 받아 간다)
      await page.getByRole('button', { name: '이전' }).click();
      await page.locator('video').first().waitFor({ state: 'visible', timeout: 15000 });
      const played = await page.evaluate(async () => {
        const v = document.querySelector('video');
        if (v.readyState < 1) await new Promise((r) => { v.onloadedmetadata = r; setTimeout(r, 10000); });
        v.muted = true;
        try { await v.play(); } catch (e) { /* ignore */ }
        await new Promise((r) => setTimeout(r, 4000));
        const out = { w: v.videoWidth, h: v.videoHeight, dur: v.duration, t: v.currentTime, err: v.error && v.error.code };
        v.pause();
        return out;
      });
      assert(!played.err && played.t > 1.5, `L12: video did not play: ${JSON.stringify(played)}`);
      assert(played.w === 1080 && played.h === 1920, `L12: expected 1080x1920, got ${played.w}x${played.h}`);
      await captureShot('04_review_playing', '7/8 영상 재생 (서명 URL · Range)', true);
      const vidResp = mediaStatuses.filter((m) => m.ct.includes('video'));
      assert(vidResp.length > 0 && vidResp.every((m) => m.s === 200 || m.s === 206), `L12: video media responses unexpected: ${JSON.stringify(vidResp)}`);
      await dwell(1200);
      return { project_id: pid, whole_bytes: wholeLen, range_status: part.status, content_range: part.headers.get('content-range'), suffix_range: `${tail.status}/${tailLen}B`, beyond_range: beyond.status, tampered_sig: tamperedSig.status, tampered_body: tamperedBody.status, thumbs, played, video_responses: vidResp.map((m) => `${m.s}${m.range ? ` (${m.range})` : ''}`) };
    }));

    const summaryPath = path.join(ARTIFACT_DIR, 'recordings', 'e2e_results_rest.json');
    mkdirSync(path.dirname(summaryPath), { recursive: true });
    writeFileSync(summaryPath, JSON.stringify({ generated_at: new Date().toISOString(), features: featureResults }, null, 2));
    console.log(`ALL_PASSED ${featureResults.length} features -> ${summaryPath}`);
  } catch (err) {
    if (backendLogs) {
      console.error('=== BACKEND LOG TAIL ===\n' + backendLogs);
    }
    throw err;
  } finally {
    await browser?.close().catch(() => {});
    plannerServer?.close();
    killTree(frontendProc);
    killTree(backendProc);
    rmSync(tempRoot, { recursive: true, force: true });
    rmSync(RAW_VIDEO_DIR, { recursive: true, force: true });
    rmSync(THUMBS_DIR, { recursive: true, force: true });
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});

