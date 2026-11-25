// API 호출 없이 전체 흐름을 확인한다.
// 아이디어(마인드맵 → 채점 → 인접 유사도) → 경로 선택 → 시나리오(1차 위반, 2차 통과) → 비용·리포트·pipeline plan.
// 실행: npx tsx test/mock-run.ts
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { MockLanguageModelV4 } from "ai/test";
import { checkScenario } from "../src/check.js";
import { generateScenarios } from "../src/generate.js";
import { pickDistinct, searchPaths, type ScoredWord } from "../src/ideate.js";
import { toPipelinePlan } from "../src/pipeline-plan.js";
import { renderReport } from "../src/report.js";
import { WorkerInputSchema } from "../src/schema.js";

// 1) 경로 탐색 단위 테스트
{
  const w = (word: string, sim: number, info = 0.8, usage = 0.1): ScoredWord => ({ word, lens: "far", branch: "x", info, sim, usage });
  // F: 유사도는 시작 범위지만 용도 영역(0.7)이라 시작이 될 수 없다
  const words = [w("A", 0.45, 0.9), w("B", 0.72), w("C", 0.85), w("D", 0.5, 0.7), w("E", 0.3), w("F", 0.5, 0.99, 0.7)];
  const key = (a: string, b: string) => (a < b ? `${a}\u0000${b}` : `${b}\u0000${a}`);
  const pairs = new Map([
    [key("A", "B"), 0.75], [key("B", "C"), 0.8], [key("A", "C"), 0.5],
    [key("D", "C"), 0.72], [key("D", "B"), 0.6], [key("F", "C"), 0.9],
  ]);
  const paths = searchPaths(words, pairs);
  const names = paths.map((p) => [p.start, ...p.bridges].map((n) => n.word).join(">"));
  assert.ok(names.includes("A>B>C") && names.includes("A>B") && names.includes("D>C"), `경로: ${names}`);
  assert.ok(!names.includes("A>C"), "인접 0.5는 탈락해야 함");
  assert.ok(!names.some((n) => n.startsWith("E")), "시작 유사도 0.3은 탈락해야 함");
  assert.ok(!names.some((n) => n.startsWith("F")), "용도 영역 단어는 시작이 될 수 없음");
  assert.deepEqual(pickDistinct(paths, 2).map((p) => p.start.word).sort(), ["A", "D"]);
  assert.equal(searchPaths(words, pairs, { excludeStarts: ["A"] }).some((p) => p.start.word === "A"), false);
  console.log("OK searchPaths");
}

// 2) 전체 흐름
const input = WorkerInputSchema.parse(JSON.parse(readFileSync("examples/01_worker-input.scenarios.json", "utf8")));

const reply = (obj: unknown, inT = 1000, outT = 500) => ({
  content: [{ type: "text" as const, text: JSON.stringify(obj) }],
  finishReason: { unified: "stop" as const, raw: "end_turn" },
  usage: {
    inputTokens: { total: inT, noCache: inT, cacheRead: 0, cacheWrite: 0 },
    outputTokens: { total: outT, text: outT, reasoning: 0 },
  },
  warnings: [],
});

const mindmap = {
  anchor: "남은 시간이 빨간 면적으로 보인다",
  usage_domains: ["시간", "집중", "공부"],
  anchor_fact: "빨간 원판이 0 방향으로 서서히 줄어들어 숫자를 읽지 않아도 남은 시간이 한눈에 보인다",
  number_hint: "도(°)",
  maps: [{ lens: "far", branches: [{ name: "동물", words: ["꿀벌 춤 각도", "원 360도", "부채꼴 면적", "고래 노래"] }] }],
};
const scores = {
  scores: [
    { word: "꿀벌 춤 각도", info: 0.9, sim: 0.45, usage: 0.1 },
    { word: "원 360도", info: 0.4, sim: 0.7, usage: 0.3 },
    { word: "부채꼴 면적", info: 0.3, sim: 0.85, usage: 0.4 },
    { word: "고래 노래", info: 0.8, sim: 0.2, usage: 0.05 },
    { word: "뇌 90분 주기", info: 0.95, sim: 0.45, usage: 0.75 },
  ],
};
const pairs = {
  pairs: [
    { a: "꿀벌 춤 각도", b: "원 360도", sim: 0.74 },
    { a: "원 360도", b: "부채꼴 면적", sim: 0.82 },
    { a: "꿀벌 춤 각도", b: "부채꼴 면적", sim: 0.55 },
  ],
};

