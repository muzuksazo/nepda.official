// Inworld TTS 로 나레이션 만들기 (pipeline/scripts/tts.mjs 의 addVoice 와 같은 일을 한다).
//   b/.env: INWORLD_API_KEY (Portal 의 Base64 키 그대로), INWORLD_VOICE_ID (예: 시스템 목소리 이름 또는 workspace__voice),
//           INWORLD_MODEL (기본 inworld-tts-2), INWORLD_RATE (speakingRate 0.5~1.5, 기본 1.1)
// 장면마다 scene.say → public/tts/<plan.id>_s<i>.wav, 음성이 장면보다 길면 장면을 늘린다(+0.25초).
// 반전(마지막 장면)이 "그런데"로 시작하면 "그런데!!"를 따로 크게 읽고 잠깐 쉰 뒤 나머지를 잇는다 (제품이 쾅 내려앉는 순간).
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";

const TAIL = 0.25;
/** 강조 "그런데!!" 뒤 쉼(초)과 음량 배율 */
export const EMPH_PAUSE = 0.22;
const EMPH_GAIN = 1.6;
const ENDPOINT = "https://api.inworld.ai/tts/v1/voice";

type Scene = { say?: string; durationSec: number; voice?: string; voiceSec?: number };
type Plan = { id?: string; scenes: Scene[]; hookSeconds: number };

export function inworldConfig() {
  const key = process.env.INWORLD_API_KEY;
  const voiceId = process.env.INWORLD_VOICE_ID;
  if (!key || !voiceId) throw new Error("b/.env 에 INWORLD_API_KEY 와 INWORLD_VOICE_ID 가 필요합니다.");
  return {
    key,
    voiceId,
    modelId: process.env.INWORLD_MODEL || "inworld-tts-2",
    rate: Number(process.env.INWORLD_RATE || 1.1),
  };
}

function wavInfo(b: Buffer) {
  const ch = b.readUInt16LE(22), rate = b.readUInt32LE(24), byteRate = b.readUInt32LE(28);
  let off = 12;
  while (off < b.length - 8 && b.toString("ascii", off, off + 4) !== "data") off += 8 + b.readUInt32LE(off + 4);
  if (b.toString("ascii", off, off + 4) !== "data") throw new Error("wav data 청크가 없습니다");
  // 스트리밍식 헤더는 data 크기가 0/최대값일 수 있어 실제 길이로 맞춘다
  const size = Math.min(b.readUInt32LE(off + 4) || b.length, b.length - off - 8);
  return { ch, rate, byteRate, off, start: off + 8, size };
}

/** 앞뒤 무음을 잘라 낸다 (16-bit PCM). */
function trimWav(b: Buffer, threshold = 400, keepSec = 0.1): Buffer {
  const { ch, rate, off, start, size } = wavInfo(b);
  const frame = 2 * ch, n = Math.floor(size / frame);
  const loud = (i: number) => Math.abs(b.readInt16LE(start + i * frame)) > threshold;
  let a = 0, z = n - 1;
  while (a < n && !loud(a)) a++;
  while (z > a && !loud(z)) z--;
  const keep = Math.floor(keepSec * rate);
  a = Math.max(0, a - keep);
  z = Math.min(n - 1, z + keep);
  const data = b.subarray(start + a * frame, start + (z + 1) * frame);
  const head = Buffer.from(b.subarray(0, start));
  head.writeUInt32LE(data.length, off + 4);
  head.writeUInt32LE(head.length - 8 + data.length, 4);
  return Buffer.concat([head, data]);
}

/** 여러 wav(같은 형식)를 사이 무음과 함께 잇는다. gains 로 조각마다 음량을 곱한다 (넘치면 자른다). */
function joinWav(parts: Buffer[], gapSec: number[], gains: number[]): Buffer {
  const first = wavInfo(parts[0]);
  const chunks: Buffer[] = [];
  parts.forEach((p, i) => {
    const { start, size } = wavInfo(p);
    const data = Buffer.from(p.subarray(start, start + size));
    const g = gains[i] ?? 1;
    if (g !== 1) for (let k = 0; k + 1 < data.length; k += 2) data.writeInt16LE(Math.max(-32768, Math.min(32767, Math.round(data.readInt16LE(k) * g))), k);
    chunks.push(data);
    const gap = Math.round((gapSec[i] ?? 0) * first.rate) * 2 * first.ch;
    if (gap > 0 && i < parts.length - 1) chunks.push(Buffer.alloc(gap));
  });
  const data = Buffer.concat(chunks);
  const head = Buffer.from(parts[0].subarray(0, first.start));
  head.writeUInt32LE(data.length, first.off + 4);
  head.writeUInt32LE(head.length - 8 + data.length, 4);
  return Buffer.concat([head, data]);
}

/** 반전 문장 "그런데 …" → ["그런데!!", "…"] (아니면 null) */
export function splitEmphasis(say: string): [string, string] | null {
  const m = say.match(/^그런데[\s,!.]+(.+)$/s);
  return m ? ["그런데!!", m[1].trim()] : null;
}

