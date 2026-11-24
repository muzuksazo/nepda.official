// 버셀 서버 함수: 브라우저가 뽑아 보낸 장면 12장을 Gemini 에게 보여 주고 C안(문제 상황 3컷 훅) 기획을 받는다.
// PR2/remix.py 를 그대로 옮긴 것 — 지시문(SYSTEM)·답 형식(SCHEMA)·다듬기(cleanPlan)를 바꾸면 두 파일을 같이 고칠 것.
// 필요한 환경 변수(버셀 설정): GEMINI_API_KEY, HOOKCUT_PASSWORD
const crypto = require("crypto");

// 고를 수 있는 모델 (페이지의 선택지와 같게)
const MODELS = {
  "gemini-3.5-flash": "Gemini 3.5 Flash",
  "gemini-3.5-flash-lite": "Gemini 3.5 Flash Lite",
  "gemini-3.1-flash-lite": "Gemini 3.1 Flash Lite",
};
const DEFAULT_MODEL = "gemini-3.5-flash-lite";
const MAX_FRAMES = 12;
const MAX_FRAME_B64 = 400 * 1024; // 장면 한 장 최대 크기 (가로 512 JPEG 이면 보통 50KB 안팎)

const CONCEPT_C = `C
앞 3초
보는 사람의 문제 상황에서 바로 시작
콘티 3선 방식

확인하려는 것
맥락이 맞으면 영상이 화려하지 않아도 보는가`;

const SYSTEM = `너는 소상공인·셀러의 세로 숏폼 광고를 편집하는 사람이야. 올라온 원본 광고 영상을 팀이 정한 실험 설계(C안)에 맞게 다시 구성해.

완성 영상 구조:
1. 훅 0~15초: 보는 사람이 겪는 문제 상황 3컷(각 5초). 컷마다 화면 한 장과 자막 두 줄. 첫 줄(caption)은 컷 시작과 함께, 둘째 줄(sub)은 컷 중간에 붙어. 첫 컷 첫 줄만 보고도 3초 안에 '내 얘기다' 싶게. 세 컷이 불편이 쌓이는 순서(상황 → 실패나 번거로움 → 한계)로 이어지게 해. 화려한 효과 없이 맥락으로 붙잡는 게 목적이야.
2. 브릿지 1.2초: 이제 광고로 넘어간다는 걸 솔직하게 말하는 한 줄. '광고'라는 단어를 꼭 넣어.
3. 본편: 원본 영상에서 고른 구간들을 시간 순서대로 이어 붙인 것. 훅에서 꺼낸 문제가 풀리는 흐름이 되게 골라.
4. 엔딩: 버튼 문구 한 줄.

지켜 줘:
- 모든 문구는 자연스러운 한국어. 훅 자막(첫 줄·둘째 줄)과 브릿지는 16자 이내, 본편 자막 14자 이내, 버튼 문구 12자 이내.
- 영상에 보이지 않는 기능, 숫자, 가격, 후기, 효능은 지어내지 마. 확실하지 않으면 보이는 것만 말해.
- 훅 6줄(3컷 × 두 줄)은 전부 보는 사람이 겪는 불편이어야 해. 제품 이름, 제품 기능, 해결 방법, '간편', '해결', '꽂기만' 같은 해결 표현은 훅에 쓰지 마. 해결은 본편의 몫이야.
- 훅 문장은 보는 사람의 일상 장면처럼 구체적으로(언제, 어디서, 무엇이 번거로운지). 첫 줄은 상황, 둘째 줄은 그 상황의 속마음이나 결과.
- 훅 컷 화면은 주어진 프레임 번호 중에서 골라. 제품이 주인공인 장면은 피하고, 조리 공간·재료·도구처럼 문제 맥락이 보이는 장면을 골라. 세 컷이 같은 프레임이면 안 돼. 화면 아래쪽 자막은 잘려 나가니 신경 쓰지 마.
{MAIN_RULE}
- 광고임을 숨기지 마.

가게·제품 정보(info)도 영상에서 읽어 채워 줘. 엔딩 화면에 그대로 들어가:
- brand: 로고나 자막에 보이는 가게·브랜드 이름. product: 제품 이름(자막·포장에 보이는 그대로).
- strength: 영상이 가장 내세우는 장점 한 줄(18자 이내). offer: 영상에 나온 혜택이나 가격. place: 영상에 나온 판매처나 위치.
- 영상에서 확인되지 않는 값은 빈 문자열로 둬. 가격이나 판매처를 추측해서 쓰지 마.`;

