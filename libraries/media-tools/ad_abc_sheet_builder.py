#!/usr/bin/env python3
"""Standalone Swiss-editorial HTML A/B/C Production & Edit Guide generator.

Reads 05_ad_spec.json (Single Source of Truth) and renders a portable, self-contained
HTML production guide featuring dynamic inline SVG remix timeline, 4-USP strip,
A/B/C hook hypothesis + storyboard rows, base64-embedded resized keyframes & source
4-cut strip, controlled Master Source Cut-Sheet table, and 2-axis KPI matrix.
"""

from __future__ import annotations

import argparse
import base64
import html
import io
import json
import os
from typing import Any, Dict, List, Optional

from PIL import Image

CSS_TEMPLATE = """    :root {
      --paper: #FFFFFF;
      --band: #F4F6F9;
      --ink: #111318;
      --ink2: #2E3440;
      --mute: #47505E;
      --hair: #D5DCE4;
      --accent: #D9481E;
      --accent-text: #9A290B;
      --accent-2: #2B4C7E;
      --accent-2-text: #1B365D;
      --serif: 'Noto Serif KR', Georgia, serif;
      --sans: 'Noto Sans KR', -apple-system, BlinkMacSystemFont, sans-serif;
      --mono: 'IBM Plex Mono', monospace;
    }
    *, *::before, *::after { box-sizing: border-box; }
    html, body {
      margin: 0; padding: 0; background: var(--paper); color: var(--ink);
      font-family: var(--sans); font-size: 16.5px; line-height: 1.72;
      -webkit-font-smoothing: antialiased; word-break: keep-all;
    }
    .page { width: 100%; padding: 68px clamp(24px, 10.4vw, 112px) 92px; }
    .grid { display: grid; grid-template-columns: repeat(12, minmax(0, 1fr)); column-gap: 24px; }
    .col-12 { grid-column: 1 / -1; }
    .col-10 { grid-column: 1 / span 10; }
    .col-8  { grid-column: 1 / span 8; }
    .col-7  { grid-column: 1 / span 7; }
    .col-5  { grid-column: 8 / span 5; }
    .col-4  { grid-column: 1 / span 4; }
    .col-8r { grid-column: 5 / span 8; }
    .measure { max-width: 68ch; }
    h1 {
      font-family: var(--serif); font-weight: 900; font-size: clamp(38px, 5vw, 68px);
      line-height: 1.15; letter-spacing: -0.025em; margin: 0 0 24px; color: var(--ink); text-wrap: balance;
    }
    .deck { font-size: clamp(18px, 1.55vw, 21px); line-height: 1.65; color: var(--ink2); margin: 0 0 44px; max-width: 64ch; }
    .hero-split { border-top: 2px solid var(--ink); padding-top: 28px; align-items: start; }
    .verdict-lead { font-family: var(--serif); font-size: 22px; font-weight: 700; line-height: 1.5; color: var(--ink); margin: 0 0 14px; }
    .emphasis-wrap { border-left: 1px solid var(--hair); padding-left: 28px; }
    .emphasis-num {
      font-family: var(--serif); font-weight: 900; font-size: clamp(68px, 7.6vw, 108px);
      line-height: 1; letter-spacing: -0.03em; color: var(--accent-text); margin: 0 0 10px; white-space: nowrap;
    }
    .emphasis-cap { font-size: 14.5px; line-height: 1.6; color: var(--mute); margin: 0; }
    .sec { margin-top: 92px; }
    h2 {
      font-family: var(--serif); font-weight: 700; font-size: clamp(26px, 3vw, 40px);
      line-height: 1.24; letter-spacing: -0.02em; margin: 0 0 18px; color: var(--ink); text-wrap: balance;
    }
    h3 { font-family: var(--serif); font-weight: 700; font-size: 20px; line-height: 1.38; margin: 0 0 8px; color: var(--ink); }
    p { margin: 0 0 18px; color: var(--ink2); }
    figure { margin: 32px 0 38px; padding: 0; }
    .fig-title { font-family: var(--serif); font-weight: 700; font-size: 19.5px; line-height: 1.4; color: var(--ink); margin: 0 0 14px; }
    figure img { display: block; width: 100%; height: auto; border-radius: 0; }
    figcaption { font-size: 13.5px; line-height: 1.55; color: var(--mute); margin-top: 10px; }
    .hypo-strip {
      display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 24px;
      border-top: 1px solid var(--hair); border-bottom: 1px solid var(--hair); padding: 20px 0; margin: 24px 0 32px;
    }
    .hypo-label { font-family: var(--mono); font-size: 12.5px; font-weight: 500; color: var(--accent-text); margin: 0 0 6px; }
    .hypo-val { font-size: 15.5px; line-height: 1.55; color: var(--ink); margin: 0; }
    .sb-head, .sb-row {
      display: grid; grid-template-columns: 104px 1.25fr 1fr 0.9fr; column-gap: 20px;
      padding: 16px 0; border-top: 1px solid var(--hair); align-items: start;
    }
    .sb-head {
      border-top: 2px solid var(--ink); padding: 12px 0; font-family: var(--mono);
      font-size: 12.5px; font-weight: 500; color: var(--mute);
    }
    .sb-row:last-child { border-bottom: 1px solid var(--hair); }
    .sb-time { font-family: var(--mono); font-size: 13px; font-weight: 500; color: var(--accent-text); white-space: nowrap; }
    .sb-cell { font-size: 15px; line-height: 1.62; color: var(--ink2); }
    .sb-cell strong { color: var(--ink); font-weight: 700; }
    .quad-strip { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 24px; margin: 28px 0 12px; }
    .quad-item { border-top: 2px solid var(--ink); padding-top: 14px; }
    .quad-item p { font-size: 14.5px; margin: 0; }
    .src-tag { font-family: var(--mono); font-size: 12.5px; color: var(--accent-2-text); display: inline-block; margin-bottom: 6px; }
    .band { background: var(--band); margin: 92px calc(-1 * clamp(24px, 10.4vw, 112px)) 0; padding: 72px clamp(24px, 10.4vw, 112px); }
    table { width: 100%; border-collapse: collapse; margin: 24px 0 28px; font-size: 15px; }
    thead th {
      text-align: left; font-family: var(--mono); font-size: 12.5px; font-weight: 500; color: var(--mute);
      padding: 12px 14px 12px 0; border-top: 2px solid var(--ink); border-bottom: 1px solid var(--ink); white-space: nowrap;
    }
    tbody td { padding: 15px 14px 15px 0; border-bottom: 1px solid var(--hair); vertical-align: top; color: var(--ink2); line-height: 1.6; }
    tbody td:first-child { color: var(--ink); font-weight: 700; white-space: nowrap; }
    .num { font-family: var(--mono); white-space: nowrap; color: var(--accent-text); font-weight: 500; }
    .src-code { font-family: var(--mono); white-space: nowrap; color: var(--accent-2-text); font-weight: 500; }
    .pullquote { border-top: 2px solid var(--ink); border-bottom: 1px solid var(--hair); padding: 32px 0; margin: 72px 0 64px; }
    .pullquote p {
      font-family: var(--serif); font-size: clamp(22px, 2.6vw, 32px); font-weight: 700;
      line-height: 1.45; color: var(--ink); margin: 0 0 12px; max-width: 38ch;
    }
    .pullquote footer { font-size: 14.5px; color: var(--mute); }
    .sources-list { list-style: none; padding: 0; margin: 18px 0 0; counter-reset: src; }
    .sources-list li { position: relative; padding: 10px 0 10px 32px; border-top: 1px solid var(--hair); font-size: 14.5px; color: var(--ink2); }
    .sources-list li::before { counter-increment: src; content: counter(src); position: absolute; left: 0; top: 10px; font-family: var(--mono); font-size: 13px; color: var(--mute); }
    .sources-list li:last-child { border-bottom: 1px solid var(--hair); }
    @media (max-width: 860px) {
      .col-10, .col-8, .col-7, .col-5, .col-4, .col-8r { grid-column: 1 / -1; }
      .emphasis-wrap { border-left: none; border-top: 1px solid var(--hair); padding-left: 0; padding-top: 20px; margin-top: 20px; }
      .hypo-strip, .quad-strip { grid-template-columns: 1fr; gap: 16px; }
      .sb-head { display: none; }
      .sb-row { grid-template-columns: 1fr; row-gap: 6px; }
      table { display: block; overflow-x: auto; }
    }"""


