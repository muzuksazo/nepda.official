#!/usr/bin/env python3
"""Assemble 10.00s Zack D.-style Jet Umbrella 3D short:
Inworld TTS (이시우) Korean narration + procedural jet turbine/wind/barrel-crash SFX
+ PIL crisp Korean subtitles + -14.0 LUFS master + 6-frame QA contact sheet.
"""

from __future__ import annotations

import os
import subprocess
import wave

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = "/Users/yun-yeowon/workspace/ad-studio/zackd-jet-umbrella"
VO_DIR = os.path.join(ROOT, "vo")
RAW_MP4 = os.path.join(ROOT, "jet_umbrella_raw.mp4")
OUT_MP4 = os.path.join(ROOT, "jet_umbrella_final.mp4")
OUT_STRIP = os.path.join(ROOT, "qa_jet_umbrella_strip.png")
FONT_PATH = "/System/Library/Fonts/AppleSDGothicNeo.ttc"


def load_font(size: int) -> ImageFont.FreeTypeFont:
    for idx in (4, 3, 2, 0):
        try:
            return ImageFont.truetype(FONT_PATH, size=size, index=idx)
        except Exception:
            pass
    return ImageFont.load_default()


def make_caption_png(lines: list[str], out_path: str, width: int = 720, height: int = 210) -> None:
    im = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    f = load_font(38)
    y0 = 24 if len(lines) > 1 else 62
    for idx, line in enumerate(lines):
        bbox = d.textbbox((0, 0), line, font=f, stroke_width=4)
        tw = bbox[2] - bbox[0]
        x = (width - tw) // 2
        y = y0 + idx * 54
        d.text(
            (x, y), line, font=f,
            fill=(255, 255, 255, 255),
            stroke_width=5, stroke_fill=(8, 10, 16, 245),
        )
    im.save(out_path)


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


