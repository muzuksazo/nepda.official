import { randomUUID } from "node:crypto";
import { generateText, Output, type LanguageModel } from "ai";
import { anthropic } from "@ai-sdk/anthropic";
import { checkAgainstPrevious, checkScenario, type CheckResult } from "./check.js";
import { priceOf, totals, type StepUsage } from "./cost.js";
import { ideate, pickDistinct, type IdeationResult, type PathCandidate } from "./ideate.js";
import { buildUserPrompt, SYSTEM_PROMPT, type PathBrief } from "./prompt.js";
import {
  GenResponseSchema,
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
  chosenPaths: PathCandidate[];
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

/** 경로 값은 모델 자기 평가가 아니라 검색 결과로 덮어쓴다. */
function applyPath(d: DraftScenario, p: PathCandidate | undefined, anchor: string | undefined): DraftScenario {
  if (!p) return d;
  const nodes = [p.start, ...p.bridges];
  return {
    ...d,
    ad_spec: {
      ...d.ad_spec,
      anchor: anchor ?? d.ad_spec.anchor,
      hook_similarity_score: p.start.sim,
      bridge_path: nodes.map((n) => ({ word: n.word, sim_to_anchor: n.sim })),
      adjacent_min_sim: p.adjMin,
    },
  };
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
  let chosen: PathCandidate[] = [];
  if (opts.ideate !== false) {
    ideation = await ideate(input, ideaModel, ideaModelId, track, { log });
    chosen = pickDistinct(ideation.paths, input.count);
    if (chosen.length < input.count)
      log(`[B] 조건(시작 0.40~0.60·용도 영역 0.40 이하, 인접 0.70 이상)을 만족하는 경로 ${chosen.length}개뿐. 나머지는 모델이 직접 고름`);
  }
  const brief: PathBrief | undefined = ideation
    ? { anchor: ideation.anchor, anchorFact: ideation.anchorFact, usageDomains: ideation.usageDomains, paths: chosen }
    : undefined;

  // 2) 시나리오 + 3D 장면 생성
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
      output: Output.object({ schema: GenResponseSchema }),
      maxOutputTokens: 32000,
      providerOptions: { anthropic: { effort: "high" } },
    });
    const inT = result.usage?.inputTokens ?? 0;
    const outT = result.usage?.outputTokens ?? 0;
    steps.push({
      step: `시나리오·3D 장면 ${attempts}차`,
      model: modelId,
      inputTokens: inT,
      outputTokens: outT,
      costUsd: priceOf(modelId, inT, outT),
      ms: Math.round(performance.now() - t0),
    });

    drafts = result.output.scenarios
      .slice(0, input.count)
      .map((d, i) => applyPath(d, chosen[i], ideation?.anchor));
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
    chosenPaths: chosen,
    steps,
    total: totals(steps),
    createdAt: new Date().toISOString(),
  };
}
