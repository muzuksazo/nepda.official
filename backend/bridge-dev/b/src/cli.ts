import { existsSync, mkdirSync, readdirSync, readFileSync, writeFileSync } from "node:fs";
import { join, resolve } from "node:path";
import { checkScenario } from "./check.js";
import { generateScenarios, type RunRecord } from "./generate.js";
import { toPipelinePlan } from "./pipeline-plan.js";
import { dur, renderReport } from "./report.js";
import { renderCuts } from "./cuts.js";
import { renderHookVideos } from "./video.js";
import { addScene3d } from "./scene3d.js";
import { totals, type StepUsage } from "./cost.js";
import { DraftScenarioSchema, WorkerInputSchema } from "./schema.js";

const USAGE = `사용법:
  npm run scenarios -- <입력.json> [--next] [--cuts] [--count N] [--no-ideate] [--attempts N]
      유사도 검색 → 시나리오·3D 장면 생성 → 규칙 검사. Claude API 호출(과금).
      --next       이 프로젝트의 다음 회차로 실행 (앞선 회차 시나리오를 피함)
      --cuts       장면 컷 이미지까지 렌더 (video_test/pipeline 필요, 추가 과금)
      --no-ideate  유사도 검색 단계 건너뛰기
      --new-search 저장된 검색(out/<project_id>/ideation.json)을 쓰지 않고 새로 검색 (앵커도 새로 정함)
      (기본: 같은 프로젝트에 저장된 검색이 있으면 재사용하고 앵커를 고정, 씨앗이 떨어지면 추가 검색)
  npm run cuts -- <project_id> <round>
      이미 만든 회차의 장면 컷 이미지를 렌더하고 리포트를 갱신. Claude API 호출(과금).
  npm run video -- <project_id> <round>
      컷 단계의 장면 코드 + TTS 나레이션으로 훅 영상(mp4)을 렌더. Claude 호출 없음.
  npm run report -- <project_id>
      out/<project_id>/ 의 회차 기록으로 report.html 다시 만들기. API 호출 없음.
  npm run check -- <시나리오응답.json> [--input <입력.json>]
      이미 있는 응답을 규칙만 검사. API 호출 없음.

결과: out/<project_id>/report.html (회차별 접기·펴기, 비용 포함)
      out/<project_id>/round-<n>.json (회차 기록)
      out/<project_id>/round-<n>/<scenario_id>.plan.json (video_test/pipeline 입력 형식)`;

const OUT = resolve("out");

function arg(flag: string): string | undefined {
  const i = process.argv.indexOf(flag);
  return i >= 0 ? process.argv[i + 1] : undefined;
}
const has = (flag: string) => process.argv.includes(flag);
const readJson = (path: string): unknown => JSON.parse(readFileSync(path, "utf8"));

export function loadRuns(projectId: string): RunRecord[] {
  const dir = join(OUT, projectId);
  if (!existsSync(dir)) return [];
  return readdirSync(dir)
    .filter((f) => /^round-\d+\.json$/.test(f))
    .map((f) => readJson(join(dir, f)) as RunRecord);
}

function writeReport(projectId: string, productName: string): string {
  const path = join(OUT, projectId, "report.html");
  writeFileSync(path, renderReport(loadRuns(projectId), productName), "utf8");
  return path;
}

type ProductInfo = ReturnType<typeof WorkerInputSchema.parse>["product_info"];

/** 기록에 제품 정보가 없으면(예전 기록) --input 또는 예시 입력에서 읽는다 */
function productOf(run: RunRecord & { product_info?: ProductInfo }): ProductInfo {
  if (run.product_info) return run.product_info;
  return WorkerInputSchema.parse(readJson(arg("--input") ?? "examples/01_worker-input.scenarios.json")).product_info;
}

async function attachCuts(run: RunRecord, projectId: string, product: ProductInfo): Promise<RunRecord> {
  const log = (m: string) => console.error(m);
  // 시나리오 단계에서 뺀 3D 명세를 여기서(고른 시나리오에만) 만든다
  const s3d = await addScene3d(run.response.scenarios, product, { log });
  const scenarios = s3d.scenarios;
  const { cuts, steps } = await renderCuts(scenarios, { projectDir: join(OUT, projectId), round: run.response.round, log });
  const kept = run.steps.filter((s) => !s.step.startsWith("컷:")); // 다시 렌더하면 이전 컷 비용을 대체
  const allSteps = [...kept, ...s3d.steps, ...steps];
  return { ...run, response: { ...run.response, scenarios }, cuts, steps: allSteps, total: totals(allSteps) };
}

function printCuts(run: RunRecord) {
  for (const c of run.cuts ?? []) {
    const ok = c.beats.filter((b) => b.ok).length;
    console.log(`\n컷 ${c.scenario_id}: 장면 ${ok}/${c.beats.length}개 생성 성공`);
    for (const b of c.beats)
      console.log(`  장면 ${b.order} ${b.ok ? "✓" : "✗ 기본 도형"} (시도 ${b.tries}회) ${b.images.length}컷${b.error ? " — " + b.error.split("\n")[0].slice(0, 100) : ""}`);
  }
}

