#!/usr/bin/env python3
"""Programmatic 9:16 Shortform Ad Remix Assembler (macOS ffmpeg 8.0.1 safe).

Renders 1080x1920 30fps publishable MP4s (clean copy + overlaid master + .srt + qa strip).
Supports both:
  - `variants` mode (`abc_remix`: A/B/C hooks + shared_body_cuts)
  - `timeline` mode (single cohesive 30s+ narrative master)

Framing modes:
  - `smart-crop`: full-bleed 1080x1920 edge-to-edge crop (optional `crop_x_ratio` 0..1 & `punch_zoom`)
  - `blur-bleed`: full-bleed blurred atmospheric background from the same source + sharp 1080w hero center
  - `editorial-card`: clean 1080w center card over solid matte (`#13161D`)

Caption styles:
  - `reels_kinetic`: large bold outline+shadow kinetic text with `**highlight**` yellow/accent emphasis & optional `pop_badge`
  - `boxed`: semi-transparent top banner container

Audio 3-Bus Architecture:
  - Strips original baked BGM cleanly via `audio_owner: "mute"`
  - Renders `bgm_timeline` stems (with exact twist dead-stop & post-drop full arrangement) via sample-accurate NumPy mixer
  - Applies FFmpeg `sidechaincompress` keying BGM under crisp Korean `vo_audio`
  - Mixes sample-accurate `sfx_events` (decoded cleanly to 48kHz stereo) + optional subtle clip room audio
  - Masters cleanly via 2-pass `ebur128` -> linear `volume + alimiter=limit=0.82:level=disabled` -> `ebur128` (-14.0 LUFS)

Uses ONLY Python stdlib + PIL + numpy + ffmpeg/ffprobe (NO drawtext/subtitles/libass, NO direct loudnorm, NO matplotlib/scipy).
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import shutil
import subprocess
import tempfile
import wave
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1920
FPS = 30
TARGET_LUFS = -14.0
SR = 48000

DISCLOSURE_TEXT = {
    "paid_ad": "유료광고",
    "sponsored": "협찬",
    "ai_assisted": "AI 연출 포함",
    "own_brand": "자사제품",
    "none": "",
}


def _load_cjk_font(size: int, bold: bool = True) -> ImageFont.ImageFont:
    env_bold = os.environ.get("SHORTFORM_FONT_BOLD", "").strip()
    env_reg = os.environ.get("SHORTFORM_FONT_REGULAR", "").strip()
    candidates = (
        [
            env_bold,
            os.path.expanduser("~/Library/Fonts/NotoSansCJKkr-Bold.otf"),
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
            "/usr/share/fonts/noto-cjk/NotoSansCJK-Bold.ttc",
            "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/System/Library/Fonts/AppleSDGothicNeo.ttc",
            os.path.expanduser("~/Library/Fonts/NotoSansCJKkr-Regular.otf"),
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        ]
        if bold
        else [
            env_reg,
            os.path.expanduser("~/Library/Fonts/NotoSansCJKkr-Regular.otf"),
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            os.path.expanduser("~/Library/Fonts/NotoSansCJKkr-Bold.otf"),
            "/System/Library/Fonts/AppleSDGothicNeo.ttc",
            "/System/Library/Fonts/Helvetica.ttc",
        ]
    )
    for p in candidates:
        if p and os.path.exists(p):
            try:
                if p.endswith(".ttc") and bold:
                    return ImageFont.truetype(p, size, index=6)
                return ImageFont.truetype(p, size)
            except Exception:
                try:
                    return ImageFont.truetype(p, size)
                except Exception:
                    pass
    return ImageFont.load_default()


def _resolve_path(path: Optional[str], base_dir: str) -> Optional[str]:
    if not path:
        return None
    if os.path.isabs(path):
        return path
    cand = os.path.join(base_dir, path)
    if os.path.exists(cand):
        return cand
    return os.path.abspath(path)


def _hex_to_rgb(hex_color: str, default: Tuple[int, int, int] = (18, 21, 28)) -> Tuple[int, int, int]:
    h = (hex_color or "").strip().lstrip("#")
    if len(h) == 6:
        try:
            return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        except ValueError:
            pass
    return default


def ffprobe_info(path: str) -> Dict[str, Any]:
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration:stream=codec_type,width,height,r_frame_rate",
        "-of", "json", path,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
    raw = json.loads(proc.stdout)
    dur = float(raw.get("format", {}).get("duration", 0.0) or 0.0)
    streams = raw.get("streams", [])
    vs = next((s for s in streams if s.get("codec_type") == "video"), {})
    has_audio = any(s.get("codec_type") == "audio" for s in streams)
    return {
        "duration": dur,
        "width": int(vs.get("width", 0) or 0),
        "height": int(vs.get("height", 0) or 0),
        "has_audio": has_audio,
    }


def _decode_audio_f32(
    path: str,
    *,
    trim_start: float = 0.0,
    duration: Optional[float] = None,
    sample_rate: int = SR,
    channels: int = 2,
) -> np.ndarray:
    cmd = ["ffmpeg", "-y", "-v", "error"]
    if trim_start > 0:
        cmd.extend(["-ss", f"{trim_start:.3f}"])
    if duration is not None and duration > 0:
        cmd.extend(["-t", f"{duration:.3f}"])
    cmd.extend([
        "-i", path,
        "-f", "f32le", "-acodec", "pcm_f32le",
        "-ac", str(channels), "-ar", str(sample_rate),
        "pipe:1",
    ])
    proc = subprocess.run(cmd, capture_output=True, check=True)
    arr = np.frombuffer(proc.stdout, dtype=np.float32)
    frames = len(arr) // channels
    return arr[: frames * channels].reshape((frames, channels))


def _write_wav_f32(out_wav: str, samples: np.ndarray, sample_rate: int = SR) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(out_wav)), exist_ok=True)
    pcm = np.clip(samples * 32767.0, -32767, 32767).astype("<i2")
    with wave.open(out_wav, "wb") as wf:
        wf.setnchannels(pcm.shape[1])
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm.tobytes())


def _synth_sfx_wav(preset: str, dur: float, out_wav: str, sr: int = SR) -> None:
    """Fallback procedural SFX bed when an explicit .caf/.wav SFX preset is not provided."""
    n = max(1, int(round(dur * sr)))
    t = np.arange(n, dtype=np.float32) / sr
    if preset == "suspense_rumble":
        sig = (
            0.16 * np.sin(2.0 * np.pi * 56.0 * t)
            + 0.09 * np.sin(2.0 * np.pi * 112.0 * t)
            + 0.04 * np.sin(2.0 * np.pi * 2.2 * t) * np.sin(2.0 * np.pi * 78.0 * t)
        )
        env = np.clip(np.minimum(1.0, t / 0.25) * np.minimum(1.0, (dur - t) / 0.12), 0.0, 1.0)
        sig *= env
    elif preset == "ding":
        sig = 0.30 * np.sin(2.0 * np.pi * 987.77 * t) + 0.16 * np.sin(2.0 * np.pi * 1479.98 * t)
        sig *= np.exp(-t * 5.8)
    elif preset == "whoosh":
        rng = np.random.default_rng(42)
        noise = rng.normal(0.0, 1.0, size=n).astype(np.float32)
        smooth = np.convolve(noise, np.ones(48, dtype=np.float32) / 48.0, mode="same")
        sig = 0.22 * smooth * (np.sin(np.pi * np.clip(t / max(dur, 0.05), 0.0, 1.0)) ** 1.5)
    else:
        sig = np.zeros(n, dtype=np.float32)
    _write_wav_f32(out_wav, np.stack([sig, sig], axis=1), sr)


def _seg_dur(seg: Dict[str, Any]) -> float:
    if seg.get("type") == "source" and "src_start" in seg and "src_end" in seg:
        spd = float(seg.get("speed", 1.0) or 1.0)
        return max(0.05, (float(seg["src_end"]) - float(seg["src_start"])) / max(spd, 0.01))
    return max(0.05, float(seg.get("duration", 1.0) or 1.0))


def _build_video_filter_graph(
    in_w: int,
    in_h: int,
    framing: str,
    bottom_crop_px: int,
    bg_hex: str,
    card_y: int,
    speed: float,
    crop_x_ratio: float = 0.5,
    punch_zoom: float = 1.0,
) -> str:
    """Return FFmpeg video filter_complex mapping `[0:v]` to crisp `[vout]` (1080x1920 30fps)."""
    pre: List[str] = []
    if abs(speed - 1.0) > 1e-3:
        pre.append(f"setpts=PTS/{speed:.4f}")

    work_h = in_h
    if bottom_crop_px > 0 and framing in ("editorial-card", "smart-crop", "blur-bleed") and in_h > bottom_crop_px + 200:
        work_h = in_h - bottom_crop_px
        pre.append(f"crop={in_w}:{work_h}:0:0")

    cx = min(1.0, max(0.0, float(crop_x_ratio)))
    pz = max(1.0, float(punch_zoom or 1.0))

    if framing == "blur-bleed":
        r, g, b = _hex_to_rgb(bg_hex, (18, 20, 26))
        bg_chain = (
            f"scale={W}:{H}:force_original_aspect_ratio=increase:flags=lanczos,"
            f"crop={W}:{H},gblur=sigma=32,eq=brightness=-0.13:saturation=1.08"
        )
        fg_w = W
        fg_h = int(round(fg_w * work_h / max(in_w, 1)))
        max_fg_h = H - 520
        if fg_h > max_fg_h:
            fg_h = max_fg_h
            fg_w = int(round(fg_h * in_w / max(work_h, 1)))
        fg_w = max(2, fg_w - (fg_w % 2))
        fg_h = max(2, fg_h - (fg_h % 2))
        fg_x = (W - fg_w) // 2
        fg_y = min(max(240, card_y), H - fg_h - 380)
        pre_str = (",".join(pre) + ",") if pre else ""
        return (
            f"[0:v]{pre_str}split=2[fg_src][bg_src];"
            f"[bg_src]{bg_chain}[bg];"
            f"[fg_src]scale={fg_w}:{fg_h}:flags=lanczos[fg];"
            f"[bg][fg]overlay={fg_x}:{fg_y},fps={FPS},setsar=1,format=yuv420p[vout]"
        )

    parts = list(pre)
    if framing == "editorial-card":
        r, g, b = _hex_to_rgb(bg_hex)
        bg_hex_ff = f"0x{r:02x}{g:02x}{b:02x}"
        card_w = W
        card_h = int(round(card_w * work_h / max(in_w, 1)))
        max_card_h = H - card_y - 360
        if card_h > max_card_h:
            card_h = max_card_h
            card_w = int(round(card_h * in_w / max(work_h, 1)))
        card_w = max(2, card_w - (card_w % 2))
        card_h = max(2, card_h - (card_h % 2))
        px = (W - card_w) // 2
        parts.append(f"scale={card_w}:{card_h}:flags=lanczos")
        parts.append(f"pad={W}:{H}:{px}:{card_y}:color={bg_hex_ff}")
    elif framing == "smart-crop":
        tw = int(round(W * pz))
        th = int(round(H * pz))
        parts.append(f"scale={tw}:{th}:force_original_aspect_ratio=increase:flags=lanczos")
        parts.append(f"crop={W}:{H}:(iw-{W})*{cx:.3f}:(ih-{H})*0.500")
    else:  # full-bleed
        parts.append(f"scale={W}:{H}:force_original_aspect_ratio=increase:flags=lanczos")
        parts.append(f"crop={W}:{H}:(iw-{W})*{cx:.3f}:(ih-{H})*0.500")

    parts.extend([f"fps={FPS}", "setsar=1", "format=yuv420p"])
    return f"[0:v]{','.join(parts)}[vout]"


def render_segment(
    seg: Dict[str, Any],
    spec: Dict[str, Any],
    base_dir: str,
    out_mp4: str,
    *,
    preview_animatic: bool = False,
) -> float:
    """Render one normalized 1080x1920 30fps stereo 48kHz segment MP4."""
    stype = seg.get("type", "source")
    framing = seg.get("framing") or spec.get("framing_mode", "smart-crop")
    bg_hex = seg.get("bg_color") or spec.get("editorial_bg_color", "#12141A")
    card_y = int(seg.get("card_y") or spec.get("editorial_card_y", 380) or 380)
    bottom_crop = int(seg.get("bottom_crop_px", spec.get("bottom_crop_px", 0)) or 0)
    speed = float(seg.get("speed", 1.0) or 1.0)
    crop_x_ratio = float(seg.get("crop_x_ratio", 0.5) if seg.get("crop_x_ratio") is not None else 0.5)
    punch_zoom = float(seg.get("punch_zoom", 1.0) or 1.0)
    audio_owner = seg.get("audio_owner", "source_audio")
    gain_db = float(seg.get("audio_gain_db", 0.0) or 0.0)
    sfx_preset = seg.get("sfx_preset")

    if stype == "flow_video":
        flow_clip = _resolve_path(seg.get("path"), base_dir)
        fallback_img = _resolve_path(seg.get("fallback_image"), base_dir)
        if not preview_animatic and flow_clip and os.path.exists(flow_clip):
            stype = "video"
            seg = {**seg, "path": flow_clip}
        elif fallback_img and os.path.exists(fallback_img):
            stype = "image"
            seg = {**seg, "path": fallback_img}
        else:
            raise RuntimeError(
                f"flow_video segment missing clip ({seg.get('path')}) and fallback_image ({seg.get('fallback_image')})"
            )

    dur = _seg_dur(seg)
    os.makedirs(os.path.dirname(os.path.abspath(out_mp4)), exist_ok=True)

    if stype == "silence_gap":
        # If freeze_frame is provided, hold a subtle dimmed stillness frame instead of flat empty screen
        freeze_src = _resolve_path(seg.get("freeze_image"), base_dir)
        if freeze_src and os.path.exists(freeze_src):
            frames = max(2, int(round(dur * FPS)))
            tmp_dir = tempfile.mkdtemp(prefix="ad_gap_")
            try:
                pre_png = os.path.join(tmp_dir, "gap.png")
                with Image.open(freeze_src) as im:
                    rgb = im.convert("RGB")
                    sf = max(W / rgb.width, H / rgb.height)
                    rw, rh = int(round(rgb.width * sf)), int(round(rgb.height * sf))
                    rs = rgb.resize((rw, rh), Image.Resampling.LANCZOS)
                    rs.crop(((rw - W) // 2, (rh - H) // 2, (rw - W) // 2 + W, (rh - H) // 2 + H)).save(pre_png)
                subprocess.run(
                    [
                        "ffmpeg", "-y", "-v", "error",
                        "-loop", "1", "-t", f"{dur:.3f}", "-i", pre_png,
                        "-f", "lavfi", "-i", f"anullsrc=channel_layout=stereo:sample_rate={SR}:d={dur:.3f}",
                        "-vf", f"eq=brightness=-0.16:saturation=0.55,fps={FPS},setsar=1,format=yuv420p",
                        "-shortest", "-c:v", "libx264", "-preset", "fast", "-crf", "18", "-pix_fmt", "yuv420p",
                        "-c:a", "aac", "-b:a", "192k", "-ar", str(SR), "-ac", "2", out_mp4,
                    ],
                    check=True,
                )
            finally:
                shutil.rmtree(tmp_dir, ignore_errors=True)
            return dur

        r, g, b = _hex_to_rgb(bg_hex, (9, 11, 14))
        color_hex = f"0x{r:02x}{g:02x}{b:02x}"
        subprocess.run(
            [
                "ffmpeg", "-y", "-v", "error",
                "-f", "lavfi", "-i", f"color=c={color_hex}:s={W}x{H}:r={FPS}:d={dur:.3f}",
                "-f", "lavfi", "-i", f"anullsrc=channel_layout=stereo:sample_rate={SR}:d={dur:.3f}",
                "-shortest", "-c:v", "libx264", "-preset", "fast", "-crf", "18", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", "192k", "-ar", str(SR), "-ac", "2", out_mp4,
            ],
            check=True,
        )
        return dur

    if stype == "image":
        img_path = _resolve_path(seg.get("path"), base_dir)
        if not img_path or not os.path.exists(img_path):
            raise RuntimeError(f"Missing image segment path: {seg.get('path')}")
        frames = max(2, int(round(dur * FPS)))
        motion = seg.get("motion", "zoom_in")
        if motion == "zoom_out":
            z_expr, x_expr, y_expr = f"1.12-0.12*on/{frames}", "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"
        elif motion == "pan_right":
            z_expr, x_expr, y_expr = "1.10", f"(iw-iw/zoom)*on/{frames}", "ih/2-(ih/zoom/2)"
        elif motion == "pan_left":
            z_expr, x_expr, y_expr = "1.10", f"(iw-iw/zoom)*(1-on/{frames})", "ih/2-(ih/zoom/2)"
        else:
            z_expr, x_expr, y_expr = f"1.0+0.12*on/{frames}", "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"

        tmp_dir = tempfile.mkdtemp(prefix="ad_imgseg_")
        try:
            pre_png = os.path.join(tmp_dir, "pre.png")
            with Image.open(img_path) as im:
                rgb = im.convert("RGB")
                tw, th = W * 2, H * 2
                scale_f = max(tw / rgb.width, th / rgb.height)
                rw, rh = max(tw, int(round(rgb.width * scale_f))), max(th, int(round(rgb.height * scale_f)))
                rs = rgb.resize((rw, rh), Image.Resampling.LANCZOS)
                lx, ly = (rw - tw) // 2, (rh - th) // 2
                rs.crop((lx, ly, lx + tw, ly + th)).save(pre_png, format="PNG")

            wav_path = None
            if sfx_preset and audio_owner not in ("silence", "mute"):
                wav_path = os.path.join(tmp_dir, "sfx.wav")
                _synth_sfx_wav(sfx_preset, dur, wav_path)

            vf = f"zoompan=z='{z_expr}':x='{x_expr}':y='{y_expr}':d={frames}:s={W}x{H}:fps={FPS},setsar=1,format=yuv420p"
            cmd = ["ffmpeg", "-y", "-v", "error", "-i", pre_png]
            if wav_path:
                cmd.extend(["-i", wav_path])
            else:
                cmd.extend(["-f", "lavfi", "-i", f"anullsrc=channel_layout=stereo:sample_rate={SR}:d={dur:.3f}"])
            cmd.extend([
                "-vf", vf,
                "-af", f"volume={gain_db:.2f}dB,aresample={SR},apad=whole_dur={dur:.3f},atrim=0:{dur:.3f}",
                "-t", f"{dur:.3f}",
                "-c:v", "libx264", "-preset", "fast", "-crf", "18", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", "192k", "-ar", str(SR), "-ac", "2",
                out_mp4,
            ])
            subprocess.run(cmd, check=True)
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        return dur

    # stype == "source" or "video"
    src_path = _resolve_path(seg.get("path") or (spec.get("source_video") if stype == "source" else None), base_dir)
    if not src_path or not os.path.exists(src_path):
        raise RuntimeError(f"Missing video segment source: {src_path}")

    info = ffprobe_info(src_path)
    src_start = float(seg.get("src_start", 0.0) or 0.0)
    if stype == "source" and "src_end" in seg:
        raw_dur = float(seg["src_end"]) - src_start
    else:
        raw_dur = float(seg.get("duration", info["duration"]) or info["duration"]) * speed

    v_graph = _build_video_filter_graph(
        info["width"], info["height"], framing, bottom_crop, bg_hex, card_y, speed,
        crop_x_ratio=crop_x_ratio, punch_zoom=punch_zoom,
    )
    tmp_dir = tempfile.mkdtemp(prefix="ad_vidseg_")
    try:
        sfx_wav = None
        if sfx_preset and audio_owner not in ("silence", "mute"):
            sfx_wav = os.path.join(tmp_dir, "sfx.wav")
            _synth_sfx_wav(sfx_preset, dur, sfx_wav)

        cmd = ["ffmpeg", "-y", "-v", "error", "-ss", f"{src_start:.3f}", "-t", f"{raw_dur:.3f}", "-i", src_path]
        use_source_audio = info["has_audio"] and audio_owner not in ("silence", "mute", "sfx_only") and gain_db > -50.0
        if not use_source_audio:
            cmd.extend(["-f", "lavfi", "-i", f"anullsrc=channel_layout=stereo:sample_rate={SR}:d={dur:.3f}"])
        if sfx_wav:
            cmd.extend(["-i", sfx_wav])

        if use_source_audio:
            base_af = f"[0:a]atempo={speed:.4f},volume={gain_db:.2f}dB,aresample={SR},apad=whole_dur={dur:.3f},atrim=0:{dur:.3f}[abase]"
        else:
            base_af = f"[1:a]aresample={SR},apad=whole_dur={dur:.3f},atrim=0:{dur:.3f}[abase]"

        if sfx_wav:
            sfx_idx = 1 if use_source_audio else 2
            fc = (
                f"{v_graph};"
                f"{base_af};"
                f"[{sfx_idx}:a]aresample={SR},apad=whole_dur={dur:.3f},atrim=0:{dur:.3f}[asfx];"
                f"[abase][asfx]amix=inputs=2:duration=first:normalize=0[aout]"
            )
        else:
            fc = f"{v_graph};{base_af};[abase]acopy[aout]"

        cmd.extend([
            "-filter_complex", fc,
            "-map", "[vout]", "-map", "[aout]",
            "-t", f"{dur:.3f}",
            "-c:v", "libx264", "-preset", "fast", "-crf", "18", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k", "-ar", str(SR), "-ac", "2",
            out_mp4,
        ])
        subprocess.run(cmd, check=True)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
    return dur


def _concat_segments(seg_paths: List[str], out_mp4: str) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(out_mp4)), exist_ok=True)
    tmp_list = out_mp4 + ".concat.txt"
    with open(tmp_list, "w", encoding="utf-8") as f:
        for sp in seg_paths:
            esc = sp.replace("'", "'\\''")
            f.write(f"file '{esc}'\n")
    try:
        subprocess.run(
            [
                "ffmpeg", "-y", "-v", "error",
                "-f", "concat", "-safe", "0", "-i", tmp_list,
                "-c:v", "libx264", "-preset", "fast", "-crf", "18", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", "192k", "-ar", str(SR), "-ac", "2",
                out_mp4,
            ],
            check=True,
        )
    finally:
        if os.path.exists(tmp_list):
            os.remove(tmp_list)


def _parse_highlighted_tokens(line: str) -> List[Tuple[str, bool]]:
    """Split `text **highlight** more` -> [(seg, is_hi), ...]."""
    out: List[Tuple[str, bool]] = []
    pos = 0
    for m in re.finditer(r"\*\*(.+?)\*\*", line):
        if m.start() > pos:
            out.append((line[pos : m.start()], False))
        out.append((m.group(1), True))
        pos = m.end()
    if pos < len(line):
        out.append((line[pos:], False))
    return [p for p in out if p[0]]


def _draw_overlay_png(
    text: str,
    *,
    caption_style: str = "reels_kinetic",
    tag_text: str = "",
    pop_badge: str = "",
    disclosure_label: str = "",
    cta_badge: str = "",
    is_cta_end: bool = False,
    y_top_center: int = 1230,
    highlight_rgb: Tuple[int, int, int] = (255, 224, 71),
    accent_rgb: Tuple[int, int, int] = (217, 72, 30),
    cta_rgb: Tuple[int, int, int] = (43, 76, 126),
    out_png: str,
) -> None:
    """Render clean 1080x1920 transparent overlay PNG (`reels_kinetic` or `boxed`)."""
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    f_disc = _load_cjk_font(22, bold=False)
    f_tag = _load_cjk_font(28, bold=True)
    f_pop = _load_cjk_font(32, bold=True)
    f_cta = _load_cjk_font(36, bold=True)

    # Top-left disclosure (inside Reel top-left safe margin)
    if disclosure_label:
        db = draw.textbbox((0, 0), disclosure_label, font=f_disc)
        dw, dh = (db[2] - db[0]) + 22, (db[3] - db[1]) + 12
        draw.rounded_rectangle([54, 138, 54 + dw, 138 + dh], radius=8, fill=(20, 24, 32, 195), outline=(140, 148, 165, 160), width=1)
        draw.text((54 + 11, 138 + 4), disclosure_label, font=f_disc, fill=(235, 239, 246, 255))

    # Optional context badge (e.g., 배달 52분 · 배달비 4,000원)
    if pop_badge:
        pb = draw.textbbox((0, 0), pop_badge, font=f_pop)
        pw = min(W - 220, (pb[2] - pb[0]) + 66)
        ph = (pb[3] - pb[1]) + 28
        px0 = (W - pw) // 2 - 20
        py0 = 248
        draw.rounded_rectangle([px0, py0, px0 + pw, py0 + ph], radius=16, fill=(14, 17, 23, 228), outline=(255, 95, 55, 220), width=2)
        # Indicator dot
        draw.ellipse([px0 + 20, py0 + ph // 2 - 7, px0 + 34, py0 + ph // 2 + 7], fill=(255, 88, 46, 255))
        draw.text((px0 + 46, py0 + 10), pop_badge, font=f_pop, fill=(255, 255, 255, 255))

    raw_lines = [ln.strip() for ln in (text or "").split("\n") if ln.strip()][:2]
    safe_center_x = 485  # Slight left shift keeps right-side Reels Likes/Comments rail clear

    if caption_style == "reels_kinetic":
        f_cap = _load_cjk_font(58 if len(raw_lines) > 1 else 62, bold=True)
        if raw_lines:
            line_h = 74
            tot_h = len(raw_lines) * line_h
            base_y = y_top_center - (tot_h // 2)
            for li, ln in enumerate(raw_lines):
                tokens = _parse_highlighted_tokens(ln)
                plain_str = "".join(t for t, _ in tokens)
                # Compute full line width carefully token-by-token so spacing matches kerning
                widths = []
                for tok, _hi in tokens:
                    tb = draw.textbbox((0, 0), tok, font=f_cap)
                    widths.append(tb[2] - tb[0])
                total_w = sum(widths)
                cur_x = max(56, min(W - 150 - total_w, safe_center_x - total_w // 2))
                ly = base_y + li * line_h
                for idx_tok, (tok, is_hi) in enumerate(tokens):
                    col = (*highlight_rgb, 255) if is_hi else (255, 255, 255, 255)
                    # Soft dark drop shadow
                    draw.text((cur_x + 3, ly + 4), tok, font=f_cap, fill=(0, 0, 0, 170))
                    # Crisp stroke outline + foreground fill
                    draw.text(
                        (cur_x, ly), tok, font=f_cap, fill=col,
                        stroke_width=8, stroke_fill=(10, 12, 16, 245),
                    )
                    cur_x += widths[idx_tok]

            if tag_text:
                tb = draw.textbbox((0, 0), tag_text, font=f_tag)
                tw, th = (tb[2] - tb[0]) + 32, (tb[3] - tb[1]) + 14
                tx0 = safe_center_x - tw // 2
                ty0 = max(170, base_y - th - 16)
                draw.rounded_rectangle([tx0, ty0, tx0 + tw, ty0 + th], radius=10, fill=(*accent_rgb, 238))
                draw.text((tx0 + 16, ty0 + 5), tag_text, font=f_tag, fill=(255, 255, 255, 255))
    else:
        # Boxed fallback (editorial-card)
        f_cap = _load_cjk_font(48, bold=True)
        box_top_y = y_top_center - 40
        if raw_lines:
            clean_lines = [re.sub(r"\*\*(.+?)\*\*", r"\1", l) for l in raw_lines]
            line_h = 62
            tot_h = len(clean_lines) * line_h
            max_lw = max(draw.textbbox((0, 0), ln, font=f_cap)[2] for ln in clean_lines)
            pad_x, pad_y = 38, 18
            box_w = min(W - 120, max_lw + pad_x * 2)
            box_h = tot_h + pad_y * 2
            bx0 = (W - box_w) // 2
            by0 = y_top_center - (tot_h // 2) + 8
            box_top_y = by0 - pad_y
            draw.rounded_rectangle([bx0, box_top_y, bx0 + box_w, box_top_y + box_h], radius=16, fill=(14, 17, 23, 224))
            for li, ln in enumerate(clean_lines):
                lb = draw.textbbox((0, 0), ln, font=f_cap)
                lx = (W - (lb[2] - lb[0])) // 2
                ly = by0 + li * line_h
                draw.text((lx + 2, ly + 2), ln, font=f_cap, fill=(0, 0, 0, 180))
                draw.text((lx, ly), ln, font=f_cap, fill=(255, 255, 255, 255))
            if tag_text:
                tb = draw.textbbox((0, 0), tag_text, font=f_tag)
                tw, th = (tb[2] - tb[0]) + 34, (tb[3] - tb[1]) + 16
                tx0 = (W - tw) // 2
                ty0 = max(145, box_top_y - th - 14)
                draw.rounded_rectangle([tx0, ty0, tx0 + tw, ty0 + th], radius=10, fill=(*accent_rgb, 240))
                draw.text((tx0 + 17, ty0 + 6), tag_text, font=f_tag, fill=(255, 255, 255, 255))

    if cta_badge:
        cb = draw.textbbox((0, 0), cta_badge, font=f_cta)
        cw = min(780, (cb[2] - cb[0]) + 60)
        ch = (cb[3] - cb[1]) + 34
        cx0 = 72
        cy0 = 1480
        fill_col = (*accent_rgb, 248) if is_cta_end else (*cta_rgb, 232)
        border_col = (255, 255, 255, 215) if is_cta_end else (180, 198, 226, 170)
        draw.rounded_rectangle([cx0, cy0, cx0 + cw, cy0 + ch], radius=16, fill=fill_col, outline=border_col, width=2)
        tx = cx0 + max(20, (cw - (cb[2] - cb[0])) // 2)
        ty = cy0 + 12
        draw.text((tx, ty), cta_badge, font=f_cta, fill=(255, 255, 255, 255))

    os.makedirs(os.path.dirname(os.path.abspath(out_png)), exist_ok=True)
    img.save(out_png, format="PNG")


def _apply_overlays_batched(in_mp4: str, overlays: List[Tuple[str, float, float]], out_mp4: str, tmp_dir: str) -> None:
    if not overlays:
        shutil.copyfile(in_mp4, out_mp4)
        return
    cur = in_mp4
    batch_size = 8
    batches = [overlays[i : i + batch_size] for i in range(0, len(overlays), batch_size)]
    for b_idx, batch in enumerate(batches):
        dst = out_mp4 if b_idx == len(batches) - 1 else os.path.join(tmp_dir, f"ov_pass_{b_idx}.mp4")
        cmd = ["ffmpeg", "-y", "-v", "error", "-i", cur]
        for png_p, _, _ in batch:
            cmd.extend(["-loop", "1", "-i", png_p])
        fc_parts: List[str] = []
        prev_label = "0:v"
        for i, (_, s, e) in enumerate(batch):
            inp_idx = i + 1
            out_lbl = "vout" if i == len(batch) - 1 else f"ov{i}"
            fc_parts.append(
                f"[{prev_label}][{inp_idx}:v]overlay=0:0:shortest=1:enable='between(t,{s:.3f},{e:.3f})'[{out_lbl}]"
            )
            prev_label = out_lbl
        cmd.extend([
            "-filter_complex", ";".join(fc_parts),
            "-map", "[vout]", "-map", "0:a",
            "-c:v", "libx264", "-preset", "fast", "-crf", "18", "-pix_fmt", "yuv420p",
            "-c:a", "copy",
            dst,
        ])
        subprocess.run(cmd, check=True)
        cur = dst


def _measure_ebur128(mp4_path: str) -> Optional[float]:
    proc = subprocess.run(
        ["ffmpeg", "-hide_banner", "-i", mp4_path, "-af", "ebur128", "-f", "null", "-"],
        capture_output=True, text=True,
    )
    txt = proc.stderr or ""
    matches = re.findall(r"^\s*I:\s*(-?[0-9]+(?:\.[0-9]+)?|inf|-inf)\s+LUFS", txt, flags=re.MULTILINE)
    if not matches:
        return None
    val_str = matches[-1]
    if "inf" in val_str.lower():
        return None
    val = float(val_str)
    if not math.isfinite(val) or val < -65.0:
        return None
    return val


def _render_bgm_bus_wav(
    bgm_timeline: List[Dict[str, Any]],
    *,
    dur: float,
    base_dir: str,
    out_wav: str,
) -> Optional[str]:
    """Build sample-accurate 48kHz stereo BGM bus across multi-stage stem sections."""
    if not bgm_timeline:
        return None
    n_tot = int(round(dur * SR))
    bus = np.zeros((n_tot, 2), dtype=np.float32)

    # Preload unique stems once
    stem_cache: Dict[str, np.ndarray] = {}
    for sec in bgm_timeline:
        stems = sec.get("stems") or ([] if not sec.get("path") else [sec["path"]])
        st = float(sec.get("start", 0.0) or 0.0)
        en = min(dur, float(sec.get("end", dur) or dur))
        if en <= st or not stems:
            continue
        gain_db = float(sec.get("gain_db", -16.0) or -16.0)
        gain_lin = 10.0 ** (gain_db / 20.0)
        fade_in = float(sec.get("fade_in", 0.08) or 0.08)
        fade_out = float(sec.get("fade_out", 0.25) or 0.25)
        loop_offset = float(sec.get("stem_offset_sec", 0.0) or 0.0)

        s_idx = max(0, int(round(st * SR)))
        e_idx = min(n_tot, int(round(en * SR)))
        seg_n = e_idx - s_idx
        if seg_n <= 0:
            continue

        sec_buf = np.zeros((seg_n, 2), dtype=np.float32)
        for sp_rel in stems:
            sp = _resolve_path(sp_rel, base_dir)
            if not sp or not os.path.exists(sp):
                continue
            if sp not in stem_cache:
                stem_cache[sp] = _decode_audio_f32(sp, sample_rate=SR, channels=2)
            raw_stem = stem_cache[sp]
            if len(raw_stem) == 0:
                continue
            # Continuous musical clock offset (default uses st * SR so stems keep downbeat alignment across drop!)
            pos_samples = np.arange(seg_n, dtype=np.int64) + int(round((loop_offset if loop_offset >= 0 else st) * SR))
            wrapped = pos_samples % len(raw_stem)
            sec_buf += raw_stem[wrapped]

        # Normalize summed stems cleanly before gain
        sec_buf *= (gain_lin / max(1.0, math.sqrt(len(stems))))
        fi_n = min(seg_n // 2, int(round(fade_in * SR)))
        fo_n = min(seg_n // 2, int(round(fade_out * SR)))
        if fi_n > 1:
            sec_buf[:fi_n] *= np.linspace(0.0, 1.0, fi_n, dtype=np.float32)[:, None]
        if fo_n > 1:
            sec_buf[-fo_n:] *= np.linspace(1.0, 0.0, fo_n, dtype=np.float32)[:, None]
        bus[s_idx:e_idx] += sec_buf

    _write_wav_f32(out_wav, bus, SR)
    return out_wav


def _render_sfx_bus_wav(
    sfx_events: List[Dict[str, Any]],
    *,
    dur: float,
    base_dir: str,
    out_wav: str,
) -> Optional[str]:
    """Mix frame-synced stereo/surround studio SFX files cleanly into a single 48kHz stereo WAV."""
    if not sfx_events:
        return None
    n_tot = int(round(dur * SR))
    bus = np.zeros((n_tot, 2), dtype=np.float32)
    any_hit = False

    for ev in sfx_events:
        fp = _resolve_path(ev.get("file"), base_dir)
        if not fp or not os.path.exists(fp):
            continue
        t_start = float(ev.get("time", 0.0) or 0.0)
        trim_s = float(ev.get("trim_start", 0.0) or 0.0)
        ev_dur = ev.get("duration")
        gain_db = float(ev.get("gain_db", -12.0) or -12.0)
        gain_lin = 10.0 ** (gain_db / 20.0)
        fi_s = float(ev.get("fade_in", 0.01) or 0.01)
        fo_s = float(ev.get("fade_out", 0.12) or 0.12)

        arr = _decode_audio_f32(fp, trim_start=trim_s, duration=float(ev_dur) if ev_dur else None, sample_rate=SR, channels=2)
        if len(arr) == 0:
            continue
        arr = np.array(arr, dtype=np.float32, copy=True)
        # Peak normalize SFX before applying dB gain so library clips match uniformly
        pk = float(np.max(np.abs(arr)))
        if pk > 1e-4:
            arr = (arr / pk) * 0.85 * gain_lin
        fi_n = min(len(arr) // 3, int(round(fi_s * SR)))
        fo_n = min(len(arr) // 2, int(round(fo_s * SR)))
        if fi_n > 1:
            arr[:fi_n] *= np.linspace(0.0, 1.0, fi_n, dtype=np.float32)[:, None]
        if fo_n > 1:
            arr[-fo_n:] *= np.linspace(1.0, 0.0, fo_n, dtype=np.float32)[:, None]

        dst_s = max(0, int(round(t_start * SR)))
        if dst_s >= n_tot:
            continue
        take_n = min(len(arr), n_tot - dst_s)
        bus[dst_s : dst_s + take_n] += arr[:take_n]
        any_hit = True

    if not any_hit:
        return None
    _write_wav_f32(out_wav, np.clip(bus, -0.95, 0.95), SR)
    return out_wav


def _master_audio_and_mix(
    video_mp4: str,
    out_mp4: str,
    *,
    vo_path: Optional[str],
    bgm_path: Optional[str],
    bgm_gain_db: float,
    bgm_timeline: Optional[List[Dict[str, Any]]],
    sfx_events: Optional[List[Dict[str, Any]]],
    base_dir: str,
    dur: float,
    tmp_dir: str,
) -> Dict[str, Any]:
    bgm_bus_wav = None
    if bgm_timeline:
        bgm_bus_wav = _render_bgm_bus_wav(
            bgm_timeline, dur=dur, base_dir=base_dir, out_wav=os.path.join(tmp_dir, "bgm_bus.wav")
        )
    elif bgm_path and os.path.exists(bgm_path):
        bgm_bus_wav = _render_bgm_bus_wav(
            [{"start": 0.0, "end": dur, "stems": [bgm_path], "gain_db": bgm_gain_db}],
            dur=dur, base_dir=base_dir, out_wav=os.path.join(tmp_dir, "bgm_bus.wav"),
        )

    sfx_bus_wav = None
    if sfx_events:
        sfx_bus_wav = _render_sfx_bus_wav(
            sfx_events, dur=dur, base_dir=base_dir, out_wav=os.path.join(tmp_dir, "sfx_bus.wav")
        )

    pre_mix = video_mp4
    has_vo = bool(vo_path and os.path.exists(vo_path))
    if has_vo or bgm_bus_wav or sfx_bus_wav:
        pre_mix = os.path.join(tmp_dir, "pre_master.mp4")
        cmd = ["ffmpeg", "-y", "-v", "error", "-i", video_mp4]
        fc = [f"[0:a]aresample={SR},apad=whole_dur={dur:.3f},atrim=0:{dur:.3f}[a0]"]
        mix_labels = ["[a0]"]
        idx = 1

        vo_key_lbl = None
        if has_vo:
            cmd.extend(["-i", vo_path])
            vo_base = (
                f"[{idx}:a]highpass=f=85,acompressor=threshold=-18dB:ratio=3:attack=8:release=120:makeup=2dB,"
                f"aresample={SR},apad=whole_dur={dur:.3f},atrim=0:{dur:.3f}"
            )
            if bgm_bus_wav:
                fc.append(f"{vo_base},asplit=2[avo][avokey]")
                vo_key_lbl = "[avokey]"
            else:
                fc.append(f"{vo_base}[avo]")
            mix_labels.append("[avo]")
            idx += 1

        if bgm_bus_wav:
            cmd.extend(["-i", bgm_bus_wav])
            if vo_key_lbl:
                fc.append(
                    f"[{idx}:a]aresample={SR},apad=whole_dur={dur:.3f},atrim=0:{dur:.3f}[abgm_raw];"
                    f"[abgm_raw]{vo_key_lbl}sidechaincompress=threshold=0.022:ratio=6:attack=12:release=260:makeup=1[abgm]"
                )
            else:
                fc.append(f"[{idx}:a]aresample={SR},apad=whole_dur={dur:.3f},atrim=0:{dur:.3f}[abgm]")
            mix_labels.append("[abgm]")
            idx += 1

        if sfx_bus_wav:
            cmd.extend(["-i", sfx_bus_wav])
            fc.append(f"[{idx}:a]aresample={SR},apad=whole_dur={dur:.3f},atrim=0:{dur:.3f}[asfx]")
            mix_labels.append("[asfx]")
            idx += 1

        fc.append(f"{''.join(mix_labels)}amix=inputs={len(mix_labels)}:duration=first:normalize=0[aout]")
        cmd.extend([
            "-filter_complex", ";".join(fc),
            "-map", "0:v", "-map", "[aout]",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", str(SR), "-ac", "2",
            pre_mix,
        ])
        subprocess.run(cmd, check=True)

    measured_i = _measure_ebur128(pre_mix)
    if measured_i is None:
        shutil.copyfile(pre_mix, out_mp4)
        return {"input_lufs": None, "applied_gain_db": 0.0, "final_lufs": None}

    diff_db = max(-24.0, min(28.0, TARGET_LUFS - measured_i))
    subprocess.run(
        [
            "ffmpeg", "-y", "-v", "error", "-i", pre_mix,
            "-af", f"volume={diff_db:.2f}dB,alimiter=limit=0.82:level=disabled",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", str(SR), "-ac", "2",
            out_mp4,
        ],
        check=True,
    )
    final_i = _measure_ebur128(out_mp4)
    return {
        "input_lufs": round(measured_i, 2),
        "applied_gain_db": round(diff_db, 2),
        "final_lufs": round(final_i, 2) if final_i is not None else None,
    }


def _write_srt(cues: List[Tuple[float, float, str]], out_srt: str) -> None:
    def _ts(sec: float) -> str:
        ms = int(round(max(0.0, sec) * 1000))
        h, ms = divmod(ms, 3600000)
        m, ms = divmod(ms, 60000)
        s, ms = divmod(ms, 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    lines: List[str] = []
    idx = 1
    for st, en, txt in cues:
        clean = re.sub(r"\*\*(.+?)\*\*", r"\1", txt.strip())
        if not clean:
            continue
        lines.extend([str(idx), f"{_ts(st)} --> {_ts(en)}", clean, ""])
        idx += 1
    os.makedirs(os.path.dirname(os.path.abspath(out_srt)), exist_ok=True)
    with open(out_srt, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def build_qa_strip(results: List[Dict[str, Any]], out_png: str) -> str:
    cols = 6
    tw, th = 225, 400
    pad = 12
    row_hdr = 34
    top_hdr = 42
    w_tot = pad + cols * (tw + pad)
    h_tot = top_hdr + pad + len(results) * (row_hdr + th + pad)
    canvas = Image.new("RGB", (w_tot, h_tot), (20, 23, 30))
    draw = ImageDraw.Draw(canvas)
    f_title = _load_cjk_font(18, bold=True)
    f_row = _load_cjk_font(15, bold=True)

    draw.text((pad, 10), f"Shortform Ad QC Matrix  |  {W}x{H} {FPS}fps", fill=(244, 247, 252), font=f_title)
    tmp_dir = tempfile.mkdtemp(prefix="ad_qa_")
    try:
        for r_idx, res in enumerate(results):
            y0 = top_hdr + pad + r_idx * (row_hdr + th + pad)
            dur = res["duration"]
            lufs_str = f"{res['lufs']['final_lufs']:.1f} LUFS" if res["lufs"]["final_lufs"] is not None else "silent"
            draw.rectangle([pad, y0, w_tot - pad, y0 + row_hdr], fill=(38, 44, 58))
            draw.text(
                (pad + 10, y0 + 7),
                f"{res['variant']} ({res['short_tag']})  |  {dur:.2f}s  |  {lufs_str}  |  {os.path.basename(res['mp4'])}",
                fill=(255, 255, 255), font=f_row,
            )
            sample_ts = [round(dur * f, 2) for f in (0.04, 0.18, 0.38, 0.56, 0.76, 0.94)]
            for c_idx, ts in enumerate(sample_ts):
                ts_clamped = min(max(0.1, ts), max(0.1, dur - 0.1))
                fp = os.path.join(tmp_dir, f"r{r_idx}_c{c_idx}.png")
                subprocess.run(
                    ["ffmpeg", "-y", "-v", "error", "-ss", f"{ts_clamped:.2f}", "-i", res["mp4"], "-frames:v", "1", fp],
                    check=True,
                )
                x0 = pad + c_idx * (tw + pad)
                with Image.open(fp) as im:
                    rs = im.convert("RGB").resize((tw, th), Image.Resampling.LANCZOS)
                    canvas.paste(rs, (x0, y0 + row_hdr))
                draw.rectangle([x0 + 6, y0 + row_hdr + 6, x0 + 76, y0 + row_hdr + 28], fill=(17, 19, 24))
                draw.text((x0 + 10, y0 + row_hdr + 8), f"{ts_clamped:.1f}s", fill=(255, 220, 120), font=f_row)
        os.makedirs(os.path.dirname(os.path.abspath(out_png)), exist_ok=True)
        canvas.save(out_png, format="PNG")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
    return os.path.abspath(out_png)


def _render_variant_output(
    vk: str,
    v: Dict[str, Any],
    segments_all: List[Dict[str, Any]],
    raw_joined: str,
    tot_dur: float,
    spec: Dict[str, Any],
    base_dir: str,
    v_work: str,
    out_dir: str,
    *,
    clean_copy: bool,
    out_stem: Optional[str] = None,
) -> Dict[str, Any]:
    disc_mode = spec.get("disclosure", "none")
    disc_label = DISCLOSURE_TEXT.get(disc_mode, "")
    cta = spec.get("cta") or {}
    cta_badge = cta.get("badge_copy") or cta.get("copy") or ""
    cta_start = float(cta.get("start_sec", max(6.0, tot_dur - 4.0)))
    cta_show_from = float(cta.get("show_from_sec", cta_start))
    cap_style = v.get("caption_style") or spec.get("caption_style") or ("boxed" if spec.get("framing_mode") == "editorial-card" else "reels_kinetic")
    default_y = int(v.get("caption_y") or spec.get("caption_y") or (282 if spec.get("framing_mode") == "editorial-card" else 1240))
    hi_rgb = _hex_to_rgb(spec.get("highlight_color", "#FFE047"), (255, 224, 71))

    stem = out_stem or f"ad_{vk}"
    clean_mp4_path: Optional[str] = None
    if clean_copy:
        clean_mp4_path = os.path.join(out_dir, f"{stem}_clean.mp4")
        shutil.copyfile(raw_joined, clean_mp4_path)

    hide_disc_until = float(v.get("hide_disclosure_until_sec", 3.5 if (disc_mode == "own_brand" and v.get("archetype") == "absurd_twist") else 0.0))
    cues: List[Tuple[float, float, str, str, str, int, bool]] = []
    explicit_caps = v.get("captions") or (spec.get("captions") if isinstance(spec.get("captions"), list) else None)
    if isinstance(explicit_caps, list) and explicit_caps:
        for c in explicit_caps:
            st, en = float(c["start"]), float(c["end"])
            cues.append((
                st, en,
                str(c.get("text", "")),
                str(c.get("header_tag", "")),
                str(c.get("pop_badge", "")),
                int(c.get("y_pos", default_y)),
                bool(c.get("is_cta", st >= cta_start - 0.1)),
            ))
    else:
        t_cur = 0.0
        for s in segments_all:
            d = _seg_dur(s)
            txt = (s.get("caption_text") or "").strip()
            tag = (s.get("header_tag") or "").strip()
            pop = (s.get("pop_badge") or "").strip()
            ypos = int(s.get("caption_y", default_y))
            is_cta_cue = (t_cur + d * 0.5) >= cta_start
            cues.append((round(t_cur, 3), round(t_cur + d, 3), txt, tag, pop, ypos, is_cta_cue))
            t_cur += d

    ov_tuples: List[Tuple[str, float, float]] = []
    srt_cues: List[Tuple[float, float, str]] = []
    for ci, (st, en, txt, tag, pop, ypos, is_cta_cue) in enumerate(cues):
        if en <= st:
            continue
        show_disc = disc_label if st >= hide_disc_until - 0.05 else ""
        show_cta = cta_badge if (cta_badge and (st >= cta_show_from - 0.1 or is_cta_cue)) else ""
        ov_png = os.path.join(v_work, f"ov_{ci:02d}.png")
        _draw_overlay_png(
            txt,
            caption_style=cap_style,
            tag_text=tag,
            pop_badge=pop,
            disclosure_label=show_disc,
            cta_badge=show_cta,
            is_cta_end=is_cta_cue,
            y_top_center=ypos,
            highlight_rgb=hi_rgb,
            out_png=ov_png,
        )
        ov_tuples.append((ov_png, st, en))
        if txt:
            srt_cues.append((st, en, txt))

    ov_video = os.path.join(v_work, f"overlaid_{vk}.mp4")
    _apply_overlays_batched(raw_joined, ov_tuples, ov_video, v_work)

    final_mp4 = os.path.join(out_dir, f"{stem}.mp4")
    vo_path = _resolve_path(v.get("vo_audio") or spec.get("vo_audio"), base_dir)
    bgm_cfg = v.get("bgm") or spec.get("bgm") or {}
    bgm_path = _resolve_path(bgm_cfg.get("path"), base_dir)
    bgm_gain = float(bgm_cfg.get("gain_db", -18.0) or -18.0)
    bgm_tl = v.get("bgm_timeline") or spec.get("bgm_timeline")
    sfx_ev = v.get("sfx_events") or spec.get("sfx_events")

    lufs_info = _master_audio_and_mix(
        ov_video, final_mp4,
        vo_path=vo_path, bgm_path=bgm_path, bgm_gain_db=bgm_gain,
        bgm_timeline=bgm_tl, sfx_events=sfx_ev, base_dir=base_dir,
        dur=tot_dur, tmp_dir=v_work,
    )
    srt_path = os.path.join(out_dir, f"{stem}.srt")
    _write_srt(srt_cues, srt_path)
    final_info = ffprobe_info(final_mp4)
    out_meta: Dict[str, Any] = {
        "variant": vk,
        "short_tag": v.get("short_tag", spec.get("short_tag", "master")),
        "mp4": os.path.abspath(final_mp4),
        "srt": os.path.abspath(srt_path),
        "duration": round(final_info["duration"], 2),
        "width": final_info["width"],
        "height": final_info["height"],
        "lufs": lufs_info,
    }
    if clean_mp4_path and os.path.exists(clean_mp4_path):
        out_meta["clean_mp4"] = os.path.abspath(clean_mp4_path)
    return out_meta


def assemble(args: argparse.Namespace) -> None:
    with open(args.spec, "r", encoding="utf-8") as f:
        spec = json.load(f)
    base_dir = args.base_dir or os.path.dirname(os.path.abspath(args.spec))
    work_dir = os.path.abspath(args.work_dir or os.path.join(base_dir, "work"))
    out_dir = os.path.abspath(args.out_dir)
    os.makedirs(work_dir, exist_ok=True)
    os.makedirs(out_dir, exist_ok=True)

    rendered_results: List[Dict[str, Any]] = []

    # Direct single cohesive timeline mode
    if isinstance(spec.get("timeline"), list) and spec["timeline"]:
        tl = spec["timeline"]
        seg_paths: List[str] = []
        tot_dur = 0.0
        for idx, seg in enumerate(tl):
            smp4 = os.path.join(work_dir, f"tl_{idx:02d}_{seg.get('id', idx)}.mp4")
            tot_dur += render_segment(seg, spec, base_dir, smp4, preview_animatic=args.preview_animatic)
            seg_paths.append(smp4)
        raw_master = os.path.join(work_dir, "raw_master.mp4")
        _concat_segments(seg_paths, raw_master)
        v_work = os.path.join(work_dir, "var_master")
        os.makedirs(v_work, exist_ok=True)
        out_stem = spec.get("output_stem") or "ad_master"
        rendered_results.append(
            _render_variant_output(
                "master", {}, tl, raw_master, round(tot_dur, 3), spec, base_dir, v_work, out_dir,
                clean_copy=args.clean_copy, out_stem=out_stem,
            )
        )
    else:
        shared_body = spec.get("shared_body_cuts") or []
        variants: Dict[str, Any] = spec.get("variants") or {}
        target_keys = list(variants.keys()) if args.variant == "all" else [k.strip() for k in args.variant.split(",") if k.strip() in variants]
        if not target_keys:
            raise RuntimeError(f"No matching variants selected for --variant={args.variant}")

        body_seg_paths: List[str] = []
        body_dur = 0.0
        for idx, seg in enumerate(shared_body):
            seg_mp4 = os.path.join(work_dir, f"body_{idx:02d}_{seg.get('id', idx)}.mp4")
            body_dur += render_segment(seg, spec, base_dir, seg_mp4, preview_animatic=args.preview_animatic)
            body_seg_paths.append(seg_mp4)

        shared_body_mp4 = os.path.join(work_dir, "shared_body_master.mp4")
        _concat_segments(body_seg_paths, shared_body_mp4)

        for vk in target_keys:
            v = variants[vk]
            v_work = os.path.join(work_dir, f"var_{vk}")
            os.makedirs(v_work, exist_ok=True)
            hook_paths: List[str] = []
            hook_dur = 0.0
            for h_idx, hseg in enumerate(v.get("hook_segments") or []):
                h_mp4 = os.path.join(v_work, f"hook_{h_idx:02d}.mp4")
                hook_dur += render_segment(hseg, spec, base_dir, h_mp4, preview_animatic=args.preview_animatic)
                hook_paths.append(h_mp4)
            hook_concat = os.path.join(v_work, f"hook_{vk}.mp4")
            _concat_segments(hook_paths, hook_concat)
            raw_joined = os.path.join(v_work, f"raw_{vk}.mp4")
            _concat_segments([hook_concat, shared_body_mp4], raw_joined)
            rendered_results.append(
                _render_variant_output(
                    vk, v, list(v.get("hook_segments") or []) + shared_body,
                    raw_joined, round(hook_dur + body_dur, 3), spec, base_dir, v_work, out_dir,
                    clean_copy=args.clean_copy,
                )
            )

    qa_out = None
    if args.qa_strip and rendered_results:
        qa_out = build_qa_strip(rendered_results, args.qa_strip)
    print(json.dumps({"rendered": rendered_results, "qa_strip": qa_out}, ensure_ascii=False, indent=2))


def main() -> None:
    p = argparse.ArgumentParser(description="Render 9:16 shortform ad variants or cohesive 30s master")
    p.add_argument("--spec", required=True)
    p.add_argument("--out-dir", required=True)
    p.add_argument("--variant", default="all", help="'all' or comma-separated variant keys e.g. A,B,C")
    p.add_argument("--work-dir", default=None)
    p.add_argument("--base-dir", default=None)
    p.add_argument("--clean-copy", action="store_true")
    p.add_argument("--preview-animatic", action="store_true")
    p.add_argument("--qa-strip", default=None)
    args = p.parse_args()
    assemble(args)


if __name__ == "__main__":
    main()
