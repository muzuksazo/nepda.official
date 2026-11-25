// 컷 이미지: 장면별 3D 명세 → React Three Fiber 코드(Claude) → 타입 검사 → Remotion 스틸 렌더.
// 렌더는 video_test/pipeline 의 Remotion 프로젝트(SceneTest 컴포지션)를 빌려 쓴다.
// pipeline/src/generated 는 렌더 동안만 쓰고 끝나면 원래대로 되돌린다. 코드와 PNG는 B의 out/ 에 남긴다.
import { execFileSync } from "node:child_process";
import { existsSync, mkdirSync, readdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { generateText, type LanguageModel, type ModelMessage } from "ai";
import { anthropic } from "@ai-sdk/anthropic";
import { priceOf, type StepUsage } from "./cost.js";
import { toPipelinePlan } from "./pipeline-plan.js";
import type { ScenarioItem } from "./schema.js";

const FPS = 30;
const B_DIR = resolve(dirname(fileURLToPath(import.meta.url)), "..");

export function pipelineDir(): string {
  return resolve(process.env.B_PIPELINE_DIR?.trim() || join(B_DIR, "../../../../pipeline"));
}

export interface BeatCut {
  order: number;
  key: string;
  ok: boolean;
  tries: number;
  /** 프로젝트 폴더(out/<project_id>/) 기준 상대 경로. 처음·중간·끝 프레임 */
  images: string[];
  code?: string;
  error?: string;
}

export interface ScenarioCuts {
  scenario_id: string;
  beats: BeatCut[];
}

// pipeline/scripts/scenegen.mjs 의 RULES 와 같은 계약
const RULES = `
Write ONE React Three Fiber scene component as a .tsx file for a Remotion video (1080x1920 vertical, 30fps).

Contract:
- \`export default function Scene({ durationInFrames, color }: { durationInFrames: number; color: string })\`
- Return ONLY 3D children (lights, meshes, groups). It is mounted INSIDE an existing <ThreeCanvas>
  with camera at [0, 0.8, 7], fov 45, looking at the origin. Do NOT render <Canvas>/<ThreeCanvas> or any HTML.
  The camera is fixed by the caller; express "camera" moves by moving/scaling a top-level <group> instead.
- Keep everything in the UPPER half of the frame (roughly y between 0 and 3, x between -2 and 2). Captions cover the lower half.
- Background is already painted behind the canvas; do not set scene.background.
- A number counter overlay (if any) is drawn by the caller at the top; never draw digits or text in 3D.
  When the scene HAS a counter, keep all 3D below y = 2.2 so the top ~15% of the frame stays clear for the number.
- Keep every object FULLY inside the frame at every frame (nothing cut off at the edges), including after any scale-up or zoom.
  Visible area at z=0 is roughly x -2.2..2.2 and y -3.5..3.9; leave a margin.

Determinism (the video is rendered by several browsers in parallel, frame by frame):
- ALL motion must come from \`const frame = useCurrentFrame()\` with \`interpolate\`/\`spring\` from 'remotion'.
- FORBIDDEN: useFrame, requestAnimationFrame, Date, performance.now, Math.random, setTimeout, useEffect-driven animation.
- Randomness only via \`random('seed-' + i)\` from 'remotion'.

Allowed imports ONLY: 'react', 'remotion', 'three', '@react-three/fiber' (types/hooks except useFrame).
No external models, textures, fonts or URLs; no @react-three/drei. Build geometry from three primitives
(BufferGeometry, TubeGeometry with CatmullRomCurve3, InstancedMesh, etc.). Use useMemo for heavy geometry.
Keep it light: under ~2000 instances total.

Make it look good: lit with ambient + directional/point lights, meshStandardMaterial or meshPhysicalMaterial,
use \`color\` as the accent. The motion must make the FACT readable at a glance.

Output ONLY the code inside one \`\`\`tsx block.`;

function staticCheck(code: string): string | null {
  const bad = [/useFrame/, /requestAnimationFrame/, /Date\.now|new Date/, /performance\.now/, /Math\.random/, /setTimeout|setInterval/, /@react-three\/drei/, /https?:\/\//, /<ThreeCanvas|<Canvas/];
  const hit = bad.filter((r) => r.test(code)).map(String);
  const imports = [...code.matchAll(/from\s+['"]([^'"]+)['"]/g)].map((m) => m[1]);
  const extra = imports.filter((i) => !["react", "remotion", "three", "@react-three/fiber"].includes(i));
  if (!/export\s+default/.test(code)) hit.push("missing export default");
  if (extra.length) hit.push(`disallowed imports: ${extra.join(", ")}`);
  return hit.length ? `Forbidden patterns: ${hit.join("; ")}` : null;
}

function extractCode(text: string): string {
  const m = text.match(/```(?:tsx|ts|jsx)?\s*\n([\s\S]*?)```/);
  return (m ? m[1] : text).trim();
}

function writeRegistry(genDir: string, keys: string[], keep: string[]) {
  const all = [...new Set([...keep, ...keys])];
  writeFileSync(
    join(genDir, "index.ts"),
    `// AUTO-GENERATED (bridge-dev/b cuts — 렌더 중 임시)\nimport type React from 'react';\n${all.map((k) => `import ${k} from './${k}';`).join("\n")}\n\n` +
      `export type GenProps = { durationInFrames: number; color: string };\n` +
      `export const generated: Record<string, React.FC<GenProps>> = { ${all.join(", ")} };\n`
  );
}

function typecheck(pdir: string): Record<string, string[]> {
  try {
    execFileSync(process.execPath, [join(pdir, "node_modules/typescript/bin/tsc"), "-p", pdir], { cwd: pdir, stdio: "pipe" });
    return {};
  } catch (e) {
    const err = e as { stdout?: Buffer; stderr?: Buffer };
    const out = String(err.stdout ?? "") + String(err.stderr ?? "");
    const errs: Record<string, string[]> = {};
    for (const line of out.split(/\r?\n/)) {
      const m = line.match(/generated[\\/](B\w+)\.tsx/);
      if (m) (errs[m[1]] ??= []).push(line.trim());
    }
    if (!Object.keys(errs).length && out.trim()) throw new Error(`pipeline 타입 검사가 생성 코드 밖에서 실패했습니다:\n${out.slice(0, 2000)}`);
    return errs;
  }
}

export interface CutsOptions {
  model?: LanguageModel;
  modelId?: string;
  maxTries?: number;
  log?: (m: string) => void;
  /** out/<project_id> 절대 경로 */
  projectDir: string;
  round: number;
}

/** 시나리오들의 장면 컷을 만든다. 반환: 컷 결과 + 비용 단계 */
export async function renderCuts(
  scenarios: ScenarioItem[],
  opts: CutsOptions
): Promise<{ cuts: ScenarioCuts[]; steps: StepUsage[] }> {
  const log = opts.log ?? (() => {});
  const pdir = pipelineDir();
  if (!existsSync(join(pdir, "src/Root.tsx")) || !existsSync(join(pdir, "node_modules/@remotion/renderer")))
    throw new Error(`video_test/pipeline 을 찾을 수 없습니다: ${pdir} (B_PIPELINE_DIR로 지정, pipeline에서 npm install 필요)`);
  const modelId = opts.modelId || process.env.B_SCENE_MODEL?.trim() || process.env.B_MODEL?.trim() || "claude-opus-5-5";
  const model = opts.model ?? anthropic(modelId);
  const maxTries = Math.max(1, opts.maxTries ?? Number(process.env.B_SCENE_MAX_TRIES || 3));
  const steps: StepUsage[] = [];

  // 렌더 대상: 시나리오 × 장면
  type Job = { s: ScenarioItem; order: number; key: string; scene: ReturnType<typeof toPipelinePlan>["scenes"][number]; convo: ModelMessage[]; tries: number; ok: boolean; code?: string; error?: string };
  const jobs: Job[] = [];
  for (const s of scenarios) {
    const plan = toPipelinePlan(s);
    const beats = [...s.beats].sort((a, b) => a.order - b.order);
    plan.scenes.forEach((scene, i) => {
      const key = `B${s.scenario_id.replace(/[^A-Za-z0-9]/g, "")}_${beats[i].order}`;
      jobs.push({
        s, order: beats[i].order, key, scene, tries: 0, ok: false,
        convo: [{ role: "user", content:
          `${RULES}\n\nScene to build (${scene.durationSec}s = ${Math.round(scene.durationSec * FPS)} frames, accent ${scene.color}, background ${scene.bg}):\n` +
          `Caption on screen (drawn by caller): ${JSON.stringify(scene.text)}\n` +
          `Counter overlay at the top: ${scene.counter ? `YES (${scene.counter.from}→${scene.counter.to}${scene.counter.suffix ?? ""}) — keep 3D below y 2.2` : "no"}\n` +
          `What the 3D must show:\n${scene.visual}` }],
      });
    });
  }

  // pipeline/src/generated 백업
  const genDir = join(pdir, "src/generated");
  mkdirSync(genDir, { recursive: true });
  const origFiles = new Map<string, string>();
  for (const f of readdirSync(genDir)) origFiles.set(f, readFileSync(join(genDir, f), "utf8"));
  const keepKeys = [...(origFiles.get("index.ts") ?? "").matchAll(/import (\w+) from '\.\/\1'/g)].map((m) => m[1]);

  const passed = new Set<string>();
  try {
    let pending = jobs;
    for (let attempt = 1; attempt <= maxTries && pending.length; attempt++) {
      log(`[B 컷] 3D 장면 코드 생성 ${attempt}/${maxTries} (${pending.length}개)`);
      await Promise.all(
        pending.map(async (j) => {
          j.tries++;
          const t0 = performance.now();
          const r = await generateText({ model, messages: j.convo, maxOutputTokens: 16000, providerOptions: { anthropic: { effort: "medium" } } });
          const inT = r.usage?.inputTokens ?? 0, outT = r.usage?.outputTokens ?? 0;
          steps.push({ step: `컷: 장면 ${j.order} 코드 ${j.tries}차`, model: modelId, inputTokens: inT, outputTokens: outT, costUsd: priceOf(modelId, inT, outT), ms: Math.round(performance.now() - t0), group: `cuts-code-${attempt}` });
          j.convo.push({ role: "assistant", content: r.text });
          j.code = extractCode(r.text);
          writeFileSync(join(genDir, `${j.key}.tsx`), j.code);
        })
      );
      const errors: Record<string, string[]> = {};
      for (const j of pending) {
        const e = staticCheck(j.code ?? "");
        if (e) errors[j.key] = [e];
      }
      const t0 = performance.now();
      writeRegistry(genDir, [...passed, ...pending.filter((j) => !errors[j.key]).map((j) => j.key)], keepKeys);
      Object.assign(errors, typecheck(pdir));
      steps.push({ step: `컷: 타입 검사 ${attempt}차`, model: "tsc", inputTokens: 0, outputTokens: 0, costUsd: 0, ms: Math.round(performance.now() - t0) });

      for (const j of pending) {
        if (errors[j.key]) {
          j.error = errors[j.key].join("\n").slice(0, 1500);
          j.convo.push({ role: "user", content: `That code failed:\n${j.error}\n\nFix it and return the full file again, same rules.` });
          log(`[B 컷] 장면 ${j.order} ${attempt}차 실패: ${j.error.split("\n")[0].slice(0, 120)}`);
        } else {
          j.ok = true;
          j.error = undefined;
          passed.add(j.key);
        }
      }
      pending = pending.filter((j) => !j.ok);
    }

    // 실패한 장면은 registry 에서 빼고(기본 도형으로 렌더) 표시만 한다
    for (const j of jobs) if (!j.ok) rmSync(join(genDir, `${j.key}.tsx`), { force: true });
    writeRegistry(genDir, [...passed], keepKeys);

    // 렌더: 장면마다 처음·중간·끝 프레임
    log(`[B 컷] Remotion 번들·렌더 (${jobs.length}장면 × 3컷)`);
    const req = createRequire(join(pdir, "package.json"));
    const { bundle } = req("@remotion/bundler") as { bundle: (o: { entryPoint: string }) => Promise<string> };
    const { renderStill, selectComposition } = req("@remotion/renderer") as {
      selectComposition: (o: object) => Promise<object>;
      renderStill: (o: object) => Promise<unknown>;
    };
    const t0 = performance.now();
    const serveUrl = await bundle({ entryPoint: join(pdir, "src/index.ts") });
    const results: ScenarioCuts[] = [];
    for (const s of scenarios) {
      const outDir = join(opts.projectDir, `round-${opts.round}`, "cuts", s.scenario_id);
      mkdirSync(outDir, { recursive: true });
      const beats: BeatCut[] = [];
      for (const j of jobs.filter((x) => x.s === s)) {
        const frames = Math.round(j.scene.durationSec * FPS);
        const scene = { ...j.scene, gen: j.ok ? j.key : undefined };
        const inputProps = { genKey: j.ok ? j.key : "", scene, frames };
        const images: string[] = [];
        try {
          const composition = await selectComposition({ serveUrl, id: "SceneTest", inputProps });
          for (const f of [0, Math.floor(frames / 2), frames - 1]) {
            const name = `beat${j.order}_f${String(f).padStart(3, "0")}.png`;
            await renderStill({ composition, serveUrl, inputProps, frame: f, chromiumOptions: { gl: "angle" }, output: join(outDir, name) });
            images.push(`round-${opts.round}/cuts/${s.scenario_id}/${name}`);
          }
        } catch (e) {
          j.ok = false;
          j.error = `렌더 실패: ${String((e as Error).message ?? e).split("\n").slice(0, 6).join("\n")}`;
        }
        if (j.code) writeFileSync(join(outDir, `beat${j.order}.tsx`), j.code);
        beats.push({ order: j.order, key: j.key, ok: j.ok, tries: j.tries, images, code: j.code ? `round-${opts.round}/cuts/${s.scenario_id}/beat${j.order}.tsx` : undefined, error: j.error });
      }
      results.push({ scenario_id: s.scenario_id, beats });
    }
    steps.push({ step: "컷: Remotion 번들·렌더", model: "remotion", inputTokens: 0, outputTokens: 0, costUsd: 0, ms: Math.round(performance.now() - t0) });
    return { cuts: results, steps };
  } finally {
    // pipeline/src/generated 원래대로
    for (const f of readdirSync(genDir)) if (!origFiles.has(f)) rmSync(join(genDir, f), { force: true });
    for (const [f, text] of origFiles) writeFileSync(join(genDir, f), text);
  }
}

/** 렌더 결과 PNG가 모두 있는지 (테스트용) */
export function cutFilesExist(projectDir: string, cuts: ScenarioCuts[]): boolean {
  return cuts.every((c) => c.beats.every((b) => b.images.every((p) => existsSync(join(projectDir, p)))));
}
