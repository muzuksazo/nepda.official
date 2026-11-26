"""Step 4: Assemble 15.00s (450f @ 30fps, 720x1280) Remarried-Empress Office Parody
with PS2 RPG Interactive Choice Box, Salary x2 Gold Popups, 3-cast Korean Voiceover,
procedural fanfare/SFX (-14 LUFS, 48kHz stereo), and 6-frame verification strip.
"""

from __future__ import annotations

import json
import os
import subprocess
import wave
from typing import Dict, List

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFont

ROOT = "/Users/yun-yeowon/workspace/ad-studio/ps2-remarried-office"
FRAMES_DIR = os.path.join(ROOT, "frames")
AUDIO_DIR = os.path.join(ROOT, "audio")
TIMELINE_JSON = os.path.join(AUDIO_DIR, "vo_timeline.json")
RAW_HUD_MP4 = os.path.join(ROOT, "ps2_remarried_office_hud.mp4")
FINAL_MP4 = os.path.join(ROOT, "ps2_remarried_office_final.mp4")
STRIP_PNG = os.path.join(ROOT, "qa_remarried_office_strip.png")
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


F_HUD_LG = load_font(28)
F_HUD_SM = load_font(19)
F_BANNER = load_font(42)
F_FAIL = load_font(54)
F_DMG = load_font(27)
F_SUB = load_font(30)
F_RPG_TITLE = load_font(22)
F_RPG_OPT = load_font(26)


def clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def draw_office_hud(im: Image.Image, f: int, timeline: List[Dict]) -> Image.Image:
    if f >= 415:
        k = clamp01((f - 415) / 14.0)
        im = ImageEnhance.Color(im).enhance(1.0 - 0.60 * k)
        im = ImageEnhance.Contrast(im).enhance(1.0 + 0.20 * k)

    im = im.convert("RGBA")
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)

    # Top-right PS2 Status Box: Boss HP & Ace Salary counter (doubles at F260!)
    boss_hp = 1.0
    if f >= 415:
        boss_hp = 0.0
    elif f >= 295:
        boss_hp = max(0.05, 0.45 - 0.40 * clamp01((f - 295) / 25.0))
    elif f >= 195:
        boss_hp = max(0.45, 1.0 - 0.55 * clamp01((f - 195) / 20.0))

    d.rounded_rectangle([440, 40, 694, 212], radius=12, fill=(10, 12, 22, 185), outline=(240, 198, 72, 140), width=2)
    d.text((462, 50), "09:00", font=F_HUD_LG, fill=(235, 240, 248, 255), stroke_width=2, stroke_fill=(0, 0, 0, 240))
    d.text((552, 53), "AM · 대회의실", font=F_HUD_SM, fill=(180, 215, 255, 255))

    if f >= 260:
        sal_col = (255, 218, 70, 255)
        sal_txt = "₩9,000만 (+100%)"
    else:
        sal_col = (120, 238, 130, 255)
        sal_txt = "₩4,500만"
    d.text((462, 88), sal_txt, font=load_font(25), fill=sal_col, stroke_width=2, stroke_fill=(0, 0, 0, 240))

    d.text((456, 130), "팀장 HP", font=F_HUD_SM, fill=(255, 225, 225, 245))
    d.rectangle([534, 132, 676, 152], fill=(28, 32, 40, 230), outline=(255, 255, 255, 160), width=2)
    if boss_hp > 0.0:
        hp_col = (60, 220, 95, 255) if boss_hp > 0.5 else ((245, 185, 45, 255) if boss_hp > 0.2 else (255, 62, 55, 255))
        d.rectangle([537, 135, 537 + max(2, int(136 * boss_hp)), 149], fill=hp_col)

    d.text((456, 166), "멘탈", font=F_HUD_SM, fill=(215, 200, 255, 240))
    mental = 1.0 if f < 195 else (0.45 if f < 355 else max(0.0, 0.45 * (1.0 - clamp01((f - 355) / 25.0))))
    d.rectangle([534, 168, 676, 186], fill=(28, 32, 40, 230), outline=(255, 255, 255, 140), width=2)
    if mental > 0.0:
        d.rectangle([537, 171, 537 + max(2, int(136 * mental)), 183], fill=(165, 110, 255, 255))

    # Arcade Damage Popups
    if 195 <= f <= 232:
        u = (f - 195) / 37.0
        a = int(255 * (1.0 - max(0.0, (u - 0.6) / 0.4)))
        d.text((410, int(224 - 24 * u)), "-55 HP 사이다 반격!", font=F_DMG, fill=(95, 245, 195, a), stroke_width=4, stroke_fill=(8, 10, 14, a))
    if 295 <= f <= 332:
        u = (f - 295) / 37.0
        a = int(255 * (1.0 - max(0.0, (u - 0.6) / 0.4)))
        d.text((400, int(224 - 24 * u)), "연봉 200% 스카우트!", font=F_DMG, fill=(255, 218, 70, a), stroke_width=4, stroke_fill=(8, 10, 14, a))

    # Interactive PS2 RPG Choice Dialogue Menu (F122..F174)
    if 122 <= f <= 174:
        bx0, by0, bx1, by1 = 54, 710, 666, 905
        d.rounded_rectangle([bx0, by0, bx1, by1], radius=14, fill=(10, 14, 28, 222), outline=(240, 196, 68, 240), width=3)
        d.text((bx0 + 22, by0 + 14), "SELECT RESPONSE  ·  대응 선택", font=F_RPG_TITLE, fill=(240, 196, 68, 255))
        d.line([(bx0 + 18, by0 + 46), (bx1 - 18, by0 + 46)], fill=(240, 196, 68, 130), width=2)

        opt2_active = f >= 142
        opt2_flash = f >= 160 and (f // 3) % 2 == 0
        c1 = (255, 235, 120, 255) if not opt2_active else (175, 182, 198, 230)
        c2 = (255, 255, 255, 255) if opt2_flash else ((255, 220, 75, 255) if opt2_active else (200, 208, 222, 235))
        p1 = "▶ " if not opt2_active else "   "
        p2 = "▶ " if opt2_active else "   "
        if opt2_active:
            fill_hl = (210, 155, 35, 140) if opt2_flash else (42, 68, 118, 190)
            d.rounded_rectangle([bx0 + 14, by0 + 112, bx1 - 14, by0 + 174], radius=8, fill=fill_hl, outline=(255, 218, 75, 220), width=2)
        else:
            d.rounded_rectangle([bx0 + 14, by0 + 54, bx1 - 14, by0 + 106], radius=8, fill=(42, 68, 118, 175))

        d.text((bx0 + 24, by0 + 64), f"{p1}[1] 울며 매달린다", font=F_RPG_OPT, fill=c1)
        d.text((bx0 + 24, by0 + 126), f"{p2}[2] 퇴사 수락 + 연봉 2배 이직 통보", font=F_RPG_OPT, fill=c2)

    # Story Act Banners
    if 4 <= f <= 62:
        txt = "MISSION: 권고사직 방어전"
        bb = d.textbbox((0, 0), txt, font=F_BANNER, stroke_width=5)
        d.text(((W - (bb[2] - bb[0])) // 2, 235), txt, font=F_BANNER, fill=(250, 205, 48, 255), stroke_width=5, stroke_fill=(10, 10, 12, 250))
    elif f >= 412:
        d.rectangle([0, 204, W, 356], fill=(12, 8, 10, 175))
        t1 = "MISSION PASSED!"
        t2 = "꼰대 팀장 WASTED · 실적 -98%"
        b1 = d.textbbox((0, 0), t1, font=F_FAIL, stroke_width=6)
        b2 = d.textbbox((0, 0), t2, font=F_SUB, stroke_width=5)
        d.text(((W - (b1[2] - b1[0])) // 2, 218), t1, font=F_FAIL, fill=(250, 210, 58, 255), stroke_width=6, stroke_fill=(8, 8, 10, 255))
        d.text(((W - (b2[2] - b2[0])) // 2, 294), t2, font=F_SUB, fill=(255, 88, 75, 255), stroke_width=5, stroke_fill=(8, 8, 10, 255))

    # Synced Korean Subtitles with Speaker Badges
    t_now = (f - 1) / float(FPS)
    active = None
    for slot in timeline:
        if slot["start"] - 0.04 <= t_now <= slot["end"] + 0.14:
            active = slot
            break
    if active is not None:
        spk = active["speaker"]
        cap = active["caption"]
        col = (255, 255, 255, 255)
        if "과장" in spk:
            col = (130, 245, 220, 255)
        elif "대표" in spk:
            col = (255, 224, 95, 255)

        # Wrap cleanly on punctuation without splitting '?!'
        bb = d.textbbox((0, 0), cap, font=F_SUB, stroke_width=5)
        if (bb[2] - bb[0]) > 630:
            if "?!" in cap[:-2]:
                idx = cap.find("?!") + 2
                lines = [cap[:idx].strip(), cap[idx:].strip()]
            elif "?" in cap[:-1]:
                idx = cap.find("?") + 1
                lines = [cap[:idx].strip(), cap[idx:].strip()]
            elif "," in cap:
                parts = cap.split(",", 1)
                lines = [parts[0].strip() + ",", parts[1].strip()]
            elif "..." in cap:
                parts = cap.split("...", 1)
                lines = [parts[0].strip() + "...", parts[1].strip()]
            else:
                mid = len(cap) // 2
                sp = cap.rfind(" ", 0, mid + 6)
                sp = sp if sp > 4 else mid
                lines = [cap[:sp].strip(), cap[sp:].strip()]
        else:
            lines = [cap]

        # Speaker tag pill
        sb = d.textbbox((0, 0), spk, font=F_HUD_SM)
        sw = sb[2] - sb[0] + 24
        y_top = 985 if len(lines) == 1 else 950
        d.rounded_rectangle([(W - sw) // 2, y_top - 38, (W + sw) // 2, y_top - 6], radius=14, fill=(10, 14, 24, 215), outline=col, width=2)
        d.text(((W - (sb[2] - sb[0])) // 2, y_top - 33), spk, font=F_HUD_SM, fill=col)

        for li, line in enumerate(lines):
            b = d.textbbox((0, 0), line, font=F_SUB, stroke_width=5)
            d.text(((W - (b[2] - b[0])) // 2, y_top + li * 46), line, font=F_SUB, fill=col, stroke_width=5, stroke_fill=(8, 10, 14, 250))

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
        comp = draw_office_hud(im, f, timeline)
        proc.stdin.write(comp.tobytes())
    proc.stdin.close()
    rc = proc.wait()
    if rc != 0:
        raise RuntimeError(f"FFmpeg HUD pipe failed: {rc}")
    print(f"[office-asm] Encoded HUD video: {RAW_HUD_MP4}", flush=True)


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
    rng = np.random.default_rng(202)
    t_all = np.arange(n, dtype=np.float32) / SR
    buf += 0.015 * np.sin(2 * np.pi * 60.0 * t_all) + 0.004 * rng.normal(0, 1, n).astype(np.float32)

    for slot in timeline:
        add_mono(buf, load_wav(slot["wav"]), slot["start"], gain=0.92)

    # 1. Royal Court Mission Chime (0.06s)
    tc = np.arange(int(0.45 * SR), dtype=np.float32) / SR
    add_mono(buf, (np.sin(2 * np.pi * 523.25 * tc) * np.exp(-tc * 9) + 0.6 * np.sin(2 * np.pi * 783.99 * tc) * np.exp(-tc * 7)).astype(np.float32), 0.06, 0.22)

    # 2. Paper slap on mahogany table (1.55s & 6.35s)
    for t_slap in (1.55, 6.35):
        ts = np.arange(int(0.18 * SR), dtype=np.float32) / SR
        add_mono(buf, ((np.sin(2 * np.pi * 120 * ts) + 0.6 * rng.normal(0, 1, len(ts))) * np.exp(-ts * 22)).astype(np.float32), t_slap, 0.28)

    # 3. RPG Choice Menu Bleep (4.70s) & Confirm Chime (5.35s)
    t_b = np.arange(int(0.12 * SR), dtype=np.float32) / SR
    add_mono(buf, (np.sin(2 * np.pi * 880 * t_b) * np.exp(-t_b * 18)).astype(np.float32), 4.70, 0.22)
    t_c = np.arange(int(0.28 * SR), dtype=np.float32) / SR
    add_mono(buf, ((np.sin(2 * np.pi * 659.25 * t_c) + 0.7 * np.sin(2 * np.pi * 987.77 * t_c)) * np.exp(-t_c * 11)).astype(np.float32), 5.35, 0.24)

    # 4. Dramatic Plot-Twist Brass Sting (6.32s)
    tbs = np.arange(int(0.45 * SR), dtype=np.float32) / SR
    add_mono(buf, ((np.sin(2 * np.pi * 220 * tbs) + 0.6 * np.sin(2 * np.pi * 329.6 * tbs)) * np.exp(-tbs * 6)).astype(np.float32), 6.32, 0.26)

    # 5. Double Doors Burst Open + Golden Rival CEO Harp/Chord Fanfare (8.25s..9.80s)
    td = np.arange(int(0.30 * SR), dtype=np.float32) / SR
    add_mono(buf, ((np.sin(2 * np.pi * 72 * td) + 0.55 * rng.normal(0, 1, len(td))) * np.exp(-td * 12)).astype(np.float32), 8.22, 0.48)
    for k, freq in enumerate((523.25, 659.25, 783.99, 1046.50)):
        th = np.arange(int(0.85 * SR), dtype=np.float32) / SR
        add_mono(buf, (np.sin(2 * np.pi * freq * th) * np.exp(-th * 3.5)).astype(np.float32), 8.30 + k * 0.08, 0.16)

    # 6. Salary 2x Coin Jingle (9.80s)
    for k, freq in enumerate((987.77, 1318.51)):
        tj = np.arange(int(0.22 * SR), dtype=np.float32) / SR
        add_mono(buf, (np.sin(2 * np.pi * freq * tj) * np.exp(-tj * 12)).astype(np.float32), 9.75 + k * 0.10, 0.22)

    # 7. Deep Retro WASTED Sub-Bass Boom on Team Leader Meltdown (13.85s)
    tw = np.arange(int(1.10 * SR), dtype=np.float32) / SR
    add_mono(buf, ((np.sin(2 * np.pi * (95 * np.exp(-tw * 1.4) + 38) * tw) + 0.4 * np.sin(2 * np.pi * 146.8 * tw)) * np.exp(-tw * 2.2)).astype(np.float32), 13.85, 0.45)

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
    mix_wav = os.path.join(AUDIO_DIR, "remarried_mix.wav")
    build_audio_mix(timeline, mix_wav)

    subprocess.run([
        "ffmpeg", "-y", "-i", RAW_HUD_MP4, "-i", mix_wav,
        "-filter:a", "aformat=sample_rates=48000:channel_layouts=stereo,loudnorm=I=-14:TP=-1.5:LRA=11,aresample=48000",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2", "-shortest",
        FINAL_MP4,
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    print(f"[office-asm] Saved 15s final MP4: {FINAL_MP4}", flush=True)

    tiles: List[Image.Image] = []
    for fnum in (45, 155, 215, 295, 340, 420):
        t_sec = (fnum - 1) / float(FPS)
        png = os.path.join(AUDIO_DIR, f"strip_{fnum}.png")
        subprocess.run([
            "ffmpeg", "-y", "-ss", f"{t_sec:.3f}", "-i", FINAL_MP4,
            "-frames:v", "1", "-q:v", "2", png,
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        tiles.append(Image.open(png).convert("RGB").resize((360, 640), Image.Resampling.LANCZOS))

    strip = Image.new("RGB", (360 * 3, 640 * 2))
    for i, tile in enumerate(tiles):
        strip.paste(tile, ((i % 3) * 360, (i // 3) * 640))
    strip.save(STRIP_PNG)
    print(f"[office-asm] Saved 6-frame strip: {STRIP_PNG}", flush=True)


if __name__ == "__main__":
    assemble()
