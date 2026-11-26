// 화면 자동 검수: 장면 컷(여러 프레임)을 Claude 가 직접 보고 체크리스트로 판정한다.
// 탈락한 장면은 고칠 점(fix)을 장면 코드 작성자에게 돌려보내 다시 만들게 한다 (cuts.ts).
// 검수 결과는 회차 기록에 남겨 통과율을 잰다 (사람 개입 없이 쓸 수 있는 비율).
import { anthropic } from "@ai-sdk/anthropic";
import { generateText, Output, type LanguageModel } from "ai";
import { readFileSync } from "node:fs";
import { z } from "zod";
import { priceOf, type StepUsage } from "./cost.js";

export const QA_MODEL = "claude-sonnet-5-5";

export const QA_KINDS = [
  "crop", // 중요한 것이 화면 가장자리에서 잘림
  "interpenetration", // 메쉬가 서로 파고듦·관통 (뚜껑이 컵을 뚫음, 물체가 바닥·벽에 박힘, 인물과 소품이 겹침)
  "floating", // 바닥에 있어야 할 물체가 떠 있음
  "empty", // 화면이 비어 보임 (큰 빈 공간·검은 영역, 3D가 위쪽 2/3를 못 채움)
  "caption_area", // 중요한 시각 정보가 자막 영역(아래 약 40%)에 가려짐
  "content", // 시각화가 사실·자막과 맞지 않음, 카운터 숫자와 자막이 어긋남
  "untextured", // 모델이 색 없이 하얗거나 회색으로만 나옴
  "text_in_3d", // 3D 안에 글자·숫자
  "product", // 반전: 제품이 작거나 안 보이거나 기울어짐, 배경이 안 어두워짐
  "other",
] as const;

const QaSchema = z.object({
  pass: z.boolean().describe("major 문제가 하나도 없으면 true"),
  score: z.number().min(1).max(5).describe("이 장면을 사람 손 안 대고 써도 되는 정도 (5 = 바로 써도 됨)"),
  issues: z.array(
    z.object({
      kind: z.enum(QA_KINDS),
      severity: z.enum(["major", "minor"]),
      owner: z.enum(["viz", "kit"]).describe("viz = 시각화 코드(사실을 보여 주는 도형·움직임)가 원인, kit = 무대·소품·인물·카메라·제품·템플릿이 원인"),
      frame: z.string().describe("몇 번째 프레임(%)에서 보이는지"),
      detail: z.string().describe("무엇이 문제인지 구체적으로 한 줄"),
      fix: z.string().describe("시각화 코드 작성자가 할 일 (owner=viz 일 때): 무엇을 어디로 얼마나 옮기거나 줄일지"),
    })
  ),
});
export type QaResult = z.infer<typeof QaSchema>;

export interface QaInput {
  images: { path: string; label: string }[];
  caption: string;
  narration: string;
  fact: string;
  reveal: boolean;
  counter?: string;
}

