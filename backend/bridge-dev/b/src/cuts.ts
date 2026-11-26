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
import { copySceneAssets, installSceneLib } from "./assets/copy.js";
import { characterNames, hdris, searchAssets } from "./catalog.js";
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


// 무대·인물·받아 둔 물건·제품 모델을 쓰는 장면 (기본). B_SCENE_STYLE=basic 이면 위 RULES(기본 도형만)
const RULES_RICH = `
Write ONE React Three Fiber scene component as a .tsx file for a Remotion video (1080x1920 vertical, 30fps).

Contract:
- \`export default function Scene({ durationInFrames, color }: { durationInFrames: number; color: string })\`
- Return ONLY 3D children. It is mounted INSIDE an existing <ThreeCanvas>. Do NOT render <Canvas>/<ThreeCanvas> or any HTML.
- Captions are drawn by the caller over the lower ~40% of the frame; a number counter (if any) at the very top.

Scene kit (already available next to your file — import exactly like this):
  import { Stage, Character, Prop, FLOOR_Y, CAMERAS, blendCamera, SlamIn, Quake, DustBurst, BackDim, SLAM_IMPACT } from './BCharacter';
  import Product from './BProduct';   // ONLY in the reveal scene, ONLY if told a product model exists

- <Stage camera={...} floorColor="#hex" wallColor="#hex" back={-4.8} hdri="bassets/polyhaven/hdri/<file>" />  — put it FIRST.
  Gives the floor (y = FLOOR_Y = -0.35), a back wall that curves up behind z ≈ -2.6, soft window daylight, shadows,
  and sets the camera. Do NOT add your own ambient/directional lights (a small extra point light for a glow is fine).
- Camera = focus. Use the presets: CAMERAS.wide (whole stage), CAMERAS.person (the character's face), CAMERAS.visual
  (the visualization spot), CAMERAS.product (reveal). Move between them with
  \`blendCamera('wide', 'visual', interpolate(frame, [a, b], [0, 1], {extrapolateLeft:'clamp', extrapolateRight:'clamp'}))\`.
- Layout (meters, a person is ~1.7 tall). Floor y = FLOOR_Y. Screen center column x≈0.
  * Character stands at [-1.2, FLOOR_Y, -0.2], rotationY 0.55 (faces the visualization), height 1.7.
  * Visualization spot: center [0.4, 1.3, -0.6], fits a ~1.4 wide object; or on the floor around x 0..1.4, z -0.6.
  * Decor (assets): back row z -1.4..-2.4 across x -2.2..2.2, plus 1-2 items near the character. Fill the space: the stage
    must not look empty, but keep the visualization spot clear.
  * Everything must stay fully in frame. With CAMERAS.wide the visible width at z=-0.6 is about x -2.1..2.1.
- <Prop file="<one of the given asset files>" position={[x, FLOOR_Y, z]} height={meters} rotationY={rad} />
  Scales the model to that height and stands it on position (base centered). Optional: width={m} instead of height,
  colors={{ <materialName>: '#hex' }}, tone="#c9b9a6" (multiplies all colors — use a warm mid tone to calm toy-like colors).
  Realistic heights: desk 0.78, chair 0.9, bookcase 1.9, barrel 0.9, crate 0.6, lamp 1.6, tree 2.6, rock 0.5, pot 0.35, cup 0.12.
  Use ONLY the asset file paths given below, as string literals exactly as written.
- <Character file="bassets/uacp/<Name>.gltf" position={[-1.2, FLOOR_Y, -0.2]} rotationY={0.55} height={1.7}
     colors={{ Skin: '#f0c9a6' }}
     timeline={[{ clip: 'Idle', from: 0, to: durationInFrames + 1 }]}
     emotes={[{ type: 'look', from: 0, to: durationInFrames, amount: 0.45 }, { type: 'surprise', from: 40, to: 70 }]} />
  Emotes (frame ranges): look (turn head, amount ±rad), tilt (curious), nod (understanding), surprise (jolt), bounce (excited),
  droop (sad). For joy add a timeline segment { clip: 'Victory', from, to }, for disappointment { clip: 'Defeat', from, to }
  (then back to 'Idle'). The character acts with emotions only — no walking, no picking things up.
- Visualization: build the FACT with three primitives (Box, Sphere, Cylinder with thetaLength for wedges, Torus, Tube,
  InstancedMesh ≤ 2000) at the visualization spot, big and clear. Use meshStandardMaterial / meshPhysicalMaterial.
  Colors the story needs are fine (e.g. the 7 real rainbow colors); use \`color\` as the accent.
- Reveal scene template (when told this is the reveal):
    <Quake impact={SLAM_IMPACT}>
      <Stage camera={CAMERAS.product} ... />
      ...the previous scene's place, character and decor (they get darkened)...
      <BackDim impact={SLAM_IMPACT} z={0.25} />
      <SlamIn impact={SLAM_IMPACT} position={[0, FLOOR_Y, 0.6]}> <Product height={1.5} lidOpen={...} /> </SlamIn>
      <DustBurst impact={SLAM_IMPACT} position={[0, FLOOR_Y, 0.6]} radius={1.0} />
      ...after landing, show the product's feature with motion in front of it (z > 0.3), e.g. particles pulled into it...
    </Quake>
  Everything that should be darkened must be at z < 0.25; the product and its feature effect at z > 0.3.
- Never draw text or digits in 3D.

Determinism (rendered frame by frame by several browsers):
- ALL motion from \`const frame = useCurrentFrame()\` with \`interpolate\`/\`spring\` from 'remotion'.
- FORBIDDEN: useFrame, requestAnimationFrame, Date, performance.now, Math.random, setTimeout, useEffect-driven animation.
- Randomness only via \`random('seed-' + i)\` from 'remotion'.

Allowed imports ONLY: 'react', 'remotion', 'three', '@react-three/fiber' (no useFrame), './BCharacter', './BProduct'.
No @react-three/drei, no URLs, no other model files than the given ones.

Output ONLY the code inside one \`\`\`tsx block.`;

