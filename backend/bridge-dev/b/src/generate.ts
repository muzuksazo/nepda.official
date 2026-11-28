import { isGemini, llm, stepOptions } from "./llm.js";
import { randomUUID } from "node:crypto";
import { generateText, Output, type LanguageModel } from "ai";
import { anthropic } from "@ai-sdk/anthropic";
import { checkAgainstPrevious, checkScenario, type CheckResult } from "./check.js";
import { priceOf, totals, type StepUsage } from "./cost.js";
import { ideate, rankSeeds, type IdeationResult, type StorySeed } from "./ideate.js";
import { buildUserPrompt, SYSTEM_PROMPT, type SeedBrief } from "./prompt.js";
import {
  ScenarioOnlyResponseSchema,
  type DraftScenario,
  type ScenarioItem,
  type ScenariosResponse,
  type WorkerInput,
} from "./schema.js";

export const DEFAULT_MODEL = "claude-opus-5-5";
/** 주제 후보(마인드맵)·채점 단계 기본 모델 */
export const IDEA_MODEL = "claude-sonnet-5-5";

export interface GenerateOptions {
  /** 기본: B_MODEL 환경변수 → claude-opus-5-5 */
  modelId?: string;
  /** 아이디어 단계 모델. 기본: B_IDEA_MODEL → modelId */
  ideaModelId?: string;
  /** 테스트용으로 모델을 바꿔 끼울 때 (두 단계 모두 이 모델 사용) */
  model?: LanguageModel;
  /** 유사도 검색 단계를 건너뛸 때 false. 기본 true */
  ideate?: boolean;
  /** 같은 프로젝트에서 저장해 둔 검색 결과. 있으면 재사용하고 앵커를 고정한다(후보가 떨어지면 추가 검색) */
  pool?: IdeationResult | null;
  /** 규칙 위반 시 다시 생성하는 최대 횟수(첫 시도 포함). 기본 2 */
  maxAttempts?: number;
  log?: (msg: string) => void;
}

export interface RunRecord {
  response: ScenariosResponse;
  checks: (CheckResult & { scenario_id: string })[];
  attempts: number;
  modelId: string;
  ideaModelId: string;
  ideation: IdeationResult | null;
  /** new: 새 검색 / reused: 저장된 검색 재사용 / expanded: 재사용 + 추가 검색 (앵커는 그대로) */
  ideationSource?: "new" | "reused" | "expanded";
  /** 시나리오 프롬프트에 후보로 준 이야기 씨앗 */
  seedCandidates?: StorySeed[];
  steps: StepUsage[];
  total: ReturnType<typeof totals>;
  createdAt: string;
  /** 컷 이미지 (--cuts 또는 npm run cuts) */
  cuts?: import("./cuts.js").ScenarioCuts[];
  /** 훅 영상 (npm run video) */
  videos?: import("./video.js").HookVideo[];
}

function checkAll(drafts: DraftScenario[], input: WorkerInput): CheckResult[] {
  return drafts.map((d) => {
    const r = checkScenario(d, input.product_info);
    r.warnings.push(...checkAgainstPrevious(d, input.previous_scenarios));
    return r;
  });
}

/** 고른 씨앗이 후보에 있으면 발단 유사도는 모델 자기 평가 대신 검색 단계 점수를 쓴다. */
function applySeed(d: DraftScenario, seeds: StorySeed[], anchor: string | undefined): DraftScenario {
  const picked = d.ad_spec.story_seed?.trim();
  const seed = picked ? seeds.find((s) => s.word === picked || picked.includes(s.word) || s.word.includes(picked)) : undefined;
  const ad = { ...d.ad_spec, anchor: anchor ?? d.ad_spec.anchor };
  if (seed) {
    ad.story_seed = seed.word;
    ad.hook_similarity_score = seed.sim;
    if (ad.bridge_path[0]) ad.bridge_path = [{ ...ad.bridge_path[0], sim_to_anchor: seed.sim }, ...ad.bridge_path.slice(1)];
  }
  return { ...d, ad_spec: ad };
}

