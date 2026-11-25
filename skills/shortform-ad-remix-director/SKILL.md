---
name: shortform-ad-remix-director
description: Use when the user asks to plan, analyze, remix, script, generate hooks/voiceover for, assemble, or review 9:16 commerce Reels, Shorts, or TikTok ads—including controlled 0-5s A/B/C hook experiments (abc_remix) and 30s 3-stage narrative escalation masters (v2_narrative_master) with Google Flow video/Korean VO, 3-bus studio sound, and full-bleed kinetic captions.
principle: pro-quality
---

# Shortform Ad Remix Director

Turn raw client product demos, store detail-page videos, or fresh briefs into publish-ready **9:16 shortform video ads** (`abc_remix` controlled variants `ad_A/B/C.mp4` OR `v2_narrative_master` ~30s unified narrative masters like `ad_night_ramen_v2.mp4`) using source-first analysis, Google Flow video & native Korean voiceover generation, 3-bus studio audio mixing (VO + sidechain-ducked multi-stage stems + Foley SFX), full-bleed `PIL + FFmpeg` kinetic Korean typography, and safe `-14.0 LUFS` mastering.

> **Genre boundary**: Use this skill + `${CLAUDE_PLUGIN_ROOT}/skills/shortform-ad-hooks-blueprint/SKILL.md` for **product, app, and commerce performance video ads**. For 3D engineering/science documentaries use `cinematic-3d-explainer-director`; for fiction melodrama use `cinematic-ai-drama-director`; for client acquisition/Google Ads account billing use `ai-shortform-ad-business`.

## Two Core Production Modes

1. **`abc_remix` (`0-5s` A/B/C Hook Experiments + `20s` Shared Body)**: Isolate ONLY the opening `0-5s` (`A` absurd twist / `B` lifestyle bridge / `C` pain-point direct) atop an identical real-product body (`shared_body_cuts`).
2. **`v2_narrative_master` (`12-15s` 3-Stage Escalation -> `0.25s` Twist Pause -> `15s` Payoff)**: When short `3-5s` cold opens feel detached from product context, build a cohesive ~30s `timeline` master: `V1 -> V2 -> V3` (`12-15s` continuous story tension via Google Flow) -> `0.25s` `silence_gap` twist freeze -> real source product payoff (`P01..P08`) driven by a continuous Google Flow Korean VO arc and beat-drop soundtrack.

## Studio Pipeline (11 Stages · 3 QA Gates)

Delegate stages cleanly to isolated studio agents under `${CLAUDE_PLUGIN_ROOT}/skills/shortform-ad-remix-director/agents/ad-*.md` (symlinked inside `agents/` of this skill folder). Keep blind critics (`Gate S` and `Gate B`) strictly separated from strategy docs, reference breakdowns, and automated lint reports.

