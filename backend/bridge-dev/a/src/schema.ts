import { z } from "zod";

/** 백엔드가 A 작업자에게 넘기는 공통 제품 정보 (a/examples/01_worker-input.scenarios.json). */
export const ProductInfoSchema = z.object({
  name: z.string().min(1),
  category: z.string().optional(),
  verified_facts: z.array(z.string()).default([]),
  price_or_offer: z.string().optional(),
  target_audience: z.string().optional(),
});
export type ProductInfo = z.infer<typeof ProductInfoSchema>;

export const WorkerInputSchema = z.object({
  hook_type: z.literal("A"),
  project_id: z.string().min(1),
  round: z.number().int().min(1),
  count: z.number().int().min(1).max(5),
  product_info: ProductInfoSchema,
  previous_scenarios: z.array(z.any()).default([]),
});
export type WorkerInput = z.infer<typeof WorkerInputSchema>;

/** 14종 Track A 무맥락 장르 · 리텐션 원형 */
export const AGenreArchetypeSchema = z.enum([
  "extreme_physics_experiment",
  "courtroom_trial",
  "noir_interrogation",
  "romance_breakup",
  "historical_drama",
  "sports_var",
  "sci_fi_contact",
  "audition_judge",
  "horror_mystery",
  "mock_documentary",
  "absurd_skit",
  "brainrot_hypnosis",
  "deadpan_rhythmic_loop",
  "sensory_sync_loop",
]);
export type AGenreArchetype = z.infer<typeof AGenreArchetypeSchema>;

/** Stage 1 (abstract): 제품/카테고리를 물리·인지 법칙 1줄과 금칙어로 추상화 */
export const AbstractLawSchema = z.object({
  abstract_law: z
    .string()
    .describe("제품명·카테고리 단어 0%로 환원한 순수 물리/심리/인과 법칙 1줄"),
  core_verified_fact: z
    .string()
    .describe("product_info.verified_facts 중 가장 강력한 시각 증명 1개 원문"),
  product_taboo_keywords: z
    .array(z.string())
    .min(2)
    .describe("반전 전 0% 금지해야 할 제품명·부품·성분 키워드"),
  category_taboo_keywords: z
    .array(z.string())
    .min(2)
    .describe("반전 전 0% 금지해야 할 사용 공간·문제 상황·카테고리 단서 어휘"),
  reference_surface_taboo: z
    .array(z.string())
    .default([])
    .describe("유행/예시 레퍼런스에서 표면 복제를 막기 위한 고유명사 금칙어"),
});
export type AbstractLaw = z.infer<typeof AbstractLawSchema>;

/** Stage 2 (blind ideate): 제품 정보 없이 무맥락 훅 비트만 생성 */
export const BeatSchema = z.object({
  order: z.number().int().min(1),
  role: z.string(),
  duration_sec: z.number().positive(),
  visual: z.string(),
  narration: z.string(),
  caption: z.string(),
});
export type Beat = z.infer<typeof BeatSchema>;

export const BlindHookDraftSchema = z.object({
  hook_title: z.string().min(1),
  a_genre_archetype: AGenreArchetypeSchema,
  visual_style: z.string().default("blender_3d_physics"),
  silence_gap_sec: z.number().min(0.18).max(0.32),
  pre_twist_beats: z
    .array(BeatSchema)
    .min(2)
    .max(4)
    .describe("어긋난 시작 → 빌드업 → 패턴 인터럽트(무음 정적)까지 2~4비트. 마지막 제품 착지는 제외"),
});
export type BlindHookDraft = z.infer<typeof BlindHookDraftSchema>;

/** Stage 3 (bridge): 무맥락 훅 뒤에 담백한 실물 반전 착지 1비트 결합 */
export const BridgePayoffSchema = z.object({
  payoff_beat: z.object({
    duration_sec: z.number().positive(),
    visual: z.string().describe("실제 제품 동작 증명 컷 (예: 90도 기울여도 안 흐르는 초록 고체 젤)"),
    narration: z.string().describe("오프닝 법칙과 연결되는 담백한 전환 + verified_facts 기반 1문장"),
    caption: z.string().describe("2줄 이하, 줄당 22자 이내, 이모지 금지"),
  }),
  replacement_test_note: z
    .string()
    .describe("왜 0~10초 훅을 다른 제품 광고에도 이식할 수 있는지 교체 테스트 근거 1줄"),
  closing_callback: z
    .string()
    .optional()
    .describe("오프닝 무맥락 소재를 가볍게 회수하는 댓글 유도 1줄"),
});
export type BridgePayoff = z.infer<typeof BridgePayoffSchema>;

export const AAdSpecSchema = z.object({
  track_archetype: z.literal("A_bgrade_reversal"),
  a_genre_archetype: AGenreArchetypeSchema,
  abstract_law: z.string().optional(),
  visual_style: z.string().default("blender_clay_diorama"),
  product_taboo_keywords: z.array(z.string()).default([]),
  category_taboo_keywords: z.array(z.string()).default([]),
  reference_surface_taboo: z.array(z.string()).default([]),
  silence_gap_sec: z.number().positive(),
  pre_twist_ratio: z.number().min(0).max(1),
  payoff_ratio: z.number().min(0).max(1),
});
export type AAdSpec = z.infer<typeof AAdSpecSchema>;

export const DraftScenarioSchema = z.object({
  hook_title: z.string(),
  hook_duration_sec: z.number().positive(),
  body_duration_sec: z.number().nonnegative(),
  replacement_test_note: z.string(),
  beats: z.array(BeatSchema),
  ad_spec: AAdSpecSchema,
});
export type DraftScenario = z.infer<typeof DraftScenarioSchema>;

export type ScenarioItem = DraftScenario & {
  scenario_id: string;
  round: number;
  type: "A";
};

export const ScenarioItemSchema = DraftScenarioSchema.extend({
  scenario_id: z.string(),
  round: z.number().int().min(1),
  type: z.literal("A"),
});

export const ScenariosResponseSchema = z.object({
  project_id: z.string(),
  status: z.literal("SCENARIOS_READY"),
  round: z.number().int().min(1),
  scenarios: z.array(ScenarioItemSchema),
});
export type ScenariosResponse = z.infer<typeof ScenariosResponseSchema>;
