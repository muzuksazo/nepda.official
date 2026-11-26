import { existsSync, mkdirSync, readdirSync, readFileSync, writeFileSync } from "node:fs";
import { join, resolve } from "node:path";
import { checkScenario } from "./check.js";
import { generateScenarios, type RunRecord } from "./generate.js";
import { toPipelinePlan } from "./pipeline-plan.js";
import { dur, renderReport } from "./report.js";
import { renderCuts } from "./cuts.js";
import { renderHookVideos } from "./video.js";
import { joinCaptions, joinVideos, makeBody, type BodyResult } from "./body.js";
import { addScene3d } from "./scene3d.js";
import { totals, type StepUsage } from "./cost.js";
import { measureRuns, measureText } from "./measure.js";
import { createHash } from "node:crypto";
import { mergeResearch, RESEARCH_MODEL, researchProduct, researchWarnings, type ProductResearch } from "./research.js";
import { DraftScenarioSchema, WorkerInputSchema } from "./schema.js";
import { applyLlmSwitch } from "./llm.js";

const USAGE = `사용법:
  npm run research -- "<제품명>" [--project <id>] [--count N] [--known "<아는 정보: 제품 사진에서 본 생김새 등>"]
      제품 이름만으로 웹에서 제품 정보를 찾아 out/<project_id>/research.json 과 입력 파일 input.json 을 만든다.
      Claude API + 웹 검색(1회 $0.01) 호출(과금). 결과를 확인한 뒤 npm run scenarios -- out/<project_id>/input.json
  npm run scenarios -- <입력.json> [--next] [--cuts] [--count N] [--no-ideate] [--attempts N]
      유사도 검색 → 시나리오·3D 장면 생성 → 규칙 검사. Claude API 호출(과금).
      --next       이 프로젝트의 다음 회차로 실행 (앞선 회차 시나리오를 피함)
      --cuts       장면 컷 이미지까지 렌더 (video_test/pipeline 필요, 추가 과금)
      --no-ideate  유사도 검색 단계 건너뛰기
      --research   제품 조사를 다시 함 (기본: verified_facts 가 비어 있을 때만 조사, 저장된 research.json 이 있으면 재사용)
      --new-search 저장된 검색(out/<project_id>/ideation.json)을 쓰지 않고 새로 검색 (앵커도 새로 정함)
      (기본: 같은 프로젝트에 저장된 검색이 있으면 재사용하고 앵커를 고정, 씨앗이 떨어지면 추가 검색)
  npm run cuts -- <project_id> <round>
      이미 만든 회차의 장면 컷 이미지를 렌더하고 리포트를 갱신. Claude API 호출(과금).
  npm run video -- <project_id> <round> [--tts=inworld] [--no-captions]
      컷 단계의 장면 코드 + TTS 나레이션으로 훅 영상(mp4)을 렌더. Claude 호출 없음.
      자막을 굽고, 같은 이름의 .captions.json(장면별 시작·끝·자막·나레이션)도 남긴다. --no-captions 면 자막 없이.
  npm run body -- <project_id> [--seconds 10] [--footage <폴더>] [--tts=edge]
      제품 촬영 영상(b/product/<제품 모델>)으로 10초 안팎 본편(설명 나레이션·자막) → out/<project_id>/body/body.mp4. 훅과 상관없는 공용 단계.
  npm run join -- <결과.mp4> <훅.mp4> <본편.mp4>
      아무 훅 영상 뒤에 본편을 이어 붙인다 (A/C 훅에도 사용).
  npm run video -- <project_id> <round> --body
      훅 영상 + 본편을 붙인 <훅>_full.mp4 도 만든다 (본편이 없으면 만들고, 있으면 재사용).
  npm run measure -- <project_id>
      회차 기록의 화면 검수 결과로 통과율(사람 손 안 대고 쓸 수 있는 비율)·자주 나온 문제·영상당 비용. API 호출 없음.
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
  const rpath = join(OUT, projectId, "research.json");
  const research = existsSync(rpath) ? (readJson(rpath) as ProductResearch) : null;
  writeFileSync(path, renderReport(loadRuns(projectId), productName, research), "utf8");
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
  const { cuts, steps } = await renderCuts(scenarios, { projectDir: join(OUT, projectId), round: run.response.round, log, productModel: product.model });
  const kept = run.steps.filter((s) => !s.step.startsWith("컷:")); // 다시 렌더하면 이전 컷 비용을 대체
  const allSteps = [...kept, ...s3d.steps, ...steps];
  return { ...run, response: { ...run.response, scenarios }, cuts, steps: allSteps, total: totals(allSteps) };
}

function printCuts(run: RunRecord) {
  for (const c of run.cuts ?? []) {
    const ok = c.beats.filter((b) => b.ok).length;
    console.log(`\n컷 ${c.scenario_id}: 장면 ${ok}/${c.beats.length}개 생성 성공`);
    for (const b of c.beats)
      console.log(
        `  장면 ${b.order} ${b.ok ? "✓" : "✗ 기본 도형"} (시도 ${b.tries}회) ${b.images.length}컷` +
          (b.qa ? ` · 검수 ${b.qa.pass ? "통과" : "탈락"} ${b.qa.score}/5 (${b.qa.rounds}차${b.qa.firstPass ? ", 처음에 통과" : ""})` : "") +
          (b.qa && !b.qa.pass ? ` — ${b.qa.issues.filter((i) => i.severity === "major").map((i) => `${i.kind}/${i.owner}: ${i.detail}`).join(" | ").slice(0, 220)}` : "") +
          (b.error ? " — " + b.error.split("\n")[0].slice(0, 100) : "")
      );
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

/** 본편: out/<project_id>/body/body.mp4 가 있으면 재사용, 없거나 force 면 제품 촬영 영상으로 새로 만든다 */
async function ensureBody(projectId: string, opts: { force?: boolean } = {}): Promise<BodyResult> {
  const outDir = join(OUT, projectId, "body");
  const meta = join(outDir, "body.json");
  if (!opts.force && !has("--force") && existsSync(meta) && existsSync(join(outDir, "body.mp4"))) {
    console.error(`[본편] 저장된 본편 재사용 (out/${projectId}/body/body.mp4)`);
    return { ...(readJson(meta) as BodyResult), steps: [] };
  }
  const inputPath = join(OUT, projectId, "input.json");
  const runs = loadRuns(projectId).sort((a, b) => b.response.round - a.response.round);
  const product = existsSync(inputPath)
    ? WorkerInputSchema.parse(readJson(inputPath)).product_info
    : runs[0]
      ? productOf(runs[0] as RunRecord & { product_info?: ProductInfo })
      : null;
  if (!product) throw new Error(`out/${projectId}/input.json 이나 회차 기록이 없어 제품 정보를 알 수 없습니다.`);
  // 촬영 영상 폴더: --footage <경로> 또는 b/product/<제품 모델 이름>
  const footageDir = resolve(arg("--footage") ?? join("product", product.model ?? product.name));
  if (!existsSync(footageDir)) throw new Error(`촬영 영상 폴더가 없습니다: ${footageDir} (--footage 로 지정)`);
  return makeBody({
    product,
    footageDir,
    outDir,
    seconds: arg("--seconds") ? Number(arg("--seconds")) : 10,
    tts: process.argv.includes("--tts=edge") ? "edge" : "inworld",
    log: (m) => console.error(m),
  });
}

const projectIdOf = (name: string) => `proj_${createHash("sha1").update(name).digest("hex").slice(0, 8)}`;

/** 제품 조사: 저장된 research.json 이 같은 제품이면 재사용, 아니면 웹에서 새로 찾는다 */
async function ensureResearch(
  name: string,
  projectId: string,
  opts: { force?: boolean; known?: string }
): Promise<{ research: ProductResearch; steps: StepUsage[]; reused: boolean }> {
  const path = join(OUT, projectId, "research.json");
  if (!opts.force && existsSync(path)) {
    const saved = readJson(path) as ProductResearch;
    if (saved.query === name) return { research: saved, steps: [], reused: true };
  }
  const steps: StepUsage[] = [];
  // 조사는 읽고 정리하는 일이라 Sonnet 으로 충분하다 (B_RESEARCH_MODEL 로 바꿀 수 있음)
  const modelId = process.env.B_RESEARCH_MODEL?.trim() || RESEARCH_MODEL;
  const research = await researchProduct(name, { modelId, known: opts.known, track: (s) => steps.push(s), log: (m) => console.error(m) });
  mkdirSync(join(OUT, projectId), { recursive: true });
  writeFileSync(path, JSON.stringify(research, null, 2) + "\n", "utf8");
  return { research, steps, reused: false };
}

function printResearch(r: ProductResearch) {
  console.log(`\n찾은 제품: ${r.found.official_name}${r.found.brand ? ` (${r.found.brand})` : ""}  확신 ${r.found.confidence.toFixed(2)}`);
  console.log(`  ${r.found.main_url}`);
  console.log(`  짧은 이름: ${r.short_name} · 분류: ${r.category} · ${r.one_liner}`);
  console.log(`  용도: ${r.usage}`);
  console.log(`  생김새: ${r.appearance.shape} / ${r.appearance.colors} / ${r.appearance.parts}${r.appearance.size ? ` / ${r.appearance.size}` : ""}`);
  console.log(`  사실 ${r.facts.length}개 (웹 검색 ${r.searches}번):`);
  for (const f of r.facts) console.log(`   ${f.source_type === "리뷰·기타" ? "·" : "-"} [${f.source_type}] ${f.fact}`);
  const w = researchWarnings(r);
  if (w.length) console.log(`  확인 필요:\n${w.map((x) => `   ! ${x}`).join("\n")}`);
}

async function main() {
  applyLlmSwitch();
  const [cmd, file] = process.argv.slice(2);
  if (!cmd || !file) {
    console.log(USAGE);
    process.exit(1);
  }

  if (cmd === "research") {
    const researchModel = process.env.B_RESEARCH_MODEL?.trim() || RESEARCH_MODEL;
    if (!/^gemini/i.test(researchModel) && !process.env.ANTHROPIC_API_KEY) {
      console.error("ANTHROPIC_API_KEY가 없습니다. b/.env.example을 b/.env로 복사해 키를 넣으세요.");
      process.exit(1);
    }
    const name = file.trim();
    const projectId = arg("--project") ?? projectIdOf(name);
    const { research, steps } = await ensureResearch(name, projectId, { force: true, known: arg("--known") });
    printResearch(research);
    const input = WorkerInputSchema.parse({
      hook_type: "B",
      project_id: projectId,
      round: 1,
      count: arg("--count") ? Number(arg("--count")) : 2,
      product_info: mergeResearch({ name, verified_facts: [] }, research),
      previous_scenarios: [],
    });
    const inputPath = join(OUT, projectId, "input.json");
    writeFileSync(inputPath, JSON.stringify({ _comment: `제품 조사로 만든 입력 (${research.at}). 사실·생김새를 확인하고 고쳐 쓸 수 있다.`, ...input }, null, 2) + "\n", "utf8");
    const t = totals(steps);
    console.log("\n비용:");
    for (const s of steps) console.log(`  ${s.step.padEnd(18)} ${s.model}  입력 ${s.inputTokens} / 출력 ${s.outputTokens}  ${s.costUsd === null ? "단가 미상" : "$" + s.costUsd.toFixed(4)}  ${dur(s.ms)}`);
    console.log(`  합계  $${t.costUsd.toFixed(4)}  ⏱ ${dur(t.ms)}`);
    console.log(`\n조사: ${join(OUT, projectId, "research.json")}\n입력: ${inputPath}\n다음: npm run scenarios -- ${inputPath.split("\\").join("/")}`);
    process.exit(0);
  }

  if (cmd === "body") {
    // npm run body -- <project_id> [--seconds 10] [--tts=edge] [--force]
    const r = await ensureBody(file, { force: true });
    console.log(`\n본편 ${r.seconds}초 → ${r.file}\n대본:\n${r.script.lines.map((l) => `  ${l.narration}  [${l.caption.replace(/\n/g, " / ")}]`).join("\n")}`);
    const t = totals(r.steps);
    console.log(`비용 $${t.costUsd.toFixed(4)} · ⏱ ${dur(t.ms)}`);
    process.exit(0);
  }

  if (cmd === "join") {
    // npm run join -- <결과.mp4> <훅.mp4> <본편.mp4> [...]
    const inputs = process.argv.slice(4).filter((a) => !a.startsWith("--"));
    if (inputs.length < 2) {
      console.error("사용법: npm run join -- <결과.mp4> <훅.mp4> <본편.mp4> [...]");
      process.exit(1);
    }
    const sec = joinVideos(inputs.map((x) => resolve(x)), resolve(file));
    console.log(`${resolve(file)} (${sec.toFixed(2)}초)`);
    process.exit(0);
  }

  if (cmd === "measure") {
    console.log(measureText(measureRuns(loadRuns(file))));
    process.exit(0);
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
    // --char: round-N/char/<scenario_id>/beat<k>.tsx (재사용 인물 장면 코드)가 있는 장면은 그 코드로 렌더
    // --char        → round-N/char/      (마네킹)
    // --char=uacp   → round-N/char_uacp/ (직업 캐릭터 등, 영상도 따로 저장)
    const charArg = gclips ? undefined : process.argv.find((a) => a === "--char" || a.startsWith("--char="));
    const char = !!charArg;
    const charVariant = (charArg?.includes("=") ? `char_${charArg.split("=")[1]}` : "char") as `char_${string}` | "char";
    let charScenes: Record<number, string> | undefined;
    if (char) {
      const s0 = run.response.scenarios[0];
      const cdir = join(OUT, file, `round-${round}`, charVariant, s0.scenario_id);
      charScenes = Object.fromEntries(
        s0.beats.map((b) => [b.order, join(cdir, `beat${b.order}.tsx`)] as const).filter(([, p]) => existsSync(p))
      );
      if (!Object.keys(charScenes).length) {
        console.error(`${cdir} 에 인물 장면 코드(beat<k>.tsx)가 없습니다.`);
        process.exit(1);
      }
    }
    // --tts=inworld: Inworld TTS (b/.env 의 INWORLD_API_KEY, INWORLD_VOICE_ID)
    const tts = process.argv.includes("--tts=inworld") ? ("inworld" as const) : ("edge" as const);
    const { videos, steps } = await renderHookVideos(run.response.scenarios, run.cuts, {
      projectDir: join(OUT, file),
      round,
      log: (m) => console.error(m),
      clips,
      charScenes,
      charVariant,
      tts,
      productModel: productOf(run).model,
      burnCaptions: !has("--no-captions"),
    });
    const base = gclips ? "gclips" : char ? charVariant : "3d";
    const variant = tts === "inworld" ? `${base}_inworld` : base;
    const stepTag = variant === "gclips" ? "영상(Google" : variant === "char" ? "영상(인물)" : variant === "3d" ? "영상:" : `영상(${variant})`;
    const isMine = (s: StepUsage) => (variant === "gclips" && s.step.startsWith("Google:")) || s.step.startsWith(stepTag);
    const allSteps = [...run.steps.filter((s) => !isMine(s)), ...gSteps, ...steps];
    const keepVideos = (run.videos ?? []).filter((v) => (v.variant ?? "3d") !== variant);
    const updated = { ...run, videos: [...keepVideos, ...videos], steps: allSteps, total: totals(allSteps) };
    writeFileSync(recordPath, JSON.stringify(updated, null, 2) + "\n", "utf8");
    const reportPath = writeReport(file, run.product_name ?? file);
    // --body: 훅 뒤에 본편(제품 촬영 영상 설명)을 붙인 영상도 만든다 → <훅>_full.mp4 (+ 자막 데이터)
    if (has("--body")) {
      const body = await ensureBody(file);
      const bodySteps = body.steps;
      for (const v of videos) {
        const hookAbs = join(OUT, file, v.file);
        const fullRel = v.file.replace(/\.mp4$/, "_full.mp4");
        const t1 = Date.now();
        const sec = joinVideos([hookAbs, body.file], join(OUT, file, fullRel));
        joinCaptions(hookAbs.replace(/\.mp4$/, ".captions.json"), v.seconds, body.captions, join(OUT, file, fullRel.replace(/\.mp4$/, ".captions.json")), fullRel);
        (v as typeof v & { full?: string; fullSeconds?: number }).full = fullRel;
        (v as typeof v & { full?: string; fullSeconds?: number }).fullSeconds = +sec.toFixed(2);
        bodySteps.push({ step: "본편: 훅에 붙이기", model: "ffmpeg", inputTokens: 0, outputTokens: 0, costUsd: 0, ms: Date.now() - t1 });
        console.log(`\n훅 + 본편: ${sec.toFixed(2)}초 → out/${file}/${fullRel}`);
      }
      const withBody = { ...updated, videos: [...keepVideos, ...videos], steps: [...allSteps, ...bodySteps], total: totals([...allSteps, ...bodySteps]) };
      writeFileSync(recordPath, JSON.stringify(withBody, null, 2) + "\n", "utf8");
      for (const s of bodySteps) console.log(`  ${s.step}  ${s.costUsd ? "$" + s.costUsd.toFixed(4) : ""} ${dur(s.ms)}`);
    }
    for (const v of videos) {
      console.log(`\n영상 ${v.scenario_id}: ${v.seconds}초 → out/${file}/${v.file}`);
      for (const s of v.scenes)
        console.log(`  장면 ${s.order}: 계획 ${s.planned}초 → ${s.final}초 (음성 ${s.voiceSec ?? "-"}초)${s.usedGen ? "" : " · 기본 도형"}`);
    }
    for (const s of steps) console.log(`  ${s.step}  ${dur(s.ms)}`);
    const vc = steps.reduce((a, s) => a + (s.costUsd ?? 0), 0);
    const unknown = steps.some((s) => s.costUsd === null);
    console.log(`\n영상 단계 ⏱ ${dur(Date.now() - t0)} · 비용 $${vc.toFixed(4)}${unknown ? " + 미상" : ""}\n리포트: ${reportPath}`);
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
    const usesClaude = [process.env.B_MODEL, process.env.B_IDEA_MODEL, process.env.B_SCENE_MODEL, process.env.B_QA_MODEL].some((m) => !m || !/^gemini/i.test(m));
    if (usesClaude && !process.env.ANTHROPIC_API_KEY) {
      console.error("ANTHROPIC_API_KEY가 없습니다. b/.env.example을 b/.env로 복사해 키를 넣으세요.");
      process.exit(1);
    }
    const input = WorkerInputSchema.parse(readJson(file));
    if (arg("--count")) input.count = Number(arg("--count"));
    // 제품 조사: 사실이 비어 있거나 --research 면 웹에서 찾아 빈 칸을 채운다
    let researchSteps: StepUsage[] = [];
    if (has("--research") || input.product_info.verified_facts.length === 0) {
      const rr = await ensureResearch(input.product_info.name, input.project_id, { force: has("--research") });
      researchSteps = rr.steps;
      if (rr.reused) console.error(`[B 조사] 저장된 조사 결과 재사용 (out/${input.project_id}/research.json)`);
      printResearch(rr.research);
      input.product_info = mergeResearch(has("--research") ? { ...input.product_info, verified_facts: [] } : input.product_info, rr.research);
    }
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
    if (researchSteps.length) run = { ...run, steps: [...researchSteps, ...run.steps], total: totals([...researchSteps, ...run.steps]) };
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
