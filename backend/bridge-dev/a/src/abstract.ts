import { generateText, Output, type LanguageModel } from "ai";
import { AbstractLawSchema, type AbstractLaw, type ProductInfo } from "./schema.js";

const ABSTRACT_SYSTEM_PROMPT = `당신은 숏폼 광고 Track A(무맥락 반전) 아키텍트입니다.
제품 정보와 검증된 사실(verified_facts)을 읽고, 제품·카테고리 단서를 100% 제거한 '순수 물리/인지/인과 법칙' 1줄과 금칙어 목록을 뽑아냅니다.
예: "원인을 안 잡고 겉만 덮으면 내부 압력이 쌓여 한 번에 터진다", "중력에 저항해도 흘러내리지 않는 상태".
금칙어에는 제품명, 부품명, 성분명, 사용 공간(현관·욕실·공부방 등), 증상(냄새·악취·두통·집중 등)을 빠짐없이 넣으세요.`;

export function buildAbstractPrompt(product: ProductInfo): string {
  const facts = product.verified_facts.length
    ? product.verified_facts.map((f, i) => `- [F${String(i + 1).padStart(2, "0")}] ${f}`).join("\n")
    : "- (제공된 verified_facts 없음)";
  return [
    `제품명: ${product.name}`,
    product.category ? `카테고리: ${product.category}` : "",
    product.target_audience ? `타겟: ${product.target_audience}` : "",
    "",
    "검증된 사실(verified_facts):",
    facts,
    "",
    "요청:",
    "1) 가장 강한 시각적 사실 1개를 core_verified_fact로 고르고,",
    "2) 제품/카테고리/생활공간 어휘가 0% 포함된 순수 물리·심리 법칙 1줄(abstract_law)을 작성하고,",
    "3) product_taboo_keywords, category_taboo_keywords, reference_surface_taboo를 촘촘히 뽑으세요.",
  ]
    .filter(Boolean)
    .join("\n");
}

export async function extractAbstractLaw(product: ProductInfo, model: LanguageModel): Promise<AbstractLaw> {
  const result = await generateText({
    model,
    system: ABSTRACT_SYSTEM_PROMPT,
    prompt: buildAbstractPrompt(product),
    output: Output.object({ schema: AbstractLawSchema }),
    maxOutputTokens: 4000,
  });
  return result.output;
}
