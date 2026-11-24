# Shortform Product Ad Model & Prompt Notes (Google Flow Native)

Reference for generating `0–5s` A/B/C opening hooks, `12–15s` 3-stage narrative escalation clips, and studio Korean voiceover beats in **Google Flow** (`Nano Banana 2 Lite` + `Omni 1.2 Flash` parallel `video-batch`) paired with real client/brand demo footage. External third-party video generators are strictly excluded.

---

## 1. Credit Economics & Real-Product Reference Injection

When brand/client demo footage exists, keep the product payoff at `0 cr` and spend Google Flow credits ONLY on narrative opening visuals (`720p`) and studio Korean voiceover tracks (`360p` video-audio):

- **Step 0 — Extract Product Anchors (`0 cr`)**:
  - Run `flow_automator.py extract-first-frame` on clean hero frames in `source_video` (`REF_PRODUCT`, `BRIDGE_*`).
- **Step 1 — Generate `9:16` Story Plates (`Nano Banana 2 Lite`, `0 cr` on ULTRA, `x1`)**:
  - Build visually continuous plates for either 3 orthogonal hooks (`R_A/R_B/R_C`) or a 3-stage problem escalation (`R_V1` trigger -> `R_V2` spatial obstacle -> `R_V3` payoff labor punchline), matching exact time-of-day lighting (e.g., `3000K` late-night apartment bedroom -> `4500K` fluorescent kitchenette).
  - Verify plates via `flow_automator.py contact-sheet` and preview cut pacing at `0 cr` via `ad_remix_assemble.py --preview-animatic`.
- **Step 2 — Generate Parallel Motion (`Omni 1.2 Flash`, `x1`, `video-batch`)**:
  - `360p` fast test (`1 cr/s`, max `15s` per clip = `15–20 cr`), `720p` crisp master (`3 cr/s`, `5s` clip = `15 cr`).
  - Typical 3-stage v2 buildup (`V1` `5s`, `V2` `5s`, `V3` `5s` at `720p` = `45 cr`) + 2–3 VO studio tracks (`360p` `10–15s` = `20–32 cr`) runs `~65–77 cr` total.
- **Automation (`ad_flow_jobs.py`)**: Run `ad_flow_jobs.py --spec 05_ad_spec.json --out-jobs 05_jobs.json --out-quote 05_credit_quote.md` to compile `abc_remix` specs with `x1` credit guards and Zero-Text tails.

---

## 2. Google Flow Native Korean Voiceover Workflow (`Omni 1.2 Flash`)

`Omni 1.2 Flash` (`360p`, `9:16`, `x1`) produces remarkably natural Seoul Korean voiceover acting when prompted as a **static close-mic acoustic vocal booth recording**:

1. **Phonetic-Hangul Vocal Booth Template (`<= 90–96` chars / 15s clip)**:
   - Write all numerals and units in **phonetic Hangul** (`이십오 분`, `육십 분`, `단 삼 초`, `한 시간`) inside the Flow prompt so `Omni 1.2 Flash` never stumbles or misreads Arabic digits. Keep Korean spoken line lengths `<= 90–96` chars per `15s` beat so pacing stays relaxed with clean tail breathing room.
   - Prompt: `Starting promptly without delay, static medium close-up of a young 28-year-old Korean voice actor in a matte black pullover hoodie standing before a large studio condenser microphone and black pop filter inside a dark acoustic foam vocal booth, speaking crisply in natural Seoul Korean, "<EXACT_PHONETIC_HANGUL_LINE>". Sound: dry studio close-mic broadcast vocal ONLY, crisp consonant articulation, finishes cleanly with 2.0 seconds of quiet room silence at the end, zero background music, zero echo, zero SFX. No background music, no singing, zero readable text, no subtitles, no watermarks.`
   - Always extract ONLY the audio (`-vn -ar 48000 -ac 2 -c:a pcm_s16le`) — never use the vocal-booth visual in the ad.
2. **Keeping Same Voice Across >15s Scripts**:
   - Max single `Omni 1.2 Flash` clip duration is `15s`. Flow blocks `/edit/` Extend on clips longer than `15s`.
   - For multi-part narration (`VO_01` `15s` + `VO_02` `10s`): either use Flow **Extend** (`연장`, `10 cr` for `+10s`) inside `/edit/` to preserve the exact booth acoustics and voice actor, OR keep `VO_03` (`10s`, `12 cr`) with identical booth/age/mic wording and normalize loudness per beat.
3. **Mandatory Listening, Island Probing & Sub-Phrase Slicing (`ad_audio_prep.py`)**:
   - Even with `2.0s` tail silence instructions, models occasionally emit stray breath clicks at `14.8–15.0s` or drop/rephrase a connecting word (`"그래서 저는"` omitted). Always **listen directly via `read_file`** on every raw VO `.mp4`/`.wav` and run `ad_audio_prep.py --probe-islands --input raw_vo.mp4 --silence-db -39.0 --min-silence 0.08` to inspect exact inter-phrase gaps.
   - Sub-slice individual phrases directly inside `vo_manifest.json` using per-beat `"start_sec"`, `"end_sec"`, `"trim_edges": false`, and exact `"gap_after"` (`0.26–0.30s` pre-twist silence), then build `audio/vo_master.wav` + `audio/vo_segments.json` via `ad_audio_prep.py --manifest vo_manifest.json --out-wav audio/vo_master.wav --out-json audio/vo_segments.json` (note explicit `--out-wav` and `--out-json` flags).
   - Build `05_ad_spec.json` timelines and verbatim kinetic subtitles strictly FROM `vo_segments.json` and your actual listening log — never before hearing the final audio.

---