const s3d = (fact: string, counter: { from: number; to: number; unit: string } | null = null) => ({
  fact_shown: fact,
  objects: [{ name: "원판", build: "CylinderGeometry r=1.2 h=0.1 thetaLength 가변", material: "meshStandardMaterial roughness 0.4", color: "#e8322a", position: "x0 y1.5" }],
  motion: [
    { from: 0, to: 0.5, action: "원판이 회전하며 등장" },
    { from: 0.5, to: 1, action: "부채꼴이 줄어든다" },
  ],
  camera: "dolly_in 7→5.5",
  counter,
  background: "#0b0b10",
  lighting: "ambient 0.5 + directional [3,5,4]",
});
const good = {
  hook_title: "꿀벌은 춤 각도로 길을 알려 줍니다",
  hook_duration_sec: 17,
  body_duration_sec: 18,
  replacement_test_note: "제품 전환 장면만 바꾸면 다른 제품에도 붙일 수 있어 B",
  beats: [
    { order: 1, role: "어긋난 시작", duration_sec: 6, visual: "꿀벌 8자 춤", narration: "꿀벌은 춤의 각도로 꽃이 있는 방향을 알려 준다고 합니다.", caption: "꿀벌 춤 각도\n= 꽃 방향", scene3d: s3d("춤 각도 = 방향") },
    { order: 2, role: "브리지 1", duration_sec: 5, visual: "원 360도", narration: "한 바퀴는 삼백육십 도입니다.", caption: "한 바퀴\n360도", scene3d: s3d("원 = 360도", { from: 0, to: 360, unit: "°" }) },
    { order: 3, role: "반전: 제품 첫 등장", duration_sec: 6, visual: "제품", narration: "비주얼 타이머는 남은 시간을 빨간 원판으로 보여 줍니다. 그래서 비주얼 타이머가 뭐냐고요?", caption: "남은 시간\n한눈에", scene3d: s3d("빨간 원판이 줄어든다") },
  ],
  ad_spec: {
    track_archetype: "B_info_hook_offset",
    hook_similarity_score: 0.5,
    anchor: "모델이 쓴 앵커(덮어써져야 함)",
    bridge_path: [{ word: "꿀벌", sim_to_anchor: 0.5 }, { word: "원", sim_to_anchor: 0.7 }],
    adjacent_min_sim: 0.7,
    number_thread: "도(°)",
    product_first_mention_beat: 3,
    product_taboo_keywords: ["타이머", "시계"],
    visual_style: "blender_3d_cutaway",
    fact_sources: [{ claim: "꿀벌 8자 춤 각도", status: "출처 확인 필요" }],
  },
};
const bad = structuredClone(good);
bad.beats[1].scene3d.motion = [{ from: 0.3, to: 0.5, action: "잠깐 회전" }];

const model = new MockLanguageModelV4({
  doGenerate: [reply(mindmap), reply(scores), reply(pairs), reply({ scenarios: [bad] }, 3000, 2000), reply({ scenarios: [good] }, 3500, 2200)],
});
const run = await generateScenarios(input, { model, modelId: "claude-opus-5-5", ideaModelId: "claude-opus-5-5", log: (m) => console.log(m) });