/** 반전 읽기 조각: 조각마다 다음 조각 앞 쉼(초)과 음량 배율 */
export interface RevealPart { text: string; gap: number; gain: number }

/**
 * 반전 문장 "그런데 <제품>은 ~합니다. 그래서 <제품>이 뭐냐고요?" 를 끊어 읽는다:
 *   [그런데!!] 쉼 → [<제품>은 ~합니다.] 긴 쉼 → [그래서] 쉼 → [<제품>이 뭐냐고요?]
 * "그래서" 앞뒤 쉼으로 반전 효과를 키운다. 모양이 다르면 "그런데!!" 만 떼거나 null.
 */
export function splitReveal(say: string): RevealPart[] | null {
  const m = say.match(/^그런데[\s,!.]+(.+?[.!])\s*그래서[\s,]+(.+)$/s);
  if (m)
    return [
      { text: "그런데!!", gap: Number(process.env.B_PAUSE_AFTER_HOWEVER ?? 0.22), gain: EMPH_GAIN },
      { text: m[1].trim(), gap: Number(process.env.B_PAUSE_BEFORE_SO ?? 0.5), gain: 1 },
      { text: "그래서", gap: Number(process.env.B_PAUSE_AFTER_SO ?? 0.32), gain: 1.15 },
      { text: m[2].trim(), gap: 0, gain: 1.05 },
    ];
  const e = splitEmphasis(say);
  return e ? [{ text: e[0], gap: EMPH_PAUSE, gain: EMPH_GAIN }, { text: e[1], gap: 0, gain: 1 }] : null;
}

export async function synthInworld(text: string): Promise<{ wav: Buffer; chars: number; ms: number }> {
  const c = inworldConfig();
  const t0 = performance.now();
  const res = await fetch(ENDPOINT, {
    method: "POST",
    headers: { Authorization: `Basic ${c.key}`, "Content-Type": "application/json" },
    body: JSON.stringify({
      text,
      voiceId: c.voiceId,
      modelId: c.modelId,
      language: "ko-KR",
      audioConfig: { audioEncoding: "LINEAR16", sampleRateHertz: 44100, speakingRate: c.rate },
    }),
  });
  const body = (await res.json().catch(() => ({}))) as { audioContent?: string; usage?: { processedCharactersCount?: number }; message?: string; error?: { message?: string } };
  if (!res.ok || !body.audioContent)
    throw new Error(`Inworld TTS 실패 (${res.status}): ${body.message ?? body.error?.message ?? "응답에 audioContent 없음"}`);
  return { wav: trimWav(Buffer.from(body.audioContent, "base64")), chars: body.usage?.processedCharactersCount ?? text.length, ms: performance.now() - t0 };
}

/** tts.mjs 의 addVoice 와 같은 결과를 Inworld 로 만든다. */
export async function addVoiceInworld(planPath: string, pipelineDir: string, log: (m: string) => void = () => {}) {
  const plan = JSON.parse(readFileSync(planPath, "utf8")) as Plan;
  const prefix = plan.id ? `${plan.id}_` : "";
  const dir = join(pipelineDir, "public/tts");
  mkdirSync(dir, { recursive: true });
  let chars = 0;
  const lastIdx = plan.scenes.map((s) => !!s.say).lastIndexOf(true);
  for (const [i, s] of plan.scenes.entries()) {
    if (!s.say) continue;
    const parts = i === lastIdx ? splitReveal(s.say) : null;
    let r: { wav: Buffer; chars: number; ms: number };
    if (parts) {
      const got = await Promise.all(parts.map((p) => synthInworld(p.text)));
      r = {
        wav: joinWav(got.map((g) => g.wav), parts.map((p) => p.gap), parts.map((p) => p.gain)),
        chars: got.reduce((a, g) => a + g.chars, 0),
        ms: Math.max(...got.map((g) => g.ms)),
      };
      log(`[tts] inworld s${i} 반전 끊어 읽기: ${parts.map((p) => `"${p.text}"${p.gap ? ` +${p.gap}s` : ""}`).join(" ")}`);
    } else r = await synthInworld(s.say);
    chars += r.chars;
    const file = join(dir, `${prefix}s${i}.wav`);
    writeFileSync(file, r.wav);
    const info = wavInfo(r.wav);
    const sec = info.size / info.byteRate;
    s.voice = `tts/${prefix}s${i}.wav`;
    s.voiceSec = +sec.toFixed(2);
    if (sec + TAIL > s.durationSec) s.durationSec = +(sec + TAIL).toFixed(2);
    log(`[tts] inworld s${i} ${sec.toFixed(2)}s (${Math.round(r.ms)}ms) -> scene ${s.durationSec}s  "${s.say}"`);
  }
  plan.hookSeconds = +plan.scenes.reduce((a, s) => a + s.durationSec, 0).toFixed(2);
  writeFileSync(planPath, JSON.stringify(plan, null, 2));
  return { scenes: plan.scenes, hookSeconds: plan.hookSeconds, chars };
}
