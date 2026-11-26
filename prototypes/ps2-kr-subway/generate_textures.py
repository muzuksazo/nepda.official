"""Generate crisp Korean Seoul Line 2 signage & retro PS2 textures via PIL."""

from __future__ import annotations

import os
from PIL import Image, ImageDraw, ImageFont

TEX_DIR = "/Users/yun-yeowon/workspace/ad-studio/ps2-kr-subway/textures"
FONT_PATH = "/System/Library/Fonts/AppleSDGothicNeo.ttc"


def load_font(size: int) -> ImageFont.FreeTypeFont:
    for idx in (4, 3, 2, 0):
        try:
            return ImageFont.truetype(FONT_PATH, size=size, index=idx)
        except Exception:
            pass
    return ImageFont.load_default()


def build_all() -> None:
    os.makedirs(TEX_DIR, exist_ok=True)

    # 1. Wangsimni hanging ceiling LED display (512x256)
    im = Image.new("RGB", (512, 256), (18, 22, 28))
    d = ImageDraw.Draw(im)
    # Top bright info panel
    d.rectangle([16, 16, 496, 128], fill=(38, 128, 212))
    d.rectangle([16, 16, 496, 46], fill=(12, 164, 78))
    d.text((34, 20), "SEOUL METRO LINE 2", font=load_font(22), fill=(255, 255, 255))
    d.text((36, 62), "강남 · 성수 순환선  INNER CIRCLE", font=load_font(26), fill=(245, 250, 255))
    # Bottom black LED bezel with Wangsimni Station + Line 2 badge
    d.rectangle([16, 138, 496, 240], fill=(12, 14, 18), outline=(45, 52, 62), width=3)
    d.ellipse([36, 156, 102, 222], fill=(0, 168, 77))
    d.text((57, 164), "2", font=load_font(44), fill=(255, 255, 255))
    d.text((132, 152), "왕십리역", font=load_font(56), fill=(255, 255, 255))
    d.text((370, 178), "Wangsimni", font=load_font(22), fill=(180, 220, 255))
    im.save(os.path.join(TEX_DIR, "wangsimni_led.png"))

    # 2. Line 2 Route Map (1024x192)
    rm = Image.new("RGB", (1024, 192), (234, 238, 242))
    dr = ImageDraw.Draw(rm)
    dr.rectangle([0, 0, 1024, 34], fill=(0, 168, 77))
    dr.text((24, 4), "2호선  LINE 2", font=load_font(22), fill=(255, 255, 255))
    dr.rectangle([40, 92, 984, 112], fill=(0, 168, 77))
    stations = ["건대입구", "성수", "뚝섬", "한양대", "왕십리", "상왕십리", "신당"]
    f_st = load_font(26)
    for i, st in enumerate(stations):
        cx = 85 + i * 142
        is_cur = (st == "왕십리")
        r = 18 if is_cur else 12
        col = (245, 190, 20) if is_cur else (255, 255, 255)
        dr.ellipse([cx - r, 102 - r, cx + r, 102 + r], fill=col, outline=(0, 110, 50), width=4)
        bbox = dr.textbbox((0, 0), st, font=f_st)
        tw = bbox[2] - bbox[0]
        dr.text((cx - tw // 2, 134), st, font=f_st, fill=(210, 40, 20) if is_cur else (25, 30, 38))
    rm.save(os.path.join(TEX_DIR, "line2_routemap.png"))

    # 3. PSD Safety Decal (512x256)
    psd = Image.new("RGB", (512, 256), (218, 226, 232))
    dp = ImageDraw.Draw(psd)
    dp.rectangle([0, 0, 512, 48], fill=(0, 168, 77))
    dp.text((28, 8), "2호선  ·  왕십리  Wangsimni", font=load_font(28), fill=(255, 255, 255))
    dp.rectangle([20, 175, 492, 236], fill=(240, 185, 18), outline=(25, 25, 25), width=3)
    dp.text((66, 186), "출입문 기대지 마세요", font=load_font(34), fill=(18, 18, 22))
    psd.save(os.path.join(TEX_DIR, "psd_decal.png"))

    # 4. Ribbed White Cotton Tank Texture (256x256 low-res PS2 grain)
    tk = Image.new("RGB", (256, 256), (235, 236, 232))
    dt = ImageDraw.Draw(tk)
    for x in range(0, 256, 4):
        shade = 220 if (x // 4) % 2 == 0 else 242
        dt.line([(x, 0), (x, 256)], fill=(shade, shade + 1, shade - 2), width=2)
    tk.save(os.path.join(TEX_DIR, "hero_tank_tex.png"))

    # 5. Wrong-way twist ceiling LED display (512x256): clean triangle icon + "성수행 (반대방향)"
    wr = Image.new("RGB", (512, 256), (18, 12, 14))
    dw = ImageDraw.Draw(wr)
    dw.rectangle([16, 16, 496, 128], fill=(165, 28, 24))
    dw.rectangle([16, 16, 496, 52], fill=(235, 165, 18))
    dw.polygon([(40, 22), (28, 46), (52, 46)], fill=(18, 14, 14))
    dw.text((37, 25), "!", font=load_font(18), fill=(235, 165, 18))
    dw.text((62, 22), "OPPOSITE DIRECTION  반대방향 경고", font=load_font(22), fill=(18, 14, 14))
    dw.text((34, 68), "반대 방향 · 성수 방면  WRONG WAY", font=load_font(26), fill=(255, 248, 240))
    dw.rectangle([16, 138, 496, 240], fill=(14, 12, 16), outline=(230, 65, 55), width=4)
    dw.ellipse([36, 156, 102, 222], fill=(0, 168, 77))
    dw.text((57, 164), "2", font=load_font(44), fill=(255, 255, 255))
    dw.text((120, 154), "성수행", font=load_font(54), fill=(255, 215, 50))
    dw.text((294, 170), "(반대방향)", font=load_font(36), fill=(255, 85, 75))
    wr.save(os.path.join(TEX_DIR, "seongsu_wrong_led.png"))
    print(f"[tex] Saved 5 PS2 subway textures into {TEX_DIR}")


if __name__ == "__main__":
    build_all()
