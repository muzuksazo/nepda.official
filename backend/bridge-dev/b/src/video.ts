// 훅 영상: 컷 단계에서 만든 장면 코드(beat{n}.tsx)를 그대로 쓰고, 나레이션 TTS를 붙여 훅만 mp4로 렌더한다.
// Claude 호출 없음. video_test/pipeline 의 tts.mjs(Edge TTS)와 Remotion HookVideo 컴포지션을 빌려 쓴다.
// pipeline/src/generated, pipeline/public/tts 는 렌더 동안만 쓰고 끝나면 원래대로 되돌린다.
import { copyFileSync, existsSync, mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, join, relative, sep } from "node:path";
import { pathToFileURL } from "node:url";
import { pipelineDir, snapshotDir, writeRegistry, type ScenarioCuts } from "./cuts.js";
import type { StepUsage } from "./cost.js";
import { toPipelinePlan } from "./pipeline-plan.js";
import type { ScenarioItem } from "./schema.js";

export interface HookVideo {
  scenario_id: string;
  /** "3d": 장면 전부 3D / "gclips": 이야기 장면은 Google 영상 클립, 반전은 3D */
  variant?: "3d" | "gclips";
  /** gclips: 원본 클립과 참고 이미지 (프로젝트 폴더 기준 상대 경로) */
  sourceClips?: { order: number; file: string }[];
  refImage?: string;
  /** 프로젝트 폴더(out/<project_id>/) 기준 상대 경로 */
  file: string;
  seconds: number;
  /** 장면별 계획 길이 → TTS 반영 후 길이 */
  scenes: { order: number; planned: number; final: number; voiceSec: number | null; usedGen: boolean }[];
}

type PipelineScene = ReturnType<typeof toPipelinePlan>["scenes"][number] & { gen?: string; voice?: string; voiceSec?: number; video?: string };

// 클립 장면: pipeline/src/scenes.tsx 의 ThreeScene 에 "scene.video 가 있으면 OffthreadVideo 로 깐다"를
// 렌더하는 동안만 덧붙이고 끝나면 원래 파일로 되돌린다. (3D 텍스처 방식은 장면 첫 0.3초가 검게 나왔음)
const SCENES_IMPORT = "import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig } from 'remotion';";
const SCENES_HOOK_LINE = "  const rot = frame * 0.06;";
function patchScenes(src: string): string {
  if (!src.includes(SCENES_IMPORT) || !src.includes(SCENES_HOOK_LINE))
    throw new Error("pipeline/src/scenes.tsx 구조가 예상과 달라 클립 장면을 붙일 수 없습니다.");
  return src
    .replace(SCENES_IMPORT, "import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig, OffthreadVideo, staticFile } from 'remotion';")
    .replace(
      SCENES_HOOK_LINE,
      `${SCENES_HOOK_LINE}
  // [bridge-dev/b 임시 패치] Google 영상 클립 장면
  const __clip = (scene as any).video as string | undefined;
  if (__clip) {
    return (
      <AbsoluteFill style={{ backgroundColor: scene.bg }}>
        <OffthreadVideo src={staticFile(__clip)} muted style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
        <AbsoluteFill style={{ background: 'linear-gradient(to bottom, rgba(0,0,0,0) 50%, rgba(0,0,0,0.72) 78%, rgba(0,0,0,0.8) 100%)' }} />
        {scene.counter && <Counter {...scene.counter} />}
        <Caption text={scene.text} sub={scene.sub} color="#fff" pop={interpolate(enter, [0, 1], [0.6, 1])} />
      </AbsoluteFill>
    );
  }`
    );
}