const CHECKLIST = `당신은 세로 숏폼(1080x1920) 3D 장면의 엄격한 화면 검수자입니다. 사람이 손대지 않고 바로 내보내도 되는지 판정합니다.
이미지는 같은 장면의 여러 프레임입니다(라벨 = 장면 진행 비율). 아래 체크리스트를 프레임마다 꼼꼼히 봅니다. 작은 부분도 확대해 보듯 봅니다.

체크리스트:
1. crop: 인물·시각화·제품 등 중요한 것이 화면 가장자리에서 잘림 (배경 소품이 살짝 잘리는 건 minor)
2. interpenetration: 메쉬가 서로 파고들거나 관통함. 예: 뚜껑이 컵 테두리를 뚫음, 물체가 바닥·벽에 박힘, 인물 몸이 소품에 박힘, 소품끼리 겹쳐 하나로 뭉개짐, 시각화 도형이 인물·소품을 뚫음. 경계선이 끊기거나 한 물체가 다른 물체 안으로 사라지는 곳을 찾습니다.
3. floating: 바닥에 있어야 할 물체가 공중에 떠 있음 (일부러 띄운 시각화는 제외)
4. empty: 화면의 큰 부분(30% 이상)이 비거나 검게 비어 있음, 3D가 화면 위쪽 2/3를 채우지 못함
5. caption_area: 자막은 호출자가 화면 아래쪽(약 58~78%)에 그립니다. 사실을 보여 주는 핵심 시각화가 그 영역에 가려지면 문제 (바닥·소품 일부가 자막 뒤에 있는 건 괜찮음)
6. content: 시각화가 아래 "보여 줘야 할 사실"과 자막 내용을 한눈에 보여 주지 못함, 카운터 숫자와 자막 숫자가 어긋남
7. untextured: 모델이 색 없이 하얗거나 회색 덩어리로만 나옴
8. text_in_3d: 3D 안에 읽히는 글자·숫자 (제품 라벨은 괜찮음)
9. product (반전 장면만): 착지 뒤 제품이 크고(화면 폭의 1/3 이상) 똑바로 서서 잘 보이는지, 제품 뒤쪽(배경·인물·소품)이 어두워졌는지

판정: major 문제가 하나라도 있으면 pass=false. 잘 보이지 않는 사소한 흠은 minor.
owner: 시각화 코드(사실을 보여 주는 도형·움직임)가 원인이면 viz, 무대·소품·인물·카메라·제품·착지 템플릿이 원인이면 kit.
fix: owner=viz 면 시각화 코드 작성자가 바로 고칠 수 있게 구체적으로 (예: "공중 원판을 지금의 70% 크기로 줄이고 위로 0.2 올리기").`;

export async function reviewScene(
  input: QaInput,
  opts: { modelId?: string; model?: LanguageModel; track: (s: StepUsage) => void; step: string }
): Promise<QaResult> {
  const modelId = opts.modelId || process.env.B_QA_MODEL?.trim() || QA_MODEL;
  const model = opts.model ?? anthropic(modelId);
  const t0 = performance.now();
  const text =
    `${CHECKLIST}\n\n` +
    `장면: ${input.reveal ? "반전 장면 (제품 첫 등장: 쾅 착지 → 뒤쪽 어두워짐 → 기능 효과)" : "이야기 장면"}\n` +
    `자막: ${JSON.stringify(input.caption)}\n나레이션: ${input.narration}\n` +
    (input.counter ? `화면 위 카운터: ${input.counter}\n` : "") +
    `보여 줘야 할 사실:\n${input.fact}\n\n프레임: ${input.images.map((i) => i.label).join(", ")}`;
  const r = await generateText({
    model,
    messages: [
      {
        role: "user",
        content: [
          { type: "text", text },
          ...input.images.flatMap((im) => [
            { type: "text" as const, text: `프레임 ${im.label}` },
            { type: "image" as const, image: readFileSync(im.path), mediaType: "image/png" },
          ]),
        ],
      },
    ],
    output: Output.object({ schema: QaSchema }),
    maxOutputTokens: 3000,
    providerOptions: { anthropic: { effort: "medium" } },
  });
  const inT = r.usage?.inputTokens ?? 0, outT = r.usage?.outputTokens ?? 0;
  opts.track({ step: opts.step, model: modelId, inputTokens: inT, outputTokens: outT, costUsd: priceOf(modelId, inT, outT), ms: Math.round(performance.now() - t0), group: "qa" });
  const out = r.output as QaResult;
  // major 가 있으면 무조건 탈락 (모델이 pass 를 잘못 매겨도)
  return { ...out, pass: out.pass && !out.issues.some((i) => i.severity === "major") };
}

/** 검수 탈락 사유 → 시각화 코드 작성자에게 줄 고칠 점 */
export function qaFeedback(q: QaResult): string {
  const viz = q.issues.filter((i) => i.owner === "viz");
  if (!viz.length) return "";
  return viz.map((i) => `- [${i.severity}] ${i.kind} @${i.frame}: ${i.detail} → ${i.fix}`).join("\n");
}
