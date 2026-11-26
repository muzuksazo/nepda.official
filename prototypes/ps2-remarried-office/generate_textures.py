"""Step 1a: Generate corporate-palace parody textures (Boardroom KPI chart, Resignation doc, Scout offer)."""

from __future__ import annotations

import os
from PIL import Image, ImageDraw, ImageFont

TEX_DIR = "/Users/yun-yeowon/workspace/ad-studio/ps2-remarried-office/textures"
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

    # 1. Boardroom Presentation Screen (1024x512): "에이스 과장 98% vs 꼰대 팀장 1% vs 아부꾼 대리 1%"
    sc = Image.new("RGB", (1024, 512), (16, 22, 34))
    ds = ImageDraw.Draw(sc)
    ds.rectangle([0, 0, 1024, 78], fill=(22, 42, 82))
    ds.rectangle([0, 74, 1024, 82], fill=(235, 190, 58))
    ds.text((34, 18), "제1분기 긴급 구조조정 회의   |   Q1 RESTRUCTURING", font=load_font(34), fill=(255, 255, 255))

    ds.text((48, 106), "부서 실적 기여도 (TEAM KPI CONTRIBUTION)", font=load_font(28), fill=(185, 215, 255))

    bars = [
        ("에이스 과장", 0.98, "98%", (40, 215, 130)),
        ("꼰대 팀장", 0.04, "1%", (235, 78, 68)),
        ("아부꾼 대리", 0.04, "1%", (225, 125, 85)),
    ]
    y0 = 178
    for label, ratio, pct, col in bars:
        ds.text((48, y0 + 14), label, font=load_font(36), fill=(245, 248, 255))
        bx0, bx1 = 290, 880
        ds.rectangle([bx0, y0 + 8, bx1, y0 + 62], fill=(30, 38, 56), outline=(70, 86, 118), width=2)
        bw = max(18, int((bx1 - bx0) * ratio))
        ds.rectangle([bx0 + 3, y0 + 11, bx0 + bw, y0 + 59], fill=col)
        ds.text((898, y0 + 12), pct, font=load_font(40), fill=col)
        y0 += 102
    sc.save(os.path.join(TEX_DIR, "boardroom_screen.png"))

    # 2. Resignation Document Prop (512x512)
    doc = Image.new("RGB", (512, 512), (242, 240, 232))
    dd = ImageDraw.Draw(doc)
    dd.rectangle([28, 28, 484, 484], outline=(40, 44, 52), width=4)
    dd.text((104, 72), "권 고 사 직 서", font=load_font(52), fill=(20, 24, 30))
    dd.line([(72, 152), (440, 152)], fill=(40, 44, 52), width=3)
    for ly in (200, 244, 288, 332):
        dd.rectangle([76, ly, 430, ly + 16], fill=(165, 168, 175))
    dd.ellipse([340, 360, 444, 464], outline=(205, 38, 38), width=6)
    dd.text((366, 396), "결재", font=load_font(28), fill=(205, 38, 38))
    doc.save(os.path.join(TEX_DIR, "resignation_doc.png"))

    # 3. Gold Executive Scout Offer Card (512x256)
    cd = Image.new("RGB", (512, 256), (18, 18, 24))
    dc = ImageDraw.Draw(cd)
    dc.rectangle([10, 10, 502, 246], outline=(242, 198, 65), width=6)
    dc.rectangle([20, 20, 492, 68], fill=(242, 198, 65))
    dc.text((48, 26), "VIP EXECUTIVE OFFER", font=load_font(30), fill=(18, 16, 14))
    dc.text((42, 96), "경쟁사 임원 스카우트 제안서", font=load_font(34), fill=(255, 255, 255))
    dc.text((42, 154), "연봉 200%  ·  ₩9,000만", font=load_font(42), fill=(248, 210, 75))
    cd.save(os.path.join(TEX_DIR, "scout_card.png"))

    print(f"[tex] Saved 3 Remarried-Office textures into {TEX_DIR}")


if __name__ == "__main__":
    build_all()