assert.equal(run.steps.length, 5, "아이디어 3단계 + 시나리오 2회");
assert.equal(run.attempts, 2);
assert.equal(run.checks[0].errors.length, 0, JSON.stringify(run.checks[0]));
const retryPrompt = JSON.stringify(model.doGenerateCalls[4].prompt);
assert.ok(retryPrompt.includes("움직임"), "재시도 프롬프트에 3D 움직임 위반이 들어가야 함");
assert.ok(JSON.stringify(model.doGenerateCalls[3].prompt).includes("꿀벌 춤 각도"), "고른 경로가 시나리오 프롬프트에 들어가야 함");
const s = run.response.scenarios[0];
// 점수가 같으면 짧은 경로(브리지 1개)가 먼저 → 장면 3개와 맞는다
assert.deepEqual(s.ad_spec.bridge_path.map((n) => n.word), ["꿀벌 춤 각도", "원 360도"], "경로 값은 검색 결과로 덮어써야 함");
assert.equal(s.ad_spec.hook_similarity_score, 0.45);
assert.equal(s.ad_spec.adjacent_min_sim, 0.74);
assert.equal(s.ad_spec.anchor, mindmap.anchor);
// 비용: 입력 1000*3+3000+3500=9500, 출력 500*3+2000+2200=5700 → 9500*4/1e6 + 5700*20/1e6 = 0.152
assert.equal(run.total.inputTokens, 9500);
assert.equal(run.total.outputTokens, 5700);
assert.ok(Math.abs(run.total.costUsd - 0.152) < 1e-9, `cost ${run.total.costUsd}`);

const plan = toPipelinePlan(s);
assert.equal(plan.scenes.length, 3);
assert.equal(plan.scenes[1].counter?.to, 360);
assert.ok(plan.scenes[0].visual.includes("MOTION") && plan.scenes[0].say.endsWith("합니다."));
assert.equal(plan.hookSeconds, 17);

// 템플릿: 질문형 시작은 위반, 반전이 "그래서 ~뭐냐고요?"로 안 끝나면 위반
{
  const q = structuredClone(good);
  q.beats[0].narration = "꿀벌이 춤으로 길을 알려 준다는 사실, 알고 계셨나요?";
  assert.ok(checkScenario(q as never, input.product_info).errors.some((e) => e.includes("질문형")), "질문형 시작은 위반");
  const r = structuredClone(good);
  r.beats[2].narration = "그래서 비주얼 타이머는 남은 시간을 빨간 원판으로 보여 줍니다.";
  assert.ok(checkScenario(r as never, input.product_info).errors.some((e) => e.includes("템플릿")), "반전 템플릿 위반");
  assert.equal(checkScenario(good as never, input.product_info).errors.length, 0, JSON.stringify(checkScenario(good as never, input.product_info).errors));
}

// 길이 15~20초: 14초·21초는 위반, 15·20초는 통과
for (const [sec, ok] of [[14, false], [15, true], [20, true], [21, false]] as const) {
  const d = structuredClone(good);
  d.hook_duration_sec = sec;
  d.beats[2].duration_sec = sec - 11;
  const hit = checkScenario(d as never, input.product_info).errors.some((e) => e.includes("hook_duration_sec"));
  assert.equal(hit, !ok, `${sec}초 판정`);
}

const run2 = { ...run, response: { ...run.response, round: 2 }, createdAt: new Date().toISOString() };
const html = renderReport([run, run2], input.product_info.name);
assert.equal((html.match(/<details class="round"/g) ?? []).length, 2, "회차 2개");
assert.equal((html.match(/<details class="round" open>/g) ?? []).length, 1, "최신 회차만 펼침");
assert.ok(html.indexOf("2회차") < html.indexOf("1회차"), "최신 회차가 위");
assert.ok(html.includes("$0.152") && html.includes("3D 장면 명세") && html.includes("유사도 검색"));
if (process.env.MOCK_REPORT) (await import("node:fs")).writeFileSync(process.env.MOCK_REPORT, html);
console.log("OK mock-run: 아이디어 → 경로 → 재시도 → 비용 → pipeline plan → 리포트");