def _esc(val: Any) -> str:
    return html.escape(str(val or ""), quote=True)


def _seg_dur(seg: Dict[str, Any]) -> float:
    if seg.get("type") == "source" and "src_start" in seg and "src_end" in seg:
        spd = float(seg.get("speed", 1.0) or 1.0)
        return max(0.0, (float(seg["src_end"]) - float(seg["src_start"])) / max(spd, 0.01))
    return float(seg.get("duration", 0.0) or 0.0)


def _fmt_range(t0: float, t1: float) -> str:
    def _s(x: float) -> str:
        s = f"{x:05.2f}" if abs(x - round(x)) > 0.05 else f"{int(round(x)):02d}"
        if "." in s and s.endswith("0"):
            s = s[:-1]
        return f"00:{s}"
    return f"{_s(t0)}–{_s(t1)}"


def _encode_image_data_uri(path: Optional[str], base_dir: str, max_w: int = 1200) -> Optional[str]:
    if not path:
        return None
    abs_p = path if os.path.isabs(path) else os.path.join(base_dir, path)
    if not os.path.exists(abs_p):
        return None
    with Image.open(abs_p) as im:
        rgb = im.convert("RGB")
        if rgb.width > max_w:
            nh = int(round(rgb.height * max_w / rgb.width))
            rgb = rgb.resize((max_w, nh), Image.Resampling.LANCZOS)
        buf = io.BytesIO()
        rgb.save(buf, format="JPEG", quality=84, optimize=True)
        b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        return f"data:image/jpeg;base64,{b64}"


