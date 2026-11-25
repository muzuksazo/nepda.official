---
name: principle-only-hook-abstraction
description: Use whenever designing Track A or Track B shortform hooks from user examples, viral trends, memes, or brainrot references so agents extract only the underlying retention mechanism and invent a 100% original world/object instead of copying surface nouns, characters, songs, or IP.
---

# Principle-Only Hook Abstraction (원리 추출 · 표면 복제 금지)

> **Core Rule**: Never copy concrete surface objects, characters, songs, dances, memes, or IP from user examples or trend references. Extract **only** the cognitive/sensory retention principle ("why viewers stop scrolling without thinking"), then invent a **100% original** world, object, and rhythm cue.

---

## 1. Commercial Copyright & Anti-Reskin Safety

- **Never crawl or V2V-reskin third-party viral videos/music** for commercial client/SaaS ads (derivative copyright + music licensing + publicity-right risk).
- **Never copy concrete objects or trends mentioned as examples** by the user or reference library (e.g., if the user says *"like spinning screws or Soda Pop brainrot vibe"*, *"screw"* and *"Soda Pop"* become **forbidden surface nouns**, NOT assets to generate).
- Recreate the **abstract retention grammar** (loop tension, beat lock, incongruity, hard-stop flip) using 100% original Blender 3D / clay / cutaway / isometric worlds and royalty-free audio + Foley SFX.

---

## 2. 3-Step Extraction & Invention Protocol

### Step 1 — Surface Taboo Lock (`reference_surface_taboo`)
Before brainstorming any scene:
1. Extract every concrete noun, IP, song title, dance/challenge name, or meme proper noun from the user's example or trend reference (both Korean and English variants).
2. Store them in `spec.reference_surface_taboo` (e.g. `["나사", "screw", "소다팝", "soda pop"]`).
3. Populate `spec.product_taboo_keywords` (product names, brand terms) and `spec.category_taboo_keywords` (room/environment/function clues such as `["욕실", "세면대", "물기", "수건", "걸레", "타일", "bathroom", "moisture", "towel"]` for a bathroom water-sponge).

### Step 2 — Mechanism Distillation (What Actually Holds Attention)
Strip away visuals/characters and identify which abstract retention mechanism drives the reference:

| Archetype (`a_genre_archetype`) | Underlying Retention Principle | Mechanical Execution (`0–9s` Cold Opener) |
| :--- | :--- | :--- |
| **`brainrot_hypnosis`** | **Zeigarnik Micro-Convergence Loop** (미완결 수렴 긴장) | A continuous, near-complete spatial alignment, gravity balance, orbit, or countdown that approaches completion across 3 beats — keeping the brain locked until the final millimeter triggers `silence_gap`. |
| **`deadpan_rhythmic_loop`** | **Locked Beat Cadence + Deadpan Incongruity** (리듬 최면 + 무표정 부조화) | Hypnotic 4-beat tempo + completely deadpan/poker-faced abstract 3D figures performing bizarrely serious non-sequitur rituals with zero explanation. |
| **`sensory_sync_loop`** | **Frame-Locked Tactile / Audio Sync** (시청각 1프레임 동기 쾌감) | Oddly satisfying polymer-clay/glass/magnetic physics where visual deformation, bounce, or snap hits exact acoustic transients before an abrupt stop. |
| **Genre-Hijack (`noir_interrogation`, `courtroom_trial`, `sci_fi_contact`, etc.)** | **Alien Stake Transposition** (무맥락 장르 탈취) | Transpose one abstract physical property of the product into an unrelated dramatic conflict with zero category setting leaks. |

Always end the hypnotic/dramatic hook with **`silence_gap` (`0.18–0.32s`)** + genre-matched SFX hard cut -> deadpan real-product payoff (`<= 55%` of total runtime).

### Step 3 — Double-Zero Invention Gate
Every invented Track A concept must pass **both** zero-leak checks before prompt generation (`ad_gate_a_lint.py` Check 13):
1. **0% Reference Surface Leak**: Zero `reference_surface_taboo` terms in pre-twist captions, `pop_badge`, `header_tag`, `flow_ref_prompt`, or `flow_video_prompt`.
2. **0% Product & Category Leak**: Zero `product_taboo_keywords` AND zero `category_taboo_keywords` (never place a bathroom sponge ad inside a miniature bathroom/sink diorama during the Track A hook!) before the twist `silence_gap`.

> For Track B (`B_info_hook_offset`), apply the same guard to `product_taboo_keywords` and `reference_surface_taboo` across the **entire** pre-bridge window before `silence_gap` (e.g., say `"해면동물"`, never `"바다 스펀지"` until the product payoff).

---

## 3. Bad (Surface Copy) vs. Good (Principle-Only Invention)

| User Prompt / Reference | BAD — Surface Copy (Forbidden) | GOOD — Principle-Only Original Invention |
| :--- | :--- | :--- |
| *"나사가 뺑뺑 도는 brainrot 느낌"* | Infinite metal screws spinning into bolts | `brainrot_hypnosis`: Floating matte-clay geometric monoliths endlessly rotating `359°` around a glowing center without ever clicking shut — until the final `0.1°` freezes dead (`silence_gap`) and snaps into real product proof |
| *"소다팝 같은 4박자 밈 바이브"* | Crawling Soda Pop video or parodying soda cans dancing to the song | `deadpan_rhythmic_loop`: Deadpan pastel polymer-clay cube creatures nodding in strict `128 BPM` isometric formation to original royalty-free percussive pops, stopping abruptly mid-beat -> dry real-product reveal |
| *"흡수력 광고 A안 (물기 제거 스펀지)"* | Clay detective in a **bathroom** looking at a **dry tile floor** without **towels** | Abstract void / surreal miniature observatory where weightless ink spheres vanish cleanly on contact with an unseen matte monolith — **0% bathroom, 0% tiles, 0% water drops, 0% towel/sponge clues** |