const SCENE_STYLE = (process.env.B_SCENE_STYLE?.trim() || "rich") as "rich" | "basic";

function staticCheck(code: string): string | null {
  const bad = [/useFrame/, /requestAnimationFrame/, /Date\.now|new Date/, /performance\.now/, /Math\.random/, /setTimeout|setInterval/, /@react-three\/drei/, /https?:\/\//, /<ThreeCanvas|<Canvas/];
  const hit = bad.filter((r) => r.test(code)).map(String);
  const imports = [...code.matchAll(/from\s+['"]([^'"]+)['"]/g)].map((m) => m[1]);
  const allowed = ["react", "remotion", "three", "@react-three/fiber", ...(SCENE_STYLE === "rich" ? ["./BCharacter", "./BProduct"] : [])];
  const extra = imports.filter((i) => !allowed.includes(i));
  if (!/export\s+default/.test(code)) hit.push("missing export default");
  if (extra.length) hit.push(`disallowed imports: ${extra.join(", ")}`);
  return hit.length ? `Forbidden patterns: ${hit.join("; ")}` : null;
}

function extractCode(text: string): string {
  const m = text.match(/```(?:tsx|ts|jsx)?\s*\n([\s\S]*?)```/);
  return (m ? m[1] : text).trim();
}

/** pipeline/src/generated 를 잠시 쓰고 원래대로 되돌린다 */
export function snapshotDir(dir: string): { keepKeys: string[]; restore: () => void } {
  mkdirSync(dir, { recursive: true });
  const orig = new Map<string, Buffer>();
  const dirs = new Set<string>();
  for (const e of readdirSync(dir, { withFileTypes: true })) {
    if (e.isDirectory()) dirs.add(e.name); // 하위 폴더는 건드리지 않는다
    else orig.set(e.name, readFileSync(join(dir, e.name)));
  }
  const keepKeys = [...(orig.get("index.ts")?.toString("utf8") ?? "").matchAll(/import (\w+) from '\.\/\1'/g)].map((m) => m[1]);
  return {
    keepKeys,
    restore: () => {
      for (const f of readdirSync(dir)) if (!orig.has(f) && !dirs.has(f)) rmSync(join(dir, f), { force: true, recursive: true });
      for (const [f, buf] of orig) writeFileSync(join(dir, f), buf);
    },
  };
}

export function writeRegistry(genDir: string, keys: string[], keep: string[]) {
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
  /** 반전 장면 제품 3D 모델 (src/assets/products/<model>.tsx) */
  productModel?: string;
}

/** 3D 명세의 assets·character 를 실제 파일로 바꿔 장면 코드 프롬프트에 넣을 글로 */
export function assetBrief(sc: NonNullable<ScenarioItem["beats"][number]["scene3d"]> | undefined): string {
  if (!sc) return "";
  const lines: string[] = [];
  if (sc.stage) lines.push(`Stage: place "${sc.stage.place}", floorColor ${sc.stage.floor_color}, wallColor ${sc.stage.wall_color}. HDRI files: ${hdris().map((h) => `bassets/polyhaven/hdri/${h}`).join(", ")}`);
  if (sc.character) {
    const ok = characterNames().includes(sc.character.model);
    lines.push(`Character: ${sc.character.role} → file "bassets/uacp/${ok ? sc.character.model : "OldClassy_Male"}.gltf"; emotions: ${sc.character.emotions.map((e) => `${e.type} ${Math.round(e.from * 100)}%~${Math.round(e.to * 100)}%`).join(", ")}`);
  }
  const files: string[] = [];
  for (const a of sc.assets ?? []) {
    const hits = searchAssets(a.query, 2);
    if (hits.length) files.push(`- ${a.role} (${a.place}): "${hits[0].file}"${hits[1] ? ` (alternative: "${hits[1].file}")` : ""}`);
  }
  if (files.length) lines.push(`Asset files to decorate the place (use these exact paths):\n${files.join("\n")}`);
  return lines.join("\n");
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
      const isReveal = i === plan.scenes.length - 1;
      const rich = SCENE_STYLE === "rich";
      const extra = rich
        ? `\n${assetBrief(beats[i].scene3d)}\n` +
          (isReveal
            ? `This is the REVEAL scene (product first appears). ${opts.productModel ? "A product model EXISTS: import Product from './BProduct' — <Product height={1.5} lidOpen={0..1} /> stands on y=0 (lidOpen 1 = lid off, leaning beside it, green gel visible). Use it, do not build the product yourself." : "No product model: build the product from primitives as described."}\n`
            : "This is NOT the reveal: do not show the product or its shape.\n")
        : "";
      jobs.push({
        s, order: beats[i].order, key, scene, tries: 0, ok: false,
        convo: [{ role: "user", content:
          `${rich ? RULES_RICH : RULES}${extra}\n\nScene to build (${scene.durationSec}s = ${Math.round(scene.durationSec * FPS)} frames, accent ${scene.color}, background ${scene.bg}):\n` +
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
  // 무대·인물·물건 모델: 부품은 generated/B*.tsx, 모델 파일은 public/bassets (끝나면 원래대로)
  const assetDir = join(pdir, "public/bassets");
  const assetSnap = snapshotDir(assetDir);
  const assetDirExisted = readdirSync(assetDir).length > 0;
  try {
    if (SCENE_STYLE === "rich") installSceneLib(genDir, opts.productModel);
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

    if (SCENE_STYLE === "rich") copySceneAssets([...passed].map((k) => join(genDir, `${k}.tsx`)), assetDir);
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
    assetSnap.restore();
    if (!assetDirExisted) rmSync(assetDir, { recursive: true, force: true });
  }
}

/** 렌더 결과 PNG가 모두 있는지 (테스트용) */
export function cutFilesExist(projectDir: string, cuts: ScenarioCuts[]): boolean {
  return cuts.every((c) => c.beats.every((b) => b.images.every((p) => existsSync(join(projectDir, p)))));
}