const B_TONE = `

톤: B급 느낌으로 만들어 줘.
- 훅 문구는 과장된 자기비하·현타 유머로, 짧게 툭 던지는 일상 말투(예: '실화냐', '현타 옴', '이게 맞나'). 그래도 내용은 실제로 겪는 불편이어야 해.
- 컷마다 sticker: 화면 구석에 붙는 한마디(6자 이내, 감탄사·의성어. 예: '후…', '띠용', '현타', '아놔'). 세 컷이 서로 달라야 해.
- 브릿지도 B급으로, 광고라는 걸 능청스럽게 인정하는 한 줄(예: '네, 광고 맞습니다 (꾸벅)').
- 실존 연예인·유명인 이름, 특정 방송·밈 대사 인용, 비하·혐오 표현은 쓰지 마. 본편 자막은 담백하게 사실만.`;

const str = { type: "string" };
const SCHEMA = {
  type: "object",
  additionalProperties: false,
  required: ["info", "problem", "cuts", "bridge", "segments", "cta"],
  properties: {
    info: {
      type: "object",
      description: "영상에서 읽은 가게·제품 정보. 확인되지 않으면 빈 문자열",
      additionalProperties: false,
      required: ["brand", "product", "strength", "offer", "place"],
      properties: { brand: str, product: str, strength: str, offer: str, place: str },
    },
    problem: { type: "string", description: "보는 사람이 겪는 문제를 한 문장으로" },
    cuts: {
      type: "array",
      description: "훅 3컷, 순서대로",
      items: {
        type: "object",
        additionalProperties: false,
        required: ["caption", "sub", "sticker", "frame"],
        properties: {
          caption: str,
          sub: str,
          sticker: { type: "string", description: "B급 톤일 때 화면 구석 스티커 한마디 (아니면 빈 문자열)" },
          frame: { type: "integer" },
        },
      },
    },
    bridge: str,
    segments: {
      type: "array",
      description: "본편에 쓸 원본 구간 (초 단위, 시간 순서)",
      items: {
        type: "object",
        additionalProperties: false,
        required: ["start", "end", "caption"],
        properties: { start: { type: "number" }, end: { type: "number" }, caption: str },
      },
    },
    cta: str,
  },
};

const HOOK_SEC = 15.0, BRIDGE_SEC = 1.2, END_SEC = 2.3;

class RemixError extends Error {
  constructor(message, status = 502) { super(message); this.status = status; }
}

function mainTarget(totalSeconds, dur) {
  // 전체 길이에서 훅·전환·엔딩을 뺀 만큼이 본편. 원본보다 길 수는 없다
  const want = totalSeconds ? Number(totalSeconds) - HOOK_SEC - BRIDGE_SEC - END_SEC : 14.0;
  return Math.round(Math.max(6.0, Math.min(want, dur - 0.5)) * 10) / 10;
}

function systemPrompt(mainSec, dur, tone) {
  const rule = mainSec <= 18
    ? `- 본편 구간은 2~4개, 각 2초 이상, 합계 약 ${mainSec}초(±2초), 원본 길이 안에서. 원본 자막이 문장 중간에 끊기지 않게 프레임 시각 사이를 넉넉히 잡아.`
    : `- 본편 구간은 3~6개, 각 3초 이상, 합계 약 ${mainSec}초(±1.5초). 원본은 ${dur}초라서 대부분을 쓰게 돼. ` +
      "겹치지 않게 시간 순서대로, 빼는 부분은 반복되거나 약한 장면 위주로. 구간 경계는 원본 자막 문장이 끝나는 곳에 맞춰. " +
      "구간마다 자막을 달되 원본 자막과 같은 말은 피하고, 그 구간이 훅의 어떤 불편을 푸는지 짧게.";
  const plain = "\n\n톤: 담백하게. sticker 는 모두 빈 문자열로 둬.";
  return SYSTEM.replace("{MAIN_RULE}", rule) + (tone === "b" ? B_TONE : plain);
}

