"""Tests for $0.00 Commercial Packshot End-Card, Outro Audio Resolve, and Service wiring."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import unittest
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from hookpipe.audio_mix import AudioPack, mix_bgm_and_sfx, resolve_audio_pack  # noqa: E402
from hookpipe.endcard import (  # noqa: E402
    DEFAULT_CTA_BADGE,
    append_endcard,
    build_endcard_clip,
    extract_best_product_frame,
    find_pretendard_font,
    render_packshot_png,
)
from hookpipe.media import MediaTools, probe, run_ffmpeg  # noqa: E402
from hookpipe.service import _pick_endcard_subhead, _read_body_cta_badge  # noqa: E402
from tests.support.hookpipe import make_video, tools_or_none  # noqa: E402
from tests.support.tempdirs import temporary_directory  # noqa: E402

TOOLS = tools_or_none()


def _make_tone(tools: MediaTools, path: Path, *, freq: int, seconds: float, volume: float = 0.35) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    run_ffmpeg(
        tools,
        [
            "-f", "lavfi",
            "-i", f"sine=frequency={freq}:duration={seconds:.2f}",
            "-af", f"volume={volume}",
            "-c:a", "libmp3lame",
            "-q:a", "4",
            str(path),
        ],
    )
    return path


def _window_mean_volume_db(tools: MediaTools, media_path: Path, *, start_sec: float, dur_sec: float) -> float:
    stderr = run_ffmpeg(
        tools,
        [
            "-ss", f"{start_sec:.3f}",
            "-t", f"{dur_sec:.3f}",
            "-i", str(media_path),
            "-vn",
            "-af", "volumedetect",
            "-f", "null",
            "-",
        ],
    )
    m = re.search(r"mean_volume:\s*(-?\d+(?:\.\d+)?)\s*dB", stderr)
    if not m:
        raise AssertionError(f"volumedetect output missing mean_volume:\n{stderr}")
    return float(m.group(1))


def _codec_names(tools: MediaTools, path: Path) -> tuple[str, str, str]:
    if not tools.ffprobe:
        return ("h264", "aac", "30/1")
    proc = subprocess.run(
        [tools.ffprobe, "-v", "error", "-show_streams", "-of", "json", str(path)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=True,
    )
    streams = json.loads(proc.stdout or "{}").get("streams") or []
    v = next(s for s in streams if s.get("codec_type") == "video")
    a = next(s for s in streams if s.get("codec_type") == "audio")
    return (str(v.get("codec_name")), str(a.get("codec_name")), str(v.get("r_frame_rate")))


class PackshotEndcardImageTests(unittest.TestCase):
    def test_find_pretendard_font_locates_bundled_otf(self) -> None:
        font = find_pretendard_font()
        self.assertIsNotNone(font)
        assert font is not None
        self.assertTrue(font.is_file())
        self.assertEqual(font.name, "Pretendard-ExtraBold.otf")

    def test_render_packshot_png_with_product_frame_and_audit_sample(self) -> None:
        with temporary_directory() as td:
            root = Path(td)
            bg = root / "product_shot.png"
            img = Image.new("RGB", (1080, 1920), (36, 48, 66))
            draw = ImageDraw.Draw(img)
            # Studio backdrop + crisp product silhouette so visual inspection is meaningful
            draw.rectangle((0, 1080, 1080, 1920), fill=(26, 33, 46))
            draw.rounded_rectangle((310, 480, 770, 1140), radius=42, fill=(215, 222, 232), outline=(255, 255, 255), width=6)
            draw.ellipse((410, 620, 670, 880), fill=(48, 128, 220), outline=(255, 224, 71), width=8)
            draw.rectangle((380, 930, 700, 1010), fill=(28, 34, 44))
            img.save(bg, format="PNG")

            out_png = root / "packshot.png"
            rendered = render_packshot_png(
                bg,
                product_name="초강력 방수 테이프",
                subhead="실내외 누수 10초 차단 · 오늘만 1+1 특가",
                cta_badge="프로필 링크에서 확인 →",
                out_png=out_png,
            )
            self.assertTrue(rendered.is_file())
            with Image.open(rendered) as out_img:
                self.assertEqual(out_img.size, (1080, 1920))
                self.assertEqual(out_img.mode, "RGB")
                # Verify bright yellow CTA pill pixels exist inside the lower safe zone
                pill_crop = out_img.crop((200, 1120, 880, 1500))
                yellow_pixels = sum(
                    1 for r, g, b in pill_crop.getdata() if r >= 235 and g >= 205 and b <= 110
                )
                self.assertGreater(yellow_pixels, 8000, f"Expected CTA pill pixels, got {yellow_pixels}")
                # Verify bright white hero title pixels exist in title region
                title_crop = out_img.crop((100, 900, 980, 1180))
                white_pixels = sum(
                    1 for r, g, b in title_crop.getdata() if r >= 235 and g >= 235 and b >= 235
                )
                self.assertGreater(white_pixels, 1500, f"Expected title text pixels, got {white_pixels}")

            audit_out = os.environ.get("ENDCARD_AUDIT_PNG", "").strip()
            if audit_out:
                audit_path = Path(audit_out)
                audit_path.parent.mkdir(parents=True, exist_ok=True)
                audit_path.write_bytes(rendered.read_bytes())
                self.assertTrue(audit_path.is_file())

    def test_render_packshot_png_without_bg_frame_and_long_korean_wrap(self) -> None:
        with temporary_directory() as td:
            out_png = Path(td) / "fallback_packshot.png"
            render_packshot_png(
                None,
                product_name="프리미엄 초고압 스테인리스 워터젯 청소기 본체 풀세트",
                subhead="무선 고압 세척으로 베란다와 욕실 틈새 물때까지 한 번에 정리",
                cta_badge="",
                out_png=out_png,
            )
            with Image.open(out_png) as out_img:
                self.assertEqual(out_img.size, (1080, 1920))
                pill_crop = out_img.crop((180, 1100, 900, 1510))
                yellow_pixels = sum(
                    1 for r, g, b in pill_crop.getdata() if r >= 235 and g >= 205 and b <= 110
                )
                self.assertGreater(yellow_pixels, 8000)


class ServiceCtaHelperTests(unittest.TestCase):
    def test_read_body_cta_badge_precedence(self) -> None:
        with temporary_directory() as td:
            root = Path(td)
            body_video = root / "body.mp4"
            body_video.write_bytes(b"stub")

            # 1) Fallback to default when no body.json and no short offer
            self.assertEqual(
                _read_body_cta_badge(body_video, {"price_or_offer": "매우 긴 프로모션 설명 문구입니다 20자 초과"}),
                DEFAULT_CTA_BADGE,
            )
            # 2) Short price_or_offer fallback when body.json absent
            self.assertEqual(
                _read_body_cta_badge(body_video, {"price_or_offer": "오늘만 19,900원"}),
                "오늘만 19,900원",
            )
            # 3) body.json script.cta_badge takes highest precedence
            (root / "body.json").write_text(
                json.dumps({"script": {"cta_badge": "특가 바로 보기 →"}}, ensure_ascii=False),
                encoding="utf-8",
            )
            self.assertEqual(
                _read_body_cta_badge(body_video, {"price_or_offer": "오늘만 19,900원"}),
                "특가 바로 보기 →",
            )

    def test_pick_endcard_subhead_avoids_duplicating_cta(self) -> None:
        product = {
            "price_or_offer": "오늘만 1+1 특가",
            "verified_facts": ["실내외 누수 즉시 차단"],
        }
        self.assertEqual(
            _pick_endcard_subhead(product, "프로필 링크에서 확인 →"),
            "실내외 누수 즉시 차단 · 오늘만 1+1 특가",
        )
        self.assertEqual(
            _pick_endcard_subhead(product, "오늘만 1+1 특가"),
            "실내외 누수 즉시 차단",
        )


@unittest.skipUnless(TOOLS, "ffmpeg (testsrc·loudnorm 필터 포함)가 필요합니다")
class EndcardMediaAndAudioTests(unittest.TestCase):
    def test_extract_best_frame_build_and_append_endcard(self) -> None:
        assert TOOLS is not None
        with temporary_directory() as td:
            root = Path(td)
            # Build a 4s body clip: first 2.7s solid gray (blurry/flat), last 1.3s testsrc2 (high-edge detail)
            flat = root / "flat.mp4"
            sharp = root / "sharp.mp4"
            body = root / "body.mp4"
            run_ffmpeg(
                TOOLS,
                [
                    "-f", "lavfi", "-i", "color=c=gray:s=1080x1920:r=30:d=2.7",
                    "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo:d=2.7",
                    "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-t", "2.7", str(flat),
                ],
            )
            make_video(TOOLS, sharp, seconds=1.3, width=1080, height=1920, fps=30)
            run_ffmpeg(
                TOOLS,
                [
                    "-i", str(flat), "-i", str(sharp),
                    "-filter_complex", "[0:v][0:a][1:v][1:a]concat=n=2:v=1:a=1[v][a]",
                    "-map", "[v]", "-map", "[a]",
                    "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", str(body),
                ],
            )

            best_png = extract_best_product_frame(body, root / "best.png", TOOLS)
            self.assertIsNotNone(best_png)
            assert best_png is not None
            self.assertTrue(best_png.is_file())
            with Image.open(best_png) as img:
                # Sharp testsrc2 frame at 74% or 86% has rich colors vs flat gray(128,128,128)
                extrema = img.convert("RGB").getextrema()
                max_spread = max(hi - lo for lo, hi in extrema)
                self.assertGreater(max_spread, 40, f"Expected sharp textured frame, got extrema={extrema}")

            card_png = render_packshot_png(
                best_png,
                product_name="60분 비주얼 타이머",
                subhead="60분형 아날로그 타이머 · 집중 시간 시각화",
                cta_badge="프로필 링크에서 확인 →",
                out_png=root / "card.png",
            )
            endcard_mp4 = build_endcard_clip(card_png, root / "endcard.mp4", duration_sec=2.0, tools=TOOLS)
            ec_info = probe(TOOLS, endcard_mp4)
            self.assertEqual((ec_info.width, ec_info.height), (1080, 1920))
            self.assertTrue(ec_info.has_audio)
            self.assertAlmostEqual(ec_info.duration, 2.0, delta=0.15)
            self.assertEqual(_codec_names(TOOLS, endcard_mp4), ("h264", "aac", "30/1"))

            final_mp4 = make_video(TOOLS, root / "final.mp4", seconds=4.0, width=1080, height=1920, fps=30)
            before_dur = probe(TOOLS, final_mp4).duration
            new_dur = append_endcard(final_mp4, endcard_mp4, tools=TOOLS, tmp_dir=root / "_tmp")
            self.assertAlmostEqual(new_dur - before_dur, 2.0, delta=0.2)
            final_info = probe(TOOLS, final_mp4)
            self.assertEqual((final_info.width, final_info.height), (1080, 1920))
            self.assertTrue(final_info.has_audio)
            self.assertEqual(_codec_names(TOOLS, final_mp4), ("h264", "aac", "30/1"))

    def test_audio_pack_and_mix_bgm_with_endcard_fade_and_outro_sfx(self) -> None:
        assert TOOLS is not None
        with temporary_directory() as td:
            root = Path(td)
            assets = root / "audio_assets"
            _make_tone(TOOLS, assets / "bgm_hook_a.mp3", freq=220, seconds=6.0, volume=0.4)
            _make_tone(TOOLS, assets / "bgm_body.mp3", freq=330, seconds=10.0, volume=0.4)
            _make_tone(TOOLS, assets / "sfx_transition.mp3", freq=660, seconds=0.4, volume=0.5)
            _make_tone(TOOLS, assets / "sfx_outro.mp3", freq=880, seconds=0.5, volume=0.5)

            pack = resolve_audio_pack(
                type("S", (), {"hook_bgm_enabled": True, "hook_audio_location": str(assets)})(),
                None,
                hook_type="A",
                cache_dir=root / "cache",
            )
            self.assertFalse(pack.is_empty())
            self.assertIsNotNone(pack.outro_sfx)
            self.assertFalse(AudioPack(outro_sfx=pack.outro_sfx).is_empty())

            # 8.0s video: 3.0s hook + 3.0s body + 2.0s silent end-card
            hook_body = make_video(TOOLS, root / "hb.mp4", seconds=6.0, width=1080, height=1920, fps=30, audio=True)
            card = render_packshot_png(
                None,
                product_name="초강력 방수 테이프",
                subhead="실내외 누수 차단",
                cta_badge="프로필 링크에서 확인 →",
                out_png=root / "card.png",
            )
            ec = build_endcard_clip(card, root / "ec.mp4", duration_sec=2.0, tools=TOOLS)
            total_dur = append_endcard(hook_body, ec, tools=TOOLS, tmp_dir=root / "_ec_tmp")
            self.assertAlmostEqual(total_dur, 8.0, delta=0.2)

            lufs = mix_bgm_and_sfx(
                hook_body,
                hook_sec=3.0,
                twist_sec=3.0,
                tools=TOOLS,
                pack=pack,
                tmp_dir=root / "_mix",
                endcard_sec=2.0,
            )
            self.assertIsNotNone(lufs)
            assert lufs is not None
            self.assertAlmostEqual(lufs, -14.0, delta=3.0)

            # Verify smooth fade-out: the very end [7.7s..8.0s] must be much quieter than [6.0s..6.4s] outro entry
            outro_head_db = _window_mean_volume_db(TOOLS, hook_body, start_sec=6.0, dur_sec=0.45)
            tail_end_db = _window_mean_volume_db(TOOLS, hook_body, start_sec=7.70, dur_sec=0.28)
            self.assertLess(tail_end_db, outro_head_db - 10.0, (outro_head_db, tail_end_db))

            # Also verify single-BGM fallback path with endcard_sec=2.0 (silent video so BGM fade-out is isolated)
            single_vid = make_video(TOOLS, root / "single.mp4", seconds=7.0, width=1080, height=1920, fps=30, audio=False)
            single_lufs = mix_bgm_and_sfx(
                single_vid,
                hook_sec=3.0,
                twist_sec=3.0,
                tools=TOOLS,
                pack=AudioPack(body_bgm=pack.body_bgm),
                tmp_dir=root / "_mix_single",
                endcard_sec=2.0,
            )
            self.assertIsNotNone(single_lufs)
            mid_db = _window_mean_volume_db(TOOLS, single_vid, start_sec=3.0, dur_sec=0.5)
            end_db = _window_mean_volume_db(TOOLS, single_vid, start_sec=6.7, dur_sec=0.28)
            self.assertLess(end_db, mid_db - 10.0, (mid_db, end_db))


if __name__ == "__main__":
    unittest.main()
