import { readdirSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const requested = process.argv.slice(2);
function collect(directory) {
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const file = join(directory, entry.name);
    return entry.isDirectory() ? collect(file) : /\.test\.(ts|mjs)$/.test(entry.name) ? [file] : [];
  });
}
const files = collect(join(root, "tests")).filter((file) =>
  requested.length === 0 || requested.some((area) => file.startsWith(join(root, "tests", area) + "/") || file.startsWith(join(root, "tests", area) + "\\"))
).sort();
if (!files.length) throw new Error("No Node tests matched the requested PRD areas");
const result = spawnSync(process.execPath, ["--import", "tsx", "--test", ...files], { cwd: root, stdio: "inherit" });
if (result.error) throw result.error;
process.exitCode = result.status ?? 1;
