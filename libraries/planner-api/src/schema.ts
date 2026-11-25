import { z } from "zod";

export const VALID_VISUAL_STYLES = [
  "blender_clay_diorama",
  "blender_3d_cutaway",
  "blender_isometric_toy",
  "photoreal",
] as const;

export const VALID_A_GENRE_ARCHETYPES = [
  "noir_interrogation",
  "romance_breakup",
  "historical_drama",
  "sports_var",
  "courtroom_trial",
  "sci_fi_contact",
  "audition_judge",
  "horror_mystery",
  "mock_documentary",
  "absurd_skit",
  "brainrot_hypnosis",
  "deadpan_rhythmic_loop",
  "sensory_sync_loop",
] as const;

export const VALID_TRACK_ARCHETYPES = [
  "A_bgrade_reversal",
  "B_info_hook_offset",
  "C_direct_proof",
] as const;

export const TimelineSegmentSchema = z.object({
  id: z.string().min(1),
  type: z.enum(["flow_video", "source", "video", "image", "silence_gap"]),
  framing: z.enum(["editorial-card", "smart-crop", "blur-bleed", "full-bleed"]).optional(),
  duration: z.number().positive().optional(),
  src_start: z.number().nonnegative().optional(),
  src_end: z.number().positive().optional(),
  speed: z.number().positive().optional(),
  bottom_crop_px: z.number().int().nonnegative().optional(),
  audio_owner: z.enum(["vo", "native_hook", "source_audio", "mute", "sfx_only", "silence"]).optional(),
  gain_db: z.number().optional(),
  path: z.string().optional(),
  fallback_image: z.string().optional(),
  flow_unit_id: z.string().optional(),
  flow_ref_id: z.string().optional(),
  attach_ids: z.array(z.string()).optional(),
  flow_mode: z.enum(["ingredients", "frames"]).optional(),
  flow_duration_sec: z.number().int().min(3).max(15).optional(),
  human_present: z.boolean().optional(),
  visual_style: z.enum(VALID_VISUAL_STYLES).optional(),
  flow_ref_prompt: z.string().optional(),
  flow_video_prompt: z.string().optional(),
  fact_ids: z.array(z.string()).optional(),
});

export const CaptionCueSchema = z.object({
  start: z.number().nonnegative(),
  end: z.number().positive(),
  text: z.string().min(1),
  pop_badge: z.string().optional(),
  header_tag: z.string().optional(),
  y_pos: z.number().int().optional(),
  is_cta: z.boolean().optional(),
});

export const AdSpecSchema = z.object({
  project_id: z.string().min(1),
  output_stem: z.string().min(1),
  title: z.string().min(1),
  visual_style: z.enum(VALID_VISUAL_STYLES).default("blender_clay_diorama"),
  mode: z.enum(["narrative_master", "abc_remix", "decision_15s", "bumper_6s"]).default("narrative_master"),
  track_archetype: z.enum(VALID_TRACK_ARCHETYPES),
  a_genre_archetype: z.enum(VALID_A_GENRE_ARCHETYPES).optional(),
  hook_similarity_score: z.number().min(0).max(1).optional(),
  product_taboo_keywords: z.array(z.string()).default([]),
  category_taboo_keywords: z.array(z.string()).default([]),
  reference_surface_taboo: z.array(z.string()).default([]),
  hook_window_sec: z.number().positive(),
  framing_mode: z.enum(["editorial-card", "smart-crop", "blur-bleed", "full-bleed"]).default("full-bleed"),
  disclosure: z.enum(["paid_ad", "sponsored", "own_brand", "ai_assisted", "none"]).default("ai_assisted"),
  source_video: z.string().min(1),
  source_duration: z.number().positive(),
  allow_static_intro: z.boolean().default(true),
  vo_audio: z.string().min(1),
  usps: z
    .array(
      z.object({
        title: z.string().min(1),
        fact_ids: z.array(z.string()).min(1),
      })
    )
    .min(1),
  timeline: z.array(TimelineSegmentSchema).min(2),
  captions: z.array(CaptionCueSchema).min(1),
  cta: z.object({
    type: z.string().min(1),
    copy: z.string().min(1),
    badge_copy: z.string().optional(),
    show_from_sec: z.number().nonnegative().optional(),
    start_sec: z.number().nonnegative().optional(),
    fact_ids: z.array(z.string()).optional(),
  }),
});

export type AdSpec = z.infer<typeof AdSpecSchema>;
export type VisualStyle = (typeof VALID_VISUAL_STYLES)[number];
export type TrackArchetype = (typeof VALID_TRACK_ARCHETYPES)[number];
export type AGenreArchetype = (typeof VALID_A_GENRE_ARCHETYPES)[number];
