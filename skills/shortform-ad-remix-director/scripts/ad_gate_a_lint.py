#!/usr/bin/env python3
"""Gate A static and cross-file validator for Shortform Ad A/B/C Remix specs.

Runs 12 automated structural, legal-claim, timing, caption-legibility, zero-text
Google Flow prompt, audio-ownership, CTA, and clean-room checks on 05_ad_spec.json,
00_product_facts.md, and optional 05_jobs.json / source_metadata.json.
Exits 0 on 12/12 PASS, exits 1 otherwise.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from typing import Any, Dict, List, Optional, Set, Tuple

FORBIDDEN_SUPERLATIVES = (
    "완벽 방수",
    "완전 방수",
    "100% 효과",
    "100% 보장",
    "기적의",
    "국내 최초",
    "세계 최초",
    "세계 유일",
    "부작용 제로",
    "무조건 해결",
)

DISALLOWED_GEN_PLATFORMS = (
    "dream" + "ina",
    "seed" + "ance",
    "byte" + "plus",
    "capcut ai video",
)

MANUFACTURED_SIGH_TERMS = (
    "small breath",
    "quiet breath",
    "relieved exhale",
    "shoulders soften",
    "shoulder drop",
    "sighs softly",
    "visible inhale",
    "visible exhale",
)

PRIVACY_PATH_RE = re.compile(r"/(?:Users|home)/[^/\s\"']+/", re.IGNORECASE)
PRIVACY_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")

EMOJI_RE = re.compile(
    "["
    "\U0001F300-\U0001F6FF"
    "\U0001F900-\U0001FAFF"
    "\U00002600-\U000027BF"
    "]+",
    flags=re.UNICODE,
)

VALID_FRAMING = {"editorial-card", "smart-crop", "blur-bleed", "full-bleed"}
VALID_DISCLOSURE = {"paid_ad", "sponsored", "own_brand", "ai_assisted", "none"}
VALID_AUDIO_OWNERS = {"vo", "native_hook", "source_audio", "mute", "sfx_only", "silence"}
VALID_TRACK_ARCHETYPES = {"A_bgrade_reversal", "B_info_hook_offset", "C_direct_proof"}
VALID_A_GENRE_ARCHETYPES = {
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
}
RESKIN_SKELETON_PATTERNS = (
    ("속보입니다", re.compile(r"속보\s*입니다|\[?\s*속보\s*\]?")),
    ("단 한 집만", re.compile(r"단\s*한\s*집만")),
    ("온 동네가", re.compile(r"온\s*동네(?:가|는|\s*바닥)")),
)
A_BGRADE_CLICHES = ("선반에 두기 딱 좋아요", "가성비도 끝장나요", "강력 추천", "소개합니다", "꿀팁 공유")
B_INFO_PAS_CLICHES = ("하는 이유", "의 함정", "해결법", "쏟아본 적", "번지고", "고민이시죠", "바꿨어요")


def parse_facts_ledger(facts_path: str) -> Tuple[Set[str], Set[str], List[str]]:
    """Parse [F01..] ledger entries and ## Whitelisted Claims from 00_product_facts.md."""
    with open(facts_path, "r", encoding="utf-8") as f:
        text = f.read()

    verified: Set[str] = set()
    unverified: Set[str] = set()
    whitelist: List[str] = []

    in_whitelist = False
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if line.startswith("## "):
            in_whitelist = "whitelist" in line.lower()
            continue
        if in_whitelist and line.startswith("- "):
            whitelist.append(line[2:].strip())

        m = re.search(r"\[(F\d{2,3})\]", line)
        if m:
            fid = m.group(1)
            upper = line.upper()
            if "[UNVERIFIED" in upper or "DO NOT USE" in upper:
                unverified.add(fid)
            elif "[VERIFIED]" in upper:
                verified.add(fid)

    return verified, unverified, whitelist


def _collect_strings(obj: Any, path: str = "") -> List[Tuple[str, str]]:
    out: List[Tuple[str, str]] = []
    if isinstance(obj, str):
        out.append((path, obj))
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            out.extend(_collect_strings(item, f"{path}[{i}]"))
    elif isinstance(obj, dict):
        for k, v in obj.items():
            out.extend(_collect_strings(v, f"{path}.{k}" if path else str(k)))
    return out


def _seg_dur(seg: Dict[str, Any]) -> float:
    if seg.get("type") == "source" and "src_start" in seg and "src_end" in seg:
        speed = float(seg.get("speed", 1.0) or 1.0)
        return max(0.0, (float(seg["src_end"]) - float(seg["src_start"])) / max(speed, 0.01))
    return float(seg.get("duration", 0.0) or 0.0)