| Stage | Agent (`ad-*`) | Reads | Writes |
|---|---|---|---|
| 0 | `ad-strategist` | Client brief, `shortform-ad-hooks-blueprint/SKILL.md` | `00_strategy.md` |
| 0.5 (**Gate F**) | `ad-source-analyst` | Source MP4 + `ad_source_analyzer.py` + `00_strategy.md` | `analysis/source_*`, `refs/master_4cuts.jpg`, `00_product_facts.md` |
| 1 | `ad-hook-writer` | `00_strategy.md`, `00_product_facts.md`, blueprint (§1–4) | `01_abc_script.md` (or v2 narrative beat script) |
| 1.5 (**Gate S**) | `ad-critic` Mode 1 (blind) | `01_abc_script.md` + `00_product_facts.md` **ONLY** | `01_script_critique.md` |
| 2 | `ad-hook-writer` | Approved script, `analysis/source_metadata.json`, `vo_segments.json` | `05_ad_spec.json`, optional `04_abc_edit_guide.html` (`ad_abc_sheet_builder.py`) |
| 3 (**Gate A**) | `ad-prompt-engineer` | `05_ad_spec.json`, `00_product_facts.md`, `model-notes.md` | `05_jobs.json`, `05_credit_quote.md` (`ad_flow_jobs.py`), `05_package.md`, `05_lint_report.md` (`ad_gate_a_lint.py`) |
| 4 (**Gate B**) | `ad-critic` Mode 2 (fresh blind) | `05_package.md` + `04_abc_edit_guide.html` **ONLY** | `07_critique.md` (`_r2.md` max) |
| 5 | **User Credit Approval Gate** | `05_credit_quote.md` (`0 cr` refs + `360p`/`720p` wave quote), disclosure | User sign-off (optional `--preview-animatic` at `0 cr` beforehand) |
| 6 | `ad-generator` (`sonnet`) | `05_jobs.json`, `flow_automator.py` (`extract-first-frame`, `refs`, `video-batch`) | `refs/`, `clips/`, `audio/`, `08_generation_log.md` |
| 7 | `ad-assembler` (`sonnet`) | `audio/vo_manifest.json` -> `ad_audio_prep.py` -> `05_ad_spec.json` + `ad_remix_assemble.py` | `audio/vo_master.wav`, `final/*.mp4`, `_clean.mp4`, `.srt`, `review/qa_*_strip.png` |
| 8 | `ad-qc-reviewer` | **Direct playback (`read_file`) of rendered MP4 + `qa_*_strip.png`** + LUFS/ffprobe | `09_video_qc.md` (audio-first sync, zero BGM bleed, verbatim subtitle check) |
| 8.5 | `ad-assembler` + `ad-qc-reviewer` | `thumbs_spec.json` -> `ad_thumbnail_builder.py` + `read_file` on sheet/covers | `thumbnails/*.png` (`1080x1920`, `1:1` `y=420..1500` safe zone), `thumbnails_sheet.png` |
| 9 | `ad-strategist` | `00_strategy.md`, script, `09_video_qc.md` | `11_campaign_kit.md` (captions, Auto-DM scripts, 48h rubric) |

## 7 Core Architectural Rules