function printChecks(rows: { title: string; errors: string[]; warnings: string[] }[]): boolean {
  let ok = true;
  for (const r of rows) {
    console.log(`\n■ ${r.title}`);
    if (!r.errors.length && !r.warnings.length) console.log("  통과");
    for (const e of r.errors) console.log(`  ✗ ${e}`);
    for (const w of r.warnings) console.log(`  △ ${w}`);
    if (r.errors.length) ok = false;
  }
  return ok;
}

async function main() {
  const [cmd, file] = process.argv.slice(2);
  if (!cmd || !file) {
    console.log(USAGE);
    process.exit(1);
  }

  if (cmd === "check") {
    const res = readJson(file) as { scenarios?: unknown[] };
    const input = WorkerInputSchema.parse(readJson(arg("--input") ?? "examples/01_worker-input.scenarios.json"));
    const rows = (res.scenarios ?? []).map((raw) => {
      const s = DraftScenarioSchema.parse(raw);
      return { title: s.hook_title, ...checkScenario(s, input.product_info) };
    });
    process.exit(printChecks(rows) ? 0 : 2);
  }

  if (cmd === "cuts") {
    const round = Number(process.argv[4]);
    const recordPath = join(OUT, file, `round-${round}.json`);
    if (!round || !existsSync(recordPath)) {
      console.error(`${recordPath} 가 없습니다. 사용법: npm run cuts -- <project_id> <round>`);
      process.exit(1);
    }
    if (!process.env.ANTHROPIC_API_KEY) {
      console.error("ANTHROPIC_API_KEY가 없습니다. b/.env를 확인하세요.");
      process.exit(1);
    }
    const run = readJson(recordPath) as RunRecord & { product_name?: string };
    const updated = await attachCuts(run, file, productOf(run));
    writeFileSync(recordPath, JSON.stringify(updated, null, 2) + "\n", "utf8");
    const reportPath = writeReport(file, run.product_name ?? file);
    printCuts(updated);
    const cutSteps = updated.steps.filter((s) => s.step.startsWith("컷:"));
    const t = totals(cutSteps);
    console.log(`\n컷 비용 $${t.costUsd.toFixed(4)} · ⏱ ${dur(t.ms)}\n리포트: ${reportPath}`);
    return;
  }

  if (cmd === "video") {
    const round = Number(process.argv[4]);
    const recordPath = join(OUT, file, `round-${round}.json`);
    if (!round || !existsSync(recordPath)) {
      console.error(`${recordPath} 가 없습니다. 사용법: npm run video -- <project_id> <round>`);
      process.exit(1);
    }
    const run = readJson(recordPath) as RunRecord & { product_name?: string };
    const t0 = Date.now();
    // --gclips: scripts/gclips.py 로 만든 Google 영상 클립을 이야기 장면에 쓴다 (반전은 3D)
    const gclips = has("--gclips");
    let clips: Record<number, string> | undefined;
    const gSteps: StepUsage[] = [];
    if (gclips) {
      const gdir = join(OUT, file, `round-${round}`, "gclips");
      const metaPath = join(gdir, "meta.json");
      if (!existsSync(metaPath)) {
        console.error(`${metaPath} 가 없습니다. 먼저 .venv/Scripts/python scripts/gclips.py ${file} ${round}`);
        process.exit(1);
      }
      const meta = readJson(metaPath) as {
        image_model: string; video_model: string;
        ref?: { elapsed_sec: number };
        clips: { order: number; path: string; elapsed_sec: number; requested_sec: number }[];
      };
      clips = Object.fromEntries(meta.clips.map((c) => [c.order, join(gdir, c.path)]));
      // Google 모델 단가는 아직 모름 → 비용 미상(null)으로 기록, 시간은 실측
      if (meta.ref) gSteps.push({ step: "Google: 참고 이미지", model: meta.image_model, inputTokens: 0, outputTokens: 0, costUsd: null, ms: Math.round(meta.ref.elapsed_sec * 1000) });
      for (const c of meta.clips)
        gSteps.push({ step: `Google: 장면 ${c.order} 클립 ${c.requested_sec}초`, model: meta.video_model, inputTokens: 0, outputTokens: 0, costUsd: null, ms: Math.round(c.elapsed_sec * 1000) });
    }
    const { videos, steps } = await renderHookVideos(run.response.scenarios, run.cuts, {
      projectDir: join(OUT, file),
      round,
      log: (m) => console.error(m),
      clips,
    });
    const variant = gclips ? "gclips" : "3d";
    const isMine = (s: StepUsage) => (gclips ? s.step.startsWith("Google:") || s.step.startsWith("영상(Google") : s.step.startsWith("영상:"));
    const allSteps = [...run.steps.filter((s) => !isMine(s)), ...gSteps, ...steps];
    const keepVideos = (run.videos ?? []).filter((v) => (v.variant ?? "3d") !== variant);
    const updated = { ...run, videos: [...keepVideos, ...videos], steps: allSteps, total: totals(allSteps) };
    writeFileSync(recordPath, JSON.stringify(updated, null, 2) + "\n", "utf8");
    const reportPath = writeReport(file, run.product_name ?? file);
    for (const v of videos) {
      console.log(`\n영상 ${v.scenario_id}: ${v.seconds}초 → out/${file}/${v.file}`);
      for (const s of v.scenes)
        console.log(`  장면 ${s.order}: 계획 ${s.planned}초 → ${s.final}초 (음성 ${s.voiceSec ?? "-"}초)${s.usedGen ? "" : " · 기본 도형"}`);
    }
    for (const s of steps) console.log(`  ${s.step}  ${dur(s.ms)}`);
    console.log(`\n영상 단계 ⏱ ${dur(Date.now() - t0)} · 비용 $0\n리포트: ${reportPath}`);
    return;
  }

  if (cmd === "report") {
    const runs = loadRuns(file);
    if (!runs.length) {
      console.error(`out/${file}/ 에 회차 기록이 없습니다.`);
      process.exit(1);
    }
    const name = (runs[0] as RunRecord & { product_name?: string }).product_name ?? file;
    console.log(`저장: ${writeReport(file, name)}`);
    return;
  }

  if (cmd === "generate") {
    if (!process.env.ANTHROPIC_API_KEY) {
      console.error("ANTHROPIC_API_KEY가 없습니다. b/.env.example을 b/.env로 복사해 키를 넣으세요.");
      process.exit(1);
    }
    const input = WorkerInputSchema.parse(readJson(file));
    if (arg("--count")) input.count = Number(arg("--count"));
    if (has("--next")) {
      const prev = loadRuns(input.project_id);
      input.round = prev.reduce((m, r) => Math.max(m, r.response.round), 0) + 1;
      input.previous_scenarios = [...input.previous_scenarios, ...prev.flatMap((r) => r.response.scenarios)];
    }
    const dir = join(OUT, input.project_id);
    const recordPath = join(dir, `round-${input.round}.json`);
    if (existsSync(recordPath) && !has("--force")) {
      console.error(`${recordPath} 가 이미 있습니다. 다음 회차는 --next, 덮어쓰려면 --force.`);
      process.exit(1);
    }

    const poolPath = join(dir, "ideation.json");
    const pool = !has("--new-search") && existsSync(poolPath) ? (readJson(poolPath) as RunRecord["ideation"]) : null;
    let run = await generateScenarios(input, {
      ideate: !has("--no-ideate"),
      pool,
      maxAttempts: arg("--attempts") ? Number(arg("--attempts")) : undefined,
      log: (m) => console.error(m),
    });
    if (has("--cuts")) run = await attachCuts(run, input.project_id, input.product_info);

    mkdirSync(join(dir, `round-${input.round}`), { recursive: true });
    // 검색 결과 저장 → 다음 회차에서 재사용 (앵커 고정)
    if (run.ideation && "seeds" in run.ideation) writeFileSync(poolPath, JSON.stringify(run.ideation, null, 2) + "\n", "utf8");
    writeFileSync(recordPath, JSON.stringify({ ...run, product_name: input.product_info.name, product_info: input.product_info }, null, 2) + "\n", "utf8");
    for (const s of run.response.scenarios)
      writeFileSync(join(dir, `round-${input.round}`, `${s.scenario_id}.plan.json`), JSON.stringify(toPipelinePlan(s), null, 2) + "\n", "utf8");
    const reportPath = writeReport(input.project_id, input.product_info.name);

    const ok = printChecks(run.response.scenarios.map((s, i) => ({ title: s.hook_title, ...run.checks[i] })));
    printCuts(run);
    console.log(`\n${run.response.round}회차 · 시나리오 ${run.response.scenarios.length}개`);
    console.log("비용:");
    for (const s of run.steps)
      console.log(`  ${s.step.padEnd(18)} ${s.model}  입력 ${s.inputTokens} / 출력 ${s.outputTokens}  ${s.costUsd === null ? "단가 미상" : "$" + s.costUsd.toFixed(4)}  ${dur(s.ms)}`);
    console.log(`  합계  입력 ${run.total.inputTokens} / 출력 ${run.total.outputTokens}  $${run.total.costUsd.toFixed(4)}  ⏱ ${dur(run.total.ms)}`);
    console.log(`\n리포트: ${reportPath}\n기록: ${recordPath}`);
    process.exit(ok ? 0 : 2);
  }

  console.log(USAGE);
  process.exit(1);
}

main().catch((e) => {
  console.error(e instanceof Error ? e.message : e);
  process.exit(1);
});
