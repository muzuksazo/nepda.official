import { randomUUID } from "node:crypto";
import { anthropic } from "@ai-sdk/anthropic";
import type { LanguageModel } from "ai";
import { extractAbstractLaw } from "./abstract.js";
import { pickUnusedArchetypes } from "./archetypes.js";
import { generateBridgeAndAssemble } from "./bridge.js";
import { checkAgainstPrevious, checkScenario, type CheckResult } from "./check.js";
import { generateBlindHook } from "./ideate.js";
import type { DraftScenario, ScenarioItem, ScenariosResponse, WorkerInput } from "./schema.js";

export const DEFAULT_MODEL = "claude-opus-5-5";

export interface GenerateOptions {
  modelId?: string;
  ideaModelId?: string;
  model?: LanguageModel;
  maxAttempts?: number;
  log?: (msg: string) => void;
}

export interface RunRecord {
  response: ScenariosResponse;
  checks: (CheckResult & { scenario_id: string })[];
  attempts: number;
  modelId: string;
  ideaModelId: string;
  createdAt: string;
}

/**
 * Track A 4단계 블라인드 파이프라인:
 * 1) extractAbstractLaw  : 제품 -> 추상 법칙 1줄 + 금칙어 목록
 * 2) pickUnusedArchetypes: 이전 회차와 겹치지 않는 장르 선택
 * 3) generateBlindHook   : ★ 제품 정보 없이 순수 법칙 + 장르만으로 무맥락 훅 발명
 * 4) generateBridge + checkScenario : 실물 착지 결합 후 Double-Zero 검문 (위반 시 자동 재시도)
 */
export async function generateScenarios(input: WorkerInput, opts: GenerateOptions = {}): Promise<RunRecord> {
  const modelId = opts.modelId || process.env.A_MODEL?.trim() || DEFAULT_MODEL;
  const ideaModelId = opts.ideaModelId || process.env.A_IDEA_MODEL?.trim() || modelId;
  const model = opts.model ?? anthropic(modelId);
  const ideaModel = opts.model ?? anthropic(ideaModelId);
  const maxAttempts = Math.max(1, opts.maxAttempts ?? 2);
  const log = opts.log ?? (() => {});

  log(`[A] 1단계: 제품 추상 법칙 & 금칙어 추출 (${ideaModelId})`);
  const law = await extractAbstractLaw(input.product_info, ideaModel);
  // Stage 2 블라인드 훅 생성에는 원본 제품명 토큰을 넘기지 않고(Stage 4 checkScenario에서 별도 검사),
  // 추상화 단계에서 도출된 금칙어만 전달한다.
  const tabooAll = [
    ...new Set([
      ...law.product_taboo_keywords,
      ...law.category_taboo_keywords,
      ...law.reference_surface_taboo,
    ]),
  ];

  const chosenArchetypes = pickUnusedArchetypes(input.previous_scenarios, input.count);
  const scenarios: ScenarioItem[] = [];
  const checks: (CheckResult & { scenario_id: string })[] = [];
  let totalAttempts = 0;

  for (let i = 0; i < input.count; i++) {
    const arch = chosenArchetypes[i % chosenArchetypes.length];
    let feedback: string | undefined;
    let bestDraft: DraftScenario | null = null;
    let bestCheck: CheckResult = { errors: [], warnings: [] };
    let attempts = 0;

    while (attempts < maxAttempts) {
      attempts++;
      totalAttempts++;
      log(`[A] 시나리오 ${i + 1}/${input.count} (${arch.id}) 시도 ${attempts}/${maxAttempts}`);
      const blindHook = await generateBlindHook(law.abstract_law, arch, tabooAll, ideaModel, feedback);
      const draft = await generateBridgeAndAssemble(blindHook, input.product_info, law, model, feedback);
      const res = checkScenario(draft, input.product_info);
      const dupErrs = checkAgainstPrevious(draft, [...input.previous_scenarios, ...scenarios]);
      res.errors.push(...dupErrs);

      bestDraft = draft;
      bestCheck = res;
      if (res.errors.length === 0) break;
      feedback = res.errors.map((e) => `- ${e}`).join("\n");
      log(`[A] 규칙 위반 감지 -> 재시도:\n${feedback}`);
    }

    if (!bestDraft) {
      throw new Error(`시나리오 ${i + 1} 생성 실패`);
    }
    const scenarioId = `sc_${randomUUID().replace(/-/g, "").slice(0, 10)}`;
    scenarios.push({
      scenario_id: scenarioId,
      round: input.round,
      type: "A",
      ...bestDraft,
    });
    checks.push({ ...bestCheck, scenario_id: scenarioId });
  }

  return {
    response: {
      project_id: input.project_id,
      status: "SCENARIOS_READY",
      round: input.round,
      scenarios,
    },
    checks,
    attempts: totalAttempts,
    modelId,
    ideaModelId,
    createdAt: new Date().toISOString(),
  };
}
