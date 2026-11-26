import { z } from "zod";

/** 백엔드가 B 작업자에게 넘기는 입력 (b/examples/01_worker-input.scenarios.json). */
export const ProductInfoSchema = z.object({
  name: z.string().min(1),
  /** 나레이션에서 제품을 부르는 이름 (브랜드·제품 고유 이름을 한글로 읽은 것, 예: PIEV → 피에브). 없으면 모델이 짧은 이름을 정한다 */
  call_name: z.string().optional(),
  /** 반전 장면에 쓰는 직접 만든 제품 3D 모델 이름 (src/assets/products/<model>.tsx) */
  model: z.string().optional(),
  category: z.string().optional(),
  verified_facts: z.array(z.string()).default([]),
  price_or_offer: z.string().optional(),
  target_audience: z.string().optional(),
});

export const WorkerInputSchema = z.object({
  hook_type: z.literal("B"),
  project_id: z.string().min(1),
  round: z.number().int().min(1),
  count: z.number().int().min(1).max(5),
  product_info: ProductInfoSchema,
  previous_scenarios: z.array(z.any()).default([]),
});
export type WorkerInput = z.infer<typeof WorkerInputSchema>;

/** Remotion + React Three Fiber로 코드 생성할 수 있는 3D 장면 명세 (pipeline/scripts/scenegen.mjs 입력). */
export const Scene3DSchema = z.object({
  fact_shown: z.string().describe("이 장면의 3D가 눈으로 보여 줘야 하는 사실 한 줄"),
  objects: z
    .array(
      z.object({
        name: z.string(),
        build: z.string().describe("three.js 기본 도형으로 만드는 법(예: CylinderGeometry thetaLength=π/4 부채꼴, InstancedMesh 200개 구)"),
        material: z.string().describe("meshStandardMaterial / meshPhysicalMaterial + 질감"),
        color: z.string().describe("hex. 강조색은 #e8322a 하나만"),
        position: z.string().describe("화면 위쪽 절반 기준 위치(x -2~2, y 0~3)"),
      })
    )
    .describe("1~4개. 외부 모델·텍스처·글자 없이 기본 도형으로"),
  motion: z
    .array(
      z.object({
        from: z.number().min(0).max(1).describe("장면 진행 비율 시작"),
        to: z.number().min(0).max(1),
        action: z.string().describe("무엇이 어떻게 움직이는지(회전, 채워짐, 쪼개짐, 수치 상승 등)"),
      })
    )
    .describe("2단계 이상. 장면 내내 무언가 움직여야 한다"),
  camera: z.string().describe("static / dolly_in / orbit / pan 중 하나 + 한 줄 설명. 기본 카메라 [0,0.8,7] fov45"),
  counter: z
    .object({ from: z.number(), to: z.number(), unit: z.string() })
    .nullable()
    .describe("숫자 카운터(화면 위쪽, 3D와 같은 spring으로 동기화). 숫자 없는 장면은 null"),
  background: z.string().describe("배경 hex(어두운 단색). 무대 벽색과 맞춘다"),
  lighting: z.string().describe("무대 자연광 위에 더할 빛이 있으면 한 줄(없으면 '무대 기본')"),
  stage: z
    .object({
      place: z.string().describe("이야기 장소 한 줄 (예: 19세기 실험실)"),
      floor_color: z.string().describe("바닥 hex (중간 밝기)"),
      wall_color: z.string().describe("뒤 벽 hex (어둡게)"),
    })
    .optional(),
  shots: z
    .array(z.object({ at: z.number().min(0).max(1), view: z.enum(["wide", "person", "visual", "product"]) }))
    .optional()
    .describe("카메라 키프레임 (장면 진행 비율 → 보는 곳). 예: [{at:0,view:wide},{at:0.5,view:visual}]"),
  viz_place: z.enum(["air", "floor"]).optional().describe("시각화 자리: air = 인물 오른쪽 공중, floor = 인물 오른쪽 바닥 위"),
  lid_open: z
    .object({ from: z.number().min(0).max(1), to: z.number().min(0).max(1) })
    .nullable()
    .optional()
    .describe("반전 장면에서 제품 뚜껑을 여는 구간 (제품에 뚜껑이 있을 때). 없으면 null"),
  character: z
    .object({
      model: z.string().describe("캐릭터 모델 이름 (있는 에셋 목록의 인물 이름 그대로)"),
      role: z.string().describe("이야기 속 누구인지"),
      emotions: z
        .array(
          z.object({
            type: z.enum(["look", "tilt", "nod", "surprise", "bounce", "droop", "victory", "defeat"]),
            from: z.number().min(0).max(1),
            to: z.number().min(0).max(1),
          })
        )
        .describe("감정 표현 (장면 진행 비율)"),
    })
    .nullable()
    .optional()
    .describe("이야기 주인공 인물. 사람이 없으면 null"),
  assets: z
    .array(
      z.object({
        query: z.string().describe("영어 1~3단어 모델 검색어 (예: desk, bookcase, pine tree)"),
        role: z.string().describe("이야기에서 무엇인지"),
        place: z.string().describe("어디에 놓는지 (예: 바닥 뒤 오른쪽)"),
        slot: z
          .enum(["back-left", "back-center", "back-right", "side-left", "side-right", "mid-left", "mid-right", "near-person", "front-right", "fg-left", "fg-right"])
          .optional()
          .describe("놓을 자리 (on 이 있으면 무시)"),
        height: z.number().optional().describe("한 개의 실제 높이(m). 사람 1.7 기준"),
        on_query: z.string().optional().describe("받침이 되는 항목의 query 를 그대로 (예: \"table\"). 탁자·책상·선반 위에 올릴 때. 받침 항목이 이 항목보다 먼저 나와야 함"),
        count: z.number().int().min(1).max(8).optional().describe("같은 물건 개수 (기본 1)"),
        pattern: z.enum(["single", "row", "grid", "stack", "cluster", "arc"]).optional().describe("여러 개 놓는 모양: row 한 줄, grid 두 줄, stack 위로 쌓기, cluster 촘촘한 무리, arc 부채꼴"),
      })
    )
    .optional()
    .describe("장소를 꾸미는 3D 물건 3~6개"),
});
export type Scene3D = z.infer<typeof Scene3DSchema>;

