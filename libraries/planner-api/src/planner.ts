import { readFileSync, existsSync } from "node:fs";
import { generateText, Output, type LanguageModel } from "ai";
import { loadConfig, type PlannerConfig } from "./config.js";
import { resolvePlannerModel, type PlannerProviderName } from "./providers.js";
import {
  AdSpecSchema,
  type AdSpec,
  type TrackArchetype,
  type VisualStyle,
} from "./schema.js";

export interface PlanRequest {
  projectId: string;
  productFacts: string;
  sourceVideo: string;
  sourceDuration: number;
  voAudio?: string;
  trackArchetype?: TrackArchetype;
  visualStyle?: VisualStyle;
  pastArchetypes?: string[];
  contactSheetPath?: string;
  extraNotes?: string;
}

export interface PlanResult {
  provider: PlannerProviderName;
  modelId: string;
  elapsedMs: number;
  spec: AdSpec;
  usage?: {
    inputTokens?: number;
    outputTokens?: number;
    totalTokens?: number;
  };
}

export interface CompareResult {
  anthropic?: PlanResult;
  google?: PlanResult;
  errors: Partial<Record<PlannerProviderName, string>>;
  summaryMarkdown: string;
}

export type ModelResolver = (
  provider: PlannerProviderName,
  modelId?: string
) => { model: LanguageModel; modelId: string; provider: PlannerProviderName };

function buildSystemPrompt(req: PlanRequest): string {
  const track = req.trackArchetype ?? "A_bgrade_reversal";
  const style = req.visualStyle ?? (track === "B_info_hook_offset" ? "blender_3d_cutaway" : "blender_clay_diorama");
  const avoid = (req.pastArchetypes ?? []).filter(Boolean);

  return [
    "You are an expert Korean shortform performance-ad director building strict 05_ad_spec JSON.",
    "Rules that MUST NEVER be violated:",
    "1. Ground every product claim, USP, and CTA strictly in [VERIFIED] [F##] facts from productFacts. Never invent numbers or forbidden superlatives.",
    `2. Track archetype = ${track}. Visual style = ${style}.`,
    track === "A_bgrade_reversal"
      ? `   - For A_bgrade_reversal: pick a fresh a_genre_archetype NOT in [${avoid.join(", ")}] (dramatic genres or mechanism-only Brainrot archetypes: brainrot_hypnosis, deadpan_rhythmic_loop, sensory_sync_loop). Abstract ONLY retention principles from user/trend examples—never copy concrete nouns/songs/IP (record them in reference_surface_taboo). Populate product_taboo_keywords AND category_taboo_keywords (room/setting/function clues) and keep all three taboo lists at 0% across pre-twist captions, pop_badge, flow_ref_prompt, and flow_video_prompt before the 0.20-0.30s silence_gap; payoff <= 55% of runtime. Never clone breaking-news templates ('속보입니다', '단 한 집만').`
      : track === "B_info_hook_offset"
      ? "   - For B_info_hook_offset: set hook_similarity_score between 0.38 and 0.58; open with an unrelated science/nature fact + number across the entire pre-bridge window before silence_gap (0% direct product_taboo_keywords or reference_surface_taboo until payoff reveal)."
      : "   - For C_direct_proof: open with bright direct POV pain -> strongest real kinetic proof cut first.",
    style !== "photoreal"
      ? `3. Use stylized Blender 3D (${style}) prompts for flow_video hook cuts (` +
        "`flow_ref_prompt` and `flow_video_prompt` in English with zero readable text, zero numbers, zero photorealistic human skin)."
      : "3. Keep flow_video prompts strictly single-camera, zero readable text, zero digits.",
    "4. Captions: <= 2 lines per cue, <= 22 plain chars per line, zero emojis, highlighting keywords with **word**.",
    `5. Use source_video=${req.sourceVideo} (duration=${req.sourceDuration}s) and vo_audio=${req.voAudio ?? "audio/vo_master.wav"}.`,
  ].join("\n");
}