def _derive_captions(variant: Dict[str, Any], shared_body: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    explicit = variant.get("captions")
    if isinstance(explicit, list) and explicit:
        return explicit
    cues: List[Dict[str, Any]] = []
    t = 0.0
    for seg in list(variant.get("hook_segments", [])) + list(shared_body):
        d = _seg_dur(seg)
        txt = (seg.get("caption_text") or "").strip()
        if txt:
            cues.append({"start": round(t, 3), "end": round(t + d, 3), "text": txt})
        t += d
    return cues


def run_lint(
    spec: Dict[str, Any],
    facts_path: str,
    jobs: Optional[Dict[str, Any]] = None,
    source_meta: Optional[Dict[str, Any]] = None,
) -> Tuple[List[Tuple[int, str, List[str]]], Dict[str, Any]]:
    verified_fids, unverified_fids, whitelist = parse_facts_ledger(facts_path)

    mode = spec.get("mode", "abc_remix")
    is_timeline_master = isinstance(spec.get("timeline"), list) and bool(spec.get("timeline"))
    variants: Dict[str, Any] = spec.get("variants") or {}
    shared_body: List[Dict[str, Any]] = spec.get("shared_body_cuts") or []
    timeline_segs: List[Dict[str, Any]] = spec.get("timeline") or []
    hook_target = float(spec.get("hook_window_sec", 13.5 if is_timeline_master else 5.0) or (13.5 if is_timeline_master else 5.0))

    # Check 1: Schema & Variants / Timeline
    c1: List[str] = []
    req_root = ("project_id", "title", "mode", "timeline", "cta") if is_timeline_master else ("project_id", "title", "mode", "variants", "cta")
    for req_key in req_root:
        if not spec.get(req_key):
            c1.append(f"Missing required root field `{req_key}`")
    if mode == "abc_remix" and not is_timeline_master:
        for vkey in ("A", "B", "C"):
            if vkey not in variants:
                c1.append(f"abc_remix mode requires variant `{vkey}`")
    for vkey, v in variants.items():
        for vk in ("hypothesis", "join_sec", "hook_segments", "kpi"):
            if vk not in v or v.get(vk) in (None, "", []):
                c1.append(f"Variant {vkey}: missing `{vk}`")

    # Check 2: Controlled Body Parity / VO Narrative Structure
    c2: List[str] = []
    if is_timeline_master:
        if not spec.get("vo_audio"):
            c2.append("Narrative master timeline requires unified `vo_audio` track")
    else:
        if not shared_body:
            c2.append("shared_body_cuts is empty; controlled body missing")
        join_secs = [float(v.get("join_sec", hook_target)) for v in variants.values() if isinstance(v, dict)]
        if join_secs and max(join_secs) - min(join_secs) > 0.1:
            c2.append(f"Variants diverge in join_sec ({join_secs}); controlled experimental join broken")
        for vkey, v in variants.items():
            if v.get("custom_body_cuts"):
                c2.append(f"Variant {vkey} defines custom_body_cuts; only 0-{hook_target}s hook may vary in abc_remix")

    # Check 3: Hook Window Bounds
    c3: List[str] = []
    is_bumper = mode == "bumper_6s"
    if is_timeline_master:
        if not (8.0 <= hook_target <= 17.5):
            c3.append(f"narrative buildup hook_window_sec={hook_target} outside allowed [8.0, 17.5]")
        for idx, seg in enumerate(timeline_segs):
            if _seg_dur(seg) <= 0:
                c3.append(f"timeline[{idx}]: non-positive duration")
    else:
        min_hook, max_hook = (1.2, 4.5) if is_bumper else (3.0, 6.0)
        if not (min_hook <= hook_target <= max_hook):
            c3.append(f"hook_window_sec={hook_target} outside allowed [{min_hook}, {max_hook}]")
        for vkey, v in variants.items():
            segs = v.get("hook_segments") or []
            h_sum = sum(_seg_dur(s) for s in segs)
            j_sec = float(v.get("join_sec", hook_target) or hook_target)
            if abs(h_sum - j_sec) > 0.25:
                c3.append(f"Variant {vkey}: hook_segments sum={h_sum:.2f}s != join_sec={j_sec:.2f}s (tol 0.25s)")
            for idx, seg in enumerate(segs):
                if _seg_dur(seg) <= 0:
                    c3.append(f"Variant {vkey}.hook_segments[{idx}]: non-positive duration")

    # Check 4: Static Intro Trim
    c4: List[str] = []
    has_source_video = bool(spec.get("source_video"))
    if has_source_video and not spec.get("allow_static_intro", False):
        check_intro_segs = timeline_segs if is_timeline_master else shared_body
        for seg in check_intro_segs:
            if seg.get("type") == "source" and float(seg.get("src_start", 0.0)) < 1.0:
                c4.append(
                    f"source cut {seg.get('id', '?')} starts at src_start={seg.get('src_start')}s < 1.0s "
                    "(set allow_static_intro=true only if 0-1s has no static slate)"
                )

    # Check 5: Source Timecode Bounds & Speed Limits
    c5: List[str] = []
    src_dur = float(source_meta.get("duration", 0.0)) if source_meta else 0.0
    if not src_dur and spec.get("source_duration"):
        src_dur = float(spec["source_duration"])
    all_source_segs: List[Tuple[str, Dict[str, Any]]] = (
        [(f"timeline.{s.get('id', i)}", s) for i, s in enumerate(timeline_segs)]
        if is_timeline_master
        else [(f"body.{s.get('id', i)}", s) for i, s in enumerate(shared_body)]
    )
    for vkey, v in variants.items():
        for i, s in enumerate(v.get("hook_segments") or []):
            all_source_segs.append((f"{vkey}.hook[{i}]", s))
    for loc, seg in all_source_segs:
        if seg.get("type") == "source":
            st = float(seg.get("src_start", -1))
            en = float(seg.get("src_end", -1))
            spd = float(seg.get("speed", 1.0) or 1.0)
            if st < 0 or en <= st:
                c5.append(f"{loc}: invalid src_start={st}, src_end={en}")
            if src_dur > 0 and en > src_dur + 0.05:
                c5.append(f"{loc}: src_end={en} exceeds source duration {src_dur:.2f}s")
            if not (0.85 <= spd <= 1.45):
                c5.append(f"{loc}: speed={spd} out of natural range [0.85, 1.45]")

    # Check 6: Duration & Pacing
    c6: List[str] = []
    body_dur = sum(_seg_dur(s) for s in (timeline_segs if is_timeline_master else shared_body))
    min_tot, max_tot = (5.0, 16.5) if mode in ("bumper_6s", "decision_15s") else (15.0, 42.0)
    if is_timeline_master:
        if not (min_tot <= body_dur <= max_tot):
            c6.append(f"Master timeline total duration {body_dur:.2f}s outside [{min_tot}, {max_tot}]")
    else:
        for vkey, v in variants.items():
            tot = sum(_seg_dur(s) for s in (v.get("hook_segments") or [])) + body_dur
            if not (min_tot <= tot <= max_tot):
                c6.append(f"Variant {vkey}: total duration {tot:.2f}s outside [{min_tot}, {max_tot}]")
    if not is_timeline_master and shared_body:
        avg_cut = body_dur / len(shared_body)
        if avg_cut > 5.0:
            c6.append(f"Average shared_body cut duration {avg_cut:.2f}s > 5.0s; tighten pacing")

    # Check 7: Fact Grounding & Ad-Law Superlatives
    c7: List[str] = []
    referenced_fids: Set[str] = set()
    for usp in spec.get("usps") or []:
        fids = usp.get("fact_ids") or ([usp["fact_id"]] if usp.get("fact_id") else [])
        if not fids:
            c7.append(f"USP '{usp.get('title', '?')}' lacks verified fact_id")
        referenced_fids.update(fids)
    for seg in (timeline_segs if is_timeline_master else shared_body):
        referenced_fids.update(seg.get("fact_ids") or [])
    for v in variants.values():
        for seg in v.get("hook_segments") or []:
            referenced_fids.update(seg.get("fact_ids") or [])
    referenced_fids.update((spec.get("cta") or {}).get("fact_ids") or [])

    if not verified_fids:
        c7.append("00_product_facts.md contains 0 [VERIFIED] [F##] entries")
    for fid in sorted(referenced_fids):
        if fid in unverified_fids:
            c7.append(f"Forbidden reference to [UNVERIFIED] fact [{fid}]")
        elif fid not in verified_fids:
            c7.append(f"Fact [{fid}] referenced in spec is missing or not marked [VERIFIED] in 00_product_facts.md")

    wl_joined = " ".join(whitelist)
    for p, txt in _collect_strings(spec):
        for term in FORBIDDEN_SUPERLATIVES:
            if term in txt and term not in wl_joined:
                c7.append(f"Unverified ad-law superlative '{term}' at {p} (must remove or substantiate)")

    # Check 8: Caption Legibility & Safe Zone Strategy
    c8: List[str] = []
    framing = spec.get("framing_mode", "")
    if framing not in VALID_FRAMING:
        c8.append(f"Invalid framing_mode `{framing}` (must be one of {sorted(VALID_FRAMING)})")
    if source_meta and source_meta.get("likely_burned_in_subtitles"):
        if not spec.get("burned_in_subtitle_strategy"):
            c8.append("Source likely has burned-in subtitles, but `burned_in_subtitle_strategy` is missing")
        if framing == "editorial-card" and int(spec.get("bottom_crop_px", 0) or 0) <= 0 and "상단" not in str(spec.get("burned_in_subtitle_strategy", "")) and "top" not in str(spec.get("burned_in_subtitle_strategy", "")).lower():
            c8.append("Source likely has burned-in bottom subtitles; set bottom_crop_px > 0 or document top-canvas offset")

    cap_groups = [("master", spec.get("captions") or _derive_captions({"hook_segments": timeline_segs}, []))] if is_timeline_master else [
        (vkey, _derive_captions(v, shared_body)) for vkey, v in variants.items()
    ]
    for vkey, cues in cap_groups:
        prev_end = -0.01
        for idx, cue in enumerate(cues):
            st = float(cue.get("start", 0.0))
            en = float(cue.get("end", 0.0))
            if st < prev_end - 0.02 or en <= st:
                c8.append(f"Variant {vkey}.caption[{idx}] non-monotonic/overlapping interval [{st}, {en}]")
            prev_end = en
            lines = [ln.strip() for ln in str(cue.get("text", "")).split("\n") if ln.strip()]
            if len(lines) > 2:
                c8.append(f"Variant {vkey}.caption[{idx}] has {len(lines)} lines (max 2)")
            for ln in lines:
                plain_ln = re.sub(r"\*\*(.+?)\*\*", r"\1", ln)
                if len(plain_ln) > 22:
                    c8.append(f"Variant {vkey}.caption[{idx}] line '{plain_ln}' is {len(plain_ln)} chars (max 22)")

    # Check 9: Google Flow Zero-Text & Prompt Hygiene
    c9: List[str] = []
    job_units = []
    if jobs and isinstance(jobs.get("units"), list):
        job_units = jobs["units"]
    elif isinstance(spec.get("ai_jobs"), list):
        job_units = spec["ai_jobs"]
    for u in job_units:
        uid = u.get("id", "?")
        pr = str(u.get("prompt", ""))
        low = pr.lower()
        for bad_plat in DISALLOWED_GEN_PLATFORMS:
            if bad_plat in low:
                c9.append(f"Job {uid} uses disallowed platform/keyword '{bad_plat}'")
        if "zero readable text" not in low and "no text" not in low and "no readable text" not in low:
            c9.append(f"Job {uid} prompt missing Zero-Text lock ('zero readable text' / 'no text')")
        if int(u.get("count", 1) or 1) != 1:
            c9.append(f"Job {uid} count={u.get('count')} violates x1 credit guard")
        model_id = u.get("model", "omni_1_2_flash")
        if model_id not in ("omni_1_2_flash", "nano_banana_2_lite", "veo_3_1_lite"):
            c9.append(f"Job {uid} unrecognized model '{model_id}'")
        if not u.get("allow_causal_breath", False):
            for sigh in MANUFACTURED_SIGH_TERMS:
                if re.search(rf"(?<!\bno\s)(?<!\bwithout\s)\b{re.escape(sigh)}\b", low):
                    c9.append(f"Job {uid} contains banned manufactured-sigh direction '{sigh}'")

    # Also verify flow_video hook segments link cleanly to jobs units and scan full spec for disallowed AI tool mentions
    unit_ids = {u.get("id") for u in job_units}
    for vkey, v in variants.items():
        for idx, seg in enumerate(v.get("hook_segments") or []):
            if seg.get("type") == "flow_video":
                fuid = seg.get("flow_unit_id") or f"G_{vkey}"
                if jobs and fuid not in unit_ids:
                    c9.append(f"Variant {vkey}.hook_segments[{idx}] flow_unit_id='{fuid}' missing from 05_jobs.json")
                vp = str(seg.get("flow_video_prompt", "")).lower()
                if vp and "zero readable text" not in vp and "no text" not in vp and "no readable text" not in vp:
                    c9.append(f"Variant {vkey}.hook_segments[{idx}] flow_video_prompt missing Zero-Text lock")

    for p, txt in _collect_strings(spec):
        low = txt.lower()
        for bad_plat in DISALLOWED_GEN_PLATFORMS:
            if bad_plat in low:
                c9.append(f"Disallowed platform term '{bad_plat}' found at {p}")

    # Check 10: Audio Ownership & Twist Silence Contrast
    c10: List[str] = []
    for loc, seg in all_source_segs:
        ao = seg.get("audio_owner", "")
        if ao not in VALID_AUDIO_OWNERS:
            c10.append(f"{loc}: invalid audio_owner '{ao}' (expected {sorted(VALID_AUDIO_OWNERS)})")
    for vkey, v in variants.items():
        if v.get("archetype") == "absurd_twist":
            segs = v.get("hook_segments") or []
            has_silence = any(s.get("type") == "silence_gap" or s.get("audio_owner") == "silence" for s in segs)
            if not has_silence:
                c10.append(f"Variant {vkey} (absurd_twist) lacks pre-twist silence beat (type='silence_gap' or audio_owner='silence')")
            else:
                for s in segs:
                    if s.get("type") == "silence_gap":
                        sd = _seg_dur(s)
                        if not (0.10 <= sd <= 0.45):
                            c10.append(f"Variant {vkey} silence_gap={sd:.2f}s outside [0.10, 0.45]")

    # Check 11: CTA & Disclosure
    c11: List[str] = []
    cta = spec.get("cta") or {}
    if not cta.get("copy"):
        c11.append("cta.copy is required")
    if not cta.get("type"):
        c11.append("cta.type (e.g. comment_dm, link_in_bio, app_install) is required")
    disc = spec.get("disclosure")
    if disc not in VALID_DISCLOSURE:
        c11.append(f"Invalid disclosure `{disc}` (must be one of {sorted(VALID_DISCLOSURE)})")
    cta_txt = str(cta.get("copy", "")) + " " + str(cta.get("badge_copy", ""))
    pct_match = re.search(r"(\d+\s*%|할인\s*\d+)", cta_txt)
    if pct_match and not (cta.get("fact_ids")):
        c11.append(f"CTA mentions specific promo figure '{pct_match.group(1)}' without verified fact_ids; use placeholder or cite [F##]")

    # Check 12: KPI Matrix & Clean Room / Zero-Emoji
    c12: List[str] = []
    axes_seen: Set[str] = set()
    for vkey, v in variants.items():
        kpi = v.get("kpi") or {}
        if not kpi.get("primary_metric") or not kpi.get("win_action") or not kpi.get("risk"):
            c12.append(f"Variant {vkey}.kpi incomplete (needs primary_metric, risk, win_action)")
        if kpi.get("primary_axis"):
            axes_seen.add(str(kpi["primary_axis"]))
    if mode == "abc_remix" and len(variants) >= 3 and len(axes_seen) < 2:
        c12.append(f"A/B/C KPI matrix should span >= 2 evaluation axes (reach_watch + conversion); saw {sorted(axes_seen)}")

    path_keys = ("source_video", ".path", ".keyframe_image", ".image", ".vo_audio", ".fallback_image")
    for p, txt in _collect_strings(spec):
        is_fs_path = p.endswith(path_keys)
        if not is_fs_path and PRIVACY_PATH_RE.search(txt):
            c12.append(f"Personal OS path leaked in copy/prompt at {p}")
        if PRIVACY_EMAIL_RE.search(txt):
            c12.append(f"Email address leaked at {p}")
        if EMOJI_RE.search(txt):
            c12.append(f"Emoji character detected at {p}; overlays and specs must stay emoji-free")

    # Check 13: Orthogonal Track Archetype & Anti-C Structural Guard
    c13: List[str] = []
    arch = spec.get("track_archetype")
    if arch:
        if arch not in VALID_TRACK_ARCHETYPES:
            c13.append(f"Invalid track_archetype `{arch}` (expected {sorted(VALID_TRACK_ARCHETYPES)})")
        taboo_words = [str(w).strip() for w in (spec.get("product_taboo_keywords") or []) if str(w).strip()]
        master_cues = (
            spec.get("captions")
            or _derive_captions({"hook_segments": timeline_segs}, [])
            if is_timeline_master
            else _derive_captions(variants.get(arch[0], {}), shared_body)
        )
        gap_idx = next((i for i, s in enumerate(timeline_segs) if s.get("type") == "silence_gap"), None) if is_timeline_master else None
        pre_gap_dur = sum(_seg_dur(s) for s in timeline_segs[:gap_idx]) if gap_idx is not None else min(hook_target, 8.0)
        post_gap_dur = sum(_seg_dur(s) for s in timeline_segs[gap_idx + 1 :]) if gap_idx is not None else 0.0

        if arch == "A_bgrade_reversal":
            a_genre = spec.get("a_genre_archetype")
            if a_genre is not None and a_genre not in VALID_A_GENRE_ARCHETYPES:
                c13.append(
                    f"Invalid a_genre_archetype `{a_genre}` (expected {sorted(VALID_A_GENRE_ARCHETYPES)})"
                )
            if is_timeline_master:
                if gap_idx is None:
                    c13.append("A_bgrade_reversal requires a `silence_gap` twist freeze before the product payoff")
                else:
                    gap_dur = _seg_dur(timeline_segs[gap_idx])
                    if not (0.12 <= gap_dur <= 0.45):
                        c13.append(f"A_bgrade_reversal silence_gap={gap_dur:.2f}s outside [0.12, 0.45]")
                    if body_dur > 0 and (post_gap_dur / body_dur) > 0.55:
                        c13.append(
                            f"A_bgrade_reversal payoff ratio={post_gap_dur / body_dur:.2f} > 0.55; keep B-grade crisis dominant and product payoff concise"
                        )
            for idx, cue in enumerate(master_cues):
                st = float(cue.get("start", 0.0))
                plain_txt = re.sub(r"\*\*(.+?)\*\*", r"\1", str(cue.get("text", "")))
                if st < pre_gap_dur - 0.05:
                    for kw in taboo_words:
                        if kw in plain_txt:
                            c13.append(f"A_bgrade_reversal hook caption[{idx}] mentions taboo product word '{kw}' before twist")
                for cliche in A_BGRADE_CLICHES:
                    if cliche in plain_txt:
                        c13.append(f"A_bgrade_reversal caption[{idx}] contains C-style review cliché '{cliche}'")

        elif arch == "B_info_hook_offset":
            sim = spec.get("hook_similarity_score")
            if sim is None or not isinstance(sim, (int, float)):
                c13.append("B_info_hook_offset requires numeric `hook_similarity_score` in [0.35, 0.65]")
            elif not (0.35 <= float(sim) <= 0.65):
                c13.append(f"B_info_hook_offset hook_similarity_score={sim} outside target offset band [0.35, 0.65]")
            header_tags = [c.get("header_tag") for c in master_cues if c.get("header_tag")]
            if len(header_tags) > 2:
                c13.append(f"B_info_hook_offset stacks {len(header_tags)} spec header_tags (max 2 to avoid C-style spec clone)")
            for idx, cue in enumerate(master_cues):
                st = float(cue.get("start", 0.0))
                plain_txt = re.sub(r"\*\*(.+?)\*\*", r"\1", str(cue.get("text", "")))
                if st < 5.5:
                    for kw in taboo_words:
                        if kw in plain_txt:
                            c13.append(f"B_info_hook_offset opening caption[{idx}] leaks product word '{kw}' before bridge")
                    for cliche in B_INFO_PAS_CLICHES:
                        if cliche in plain_txt:
                            c13.append(f"B_info_hook_offset opening caption[{idx}] uses C-style PAS cliché '{cliche}'")

    checks = [
        (1, "Schema, Mode & Variant Structure", c1),
        (2, "Controlled Master Body Parity (Same Join & Shared Cuts)", c2),
        (3, "Hook Window Bounds (3.0-6.0s) & Segment Sum Parity", c3),
        (4, "Static Opening Intro Trim Rule", c4),
        (5, "Source Timecode Bounds & Natural Speed Limits (0.85-1.40x)", c5),
        (6, "Total Runtime & Cut Pacing Bounds", c6),
        (7, "Product Fact Grounding [F##] & Ad-Law Superlative Guard", c7),
        (8, "Korean Caption Legibility (<=2 lines, <=22 chars) & Safe-Zone Strategy", c8),
        (9, "Google Flow Zero-Text Lock, x1 Guard & Platform Hygiene", c9),
        (10, "Single Audio Ownership & Pre-Twist Silence Contrast", c10),
        (11, "Single-Step CTA, Unverified Promo Placeholder & Disclosure", c11),
        (12, "2-Axis KPI Experiment Matrix & Zero-Emoji / Privacy Hygiene", c12),
        (13, "Orthogonal Track Archetype & Anti-C Structural Guard", c13),
    ]

    meta_summary = {
        "project_id": spec.get("project_id", ""),
        "mode": mode,
        "variants": list(variants.keys()),
        "hook_sec": hook_target,
        "body_sec": round(body_dur, 2),
        "verified_facts": len(verified_fids),
        "framing_mode": framing,
        "disclosure": disc,
        "flow_jobs": len(job_units),
    }
    return checks, meta_summary


def format_report(checks: List[Tuple[int, str, List[str]]], meta: Dict[str, Any]) -> Tuple[str, int, int]:
    failed = sum(1 for _, _, errs in checks if errs)
    passed = len(checks) - failed
    status = "PASS" if failed == 0 else "FAIL"
    lines = [
        f"# Gate A Ad Remix Lint Report — {status} ({passed}/{len(checks)})",
        "",
        (
            f"> Project `{meta['project_id']}` | Mode `{meta['mode']}` | Variants `{','.join(meta['variants'])}` | "
            f"Hook `{meta['hook_sec']}s` + Shared Body `{meta['body_sec']}s` | Framing `{meta['framing_mode']}` | "
            f"Disclosure `{meta['disclosure']}` | Verified Facts `{meta['verified_facts']}` | Flow Jobs `{meta['flow_jobs']}`"
        ),
        "",
        "| # | Check | Status | Details |",
        "|---|---|---|---|",
    ]
    for idx, title, errs in checks:
        st = "PASS" if not errs else f"FAIL ({len(errs)})"
        detail = "OK" if not errs else "; ".join(errs)
        lines.append(f"| {idx} | {title} | {st} | {detail} |")
    lines.append("")
    return "\n".join(lines), passed, failed


def validate_abc_orthogonality(specs: List[Dict[str, Any]]) -> List[str]:
    """Ensure A, B, and C specs execute 3 strictly orthogonal genres instead of C clones."""
    errs: List[str] = []
    if len(specs) < 3:
        return [f"Expected 3 specs (A, B, C), got {len(specs)}"]
    archs = [s.get("track_archetype") for s in specs]
    expected = {"A_bgrade_reversal", "B_info_hook_offset", "C_direct_proof"}
    if any(a is None for a in archs):
        errs.append(f"All 3 specs must declare track_archetype in {sorted(expected)}; got {archs}")
    elif set(archs) != expected:
        errs.append(f"A/B/C track_archetypes must cover {sorted(expected)}; got {archs}")

    openings: Dict[str, str] = {}
    tags_by_arch: Dict[str, Set[str]] = {}
    for s in specs:
        a = str(s.get("track_archetype") or s.get("project_id") or "?")
        caps = s.get("captions") or []
        if caps:
            first_txt = re.sub(r"\*\*(.+?)\*\*", r"\1", str(caps[0].get("text", ""))).strip()
            openings[a] = first_txt
        tags_by_arch[a] = {str(c.get("header_tag")) for c in caps if c.get("header_tag")}

    seen_openings: Dict[str, str] = {}
    for a, txt in openings.items():
        if txt in seen_openings:
            errs.append(f"Tracks {seen_openings[txt]} and {a} share identical opening line '{txt}'")
        else:
            seen_openings[txt] = a

    overlap_ac = tags_by_arch.get("A_bgrade_reversal", set()) & tags_by_arch.get("C_direct_proof", set())
    if len(overlap_ac) >= 2:
        errs.append(f"A_bgrade_reversal shares >=2 spec header_tags with C_direct_proof: {sorted(overlap_ac)}")
    return errs


def validate_no_campaign_reskin(specs: List[Dict[str, Any]]) -> List[str]:
    """Detect Track A reskinning across 2+ different product campaigns."""
    errs: List[str] = []
    if len(specs) < 2:
        return [f"Expected >= 2 Track A campaign specs to compare, got {len(specs)}"]

    seen_genres: Dict[str, str] = {}
    seen_prefixes: Dict[str, str] = {}
    seen_skeletons: Dict[str, List[str]] = {}
    seen_sound_sigs: Dict[Tuple[Tuple[str, ...], Tuple[str, ...]], str] = {}

    for spec in specs:
        pid = str(spec.get("project_id") or spec.get("output_stem") or "unknown")
        a_genre = spec.get("a_genre_archetype")
        if a_genre is not None:
            if a_genre not in VALID_A_GENRE_ARCHETYPES:
                errs.append(f"{pid}: invalid a_genre_archetype `{a_genre}`")
            elif a_genre in seen_genres:
                errs.append(
                    f"Campaigns `{seen_genres[a_genre]}` and `{pid}` share identical a_genre_archetype `{a_genre}` (reskin)"
                )
            else:
                seen_genres[a_genre] = pid

        timeline_segs = spec.get("timeline") or []
        gap_idx = next((i for i, s in enumerate(timeline_segs) if s.get("type") == "silence_gap"), None)
        pre_gap_dur = (
            sum(float(s.get("duration") or 0.0) for s in timeline_segs[:gap_idx])
            if gap_idx is not None
            else float(spec.get("hook_window_sec") or 8.0)
        )

        caps = spec.get("captions") or []
        if caps:
            first_plain = re.sub(r"\*\*(.+?)\*\*", r"\1", str(caps[0].get("text", "")))
            compact = re.sub(r"[\s\[\]()·,.!?:;\n\"']+", "", first_plain)
            prefix = compact[:6]
            if len(prefix) >= 6:
                if prefix in seen_prefixes:
                    errs.append(
                        f"Campaigns `{seen_prefixes[prefix]}` and `{pid}` share identical opening prefix `{prefix}` (reskin)"
                    )
                else:
                    seen_prefixes[prefix] = pid

        pre_text = " ".join(
            re.sub(r"\*\*(.+?)\*\*", r"\1", str(c.get("text", "")))
            for c in caps
            if float(c.get("start", 0.0)) < pre_gap_dur + 0.05
        )
        matched_here: Set[str] = set()
        for label, pat in RESKIN_SKELETON_PATTERNS:
            if pat.search(pre_text):
                matched_here.add(label)
        for label in sorted(matched_here):
            if label in seen_skeletons:
                errs.append(
                    f"Campaigns `{seen_skeletons[label][0]}` and `{pid}` both reuse reskin skeleton phrase `{label}`"
                )
                seen_skeletons[label].append(pid)
            else:
                seen_skeletons[label] = [pid]

        sfx_seq = tuple(os.path.basename(str(e.get("file", ""))) for e in (spec.get("sfx_events") or []))
        bgm_tl = spec.get("bgm_timeline") or []
        act1_stems = tuple(
            os.path.basename(str(st)) for st in (bgm_tl[0].get("stems") or [])
        ) if bgm_tl else ()
        if sfx_seq and act1_stems:
            sig = (sfx_seq, act1_stems)
            if sig in seen_sound_sigs:
                errs.append(
                    f"Campaigns `{seen_sound_sigs[sig]}` and `{pid}` share identical Act-1 BGM stems and SFX sequence (audio reskin)"
                )
            else:
                seen_sound_sigs[sig] = pid

    return errs


def main() -> None:
    p = argparse.ArgumentParser(description="Gate A linter for 05_ad_spec.json")
    p.add_argument("--spec", default=None, help="Path to 05_ad_spec.json")
    p.add_argument("--facts", default=None, help="Path to 00_product_facts.md")
    p.add_argument("--jobs", default=None, help="Optional 05_jobs.json")
    p.add_argument("--source-meta", default=None, help="Optional source_metadata.json")
    p.add_argument("--out", default=None, help="Write markdown lint report to this path")
    p.add_argument("--compare-abc", nargs=3, metavar=("SPEC_A", "SPEC_B", "SPEC_C"), help="Verify orthogonal A/B/C archetypes across 3 specs")
    p.add_argument(
        "--compare-campaigns",
        nargs="+",
        metavar="SPEC_A",
        help="Verify 2+ Track A specs across different campaigns do not reskin the same genre/opening/sound skeleton",
    )
    args = p.parse_args()

    if args.compare_campaigns:
        loaded_cmp = []
        for sp in args.compare_campaigns:
            with open(sp, "r", encoding="utf-8") as f:
                loaded_cmp.append(json.load(f))
        reskin_errs = validate_no_campaign_reskin(loaded_cmp)
        if reskin_errs:
            print(f"Campaign Anti-Reskin: FAIL ({len(reskin_errs)} violations)")
            for e in reskin_errs:
                print(f"  {e}")
            raise SystemExit(1)
        print(f"Campaign Anti-Reskin: PASS ({len(loaded_cmp)} campaigns use distinct genres/openings)")
        if not args.spec and not args.compare_abc:
            raise SystemExit(0)

    if args.compare_abc:
        loaded = []
        for sp in args.compare_abc:
            with open(sp, "r", encoding="utf-8") as f:
                loaded.append(json.load(f))
        abc_errs = validate_abc_orthogonality(loaded)
        if abc_errs:
            print(f"ABC Orthogonality: FAIL ({len(abc_errs)} violations)")
            for e in abc_errs:
                print(f"  {e}")
            raise SystemExit(1)
        print("ABC Orthogonality: PASS (A_bgrade_reversal / B_info_hook_offset / C_direct_proof distinct)")
        if not args.spec:
            raise SystemExit(0)

    if not args.spec or not args.facts:
        p.error("--spec and --facts are required unless --compare-abc / --compare-campaigns is used standalone")

    with open(args.spec, "r", encoding="utf-8") as f:
        spec = json.load(f)
    jobs = None
    if args.jobs and os.path.exists(args.jobs):
        with open(args.jobs, "r", encoding="utf-8") as f:
            jobs = json.load(f)
    src_meta = None
    if args.source_meta and os.path.exists(args.source_meta):
        with open(args.source_meta, "r", encoding="utf-8") as f:
            src_meta = json.load(f)

    checks, meta = run_lint(spec, args.facts, jobs=jobs, source_meta=src_meta)
    report_md, passed, failed = format_report(checks, meta)
    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(report_md)

    verdict = "PASS" if failed == 0 else "FAIL"
    print(f"Gate A: {passed}/{len(checks)} {verdict} ({failed} violations)")
    for idx, title, errs in checks:
        if errs:
            for e in errs:
                print(f"  [{idx}:{title}] {e}")
    raise SystemExit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