function userParts(meta) {
  // 프레임 12장(시각 표시) + 요청 문장
  const parts = [];
  for (const f of meta.frames) {
    parts.push({ text: `[프레임 ${f.index}] ${f.t}초` });
    parts.push({ inline_data: { mime_type: "image/jpeg", data: f.data } });
  }
  parts.push({
    text: `원본 영상 길이: ${meta.duration}초, 화면 ${meta.w}x${meta.h}. 위 프레임은 영상 전체에서 고르게 뽑은 장면이야.\n\n` +
      `팀이 정한 실험 설계(C안):\n${CONCEPT_C}\n\n이 설계대로 영상을 재구성해 줘.`,
  });
  return parts;
}

async function askGemini(meta, model, system) {
  const key = process.env.GEMINI_API_KEY;
  if (!key) throw new RemixError("버셀에 Gemini API 키가 설정돼 있지 않아요. (GEMINI_API_KEY)", 500);
  const body = {
    system_instruction: { parts: [{ text: system }] },
    contents: [{ role: "user", parts: userParts(meta) }],
    generationConfig: { responseMimeType: "application/json", responseJsonSchema: SCHEMA },
  };
  let r;
  try {
    r = await fetch(`https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "x-goog-api-key": key },
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(110000),
    });
  } catch (e) {
    throw new RemixError("Gemini API 에 연결하지 못했어요. 잠시 뒤에 다시 눌러 주세요.");
  }
  const d = await r.json().catch(() => ({}));
  if (!r.ok) {
    const msg = (d.error && d.error.message) || "";
    if ((r.status === 400 || r.status === 403) && msg.includes("API key")) throw new RemixError("Gemini API 키가 올바르지 않아요.", 500);
    if (r.status === 429) throw new RemixError("Gemini 사용량 한도에 걸렸어요. 잠시 뒤에 다시 눌러 주세요.");
    throw new RemixError(`Gemini API 오류 (${r.status}): ${msg.slice(0, 200)}`);
  }
  const cands = d.candidates || [];
  if (!cands.length) {
    const reason = (d.promptFeedback || {}).blockReason || "";
    throw new RemixError("Gemini 가 답을 주지 않았어요. " + (reason ? `(${reason})` : ""));
  }
  const c = cands[0];
  if (c.finishReason && c.finishReason !== "STOP") throw new RemixError(`Gemini 답이 중간에 멈췄어요 (${c.finishReason}). 다시 눌러 주세요.`);
  const text = ((c.content || {}).parts || []).filter((p) => !p.thought).map((p) => p.text || "").join("");
  try {
    return { raw: JSON.parse(text), model: d.modelVersion || model };
  } catch (e) {
    throw new RemixError("모델 답을 읽지 못했어요. 다시 눌러 주세요.");
  }
}

function bridgeText(b) {
  // 브릿지에는 광고라는 사실이 꼭 들어가야 한다
  b = String(b || "").trim().slice(0, 24);
  if (!b) return "그래서 바꿨어요 (광고)";
  return b.includes("광고") ? b : (b + " (광고)").slice(0, 30);
}

const s = (v, n) => String(v == null ? "" : v).trim().slice(0, n);

function cleanPlan(plan, meta, mainSec) {
  // 모델 답을 영상 범위와 화면 규칙에 맞게 다듬는다
  const n = meta.frames.length, dur = meta.duration;
  const cuts = (Array.isArray(plan.cuts) ? plan.cuts : []).filter((c) => c && typeof c === "object").slice(0, 3);
  const used = new Set();
  cuts.forEach((c, i) => {
    let f = parseInt(c.frame, 10);
    if (!Number.isFinite(f)) f = i;
    f = Math.min(Math.max(f, 0), n - 1);
    while (used.has(f) && used.size < n) f = (f + 1) % n;
    used.add(f);
    c.frame = f; c.caption = s(c.caption, 24); c.sub = s(c.sub, 24); c.sticker = s(c.sticker, 8);
  });
  while (cuts.length < 3) {
    let f = 0; while (used.has(f)) f++;
    used.add(f);
    cuts.push({ caption: "", sub: "", sticker: "", frame: f });
  }
  const segs = [];
  let last = 0, total = 0;
  const capTotal = mainSec + 1.5; // 정한 본편 길이를 크게 넘지 않게
  const raw = (Array.isArray(plan.segments) ? plan.segments : []).filter((x) => x && typeof x === "object")
    .sort((a, b) => (Number(a.start) || 0) - (Number(b.start) || 0));
  for (const x of raw) {
    const a = Math.max(Number(x.start) || 0, last, 0);
    const b = Math.min(Number(x.end) || 0, dur, a + (capTotal - total));
    if (b - a >= 1.0) {
      segs.push({ start: Math.round(a * 100) / 100, end: Math.round(b * 100) / 100, caption: s(x.caption, 24) });
      last = b; total += b - a;
    }
  }
  if (!segs.length) segs.push({ start: 0, end: Math.round(Math.min(dur, 14) * 100) / 100, caption: "" });
  const vi = plan.info && typeof plan.info === "object" ? plan.info : {};
  const limits = { brand: 20, product: 30, strength: 30, offer: 30, place: 30 };
  const info = {};
  for (const k of Object.keys(limits)) info[k] = s(vi[k], limits[k]);
  return {
    info,
    problem: s(plan.problem, 200),
    cuts,
    bridge: bridgeText(plan.bridge),
    segments: segs,
    cta: s(plan.cta, 16) || "프로필 링크에서 확인",
  };
}

function passwordOk(given) {
  // 비밀번호가 맞을 때만 Gemini 를 부른다 (아무나 눌러 내 키 요금이 나가는 걸 막기)
  const pw = process.env.HOOKCUT_PASSWORD || "";
  if (!pw) return false;
  const a = crypto.createHash("sha256").update(String(given || "")).digest();
  const b = crypto.createHash("sha256").update(pw).digest();
  return crypto.timingSafeEqual(a, b);
}

function readMeta(body) {
  // 브라우저가 보낸 장면 묶음을 검사한다
  const frames = Array.isArray(body.frames) ? body.frames : [];
  if (frames.length < 3 || frames.length > MAX_FRAMES) throw new RemixError("장면이 3~12장이어야 해요.", 400);
  const out = frames.map((f, i) => {
    const data = String((f && f.data) || "");
    if (!data || data.length > MAX_FRAME_B64 || !/^[A-Za-z0-9+/=]+$/.test(data)) throw new RemixError("장면 사진 형식이 올바르지 않아요.", 400);
    return { index: i, t: Math.round((Number(f.t) || 0) * 100) / 100, data };
  });
  const duration = Math.round((Number(body.duration) || 0) * 100) / 100;
  if (!(duration > 0 && duration < 3600)) throw new RemixError("영상 길이를 읽지 못했어요.", 400);
  return { frames: out, duration, w: parseInt(body.w, 10) || 0, h: parseInt(body.h, 10) || 0 };
}

module.exports = async (req, res) => {
  res.setHeader("Cache-Control", "no-store");
  if (req.method !== "POST") return res.status(405).json({ error: "POST 로만 불러 주세요." });
  if (!passwordOk(req.headers["x-hookcut-password"])) {
    return res.status(401).json({ error: "비밀번호가 맞지 않아요.", need_password: true });
  }
  try {
    const body = req.body && typeof req.body === "object" ? req.body : {};
    const model = MODELS[body.model] ? body.model : DEFAULT_MODEL;
    const tone = body.tone === "b" ? "b" : "";
    const meta = readMeta(body);
    const mainSec = mainTarget(body.total_seconds || 50, meta.duration);
    const { raw, model: used } = await askGemini(meta, model, systemPrompt(mainSec, meta.duration, tone));
    const plan = cleanPlan(raw, meta, mainSec);
    plan.model = used;
    plan.tone = tone;
    plan.duration = meta.duration;
    plan.frame_times = plan.cuts.map((c) => meta.frames[c.frame].t);
    // 훅 컷 사진은 브라우저가 가진 고해상도 장면에서 직접 자른다 (plan.cuts[].frame 번호로)
    return res.status(200).json(plan);
  } catch (e) {
    const status = e instanceof RemixError ? e.status : 500;
    return res.status(status).json({ error: e instanceof RemixError ? e.message : "재구성 중 오류가 났어요." });
  }
};