def _build_timeline_svg(spec: Dict[str, Any]) -> str:
    variants: Dict[str, Any] = spec.get("variants") or {}
    body = spec.get("shared_body_cuts") or []
    hook_sec = float(spec.get("hook_window_sec", 5.0) or 5.0)
    body_dur = sum(_seg_dur(s) for s in body)
    total_sec = round(hook_sec + body_dur, 1)
    cta = spec.get("cta") or {}
    cta_start = float(cta.get("start_sec", max(hook_sec + 1.0, total_sec - 4.0)))
    cta_start = min(max(hook_sec + 0.5, cta_start), max(hook_sec + 0.5, total_sec - 1.0))

    x0, x_end = 110.0, 650.0
    scale = (x_end - x0) / max(total_sec, 1.0)
    x_join = x0 + hook_sec * scale
    x_cta = x0 + cta_start * scale

    vkeys = list(variants.keys())
    y_top = 54
    row_step = 84
    y_bot = y_top + len(vkeys) * row_step
    svg_h = y_bot + 74

    lines: List[str] = [
        f'<svg viewBox="0 0 700 {svg_h}" width="100%" role="img" aria-label="A/B/C 리믹스 타임라인 구조">',
        f'  <line x1="{x0:.1f}" y1="{y_top}" x2="{x0:.1f}" y2="{y_bot}" stroke="#D5DCE4" stroke-width="1" />',
        f'  <line x1="{x_join:.1f}" y1="{y_top}" x2="{x_join:.1f}" y2="{y_bot}" stroke="#111318" stroke-width="1.5" stroke-dasharray="4 4" />',
        f'  <line x1="{x_cta:.1f}" y1="{y_top}" x2="{x_cta:.1f}" y2="{y_bot}" stroke="#D5DCE4" stroke-width="1" stroke-dasharray="4 4" />',
        f'  <line x1="{x_end:.1f}" y1="{y_top}" x2="{x_end:.1f}" y2="{y_bot}" stroke="#D5DCE4" stroke-width="1" />',
        f'  <text x="{x0:.1f}" y="36" fill="#47505E" font-family="IBM Plex Mono, monospace" font-size="13" text-anchor="middle">0초</text>',
        f'  <text x="{x_join:.1f}" y="36" fill="#111318" font-family="IBM Plex Mono, monospace" font-size="13" font-weight="500" text-anchor="middle">{hook_sec:g}초(원본 합류)</text>',
        f'  <text x="{x_cta:.1f}" y="36" fill="#47505E" font-family="IBM Plex Mono, monospace" font-size="13" text-anchor="middle">{cta_start:g}초</text>',
        f'  <text x="{x_end:.1f}" y="36" fill="#47505E" font-family="IBM Plex Mono, monospace" font-size="13" text-anchor="middle">{total_sec:g}초</text>',
    ]

    for idx, vk in enumerate(vkeys):
        v = variants[vk]
        ry = y_top + 28 + idx * row_step
        lbl = _esc(v.get("label") or f"{vk}안")
        stag = _esc(v.get("short_tag") or v.get("archetype") or "")
        lines.append(f'  <text x="14" y="{ry + 24}" fill="#111318" font-family="Noto Sans KR, sans-serif" font-size="15" font-weight="700">{lbl}</text>')
        lines.append(f'  <text x="14" y="{ry + 44}" fill="#47505E" font-family="Noto Sans KR, sans-serif" font-size="13">{stag}</text>')

        segs = v.get("hook_segments") or []
        first_dur = _seg_dur(segs[0]) if segs else hook_sec * 0.65
        for si, s in enumerate(segs):
            if si > 0 and s.get("type") in ("source", "silence_gap"):
                break
            if si == 0:
                continue
        pivot_sec = min(max(1.5, first_dur), max(1.5, hook_sec - 0.8))
        w_h1 = max(24.0, (pivot_sec * scale) - 2.0)
        x_h2 = x0 + pivot_sec * scale
        w_h2 = max(24.0, (x_join - x_h2) - 2.0)

        h1_lbl = _esc(v.get("timeline_h1_label") or stag[:6] or "신규 훅")
        h2_lbl = _esc(v.get("timeline_h2_label") or "브리지")
        w_body = max(40.0, (x_cta - x_join) - 4.0)
        w_cta = max(40.0, (x_end - x_cta) - 2.0)

        lines.append(f'  <rect x="{x0:.1f}" y="{ry}" width="{w_h1:.1f}" height="54" fill="#D9481E" />')
        lines.append(f'  <text x="{x0 + w_h1/2:.1f}" y="{ry + 32}" fill="#FFFFFF" font-family="Noto Sans KR, sans-serif" font-size="13.5" font-weight="700" text-anchor="middle">{h1_lbl}</text>')
        lines.append(f'  <rect x="{x_h2:.1f}" y="{ry}" width="{w_h2:.1f}" height="54" fill="#9A290B" />')
        lines.append(f'  <text x="{x_h2 + w_h2/2:.1f}" y="{ry + 32}" fill="#FFFFFF" font-family="Noto Sans KR, sans-serif" font-size="12.5" font-weight="700" text-anchor="middle">{h2_lbl}</text>')
        lines.append(f'  <rect x="{x_join + 2:.1f}" y="{ry}" width="{w_body:.1f}" height="54" fill="#E8EDF3" />')
        lines.append(f'  <text x="{x_join + 2 + w_body/2:.1f}" y="{ry + 32}" fill="#111318" font-family="Noto Sans KR, sans-serif" font-size="14" font-weight="500" text-anchor="middle">공통 원본 시연 리믹스</text>')
        lines.append(f'  <rect x="{x_cta + 2:.1f}" y="{ry}" width="{w_cta:.1f}" height="54" fill="#2B4C7E" />')
        lines.append(f'  <text x="{x_cta + 2 + w_cta/2:.1f}" y="{ry + 32}" fill="#FFFFFF" font-family="Noto Sans KR, sans-serif" font-size="13.5" font-weight="500" text-anchor="middle">전환 CTA</text>')

    ly = y_bot + 24
    lines.append(f'  <line x1="{x0:.1f}" y1="{ly}" x2="{x_join - 2:.1f}" y2="{ly}" stroke="#9A290B" stroke-width="2" />')
    lines.append(f'  <text x="{(x0 + x_join)/2:.1f}" y="{ly + 24}" fill="#9A290B" font-family="Noto Sans KR, sans-serif" font-size="13" font-weight="700" text-anchor="middle">신규 훅 실험 변인 (0-{hook_sec:g}초)</text>')
    lines.append(f'  <line x1="{x_join + 2:.1f}" y1="{ly}" x2="{x_end:.1f}" y2="{ly}" stroke="#1B365D" stroke-width="2" />')
    lines.append(f'  <text x="{(x_join + x_end)/2:.1f}" y="{ly + 24}" fill="#1B365D" font-family="Noto Sans KR, sans-serif" font-size="13" font-weight="700" text-anchor="middle">공통 통제 본편 ({hook_sec:g}-{total_sec:g}초)</text>')
    lines.append("</svg>")
    return "\n".join(lines)


