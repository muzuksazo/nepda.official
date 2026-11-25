import assert from "node:assert/strict";
import { mkdtempSync, readFileSync, readdirSync } from "node:fs";
import { createRequire } from "node:module";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";
import { buildPrototype, prototypeAssets } from "../../scripts/build-prototype.mjs";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "../..");
const require = createRequire(import.meta.url);

test("prototype build exposes the web assets without backend or campaign sources", () => {
  const output = mkdtempSync(join(tmpdir(), "napda-prototype-"));
  buildPrototype(output);
  assert.deepEqual(readdirSync(output).sort(), [...prototypeAssets].sort());
  for (const asset of prototypeAssets) {
    assert.deepEqual(readFileSync(join(output, asset)), readFileSync(join(root, "prototypes/hookcut", asset)));
  }
});

test("existing remix API entrypoint delegates to the grouped implementation", () => {
  assert.equal(require("../../api/remix.js"), require("../../prototypes/hookcut/api/remix.js"));
});
