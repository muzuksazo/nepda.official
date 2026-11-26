"""Shared post-production module: Inworld TTS synthesis, multi-archetype procedural SFX,
PIL Korean captions, -14.0 LUFS FFmpeg muxer, 2x2 preview & 6-frame strip builders.
"""

from __future__ import annotations

import base64
import json
import os
import subprocess
import urllib.request
import wave
from typing import Dict, List

import numpy as np
from PIL import Image, ImageDraw, ImageFont

FONT_PATH = "/System/Library/Fonts/AppleSDGothicNeo.ttc"
DEFAULT_VOICE_ID = "snowy-otter-1773__leesiu_docu_kr"


def load_font(size: int) -> ImageFont.FreeTypeFont:
    for idx in (4, 3, 2, 0):
        try:
            return ImageFont.truetype(FONT_PATH, size=size, index=idx)
        except Exception:
            pass
    return ImageFont.load_default()


def make_caption_png(lines: List[str], out_path: str, width: int = 720, height: int = 210) -> None:
    im = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    f = load_font(38)
    y0 = 24 if len(lines) > 1 else 62
    for idx, line in enumerate(lines):
        bbox = d.textbbox((0, 0), line, font=f, stroke_width=5)
        tw = bbox[2] - bbox[0]
        x = (width - tw) // 2
        y = y0 + idx * 54
        d.text(
            (x, y), line, font=f,
            fill=(255, 255, 255, 255),
            stroke_width=5, stroke_fill=(8, 10, 16, 245),
        )
    im.save(out_path)


