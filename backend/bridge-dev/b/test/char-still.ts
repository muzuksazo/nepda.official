// 인물 장면 코드 확인용: 장면 tsx 하나를 SceneTest 로 몇 프레임 찍어 본다 (Claude 호출 없음).
//   npx tsx test/char-still.ts <scene.tsx> <seconds> <outDir>
import { copyFileSync, cpSync, existsSync, mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { copySceneAssets, installSceneLib } from "../src/assets/copy.js";
import { pipelineDir, snapshotDir, writeRegistry } from "../src/cuts.js";

const [scenePath, secArg, outArg, framesArg] = process.argv.slice(2); // framesArg: "0,15,18" (선택)
if (!scenePath) throw new Error("usage: tsx test/char-still.ts <scene.tsx> <seconds> <outDir>");
const here = dirname(fileURLToPath(import.meta.url));
const pdir = pipelineDir();
const genDir = join(pdir, "src/generated");
const assetDir = join(pdir, "public/bassets");
const assetExisted = existsSync(assetDir);
const gen = snapshotDir(genDir);
const assets = snapshotDir(assetDir);
const outDir = resolve(outArg ?? "out/_charstill");
mkdirSync(outDir, { recursive: true });
try {
  installSceneLib(genDir, process.env.B_PRODUCT_MODEL);
  console.log("assets", copySceneAssets([scenePath], assetDir));
  writeFileSync(join(genDir, "Ctest.tsx"), readFileSync(scenePath));
  // 키트 장면(beat<k>.tsx)이면 같은 폴더의 시각화 코드(beat<k>V.tsx)도 그 import 이름으로 넣는다
  const vizImport = /from '\.\/(B\w+V)'/.exec(readFileSync(scenePath, "utf8"));
  const vizPath = scenePath.replace(/\.tsx$/, "V.tsx");
  if (vizImport && existsSync(vizPath)) writeFileSync(join(genDir, `${vizImport[1]}.tsx`), readFileSync(vizPath));
  writeRegistry(genDir, ["Ctest"], gen.keepKeys);
  const req = createRequire(join(pdir, "package.json"));
  const { bundle } = req("@remotion/bundler");
  const { renderStill, selectComposition } = req("@remotion/renderer");
  const serveUrl = await bundle({ entryPoint: join(pdir, "src/index.ts") });
  const frames = Math.round(Number(secArg ?? 4) * 30);
  const scene = { type: "three", durationSec: frames / 30, text: "인물 테스트\n두 줄 자막", color: "#e8322a", bg: "#0b0b10", gen: "Ctest" };
  const inputProps = { genKey: "Ctest", scene, frames };
  const composition = await selectComposition({ serveUrl, id: "SceneTest", inputProps });
  const picks = framesArg ? framesArg.split(",").map(Number) : [0, Math.floor(frames * 0.25), Math.floor(frames * 0.5), Math.floor(frames * 0.75), frames - 1];
  for (const f of picks) {
    const out = join(outDir, `f${String(f).padStart(3, "0")}.png`);
    await renderStill({ composition, serveUrl, inputProps, frame: f, chromiumOptions: { gl: "angle" }, output: out });
    console.log(out);
  }
} finally {
  gen.restore();
  assets.restore();
  if (!assetExisted) rmSync(assetDir, { recursive: true, force: true });
}