1. **Real-Source-First, Strictly Orthogonal A/B/C Genres, Zero Reskinning & Direct-Frame Truth**: When client footage exists, normalize raw VFR/HEVC/`.mov`/extensionless clips (`normalize-cfr`) and preserve real physical proof for payoff. Keep A/B/C **genre-orthogonal** (verified by `ad_gate_a_lint.py` Check 13 + `--compare-abc` + `--compare-campaigns`): **A (`A_bgrade_reversal`, 무맥락 반전 원리 — `bgrade-reversal-ad` & 고집돌우럭 원칙)** hijacks an alien `a_genre_archetype` (`noir_interrogation`, `romance_breakup`, `historical_drama`, `sports_var`, `courtroom_trial`, `sci_fi_contact`, `audition_judge`, `horror_mystery`, `mock_documentary`, `absurd_skit` — NEVER reskinning `"속보입니다"` / `"단 한 집만"` disaster-news clichés across campaigns) and flips one physical truth into intense `>= 45–60%` dramatic stakes (`0%` product words) -> `0.18–0.32s` `silence_gap` + genre-matched SFX -> serene real-product landing (`<= 55%`, no spec list); **B (`B_info_hook_offset`, `b-info-hook` `sim 0.4–0.6` 정보성 훅)** opens on an unrelated science/nature fact with concrete numbers (`0–7s`, `0%` product/PAS clichés) -> 1–2 bridges -> calm `"~습니다"` reveal; **C (`C_direct_proof`)** runs direct bright POV pain -> strongest kinetic proof cut first -> 2–3 verified USPs. Always inspect printed dial/body text directly on extracted frames via `read_file` before writing copy; set AI product props with `"strictly ZERO numbers, ZERO digits, ZERO text marks"`. Support Pure Organic Review mode (`disclosure: "ai_assisted"`, `cta.type: "comment_engagement"`, zero sales/group-buy labels).
2. **Product Fact Truth & Ad-Law Safety (`Gate F -> Gate S -> Gate A`)**: Every USP, caption, and promo claim must cite `[VERIFIED]` `[F##]` IDs in `00_product_facts.md`. Unverified superlatives (`완벽 방수`, `100% 효과`) and guessed discounts/dates are mechanically blocked by `ad_gate_a_lint.py`.
3. **Mixed Aspect-Ratio `9:16` Framing & Pre-Assembly Clip Strip QC**: `ad_source_analyzer.py` probes multi-source clips (`1:1 -> blur-bleed` to protect dials/props from horizontal clipping, `3:4 -> smart-crop`, `9:16 -> full-bleed`) and detects baked subtitles (`suggested_bottom_crop_px`). Combine primary `"type": "source"` and secondary real `"type": "video"` cuts with `"audio_owner": "mute", "gain_db": -60.0`. Explicitly set `"framing": "full-bleed", "bottom_crop_px": 0` on native `9:16` Flow cuts, keep `duration * speed <= actual_clip_duration`, and inspect `_qc/*_strip.png` before assembly to trim AI morph glitches (`src_start`/`duration`).
4. **Google Flow Hygiene, Tab Focus Guard & Batched Concurrency (`--concurrency 3`)**: Inspect live Flow tabs before submitting so you never collide on a tab rendering another project; open a dedicated project tab if busy. Prefer stylized `"visual_style"` **Blender 3D** presets (`blender_clay_diorama` for Track A, `blender_3d_cutaway` for Track B, `blender_isometric_toy`) via `ad_flow_jobs.py` whenever avoiding photorealistic AI artifacts in `0–12s` openers before switching to real client product footage. Extract anchors via `extract-first-frame`, generate `0 cr` `9:16` refs (`Nano Banana 2 Lite`), inspect `contact-sheet`, and batch visual + VO units together in `flow_automator.py video-batch --concurrency 3` (relying on `ensure_tab_active`, single-call `poll_wave_snapshot`, and settings fast-path caching to prevent 90s inactive-tab timeouts and bridge bloat). Author Flow Korean VO in phonetic Hangul (`<= 95` chars per 15s clip, digits spelled out like `이십오 분`/`육십 분`, prompt bookended with `"Starting promptly without delay..."` and `"2.0 seconds of quiet room silence at the end"`), inspect pauses with `ad_audio_prep.py --probe-islands`, listen via `read_file`, sub-slice via `vo_manifest.json` (`start_sec`/`end_sec`, `trim_edges: false`), and build captions verbatim from spoken words.
5. **100% Mute Original BGM & 3-Bus Studio Sound Redesign**: Never leave chopped client background music across jump cuts (`audio_owner: "mute"` on all cut segments). Build 3 discrete studio buses in `ad_remix_assemble.py`: (1) `vo_audio` (`highpass=85` + broadcast compression), (2) `bgm_timeline` (multi-stage stems keyed by VO `sidechaincompress`, stopping completely during `silence_gap`, slamming down on Act 2 transition with bar-1 `stem_offset_sec: 0.0`), and (3) sample-accurate stereo `sfx_events`. Master cleanly via 2-pass `ebur128` -> linear `volume + alimiter=limit=0.82:level=disabled` (`-14.0 LUFS`).
6. **Reels Kinetic Typography, Oversized Zero-Clip Cover Thumbnails & Safe Zones**: Render `reels_kinetic` captions (`**word**` highlight in `#FFE047`, heavy stroke without dark boxes, compact red-dot `pop_badge`), top-left disclosure pills, and fixed-coordinate CTA badges via `PIL` (`NotoSansCJKkr-Bold.otf`, max `2` lines, `<= 22` plain chars/line, `>= 1.2s` dwell, zero emojis). Build `1080x1920` cover thumbnails via `ad_thumbnail_builder.py` using `picturebooksub`-grade oversized bold typography (`116–134px`, `stroke_bold` / `line_blocks` / `panel_card` + automatic horizontal width fit) and `"strict_margin": true` (`x=56..1024`, `y=460..1460` inside both `1:1` `420..1500` & `3:4` `240..1680` with zero line clipping) + QA contact sheet.
7. **Mandatory End-to-End Real Playback & Thumbnail Visual QC (`check-actual-output`)**: NEVER approve any deliverable from LUFS numbers or silent strips alone. Watch and listen to every rendered `.mp4` end-to-end AND inspect `thumbnails_sheet.png` + individual `thumb_*.png` via `read_file`: verify verbatim VO-caption match, zero legacy BGM bleed, zero stray cut frames, clean twist dead-stop, and unobstructed `1:1` cover safe zones.