def synthesize_vo_lines(spec: Dict, vo_dir: str) -> None:
    """Generate any missing VO MP3s via Inworld TTS using INWORLD_AUTH env var (never stored on disk)."""
    os.makedirs(vo_dir, exist_ok=True)
    slots = spec.get("vo_slots", [])
    missing = [s for s in slots if not os.path.exists(os.path.join(vo_dir, s["file"]))]
    if not missing:
        return
    auth = os.environ.get("INWORLD_AUTH", "").strip()
    if not auth:
        raise RuntimeError(f"Missing INWORLD_AUTH env var to synthesize {len(missing)} VO files.")
    voice_id = spec.get("voice_id", DEFAULT_VOICE_ID)
    for slot in missing:
        out_p = os.path.join(vo_dir, slot["file"])
        payload = json.dumps({
            "text": slot["text"],
            "voiceId": voice_id,
            "modelId": "inworld-tts-2",
            "audioConfig": {"audioEncoding": "MP3"},
        }).encode("utf-8")
        req = urllib.request.Request(
            "https://api.inworld.ai/tts/v1/voice",
            data=payload,
            headers={
                "Authorization": f"Basic {auth}",
                "Content-Type": "application/json",
                "User-Agent": "Antigravity-ViralTemplates/1.0",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            res = json.loads(resp.read().decode("utf-8"))
        raw = base64.b64decode(res["audioContent"])
        with open(out_p, "wb") as f:
            f.write(raw)
        print(f"[vo] Synthesized {slot['file']} ({len(raw)}B)", flush=True)


def trim_and_fit_vo(mp3_path: str, target_dur: float, out_wav: str) -> None:
    tmp_wav = out_wav + ".raw.wav"
    subprocess.run(
        ["ffmpeg", "-y", "-i", mp3_path, "-ac", "1", "-ar", "48000", tmp_wav],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True,
    )
    with wave.open(tmp_wav, "rb") as wf:
        pcm = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0
    nz = np.where(np.abs(pcm) > 0.015)[0]
    i0 = max(0, int(nz[0] - 0.03 * 48000)) if len(nz) else 0
    i1 = min(len(pcm), int(nz[-1] + 0.05 * 48000)) if len(nz) else len(pcm)
    trimmed = pcm[i0:i1]
    trim_dur = len(trimmed) / 48000.0
    trimmed_wav = out_wav + ".trim.wav"
    with wave.open(trimmed_wav, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(48000)
        wf.writeframes((np.clip(trimmed, -0.99, 0.99) * 32767.0).astype(np.int16).tobytes())

    tempo = max(0.95, min(1.48, trim_dur / target_dur))
    subprocess.run([
        "ffmpeg", "-y", "-i", trimmed_wav,
        "-filter:a", f"atempo={tempo:.4f},apad=whole_dur={target_dur:.4f},atrim=0:{target_dur:.4f}",
        "-ac", "1", "-ar", "48000", out_wav,
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    for p in (tmp_wav, trimmed_wav):
        if os.path.exists(p):
            os.remove(p)


def build_sfx_track(spec: Dict, total_dur: float, out_wav: str) -> None:
    sr = 48000
    n = int(total_dur * sr)
    t = np.arange(n, dtype=np.float32) / sr
    rng = np.random.default_rng(2026)
    noise = rng.normal(0.0, 1.0, n).astype(np.float32)
    low_rumble = np.convolve(noise, np.ones(36, dtype=np.float32) / 36.0, mode="same")
    profile = spec.get("sfx_profile", "generic")
    cues = spec.get("sfx_cues", [])

    sig = np.zeros(n, dtype=np.float32)

    if profile == "hydraulic_press":
        # Continuous rising hydraulic whine + steel groan until fracture cue, then explosive glass/metal shatter
        whine_end = cues[0] if cues else 3.23
        spool = np.clip(t / max(0.5, whine_end), 0.0, 1.0)
        active = (t < whine_end + 0.1).astype(np.float32)
        freq = 110.0 + 180.0 * spool
        phase = 2.0 * np.pi * np.cumsum(freq) / sr
        sig += (0.28 * np.sin(phase) + 0.16 * low_rumble) * (0.35 + 0.65 * spool) * active
        if cues:
            ct = cues[0]
            dt = t - ct
            m = (dt >= 0.0) & (dt < 1.35)
            shatter = np.exp(-dt[m] * 7.5) * noise[m] * 0.9 + np.exp(-dt[m] * 14.0) * np.sin(2.0 * np.pi * 88.0 * dt[m])
            # High glass/metal shard sparkles
            for off, pf in ((0.03, 1850.0), (0.09, 2400.0), (0.16, 1520.0), (0.25, 2900.0)):
                dm = (dt >= off) & (dt < off + 0.25)
                sig[dm] += 0.35 * np.exp(-(dt[dm] - off) * 18.0) * np.sin(2.0 * np.pi * pf * (dt[dm] - off))
            sig[m] += shatter * 0.85

    elif profile == "scale_drop":
        # Falling whistle + progressively heavier deep bass thuds (bowling ball -> car -> massive asteroid boom!)
        for idx, ct in enumerate(cues):
            dt = t - ct
            # Descending whistle before each hit
            mw = (dt >= -0.45) & (dt < 0.0)
            if np.any(mw):
                wf = np.lerp if hasattr(np, "lerp") else None
                u = (dt[mw] + 0.45) / 0.45
                f_w = (900.0 - 450.0 * u) / (1.0 + 0.25 * idx)
                sig[mw] += 0.12 * np.sin(2.0 * np.pi * f_w * (dt[mw] + 0.45)) * u
            # Impact boom + debris
            dur_h = 0.45 + 0.35 * idx
            mh = (dt >= 0.0) & (dt < dur_h)
            f0 = 140.0 / (1.0 + 0.7 * idx)
            amp = 0.55 + 0.25 * idx
            sig[mh] += amp * (
                np.exp(-dt[mh] * (10.0 - 2.5 * idx)) * np.sin(2.0 * np.pi * f0 * np.exp(-dt[mh] * 4.0) * dt[mh])
                + 0.75 * np.exp(-dt[mh] * (7.0 - 1.5 * idx)) * low_rumble[mh]
            )

    elif profile == "domino_chain":
        # 10 exponentially deeper wooden/concrete clacks + final barrel crash!
        for idx, ct in enumerate(cues[:-1] if len(cues) > 1 else cues):
            dt = t - ct
            m = (dt >= 0.0) & (dt < 0.24)
            pitch = max(95.0, 520.0 * (0.83 ** idx))
            amp = min(0.95, 0.28 + 0.075 * idx)
            sig[m] += amp * np.exp(-dt[m] * 22.0) * (np.sin(2.0 * np.pi * pitch * dt[m]) + 0.5 * noise[m] * np.exp(-dt[m] * 30.0))
        if cues:
            ct = cues[-1]
            dt = t - ct
            m = (dt >= 0.0) & (dt < 1.1)
            sig[m] += 0.90 * np.exp(-dt[m] * 6.5) * (low_rumble[m] + 0.6 * np.sin(2.0 * np.pi * 68.0 * dt[m]) + 0.4 * np.sin(2.0 * np.pi * 240.0 * dt[m]))

    else:
        # Generic whoosh + impact thuds
        for ct in cues:
            dt = t - ct
            m = (dt >= 0.0) & (dt < 0.7)
            sig[m] += 0.75 * np.exp(-dt[m] * 9.0) * (low_rumble[m] + np.sin(2.0 * np.pi * 95.0 * dt[m]))
        sig += 0.14 * low_rumble

    mix = np.tanh(sig * 0.85) * 0.65
    with wave.open(out_wav, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes((np.clip(mix, -0.99, 0.99) * 32767.0).astype(np.int16).tobytes())


def stitch_preview_grid(frame_paths: List[str], out_png: str) -> None:
    imgs = [Image.open(p).resize((540, 960), Image.Resampling.LANCZOS) for p in frame_paths[:4]]
    canvas = Image.new("RGB", (540 * 2, 960 * 2), (16, 18, 24))
    font = load_font(22)
    for idx, (p, im) in enumerate(zip(frame_paths[:4], imgs)):
        x = (idx % 2) * 540
        y = (idx // 2) * 960
        canvas.paste(im, (x, y))
        d = ImageDraw.Draw(canvas)
        d.rectangle([x + 12, y + 12, x + 380, y + 52], fill=(0, 0, 0))
        d.text((x + 20, y + 18), os.path.basename(p), font=font, fill=(120, 255, 180))
    canvas.save(out_png)


def assemble_template_video(spec: Dict, out_dir: str, raw_mp4: str, final_mp4: str, strip_png: str) -> None:
    total_dur = float(spec.get("total_frames", 150)) / float(spec.get("fps", 30))
    vo_dir = os.path.join(out_dir, "vo")
    synthesize_vo_lines(spec, vo_dir)

    sfx_wav = os.path.join(out_dir, "sfx_mix.wav")
    build_sfx_track(spec, total_dur, sfx_wav)

    inputs = ["-i", sfx_wav]
    fparts = ["[0:a]aresample=48000,volume=0.45[sfx]"]
    labels = ["[sfx]"]
    cap_paths = []
    for idx, slot in enumerate(spec.get("vo_slots", []), start=1):
        w_out = os.path.join(out_dir, f"vo_fit_{idx}.wav")
        trim_and_fit_vo(os.path.join(vo_dir, slot["file"]), float(slot["dur"]), w_out)
        inputs += ["-i", w_out]
        ms = int(round(float(slot["start"]) * 1000))
        fparts.append(f"[{idx}:a]aresample=48000,adelay={ms}|{ms}[v{idx}]")
        labels.append(f"[v{idx}]")

        cap_p = os.path.join(out_dir, f"cap_{idx}.png")
        make_caption_png(slot["caption"], cap_p)
        cap_paths.append((cap_p, float(slot["start"]), float(slot["start"]) + float(slot["dur"])))

    mix_wav = os.path.join(out_dir, "final_audio_mix.wav")
    fc = ";".join(fparts) + f";{''.join(labels)}amix=inputs={len(labels)}:normalize=0,loudnorm=I=-14.0:TP=-1.0:LRA=7[aout]"
    subprocess.run([
        "ffmpeg", "-y", *inputs, "-filter_complex", fc, "-map", "[aout]",
        "-ar", "48000", "-ac", "2", "-t", f"{total_dur:.3f}", mix_wav,
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

    v_inputs = ["-i", raw_mp4]
    v_fc = []
    cur = "[0:v]"
    for idx, (cap_p, s0, s1) in enumerate(cap_paths, start=1):
        v_inputs += ["-loop", "1", "-t", f"{total_dur:.3f}", "-i", cap_p]
        nxt = f"[v{idx}]" if idx < len(cap_paths) else "[vout]"
        v_fc.append(f"{cur}[{idx}:v]overlay=0:940:enable='between(t,{s0:.2f},{s1:.2f})':shortest=1{nxt}")
        cur = nxt

    subprocess.run([
        "ffmpeg", "-y", *v_inputs, "-i", mix_wav,
        "-filter_complex", ";".join(v_fc),
        "-map", "[vout]", "-map", f"{len(cap_paths) + 1}:a",
        "-c:v", "libx264", "-preset", "medium", "-crf", "17", "-pix_fmt", "yuv420p", "-r", "30",
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
        "-shortest", final_mp4,
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

    tmp = os.path.join(out_dir, "strip_tmp")
    os.makedirs(tmp, exist_ok=True)
    thumbs = []
    for i in range(6):
        ts = total_dur * (0.08 + 0.17 * i)
        p = os.path.join(tmp, f"k_{i:02d}.jpg")
        subprocess.run(["ffmpeg", "-y", "-ss", f"{ts:.2f}", "-i", final_mp4, "-vframes", "1", "-q:v", "2", p],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        thumbs.append(Image.open(p).resize((480, 853), Image.Resampling.LANCZOS))
    sheet = Image.new("RGB", (480 * 3, 853 * 2), (12, 14, 20))
    for i, im in enumerate(thumbs):
        sheet.paste(im, ((i % 3) * 480, (i // 3) * 853))
    sheet.save(strip_png)
