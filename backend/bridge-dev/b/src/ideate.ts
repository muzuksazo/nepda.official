// B 훅 아이디어 단계: 앵커 → 마인드맵 → 단어 채점 → 인접 유사도 → 경로 탐색.
// video_test/pipeline/scripts/ideate.mjs(마인드맵 + 단어 채점)를 옮기고,
// 스킬 초안 2단계의 4~5번(브리지 경로 탐색)을 코드로 추가했다.
// 유사도는 임베딩이 아니라 Claude가 같은 기준표로 한꺼번에 매긴 추정치다.
import { generateText, Output, type LanguageModel } from "ai";
import { z } from "zod";
import { priceOf, type StepUsage } from "./cost.js";
import type { WorkerInput } from "./schema.js";

// 시작은 "지식 설명"(주어 + 사실 + 숫자)으로 연다. 분야별 관점 + 브리지용 사용 상황 관점.
export const LENSES = [
  { id: "nature", label: "자연", hint: "동물·식물 생태, 우주·천문, 지구·날씨·지리" },
  { id: "human", label: "사람", hint: "인체·생리, 심리·행동, 언어·어원" },
  { id: "math", label: "수와 모양", hint: "수학·기하, 통계·확률, 단위의 유래" },
  { id: "made", label: "만든 것", hint: "건축·공학, 발명·기술, 색채·디자인" },
  { id: "life", label: "삶", hint: "음식 과학, 스포츠 과학, 세계 풍습, 음악·소리" },
  { id: "record", label: "기록", hint: "역사 속 인물·사건, 세계 기록" },
  { id: "situation", label: "사용 상황", hint: "언제/어디서/누가 쓰는지 (브리지용)" },
] as const;

export const SIM_MIN = 0.4;
export const SIM_MAX = 0.6;
export const ADJ_MIN = 0.7;
/** 시작 단어는 제품 용도 영역과 이 값 이하로 떨어져 있어야 한다. */
export const USAGE_MAX_START = 0.35;
// 작은 검색: 단어 약 40개, 채점은 나눠서 동시에, 쌍은 약 40개
const TOP_STARTS = 4;
const TOP_BRIDGES = 8;
const SCORE_CHUNK = 20;

export interface ScoredWord {
  word: string;
  lens: string;
  branch: string;
  info: number;
  sim: number;
  /** 제품 용도 영역(usage_domains)과의 유사도 */
  usage: number;
}

export interface PathCandidate {
  start: ScoredWord;
  bridges: ScoredWord[];
  adjacent: number[];
  adjMin: number;
  score: number;
}

export interface IdeationResult {
  anchor: string;
  usageDomains: string[];
  anchorFact: string;
  numberHint: string;
  words: ScoredWord[];
  pairs: { a: string; b: string; sim: number }[];
  paths: PathCandidate[];
}

const MindmapSchema = z.object({
  anchor: z.string().describe("반전 앵커: 제품 핵심 기능 하나 + 숫자 하나, 한 줄 25자 안팎"),
  usage_domains: z.array(z.string()).describe("제품의 용도 영역 3~6개: 언제·무엇을 하려고 쓰는지(주제와 단위)"),
  anchor_fact: z.string().describe("앵커의 근거가 된 verified_facts 문장 그대로"),
  number_hint: z.string().describe("경로에 이어질 숫자 실 후보(예: 도(°), 분, 개수)"),
  maps: z.array(
    z.object({
      lens: z.string(),
      branches: z.array(z.object({ name: z.string(), words: z.array(z.string()) })),
    })
  ),
});

const ScoreSchema = z.object({
  scores: z.array(z.object({ word: z.string(), info: z.number(), sim: z.number(), usage: z.number() })),
});

const PairSchema = z.object({
  pairs: z.array(z.object({ a: z.string(), b: z.string(), sim: z.number() })),
});

const SIM_SCALE = `유사도 기준표 (0~1, 소수 둘째 자리):
- 0.9 이상: 앵커와 사실상 같은 말
- 0.7~0.9: 바로 이어지는 개념. 한 문장으로 자연스럽게 넘어간다
- 0.4~0.6: 절반쯤 어긋남. "이게 왜 나오지?" 싶은데 설명하면 납득된다
- 0.3 미만: 거의 무관
주의: 생김새·형태·단위가 앵커와 같으면(예: 부채꼴 면적 앵커에 피자 조각) 주제가 달라도 0.6 이상으로 매긴다. 모든 단어에 같은 기준을 일관되게 적용한다.`;

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

const pairKey = (a: string, b: string) => (a < b ? `${a}\u0000${b}` : `${b}\u0000${a}`);