export async function renderHookVideos(
  scenarios: ScenarioItem[],
  cuts: ScenarioCuts[] | undefined,
  opts: {
    projectDir: string;
    round: number;
    log?: (m: string) => void;
    /** 장면 order → Google 영상 클립(mp4 절대 경로). 있으면 그 장면은 3D 코드 대신 클립 */
    clips?: Record<number, string>;
  }
): Promise<{ videos: HookVideo[]; steps: StepUsage[] }> {
  const log = opts.log ?? (() => {});
  const variant: "3d" | "gclips" = opts.clips && Object.keys(opts.clips).length ? "gclips" : "3d";
  const pdir = pipelineDir();
  const genDir = join(pdir, "src/generated");
  const ttsDir = join(pdir, "public/tts");
  const clipDir = join(pdir, "public/bclips");
  const clipDirExisted = existsSync(clipDir);
  const steps: StepUsage[] = [];
  const videos: HookVideo[] = [];

  const gen = snapshotDir(genDir);
  const tts = snapshotDir(ttsDir);
  const clipSnap = snapshotDir(clipDir);
  const scenesPath = join(pdir, "src/scenes.tsx");
  const scenesOrig = readFileSync(scenesPath, "utf8");
  try {
    if (variant === "gclips") writeFileSync(scenesPath, patchScenes(scenesOrig));
    // 1) 장면 코드 복원 + plan 작성
    const plans: { s: ScenarioItem; planPath: string; plan: { id: string; scenes: PipelineScene[]; hookSeconds: number } }[] = [];
    const keys: string[] = [];
    for (const s of scenarios) {
      const cut = cuts?.find((c) => c.scenario_id === s.scenario_id);
      if (!cut) throw new Error(`${s.scenario_id}: 컷 기록이 없습니다. 먼저 npm run cuts 로 장면 코드를 만드세요.`);
      const base = toPipelinePlan(s);
      const beats = [...s.beats].sort((a, b) => a.order - b.order);
      const scenes: PipelineScene[] = base.scenes.map((sc, i) => {
        const clip = opts.clips?.[beats[i].order];
        if (clip && existsSync(clip)) {
          const key = `G${s.scenario_id.replace(/[^A-Za-z0-9]/g, "")}_${beats[i].order}`;
          copyFileSync(clip, join(clipDir, `${key}.mp4`));
          return { ...sc, video: `bclips/${key}.mp4` };
        }
        const cb = cut.beats.find((b) => b.order === beats[i].order);
        const codePath = cb?.code ? join(opts.projectDir, cb.code) : "";
        if (cb?.ok && codePath && existsSync(codePath)) {
          writeFileSync(join(genDir, `${cb.key}.tsx`), readFileSync(codePath));
          keys.push(cb.key);
          return { ...sc, gen: cb.key };
        }
        return { ...sc };
      });
      const dir = join(opts.projectDir, `round-${opts.round}`, "video");
      mkdirSync(dir, { recursive: true });
      const id = `b_${s.scenario_id}`;
      const plan = { id, concept: base.concept, hookSeconds: base.hookSeconds, scenes };
      const planPath = join(dir, `${s.scenario_id}.plan.json`);
      writeFileSync(planPath, JSON.stringify(plan, null, 2));
      plans.push({ s, planPath, plan });
    }
    writeRegistry(genDir, keys, gen.keepKeys);

    // 2) TTS (pipeline/scripts/tts.mjs 의 addVoice: 음성이 장면보다 길면 장면을 늘림)
    log("[B 영상] TTS 나레이션");
    let t0 = performance.now();
    const ttsMod = (await import(pathToFileURL(join(pdir, "scripts/tts.mjs")).href)) as {
      addVoice: (p: string) => { scenes: PipelineScene[]; hookSeconds: number };
    };
    for (const p of plans) p.plan = { ...p.plan, ...ttsMod.addVoice(p.planPath) };
    steps.push({ step: "영상: TTS 나레이션", model: "edge-tts", inputTokens: 0, outputTokens: 0, costUsd: 0, ms: Math.round(performance.now() - t0) });

    // 3) 렌더 (훅만, 본편 없음)
    log("[B 영상] Remotion 번들·렌더");
    t0 = performance.now();
    const req = createRequire(join(pdir, "package.json"));
    const { bundle } = req("@remotion/bundler") as { bundle: (o: { entryPoint: string }) => Promise<string> };
    const { renderMedia, selectComposition } = req("@remotion/renderer") as {
      selectComposition: (o: object) => Promise<object>;
      renderMedia: (o: object) => Promise<unknown>;
    };
    const serveUrl = await bundle({ entryPoint: join(pdir, "src/index.ts") });
    for (const p of plans) {
      const inputProps = { plan: p.plan, mainClips: [], musicVolume: 0 };
      const composition = await selectComposition({ serveUrl, id: "HookVideo", inputProps });
      const rel = `round-${opts.round}/video/hook_${p.s.scenario_id}${variant === "gclips" ? "_gclips" : ""}.mp4`;
      let last = -1;
      await renderMedia({
        composition, serveUrl, codec: "h264", outputLocation: join(opts.projectDir, rel), inputProps,
        chromiumOptions: { gl: "angle" },
        onProgress: ({ progress }: { progress: number }) => {
          const pct = Math.floor(progress * 10) * 10;
          if (pct !== last) { last = pct; log(`[B 영상] ${p.s.scenario_id} ${pct}%`); }
        },
      });
      // 음성 파일도 B 쪽에 남긴다
      for (const sc of p.plan.scenes) if (sc.voice) copyFileSync(join(pdir, "public", sc.voice), join(opts.projectDir, `round-${opts.round}`, "video", sc.voice.split("/").pop()!));
      const beats = [...p.s.beats].sort((a, b) => a.order - b.order);
      const relOf = (abs: string) => relative(opts.projectDir, abs).split(sep).join("/");
      const clipEntries = Object.entries(opts.clips ?? {}).map(([o, f]) => ({ order: Number(o), file: relOf(f) }));
      const refAbs = clipEntries.length ? join(dirname(Object.values(opts.clips!)[0]), "ref.jpg") : "";
      videos.push({
        scenario_id: p.s.scenario_id,
        variant,
        ...(variant === "gclips" ? { sourceClips: clipEntries, refImage: existsSync(refAbs) ? relOf(refAbs) : undefined } : {}),
        file: rel,
        seconds: p.plan.hookSeconds,
        scenes: p.plan.scenes.map((sc, i) => ({
          order: beats[i].order,
          planned: beats[i].duration_sec,
          final: sc.durationSec,
          voiceSec: sc.voiceSec ?? null,
          usedGen: !!sc.gen,
        })),
      });
    }
    steps.push({ step: `영상${variant === "gclips" ? "(Google 클립)" : ""}: Remotion 번들·렌더`, model: "remotion", inputTokens: 0, outputTokens: 0, costUsd: 0, ms: Math.round(performance.now() - t0) });
    return { videos, steps };
  } finally {
    writeFileSync(scenesPath, scenesOrig); // scenes.tsx 원래대로
    gen.restore();
    tts.restore();
    clipSnap.restore();
    if (!clipDirExisted) rmSync(clipDir, { recursive: true, force: true });
  }
}
