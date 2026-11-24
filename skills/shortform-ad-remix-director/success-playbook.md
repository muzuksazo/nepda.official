# Shortform Ad Remix Success Playbook & QA Checklists

Operational field rules distilled from Korean commerce Reels, Shorts, and TikTok group-buy (`공구`) ad production. Treat structures as controlled hypotheses verified over 48-hour live metrics, never guaranteed virality claims.

---

## 1. Narrative Structure Selection: `30s Narrative Master` vs `0–5s A/B/C`

Pick the opening architecture to fit user intent and source footage:

1. **Cohesive ~30s Brand Hero / Persuasive Story (`v2_narrative_master`)**:
   - Avoid razor-thin `2–3.5s` random gimmicks when viewers need emotional & logical buy-in before seeing the SKU.
   - Run a **12–15s 3-Stage Escalation** (`V1` trigger/time-cost -> `V2` spatial obstacle -> `V3` quantified effort punchline, e.g. `"3분 라면 하나에 47분 중노동"`) -> **`0.25s` dead-stop silence freeze** (`TWIST_FREEZE`) -> **`15s` seamless product payoff** (`P01..P08`) driven by continuous Korean VO and beat drop.
   - Audio-First Workflow: Generate & clean Flow Korean VO tracks (`VO_01..03`), audit spoken lines directly via `read_file`, run `ad_audio_prep.py --manifest` -> lock `vo_segments.json`, then cut visuals cleanly to exact VO timestamps.
2. **Controlled & Orthogonal Hook Matrix (`A / B / C` Anti-Overlap Playbook, QC Order `C -> B -> A`)**:
   - Never ship 3 superficial wordings of the same routine pain-point. Keep each variant strictly distinct:
     - **Track A (`무맥락 기하 매치컷 반전`)**: `0–8s` zero category/problem hint -> unrelated high-intrigue scene sharing exact shape & accent color -> `Turntable Scratch` + `0.28s` dead silence -> geometric match-cut onto real product + closing metaphor callback.
     - **Track B (`맥락인 듯 맥락 아닌 심리·무드 훅`)**: Zero explaining, zero lecturing, zero documentary narrator voice (fixes the "B collapses into C" bug). Use 1st-person atmospheric/psychological curiosity (`"이상하게..."`) + subtle behavior restraint visual -> honest low-key product review.
     - **Track C (`실용/루틴 직격형`)**: Immediate POV obstacle + reset -> open product proof on the strongest kinetic action shot first.
   - Build `0 cr` plates (`R_*`) + preview pacing (`--preview-animatic`) -> parallel wave `video-batch` -> inspect every `_qc/*_strip.png` -> assemble & QC **`C -> B -> A`**.

---

## 2. Raw Phone Normalization, Mixed Aspect-Ratio Framing & Subtitle Removal

Raw phone uploads (`3:4` portrait `.mov`, VFR `25–29fps` HEVC, extensionless files) and `1:1` / `16:9` brand demos require clean pre-normalization and per-aspect framing:

- **CFR `30fps` Normalization First**: Always normalize raw user videos via `ad_source_analyzer.py normalize-cfr` before cutting, so `-ss` frame seeks never drift. Combine main `"type": "source"` and secondary real `"type": "video"` cuts with `"audio_owner": "mute", "gain_db": -60.0` to silence room chatter.
- **Per-Aspect Framing Matrix (`smart-crop` + `blur-bleed` + `full-bleed`)**:
  - **`1:1` Gauges/Dials & Wide Props (`blur-bleed`)**: NEVER apply `smart-crop` to `1:1` precision dials or multi-object frames (horizontal crop clips peripheral numbers/hands). Render sharp centered (`card_y: 330`) over `gblur=sigma=32`, keeping captions strictly below the card bottom border (`y_pos: 1385`).
  - **`3:4` / Narrow `1:1` Single-Subject Cuts (`smart-crop`)**: Strip client bottom subtitles (`bottom_crop_px: 152–162` on `1080x1080`) and fill `1080x1920` with tuned `crop_x_ratio` and subtle `punch_zoom: 1.04`.
  - **Native `9:16` Flow Cuts (`full-bleed`)**: Set `"framing": "full-bleed", "bottom_crop_px": 0` explicitly so root `bottom_crop_px` never crops Flow footage, and ensure `duration * speed <= actual_clip_duration`.
- **Legacy Fallback (`editorial-card`)**: Only when a campaign requires fixed dark studio borders (`#12141A`, top caption `y = 200..390`, bottom CTA `y = 1488`).

---

## 3. 3-Bus Studio Sound Redesign (Zero Choppy Source BGM)

Chopping and speeding up a client video's existing bright marimba/pop track across 8 cuts sounds amateur:

1. **Mute 100% of Original Cut Audio**: Set `audio_owner: "mute"` on every source cut and generated hook clip when running unified narration.
2. **Continuous 2-Stage Musical Clock (`bgm_timeline`)**:
   - **Act 1 Tension (`0.0s .. t_twist - 0.15s`)**: Sparse minor keys stem only (`City Nights Electric Piano.caf`, `-15 dB`), ducked cleanly by VO `sidechaincompress` (`ratio=6`).
   - **Twist Dead-Stop (`0.26s`)**: Complete BGM + VO silence freeze preceded by a tight scratch/stop SFX (`Turntable Scratch 1.caf`).
   - **Act 2 Payoff & Drop**: Sparse bass+keys buildup (`t_twist_end .. t_drop`), then full 3-stem beat drop (`Beat + Bass + Keys`, `-10.8 dB`, `stem_offset_sec: 0.0` so downbeat 1 lands squarely on the physical plug/activation cut!) sucked in by reverse whoosh + LFE sub-thump.
3. **Sync Foley Accents (`sfx_events`)**: Ground key visual cuts with real FCP `.caf` sounds (`Bell Small`, `Dishes`, `Boiling Water`, `Bell Transition` on CTA), mixed at subtle support gain (`-21 dB` to `-11 dB`) and mastered to **`-14.0 LUFS`**.

---

## 4. Reels Kinetic Captions & Safe-Zone Geometry (`1080x1920`)

- **Reels Kinetic Style (`reels_kinetic`)**: Replace heavy dark rounded rectangles with crisp outlined display type (`stroke_width=8`), highlighting `1–2` anchor words per cue with `**keyword**` (`#FFE047`) plus a compact top-center red-dot badge (`pop_badge`).
- **Safe Box**: Top header clear `y >= 145` (`자사제품`/`유료광고` badge top-left), floating subtitles centered safely around `y = 1220..1420` (above Instagram caption drawer `> 1600`), CTA badge anchored within `x = 72..852, y = 1480` (clear of right engagement rail `x > 880`).
- **Reading Comfort**: Max `2` lines per cue, `<= 22` plain chars/line, `>= 1.2s` screen time per cue (no `<1.0s` flashes), zero emojis.

---

## 5. Mandatory Pre-Ship Playback Audit Checklist (`check-actual-output`)

NEVER deliver based only on LUFS stats or static thumbnails. Open the rendered `.mp4` directly via `read_file` and verify every item:

1. **Verbatim Subtitle-to-VO Lock**: Does every caption cue match the exact Korean words the voice actor actually spoke (no stale script phrasing left behind)?
2. **Boundary Frame Cleanliness**: Inspect every `source` transition (`P01..P08`) — verify zero 0.1–0.2s stray frames from adjacent client cuts and zero orange client subtitle edges peeking at the bottom.
3. **Blur-Bleed Card Margin Check**: Confirm `reels_kinetic` captions sit completely outside sharp `blur-bleed` card borders.
4. **Audio Bus Verification**: Confirm `0%` legacy marimba bleed, smooth tone/loudness continuity between `VO_01 -> VO_02 -> VO_03`, unmistakable `0.25s` twist dead-stop, and punchy Act 2 beat drop.
5. **Pre-Assembly Clip Contact-Strip Defect Audit (`_qc/*_strip.png`)**: Before running full video assembly, visually inspect multi-frame strips of every generated Flow video (`flow_automator.py` / `ad_source_analyzer.py extract-strip`) via `read_file` to trim late-frame AI hand/pen morphs (`src_start`/`duration`) and reject hallucinated dial numerals early.
6. **Cover Thumbnail Visual Audit (`thumbnails_sheet.png`)**: Confirm every face, pill badge, headline, and rounded product card stays strictly inside the `1:1` cyan safe-zone band (`y = 420..1500`) on `thumbnails_sheet.png`, and individual upload covers carry zero guide lines or emojis.

---

## 6. Advertising Law, Organic Review Mode, Cover Thumbnails & 48-Hour Matrix

- **Ad-Law Guard & Organic Review Mode (`표시광고법`)**: Block unverified superlatives (`완벽 방수`, `100% 효과`, `기적의`, `국내 최초`, `부작용 제로`) unless substantiated under `## Whitelisted Claims`. Keep unconfirmed promo figures as `단 O일 한정`. When producing non-sponsored organic reviews, remove unrequested sales badges (`자사제품`/`공구 진행중`), set `disclosure: "ai_assisted"` (`AI 연출 포함`), verify product housing text directly on extracted source frames, and close with an open question CTA (`cta.type: "comment_engagement"`).
- **1:1 Safe-Zone Cover Thumbnail Checklist (`ad_thumbnail_builder.py`)**: Build `1080x1920` covers tailored per hook (`split_2panel` reaction+prop for A, moody single for B, bright POV + rounded product inset card for C) keeping all faces, pills, headlines, and inset cards inside `y = 420..1500` (`1:1` profile-grid center crop); visually inspect `thumbnails_sheet.png` + individual `thumb_*.png` via `read_file`.
- **Single-Action Comment-DM CTA**: For sales/lead campaigns, use one concrete `2–4` syllable keyword (`댓글에 '키워드' 남기면 링크 DM`), echoed in caption first line and pinned comment.
- **48-Hour 2-Axis Evaluation**: Judge A/B/C variants across **Axis 1 (3s hold >= 35%, watch time, shares)** and **Axis 2 (Comment-DM or engagement saves/conversions per 1K views)** before scaling winning creative beats.
