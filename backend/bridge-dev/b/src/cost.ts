// Claude API 표준 요금 (USD / 100만 토큰, 2026-11 기준, 캐시·배치 할인 미반영).
// 실제 청구액은 Console의 Usage에서 확인한다.
export const PRICES: Record<string, { input: number; output: number }> = {
  "claude-fable-5-2": { input: 8, output: 40 },
  "claude-opus-5-5": { input: 4, output: 20 },
  "claude-opus-5": { input: 5, output: 25 },
  "claude-sonnet-5-5": { input: 2, output: 10 },
  "claude-sonnet-5": { input: 2, output: 10 },
  "claude-haiku-5-5": { input: 0.1, output: 0.5 },
  // Gemini (ai.google.dev/gemini-api/docs/pricing, 2026-11): 3.8 Flash 도입가 2026-12-31 까지, 2027-01-01 부터 $1.50/$7.50. 생각 토큰은 출력 요금
  "gemini-3.8-flash": { input: 0.75, output: 3.75 },
  "gemini-3.5-flash": { input: 1.5, output: 9 },
};

export interface StepUsage {
  step: string;
  model: string;
  inputTokens: number;
  outputTokens: number;
  costUsd: number | null;
  ms: number;
  /** 같은 group 끼리는 동시에 실행됨 → 소요 시간 합계에는 가장 긴 것만 더한다 */
  group?: string;
}

export function priceOf(model: string, inputTokens: number, outputTokens: number): number | null {
  const p = PRICES[model];
  if (!p) return null;
  return (inputTokens * p.input + outputTokens * p.output) / 1_000_000;
}

export function totals(steps: StepUsage[]) {
  const t = { inputTokens: 0, outputTokens: 0, costUsd: 0, ms: 0, unknownPrice: false };
  const groupMax = new Map<string, number>();
  for (const s of steps) {
    t.inputTokens += s.inputTokens;
    t.outputTokens += s.outputTokens;
    if (s.group) groupMax.set(s.group, Math.max(groupMax.get(s.group) ?? 0, s.ms));
    else t.ms += s.ms;
    if (s.costUsd === null) t.unknownPrice = true;
    else t.costUsd += s.costUsd;
  }
  for (const ms of groupMax.values()) t.ms += ms;
  return t;
}

/** B_USD_KRW 환경변수가 있을 때만 원화 환산(환율을 지어내지 않는다). */
export function krw(usd: number): number | null {
  const rate = Number(process.env.B_USD_KRW);
  return Number.isFinite(rate) && rate > 0 ? Math.round(usd * rate) : null;
}
