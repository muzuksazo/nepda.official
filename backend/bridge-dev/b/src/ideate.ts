// B 훅 아이디어 단계 (이야기 모드): 앵커·용도 영역 → 이야기 씨앗 마인드맵 → 씨앗 채점 → 씨앗 고르기.
// 훅은 "지식 이야기 하나"를 처음부터 끝까지 따라간다(장면마다 다른 사실을 늘어놓지 않음).
// 씨앗 = 누가(무엇이) 무엇을 했는지 + 숫자. 이야기의 발단은 앵커와 절반쯤 어긋나고(0.40~0.60),
// 이야기의 핵심 원리(결말)는 앵커와 모양·단위·움직임으로 이어져야 한다(link).
// 유사도는 임베딩이 아니라 Claude가 같은 기준표로 한꺼번에 매긴 추정치다.
import { generateText, Output, type LanguageModel } from "ai";
import { z } from "zod";
import { priceOf, type StepUsage } from "./cost.js";
import type { WorkerInput } from "./schema.js";

export const LENSES = [
  { id: "nature", label: "자연", hint: "동물·식물 생태, 우주·천문, 지구·날씨·지리" },
  { id: "human", label: "사람", hint: "인체·생리, 심리·행동, 언어·어원" },
  { id: "math", label: "수와 모양", hint: "수학·기하, 통계·확률, 단위의 유래" },
  { id: "made", label: "만든 것", hint: "건축·공학, 발명·기술, 색채·디자인" },
  { id: "life", label: "삶", hint: "음식 과학, 스포츠 과학, 세계 풍습, 음악·소리" },
  { id: "record", label: "기록", hint: "역사 속 인물·사건, 세계 기록" },
] as const;

export const SIM_MIN = 0.4;
export const SIM_MAX = 0.6;
/** 발단은 제품 용도 영역과 이 값 이하로 떨어져 있어야 한다 */
export const USAGE_MAX_START = 0.35;
/** 이야기의 결말이 앵커로 이어지는 정도의 최소값 */
export const LINK_MIN = 0.6;
const SCORE_CHUNK = 9; // 채점은 이 크기로 나눠 동시에 (씨앗 18개 → 2번)

export interface StorySeed {
  /** 씨앗 한 줄: 누가 무엇을 했나 + 숫자 */
  word: string;
  /** 이야기 흐름 한 줄: 발단 → 전개 → 핵심 원리 */
  arc: string;
  lens: string;
  info: number;
  /** 발단과 앵커의 유사도 */
  sim: number;
  /** 제품 용도 영역과의 유사도 */
  usage: number;
  /** 이야기의 핵심 원리가 앵커로 이어지는 정도 */
  link: number;
  score: number;
}

export interface IdeationResult {
  anchor: string;
  usageDomains: string[];
  anchorFact: string;
  numberHint: string;
  seeds: StorySeed[];
}

const MindmapSchema = z.object({
  anchor: z.string().describe("반전 앵커: 제품 핵심 기능 하나 + 숫자 하나, 한 줄 25자 안팎"),
  usage_domains: z.array(z.string()).describe("제품의 용도 영역 3~6개: 언제·무엇을 하려고 쓰는지(주제와 단위)"),
  anchor_fact: z.string().describe("앵커의 근거가 된 verified_facts 문장 그대로"),
  number_hint: z.string().describe("이야기에 이어질 숫자 실 후보(예: 도(°), 분, 개수)"),
  seeds: z.array(
    z.object({
      lens: z.string(),
      word: z.string().describe("씨앗 한 줄: 누가(무엇이) 무엇을 했나 + 숫자. 예: '나이팅게일 1858년 사망 원인을 부채꼴 면적으로 그림'"),
      arc: z.string().describe("이야기 흐름 한 줄: 발단 → 전개(문제·발견) → 핵심 원리"),
    })
  ),
});

const ScoreSchema = z.object({
  scores: z.array(z.object({ word: z.string(), info: z.number(), sim: z.number(), usage: z.number(), link: z.number() })),
});

const SIM_SCALE = `유사도 기준표 (0~1, 소수 둘째 자리):
- 0.9 이상: 앵커와 사실상 같은 말
- 0.7~0.9: 바로 이어지는 개념. 한 문장으로 자연스럽게 넘어간다
- 0.4~0.6: 절반쯤 어긋남. "이게 왜 나오지?" 싶은데 설명하면 납득된다
- 0.3 미만: 거의 무관
주의: 생김새·형태·단위가 앵커와 같으면(예: 부채꼴 면적 앵커에 피자 조각) 주제가 달라도 0.6 이상으로 매긴다. 모든 씨앗에 같은 기준을 일관되게 적용한다.`;

export type Track = (s: StepUsage) => void;

async function call<T extends z.ZodType>(
  model: LanguageModel,
  modelId: string,
  step: string,
  schema: T,
  prompt: string,
  track: Track,
  group?: string
): Promise<z.infer<T>> {
  const t0 = performance.now();
  const r = await generateText({
    model,
    prompt,
    output: Output.object({ schema }),
    maxOutputTokens: 16000,
    providerOptions: { anthropic: { effort: "medium" } },
  });
  const inputTokens = r.usage?.inputTokens ?? 0;
  const outputTokens = r.usage?.outputTokens ?? 0;
  track({ step, model: modelId, inputTokens, outputTokens, costUsd: priceOf(modelId, inputTokens, outputTokens), ms: Math.round(performance.now() - t0), group });
  return r.output as z.infer<T>;
}