## 3. Six-Layer Zero-Text Hook Prompt Formula (`Omni 1.2 Flash` / `Nano Banana 2 Lite`)

Every visual prompt submitted via `05_jobs.json` follows this strict 6-layer structure:

1. **Camera & Format Lock**: Single continuous shot (`9:16 vertical frame`), specifying focal length and one physical camera movement (`slow macro push-in`, `handheld 1st-person POV walk-in`, `overhead close-up`). Add `strictly no camera cuts`.
2. **Physical Subject & Single Action**: Concrete observable object + motion only (`right hand gently flips matte-black smartphone face-down onto rumpled charcoal blanket`, `placing cream rubber dishwashing gloves on stainless counter`). Never ask Flow for UI text or brand labels on screen unless an approved `R..` photo is attached.
3. **Palette, Surface & Lighting Continuity**: Match exact color temperature across adjacent cuts (`3000K` warm bedroom lamp -> `4500K` cramped kitchenette fluorescent).
4. **Photoreal Look / Texture**: Authentic handheld smartphone realism or studio close-up — avoid plastic CGI bloom.
5. **Physical SFX & Room Tone Only**: Describe room ambience (`soft fabric rustle`, `faint fridge hum`), knowing `ad_remix_assemble.py` (`audio_owner: "mute"`) will replace clip audio cleanly with the 3-bus studio mix.
6. **Zero-Text, Zero-Digit Prop & Anti-Sigh Hard Exclusion Tail**:
   - Required tail: `No camera cuts, zero readable text, no typography, no subtitles, no watermarks, no logos, no music.`
   - **Zero-Digit AI Prop Rule & Local Upload Fallback**: When generating AI lifestyle stills or video plates containing dials, timers, screens, or meters without reference upload (or when Chrome `extension` backend blocks `upload_files` on hidden `<input type="file">` with `-32000 Not allowed`), fall back cleanly to a `0 cr` `Nano Banana 2 Lite` text-anchored plate describing exact industrial shape/color ratios PLUS `"completely blank smooth unmarked face with strictly ZERO numbers, ZERO digits, ZERO text marks"`, verify via `read_file`, and leave all readable scale/number proof to real client footage.
   - Keep human posture concrete (`calm grounded posture, steady hand placement`) rather than melodramatic sighing.

### Bridge-Shot Pairing Pattern (`Frames-to-Video`)

1. Run `ad_source_analyzer.py extract-frame --input source.mp4 --time 2.3 --out refs/BRIDGE_A.png` (or `flow_automator.py extract-first-frame`).
2. Generate `R_A_start` (`Nano Banana 2 Lite`, `0 cr`, `9:16`).
3. Submit `Omni 1.2 Flash` in `frames` mode with `first_frame` + `last_frame`.

---

## 4. Flow DOM Resilience, Tab Hygiene & macOS Assembly Constraints

- **Flow Chrome Automation (`flow_automator.py`)**:
  - **CLI Flag Placement & Tab Hygiene**: Always place `--tab <TAB_ID>` AFTER the subcommand (`flow_automator.py inspect --tab <TAB_ID>`, `refs --tab <TAB_ID>`, `video-batch --tab <TAB_ID>`). Inspect live tabs first; if an existing Flow tab is actively rendering (`%` progress or another project's prompts), **never touch or cancel it** — open a clean `새 프로젝트` tab instead.
  - **Compact-Viewport Hardening**: In compact viewports (`~1147x530`), `button[aria-label="미디어 다운로드"]` collapses inside `button[aria-label="옵션 더보기"]`, grid clicks can hit `stale_ref: target changed`, SPA transitions trigger `document_changed`, and signed URLs can rotate mid-poll. `flow_automator.py` enforces: (1) `document_changed` SPA retries in `ugot()`, (2) JS `PointerEvent` + `.click()` radio selection + `rem_len <= 20` submit verification, (3) upper-band tile click (`_open_tile_to_lightbox`) with `stale_ref` JS `img, video` + ancestor click fallback, (4) `prev_keys` (`src_key` set membership + `!still_running`) polling in `generate_ref`, and (5) `_open_lightbox_download_menu` auto-falling back to `옵션 더보기 -> 미디어 다운로드` while filtering out outer menu items (`즐겨찾기`/`공유`/`휴지통`).
- **macOS Sound Palette & `ffmpeg 8.0.1` Constraints**:
  - **Apple Loops & FCP Foley Stems (`/Library/Audio/Apple Loops/Apple/`)**: Pair continuous stem packs for clean Act transitions — e.g. `07 Chillwave` (`Brooklyn Nights` / `Pastel Colors Beat 01`), `01 Hip Hop` (`Epoch`, `City Nights`, `Empire State`, `Distant Memories`) — and sample-accurate `.caf` Foley (`Ratchet FX`, `Click Off FX`, `Computer Keyboard`, `Bell Small`, `Bell Transition`, `Air Reverse Burst 1`, `Turntable Scratch 2`, `LFE Hit Impact 04`).
  - Never rely on FFmpeg `drawtext`, `subtitles`, or `libass` filters (unavailable here); render all Korean captions, `pop_badge` pills, disclosure badges, CTA bars, and cover thumbnails (`ad_thumbnail_builder.py`) via `PIL` (`NotoSansCJKkr-Bold.otf`).
  - Never import `matplotlib` or `scipy` (broken Anaconda ABI on host); use `numpy` + `subprocess` `ffmpeg` (`_decode_audio_f32` downmixes multi-channel `.caf` SFX cleanly to `48kHz` stereo).
  - Never pass silence gaps straight into `loudnorm` (throws `NaN`); always use 2-pass `ebur128` -> `volume + alimiter=limit=0.82:level=disabled` -> `ebur128` verification (`-14.0 LUFS`).
