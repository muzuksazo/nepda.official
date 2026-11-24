# Shortform Ad Hooks Reference Breakdown (Clean Room Archive)

> **ISOLATION WARNING**: This file is an offline case-study archive for human architects and blueprint maintenance ONLY. Production agents (`ad-hook-writer`, `ad-prompt-engineer`, `ad-strategist`, `ad-critic`) MUST NOT read this file during live ad generation and MUST NEVER reuse its brand names, exact jokes, or shot sequences. Creative patterns are documented strictly as structural hypotheses, not guaranteed campaign outcomes.

---

## Case 1: Mooas Mug Pot 36s Original -> 25s A/B/C Hook-Only Variable Remix

Source specimen inspected directly (`1080x1080`, `30fps`, `36.06s`, `aac 44.1kHz stereo`): Naver/Coupang-style square commerce product demo for a stainless inner-pot electric ramen/multi-cooker with detachable power cord, silicone port cover, 2-level circular dial, and steamer rack.

### Raw Source Timecode Map (`36.06s` Square Master)
- `00:00–00:01.3`: Static hero frame + title slate (*"간편한 감성 한 끼 / 머그팟 라면포트 멀티쿠커"*). Low 1-second scroll-stop power -> **trimmed out of shared body**.
- `00:02.0–00:06.5`: Glass lid lifts over rolling boil inside stainless pot -> plugging in detachable power cord -> turning circular dial (Level 1 / 2), orange bottom subtitle (*"가스레인지나 인덕션 없이 전기코드만 꽂으면 OK!"*).
- `00:07.0–00:15.5`: 8-dish speed demo montage — egg ramen (`00:07`), hotpot/nabe (`00:08`), fish cake soup (`00:09`), steamed dumplings (`00:10`), steamed eggs (`00:11`), 3-min curry pouch (`00:12`), Hetbahn rice (`00:13`), tteokbokki (`00:14–00:15`).
- `00:16.0–00:21.5`: 1-burner apartment stove context + moving product without cord by wood handle to sunny table (*"인덕션 1구만 있는 1인 가구에 요리팟 하나 더 쓸 수 있어 꿀" / "분리형 코드로 이동도 간편!"*).
- `00:22.0–00:25.5`: Silicone port "smile cover" flip close-up with hand-drawn emphasis ticks (*"코드 꽂는 부분에 스마일커버가 있어 세척할 때도 걱정 없어요:)"*).
- `00:26.0–00:35.8`: Boiling noodles (`00:26–00:27`), white+wood aesthetic full shot (`00:28–00:31`), close-up bubbling pot closing beat (`00:32–00:35`).

### Why `a_b_c_3.html` Split Only `0–5s` While Locking `5–25s`
- Re-shooting 25s three times would waste studio time and break trust in real stainless-pot boiling physics.
- Compressing `00:02–00:35` (skipping `00:00–00:01` static slate) into `20s` created a single **Controlled Common Master (`5–25s`)**:
  - `05–09s`: Src `00:02–00:06` at `1.2x` (Core mechanism: lid boil + plug + 2-level dial).
  - `09–14s`: Src `00:07`, `00:10–00:13` at `0.8–1.0s/cut` (4-in-1 range: ramen, dumpling steam, egg steam, pouch heat-up).
  - `14–18s`: Src `00:19–00:24` (Detachable cord portability + silicone port cover for stress-free washing).
  - `18–21s`: Src `00:26–00:31` (Noodle drop + white/wood tabletop reveal).
  - `21–25s`: Src `00:32–00:35` (Bubbling close-up under locked CTA + comment-keyword Auto-DM banner).
- Three `0–5s` Hook Forks tested orthogonal creative hypotheses while bridging cleanly into real source footage at `3.5s` or `2.0s`:
  - **Variant A (Absurd Fake-Doc Twist)**: `0–3.5s` dark studio macro boiling glass flask (deadpan pseudo-thermodynamics narration + heart-thump swell -> `0.2s` hard silence) -> `3.5–5.0s` snap cut to bright real lid-open (`00:02.5`) + ramen (`00:07`).
  - **Variant B (Natural Lifestyle Bridge)**: `0–3.5s` 11 PM late-night bed collapse POV after seeing long food-delivery ETA -> eyeline shifts naturally to warm-lit cream cooker steaming on dorm desk -> `3.5–5.0s` hands plugging cord + turning dial (`00:04–00:06`).
  - **Variant C (Pain-Point Direct)**: `0–2.0s` unpolished smartphone POV holding ramen pack over cramped sink full of dirty dishes -> `2.0–3.5s` pulls source clip's OWN 1-burner apartment scene (`00:16`) forward into opening -> `3.5–5.0s` sunny table lid reveal (`00:17–00:18`). Build time for C was shortest (~10 min) because half its hook already existed in the source file.
- **Critical Technical Lesson Observed**: Because the original `1:1` video had burned-in orange bottom captions, the new vertical `9:16` edit explicitly avoids overlap either by placing new typography in the upper 25% band / editorial top canvas or zooming `105–110%` / cropping out the bottom caption band cleanly.

---

## Case 2: Observed Korean Shortform Commerce Structural Patterns (From Field Audit)

Empirical structural observations from audited Korean Reels/Shorts commerce spots (treated strictly as creative test structures, never sales guarantees):

1. **Expectation Disruption Before Product Reveal**:
   - Pattern: Serious or unrelated first `2–4s` (scientific tone, mock debate, tournament bracket, or sudden physical gag like falling/stumbling) followed by sharp rhythmic cut into mundane product usefulness.
   - Guardrail: Must contain a clear visual/auditory hinge (`match object`, `matching motion`, or `ironic punchline`) within `4s` or viewers swipe off feeling tricked without payoff.
2. **Hand-Driven Tactile Proof Over Presenter Talking Head**:
   - Pattern (`COX`, `Philips`, appliance demos): Show active hand manipulation within `0.2–1.0s` (lifting lid, pressing button, lifting inner tray, wiping residue, plugging cable). Every feature caption maps 1-to-1 to the exact motion visible in that second.
   - Guardrail: Static hero beauty shots at `0.0–1.5s` consistently stall scroll-stop momentum unless action begins immediately.
3. **Host-Plus-Product Roleplay / Mock Awards (`Olive Young` / Tournament Format)**:
   - Pattern: Framing product choices as live elimination rounds, hesitant host dilemma, or staff taste-test preferences turns multi-SKU comparison into narrative tension without dry spec sheets.
   - Guardrail: High filming/casting overhead — reserve only for multi-SKU / seasonal campaigns after simpler 5s A/B/C hooks prove SKU demand.
4. **App & High-Consideration Service Decision Pattern (`make-video-ad` Mode 2)**:
   - Pattern (`6s` bumper / `15s` decision spine / `30s` demo): One protagonist, one concrete physical dilemma prop (contract folder, keys, calendar), real phone UI capture (`ADB` / native screen record), single decisive action, restrained silent release (`no manufactured sighs`), and pixel-locked closing CTA card.
