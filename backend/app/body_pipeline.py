"""FR-009 standalone body editing + TTS pipeline producing hookpipe-compatible body.mp4 & body.srt."""

from __future__ import annotations

import json
import os
import re
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from PIL import Image, ImageDraw, ImageFont

from .config import Settings
from .filming_guide_service import compute_target_body_duration
from .media_delivery import body_object_key
from .storage import StorageBackend
from .tts_service import (
    TARGET_LUFS,
    TARGET_SR,
    TTSProvider,
    build_tts_provider,
    measure_lufs,
    synthesize_body_narration,
)
from .upload_service import probe_video_metadata, recommended_framing

W, H = 1080, 1920
FPS = 30

EMOJI_RE = re.compile(
    "["
    "\U0001F300-\U0001F6FF"
    "\U0001F900-\U0001FAFF"
    "\U00002600-\U000027BF"
    "]+",
    flags=re.UNICODE,
)


def _load_cjk_font(size: int) -> ImageFont.ImageFont:
    candidates = [
        os.environ.get("SHORTFORM_FONT_BOLD", "").strip(),
        os.path.expanduser("~/Library/Fonts/NotoSansCJKkr-Bold.otf"),
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/noto-cjk/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/System/Library/Fonts/AppleSDGothicNeo.ttc",
        "/System/Library/Fonts/Helvetica.ttc",
    ]
    for path in candidates:
        if path and os.path.exists(path):
            try:
                if path.endswith(".ttc"):
                    return ImageFont.truetype(path, size, index=6)
                return ImageFont.truetype(path, size)
            except Exception:
                try:
                    return ImageFont.truetype(path, size)
                except Exception:
                    pass
    return ImageFont.load_default()


def _clean_caption_text(text: str) -> str:
    clean = EMOJI_RE.sub("", str(text or "")).strip()
    lines = [ln.strip() for ln in clean.splitlines() if ln.strip()][:2]
    return "\n".join(lines)


def _wrap_short_caption(text: str, max_chars: int = 10) -> str:
    words = [w for w in str(text or "").strip().split() if w]
    if not words:
        return ""
    lines: List[str] = []
    cur = ""
    for w in words:
        cand = f"{cur} {w}".strip() if cur else w
        if len(cand) <= max_chars or not cur:
            cur = cand
        else:
            lines.append(cur)
            cur = w
            if len(lines) >= 1:
                break
    if cur and len(lines) < 2:
        lines.append(cur)
    return "\n".join(lines[:2])


def build_body_script(product: Dict[str, Any], target_duration_sec: float) -> List[Dict[str, str]]:
    """Build 2~3 concise Korean '~습니다' narration + caption lines strictly from verified_facts."""
    _ = target_duration_sec
    name = str(product.get("name") or "제품").strip()
    facts = [str(f).strip() for f in (product.get("verified_facts") or []) if str(f).strip()]
    if not facts:
        facts = [f"{name}의 실사용 장점을 직접 확인할 수 있습니다"]

    f1 = facts[0].rstrip(".!")
    lines: List[Dict[str, str]] = [
        {
            "narration": f"이 제품은 {name}입니다.",
            "caption": _wrap_short_caption(name, max_chars=10) or name[:10],
        },
        {
            "narration": f"{f1} 구조로 설계되었습니다." if not f1.endswith("다") else f"{f1}.",
            "caption": _wrap_short_caption(f1, max_chars=10) or f1[:10],
        },
    ]
    if len(facts) > 1:
        f2 = facts[1].rstrip(".!")
        lines.append(
            {
                "narration": f"{f2} 점이 실사용 핵심입니다." if not f2.endswith("다") else f"{f2}.",
                "caption": _wrap_short_caption(f2, max_chars=10) or f2[:10],
            }
        )
    return lines


