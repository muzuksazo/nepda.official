// API 호출 없이 컷 렌더 경로를 확인한다 (video_test/pipeline 필요, 1~2분). 장면 키트 방식(기본), 화면 검수는 끔(B_QA=0).
process.env.B_QA = "0";
// 가짜 모델: 장면 1은 처음에 금지 패턴(Math.random)을 써서 실패 → 2차에 통과, 나머지는 바로 통과.
// 실행: npx tsx test/cuts-render.ts
import assert from "node:assert/strict";
import { existsSync, readFileSync, readdirSync, rmSync } from "node:fs";
import { join, resolve } from "node:path";
import { MockLanguageModelV4 } from "ai/test";
import { cutFilesExist, pipelineDir, renderCuts } from "../src/cuts.js";
import type { ScenarioItem } from "../src/schema.js";

const example = JSON.parse(readFileSync("examples/02_scenarios.response.json", "utf8")).scenarios[0] as ScenarioItem;
const scenario: ScenarioItem = { ...example, scenario_id: "sc_cuttest01" };

const tsx = (bad = false) => "```tsx\n" + `import React from 'react';
import { useCurrentFrame, interpolate } from 'remotion';
export default function Viz({ frame, durationInFrames, color }: { frame: number; progress: number; durationInFrames: number; color: string }) {
  const f = useCurrentFrame();
  const t = interpolate(frame ?? f, [0, durationInFrames - 1], [0, Math.PI * 2]);
  ${bad ? "const jitter = Math.random();" : ""}
  return (
    <group>
      <mesh rotation={[Math.PI / 2, 0, t]}>
        <cylinderGeometry args={[0.85, 0.85, 0.1, 64, 1, false, 0, t]} />
        <meshStandardMaterial color={color} />
      </mesh>
    </group>
  );
}
` + "```";
const reply = (text: string) => ({
  content: [{ type: "text" as const, text }],
  finishReason: { unified: "stop" as const, raw: "end_turn" },
  usage: { inputTokens: { total: 800, noCache: 800, cacheRead: 0, cacheWrite: 0 }, outputTokens: { total: 400, text: 400, reasoning: 0 } },
  warnings: [],
});

let call = 0;
const model = new MockLanguageModelV4({
  doGenerate: async (opts) => {
    call++;
    const prompt = JSON.stringify(opts.prompt);
    const isBeat1First = prompt.includes("3D 단면 지구") && !prompt.includes("That code failed");
    return reply(tsx(isBeat1First));
  },
});

const genDir = join(pipelineDir(), "src/generated");
const before = readdirSync(genDir).map((f) => f + ":" + readFileSync(join(genDir, f), "utf8")).sort();
const projectDir = resolve("out/_cuttest");
rmSync(projectDir, { recursive: true, force: true });

const t0 = Date.now();
const { cuts, steps } = await renderCuts([scenario], { model, modelId: "claude-opus-5-5", projectDir, round: 1, log: console.log, productModel: "piev" });
console.log(`소요 ${(Date.now() - t0) / 1000}초, 모델 호출 ${call}회`);

const beats = cuts[0].beats;
assert.equal(beats.length, 4);
assert.ok(beats.every((b) => b.ok), JSON.stringify(beats.map((b) => [b.order, b.ok, b.error])));
assert.equal(beats[0].tries, 2, "장면 1은 금지 패턴으로 한 번 실패 후 통과");
assert.ok(beats.every((b) => b.images.length === 4));
assert.ok(cutFilesExist(projectDir, cuts), "PNG가 모두 있어야 함");
assert.ok(existsSync(join(projectDir, "round-1/cuts/sc_cuttest01/beat1.tsx")) && existsSync(join(projectDir, "round-1/cuts/sc_cuttest01/beat1V.tsx")), "설계표 + 시각화 코드");
assert.ok(steps.some((s) => s.step.startsWith("컷: Remotion")) && steps.filter((s) => s.model === "claude-opus-5-5").length === 5);
const after = readdirSync(genDir).map((f) => f + ":" + readFileSync(join(genDir, f), "utf8")).sort();
assert.deepEqual(after, before, "pipeline/src/generated 는 원래대로 돌아와야 함");
console.log("OK cuts-render:", beats.map((b) => b.images[1]).join(", "));
