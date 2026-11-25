// 훅 영상: 컷 단계에서 만든 장면 코드(beat{n}.tsx)를 그대로 쓰고, 나레이션 TTS를 붙여 훅만 mp4로 렌더한다.
// Claude 호출 없음. video_test/pipeline 의 tts.mjs(Edge TTS)와 Remotion HookVideo 컴포지션을 빌려 쓴다.
// pipeline/src/generated, pipeline/public/tts 는 렌더 동안만 쓰고 끝나면 원래대로 되돌린다.
import { copyFileSync, existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";
import { pathToFileURL } from "node:url";
import { pipelineDir, snapshotDir, writeRegistry, type ScenarioCuts } from "./cuts.js";
import type { StepUsage } from "./cost.js";
import { toPipelinePlan } from "./pipeline-plan.js";
import type { ScenarioItem } from "./schema.js";

export interface HookVideo {
  scenario_id: string;
  /** 프로젝트 폴더(out/<project_id>/) 기준 상대 경로 */
  file: string;
  seconds: number;
  /** 장면별 계획 길이 → TTS 반영 후 길이 */
  scenes: { order: number; planned: number; final: number; voiceSec: number | null; usedGen: boolean }[];
}

type PipelineScene = ReturnType<typeof toPipelinePlan>["scenes"][number] & { gen?: string; voice?: string; voiceSec?: number };

export async function renderHookVideos(
  scenarios: ScenarioItem[],
  cuts: ScenarioCuts[] | undefined,
  opts: { projectDir: string; round: number; log?: (m: string) => void }
): Promise<{ videos: HookVideo[]; steps: StepUsage[] }> {
  const log = opts.log ?? (() => {});
  const pdir = pipelineDir();
  const genDir = join(pdir, "src/generated");
  const ttsDir = join(pdir, "public/tts");
  const steps: StepUsage[] = [];
  const videos: HookVideo[] = [];

  const gen = snapshotDir(genDir);
  const tts = snapshotDir(ttsDir);
  try {
    // 1) 장면 코드 복원 + plan 작성
    const plans: { s: ScenarioItem; planPath: string; plan: { id: string; scenes: PipelineScene[]; hookSeconds: number } }[] = [];
    const keys: string[] = [];
    for (const s of scenarios) {
      const cut = cuts?.find((c) => c.scenario_id === s.scenario_id);
      if (!cut) throw new Error(`${s.scenario_id}: 컷 기록이 없습니다. 먼저 npm run cuts 로 장면 코드를 만드세요.`);
      const base = toPipelinePlan(s);
      const beats = [...s.beats].sort((a, b) => a.order - b.order);
      const scenes: PipelineScene[] = base.scenes.map((sc, i) => {
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
      const rel = `round-${opts.round}/video/hook_${p.s.scenario_id}.mp4`;
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
      videos.push({
        scenario_id: p.s.scenario_id,
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
    steps.push({ step: "영상: Remotion 번들·렌더", model: "remotion", inputTokens: 0, outputTokens: 0, costUsd: 0, ms: Math.round(performance.now() - t0) });
    return { videos, steps };
  } finally {
    gen.restore();
    tts.restore();
  }
}