export const BeatSchema = z.object({
  order: z.number().int().min(1),
  role: z.string().describe("어긋난 시작 / 브리지 1 / 브리지 2 / 반전: 제품 첫 등장"),
  duration_sec: z.number().positive(),
  visual: z.string().describe("장면 요약 한 줄(사람이 읽는 용도)"),
  scene3d: Scene3DSchema.optional(),
  narration: z.string().describe("'~습니다/~ㅂ니다'체, 숫자는 한글로 읽히게"),
  caption: z.string().describe("짧은 구어, 한 줄 8자 안팎, 최대 2줄(\\n), 숫자는 아라비아 숫자"),
});

export const BridgeNodeSchema = z.object({
  word: z.string(),
  sim_to_anchor: z.number().min(0).max(1),
});

export const FactSourceSchema = z.object({
  claim: z.string(),
  status: z.string().describe("'제품 정보(verified_facts)' / '계산(검증 불필요)' / '출처 확인 필요' 중 하나"),
});

export const BAdSpecSchema = z.object({
  track_archetype: z.literal("B_info_hook_offset"),
  hook_similarity_score: z.number().min(0).max(1),
  anchor: z.string(),
  bridge_path: z.array(BridgeNodeSchema).describe("[시작 단어, 브리지 1, (브리지 2)]. 앵커 자체는 넣지 않는다"),
  adjacent_min_sim: z.number().min(0).max(1),
  number_thread: z.string(),
  product_first_mention_beat: z.number().int().min(1),
  story_seed: z.string().optional().describe("고른 이야기 씨앗 한 줄 (유사도 검색 후보에서)"),
  product_taboo_keywords: z.array(z.string()).default([]).describe("반전 전까지 쓰면 안 되는 제품명·제품군 어휘"),
  visual_style: z.string().default("blender_3d_cutaway"),
  fact_sources: z.array(FactSourceSchema),
});

/** 모델이 만드는 부분. scenario_id·round·type은 코드가 채운다. */
export const DraftScenarioSchema = z.object({
  hook_title: z.string(),
  hook_duration_sec: z.number().positive(),
  body_duration_sec: z.number().nonnegative(),
  replacement_test_note: z.string(),
  beats: z.array(BeatSchema),
  ad_spec: BAdSpecSchema,
});
export type DraftScenario = z.infer<typeof DraftScenarioSchema>;

/** 시나리오 단계 출력: 3D 명세(scene3d)는 다음 단계에서 따로 만들므로 뺀다 (구조화 출력 스키마가 너무 커지지 않게) */
export const ScenarioOnlyResponseSchema = z.object({
  scenarios: z.array(DraftScenarioSchema.extend({ beats: z.array(BeatSchema.omit({ scene3d: true })) })),
});

export const DraftResponseSchema = z.object({
  scenarios: z.array(DraftScenarioSchema),
});

/** 생성용: scene3d를 필수로 요구한다. */
const GenBeatSchema = BeatSchema.extend({ scene3d: Scene3DSchema });
export const GenResponseSchema = z.object({
  scenarios: z.array(DraftScenarioSchema.extend({ beats: z.array(GenBeatSchema) })),
});

export type ScenarioItem = DraftScenario & {
  scenario_id: string;
  round: number;
  type: "B";
};

export interface ScenariosResponse {
  project_id: string;
  status: "SCENARIOS_READY";
  round: number;
  scenarios: ScenarioItem[];
}