function buildUserContent(req: PlanRequest) {
  const textPrompt = [
    `Project ID: ${req.projectId}`,
    `Source Video: ${req.sourceVideo} (${req.sourceDuration}s)`,
    `Visual Style: ${req.visualStyle ?? "blender_clay_diorama"}`,
    req.extraNotes ? `Extra Notes: ${req.extraNotes}` : "",
    "",
    "Product Facts Ledger:",
    req.productFacts,
  ]
    .filter(Boolean)
    .join("\n");

  if (req.contactSheetPath && existsSync(req.contactSheetPath)) {
    const imgBytes = readFileSync(req.contactSheetPath);
    return [
      { type: "text" as const, text: textPrompt },
      { type: "image" as const, image: imgBytes, mediaType: "image/png" },
    ];
  }
  return textPrompt;
}

export async function planAdSpec(
  req: PlanRequest,
  options: {
    provider?: PlannerProviderName;
    modelId?: string;
    config?: PlannerConfig;
    modelResolver?: ModelResolver;
  } = {}
): Promise<PlanResult> {
  const provider = options.provider ?? "anthropic";
  const cfg = options.config ?? loadConfig();
  const resolver: ModelResolver =
    options.modelResolver ??
    ((p, m) => resolvePlannerModel(p, { modelId: m, config: cfg }));

  const resolved = resolver(provider, options.modelId);
  const t0 = performance.now();

  const result = await generateText({
    model: resolved.model,
    output: Output.object({ schema: AdSpecSchema }),
    system: buildSystemPrompt(req),
    messages: [{ role: "user", content: buildUserContent(req) as never }],
  });

  const elapsedMs = Math.round(performance.now() - t0);
  return {
    provider,
    modelId: resolved.modelId,
    elapsedMs,
    spec: result.output,
    usage: result.usage
      ? {
          inputTokens: result.usage.inputTokens,
          outputTokens: result.usage.outputTokens,
          totalTokens: result.usage.totalTokens,
        }
      : undefined,
  };
}

export async function compareProviders(
  req: PlanRequest,
  options: {
    anthropicModel?: string;
    googleModel?: string;
    config?: PlannerConfig;
    modelResolver?: ModelResolver;
  } = {}
): Promise<CompareResult> {
  const providers: PlannerProviderName[] = ["anthropic", "google"];
  const settled = await Promise.allSettled(
    providers.map((p) =>
      planAdSpec(req, {
        provider: p,
        modelId: p === "anthropic" ? options.anthropicModel : options.googleModel,
        config: options.config,
        modelResolver: options.modelResolver,
      })
    )
  );

  const out: CompareResult = { errors: {}, summaryMarkdown: "" };
  settled.forEach((entry, idx) => {
    const p = providers[idx];
    if (entry.status === "fulfilled") {
      out[p] = entry.value;
    } else {
      out.errors[p] = entry.reason instanceof Error ? entry.reason.message : String(entry.reason);
    }
  });

  const rows: string[] = [
    `# Provider A/B Comparison — ${req.projectId}`,
    "",
    "| Provider | Model | Track | A-Genre / Style | Hook Title | First Caption | Elapsed |",
    "|---|---|---|---|---|---|---|",
  ];
  for (const p of providers) {
    const r = out[p];
    if (r) {
      const cap1 = r.spec.captions[0]?.text.replace(/\n/g, " / ") ?? "-";
      const tag = `${r.spec.a_genre_archetype ?? "-"} / ${r.spec.visual_style}`;
      rows.push(
        `| ${p} | \`${r.modelId}\` | \`${r.spec.track_archetype}\` | ${tag} | ${r.spec.title} | ${cap1} | ${r.elapsedMs}ms |`
      );
    } else {
      rows.push(`| ${p} | - | - | ERROR | ${out.errors[p] ?? "failed"} | - | - |`);
    }
  }
  out.summaryMarkdown = rows.join("\n");
  return out;
}
