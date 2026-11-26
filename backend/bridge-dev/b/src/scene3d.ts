// 장면별 3D 명세(scene3d)를 고른 시나리오에만 만든다. 컷 단계 직전에 호출.
// (시나리오 단계에서 3D 명세를 빼서 시나리오 생성을 빠르게 하기 위함)
import { llm, stepOptions } from "./llm.js";
import { generateText, Output, type LanguageModel } from "ai";
import { anthropic } from "@ai-sdk/anthropic";
import { z } from "zod";
import { checkScenario } from "./check.js";
import { priceOf, type StepUsage } from "./cost.js";
import { SCENE3D_PROMPT } from "./prompt.js";
import { catalogSummary, characterNames, searchAssets } from "./catalog.js";
import { Scene3DSchema, type ProductInfoSchema, type ScenarioItem } from "./schema.js";

const BatchSchema = z.object({
  beats: z.array(z.object({ order: z.number().int(), scene3d: Scene3DSchema })),
});

export async function addScene3d(
  scenarios: ScenarioItem[],
  product: z.infer<typeof ProductInfoSchema>,
  opts: { model?: LanguageModel; modelId?: string; maxAttempts?: number; log?: (m: string) => void } = {}
): Promise<{ scenarios: ScenarioItem[]; steps: StepUsage[] }> {
  const modelId = opts.modelId || process.env.B_SCENE_MODEL?.trim() || process.env.B_MODEL?.trim() || "claude-opus-5-5";
  const model = opts.model ?? llm(modelId);
  const maxAttempts = Math.max(1, opts.maxAttempts ?? 2);
  const steps: StepUsage[] = [];
  const out: ScenarioItem[] = [];

  for (const s of scenarios) {
    if (s.beats.every((b) => b.scene3d)) {
      out.push(s);
      continue;
    }
    opts.log?.(`[B 3D] ${s.scenario_id} 장면별 3D 명세`);
    let feedback = "";
    let next = s;
    for (let attempt = 1; attempt <= maxAttempts; attempt++) {
      const t0 = performance.now();
      const r = await generateText({
        model,
        system: SCENE3D_PROMPT,
        prompt:
          `제품 verified_facts:\n${product.verified_facts.map((f) => `- ${f}`).join("\n")}\n` +
          (product.model ? `제품 3D 모델 있음: 반전 장면은 이 모델(Product)을 씁니다. objects에 제품을 따로 만들지 않습니다.\n` : "") +
          `\n## 있는 에셋\n${catalogSummary()}\n\n` +
          `시나리오(JSON):\n${JSON.stringify({ hook_title: s.hook_title, beats: s.beats.map(({ scene3d: _x, ...b }) => b), anchor: s.ad_spec.anchor }, null, 1)}\n\n` +
          `모든 장면(order)마다 scene3d를 쓰세요. stage·assets(3~6개)는 모든 장면에, character는 사람이 나오는 이야기면 모든 장면에 채웁니다.${feedback ? `\n\n직전 결과의 규칙 위반(모두 고치세요):\n${feedback}` : ""}`,
        output: Output.object({ schema: BatchSchema }),
        maxOutputTokens: 16000,
        providerOptions: stepOptions("spec", "medium"),
      });
      const inT = r.usage?.inputTokens ?? 0, outT = r.usage?.outputTokens ?? 0;
      steps.push({ step: `컷: 3D 명세 ${attempt}차`, model: modelId, inputTokens: inT, outputTokens: outT, costUsd: priceOf(modelId, inT, outT), ms: Math.round(performance.now() - t0) });
      const byOrder = new Map(r.output.beats.map((b) => [b.order, b.scene3d]));
      next = { ...s, beats: s.beats.map((b) => ({ ...b, scene3d: byOrder.get(b.order) ?? b.scene3d })) };
      const errs = checkScenario(next, product).errors.filter((e) => /3D|움직임|오브젝트/.test(e));
      const missing = next.beats.filter((b) => !b.scene3d).map((b) => `장면 ${b.order} scene3d 없음`);
      const names = new Set(characterNames());
      for (const b of next.beats) {
        const sc = b.scene3d;
        if (!sc) continue;
        if (!sc.stage) missing.push(`장면 ${b.order} stage 없음`);
        if (!sc.assets?.length) missing.push(`장면 ${b.order} assets 없음 (3~6개)`);
        const visible = (sc.assets ?? []).reduce((n, a) => n + Math.max(1, a.count ?? 1), 0);
        if (!b.scene3d?.lid_open && visible < 6 && b.order !== Math.max(...next.beats.map((x) => x.order)))
          missing.push(`장면 ${b.order} 보이는 물체가 ${visible}개뿐 — 같은 물건 여러 개(count·pattern)나 받침 위 소품(on_query)으로 6개 이상`);
        for (const a of sc.assets ?? [])
          if (a.on_query && !(sc.assets ?? []).some((x, i) => i < (sc.assets ?? []).indexOf(a) && x.query.trim().toLowerCase() === a.on_query!.trim().toLowerCase()))
            missing.push(`장면 ${b.order} "${a.query}" 의 on_query "${a.on_query}" 는 앞에 나온 항목의 query 여야 함`);
        for (const a of sc.assets ?? []) if (!searchAssets(a.query, 1).length) missing.push(`장면 ${b.order} assets "${a.query}" 에 맞는 모델이 없음 — 있는 에셋 목록의 다른 영어 낱말로 바꾸거나 빼세요`);
        if (sc.character && !names.has(sc.character.model)) missing.push(`장면 ${b.order} character "${sc.character.model}" 는 목록에 없는 이름 — 목록의 이름 그대로 쓰세요`);
      }
      if (!errs.length && !missing.length) break;
      feedback = [...errs, ...missing].map((e) => `- ${e}`).join("\n");
    }
    out.push(next);
  }
  return { scenarios: out, steps };
}
