import { readFileSync, writeFileSync } from "node:fs";
import { loadConfig } from "./config.js";
import { submitJobToWorker } from "./bridge.js";
import { compareProviders, planAdSpec, type PlanRequest } from "./planner.js";
import type { PlannerProviderName } from "./providers.js";
import { AdSpecSchema, type TrackArchetype, type VisualStyle } from "./schema.js";
import { createPlannerServer } from "./server.js";

function parseFlags(argv: string[]): { cmd: string; flags: Record<string, string | boolean> } {
  const [cmd = "help", ...rest] = argv;
  const flags: Record<string, string | boolean> = {};
  for (let i = 0; i < rest.length; i++) {
    const token = rest[i];
    if (!token.startsWith("--")) continue;
    const key = token.slice(2);
    const next = rest[i + 1];
    if (!next || next.startsWith("--")) {
      flags[key] = true;
    } else {
      flags[key] = next;
      i++;
    }
  }
  return { cmd, flags };
}

function buildPlanRequest(flags: Record<string, string | boolean>): PlanRequest {
  const factsPath = String(flags.facts || "");
  if (!factsPath) throw new Error("--facts <00_product_facts.md> is required");
  const productFacts = readFileSync(factsPath, "utf8");
  return {
    projectId: String(flags["project-id"] || "campaign-ai-sdk"),
    productFacts,
    sourceVideo: String(flags.source || "source/product.mp4"),
    sourceDuration: Number(flags["source-duration"] || 10.0),
    voAudio: typeof flags.vo === "string" ? flags.vo : undefined,
    trackArchetype: (typeof flags.track === "string"
      ? flags.track
      : "A_bgrade_reversal") as TrackArchetype,
    visualStyle: (typeof flags.style === "string"
      ? flags.style
      : "blender_clay_diorama") as VisualStyle,
    contactSheetPath: typeof flags.sheet === "string" ? flags.sheet : undefined,
    pastArchetypes:
      typeof flags.avoid === "string"
        ? flags.avoid
            .split(",")
            .map((s) => s.trim())
            .filter(Boolean)
        : undefined,
  };
}

async function main() {
  const { cmd, flags } = parseFlags(process.argv.slice(2));
  const cfg = loadConfig();

  if (cmd === "serve") {
    const port = Number(flags.port || cfg.plannerPort);
    const server = createPlannerServer({ config: cfg });
    server.listen(port, "127.0.0.1", () => {
      console.log(
        `[planner-ai-sdk] serving at http://127.0.0.1:${port} (worker=${cfg.workerBaseUrl})`
      );
    });
    return;
  }

  if (cmd === "plan") {
    const provider = (typeof flags.provider === "string" ? flags.provider : "anthropic") as PlannerProviderName;
    const req = buildPlanRequest(flags);
    const res = await planAdSpec(req, {
      provider,
      modelId: typeof flags.model === "string" ? flags.model : undefined,
      config: cfg,
    });
    const jsonOut = JSON.stringify(res.spec, null, 2);
    if (typeof flags.out === "string") {
      writeFileSync(flags.out, jsonOut, "utf8");
    }
    console.log(jsonOut);
    return;
  }

  if (cmd === "compare") {
    const req = buildPlanRequest(flags);
    const compared = await compareProviders(req, { config: cfg });
    if (typeof flags.out === "string") {
      writeFileSync(flags.out, JSON.stringify(compared, null, 2), "utf8");
    }
    console.log(compared.summaryMarkdown);
    return;
  }

  if (cmd === "submit") {
    const specPath = String(flags.spec || "");
    const factsPath = String(flags.facts || "");
    if (!specPath || !factsPath) {
      throw new Error("--spec <05_ad_spec.json> and --facts <00_product_facts.md> are required");
    }
    const spec = AdSpecSchema.parse(JSON.parse(readFileSync(specPath, "utf8")));
    const factsMarkdown = readFileSync(factsPath, "utf8");
    const sub = await submitJobToWorker(
      {
        campaignId: String(flags["campaign-id"] || spec.project_id),
        specData: spec,
        factsMarkdown,
        sourceVideo: typeof flags.source === "string" ? flags.source : spec.source_video,
        resolution: (typeof flags.res === "string" ? flags.res : "720p") as "360p" | "720p",
        dryRun: Boolean(flags["dry-run"]),
      },
      { config: cfg }
    );
    console.log(JSON.stringify(sub, null, 2));
    return;
  }

  console.log(
    "Usage: planner-cli <plan|compare|submit|serve> [--provider anthropic|google] [--facts PATH] [--spec PATH]"
  );
}

main().catch((err) => {
  console.error(err instanceof Error ? err.message : err);
  process.exit(1);
});
