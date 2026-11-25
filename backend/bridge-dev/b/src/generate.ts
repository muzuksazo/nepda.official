import { randomUUID } from "node:crypto";
import { generateText, Output, type LanguageModel } from "ai";
import { anthropic } from "@ai-sdk/anthropic";
import { checkAgainstPrevious, checkScenario, type CheckResult } from "./check.js";
import { priceOf, totals, type StepUsage } from "./cost.js";
import { ideate, rankSeeds, type IdeationResult, type StorySeed } from "./ideate.js";
import { buildUserPrompt, SYSTEM_PROMPT, type SeedBrief } from "./prompt.js";
import {
  DraftResponseSchema,
  type DraftScenario,
  type ScenarioItem,
  type ScenariosResponse,
  type WorkerInput,
} from "./schema.js";

export const DEFAULT_MODEL = "claude-opus-5-5";

export interface GenerateOptions {
  /** 기본: B_MODEL 환경변수 → claude-opus-5-5 */
  modelId?: string;
  /** 아이디어 단계 모델. 기본: B_IDEA_MODEL → modelId */
  ideaModelId?: string;
  /** 테스트용으로 모델을 바꿔 끼울 때 (두 단계 모두 이 모델 사용) */
  model?: LanguageModel;
  /** 유사도 검색 단계를 건너뛸 때 false. 기본 true */
  ideate?: boolean;
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
  const ideaModelId = opts.ideaModelId || process.env.B_IDEA_MODEL?.trim() || modelId;
  const model = opts.model ?? anthropic(modelId);
  const ideaModel = opts.model ?? anthropic(ideaModelId);
  const maxAttempts = Math.max(1, opts.maxAttempts ?? 2);
  const log = opts.log ?? (() => {});
  const steps: StepUsage[] = [];
  const track = (s: StepUsage) => steps.push(s);

  // 1) 유사도 검색
  let ideation: IdeationResult | null = null;
  let chosen: StorySeed[] = [];
  if (opts.ideate !== false) {
    ideation = await ideate(input, ideaModel, ideaModelId, track, { log });
    const used = input.previous_scenarios
      .map((s) => (s as { ad_spec?: { story_seed?: string } })?.ad_spec?.story_seed)
      .filter((w): w is string => !!w);
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
      output: Output.object({ schema: DraftResponseSchema }),
      maxOutputTokens: 16000,
      providerOptions: { anthropic: { effort: "high" } },
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
    seedCandidates: chosen,
    steps,
    total: totals(steps),
    createdAt: new Date().toISOString(),
  };
}
