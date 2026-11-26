import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { checkAgainstPrevious, checkScenario } from "./check.js";
import { generateScenarios } from "./generate.js";
import { DraftScenarioSchema, ScenariosResponseSchema, WorkerInputSchema } from "./schema.js";

function usage(): never {
  console.error(
    [
      "사용법:",
      "  tsx src/cli.ts generate <input.json> [--out <path>] [--next] [--count N] [--attempts N]",
      "  tsx src/cli.ts generate --input <input.json> [--out <path>] [--next] [--count N] [--attempts N]",
      "  tsx src/cli.ts check <response.json> [input.json]",
      "  tsx src/cli.ts check --input <response.json> [input.json]",
    ].join("\n"),
  );
  process.exit(1);
}

function takeFlag(args: string[], flag: string): string | undefined {
  const idx = args.indexOf(flag);
  if (idx === -1) return undefined;
  const val = args[idx + 1];
  args.splice(idx, val && !val.startsWith("--") ? 2 : 1);
  return val && !val.startsWith("--") ? val : undefined;
}

function hasFlag(args: string[], flag: string): boolean {
  const idx = args.indexOf(flag);
  if (idx === -1) return false;
  args.splice(idx, 1);
  return true;
}

function readJson(path: string): unknown {
  return JSON.parse(readFileSync(resolve(path), "utf8"));
}

async function cmdGenerate(args: string[]) {
  const inputFlag = takeFlag(args, "--input");
  const outFlag = takeFlag(args, "--out");
  const countFlag = takeFlag(args, "--count");
  const attemptsFlag = takeFlag(args, "--attempts");
  const nextMode = hasFlag(args, "--next");
  const inputPath = inputFlag ?? args.find((a) => !a.startsWith("--"));
  if (!inputPath) usage();

  const raw = readJson(inputPath);
  const input = WorkerInputSchema.parse(raw);

  if (countFlag) input.count = Number(countFlag);
  if (nextMode) {
    input.round += 1;
  }

  const maxAttempts = attemptsFlag ? Number(attemptsFlag) : 2;
  const record = await generateScenarios(input, {
    maxAttempts,
    log: (msg) => console.error(msg),
  });

  if (outFlag) {
    const outPath = resolve(outFlag);
    mkdirSync(dirname(outPath), { recursive: true });
    writeFileSync(outPath, JSON.stringify(record.response, null, 2), "utf8");
    console.error(`[A] 저장 완료: ${outPath}`);
  } else {
    process.stdout.write(JSON.stringify(record.response, null, 2) + "\n");
  }

  let hasError = false;
  for (const c of record.checks) {
    for (const w of c.warnings) console.error(`[경고:${c.scenario_id}] ${w}`);
    for (const e of c.errors) {
      hasError = true;
      console.error(`[오류:${c.scenario_id}] ${e}`);
    }
  }
  process.exit(hasError ? 2 : 0);
}

function cmdCheck(args: string[]) {
  const inputFlag = takeFlag(args, "--input");
  const positional = args.filter((a) => !a.startsWith("--"));
  const responsePath = inputFlag ?? positional[0];
  const workerInputPath = inputFlag ? positional[0] : positional[1];
  if (!responsePath) usage();

  const rawResp = readJson(responsePath);
  const parsedResp = ScenariosResponseSchema.parse(rawResp);

  let workerInput: ReturnType<typeof WorkerInputSchema.parse> | undefined;
  if (workerInputPath && existsSync(resolve(workerInputPath))) {
    workerInput = WorkerInputSchema.parse(readJson(workerInputPath));
  }

  let totalErrors = 0;
  let totalWarnings = 0;
  const seenPrev: unknown[] = [...(workerInput?.previous_scenarios ?? [])];

  for (const s of parsedResp.scenarios) {
    const draft = DraftScenarioSchema.parse(s);
    const res = checkScenario(draft, workerInput?.product_info);
    const dupErrs = checkAgainstPrevious(draft, seenPrev);
    res.errors.push(...dupErrs);
    seenPrev.push(s);

    for (const w of res.warnings) {
      totalWarnings++;
      console.error(`[경고:${s.scenario_id}] ${w}`);
    }
    for (const e of res.errors) {
      totalErrors++;
      console.error(`[오류:${s.scenario_id}] ${e}`);
    }
  }

  console.error(
    `[A:check] 시나리오 ${parsedResp.scenarios.length}건 검사 완료 (오류 ${totalErrors}건, 경고 ${totalWarnings}건)`,
  );
  process.exit(totalErrors > 0 ? 2 : 0);
}

async function main() {
  const [, , subcmd, ...rest] = process.argv;
  if (!subcmd || subcmd === "--help" || subcmd === "-h") usage();
  if (subcmd === "generate") {
    await cmdGenerate(rest);
  } else if (subcmd === "check") {
    cmdCheck(rest);
  } else {
    usage();
  }
}

main().catch((err) => {
  console.error(err instanceof Error ? err.message : String(err));
  process.exit(1);
});