/** 순수 함수: 채점된 단어와 인접 유사도로 [시작 → 브리지 1~2] 경로를 찾는다. */
export function searchPaths(
  words: ScoredWord[],
  pairSim: Map<string, number>,
  opts: { excludeStarts?: string[]; limit?: number } = {}
): PathCandidate[] {
  const exclude = new Set(opts.excludeStarts ?? []);
  const adj = (a: ScoredWord, b: ScoredWord) => pairSim.get(pairKey(a.word, b.word));
  const starts = words.filter(
    (w) => w.sim >= SIM_MIN && w.sim <= SIM_MAX && w.usage <= USAGE_MAX_START && !exclude.has(w.word)
  );
  const bridges = words.filter((w) => w.sim > SIM_MIN && w.sim < 0.95);
  const out: PathCandidate[] = [];

  const push = (start: ScoredWord, chain: ScoredWord[]) => {
    const nodes = [start, ...chain];
    const adjacent: number[] = [];
    for (let i = 1; i < nodes.length; i++) {
      const s = adj(nodes[i - 1], nodes[i]);
      if (s === undefined || s < ADJ_MIN || nodes[i].sim <= nodes[i - 1].sim) return;
      adjacent.push(s);
    }
    const last = nodes[nodes.length - 1];
    if (last.sim < ADJ_MIN) return; // 마지막 브리지에서 앵커로 바로 넘어갈 수 있어야 한다
    const adjMin = Math.min(...adjacent);
    const score = start.info * adjMin * (1 - start.sim);
    out.push({ start, bridges: chain, adjacent, adjMin, score: Math.round(score * 1000) / 1000 });
  };

  for (const s of starts)
    for (const b1 of bridges) {
      if (b1.word === s.word) continue;
      push(s, [b1]);
      for (const b2 of bridges) if (b2.word !== b1.word && b2.word !== s.word) push(s, [b1, b2]);
    }

  out.sort((x, y) => y.score - x.score);
  return out.slice(0, opts.limit ?? 20);
}

