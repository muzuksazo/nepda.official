// 측정: 회차 기록의 화면 검수 결과를 모아 "사람 손 안 대고 쓸 수 있는 비율"을 본다.
//   장면 단위: 첫 검수 통과율, 다시 만든 뒤 최종 통과율, 평균 점수
//   영상 단위: 모든 장면이 최종 통과한 영상 비율
//   문제 종류: 어떤 문제가 얼마나 나오는지(시각화 코드 탓 / 키트 탓) → 키트·부품을 고칠 곳
import type { RunRecord } from "./generate.js";
import type { BeatCut } from "./cuts.js";

export interface Measure {
  rounds: number[];
  videos: number;
  videosAllPass: number;
  scenes: number;
  reviewed: number;
  firstPass: number;
  finalPass: number;
  avgScore: number;
  codeFailed: number;
  kinds: { kind: string; count: number }[];
  costPerVideo: number;
  minutesPerRound: number;
}

export function measureRuns(runs: RunRecord[]): Measure {
  const beats: BeatCut[] = [];
  let videos = 0, videosAllPass = 0, cost = 0, ms = 0;
  const rounds: number[] = [];
  for (const r of runs) {
    const cuts = r.cuts ?? [];
    if (!cuts.some((c) => c.beats.some((b) => b.qa))) continue; // 검수 전 기록은 빼고
    rounds.push(r.response.round);
    cost += r.total.costUsd;
    ms += r.total.ms;
    for (const c of cuts) {
      videos++;
      if (c.beats.every((b) => b.ok && b.qa?.pass)) videosAllPass++;
      beats.push(...c.beats);
    }
  }
  const reviewed = beats.filter((b) => b.qa);
  const counts = new Map<string, number>();
  for (const b of reviewed) for (const h of b.qa!.history) for (const k of h.kinds) counts.set(k, (counts.get(k) ?? 0) + 1);
  return {
    rounds: rounds.sort((a, b) => a - b),
    videos,
    videosAllPass,
    scenes: beats.length,
    reviewed: reviewed.length,
    firstPass: reviewed.filter((b) => b.qa!.firstPass).length,
    finalPass: reviewed.filter((b) => b.qa!.pass).length,
    avgScore: reviewed.length ? reviewed.reduce((a, b) => a + b.qa!.score, 0) / reviewed.length : 0,
    codeFailed: beats.filter((b) => !b.ok).length,
    kinds: [...counts.entries()].map(([kind, count]) => ({ kind, count })).sort((a, b) => b.count - a.count),
    costPerVideo: videos ? cost / videos : 0,
    minutesPerRound: rounds.length ? ms / rounds.length / 60000 : 0,
  };
}

const pct = (a: number, b: number) => (b ? `${Math.round((a / b) * 100)}% (${a}/${b})` : "-");

export function measureText(m: Measure): string {
  return [
    `측정 회차: ${m.rounds.join(", ") || "없음 (화면 검수가 들어간 회차가 없음)"}`,
    `영상: 모든 장면 최종 통과 ${pct(m.videosAllPass, m.videos)}`,
    `장면: 첫 검수 통과 ${pct(m.firstPass, m.reviewed)} → 다시 만든 뒤 ${pct(m.finalPass, m.reviewed)} · 평균 점수 ${m.avgScore.toFixed(1)}/5 · 코드 실패 ${m.codeFailed}`,
    `자주 나온 문제(종류/원인): ${m.kinds.slice(0, 8).map((k) => `${k.kind} ${k.count}`).join(", ") || "없음"}`,
    `비용: 영상당 $${m.costPerVideo.toFixed(2)} · 회차당 ${m.minutesPerRound.toFixed(1)}분`,
  ].join("\n");
}