/** 순수 함수: 조건을 만족하는 씨앗을 점수순으로. 점수 = info × link × (1 − 발단 유사도) */
export function rankSeeds(seeds: StorySeed[], opts: { exclude?: string[] } = {}): StorySeed[] {
  const ex = new Set(opts.exclude ?? []);
  return seeds
    .filter((s) => s.sim >= SIM_MIN && s.sim <= SIM_MAX && s.usage <= USAGE_MAX_START && s.link >= LINK_MIN && !ex.has(s.word))
    .sort((a, b) => b.score - a.score);
}

export async function ideate(
  input: WorkerInput,
  model: LanguageModel,
  modelId: string,
  track: Track,
  opts: { log?: (m: string) => void } = {}
): Promise<IdeationResult> {
  const log = opts.log ?? (() => {});
  const p = input.product_info;
  const product = `제품: ${p.name}\nverified_facts:\n${p.verified_facts.map((f) => `- ${f}`).join("\n")}`;

  // 1) 앵커 + 용도 영역 + 이야기 씨앗
  log("[B 아이디어] 1/2 앵커와 이야기 씨앗");
  const mm = await call(
    model,
    modelId,
    "아이디어: 앵커·이야기 씨앗",
    MindmapSchema,
    `${product}

1. verified_facts에서 반전 앵커 하나를 고르세요. 앵커 = 제품 핵심 기능 하나 + 숫자 하나, 한 줄 25자 안팎. 특징을 여러 개 엮지 마세요.
2. 제품의 용도 영역(usage_domains)을 3~6개 적으세요. 이 제품을 언제·무엇을 하려고 쓰는지, 그 주제와 단위입니다.
   예: 시간 관리 제품 → 시간, 집중, 공부, 휴식 주기, 분·시간 단위, 시계·시간 측정 도구의 역사 / 주방 가전 → 요리, 음식 온도, 끓는점, 조리 도구의 역사
   제품군의 역사·옛 형태·발명가, 그 용도를 위한 기법의 유래·창시자도 용도 영역에 넣으세요.
3. 아래 관점마다 "지식 이야기 씨앗"을 3개씩 적으세요. word와 arc는 각각 한 줄, 40자 안팎으로 짧게 씁니다.
   - 씨앗 = 실제 인물·동물·장소·사건이 무엇을 했는지 하나의 이야기(word: 한 줄 + 숫자, arc: 발단 → 전개 → 핵심 원리 한 줄).
   - 15~20초 동안 그 이야기 하나만 따라가며 설명할 수 있어야 합니다. 서로 다른 사실 여러 개를 엮은 것은 씨앗이 아닙니다.
   - 이야기의 발단은 용도 영역 밖이어야 하고, 이야기의 핵심 원리(결말)는 앵커와 모양·단위·움직임(원, 각도, 면적, 비율, 줄어듦 등)으로 이어질 수 있어야 합니다.
   - 제품명과 제품군 어휘는 쓰지 마세요. 널리 알려져 출처를 댈 수 있는 이야기를 우선하세요.
관점: ${LENSES.map((l) => `${l.id}(${l.label}: ${l.hint})`).join(" / ")}`,
    track
  );

  const seen = new Set<string>();
  const flat = mm.seeds.filter((s) => (seen.has(s.word) ? false : (seen.add(s.word), true)));

  // 2) 씨앗 채점 (동시에)
  log(`[B 아이디어] 2/2 이야기 씨앗 ${flat.length}개 채점`);
  const chunks: (typeof flat)[] = [];
  for (let i = 0; i < flat.length; i += SCORE_CHUNK) chunks.push(flat.slice(i, i + SCORE_CHUNK));
  const scored = await Promise.all(
    chunks.map(async (chunk, ci) => {
      const { scores } = await call(
        model,
        modelId,
        `아이디어: 씨앗 채점 ${ci + 1}`,
        ScoreSchema,
        `앵커: ${mm.anchor}
용도 영역: ${mm.usage_domains.join(", ")}

각 이야기 씨앗을 0~1로 채점하세요.
- info: 이 이야기가 "알고 보면 놀라운 이야기"로서 얼마나 흥미로운지. 누구나 아는 이야기나 단순 계산은 0.3 이하.
- sim: 이야기의 **발단**(첫 장면)과 앵커의 의미 유사도.
- usage: 이야기의 발단이 제품 용도 영역과 얼마나 가까운지. 용도 영역의 주제·단위를 다루면 0.6 이상, 전혀 다른 영역이면 0.2 이하.
  제품군의 역사·옛 형태·발명가, 그 용도를 위한 기법의 유래·창시자도 용도 영역입니다(0.6 이상).
- link: 이야기의 **핵심 원리(결말)**가 앵커로 얼마나 자연스럽게 이어지는지. 모양·단위·움직임이 같으면 0.8 이상, 억지로 이어야 하면 0.4 이하.
${SIM_SCALE}

씨앗: ${JSON.stringify(chunk.map((c) => ({ word: c.word, arc: c.arc })))}`,
        track,
        "idea-score"
      );
      return { chunk, scores };
    })
  );

  const seeds: StorySeed[] = [];
  for (const { chunk, scores } of scored) {
    const byWord = new Map(scores.map((s) => [s.word, s]));
    for (const c of chunk) {
      const s = byWord.get(c.word);
      if (!s) continue;
      const score = Math.round(s.info * s.link * (1 - s.sim) * 1000) / 1000;
      seeds.push({ word: c.word, arc: c.arc, lens: c.lens, info: s.info, sim: s.sim, usage: s.usage, link: s.link, score });
    }
  }
  const ok = rankSeeds(seeds).length;
  log(`[B 아이디어] 조건을 만족하는 씨앗 ${ok}개 / ${seeds.length}개`);
  return { anchor: mm.anchor, usageDomains: mm.usage_domains, anchorFact: mm.anchor_fact, numberHint: mm.number_hint, seeds };
}