def _format_srt_timestamp(sec: float) -> str:
    ms = int(round(max(0.0, sec) * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def write_body_srt(segments: Sequence[Dict[str, Any]], out_srt: Path) -> None:
    lines: List[str] = []
    idx = 1
    for seg in segments:
        st = float(seg["start_sec"])
        en = float(seg["end_sec"])
        cap = _clean_caption_text(seg.get("caption") or seg.get("narration") or "")
        if not cap or en <= st:
            continue
        lines.extend([str(idx), f"{_format_srt_timestamp(st)} --> {_format_srt_timestamp(en)}", cap, ""])
        idx += 1
    out_srt.parent.mkdir(parents=True, exist_ok=True)
    out_srt.write_text("\n".join(lines), encoding="utf-8")


def _render_caption_png(text: str, out_png: Path, *, y_center: int = 1360) -> None:
    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    clean = _clean_caption_text(text)
    if not clean:
        canvas.save(out_png, format="PNG")
        return

    draw = ImageDraw.Draw(canvas)
    font = _load_cjk_font(62)
    lines = clean.splitlines()[:2]
    line_heights: List[int] = []
    line_widths: List[int] = []
    for ln in lines:
        bbox = draw.textbbox((0, 0), ln, font=font, stroke_width=8)
        line_widths.append(bbox[2] - bbox[0])
        line_heights.append(bbox[3] - bbox[1])

    gap = 14
    total_h = sum(line_heights) + gap * max(0, len(lines) - 1)
    y_cur = y_center - total_h // 2
    for idx, ln in enumerate(lines):
        x = (W - line_widths[idx]) // 2
        draw.text(
            (x, y_cur),
            ln,
            font=font,
            fill=(255, 255, 255, 255),
            stroke_width=8,
            stroke_fill=(12, 14, 18, 255),
        )
        y_cur += line_heights[idx] + gap
    out_png.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out_png, format="PNG")


def _framing_filter(in_w: int, in_h: int, framing: str, *, speed: float = 1.0, pad_sec: float = 0.0) -> str:
    parts: List[str] = []
    if abs(speed - 1.0) > 1e-3:
        parts.append(f"setpts=PTS/{speed:.4f}")

    if framing == "blur-bleed":
        fg_w = W
        fg_h = int(round(fg_w * in_h / max(in_w, 1)))
        max_fg_h = H - 520
        if fg_h > max_fg_h:
            fg_h = max_fg_h
            fg_w = int(round(fg_h * in_w / max(in_h, 1)))
        fg_w = max(2, fg_w - (fg_w % 2))
        fg_h = max(2, fg_h - (fg_h % 2))
        fg_x = (W - fg_w) // 2
        fg_y = (H - fg_h) // 2
        pre_str = (",".join(parts) + ",") if parts else ""
        tail = f",tpad=stop_mode=clone:stop_duration={pad_sec:.3f}" if pad_sec > 0.02 else ""
        return (
            f"[0:v]{pre_str}split=2[fg_src][bg_src];"
            f"[bg_src]scale={W}:{H}:force_original_aspect_ratio=increase:flags=lanczos,"
            f"crop={W}:{H},gblur=sigma=32,eq=brightness=-0.13:saturation=1.08[bg];"
            f"[fg_src]scale={fg_w}:{fg_h}:flags=lanczos[fg];"
            f"[bg][fg]overlay={fg_x}:{fg_y}{tail},fps={FPS},setsar=1,format=yuv420p[vout]"
        )

    parts.append(f"scale={W}:{H}:force_original_aspect_ratio=increase:flags=lanczos")
    parts.append(f"crop={W}:{H}:(iw-{W})*0.500:(ih-{H})*0.500")
    if pad_sec > 0.02:
        parts.append(f"tpad=stop_mode=clone:stop_duration={pad_sec:.3f}")
    parts.extend([f"fps={FPS}", "setsar=1", "format=yuv420p"])
    return f"[0:v]{','.join(parts)}[vout]"


def _resolve_clip_local_path(
    clip: Dict[str, Any],
    dest_dir: Path,
    storage: StorageBackend,
) -> Path:
    lp = clip.get("local_path")
    if lp and os.path.exists(lp):
        return Path(lp).resolve()
    key = clip["object_key"]
    resolve_local = getattr(storage, "resolve_local_path", None)
    if callable(resolve_local):
        found = resolve_local(key)
        if found is not None:
            return found
    dest = dest_dir / f"shot_{int(clip.get('shot_no') or 1):02d}_{Path(key).name}"
    storage.download_file(key, dest)
    return dest


def _allocate_clip_durations(clips_meta: List[Dict[str, Any]], target_total: float) -> List[float]:
    raw_durs = [max(0.2, float(c["duration_sec"])) for c in clips_meta]
    raw_sum = sum(raw_durs)
    if raw_sum <= 0.0:
        return [target_total / max(1, len(clips_meta))] * len(clips_meta)
    allocated = [round(target_total * (d / raw_sum), 3) for d in raw_durs]
    if allocated:
        allocated[-1] = round(max(0.2, target_total - sum(allocated[:-1])), 3)
    return allocated


def build_body_video(
    project: Dict[str, Any],
    *,
    storage: StorageBackend,
    settings: Settings,
    tts_provider: Optional[TTSProvider] = None,
    target_duration_sec: Optional[float] = None,
    tts_enabled: bool = True,
    voice_id: Optional[str] = None,
    burn_captions: Optional[bool] = None,
    custom_lines: Optional[List[Dict[str, str]]] = None,
    scenarios: Optional[Sequence[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Assemble uploaded clips (1..20) + body TTS into standard 1080x1920 30fps -14 LUFS body.mp4 + body.srt."""
    uploads = project.get("uploads") or {}
    raw_clips = sorted(uploads.get("clips") or [], key=lambda c: int(c.get("shot_no") or 0))
    if not raw_clips:
        raise ValueError("본편을 생성하기 전에 원본 영상을 업로드해 주세요.")

    if target_duration_sec is not None:
        target_dur = max(5.0, float(target_duration_sec))
    elif (project.get("filming_guide") or {}).get("target_body_duration_sec"):
        target_dur = max(5.0, float(project["filming_guide"]["target_body_duration_sec"]))
    else:
        sel_id = project.get("selected_scenario_id")
        sel_scn = next((s for s in (scenarios or []) if s.get("scenario_id") == sel_id), None)
        target_dur = compute_target_body_duration(sel_scn) if sel_scn else 12.0

    body_id = f"body_{uuid.uuid4().hex[:10]}"
    work_dir = Path(settings.work_root).resolve() / project["project_id"] / "body" / body_id
    src_dir = work_dir / "src"
    seg_dir = work_dir / "segs"
    ov_dir = work_dir / "overlays"
    out_dir = work_dir / "out"
    for d in (src_dir, seg_dir, ov_dir, out_dir):
        d.mkdir(parents=True, exist_ok=True)

    # 1. Resolve & probe all uploaded clips
    clips_meta: List[Dict[str, Any]] = []
    for clip in raw_clips:
        local_src = _resolve_clip_local_path(clip, src_dir, storage)
        probed = probe_video_metadata(str(local_src))
        clips_meta.append(
            {
                "shot_no": int(clip.get("shot_no") or len(clips_meta) + 1),
                "path": local_src,
                "duration_sec": float(probed["duration_sec"]),
                "width": int(probed["width"]),
                "height": int(probed["height"]),
                "framing": clip.get("recommended_framing") or recommended_framing(probed["width"], probed["height"]),
            }
        )

    # 2. Build script & synthesize TTS (if enabled)
    lines = custom_lines or build_body_script(project["product"], target_dur)
    vo_wav_path: Optional[Path] = None
    vo_segments: List[Dict[str, Any]] = []
    vo_lufs: Optional[float] = None

    if tts_enabled:
        provider = tts_provider or build_tts_provider(settings)
        vo_res = synthesize_body_narration(lines, work_dir, provider, voice_id=voice_id)
        vo_wav_path = Path(vo_res["wav_path"])
        vo_segments = list(vo_res["segments"])
        vo_lufs = (vo_res.get("lufs") or {}).get("final_lufs")
        final_dur = round(max(target_dur, float(vo_res["duration_sec"]) + 0.25), 3)
    else:
        final_dur = round(target_dur, 3)
        per_line = round(final_dur / max(1, len(lines)), 3)
        t_cur = 0.0
        for idx, line in enumerate(lines):
            t_end = round(min(final_dur, t_cur + per_line), 3)
            vo_segments.append(
                {
                    "index": idx + 1,
                    "narration": line.get("narration", ""),
                    "caption": line.get("caption", ""),
                    "start_sec": round(t_cur, 3),
                    "end_sec": t_end,
                    "duration_sec": round(t_end - t_cur, 3),
                }
            )
            t_cur = t_end

    # 3. Normalize each clip segment to 1080x1920 30fps CFR H.264
    alloc_durs = _allocate_clip_durations(clips_meta, final_dur)
    seg_files: List[Path] = []
    for idx, (cmeta, alloc) in enumerate(zip(clips_meta, alloc_durs)):
        src_dur = cmeta["duration_sec"]
        speed = 1.0
        pad_sec = 0.0
        in_trim = min(src_dur, alloc)
        if alloc > src_dur:
            # Stretch up to 0.85x slow motion, then freeze last frame if still needed
            slow_max_dur = src_dur / 0.85
            if alloc <= slow_max_dur:
                speed = src_dur / alloc
                in_trim = src_dur
            else:
                speed = 0.85
                in_trim = src_dur
                pad_sec = max(0.0, alloc - slow_max_dur)

        fc = _framing_filter(cmeta["width"], cmeta["height"], cmeta["framing"], speed=speed, pad_sec=pad_sec)
        seg_out = seg_dir / f"seg_{idx + 1:02d}.mp4"
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-v",
                "error",
                "-i",
                str(cmeta["path"]),
                "-t",
                f"{in_trim:.3f}",
                "-filter_complex",
                fc,
                "-map",
                "[vout]",
                "-t",
                f"{alloc:.3f}",
                "-an",
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-crf",
                "20",
                "-pix_fmt",
                "yuv420p",
                "-r",
                str(FPS),
                str(seg_out),
            ],
            check=True,
            capture_output=True,
        )
        seg_files.append(seg_out)

    # 4. Concatenate normalized video cuts
    concat_txt = work_dir / "concat.txt"
    concat_txt.write_text(
        "\n".join(f"file '{p.resolve().as_posix()}'" for p in seg_files),
        encoding="utf-8",
    )
    video_joined = work_dir / "body_video_only.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-v",
            "error",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_txt),
            "-c",
            "copy",
            str(video_joined),
        ],
        check=True,
        capture_output=True,
    )

    # 5. Write body.srt & optionally burn captions with PIL PNG overlays
    srt_path = out_dir / "body.srt"
    write_body_srt(vo_segments, srt_path)

    do_burn = settings.hook_burn_captions if burn_captions is None else bool(burn_captions)
    video_with_subs = video_joined
    if do_burn and vo_segments:
        ov_inputs: List[str] = []
        ov_filters: List[str] = []
        cur_lbl = "[0:v]"
        ov_idx = 0
        for s_idx, seg in enumerate(vo_segments):
            cap = _clean_caption_text(seg.get("caption") or seg.get("narration") or "")
            st = float(seg["start_sec"])
            en = float(seg["end_sec"])
            if not cap or en <= st:
                continue
            ov_png = ov_dir / f"ov_{s_idx + 1:02d}.png"
            _render_caption_png(cap, ov_png)
            ov_inputs.extend(["-loop", "1", "-t", f"{final_dur:.3f}", "-i", str(ov_png)])
            in_idx = ov_idx + 1
            next_lbl = f"[vov{ov_idx}]"
            ov_filters.append(
                f"{cur_lbl}[{in_idx}:v]overlay=0:0:enable='between(t,{st:.3f},{en:.3f})'{next_lbl}"
            )
            cur_lbl = next_lbl
            ov_idx += 1

        if ov_filters:
            video_with_subs = work_dir / "body_captioned.mp4"
            subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-v",
                    "error",
                    "-i",
                    str(video_joined),
                    *ov_inputs,
                    "-filter_complex",
                    ";".join(ov_filters),
                    "-map",
                    cur_lbl,
                    "-c:v",
                    "libx264",
                    "-preset",
                    "veryfast",
                    "-crf",
                    "19",
                    "-pix_fmt",
                    "yuv420p",
                    "-r",
                    str(FPS),
                    "-t",
                    f"{final_dur:.3f}",
                    str(video_with_subs),
                ],
                check=True,
                capture_output=True,
            )

    # 6. Mux 48kHz stereo AAC audio (-14 LUFS when VO present, clean silent stereo track otherwise)
    body_mp4 = out_dir / "body.mp4"
    if vo_wav_path is not None and vo_wav_path.is_file():
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-v",
                "error",
                "-i",
                str(video_with_subs),
                "-i",
                str(vo_wav_path),
                "-filter_complex",
                f"[1:a]aresample={TARGET_SR},apad=whole_dur={final_dur:.3f},atrim=0:{final_dur:.3f}[aout]",
                "-map",
                "0:v",
                "-map",
                "[aout]",
                "-c:v",
                "copy",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                "-ar",
                str(TARGET_SR),
                "-ac",
                "2",
                "-movflags",
                "+faststart",
                str(body_mp4),
            ],
            check=True,
            capture_output=True,
        )
        measured_final_lufs = measure_lufs(body_mp4)
    else:
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-v",
                "error",
                "-i",
                str(video_with_subs),
                "-f",
                "lavfi",
                "-i",
                f"anullsrc=channel_layout=stereo:sample_rate={TARGET_SR}",
                "-map",
                "0:v",
                "-map",
                "1:a",
                "-c:v",
                "copy",
                "-c:a",
                "aac",
                "-b:a",
                "128k",
                "-ar",
                str(TARGET_SR),
                "-ac",
                "2",
                "-t",
                f"{final_dur:.3f}",
                "-movflags",
                "+faststart",
                str(body_mp4),
            ],
            check=True,
            capture_output=True,
        )
        measured_final_lufs = None

    final_probe = probe_video_metadata(str(body_mp4))

    # 7. Upload deliverables to StorageBackend using canonical object_keys
    mp4_key = body_object_key(project["project_id"], body_id, "body.mp4")
    srt_key = body_object_key(project["project_id"], body_id, "body.srt")
    storage.upload_file(body_mp4, mp4_key)
    storage.upload_file(srt_path, srt_key)

    vo_key: Optional[str] = None
    if vo_wav_path is not None and vo_wav_path.is_file():
        vo_key = body_object_key(project["project_id"], body_id, "body_vo.wav")
        storage.upload_file(vo_wav_path, vo_key)

    manifest = {
        "body_id": body_id,
        "project_id": project["project_id"],
        "clip_count": len(clips_meta),
        "duration_sec": round(float(final_probe["duration_sec"]), 3),
        "width": int(final_probe["width"]),
        "height": int(final_probe["height"]),
        "fps": float(final_probe["fps"]),
        "lufs": measured_final_lufs if measured_final_lufs is not None else vo_lufs,
        "tts_enabled": bool(tts_enabled),
        "burn_captions": do_burn,
        "object_keys": {
            "body_video": mp4_key,
            "body_srt": srt_key,
            "body_audio": vo_key,
        },
        "segments": vo_segments,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    (out_dir / "body_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return manifest
