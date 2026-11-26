"""Step B4: Nearest-neighbor 2x PS2 upscale (360x640 -> 720x1280), dynamic frame-accurate
PS2 Game HUD + Korean subtitles, Yuna subway PA + procedural retro SFX (-14 LUFS),
final MP4 muxer, and 6-frame contact strip QA sheet.
"""

from __future__ import annotations

import math
import os
import subprocess
import wave
from typing import List, Tuple

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = "/Users/yun-yeowon/workspace/ad-studio/ps2-kr-subway"
FRAMES_DIR = os.path.join(ROOT, "frames")
AUDIO_DIR = os.path.join(ROOT, "audio")
RAW_HUD_MP4 = os.path.join(ROOT, "ps2_kr_subway_hud.mp4")
FINAL_MP4 = os.path.join(ROOT, "ps2_kr_subway_ep1_final.mp4")
STRIP_PNG = os.path.join(ROOT, "qa_ps2_subway_strip.png")
FONT_PATH = "/System/Library/Fonts/AppleSDGothicNeo.ttc"

W, H, FPS, TOTAL_FRAMES = 720, 1280, 30, 240
SR = 48000


def load_font(size: int) -> ImageFont.FreeTypeFont:
    for idx in (4, 3, 2, 0):
        try:
            return ImageFont.truetype(FONT_PATH, size=size, index=idx)
        except Exception:
            pass
    return ImageFont.load_default()


F_HUD_LG = load_font(30)
F_HUD_SM = load_font(20)
F_BANNER = load_font(44)
F_PASS = load_font(58)
F_SUB = load_font(36)


def clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def draw_hud(im: Image.Image, f: int) -> Image.Image:
    im = im.convert("RGBA")
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)

    # Top-right PS2 Game HUD: Clock, Cash, HP bar (drains 1.0 -> 0.10), ST bar
    hp = 1.0
    if f > 52:
        hp = max(0.10, 1.0 - 0.90 * clamp01((f - 52) / 92.0))
    stamina = 1.0
    if 48 <= f <= 145:
        stamina = max(0.12, 1.0 - 0.85 * clamp01((f - 48) / 94.0))
    elif f > 145:
        stamina = min(0.45, 0.12 + 0.33 * clamp01((f - 145) / 60.0))

    # Top-right panel box
    d.rounded_rectangle([476, 44, 690, 212], radius=12, fill=(8, 12, 18, 175), outline=(255, 255, 255, 70), width=2)
    d.text((502, 54), "08:42", font=F_HUD_LG, fill=(235, 240, 248, 255), stroke_width=2, stroke_fill=(0, 0, 0, 240))
    d.text((598, 56), "AM", font=F_HUD_SM, fill=(170, 215, 255, 255))
    d.text((502, 92), "₩ 1,400", font=F_HUD_LG, fill=(115, 238, 125, 255), stroke_width=2, stroke_fill=(0, 0, 0, 240))

    # HP bar (green -> amber -> flashing red)
    if hp > 0.55:
        hp_col = (55, 220, 95, 255)
    elif hp > 0.25:
        hp_col = (245, 190, 40, 255)
    else:
        flash = (f // 4) % 2 == 0
        hp_col = (255, 65, 55, 255) if flash else (195, 35, 35, 255)
    d.text((494, 134), "HP", font=F_HUD_SM, fill=(255, 255, 255, 240))
    d.rectangle([532, 136, 672, 156], fill=(28, 32, 40, 230), outline=(255, 255, 255, 160), width=2)
    d.rectangle([535, 139, 535 + int(134 * hp), 153], fill=hp_col)

    # Stamina bar
    d.text((494, 168), "ST", font=F_HUD_SM, fill=(190, 235, 255, 240))
    d.rectangle([532, 170, 672, 188], fill=(28, 32, 40, 230), outline=(255, 255, 255, 140), width=2)
    d.rectangle([535, 173, 535 + int(134 * stamina), 185], fill=(60, 195, 255, 255))

    # Bottom-left Circular Line 2 Radar Minimap
    cx, cy, r = 104, 1172, 68
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(10, 16, 22, 200), outline=(210, 220, 230, 220), width=4)
    # Line 2 green track across minimap
    d.line([(cx - r + 10, cy + 4), (cx + r - 10, cy - 10)], fill=(0, 185, 88, 255), width=8)
    d.ellipse([cx + 12, cy - 12, cx + 26, cy + 2], fill=(250, 205, 35, 255), outline=(10, 14, 18, 255), width=2)
    d.text((cx - 26, cy + 16), "왕십리", font=F_HUD_SM, fill=(255, 255, 255, 240))
    # Player blip moving into train
    py_blip = int(cy + 26 - 30 * clamp01((f - 30) / 115.0))
    d.polygon([(cx, py_blip - 11), (cx - 8, py_blip + 7), (cx + 8, py_blip + 7)], fill=(255, 255, 255, 255), outline=(0, 0, 0, 255))

    # Dynamic Act Mission Banners & Korean Subtitles
    if 5 <= f <= 55:
        txt = "MISSION: 2호선 출근길 탑승"
        bb = d.textbbox((0, 0), txt, font=F_BANNER, stroke_width=5)
        tw = bb[2] - bb[0]
        d.text(((W - tw) // 2, 1020), txt, font=F_BANNER, fill=(250, 205, 48, 255), stroke_width=5, stroke_fill=(10, 10, 12, 250))
    elif 58 <= f <= 145:
        txt = "출입문 닫습니다! 밀어넣어!"
        bb = d.textbbox((0, 0), txt, font=F_SUB, stroke_width=5)
        tw = bb[2] - bb[0]
        d.text(((W - tw) // 2, 1026), txt, font=F_SUB, fill=(255, 255, 255, 255), stroke_width=5, stroke_fill=(8, 10, 14, 250))
    elif f >= 172:
        t1 = "MISSION PASSED!"
        t2 = "왕십리 탑승 성공 · 체력 -90%"
        b1 = d.textbbox((0, 0), t1, font=F_PASS, stroke_width=6)
        b2 = d.textbbox((0, 0), t2, font=F_SUB, stroke_width=5)
        w1, w2 = b1[2] - b1[0], b2[2] - b2[0]
        d.text(((W - w1) // 2, 232), t1, font=F_PASS, fill=(248, 198, 42, 255), stroke_width=6, stroke_fill=(10, 10, 14, 255))
        d.text(((W - w2) // 2, 304), t2, font=F_SUB, fill=(255, 255, 255, 255), stroke_width=5, stroke_fill=(10, 10, 14, 255))

    return Image.alpha_composite(im, ov).convert("RGB")


def render_hud_video() -> None:
    proc = subprocess.Popen([
        "ffmpeg", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
        "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
        "-c:v", "libx264", "-preset", "medium", "-crf", "17", "-pix_fmt", "yuv420p", "-r", str(FPS),
        RAW_HUD_MP4,
    ], stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)
    assert proc.stdin is not None
    for f in range(1, TOTAL_FRAMES + 1):
        fp = os.path.join(FRAMES_DIR, f"frame_{f:04d}.png")
        im = Image.open(fp).convert("RGB")
        if im.size != (W, H):
            im = im.resize((W, H), Image.Resampling.LANCZOS)
        comp = draw_hud(im, f)
        proc.stdin.write(comp.tobytes())
    proc.stdin.close()
    rc = proc.wait()
    if rc != 0:
        raise RuntimeError(f"FFmpeg HUD pipe failed with {rc}")
    print(f"[ps2-asm] Encoded nearest-neighbor + HUD video: {RAW_HUD_MP4}", flush=True)


def make_pa_wav(text: str, out_wav: str, rate: int = 185) -> None:
    aiff = out_wav + ".aiff"
    subprocess.run(["say", "-v", "Yuna", "-r", str(rate), "-o", aiff, text], check=True)
    # Radio station PA bandpass + crisp metallic announcement echo
    subprocess.run([
        "ffmpeg", "-y", "-i", aiff,
        "-af", "highpass=f=450,lowpass=f=2800,acompressor=threshold=-16dB:ratio=4,aecho=0.8:0.7:45:0.25",
        "-ac", "1", "-ar", str(SR), out_wav,
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    if os.path.exists(aiff):
        os.remove(aiff)


def load_wav(path: str) -> np.ndarray:
    with wave.open(path, "rb") as wf:
        pcm = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0
    return pcm


def add_mono(buf: np.ndarray, sig: np.ndarray, t_sec: float, gain: float = 1.0) -> None:
    i0 = int(t_sec * SR)
    i1 = min(len(buf), i0 + len(sig))
    if i1 > i0 and i0 >= 0:
        buf[i0:i1] += gain * sig[:i1 - i0]


def build_audio_mix(mix_wav: str) -> None:
    os.makedirs(AUDIO_DIR, exist_ok=True)
    pa1_w = os.path.join(AUDIO_DIR, "pa_arrive.wav")
    pa2_w = os.path.join(AUDIO_DIR, "pa_closing.wav")
    make_pa_wav("이번 역은 왕십리, 왕십리역입니다.", pa1_w, rate=185)
    make_pa_wav("출입문 닫습니다.", pa2_w, rate=215)

    dur = TOTAL_FRAMES / float(FPS)
    n = int(dur * SR)
    buf = np.zeros(n, dtype=np.float32)
    rng = np.random.default_rng(77)

    # Low subway station rumble bed
    t_all = np.arange(n, dtype=np.float32) / SR
    buf += 0.05 * np.sin(2 * np.pi * 52.0 * t_all) + 0.015 * rng.normal(0, 1, n).astype(np.float32)

    # Place PA announcements cleanly
    add_mono(buf, load_wav(pa1_w), 0.25, gain=0.65)
    add_mono(buf, load_wav(pa2_w), 3.70, gain=0.72)

    # 1. Mission Start Retro Synth Chime (0.12s)
    tc = np.arange(int(0.35 * SR), dtype=np.float32) / SR
    chime = np.sin(2 * np.pi * 523.25 * tc) * np.exp(-tc * 10.0) + 0.6 * np.sin(2 * np.pi * 783.99 * tc) * np.exp(-tc * 8.0)
    add_mono(buf, chime.astype(np.float32), 0.12, gain=0.25)

    # 2. Pneumatic door open hiss (0.45s)
    th = np.arange(int(0.55 * SR), dtype=np.float32) / SR
    hiss = rng.normal(0, 1, len(th)).astype(np.float32) * np.sin(np.pi * th / 0.55)
    add_mono(buf, hiss, 0.45, gain=0.14)

    # 3. Three crowd push thuds (1.95s, 2.85s, 3.75s)
    for t_push in (1.95, 2.85, 3.75):
        tp = np.arange(int(0.24 * SR), dtype=np.float32) / SR
        thud = (np.sin(2 * np.pi * 88.0 * np.exp(-tp * 9.0) * tp) + 0.35 * rng.normal(0, 1, len(tp))) * np.exp(-tp * 14.0)
        add_mono(buf, thud.astype(np.float32), t_push, gain=0.42)

    # 4. Iconic Seoul Metro Line 2 Door-Closing Buzzer Beep (3.95s..4.60s)
    for b_off, freq in ((3.95, 880.0), (4.15, 698.46), (4.35, 880.0), (4.55, 698.46)):
        tb = np.arange(int(0.14 * SR), dtype=np.float32) / SR
        beep = np.sin(2 * np.pi * freq * tb) * (1.0 - np.exp(-tb * 90.0)) * np.exp(-tb * 10.0)
        add_mono(buf, beep.astype(np.float32), b_off, gain=0.26)

    # 5. Heavy Door SLAM CLUNK! (4.80s)
    td = np.arange(int(0.28 * SR), dtype=np.float32) / SR
    slam = (np.sin(2 * np.pi * 62.0 * td) + 0.5 * rng.normal(0, 1, len(td))) * np.exp(-td * 16.0)
    add_mono(buf, slam.astype(np.float32), 4.80, gain=0.58)

    # 6. Subway VVVF Electric Inverter Whine (5.05s..8.00s): ascending harmonic pitch!
    tv = np.arange(int(2.95 * SR), dtype=np.float32) / SR
    f_vvvf = 95.0 + 185.0 * np.clip(tv / 2.6, 0.0, 1.0)
    phase = 2.0 * np.pi * np.cumsum(f_vvvf) / SR
    vvvf = (0.55 * np.sin(phase) + 0.25 * np.sin(2.0 * phase) + 0.12 * np.sin(3.0 * phase)) * np.minimum(1.0, tv / 0.35)
    add_mono(buf, vvvf.astype(np.float32), 5.05, gain=0.16)

    # 7. Original Warm Retro PS2 "MISSION PASSED!" Triumph Chord (5.75s..7.85s)
    t_end = np.arange(int(2.1 * SR), dtype=np.float32) / SR
    env = np.minimum(1.0, t_end / 0.06) * np.exp(-t_end * 1.15)
    chord = (
        np.sin(2 * np.pi * 261.63 * t_end)
        + 0.8 * np.sin(2 * np.pi * 329.63 * t_end)
        + 0.7 * np.sin(2 * np.pi * 392.00 * t_end)
        + 0.5 * np.sin(2 * np.pi * 523.25 * t_end)
    ) * env
    add_mono(buf, chord.astype(np.float32), 5.75, gain=0.22)

    buf = np.tanh(buf * 1.15).astype(np.float32)
    pcm16 = (np.clip(buf, -0.99, 0.99) * 32767.0).astype(np.int16)
    with wave.open(mix_wav, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SR)
        wf.writeframes(pcm16.tobytes())


def assemble() -> None:
    render_hud_video()
    mix_wav = os.path.join(AUDIO_DIR, "ps2_mix.wav")
    build_audio_mix(mix_wav)

    subprocess.run([
        "ffmpeg", "-y", "-i", RAW_HUD_MP4, "-i", mix_wav,
        "-filter:a", "aformat=sample_rates=48000:channel_layouts=stereo,loudnorm=I=-14:TP=-1.5:LRA=11,aresample=48000",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2", "-shortest",
        FINAL_MP4,
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    print(f"[ps2-asm] Assembled final video: {FINAL_MP4}", flush=True)

    # Build 6-frame contact strip (frames 15, 60, 100, 142, 175, 225)
    tmp_dir = os.path.join(ROOT, "audio")
    tiles: List[Image.Image] = []
    for fnum in (15, 60, 100, 142, 175, 225):
        t_sec = (fnum - 1) / float(FPS)
        png = os.path.join(tmp_dir, f"strip_{fnum}.png")
        subprocess.run([
            "ffmpeg", "-y", "-ss", f"{t_sec:.3f}", "-i", FINAL_MP4,
            "-frames:v", "1", "-q:v", "2", png,
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        tiles.append(Image.open(png).convert("RGB").resize((360, 640), Image.Resampling.LANCZOS))

    strip = Image.new("RGB", (360 * 3, 640 * 2))
    for i, tile in enumerate(tiles):
        strip.paste(tile, ((i % 3) * 360, (i // 3) * 640))
    strip.save(STRIP_PNG)
    print(f"[ps2-asm] Saved 6-frame strip: {STRIP_PNG}", flush=True)


if __name__ == "__main__":
    assemble()
