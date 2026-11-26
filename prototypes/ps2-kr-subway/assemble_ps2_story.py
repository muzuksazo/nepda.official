"""Step 4: Assemble 15.00s (450f @ 30fps, 720x1280) Narrated 4-Act PS2 Subway Comedy Episode
with dynamic arcade damage popups, HP/ST bars, wrong-way minimap alert, synced Korean subtitles,
procedural PS2/subway SFX, and -14 LUFS 48kHz stereo mastering.
"""

from __future__ import annotations

import json
import os
import subprocess
import wave
from typing import Dict, List

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFont

ROOT = "/Users/yun-yeowon/workspace/ad-studio/ps2-kr-subway"
FRAMES_DIR = os.path.join(ROOT, "frames_story")
AUDIO_DIR = os.path.join(ROOT, "audio")
TIMELINE_JSON = os.path.join(AUDIO_DIR, "vo_timeline.json")
RAW_HUD_MP4 = os.path.join(ROOT, "ps2_kr_subway_story_hud.mp4")
FINAL_MP4 = os.path.join(ROOT, "ps2_kr_subway_ep1_story_final.mp4")
STRIP_PNG = os.path.join(ROOT, "qa_ps2_story_strip.png")
FONT_PATH = "/System/Library/Fonts/AppleSDGothicNeo.ttc"

W, H, FPS, TOTAL_FRAMES = 720, 1280, 30, 450
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
F_BANNER = load_font(42)
F_FAIL = load_font(56)
F_DMG = load_font(28)
F_SUB = load_font(34)


def clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def draw_story_hud(im: Image.Image, f: int, timeline: List[Dict]) -> Image.Image:
    # WASTED dramatic desaturation/contrast shift at F418..F450
    if f >= 418:
        k = clamp01((f - 418) / 14.0)
        im = ImageEnhance.Color(im).enhance(1.0 - 0.65 * k)
        im = ImageEnhance.Contrast(im).enhance(1.0 + 0.22 * k)

    im = im.convert("RGBA")
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)

    # Top-right PS2 Game HUD: HP drops -45% at F142 bounce, drops to 10% at F302 door crush, 0% at F418 twist!
    hp = 1.0
    if f >= 418:
        hp = max(0.0, 0.10 * (1.0 - clamp01((f - 418) / 10.0)))
    elif f >= 298:
        hp = max(0.10, 0.55 - 0.45 * clamp01((f - 298) / 12.0))
    elif f >= 140:
        hp = max(0.55, 1.0 - 0.45 * clamp01((f - 140) / 10.0))

    stamina = 1.0
    if 96 <= f <= 145:
        stamina = max(0.30, 1.0 - 0.70 * clamp01((f - 96) / 45.0))
    elif 145 < f <= 210:
        stamina = min(0.75, 0.30 + 0.45 * clamp01((f - 145) / 60.0))
    elif 210 < f <= 315:
        stamina = max(0.08, 0.75 - 0.67 * clamp01((f - 210) / 90.0))
    else:
        stamina = 0.08

    d.rounded_rectangle([476, 44, 690, 212], radius=12, fill=(8, 12, 18, 180), outline=(255, 255, 255, 75), width=2)
    d.text((502, 54), "08:42", font=F_HUD_LG, fill=(235, 240, 248, 255), stroke_width=2, stroke_fill=(0, 0, 0, 240))
    d.text((598, 56), "AM", font=F_HUD_SM, fill=(170, 215, 255, 255))
    d.text((502, 92), "₩ 1,400", font=F_HUD_LG, fill=(115, 238, 125, 255), stroke_width=2, stroke_fill=(0, 0, 0, 240))

    if hp > 0.58:
        hp_col = (55, 220, 95, 255)
    elif hp > 0.25:
        hp_col = (245, 190, 40, 255)
    else:
        flash = (f // 4) % 2 == 0
        hp_col = (255, 58, 52, 255) if flash else (180, 28, 28, 255)

    d.text((494, 134), "HP", font=F_HUD_SM, fill=(255, 255, 255, 240))
    d.rectangle([532, 136, 672, 156], fill=(28, 32, 40, 230), outline=(255, 255, 255, 160), width=2)
    if hp > 0.0:
        d.rectangle([535, 139, 535 + max(2, int(134 * hp)), 153], fill=hp_col)

    d.text((494, 168), "ST", font=F_HUD_SM, fill=(190, 235, 255, 240))
    d.rectangle([532, 170, 672, 188], fill=(28, 32, 40, 230), outline=(255, 255, 255, 140), width=2)
    d.rectangle([535, 173, 535 + max(2, int(134 * stamina)), 185], fill=(60, 195, 255, 255))

    # Floating arcade damage popups
    if 141 <= f <= 178:
        u = (f - 141) / 37.0
        a = int(255 * (1.0 - max(0.0, (u - 0.6) / 0.4)))
        d.text((430, int(224 - 24 * u)), "-45 HP 인파 반동!", font=F_DMG, fill=(255, 75, 65, a), stroke_width=4, stroke_fill=(10, 10, 12, a))
    if 298 <= f <= 332:
        u = (f - 298) / 34.0
        a = int(255 * (1.0 - max(0.0, (u - 0.6) / 0.4)))
        d.text((425, int(224 - 24 * u)), "-45 HP 출입문 압착!", font=F_DMG, fill=(255, 75, 65, a), stroke_width=4, stroke_fill=(10, 10, 12, a))

    # Bottom-left Line 2 Radar Minimap (wrong-way red flash at F385+!)
    cx, cy, r = 104, 1172, 68
    ring_col = (255, 70, 60, 240) if (f >= 385 and (f // 5) % 2 == 0) else (210, 220, 230, 220)
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(10, 16, 22, 205), outline=ring_col, width=4)
    d.line([(cx - r + 10, cy + 4), (cx + r - 10, cy - 10)], fill=(0, 185, 88, 255), width=8)
    d.ellipse([cx + 10, cy - 12, cx + 24, cy + 2], fill=(250, 205, 35, 255), outline=(10, 14, 18, 255), width=2)
    if f >= 385:
        d.text((cx - 32, cy + 16), "성수행!", font=F_HUD_SM, fill=(255, 85, 75, 255))
        # Red wrong-way arrow pointing backward
        d.polygon([(cx - 12, cy - 16), (cx + 4, cy - 26), (cx + 4, cy - 6)], fill=(255, 65, 55, 255), outline=(0, 0, 0, 255))
    else:
        d.text((cx - 26, cy + 16), "왕십리", font=F_HUD_SM, fill=(255, 255, 255, 240))
        py_b = int(cy + 22 - 28 * clamp01((f - 95) / 215.0))
        d.polygon([(cx, py_b - 10), (cx - 8, py_b + 7), (cx + 8, py_b + 7)], fill=(255, 255, 255, 255), outline=(0, 0, 0, 255))

    # Story Act Banners
    if 4 <= f <= 62:
        txt = "MISSION: 2호선 출근길 탑승"
        bb = d.textbbox((0, 0), txt, font=F_BANNER, stroke_width=5)
        tw = bb[2] - bb[0]
        d.text(((W - tw) // 2, 235), txt, font=F_BANNER, fill=(250, 205, 48, 255), stroke_width=5, stroke_fill=(10, 10, 12, 250))
    elif 332 <= f <= 376:
        t1 = "MISSION PASSED...?"
        t2 = "왕십리 탑승 성공 · 체력 10%"
        b1 = d.textbbox((0, 0), t1, font=F_FAIL, stroke_width=6)
        b2 = d.textbbox((0, 0), t2, font=F_SUB, stroke_width=5)
        w1, w2 = b1[2] - b1[0], b2[2] - b2[0]
        d.text(((W - w1) // 2, 224), t1, font=F_FAIL, fill=(248, 205, 55, 255), stroke_width=6, stroke_fill=(10, 10, 14, 255))
        d.text(((W - w2) // 2, 294), t2, font=F_SUB, fill=(255, 255, 255, 255), stroke_width=5, stroke_fill=(10, 10, 14, 255))
    elif f >= 415:
        d.rectangle([0, 208, W, 355], fill=(12, 6, 8, 175))
        t1 = "MISSION FAILED!"
        t2 = "반대 방향 탑승 · 지각 확정"
        b1 = d.textbbox((0, 0), t1, font=F_FAIL, stroke_width=6)
        b2 = d.textbbox((0, 0), t2, font=F_SUB, stroke_width=5)
        w1, w2 = b1[2] - b1[0], b2[2] - b2[0]
        d.text(((W - w1) // 2, 224), t1, font=F_FAIL, fill=(255, 72, 58, 255), stroke_width=6, stroke_fill=(8, 8, 10, 255))
        d.text(((W - w2) // 2, 296), t2, font=F_SUB, fill=(255, 230, 160, 255), stroke_width=5, stroke_fill=(8, 8, 10, 255))

    # Synced Korean Dialogue & PA Subtitles from vo_timeline.json
    t_now = (f - 1) / float(FPS)
    active_cap = None
    for slot in timeline:
        if slot["start"] - 0.04 <= t_now <= slot["end"] + 0.14:
            active_cap = slot
            break
    if active_cap is not None:
        cap_txt = active_cap["caption"]
        col = (125, 228, 255, 255) if active_cap.get("pa") else (255, 255, 255, 255)
        bb = d.textbbox((0, 0), cap_txt, font=F_SUB, stroke_width=5)
        tw = bb[2] - bb[0]
        # Wrap slightly if very long (> 640px)
        if tw > 640 and "!" in cap_txt[:-1]:
            parts = cap_txt.split("!", 1)
            lines = [parts[0].strip() + "!", parts[1].strip()]
        elif tw > 640 and "," in cap_txt:
            parts = cap_txt.split(",", 1)
            lines = [parts[0].strip() + ",", parts[1].strip()]
        else:
            lines = [cap_txt]
        y0 = 1015 if len(lines) == 1 else 992
        for li, line in enumerate(lines):
            b = d.textbbox((0, 0), line, font=F_SUB, stroke_width=5)
            lw = b[2] - b[0]
            d.text(((W - lw) // 2, y0 + li * 48), line, font=F_SUB, fill=col, stroke_width=5, stroke_fill=(8, 10, 14, 250))

    return Image.alpha_composite(im, ov).convert("RGB")


def render_hud_video(timeline: List[Dict]) -> None:
    proc = subprocess.Popen([
        "ffmpeg", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
        "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
        "-c:v", "libx264", "-preset", "medium", "-crf", "17", "-pix_fmt", "yuv420p", "-r", str(FPS),
        RAW_HUD_MP4,
    ], stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)
    assert proc.stdin is not None
    for f in range(1, TOTAL_FRAMES + 1):
        fp = os.path.join(FRAMES_DIR, f"frame_{f:04d}.png")
        im = Image.open(fp).convert("RGB").resize((W, H), Image.Resampling.LANCZOS)
        comp = draw_story_hud(im, f, timeline)
        proc.stdin.write(comp.tobytes())
    proc.stdin.close()
    rc = proc.wait()
    if rc != 0:
        raise RuntimeError(f"FFmpeg HUD pipe failed with {rc}")
    print(f"[story-asm] Encoded HUD video: {RAW_HUD_MP4}", flush=True)


def load_wav(path: str) -> np.ndarray:
    with wave.open(path, "rb") as wf:
        return np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0


def add_mono(buf: np.ndarray, sig: np.ndarray, t_sec: float, gain: float = 1.0) -> None:
    i0 = int(t_sec * SR)
    i1 = min(len(buf), i0 + len(sig))
    if i1 > i0 and i0 >= 0:
        buf[i0:i1] += gain * sig[:i1 - i0]


def build_audio_mix(timeline: List[Dict], mix_wav: str) -> None:
    dur = TOTAL_FRAMES / float(FPS)
    n = int(dur * SR)
    buf = np.zeros(n, dtype=np.float32)
    rng = np.random.default_rng(108)
    t_all = np.arange(n, dtype=np.float32) / SR

    # Station rumble bed + accelerating train bed after F316 (10.53s)
    buf += 0.035 * np.sin(2 * np.pi * 52.0 * t_all) + 0.012 * rng.normal(0, 1, n).astype(np.float32)

    # Dialogue & PA voices from timeline
    for slot in timeline:
        g = 0.72 if slot.get("pa") else 0.90
        add_mono(buf, load_wav(slot["wav"]), slot["start"], gain=g)

    # 1. Mission Start Retro Chime (0.06s)
    tc = np.arange(int(0.35 * SR), dtype=np.float32) / SR
    add_mono(buf, (np.sin(2 * np.pi * 523.25 * tc) * np.exp(-tc * 10) + 0.6 * np.sin(2 * np.pi * 783.99 * tc) * np.exp(-tc * 8)).astype(np.float32), 0.06, 0.22)

    # 2. Pneumatic Door Open Hiss (1.45s)
    th = np.arange(int(0.55 * SR), dtype=np.float32) / SR
    add_mono(buf, (rng.normal(0, 1, len(th)).astype(np.float32) * np.sin(np.pi * th / 0.55)), 1.45, 0.14)

    # 3. Crowd Shock Sting (2.02s)
    ts = np.arange(int(0.32 * SR), dtype=np.float32) / SR
    add_mono(buf, (np.sin(2 * np.pi * (440.0 + 180.0 * ts) * ts) * np.exp(-ts * 9.0)).astype(np.float32), 2.02, 0.14)

    # 4. Push Effort Thuds (3.80s, 4.30s) & Comic Bounce-Back Spring/Hit (4.68s)!
    for t_p in (3.80, 4.30):
        tp = np.arange(int(0.22 * SR), dtype=np.float32) / SR
        add_mono(buf, ((np.sin(2 * np.pi * 92 * tp) + 0.35 * rng.normal(0, 1, len(tp))) * np.exp(-tp * 14)).astype(np.float32), t_p, 0.32)
    tb = np.arange(int(0.45 * SR), dtype=np.float32) / SR
    bounce = (np.sin(2 * np.pi * (110 + 210 * np.exp(-tb * 7)) * tb) + 0.4 * rng.normal(0, 1, len(tb))) * np.exp(-tb * 8)
    add_mono(buf, bounce.astype(np.float32), 4.68, 0.45)

    # 5. Iconic Line 2 Door-Closing Buzzer Melody (7.80s..9.40s) + Heavy Door SLAM (10.18s)
    for b_off, freq in ((7.80, 880.0), (8.02, 698.46), (8.24, 880.0), (8.46, 698.46), (8.68, 880.0)):
        td = np.arange(int(0.14 * SR), dtype=np.float32) / SR
        add_mono(buf, (np.sin(2 * np.pi * freq * td) * (1 - np.exp(-td * 90)) * np.exp(-td * 10)).astype(np.float32), b_off, 0.22)
    tsl = np.arange(int(0.28 * SR), dtype=np.float32) / SR
    add_mono(buf, ((np.sin(2 * np.pi * 58 * tsl) + 0.55 * rng.normal(0, 1, len(tsl))) * np.exp(-tsl * 15)).astype(np.float32), 10.18, 0.52)

    # 6. Subway VVVF Electric Inverter Acceleration (10.55s..15.00s)
    tv = np.arange(int(4.45 * SR), dtype=np.float32) / SR
    f_vv = 95.0 + 215.0 * np.clip(tv / 3.8, 0.0, 1.0)
    ph = 2.0 * np.pi * np.cumsum(f_vv) / SR
    add_mono(buf, ((0.5 * np.sin(ph) + 0.22 * np.sin(2 * ph)) * np.minimum(1.0, tv / 0.4)).astype(np.float32), 10.55, 0.13)

    # 7. Tentative Triumph Chime (11.10s) -> Twist Monitor Alert Beep (12.48s) -> WASTED MISSION FAILED Boom (13.88s)!
    tc2 = np.arange(int(0.8 * SR), dtype=np.float32) / SR
    add_mono(buf, ((np.sin(2 * np.pi * 261.6 * tc2) + 0.7 * np.sin(2 * np.pi * 392 * tc2)) * np.exp(-tc2 * 2.5)).astype(np.float32), 11.10, 0.16)
    tw = np.arange(int(0.25 * SR), dtype=np.float32) / SR
    add_mono(buf, (np.sin(2 * np.pi * (980 - 420 * tw) * tw) * np.exp(-tw * 12)).astype(np.float32), 12.48, 0.25)
    tfail = np.arange(int(1.1 * SR), dtype=np.float32) / SR
    fail_boom = (np.sin(2 * np.pi * (95 * np.exp(-tfail * 1.4) + 38) * tfail) + 0.45 * np.sin(2 * np.pi * 138.6 * tfail)) * np.exp(-tfail * 2.2)
    add_mono(buf, fail_boom.astype(np.float32), 13.88, 0.48)

    buf = np.tanh(buf * 1.1).astype(np.float32)
    pcm16 = (np.clip(buf, -0.99, 0.99) * 32767.0).astype(np.int16)
    with wave.open(mix_wav, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SR)
        wf.writeframes(pcm16.tobytes())


def assemble() -> None:
    with open(TIMELINE_JSON, "r", encoding="utf-8") as f:
        timeline = json.load(f)

    render_hud_video(timeline)
    mix_wav = os.path.join(AUDIO_DIR, "ps2_story_mix.wav")
    build_audio_mix(timeline, mix_wav)

    subprocess.run([
        "ffmpeg", "-y", "-i", RAW_HUD_MP4, "-i", mix_wav,
        "-filter:a", "aformat=sample_rates=48000:channel_layouts=stereo,loudnorm=I=-14:TP=-1.5:LRA=11,aresample=48000",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2", "-shortest",
        FINAL_MP4,
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    print(f"[story-asm] Assembled 15s final MP4: {FINAL_MP4}", flush=True)

    tiles: List[Image.Image] = []
    for fnum in (25, 80, 155, 265, 355, 425):
        t_sec = (fnum - 1) / float(FPS)
        png = os.path.join(AUDIO_DIR, f"story_strip_{fnum}.png")
        subprocess.run([
            "ffmpeg", "-y", "-ss", f"{t_sec:.3f}", "-i", FINAL_MP4,
            "-frames:v", "1", "-q:v", "2", png,
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        tiles.append(Image.open(png).convert("RGB").resize((360, 640), Image.Resampling.LANCZOS))

    strip = Image.new("RGB", (360 * 3, 640 * 2))
    for i, tile in enumerate(tiles):
        strip.paste(tile, ((i % 3) * 360, (i // 3) * 640))
    strip.save(STRIP_PNG)
    print(f"[story-asm] Saved 6-frame QA strip: {STRIP_PNG}", flush=True)


if __name__ == "__main__":
    assemble()
