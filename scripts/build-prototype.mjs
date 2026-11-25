import { copyFileSync, mkdirSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
export const prototypeAssets = ["index.html", "three_render.js", "render_bridge.js"];

export function buildPrototype(output = join(root, "dist", "prototype")) {
  mkdirSync(output, { recursive: true });
  for (const file of prototypeAssets) {
    copyFileSync(join(root, "prototypes", "hookcut", file), join(output, file));
  }
  return output;
}

if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) {
  console.log(`Prototype assets: ${buildPrototype()}`);
}
