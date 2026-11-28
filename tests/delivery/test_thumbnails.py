"""Offline regression coverage organized by PRD area."""
from tests.support.media_tools import (
    Image,
    ThumbnailBuilderCase,
    ad_thumbnail_builder,
    json,
    os,
    tempfile,
)
from tests.support.tempdirs import temporary_directory


class TestThumbnailBuilder(ThumbnailBuilderCase):
    def test_single_and_split_thumbnails_and_safe_zone_checks(self) -> None:
        with temporary_directory() as td:
            img_a = os.path.join(td, "a.png")
            img_b = os.path.join(td, "b.png")
            img_prod = os.path.join(td, "prod.png")
            Image.new("RGB", (768, 1376), (35, 45, 70)).save(img_a)
            Image.new("RGB", (720, 1280), (140, 40, 35)).save(img_b)
            Image.new("RGB", (512, 512), (230, 230, 230)).save(img_prod)

            spec = {
                "canvas": {"width": 1080, "height": 1920},
                "thumbnails": [
                    {
                        "id": "split_safe",
                        "filename": "thumb_split.png",
                        "layout": "split_2panel",
                        "panels": [
                            {"image": "a.png", "height": 940, "y": 0, "crop_norm": [0, 0.02, 1, 0.64]},
                            {"image": "b.png", "height": 968, "y": 952, "crop_norm": [0, 0.2, 1, 0.8]},
                        ],
                        "scrim": {"y_top": 745, "y_bottom": 1020, "peak_alpha": 200, "edge_soft": 90},
                        "pill": {"y": 725, "text": "첫 장면 테스트", "fill": [214, 48, 34, 240], "font_size": 33},
                        "headline": {
                            "gap_after_pill": 20,
                            "font_size": 84,
                            "lines": [
                                {"text": "상단 첫 번째 줄", "color": [255, 255, 255]},
                                {"text": "강조 두 번째 줄", "color": [255, 224, 71]},
                            ],
                        },
                    },
                    {
                        "id": "single_inset_safe",
                        "filename": "thumb_single.png",
                        "layout": "single",
                        "image": "a.png",
                        "scrim": {"y_top": 520, "y_bottom": 880},
                        "pill": {"y": 510, "text": "루틴 테스트", "font_size": 34},
                        "headline": {
                            "gap_after_pill": 22,
                            "font_size": 84,
                            "lines": [
                                {"text": "책상 위 변화", "color": [255, 224, 71]},
                                {"text": "직접 확인하기", "color": [255, 255, 255]},
                            ],
                        },
                        "inset_cards": [
                            {"image": "prod.png", "crop_px": [50, 50, 450, 450], "x": 680, "y": 1120, "size": 300}
                        ],
                    },
                    {
                        "id": "overflow_oob",
                        "filename": "thumb_oob.png",
                        "layout": "single",
                        "image": "b.png",
                        "pill": {"y": 240, "text": "상단 이탈 경고"},
                        "headline": {"gap_after_pill": 20, "lines": [{"text": "안전선 밖", "color": [255, 255, 255]}]},
                    },
                ],
            }
            spec_path = os.path.join(td, "thumbs_spec.json")
            with open(spec_path, "w", encoding="utf-8") as f:
                json.dump(spec, f, ensure_ascii=False)

            out_dir = os.path.join(td, "thumbs")
            sheet_path = os.path.join(out_dir, "thumbnails_sheet.png")
            res = ad_thumbnail_builder.build_from_spec(spec_path, out_dir, sheet_path=sheet_path)

            self.assertEqual(res["count"], 3)
            self.assertFalse(res["all_safe_zone_ok"])
            self.assertTrue(res["thumbnails"][0]["safe_zone_ok"])
            self.assertTrue(res["thumbnails"][1]["safe_zone_ok"])
            self.assertFalse(res["thumbnails"][2]["safe_zone_ok"])
            self.assertTrue(any("safe zone" in w for w in res["thumbnails"][2]["warnings"]))

            with Image.open(res["thumbnails"][0]["path"]) as im0:
                self.assertEqual(im0.size, (1080, 1920))
            with Image.open(res["thumbnails"][1]["path"]) as im1:
                self.assertEqual(im1.size, (1080, 1920))
            self.assertTrue(os.path.exists(sheet_path))
            with Image.open(sheet_path) as sh:
                # 3 tiles * 360 + 4 pads * 18 = 1152; hdr 42 + 640 + 2*18 = 718
                self.assertEqual(sh.size, (1152, 718))


    def test_oversized_line_blocks_panel_card_and_strict_margins(self) -> None:
        with temporary_directory() as td:
            bg = os.path.join(td, "bg.png")
            Image.new("RGB", (768, 1376), (25, 35, 50)).save(bg)
            spec = {
                "strict_margin": True,
                "thumbnails": [
                    {
                        "id": "blocks_ok",
                        "filename": "blocks.png",
                        "layout": "single",
                        "image": "bg.png",
                        "pill": {"y": 500, "text": "압도적 가독성 테스트", "font_size": 42},
                        "headline": {
                            "style": "line_blocks",
                            "font_size": 124,
                            "gap_after_pill": 22,
                            "lines": [
                                {"text": "아주 긴 한 줄 테스트 문구입니다", "color": [14, 18, 26]},
                                {"text": "자동 폭 맞춤 확인", "color": [180, 35, 20]},
                            ],
                        },
                    },
                    {
                        "id": "panel_clip_warn",
                        "filename": "panel_warn.png",
                        "layout": "single",
                        "image": "bg.png",
                        "pill": {"y": 430, "text": "엄격 마진 경계 테스트", "font_size": 40},
                        "headline": {
                            "style": "panel_card",
                            "font_size": 116,
                            "lines": [{"text": "짧은 제목", "color": [255, 255, 255]}],
                        },
                    },
                ],
            }
            sp = os.path.join(td, "spec.json")
            with open(sp, "w", encoding="utf-8") as f:
                json.dump(spec, f, ensure_ascii=False)
            res = ad_thumbnail_builder.build_from_spec(sp, os.path.join(td, "out"))
            t0 = res["thumbnails"][0]
            self.assertTrue(t0["safe_zone_ok"], t0["warnings"])
            self.assertGreaterEqual(t0["bounds"]["headline"][0], ad_thumbnail_builder.SAFE_X_MIN)
            self.assertLessEqual(t0["bounds"]["headline"][2], ad_thumbnail_builder.SAFE_X_MAX)
            t1 = res["thumbnails"][1]
            self.assertFalse(t1["safe_zone_ok"])
            self.assertTrue(any("strict" in w for w in t1["warnings"]))

    def test_serif_outline_short_lines_stay_inside_safe_zone(self) -> None:
        """테두리 글자의 오른쪽 끝을 2배로 잡아 정상 썸네일을 안전 영역 밖이라고 판정하던 버그의 회귀 테스트."""
        with temporary_directory() as td:
            bg = os.path.join(td, "bg.png")
            Image.new("RGB", (1080, 1920), (120, 140, 160)).save(bg)
            cases = (["3초 만에", "물기 순삭"], ["3초 만에 물기 순삭"])
            spec = {
                "canvas": {"width": 1080, "height": 1920},
                "strict_margin": True,
                "thumbnails": [
                    {
                        "id": f"serif_{i}",
                        "filename": f"serif_{i}.png",
                        "layout": "figma",
                        "figma_variant": "serif-outline",
                        "image": "bg.png",
                        "strict_margin": True,
                        "headline": {"style": "serif-outline", "lines": [{"text": ln} for ln in lines]},
                    }
                    for i, lines in enumerate(cases)
                ],
            }
            sp = os.path.join(td, "spec.json")
            with open(sp, "w", encoding="utf-8") as f:
                json.dump(spec, f, ensure_ascii=False)
            res = ad_thumbnail_builder.build_from_spec(sp, os.path.join(td, "out"))
            bg_rgb = (120, 140, 160)
            for t in res["thumbnails"]:
                self.assertTrue(t["safe_zone_ok"], t["warnings"])
                # 보고된 경계가 실제 그려진 글자(테두리 포함)를 감싸야 한다
                im = Image.open(t["path"]).convert("RGB")
                px = im.load()
                y0, y1 = t["bounds"]["headline"][1], t["bounds"]["headline"][3]
                ink_right = max(
                    x
                    for y in range(y0, y1, 4)
                    for x in range(im.width - 1, 0, -1)
                    if max(abs(px[x, y][c] - bg_rgb[c]) for c in range(3)) > 90
                    and not any(max(abs(px[x2, y][c] - bg_rgb[c]) for c in range(3)) > 90 for x2 in range(x + 1, im.width, 8))
                )
                self.assertLessEqual(ink_right, t["bounds"]["headline"][2])
