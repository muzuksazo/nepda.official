// API 호출 없이 전체 흐름을 확인한다 (이야기 모드).
// 아이디어(앵커·이야기 씨앗 → 씨앗 채점) → 씨앗 후보 → 시나리오(1차 템플릿 위반, 2차 통과) → 비용·리포트·pipeline plan.
// 실행: npx tsx test/mock-run.ts
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { MockLanguageModelV4 } from "ai/test";
import { checkScenario } from "../src/check.js";
import { generateScenarios } from "../src/generate.js";
import { rankSeeds, type StorySeed } from "../src/ideate.js";
import { toPipelinePlan } from "../src/pipeline-plan.js";
import { renderReport } from "../src/report.js";
import { WorkerInputSchema } from "../src/schema.js";

// 1) 씨앗 고르기 단위 테스트
{
  const s = (word: string, sim: number, usage: number, link: number, info = 0.8): StorySeed => ({
    word, arc: "-", lens: "record", info, sim, usage, link, score: Math.round(info * link * (1 - sim) * 1000) / 1000,
  });
  const seeds = [
    s("A 나이팅게일", 0.45, 0.1, 0.9),
    s("B 용도 영역", 0.5, 0.7, 0.9, 0.99), // 용도 영역이라 탈락
    s("C 연결 약함", 0.5, 0.1, 0.4), // 결말 연결 약해서 탈락
    s("D 너무 가까움", 0.75, 0.1, 0.9), // 발단이 앵커에 너무 가까워 탈락
    s("E 해바라기", 0.55, 0.2, 0.8, 0.7),
  ];
  assert.deepEqual(rankSeeds(seeds).map((x) => x.word), ["A 나이팅게일", "E 해바라기"]);
  assert.deepEqual(rankSeeds(seeds, { exclude: ["A 나이팅게일"] }).map((x) => x.word), ["E 해바라기"]);
  console.log("OK rankSeeds");
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

const SEED = "나이팅게일 1858년 사망 원인을 부채꼴 면적으로 그림";
const mindmap = {
  anchor: "남은 시간이 빨간 면적으로 보인다",
  usage_domains: ["시간", "집중", "공부"],
  anchor_fact: "빨간 원판이 0 방향으로 서서히 줄어들어 숫자를 읽지 않아도 남은 시간이 한눈에 보인다",
  number_hint: "면적",
  seeds: [
    { lens: "record", word: SEED, arc: "사망 원인 집계 → 표로는 설득 실패 → 부채꼴 면적 그래프" },
    { lens: "human", word: "뽀모도로 창시자 25분", arc: "용도 영역 이야기" },
  ],
};
const scores = {
  scores: [
    { word: SEED, info: 0.9, sim: 0.45, usage: 0.1, link: 0.9 },
    { word: "뽀모도로 창시자 25분", info: 0.95, sim: 0.5, usage: 0.9, link: 0.9 },
  ],
};

const good = {
  hook_title: "나이팅게일의 부채꼴",
  hook_duration_sec: 17,
  body_duration_sec: 18,
  replacement_test_note: "제품 전환 장면만 바꾸면 다른 제품에도 붙일 수 있어 B",
  beats: [
    { order: 1, role: "발단", duration_sec: 5, visual: "야전 병원 침대 줄", narration: "나이팅게일은 전쟁터 병원에서 병사들이 죽는 이유를 세어 봤습니다.", caption: "1854년\n야전 병원" },
    { order: 2, role: "전개", duration_sec: 5, visual: "부채꼴 그래프가 펼쳐짐", narration: "그래서 그녀는 원을 부채꼴로 나눠 죽음을 면적으로 그렸습니다.", caption: "원을 나눠\n면적으로" },
    { order: 3, role: "반전: 제품 첫 등장", duration_sec: 7, visual: "제품", narration: "비주얼 타이머는 남은 시간을 빨간 면적으로 보여 줍니다. 그래서 비주얼 타이머가 뭐냐고요?", caption: "남은 시간\n빨간 면적" },
  ],
  ad_spec: {
    track_archetype: "B_info_hook_offset",
    hook_similarity_score: 0.5,
    anchor: "모델이 쓴 앵커(덮어써져야 함)",
    bridge_path: [{ word: "사망 원인 집계", sim_to_anchor: 0.5 }, { word: "부채꼴 면적 그래프", sim_to_anchor: 0.75 }],
    adjacent_min_sim: 0.72,
    number_thread: "면적",
    product_first_mention_beat: 3,
    product_taboo_keywords: ["타이머", "시계"],
    story_seed: SEED,
    visual_style: "blender_3d_cutaway",
    fact_sources: [{ claim: "나이팅게일의 장미 도표(1858)", status: "출처 확인 필요" }],
  },
};
const bad = structuredClone(good);
bad.beats[2].narration = "그래서 비주얼 타이머는 남은 시간을 빨간 면적으로 보여 줍니다."; // 템플릿 위반

const model = new MockLanguageModelV4({
  doGenerate: [reply(mindmap), reply(scores), reply({ scenarios: [bad] }, 3000, 1000), reply({ scenarios: [good] }, 3500, 1200)],
});
const run = await generateScenarios(input, { model, modelId: "claude-opus-5-5", ideaModelId: "claude-opus-5-5", log: (m) => console.log(m) });

assert.equal(run.steps.length, 4, "아이디어 2단계(씨앗·채점) + 시나리오 2회");
assert.equal(run.attempts, 2);
assert.equal(run.checks[0].errors.length, 0, JSON.stringify(run.checks[0]));
assert.ok(JSON.stringify(model.doGenerateCalls[3].prompt).includes("템플릿"), "재시도 프롬프트에 템플릿 위반이 들어가야 함");
const scenarioPrompt = JSON.stringify(model.doGenerateCalls[2].prompt);
assert.ok(scenarioPrompt.includes(SEED), "조건 통과 씨앗이 후보로 들어가야 함");
assert.ok(!scenarioPrompt.includes("뽀모도로 창시자"), "용도 영역 씨앗은 후보에서 빠져야 함");
const s = run.response.scenarios[0];
assert.equal(s.ad_spec.story_seed, SEED);
assert.equal(s.ad_spec.hook_similarity_score, 0.45, "발단 유사도는 검색 점수로");
assert.equal(s.ad_spec.bridge_path[0].sim_to_anchor, 0.45);
assert.equal(s.ad_spec.anchor, mindmap.anchor);
assert.equal(run.seedCandidates?.length, 1);
// 비용: 입력 1000*2+3000+3500=8500, 출력 500*2+1000+1200=3200 → 8500*4/1e6 + 3200*20/1e6 = 0.098
assert.equal(run.total.inputTokens, 8500);
assert.equal(run.total.outputTokens, 3200);
assert.ok(Math.abs(run.total.costUsd - 0.098) < 1e-9, `cost ${run.total.costUsd}`);

const plan = toPipelinePlan(s);
assert.equal(plan.scenes.length, 3);
assert.equal(plan.hookSeconds, 17);

// 템플릿: 질문형 시작은 위반, 반전이 "그래서 ~뭐냐고요?"로 안 끝나면 위반
{
  const q = structuredClone(good);
  q.beats[0].narration = "나이팅게일이 그래프를 그렸다는 사실, 알고 계셨나요?";
  assert.ok(checkScenario(q as never, input.product_info).errors.some((e) => e.includes("질문형")), "질문형 시작은 위반");
  assert.ok(checkScenario(bad as never, input.product_info).errors.some((e) => e.includes("템플릿")), "반전 템플릿 위반");
}

// 길이 15~20초: 14초·21초는 위반, 15·20초는 통과
for (const [sec, ok] of [[14, false], [15, true], [20, true], [21, false]] as const) {
  const d = structuredClone(good);
  d.hook_duration_sec = sec;
  d.beats[2].duration_sec = sec - 10;
  const hit = checkScenario(d as never, input.product_info).errors.some((e) => e.includes("hook_duration_sec"));
  assert.equal(hit, !ok, `${sec}초 판정`);
}

const run2 = { ...run, response: { ...run.response, round: 2 }, createdAt: new Date().toISOString() };
const html = renderReport([run, run2], input.product_info.name);
assert.equal((html.match(/<details class="round"/g) ?? []).length, 2, "회차 2개");
assert.equal((html.match(/<details class="round" open>/g) ?? []).length, 1, "최신 회차만 펼침");
assert.ok(html.indexOf("2회차") < html.indexOf("1회차"), "최신 회차가 위");
assert.ok(html.includes("$0.098") && html.includes("이야기 씨앗") && html.includes(SEED));
if (process.env.MOCK_REPORT) (await import("node:fs")).writeFileSync(process.env.MOCK_REPORT, html);
console.log("OK mock-run: 씨앗 → 후보 → 재시도 → 비용 → pipeline plan → 리포트");