def build_sfx_track(total_dur: float, crash_t: float, out_wav: str) -> None:
    sr = 48000
    n = int(total_dur * sr)
    t = np.arange(n, dtype=np.float32) / sr
    rng = np.random.default_rng(2026)

    # 1. Jet turbine harmonic whine rising F65 (2.1s) -> roaring peak F95..245 (3.2..8.2s)
    spool = np.clip((t - 1.6) / 1.8, 0.0, 1.0)
    fade_out = 1.0 - np.clip((t - 8.2) / 1.8, 0.0, 1.0)
    freq = 360.0 + 980.0 * (spool ** 1.2)
    phase = 2.0 * np.pi * np.cumsum(freq) / sr
    whine = (0.14 * np.sin(phase) + 0.06 * np.sin(2.0 * phase)) * (0.25 + 0.75 * spool) * fade_out

    # 2. Low broadband jet exhaust roar + supersonic wind rush
    noise = rng.normal(0.0, 1.0, n).astype(np.float32)
    # Moving-average low-pass for deep rumble & mid wind
    k_low = np.ones(28, dtype=np.float32) / 28.0
    rumble = np.convolve(noise, k_low, mode="same")
    roar_env = 0.08 + 0.52 * np.clip((t - 2.1) / 1.1, 0.0, 1.0) * (1.0 - 0.75 * np.clip((t - 8.3) / 1.5, 0.0, 1.0))
    jet_roar = rumble * roar_env

    # 3. Sharp umbrella snap inside-out crack at t ~ 3.45s + second flutter at 4.05s
    snap = np.zeros(n, dtype=np.float32)
    for st, amp in ((3.45, 0.65), (4.05, 0.35), (4.85, 0.55)):
        dt = t - st
        mask = (dt >= 0.0) & (dt < 0.28)
        snap[mask] += amp * np.exp(-dt[mask] * 18.0) * (0.65 * noise[mask] + 0.45 * np.sin(2.0 * np.pi * 190.0 * dt[mask]))

    # 4. Heavy metallic barrel crash & rolling clatter around crash_t
    crash = np.zeros(n, dtype=np.float32)
    for offset, amp, f_ring in ((0.0, 0.90, 210.0), (0.09, 0.62, 340.0), (0.24, 0.48, 285.0), (0.45, 0.30, 410.0), (0.72, 0.18, 260.0)):
        dt = t - (crash_t + offset)
        mask = (dt >= 0.0) & (dt < 0.65)
        env = np.exp(-dt[mask] * 9.5)
        ring = np.sin(2.0 * np.pi * f_ring * dt[mask]) + 0.5 * np.sin(2.0 * np.pi * f_ring * 1.47 * dt[mask])
        crash[mask] += amp * env * (0.55 * ring + 0.65 * noise[mask] * np.exp(-dt[mask] * 16.0))

    mix = np.tanh((whine * 0.45 + jet_roar * 0.65 + snap * 0.85 + crash * 0.95) * 0.85) * 0.65
    with wave.open(out_wav, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes((np.clip(mix, -0.99, 0.99) * 32767.0).astype(np.int16).tobytes())


def main(crash_sec: float = 8.27) -> None:
    total_dur = 10.00
    slots = [
        ("s1_hook.mp3", 0.04, 2.74, ["만약 시동이 걸린 제트 엔진 뒤에서", "우산을 펼치면 어떻게 될까요?"]),
        ("s2_invert.mp3", 2.82, 2.40, ["시속 300km의 후폭풍에", "우산이 순식간에 뒤집히고,"]),
        ("s3_flight.mp3", 5.26, 2.36, ["몸 전체가 활주로 끝까지", "종이인형처럼 날아가 버립니다."]),
        ("s4_crash.mp3", 7.66, 2.28, ["실제 여객기 엔진은 차 한 대도", "날려버릴 만큼 강력합니다."]),
    ]

    sfx_wav = os.path.join(ROOT, "sfx_mix.wav")
    build_sfx_track(total_dur, crash_sec, sfx_wav)

    inputs = ["-i", sfx_wav]
    fparts = ["[0:a]aresample=48000,volume=0.44[sfx]"]
    vo_labels = ["[sfx]"]
    cap_paths = []
    for idx, (mp3_name, start_s, dur_s, lines) in enumerate(slots, start=1):
        w_out = os.path.join(ROOT, f"vo_fit_{idx}.wav")
        trim_and_fit_vo(os.path.join(VO_DIR, mp3_name), dur_s, w_out)
        inputs += ["-i", w_out]
        ms = int(round(start_s * 1000))
        fparts.append(f"[{idx}:a]aresample=48000,adelay={ms}|{ms}[v{idx}]")
        vo_labels.append(f"[v{idx}]")

        cap_p = os.path.join(ROOT, f"cap_{idx}.png")
        make_caption_png(lines, cap_p)
        cap_paths.append((cap_p, start_s, start_s + dur_s))

    mix_wav = os.path.join(ROOT, "final_audio_mix.wav")
    n_in = len(vo_labels)
    fc = ";".join(fparts) + f";{''.join(vo_labels)}amix=inputs={n_in}:normalize=0,loudnorm=I=-14.0:TP=-1.0:LRA=7[aout]"
    subprocess.run([
        "ffmpeg", "-y", *inputs, "-filter_complex", fc, "-map", "[aout]",
        "-ar", "48000", "-ac", "2", "-t", f"{total_dur:.3f}", mix_wav,
    ], check=True)

    v_inputs = ["-i", RAW_MP4]
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
        "-shortest", OUT_MP4,
    ], check=True)

    # 6-frame QA contact sheet (3x2)
    tmp = os.path.join(ROOT, "strip_tmp")
    os.makedirs(tmp, exist_ok=True)
    thumbs = []
    for i, ts in enumerate((0.8, 2.8, 4.1, 6.2, 7.6, 8.9)):
        p = os.path.join(tmp, f"k_{i:02d}.jpg")
        subprocess.run(["ffmpeg", "-y", "-ss", f"{ts:.2f}", "-i", OUT_MP4, "-vframes", "1", "-q:v", "2", p],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        thumbs.append(Image.open(p).resize((480, 853), Image.Resampling.LANCZOS))
    sheet = Image.new("RGB", (480 * 3, 853 * 2), (12, 14, 20))
    for i, im in enumerate(thumbs):
        sheet.paste(im, ((i % 3) * 480, (i // 3) * 853))
    sheet.save(OUT_STRIP)

    for p in (RAW_MP4, OUT_MP4):
        res = subprocess.check_output(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration,size:stream=codec_type,codec_name,width,height,r_frame_rate", "-of", "json", p],
            text=True,
        )
        print(f"=== {os.path.basename(p)} ===\n{res}")


if __name__ == "__main__":
    main()
