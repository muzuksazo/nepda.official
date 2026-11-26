import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { MockLanguageModelV4 } from "ai/test";
import { pickUnusedArchetypes } from "../src/archetypes.js";
import { checkScenario } from "../src/check.js";
import { generateScenarios } from "../src/generate.js";
import { ScenariosResponseSchema, WorkerInputSchema } from "../src/schema.js";

const reply = (obj: unknown, inT = 800, outT = 400) => ({
  content: [{ type: "text" as const, text: JSON.stringify(obj) }],
  finishReason: { unified: "stop" as const, raw: "end_turn" },
  usage: {
    inputTokens: { total: inT, noCache: inT, cacheRead: 0, cacheWrite: 0 },
    outputTokens: { total: outT, text: outT, reasoning: 0 },
  },
  warnings: [],
});

// 1) 예제 응답(02_scenarios.response.json) & 입력 정적 검사 통과 확인
const input = WorkerInputSchema.parse(JSON.parse(readFileSync("examples/01_worker-input.scenarios.json", "utf8")));
const exampleRes = ScenariosResponseSchema.parse(JSON.parse(readFileSync("examples/02_scenarios.response.json", "utf8")));
const exCheck = checkScenario(exampleRes.scenarios[0], input.product_info);
assert.equal(exCheck.errors.length, 0, `예제 응답 검사 실패: ${exCheck.errors.join("; ")}`);
console.log("OK example check");

// 2) 이전 회차 장르 중복 방지 확인 (courtroom_trial 사용 후 다음 픽에서는 배제)
const picked = pickUnusedArchetypes([exampleRes.scenarios[0]], 1);
assert.notEqual(picked[0].id, "courtroom_trial", "이전 회차 장르를 건너뛰어야 함");
console.log(`OK pickUnusedArchetypes -> ${picked[0].id}`);

// 3) 4단계 블라인드 파이프라인 + Double-Zero 금칙어 적발 후 자동 재시도 검증
const lawOut = {
  abstract_law: "흘러가는 것을 막으려 겉만 덮지 말고 눈에 보이는 실물 면적 자체를 잠가야 한다",
  core_verified_fact: "빨간 원판이 0 방향으로 서서히 줄어들어 숫자를 읽지 않아도 남은 시간이 한눈에 보인다",
  product_taboo_keywords: ["타이머", "시계", "다이얼", "원판", "뽀모도로"],
  category_taboo_keywords: ["공부", "집중", "독서실", "책상"],
  reference_surface_taboo: ["제트기", "우산"],
};

// 시도 1: 의도적으로 반전 전 비트 1에 금지어 "타이머"와 "집중" 누출
const badBlindHook = {
  hook_title: "타이머 폭발 실험",
  a_genre_archetype: "extreme_physics_experiment",
  visual_style: "blender_3d_physics",
  silence_gap_sec: 0.25,
  pre_twist_beats: [
    { order: 1, role: "어긋난 시작", duration_sec: 3.0, visual: "거대한 타이머 폭탄", narration: "집중 못 하면 터지는 100톤 댐을 테이프로 막아봤습니다.", caption: "타이머 폭탄 실험" },
    { order: 2, role: "빌드업", duration_sec: 3.5, visual: "테이프가 팽창하며 부푼다", narration: "겉만 덮어놨더니 수압이 폭발합니다.", caption: "겉만 덮으면\n바로 터집니다" },
    { order: 3, role: "패턴 인터럽트", duration_sec: 1.5, visual: "폭발 직전 정지", narration: "", caption: "정적!" },
  ],
};

// 시도 2: 100% 무맥락(제품·카테고리 단서 0%) 훅
const goodBlindHook = {
  hook_title: "100톤 댐 테이프 봉인 실험",
  a_genre_archetype: "extreme_physics_experiment",
  visual_style: "blender_3d_physics",
  silence_gap_sec: 0.25,
  pre_twist_beats: [
    { order: 1, role: "어긋난 시작", duration_sec: 3.0, visual: "3D 수력 댐 균열에 은색 테이프 100겹을 붙이는 작업자", narration: "100톤 수압이 밀려오는 댐 균열을 테이프로 덮으면 어떻게 될까요?", caption: "100톤 수압 vs\n테이프 100겹" },
    { order: 2, role: "빌드업", duration_sec: 3.5, visual: "수압 돔이 부풀다 테이프와 함께 날아가는 슬로모션", narration: "겉만 덮어놔도 안쪽 압력은 그대로 쌓여 한 번에 날아갑니다.", caption: "겉만 덮어봤자\n3초 만에 붕괴" },
    { order: 3, role: "패턴 인터럽트", duration_sec: 1.5, visual: "충격 직전 0.25초 프리즈 프레임", narration: "", caption: "딱 3초!" },
  ],
};

const bridgePayoff = {
  payoff_beat: {
    duration_sec: 4.0,
    visual: "실물 60분 비주얼 타이머의 빨간 원판이 부드럽게 줄어드는 클로즈업",
    narration: "시간 관리도 겉치레 대신 남은 면적이 바로 보이는 60분 비주얼 아날로그 타이머가 답입니다.",
    caption: "남은 면적이\n한눈에 보입니다",
  },
  replacement_test_note: "0~8초 댐·테이프 실험은 어떤 제품군에도 연결 가능한 0% 제품 단서 무맥락 훅입니다.",
  closing_callback: "댐까지 터뜨려 봤습니다.",
};

const model = new MockLanguageModelV4({
  doGenerate: [
    reply(lawOut),
    reply(badBlindHook),
    reply(bridgePayoff),
    reply(goodBlindHook),
    reply(bridgePayoff),
  ],
});

const run = await generateScenarios(input, { model, log: (m) => console.log(m) });

// 핵심 검증 1: 2단계 블라인드 프롬프트에 제품명("뽀모도로")이나 카테고리("stationery")가 절대 포함되지 않았는가?
const blindPromptText = JSON.stringify(model.doGenerateCalls[1].prompt);
assert.ok(blindPromptText.includes(lawOut.abstract_law), "Stage 2 프롬프트에 추상 법칙이 들어가야 함");
assert.ok(!blindPromptText.includes("stationery"), "★ Stage 2 블라인드 프롬프트에 카테고리 노출 금지");
assert.ok(!blindPromptText.includes("아날로그"), "★ Stage 2 블라인드 프롬프트에 제품명 노출 금지");
console.log("OK Stage 2 blind isolation");

// 핵심 검증 2: 1차 시도의 금지어 누출이 걸러져 재시도(calls[3]) 프롬프트에 에러 피드백이 전달되고 2차에서 0에러 통과!
const retryPromptText = JSON.stringify(model.doGenerateCalls[3].prompt);
assert.ok(retryPromptText.includes("금칙어") || retryPromptText.includes("타이머"), "재시도 프롬프트에 금지어 위반 피드백이 들어가야 함");
assert.equal(run.attempts, 2);
assert.equal(run.checks[0].errors.length, 0, JSON.stringify(run.checks[0]));
assert.equal(run.response.scenarios[0].ad_spec.a_genre_archetype, "extreme_physics_experiment");
console.log("OK Mock E2E Track A blind pipeline + auto-retry (0 errors)");