export async function generateScenarios(input: WorkerInput, opts: GenerateOptions = {}): Promise<RunRecord> {
  const modelId = opts.modelId || process.env.B_MODEL?.trim() || DEFAULT_MODEL;
  // 주제 후보·채점은 빠른 모델로 (시나리오 2분대 → 단축, 2026-11-28). Gemini 로 돌 때는 같은 모델을 쓴다
  const ideaModelId =
    opts.ideaModelId || process.env.B_IDEA_MODEL?.trim() || (isGemini(modelId) ? modelId : IDEA_MODEL);
  const model = opts.model ?? llm(modelId);
  const ideaModel = opts.model ?? llm(ideaModelId);
  const maxAttempts = Math.max(1, opts.maxAttempts ?? 2);
  const log = opts.log ?? (() => {});
  const steps: StepUsage[] = [];
  const track = (s: StepUsage) => steps.push(s);

  // 1) 유사도 검색
  let ideation: IdeationResult | null = null;
  let ideationSource: RunRecord["ideationSource"];
  let chosen: StorySeed[] = [];
  if (opts.ideate !== false) {
    const used = input.previous_scenarios
      .map((s) => (s as { ad_spec?: { story_seed?: string } })?.ad_spec?.story_seed)
      .filter((w): w is string => !!w);
    if (opts.pool?.seeds?.length) {
      // 검색 재사용: 저장된 씨앗에서 이미 쓴 것만 빼고 고른다. 앵커는 그대로.
      ideation = opts.pool;
      ideationSource = "reused";
      steps.push({ step: "아이디어: 저장된 검색 재사용 (앵커 고정)", model: "-", inputTokens: 0, outputTokens: 0, costUsd: 0, ms: 0 });
      const left = rankSeeds(ideation.seeds, { exclude: used }).length;
      log(`[B 아이디어] 저장된 검색 재사용 — 남은 씨앗 ${left}개, 앵커: ${ideation.anchor}`);
      if (left < input.count) {
        log("[B 아이디어] 남은 씨앗이 부족해서 추가 검색 (앵커 고정)");
        ideation = await ideate(input, ideaModel, ideaModelId, track, { log, expandFrom: ideation });
        ideationSource = "expanded";
      }
    } else {
      ideation = await ideate(input, ideaModel, ideaModelId, track, { log });
      ideationSource = "new";
    }
    chosen = rankSeeds(ideation.seeds, { exclude: used }).slice(0, Math.max(3, input.count * 2));
    if (chosen.length < input.count)
      log(`[B] 조건(발단 0.40~0.60·용도 영역 0.35 이하·결말 연결 0.6 이상)을 만족하는 씨앗 ${chosen.length}개뿐. 나머지는 모델이 직접 고름`);
  }
  const brief: SeedBrief | undefined = ideation
    ? { anchor: ideation.anchor, anchorFact: ideation.anchorFact, usageDomains: ideation.usageDomains, seeds: chosen }
    : undefined;

  // 2) 시나리오 생성 (3D 명세는 컷 단계)
  let feedback: string | undefined;
  let drafts: DraftScenario[] = [];
  let checks: CheckResult[] = [];
  let attempts = 0;

  while (attempts < maxAttempts) {
    attempts++;
    log(`[B] 시나리오 ${modelId} 호출 ${attempts}/${maxAttempts} (count=${input.count})`);
    const t0 = performance.now();
    const result = await generateText({
      model,
      system: SYSTEM_PROMPT,
      prompt: buildUserPrompt(input, feedback, brief),
      // 3D 명세(scene3d)는 여기서 만들지 않는다 → 컷 단계에서 고른 시나리오에만 (src/scene3d.ts)
      output: Output.object({ schema: ScenarioOnlyResponseSchema }),
      maxOutputTokens: 16000,
      providerOptions: stepOptions("scenario", "medium"), // high → medium: 시나리오 시간 단축 (2026-11-28)
    });
    const inT = result.usage?.inputTokens ?? 0;
    const outT = result.usage?.outputTokens ?? 0;
    steps.push({
      step: `시나리오 ${attempts}차`,
      model: modelId,
      inputTokens: inT,
      outputTokens: outT,
      costUsd: priceOf(modelId, inT, outT),
      ms: Math.round(performance.now() - t0),
    });

    drafts = result.output.scenarios
      .slice(0, input.count)
      .map((d) => applySeed(d, chosen, ideation?.anchor));
    if (drafts.length < input.count) log(`[B] 요청 ${input.count}개 중 ${drafts.length}개만 생성됨`);
    checks = checkAll(drafts, input);

    const failing = checks
      .map((c, i) => (c.errors.length ? `시나리오 ${i + 1} "${drafts[i].hook_title}":\n${c.errors.map((e) => `  - ${e}`).join("\n")}` : ""))
      .filter(Boolean);
    if (!failing.length) break;
    feedback = failing.join("\n");
    log(`[B] 규칙 위반:\n${feedback}`);
  }

  const scenarios: ScenarioItem[] = drafts.map((d) => ({
    scenario_id: `sc_${randomUUID().replace(/-/g, "").slice(0, 10)}`,
    round: input.round,
    type: "B",
    ...d,
  }));

  return {
    response: { project_id: input.project_id, status: "SCENARIOS_READY", round: input.round, scenarios },
    checks: checks.map((c, i) => ({ ...c, scenario_id: scenarios[i].scenario_id })),
    attempts,
    modelId,
    ideaModelId,
    ideation,
    ideationSource,
    seedCandidates: chosen,
    steps,
    total: totals(steps),
    createdAt: new Date().toISOString(),
  };
}
