// 본편(제품 촬영 영상) 파이프라인 — 훅 종류(A/B/C)와 상관없는 공용 단계.
//   제품 촬영 영상 폴더 + 제품 정보 → 10초 내외 설명 영상(body.mp4) + 자막 데이터(body.captions.json)
//   그리고 아무 훅 영상(mp4) 뒤에 본편을 붙이는 joinVideos (A/C 훅에도 그대로 쓴다)
//
// 단계: 1) 촬영 영상을 세로 1080x1920·30fps 로 정리  2) 클립 프레임을 보고 대본·컷 고르기(LLM, 기본 Sonnet)
//       3) 문장별 음성(Inworld 또는 Edge) → 음성 길이에 맞춰 컷 자르기  4) 훅과 같은 자막 스타일로 Remotion 렌더
// 렌더는 video_test/pipeline 의 HookVideo 를 빌려 쓰고(영상 장면 임시 패치), 끝나면 pipeline 을 원래대로 되돌린다.
import { execFileSync } from "node:child_process";
import { copyFileSync, existsSync, mkdirSync, readdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import { basename, join } from "node:path";
import { pathToFileURL } from "node:url";
import { generateText, Output } from "ai";
import { z } from "zod";
import { priceOf, type StepUsage } from "./cost.js";
import { pipelineDir, snapshotDir } from "./cuts.js";
import { llm, stepOptions } from "./llm.js";
import type { WorkerInput } from "./schema.js";
import { addVoiceInworld, inworldConfig } from "./tts-inworld.js";
import { patchScenes } from "./video.js";

type ProductInfo = WorkerInput["product_info"];
const FPS = 30;
const INWORLD_USD_PER_M_CHARS: Record<string, number> = { "inworld-tts-2": 25, "inworld-tts-2-flash": 15 };

/** Remotion 에 들어 있는 ffmpeg/ffprobe */
export function ffbin(name: "ffmpeg" | "ffprobe"): string {
  const base = join(pipelineDir(), "node_modules/@remotion");
  const dir = existsSync(base) ? readdirSync(base).find((d) => d.startsWith("compositor-")) : undefined;
  const exe = dir ? join(base, dir, process.platform === "win32" ? `${name}.exe` : name) : "";
  if (!exe || !existsSync(exe)) throw new Error(`${name} 을 찾을 수 없습니다 (pipeline/node_modules/@remotion/compositor-*)`);
  return exe;
}
const ff = (args: string[]) => execFileSync(ffbin("ffmpeg"), ["-hide_banner", "-loglevel", "error", "-y", ...args], { stdio: "pipe" });
export function probeSeconds(file: string): number {
  const out = execFileSync(ffbin("ffprobe"), ["-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", file]).toString();
  return Number(out.trim());
}
function hasAudio(file: string): boolean {
  const out = execFileSync(ffbin("ffprobe"), ["-v", "error", "-select_streams", "a", "-show_entries", "stream=index", "-of", "csv=p=0", file]).toString();
  return out.trim().length > 0;
}

const BodySchema = z.object({
  lines: z
    .array(
      z.object({
        narration: z.string().describe("나레이션 한 문장 ('~습니다'체, 숫자는 한글로 읽히게)"),
        caption: z.string().describe("자막: 짧은 구어, 한 줄 8~10자, 최대 2줄(\\n), 숫자는 아라비아 숫자"),
        shots: z
          .array(z.object({ clip: z.number().int(), start: z.number(), end: z.number(), why: z.string() }))
          .describe("이 문장 동안 보여 줄 장면 1~2개 (클립 번호와 초)"),
      })
    )
    .describe("2~3문장"),
});
export type BodyScript = z.infer<typeof BodySchema>;

export interface BodyResult {
  file: string;
  captions: string;
  seconds: number;
  script: BodyScript;
  steps: StepUsage[];
}

/** 제품 촬영 영상 폴더 → 본편 영상 */
export async function makeBody(opts: {
  product: ProductInfo;
  footageDir: string;
  outDir: string;
  seconds?: number;
  tts?: "inworld" | "edge";
  modelId?: string;
  log?: (m: string) => void;
}): Promise<BodyResult> {
  const log = opts.log ?? (() => {});
  const target = opts.seconds ?? 10;
  const modelId = opts.modelId || process.env.B_BODY_MODEL?.trim() || "claude-sonnet-5-5";
  const steps: StepUsage[] = [];
  const out = opts.outDir;
  mkdirSync(join(out, "src"), { recursive: true });
  mkdirSync(join(out, "frames"), { recursive: true });

  // 1) 촬영 영상 정리: 세로 1080x1920(가득 채워 자르기), 30fps, 소리 없음. 회전 정보는 ffmpeg 가 알아서 적용
  const raw = readdirSync(opts.footageDir).filter((f) => /\.(mov|mp4|m4v)$/i.test(f)).sort();
  if (!raw.length) throw new Error(`${opts.footageDir} 에 촬영 영상(mov/mp4)이 없습니다.`);
  let t0 = performance.now();
  const clips = raw.map((f, i) => {
    const dst = join(out, "src", `clip${i + 1}.mp4`);
    if (!existsSync(dst))
      ff(["-i", join(opts.footageDir, f), "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920", "-r", "30", "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", dst]);
    return { index: i + 1, source: f, file: dst, seconds: probeSeconds(dst) };
  });
  steps.push({ step: `본편: 촬영 영상 정리 (${clips.length}개)`, model: "ffmpeg", inputTokens: 0, outputTokens: 0, costUsd: 0, ms: Math.round(performance.now() - t0) });
  log(`[본편] 촬영 영상 ${clips.length}개 정리: ${clips.map((c) => `${c.index}번 ${c.seconds.toFixed(1)}초`).join(", ")}`);

  // 2) 대본·컷 고르기: 클립마다 5프레임(시각 표시)을 보여 준다
  const frames: { clip: number; t: number; path: string }[] = [];
  for (const c of clips)
    for (const k of [0.1, 0.3, 0.5, 0.7, 0.9]) {
      const t = +(c.seconds * k).toFixed(2);
      const p = join(out, "frames", `clip${c.index}_${t.toFixed(2)}.jpg`);
      if (!existsSync(p)) ff(["-ss", String(t), "-i", c.file, "-frames:v", "1", "-vf", "scale=270:-1", p]);
      frames.push({ clip: c.index, t, path: p });
    }
  const p = opts.product;
  const name = p.call_name ?? p.name;
  const syllables = Math.round(target * 4.6);
  const prompt =
    `제품 촬영 영상으로 ${target}초 안팎의 제품 설명 영상(본편)을 만듭니다. 이 본편은 어떤 훅 영상 뒤에도 붙으므로, 훅 내용과 상관없이 제품만 설명합니다.\n` +
    `제품: ${p.name} (나레이션에서 부르는 이름: "${name}")\n` +
    `제품 사실(이것만 말합니다):\n${p.verified_facts.map((f) => `- ${f}`).join("\n")}\n\n` +
    `대본 규칙:\n` +
    `- 2~3문장, 나레이션 전체 ${syllables}음절 이내(문장 사이 쉼 포함 ${target}초). 짧고 또렷하게. '~습니다'체. 첫 문장에 제품 이름("${name}")을 부르고 무엇인지 말합니다.\n` +
    `- 사실 목록의 '~로 표기한다', '~라고 소개한다' 같은 출처 표현은 빼고 제품 설명으로 말합니다. 단 '최대', '국내 최초' 같은 조건·수식은 그대로 둡니다.\n` +
    `- 핵심 특징 1~2개를 숫자와 함께(사실 목록에 있는 것만). 과장·없는 기능 금지. 마지막 문장은 쓰는 방법이나 놓는 곳처럼 바로 떠오르는 장면으로 끝냅니다.\n` +
    `- caption: 짧은 구어 자막, 한 줄 8~10자, 최대 2줄(\\n).\n` +
    `컷 규칙:\n` +
    `- 아래 프레임은 클립별로 시각(초)이 붙어 있습니다. 문장마다 그 말과 가장 잘 맞는 장면을 클립 번호와 시작·끝 초로 고릅니다(문장당 1~2개, 한 컷 1.5초 이상).\n` +
    `- 흔들리거나 흐린 부분, 손이 화면을 가리는 부분, 제품이 안 보이는 부분은 피합니다. 같은 장면을 반복하지 않습니다.\n` +
    `- 시작·끝은 그 클립 길이 안에서: ${clips.map((c) => `${c.index}번 0~${c.seconds.toFixed(1)}초`).join(", ")}.`;
  t0 = performance.now();
  const r = await generateText({
    model: llm(modelId),
    messages: [
      {
        role: "user",
        content: [
          { type: "text", text: prompt },
          ...frames.flatMap((f) => [
            { type: "text" as const, text: `클립 ${f.clip}번 ${f.t.toFixed(1)}초` },
            { type: "image" as const, image: readFileSync(f.path), mediaType: "image/jpeg" },
          ]),
        ],
      },
    ],
    output: Output.object({ schema: BodySchema }),
    maxOutputTokens: 4000,
    providerOptions: stepOptions("scenario", "medium"),
  });
  const inT = r.usage?.inputTokens ?? 0, outT = r.usage?.outputTokens ?? 0;
  steps.push({ step: "본편: 대본·컷 고르기", model: modelId, inputTokens: inT, outputTokens: outT, costUsd: priceOf(modelId, inT, outT), ms: Math.round(performance.now() - t0) });
  const script = r.output as BodyScript;
  log(`[본편] 대본: ${script.lines.map((l) => l.narration).join(" / ")}`);

  // 3)·4) 음성 → 컷 자르기 → 렌더 (pipeline 은 끝나면 원래대로)
  const pdir = pipelineDir();
  const genDir = join(pdir, "src/generated");
  const ttsDir = join(pdir, "public/tts");
  const clipDir = join(pdir, "public/bbody");
  const clipDirExisted = existsSync(clipDir);
  const gen = snapshotDir(genDir);
  const tts = snapshotDir(ttsDir);
  const clipSnap = snapshotDir(clipDir);
  const scenesPath = join(pdir, "src/scenes.tsx");
  const scenesOrig = readFileSync(scenesPath, "utf8");
  const bodyFile = join(out, "body.mp4");
  try {
    writeFileSync(scenesPath, patchScenes(scenesOrig));
    const planPath = join(out, "body.plan.json");
    const plan = {
      id: "body",
      concept: `${name} 본편`,
      hookSeconds: 0,
      // 길이는 음성으로 정한다 (TTS 가 음성 + 0.25초로 늘림) → 아래에서 문장 사이 쉼 0.2초를 더한다
      scenes: script.lines.map((l) => ({ type: "three", durationSec: 0.5, text: l.caption, say: l.narration, color: "#e8322a", bg: "#0b0b10" })),
    };
    writeFileSync(planPath, JSON.stringify(plan, null, 2));
    t0 = performance.now();
    let ttsCost: number | null = 0;
    let chars = 0;
    if ((opts.tts ?? "inworld") === "inworld") {
      const v = await addVoiceInworld(planPath, pdir, log);
      chars = v.chars;
      const perM = INWORLD_USD_PER_M_CHARS[inworldConfig().modelId];
      ttsCost = perM ? (chars * perM) / 1e6 : null;
    } else {
      const ttsMod = (await import(pathToFileURL(join(pdir, "scripts/tts.mjs")).href)) as { addVoice: (p: string) => unknown };
      ttsMod.addVoice(planPath);
    }
    steps.push({ step: `본편: 음성${chars ? ` (Inworld ${chars}자)` : ""}`, model: chars ? `inworld/${inworldConfig().modelId}` : "edge-tts", inputTokens: chars, outputTokens: 0, costUsd: ttsCost, ms: Math.round(performance.now() - t0) });
    const voiced = JSON.parse(readFileSync(planPath, "utf8")) as { scenes: { durationSec: number; voice?: string; voiceSec?: number; text: string; say: string; video?: string }[] };
    for (const sc of voiced.scenes) sc.durationSec = +(sc.durationSec + 0.2).toFixed(2);

    // 문장마다 고른 컷을 음성 길이에 맞춰 자르고 이어 붙인다 (모자라면 그 클립 안에서 늘림)
    t0 = performance.now();
    mkdirSync(clipDir, { recursive: true });
    voiced.scenes.forEach((sc, i) => {
      const line = script.lines[i];
      const shots = (line.shots.length ? line.shots : [{ clip: 1, start: 0, end: 3, why: "" }]).slice(0, 2);
      const total = sc.durationSec;
      const want = shots.map((s) => Math.max(0.5, s.end - s.start));
      const sum = want.reduce((a, b) => a + b, 0);
      const parts: string[] = [];
      shots.forEach((s, k) => {
        const c = clips.find((x) => x.index === s.clip) ?? clips[0];
        const dur = (total * want[k]) / sum;
        let start = Math.max(0, Math.min(s.start, c.seconds - 0.2));
        if (start + dur > c.seconds) start = Math.max(0, c.seconds - dur);
        const part = join(out, "src", `line${i + 1}_${k + 1}.mp4`);
        ff(["-ss", start.toFixed(3), "-i", c.file, "-t", dur.toFixed(3), "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-r", "30", part]);
        parts.push(part);
      });
      const lineFile = join(out, "src", `line${i + 1}.mp4`);
      if (parts.length === 1) copyFileSync(parts[0], lineFile);
      else ff([...parts.flatMap((x) => ["-i", x]), "-filter_complex", `${parts.map((_, k) => `[${k}:v]`).join("")}concat=n=${parts.length}:v=1:a=0[v]`, "-map", "[v]", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", lineFile]);
      copyFileSync(lineFile, join(clipDir, `line${i + 1}.mp4`));
      sc.video = `bbody/line${i + 1}.mp4`;
    });
    steps.push({ step: "본편: 컷 자르기", model: "ffmpeg", inputTokens: 0, outputTokens: 0, costUsd: 0, ms: Math.round(performance.now() - t0) });

    // 렌더 (HookVideo: 장면마다 영상 + 자막 + 음성)
    log("[본편] Remotion 렌더");
    t0 = performance.now();
    const req = createRequire(join(pdir, "package.json"));
    const { bundle } = req("@remotion/bundler") as { bundle: (o: { entryPoint: string }) => Promise<string> };
    const { renderMedia, selectComposition } = req("@remotion/renderer") as {
      selectComposition: (o: object) => Promise<object>;
      renderMedia: (o: object) => Promise<unknown>;
    };
    const serveUrl = await bundle({ entryPoint: join(pdir, "src/index.ts") });
    const seconds = +voiced.scenes.reduce((a, s) => a + s.durationSec, 0).toFixed(2);
    const inputProps = { plan: { concept: plan.concept, hookSeconds: seconds, scenes: voiced.scenes }, mainClips: [], musicVolume: 0 };
    const composition = await selectComposition({ serveUrl, id: "HookVideo", inputProps });
    await renderMedia({ composition, serveUrl, codec: "h264", outputLocation: bodyFile, inputProps, chromiumOptions: { gl: "angle" } });
    for (const sc of voiced.scenes) if (sc.voice) copyFileSync(join(pdir, "public", sc.voice), join(out, basename(sc.voice)));
    steps.push({ step: "본편: Remotion 렌더", model: "remotion", inputTokens: 0, outputTokens: 0, costUsd: 0, ms: Math.round(performance.now() - t0) });

    // 자막 데이터
    let at = 0;
    const captions = voiced.scenes.map((sc, i) => {
      const start = +at.toFixed(3);
      at += sc.durationSec;
      return { order: i + 1, start, end: +at.toFixed(3), text: sc.text, narration: sc.say, voice: sc.voice ? { file: basename(sc.voice), start, sec: sc.voiceSec ?? null } : null };
    });
    const captionsFile = join(out, "body.captions.json");
    writeFileSync(captionsFile, JSON.stringify({ video: "body.mp4", fps: FPS, width: 1080, height: 1920, seconds, captions }, null, 2) + "\n");
    const result: BodyResult = { file: bodyFile, captions: captionsFile, seconds, script, steps };
    writeFileSync(join(out, "body.json"), JSON.stringify({ product: p.name, footage: opts.footageDir, clips: clips.map((c) => ({ index: c.index, source: c.source, seconds: c.seconds })), ...result }, null, 2) + "\n");
    log(`[본편] ${seconds}초 → ${bodyFile}`);
    return result;
  } finally {
    writeFileSync(scenesPath, scenesOrig);
    gen.restore();
    tts.restore();
    clipSnap.restore();
    if (!clipDirExisted) rmSync(clipDir, { recursive: true, force: true });
  }
}

/** 훅 영상 + 본편(또는 영상 여러 개)을 이어 붙인다. 해상도·fps 를 맞추고, 소리가 없는 영상엔 무음을 넣는다 */
export function joinVideos(files: string[], outFile: string): number {
  const inputs: string[] = [];
  const chains: string[] = [];
  files.forEach((f, i) => {
    inputs.push("-i", f);
    chains.push(`[${i}:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1[v${i}]`);
    if (hasAudio(f)) chains.push(`[${i}:a]aresample=48000,aformat=channel_layouts=stereo[a${i}]`);
    else chains.push(`anullsrc=r=48000:cl=stereo,atrim=duration=${probeSeconds(f).toFixed(3)}[a${i}]`);
  });
  const cat = files.map((_, i) => `[v${i}][a${i}]`).join("") + `concat=n=${files.length}:v=1:a=1[v][a]`;
  ff([...inputs, "-filter_complex", [...chains, cat].join(";"), "-map", "[v]", "-map", "[a]", "-r", "30", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", outFile]);
  return probeSeconds(outFile);
}

/** 훅 자막 데이터 + 본편 자막 데이터 → 이어 붙인 영상용 하나 (본편 시각은 훅 길이만큼 밀어서) */
export function joinCaptions(hookCaptionsFile: string | null, hookSeconds: number, bodyCaptionsFile: string, outFile: string, video: string) {
  const hook = hookCaptionsFile && existsSync(hookCaptionsFile) ? (JSON.parse(readFileSync(hookCaptionsFile, "utf8")) as { captions: { start: number; end: number }[] }) : { captions: [] };
  const body = JSON.parse(readFileSync(bodyCaptionsFile, "utf8")) as { captions: { start: number; end: number }[] };
  const shift = (c: { start: number; end: number }) => ({ ...c, start: +(c.start + hookSeconds).toFixed(3), end: +(c.end + hookSeconds).toFixed(3) });
  writeFileSync(
    outFile,
    JSON.stringify({ video, fps: FPS, width: 1080, height: 1920, parts: [{ part: "hook", start: 0, end: hookSeconds }, { part: "body", start: hookSeconds }], captions: [...hook.captions.map((c) => ({ ...c, part: "hook" })), ...body.captions.map((c) => ({ ...shift(c), part: "body" }))] }, null, 2) + "\n"
  );
}