def build_html(spec: Dict[str, Any], base_dir: str, max_img_width: int = 1200) -> str:
    title = _esc(spec.get("title", "숏폼 광고 A·B·C 리믹스 가이드"))
    deck = _esc(spec.get("deck", ""))
    verdict_lead = _esc(spec.get("verdict_lead", ""))
    verdict_body = _esc(spec.get("verdict_body", ""))
    emphasis_num = _esc(spec.get("emphasis_num", f"{spec.get('hook_window_sec', 5):g}초"))
    emphasis_cap = _esc(spec.get("emphasis_cap", "유일한 실험 변인 구간. 합류 이후 본편은 A·B·C 모두 동일한 마스터를 사용합니다."))

    usp_cards = []
    for u in spec.get("usps") or []:
        usp_cards.append(
            f'<div class="quad-item"><span class="src-tag">{_esc(u.get("source_tag", ""))}</span>'
            f'<h3>{_esc(u.get("title", ""))}</h3><p>{_esc(u.get("desc", ""))}</p></div>'
        )

    svg_block = _build_timeline_svg(spec)
    shared_body = spec.get("shared_body_cuts") or []
    hook_sec = float(spec.get("hook_window_sec", 5.0) or 5.0)
    body_dur = sum(_seg_dur(s) for s in shared_body)
    total_sec = round(hook_sec + body_dur, 1)

    variant_sections = []
    kpi_rows = []
    for vk, v in (spec.get("variants") or {}).items():
        v_title = _esc(v.get("section_title") or f"{vk}안: {v.get('short_tag', '')}")
        v_intro = _esc(v.get("section_intro") or "")
        kf_uri = _encode_image_data_uri(v.get("keyframe_image"), base_dir, max_w=max_img_width)
        kf_fig = ""
        if kf_uri:
            kf_fig = (
                f'<div class="col-12"><figure>'
                f'<p class="fig-title">{_esc(v.get("keyframe_title") or f"{vk}안 0-3초 오프닝 키프레임")}</p>'
                f'<img src="{kf_uri}" alt="{_esc(v.get("keyframe_caption") or vk)}" />'
                f'<figcaption>{_esc(v.get("keyframe_caption") or "")}</figcaption>'
                f'</figure></div>'
            )

        sb_rows = []
        t = 0.0
        for s in v.get("hook_segments") or []:
            d = _seg_dur(s)
            stype = s.get("type", "video")
            if stype == "source":
                src_badge = f"원본 {_fmt_range(float(s.get('src_start', 0)), float(s.get('src_end', 0)))}"
            elif stype == "silence_gap":
                src_badge = "무음 컷"
            elif stype == "flow_video":
                src_badge = f"Flow {s.get('flow_unit_id') or ('G_' + vk)}"
            else:
                src_badge = "신규 컷"
            vis = _esc(s.get("visual_note") or s.get("prompt_summary") or src_badge)
            cap = _esc((s.get("caption_text") or "").replace("\n", " "))
            aud = _esc(s.get("narration_note") or s.get("audio_owner") or "")
            sb_rows.append(
                f'<div class="sb-row">'
                f'<div class="sb-time">{_fmt_range(t, t + d)}</div>'
                f'<div class="sb-cell"><strong>[{_esc(src_badge)}]</strong> {vis}</div>'
                f'<div class="sb-cell">{cap or "(무자막/컷 전환)"}</div>'
                f'<div class="sb-cell">{aud}</div>'
                f'</div>'
            )
            t += d
        sb_rows.append(
            f'<div class="sb-row">'
            f'<div class="sb-time">{_fmt_range(hook_sec, total_sec)}</div>'
            f'<div class="sb-cell"><strong>[공통 원본 리믹스 합류]</strong> 아래 공통 본편 타임코드표 그대로 연결.</div>'
            f'<div class="sb-cell">(공통 마스터 자막 사용)</div>'
            f'<div class="sb-cell">(공통 마스터 오디오 사용)</div>'
            f'</div>'
        )

        variant_sections.append(
            f'<section class="sec grid">'
            f'<div class="col-10"><h2>{v_title}</h2><p class="measure">{v_intro}</p></div>'
            f'<div class="col-12"><div class="hypo-strip">'
            f'<div><p class="hypo-label">검증 가설</p><p class="hypo-val">{_esc(v.get("hypothesis", ""))}</p></div>'
            f'<div><p class="hypo-label">원본 연결 지점</p><p class="hypo-val">{_esc(v.get("bridge_note", f"{hook_sec:g}초 원본 합류"))}</p></div>'
            f'<div><p class="hypo-label">필요 신규 소스</p><p class="hypo-val">{_esc(v.get("new_source_note", ""))}</p></div>'
            f'</div></div>'
            f'{kf_fig}'
            f'<div class="col-12"><div class="sb-head"><div>타임코드</div><div>화면·편집 소스</div><div>화면 자막</div><div>사운드·효과음</div></div>'
            f'{"".join(sb_rows)}</div>'
            f'</section>'
        )

        kpi = v.get("kpi") or {}
        kpi_rows.append(
            f'<tr><td>{_esc(v.get("label") or vk)} · {_esc(v.get("short_tag") or "")}</td>'
            f'<td>{_esc(v.get("hypothesis", ""))}</td>'
            f'<td>{_esc(kpi.get("primary_metric", ""))}</td>'
            f'<td>{_esc(kpi.get("risk", ""))}</td>'
            f'<td>{_esc(kpi.get("win_action", ""))}</td></tr>'
        )

    master_fig = ""
    m4 = spec.get("master_4cuts") or {}
    m4_uri = _encode_image_data_uri(m4.get("image"), base_dir, max_w=max_img_width)
    if m4_uri:
        master_fig = (
            f'<div class="col-12"><figure>'
            f'<p class="fig-title">{_esc(m4.get("title") or "원본 핵심 시연 프레임 추출")}</p>'
            f'<img src="{m4_uri}" alt="{_esc(m4.get("alt") or "master cuts")}" />'
            f'<figcaption>{_esc(m4.get("caption") or "")}</figcaption>'
            f'</figure></div>'
        )

    body_rows = []
    bt = hook_sec
    for seg in shared_body:
        d = _seg_dur(seg)
        src_rng = _fmt_range(float(seg.get("src_start", 0)), float(seg.get("src_end", 0))) if seg.get("type") == "source" else "신규/CTA"
        body_rows.append(
            f'<tr><td class="num">{_esc(seg.get("caption_timecode") or _fmt_range(bt, bt + d))}</td>'
            f'<td class="src-code">{_esc(seg.get("src_label") or src_rng)}</td>'
            f'<td>{_esc(seg.get("visual_note") or "")}</td>'
            f'<td>{_esc((seg.get("caption_text") or "").replace(chr(10), " "))}</td></tr>'
        )
        bt += d

    src_items = "".join(f"<li>{_esc(s)}</li>" for s in (spec.get("sources") or []))
    sub_strat = _esc(spec.get("burned_in_subtitle_strategy") or "원본 하단 자막 영역과 겹치지 않게 상단 25% 또는 에디토리얼 상단 여백에 새 자막을 고정 배치합니다.")
    build_note = _esc(spec.get("build_order_note") or "제작 순서 권장 — 가장 빠른 C안을 먼저 완성해 기준점을 잡고, 이어서 B안과 A안을 비교하세요.")

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{title}</title>
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=Noto+Sans+KR:wght@400;500;700&family=Noto+Serif+KR:wght@600;700;900&display=swap" rel="stylesheet" />
  <style>
{CSS_TEMPLATE}
  </style>