## Programmatic CLI Toolchain (`scripts/`)

Run all heavy work deterministically via scripts inside `${CLAUDE_PLUGIN_ROOT}/libraries/media-tools/`:

- `ad_source_analyzer.py` — `normalize-cfr` (raw VFR/HEVC/`.mov`/extensionless -> CFR `30fps` H.264), `analyze` (`ffprobe` + scene cuts + contact sheet + subtitle detection + aspect framing), `extract-strip`, `extract-frame`.
- `ad_audio_prep.py` — `--probe-islands` (speech-island & gap scanner), `--input` (single-take trim), `--manifest` (per-beat `start_sec`/`end_sec` slicing, speed, RMS loudness normalization, exact gaps -> `48kHz` stereo `vo_master.wav` + `vo_segments.json`; always pass `--out-wav` + `--out-json`).
- `ad_flow_jobs.py` — Compiles `05_ad_spec.json` (`variants` & `timeline` modes, with optional `visual_style` Blender 3D presets `blender_clay_diorama` / `blender_3d_cutaway` / `blender_isometric_toy`) into `05_jobs.json` (`Nano Banana 2 Lite` `0 cr` + `Omni 1.2 Flash` `x1` + Zero-Text tails) and `05_credit_quote.md`.
- `ad_abc_sheet_builder.py` — Builds portable HTML A/B/C Production & Edit Guide with SVG timeline & embedded stills.
- `ad_gate_a_lint.py` — 13-check Gate A static, cross-file & orthogonality validator (`variants` & `timeline` modes), plus `--compare-abc` and `--compare-campaigns` cross-campaign anti-reskin enforcement.
- `ad_remix_assemble.py` — Renders `abc_remix` (`--variant all`) or `v2_narrative_master` (`timeline` mode): `smart-crop`, `blur-bleed`, `reels_kinetic`, 3-bus `bgm_timeline` + VO-keyed `sidechaincompress` + stereo-downmixed `sfx_events`, `-14.0 LUFS` limiter, `.srt`, and `review/qa_*_strip.png`.
- `ad_thumbnail_builder.py` — Renders `1080x1920` Reels/Shorts cover thumbnails (`single` & `split_2panel` layouts, scrims, pills, headlines, rounded product inset cards) + `1:1` safe-zone (`y=420..1500`) QA contact sheet.
- `flow_automator.py` — Google Flow Chrome runner (`<subcmd> --tab <TAB_ID> ...`, supporting `extract-first-frame`, `refs`, `contact-sheet`, `extract-last-frame`, `video`, `video-batch` defaulting `--concurrency 3`, `download-top`) with proactive `ensure_tab_active` tab-focus recovery, single-call `poll_wave_snapshot`, settings-popover fast-path caching, compact-viewport `옵션 더보기 -> 미디어 다운로드` fallback, `stale_ref` JS tile-open fallback, `prev_keys` image completion polling, and `document_changed` SPA retry.

## Working Folder & Default Settings

- Project folder: `<workspace>/ad-studio/<project_slug>/`
- Supported modes: **`abc_remix`** (`0-5s` A/B/C hook + `20s` body) or **`v2_narrative_master`** (`12-15s` 3-stage escalation + `0.25s` twist freeze + `15s` payoff, `30s` total)
- Preferred Reels framing: **`smart-crop` + `blur-bleed`** (`editorial-card` only when client footage requires fixed border framing)
- Zero unapproved Flow credit spend: always clear Stage 5 before touching Chrome / `flow_automator.py`.
