// ScenarioItem → video_test/pipeline 의 out/plan.json 형식.
// pipeline: scripts/scenegen.mjs 가 scene.visual 로 R3F 장면 코드를 만들고, tts.mjs 가 scene.say 로 음성을 만든다.
import type { Scene3D, ScenarioItem } from "./schema.js";

export const ACCENT = "#e8322a";

export function scene3dToVisual(sc: Scene3D): string {
  const objs = sc.objects
    .map((o) => `- ${o.name}: ${o.build}; material ${o.material}; color ${o.color}; position ${o.position}`)
    .join("\n");
  const motion = [...sc.motion]
    .sort((a, b) => a.from - b.from)
    .map((m) => `- ${Math.round(m.from * 100)}%~${Math.round(m.to * 100)}%: ${m.action}`)
    .join("\n");
  return [
    `FACT TO SHOW: ${sc.fact_shown}`,
    `OBJECTS:\n${objs}`,
    `MOTION (fraction of scene duration):\n${motion}`,
    `CAMERA: ${sc.camera}`,
    `LIGHTING: ${sc.lighting}`,
    sc.counter ? `A number counter overlay (${sc.counter.from}→${sc.counter.to} ${sc.counter.unit}) is drawn by the caller; sync the 3D motion to it.` : "",
    "No readable text or digits inside the 3D.",
  ]
    .filter(Boolean)
    .join("\n");
}

export function toPipelinePlan(s: ScenarioItem) {
  const scenes = [...s.beats]
    .sort((a, b) => a.order - b.order)
    .map((b) => ({
      type: "three" as const,
      durationSec: b.duration_sec,
      text: b.caption,
      say: b.narration,
      visual: b.scene3d ? scene3dToVisual(b.scene3d) : b.visual,
      // pipeline 카운터는 천 단위 쉼표를 붙여서 연도(1,980년)가 어색해진다 → 연도 카운터는 내보내지 않는다
      counter:
        b.scene3d?.counter && !/년/.test(b.scene3d.counter.unit)
          ? { from: b.scene3d.counter.from, to: b.scene3d.counter.to, suffix: b.scene3d.counter.unit, at: "top" as const }
          : undefined,
      color: ACCENT,
      bg: b.scene3d?.background ?? "#0b0b10",
    }));
  return {
    concept: `${s.hook_title} — ${s.ad_spec.anchor}`,
    hookSeconds: scenes.reduce((a, x) => a + x.durationSec, 0),
    scenes,
    source: "bridge-dev/b",
    scenario_id: s.scenario_id,
  };
}