</head>
<body>
  <main class="page">
    <header class="grid">
      <div class="col-10">
        <h1>{title}</h1>
        <p class="deck">{deck}</p>
      </div>
      <div class="col-12 grid hero-split">
        <div class="col-7">
          <p class="verdict-lead">{verdict_lead}</p>
          <p class="measure">{verdict_body}</p>
        </div>
        <div class="col-5 emphasis-wrap">
          <p class="emphasis-num">{emphasis_num}</p>
          <p class="emphasis-cap">{emphasis_cap}</p>
        </div>
      </div>
    </header>

    <section class="sec grid">
      <div class="col-10">
        <h2>원본에서 반드시 살려야 할 핵심 소구 4가지</h2>
      </div>
      <div class="col-12"><div class="quad-strip">{"".join(usp_cards)}</div></div>
      <div class="col-12">
        <figure>
          <p class="fig-title">앞 {hook_sec:g}초 훅만 A·B·C로 분기하고 {hook_sec:g}초 지점에서 공통 원본 리믹스 본편으로 합류한다</p>
          {svg_block}
          <figcaption>단위: 초(sec). 본편 {body_dur:g}초는 완전히 통제하고, 오프닝 {hook_sec:g}초 훅의 순수 성과만 비교합니다.</figcaption>
        </figure>
      </div>
    </section>

    {"".join(variant_sections)}

    <section class="band">
      <div class="grid">
        <div class="col-10">
          <h2>공통 본편({hook_sec:g}–{total_sec:g}초): 마스터 컷편집 타임코드 시트</h2>
          <p class="measure">{sub_strat}</p>
        </div>
        {master_fig}
        <div class="col-12">
          <table>
            <thead><tr><th>완성 타임코드</th><th>원본 추출 구간</th><th>화면 구성</th><th>공통 리라이팅 자막</th></tr></thead>
            <tbody>{"".join(body_rows)}</tbody>
          </table>
        </div>
      </div>
    </section>

    <section class="sec grid">
      <div class="col-10">
        <h2>A·B·C 실험 판정 기준 및 다음 액션</h2>
        <p class="measure">세 버전을 동일 타겟 시간대에 게시하거나 동일 예산으로 48시간 동시 집행한 뒤 도달 축(조회수/공유)과 전환 축(댓글 DM/링크 클릭)을 분리해 판정하세요.</p>
      </div>
      <div class="col-12">
        <table>
          <thead><tr><th>버전</th><th>검증 가설</th><th>기대 우위 지표</th><th>주의할 리스크</th><th>승리 시 다음 액션</th></tr></thead>
          <tbody>{"".join(kpi_rows)}</tbody>
        </table>
      </div>
      <div class="col-12">
        <blockquote class="pullquote">
          <p>본편 시연은 그대로 두고 앞 {hook_sec:g}초 훅 3개만 분기해도, 최소 공수로 세 가지 광고 가설을 공정하게 검증할 수 있습니다.</p>
          <footer>{build_note}</footer>
        </blockquote>
      </div>
      <div class="col-10">
        <h2>Sources</h2>
        <ol class="sources-list">{src_items}</ol>
      </div>
    </section>
  </main>
</body>
</html>
"""


def main() -> None:
    p = argparse.ArgumentParser(description="Generate standalone HTML A/B/C Production & Edit Guide from 05_ad_spec.json")
    p.add_argument("--spec", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--max-img-width", type=int, default=1200)
    args = p.parse_args()

    with open(args.spec, "r", encoding="utf-8") as f:
        spec = json.load(f)
    base_dir = os.path.dirname(os.path.abspath(args.spec))
    html_str = build_html(spec, base_dir, max_img_width=args.max_img_width)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(html_str)

    print(json.dumps({"out": os.path.abspath(args.out), "bytes": len(html_str.encode("utf-8"))}, ensure_ascii=False))


if __name__ == "__main__":
    main()