/** 시작 단어가 서로 다른 경로를 n개 고른다. */
export function pickDistinct(paths: PathCandidate[], n: number): PathCandidate[] {
  const used = new Set<string>();
  const picked: PathCandidate[] = [];
  for (const p of paths) {
    if (used.has(p.start.word)) continue;
    used.add(p.start.word);
    picked.push(p);
    if (picked.length === n) break;
  }
  return picked;
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

  // 1) 앵커 + 마인드맵
  log("[B 아이디어] 1/3 앵커와 마인드맵");
  const mm = await call(
    model,
    modelId,
    "아이디어: 앵커·마인드맵",
    MindmapSchema,
    `${product}

1. verified_facts에서 반전 앵커 하나를 고르세요. 앵커 = 제품 핵심 기능 하나 + 숫자 하나, 한 줄 25자 안팎. 특징을 여러 개 엮지 마세요.
2. 제품의 용도 영역(usage_domains)을 3~6개 적으세요. 이 제품을 언제·무엇을 하려고 쓰는지, 그 주제와 단위입니다.
   예: 시간 관리 제품 → 시간, 집중, 공부, 휴식 주기, 분·시간 단위, 시계·시간 측정 도구의 역사 / 주방 가전 → 요리, 음식 온도, 끓는점, 조리 도구의 역사
   제품군의 역사·옛 형태·발명가, 그 용도를 위한 기법의 유래·창시자도 용도 영역에 넣으세요.
3. 아래 관점마다 마인드맵을 만드세요. 관점마다 가지 2개, 가지마다 단어 3개.
   단어는 "주어 + 사실 + 숫자"를 담은 짧은 명사구로, 그대로 "<주어>는 ~했습니다." 문장이 될 수 있게 쓰세요(예: "뉴턴 프리즘 7색", "꿀벌 8자 춤 각도").
   제품명과 제품군 어휘(${p.name}의 일반 명칭)는 단어로 쓰지 마세요. 뒤로 갈수록 제품과 먼 연상을 섞으세요.
   situation 이외 관점의 단어는 용도 영역 밖에서 고르되, 앵커와 모양·단위·움직임(원, 각도, 면적, 비율, 줄어듦 등)으로 이어질 수 있는 것을 우선하세요.
관점: ${LENSES.map((l) => `${l.id}(${l.label}: ${l.hint})`).join(" / ")}`,
    track
  );

  const seen = new Set<string>();
  const flat: { word: string; lens: string; branch: string }[] = [];
  for (const m of mm.maps)
    for (const b of m.branches)
      for (const w of b.words)
        if (!seen.has(w)) {
          seen.add(w);
          flat.push({ word: w, lens: m.lens, branch: b.name });
        }

  // 2) 단어 채점: info + 앵커 유사도 + 용도 영역 (SCORE_CHUNK개씩 동시에)
  log(`[B 아이디어] 2/3 단어 ${flat.length}개 채점`);
  const words: ScoredWord[] = [];
  const chunks: (typeof flat)[] = [];
  for (let i = 0; i < flat.length; i += SCORE_CHUNK) chunks.push(flat.slice(i, i + SCORE_CHUNK));
  const scoredChunks = await Promise.all(chunks.map(async (chunk, ci) => {
    const { scores } = await call(
      model,
      modelId,
      `아이디어: 단어 채점 ${ci + 1}`,
      ScoreSchema,
      `앵커: ${mm.anchor}

각 단어를 0~1로 채점하세요.
- info: 이 단어로 "알고 보면 놀라운 사실 / 잘못 알려진 상식 / 의외의 통계"를 말할 수 있는 정도. 단순 계산이나 누구나 아는 사실은 0.3 이하.
- sim: 단어와 앵커의 의미 유사도.
- usage: 단어가 제품의 용도 영역과 얼마나 가까운지. 용도 영역의 주제나 단위를 다루면 0.6 이상, 전혀 다른 영역이면 0.2 이하.
  아래도 모두 용도 영역입니다(0.6 이상):
  · 제품군의 역사·옛 형태·발명가·기원 (같은 기능을 하던 옛 물건, 그 물건을 만든 사람)
  · 그 용도를 위한 기법·방법론의 유래와 창시자
  · 그 용도의 대표 단위나 측정 도구 이야기
  예: 시간 관리 제품 → 해시계·물시계·모래시계·시계의 역사, 시간 관리법의 창시자 / 주방 가전 → 주전자·가마솥의 역사, 조리법의 기원
${SIM_SCALE}

용도 영역: ${mm.usage_domains.join(", ")}

단어: ${JSON.stringify(chunk.map((c) => c.word))}`,
      track,
      "idea-score"
    );
    return { chunk, scores };
  }));
  for (const { chunk, scores } of scoredChunks) {
    const byWord = new Map(scores.map((s) => [s.word, s]));
    for (const c of chunk) {
      const s = byWord.get(c.word);
      if (s) words.push({ ...c, info: s.info, sim: s.sim, usage: s.usage });
    }
  }

  // 3) 후보끼리 인접 유사도
  const exclude = input.previous_scenarios
    .map((s) => (s as { ad_spec?: { bridge_path?: { word?: string }[] } })?.ad_spec?.bridge_path?.[0]?.word)
    .filter((w): w is string => !!w);
  const starts = words
    .filter((w) => w.sim >= SIM_MIN && w.sim <= SIM_MAX && w.usage <= USAGE_MAX_START && !exclude.includes(w.word))
    .sort((a, b) => b.info - a.info)
    .slice(0, TOP_STARTS);
  const bridges = words
    .filter((w) => w.sim > 0.5 && w.sim < 0.95)
    .sort((a, b) => b.sim * 0.5 + b.info * 0.5 - (a.sim * 0.5 + a.info * 0.5))
    .slice(0, TOP_BRIDGES);
  const pool = [...new Map([...starts, ...bridges].map((w) => [w.word, w])).values()];
  const pairList: [string, string][] = [];
  for (const a of pool)
    for (const b of pool)
      if (a.word !== b.word && a.sim < b.sim && !starts.some((s) => s.word === b.word)) pairList.push([a.word, b.word]);

  log(`[B 아이디어] 3/3 인접 유사도 ${pairList.length}쌍`);
  const pairs: { a: string; b: string; sim: number }[] = [];
  if (pairList.length) {
    const res = await call(
      model,
      modelId,
      "아이디어: 인접 유사도",
      PairSchema,
      `두 단어를 영상에서 앞뒤 장면으로 이을 때 얼마나 자연스럽게 넘어가는지, 두 단어 사이의 유사도를 0~1로 매기세요.
${SIM_SCALE}

쌍(a, b): ${JSON.stringify(pairList)}`,
      track
    );
    pairs.push(...res.pairs);
  }
  const pairSim = new Map(pairs.map((x) => [pairKey(x.a, x.b), x.sim]));
  const paths = searchPaths(words, pairSim, { excludeStarts: exclude });
  log(`[B 아이디어] 경로 후보 ${paths.length}개`);

  return { anchor: mm.anchor, usageDomains: mm.usage_domains, anchorFact: mm.anchor_fact, numberHint: mm.number_hint, words, pairs, paths };
}
