#!/usr/bin/env python3
"""Offline unit tests for shortform-ad-remix-director scripts.

Covers ad_thumbnail_builder.py, ad_audio_prep.py, ad_source_analyzer.py, and
hardened Google Flow helpers in flow_automator.py without touching live Chrome.
"""

from __future__ import annotations

import json
import math
import os
import struct
import sys
import tempfile
import unittest
import wave
from unittest.mock import patch

from PIL import Image

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

import ad_audio_prep  # noqa: E402
import ad_gate_a_lint  # noqa: E402
import ad_source_analyzer  # noqa: E402
import ad_thumbnail_builder  # noqa: E402
import flow_automator  # noqa: E402


def _write_test_wav(path: str, *, sample_rate: int = 48000) -> None:
    """Write 2.1s stereo WAV: 0.2s silence + 0.6s 440Hz tone + 0.5s silence + 0.6s 554Hz tone + 0.2s silence."""
    segments = [
        (0.20, 0.0, 0.0),
        (0.60, 440.0, 0.35),
        (0.50, 0.0, 0.0),
        (0.60, 554.37, 0.35),
        (0.20, 0.0, 0.0),
    ]
    frames = bytearray()
    for dur, freq, amp in segments:
        n = int(round(dur * sample_rate))
        for i in range(n):
            v = amp * math.sin(2.0 * math.pi * freq * (i / sample_rate)) if amp > 0 else 0.0
            s16 = max(-32767, min(32767, int(v * 32767.0)))
            frames.extend(struct.pack("<hh", s16, s16))
    with wave.open(path, "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(bytes(frames))


class TestThumbnailBuilder(unittest.TestCase):
    def test_single_and_split_thumbnails_and_safe_zone_checks(self) -> None:
        with tempfile.TemporaryDirectory() as td:
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
        with tempfile.TemporaryDirectory() as td:
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


class TestGateAOrthogonalGuard(unittest.TestCase):
    def _base_facts(self, td: str) -> str:
        fp = os.path.join(td, "00_product_facts.md")
        with open(fp, "w", encoding="utf-8") as f:
            f.write("# Facts\n- [F01] [VERIFIED] 실물 테스트 스펀지\n")
        return fp

    def _base_spec(self, td: str, arch: str, captions: list, *, gap: bool = True, sim: float | None = None, taboo: list | None = None) -> dict:
        src = os.path.join(td, "src.mp4")
        if not os.path.exists(src):
            open(src, "wb").write(b"dummy")
        vo = os.path.join(td, "vo.wav")
        if not os.path.exists(vo):
            open(vo, "wb").write(b"dummy")
        tl = [
            {"id": "H1", "type": "video", "path": src, "framing": "full-bleed", "duration": 5.0, "audio_owner": "mute"},
            {"id": "H2", "type": "video", "path": src, "framing": "full-bleed", "duration": 4.0, "audio_owner": "mute"},
        ]
        if gap:
            tl.append({"id": "STOP", "type": "silence_gap", "duration": 0.28, "audio_owner": "silence"})
        tl.append({"id": "P1", "type": "video", "path": src, "framing": "full-bleed", "duration": 7.0, "audio_owner": "mute", "fact_ids": ["F01"]})
        spec = {
            "project_id": f"test-{arch}",
            "title": "테스트",
            "mode": "narrative_master",
            "track_archetype": arch,
            "hook_window_sec": 9.0,
            "framing_mode": "full-bleed",
            "disclosure": "ai_assisted",
            "source_video": src,
            "source_duration": 10.0,
            "allow_static_intro": True,
            "vo_audio": vo,
            "usps": [{"title": "테스트 USP", "fact_ids": ["F01"]}],
            "timeline": tl,
            "captions": captions,
            "cta": {"type": "comment_engagement", "copy": "어떠신가요?", "fact_ids": ["F01"]},
        }
        if sim is not None:
            spec["hook_similarity_score"] = sim
        if taboo is not None:
            spec["product_taboo_keywords"] = taboo
        return spec

    def test_gate_a_blocks_c_disguised_a_and_b_and_accepts_orthogonal(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            fp = self._base_facts(td)
            bad_a = self._base_spec(
                td,
                "A_bgrade_reversal",
                [
                    {"start": 0.0, "end": 4.0, "text": "스펀지 하나면 끝"},
                    {"start": 9.3, "end": 16.0, "text": "선반에 두기 딱 좋아요"},
                ],
                taboo=["스펀지"],
            )
            checks_bad_a, _ = ad_gate_a_lint.run_lint(bad_a, fp)
            c13_errs = [e for i, _, e in checks_bad_a if i == 13][0]
            self.assertGreaterEqual(len(c13_errs), 2)

            good_a = self._base_spec(
                td,
                "A_bgrade_reversal",
                [
                    {"start": 0.0, "end": 8.5, "text": "전국 원룸 욕실 해수면 상승"},
                    {"start": 9.3, "end": 16.0, "text": "단 한 집만 사막처럼 말라 있었다"},
                ],
                taboo=["스펀지"],
            )
            checks_good_a, _ = ad_gate_a_lint.run_lint(good_a, fp)
            self.assertTrue(all(not e for _, _, e in checks_good_a), checks_good_a)

            bad_b = self._base_spec(
                td,
                "B_info_hook_offset",
                [{"start": 0.0, "end": 4.0, "text": "행주로 닦아도 번지고 바꿨어요"}],
                sim=0.80,
                taboo=["스펀지"],
            )
            checks_bad_b, _ = ad_gate_a_lint.run_lint(bad_b, fp)
            self.assertTrue([e for i, _, e in checks_bad_b if i == 13][0])

            good_b = self._base_spec(
                td,
                "B_info_hook_offset",
                [
                    {"start": 0.0, "end": 5.0, "text": "6억 년 살아남은 해면동물"},
                    {"start": 9.3, "end": 16.0, "text": "천 원 블록 소분 원리입니다"},
                ],
                sim=0.45,
                taboo=["스펀지"],
            )
            spec_c = self._base_spec(
                td,
                "C_direct_proof",
                [
                    {"start": 0.0, "end": 4.0, "text": "행주 물자국 번지죠"},
                    {"start": 9.3, "end": 16.0, "text": "원스윕 흡수 스펀지"},
                ],
            )
            checks_good_b, _ = ad_gate_a_lint.run_lint(good_b, fp)
            self.assertTrue(all(not e for _, _, e in checks_good_b), checks_good_b)
            self.assertEqual(ad_gate_a_lint.validate_abc_orthogonality([good_a, good_b, spec_c]), [])
            self.assertTrue(ad_gate_a_lint.validate_abc_orthogonality([good_a, spec_c, spec_c]))


class TestAudioPrep(unittest.TestCase):
    def test_probe_islands_and_manifest_subslice(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            wav_path = os.path.join(td, "sample.wav")
            _write_test_wav(wav_path)

            probed = ad_audio_prep.probe_islands(wav_path, silence_db=-39.0, min_silence=0.15)
            self.assertEqual(probed["island_count"], 2)
            self.assertAlmostEqual(probed["islands"][0]["start"], 0.16, delta=0.06)
            self.assertAlmostEqual(probed["islands"][1]["start"], 1.26, delta=0.06)
            self.assertGreaterEqual(probed["islands"][0]["gap_after"], 0.30)

            manifest_path = os.path.join(td, "vo_manifest.json")
            with open(manifest_path, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "beats": [
                            {
                                "id": "VO_1",
                                "file": "sample.wav",
                                "start_sec": probed["islands"][0]["start"],
                                "end_sec": probed["islands"][0]["end"],
                                "trim_edges": False,
                                "gap_after": 0.28,
                                "text": "첫 문장",
                            },
                            {
                                "id": "VO_2",
                                "file": "sample.wav",
                                "start_sec": probed["islands"][1]["start"],
                                "end_sec": probed["islands"][1]["end"],
                                "trim_edges": False,
                                "gap_after": 0.0,
                                "text": "둘째 문장",
                            },
                        ]
                    },
                    f,
                    ensure_ascii=False,
                )

            out_wav = os.path.join(td, "vo_master.wav")
            out_json = os.path.join(td, "vo_segments.json")
            built = ad_audio_prep.build_manifest_vo(manifest_path, out_wav, out_json)
            self.assertEqual(built["segment_count"], 2)
            self.assertAlmostEqual(built["segments"][0]["gap_after"], 0.28, places=2)
            gap_actual = built["segments"][1]["start"] - built["segments"][0]["end"]
            self.assertAlmostEqual(gap_actual, 0.28, delta=0.02)
            self.assertTrue(os.path.exists(out_wav))


class TestSourceAnalyzer(unittest.TestCase):
    def test_aspect_framing_recommendations(self) -> None:
        cases = [
            (532, 532, "1:1", "blur-bleed"),
            (960, 1280, "960:1280", "smart-crop"),
            (720, 1280, "9:16", "full-bleed"),
            (1920, 1080, "16:9", "blur-bleed"),
        ]
        for w, h, exp_aspect, exp_framing in cases:
            payload = {
                "format": {"duration": "8.0", "size": "100000", "bit_rate": "500000"},
                "streams": [
                    {
                        "codec_type": "video",
                        "codec_name": "h264",
                        "width": w,
                        "height": h,
                        "r_frame_rate": "30/1",
                    }
                ],
            }
            with patch.object(ad_source_analyzer.subprocess, "run") as m_run:
                m_run.return_value.stdout = json.dumps(payload)
                meta = ad_source_analyzer.ffprobe_metadata("/tmp/dummy.mp4")
                self.assertEqual(meta["aspect_label"], exp_aspect)
                self.assertEqual(meta["recommended_framing"], exp_framing)


class TestFlowAutomatorHardening(unittest.TestCase):
    def test_open_lightbox_download_menu_compact_fallback_and_filter(self) -> None:
        dom_compact = {
            "elements": [
                {"role": "button", "name": "옵션 더보기", "ref": "r_more"},
            ]
        }
        dom_more_menu = {
            "elements": [
                {"role": "menuitem", "name": "즐겨찾기", "ref": "m_fav"},
                {"role": "menuitem", "name": "download 미디어 다운로드", "ref": "m_dl"},
                {"role": "menuitem", "name": "휴지통", "ref": "m_trash"},
            ]
        }
        dom_quality_menu = {
            "elements": [
                {"role": "menuitem", "name": "즐겨찾기", "ref": "q_fav"},
                {"role": "menuitem", "name": "720p 원본 크기", "ref": "q_720"},
                {"role": "menuitem", "name": "1080p 업스케일링됨", "ref": "q_1080"},
                {"role": "menuitem", "name": "휴지통", "ref": "q_trash"},
            ]
        }
        clicked: list[str] = []

        def fake_click_ref(_tab: int, ref: str) -> None:
            clicked.append(ref)

        with patch.object(flow_automator, "read_dom", side_effect=[dom_compact, dom_more_menu, dom_quality_menu]), patch.object(
            flow_automator, "click_ref", side_effect=fake_click_ref
        ), patch.object(flow_automator.time, "sleep"):
            _, filtered = flow_automator._open_lightbox_download_menu(123, media="video")

        self.assertEqual(clicked, ["r_more", "m_dl"])
        self.assertEqual([el["ref"] for el in filtered], ["q_720", "q_1080"])

    def test_open_tile_to_lightbox_stale_ref_fallback(self) -> None:
        urls = iter([
            "https://labs.google/fx/project/abc",
            "https://labs.google/fx/project/abc",
            "https://labs.google/fx/project/abc",
            "https://labs.google/fx/project/abc",
            "https://labs.google/fx/project/abc",
            "https://labs.google/fx/project/abc",
            "https://labs.google/fx/project/abc",
            "https://labs.google/fx/project/abc",
            "https://labs.google/fx/project/abc",
            "https://labs.google/fx/project/abc/edit/item-1",
        ])
        with patch.object(flow_automator, "click_xy", side_effect=RuntimeError("ugot click rc=1: stale_ref")), patch.object(
            flow_automator, "get_page_url", side_effect=lambda _t: next(urls)
        ), patch.object(flow_automator, "evaluate_js") as m_eval, patch.object(flow_automator.time, "sleep"):
            flow_automator._open_tile_to_lightbox(
                123,
                {"x": 200, "y": 300, "top": 220, "h": 180},
                "media_key_xyz",
                "wave tile",
            )
            self.assertTrue(m_eval.called)

    def test_generate_ref_ignores_signed_url_rotation_until_new_key(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            media_states = iter([
                {"items": [{"src_key": "old_key_1"}], "firstKey": "old_key_1", "firstSrc": "https://cdn/1?sig=A"},
                {"items": [{"src_key": "old_key_1"}], "firstKey": "old_key_1", "firstSrc": "https://cdn/1?sig=B"},
                {"items": [{"src_key": "new_key_2"}], "firstKey": "new_key_2", "firstSrc": "https://cdn/2?sig=A"},
            ])
            texts = iter([
                "Minimalist desk frame, Zero camera cuts, zero readable text",
                "Minimalist desk frame, Zero camera cuts, zero readable text",
                "생성 중 40%",
                "완료됨",
            ])
            with patch.object(flow_automator, "ensure_grid_view"), patch.object(
                flow_automator, "scroll_grid_top"
            ), patch.object(flow_automator, "clear_attachments"), patch.object(
                flow_automator, "ensure_image_settings"
            ), patch.object(
                flow_automator, "read_dom", return_value={"elements": [{"role": "textbox", "name": "무엇을 만들고 싶으신가요?", "ref": "tb1"}, {"role": "button", "name": "생성 시작", "ref": "btn1"}]}
            ), patch.object(
                flow_automator, "ugot", return_value={}
            ), patch.object(
                flow_automator, "click_ref"
            ), patch.object(
                flow_automator, "evaluate_js", return_value=0
            ), patch.object(
                flow_automator, "read_text", side_effect=lambda _t: next(texts)
            ), patch.object(
                flow_automator, "get_media_state", side_effect=lambda _t: next(media_states)
            ), patch.object(
                flow_automator,
                "download_top_lightbox",
                return_value={
                    "file": "refs/R_T.png",
                    "src_key": "new_key_2",
                    "width": 768,
                    "height": 1376,
                    "bytes": 12345,
                    "title": "R_T",
                },
            ) as m_dl, patch.object(
                flow_automator.time, "sleep"
            ):
                res = flow_automator.generate_ref(
                    123,
                    td,
                    {
                        "id": "R_T",
                        "file": "refs/R_T.png",
                        "prompt": "Minimalist desk frame, Zero camera cuts, zero readable text",
                        "settings": {"aspect_ratio": "9:16"},
                    },
                )
            self.assertEqual(res["src_key"], "new_key_2")
            self.assertEqual(m_dl.call_count, 1)

    def test_ugot_retries_document_changed_error(self) -> None:
        resp_err = type("P", (), {"returncode": 1, "stdout": "", "stderr": "document_changed: page navigated"})()
        resp_ok = type("P", (), {"returncode": 0, "stdout": json.dumps({"structuredContent": {"ok": True}}), "stderr": ""})()
        with patch.object(flow_automator.subprocess, "run", side_effect=[resp_err, resp_ok]) as m_run, patch.object(
            flow_automator.time, "sleep"
        ) as m_sleep:
            out = flow_automator.ugot("read_page", {"tabId": 1})
        self.assertTrue(out["ok"])
        self.assertEqual(m_run.call_count, 2)
        m_sleep.assert_called_once_with(1.0)


class TestGateACrossCampaignReskin(unittest.TestCase):
    def test_detects_reskin_across_campaigns_and_passes_distinct_genres(self) -> None:
        sponge_reskin = {
            "project_id": "sponge-A",
            "a_genre_archetype": "mock_documentary",
            "hook_window_sec": 11.0,
            "captions": [
                {"start": 0.0, "end": 5.0, "text": "**[속보]** 전국 원룸 욕실 해수면 상승"},
                {"start": 5.5, "end": 11.0, "text": "단 한 집만 사막처럼 말라 있었다"},
            ],
            "bgm_timeline": [{"stems": ["/loops/Caution Synth.caf"]}],
            "sfx_events": [{"file": "/sfx/Turntable Scratch 2.caf"}],
        }
        piev_reskin = {
            "project_id": "piev-A",
            "a_genre_archetype": "mock_documentary",
            "hook_window_sec": 10.0,
            "captions": [
                {"start": 0.0, "end": 5.0, "text": "**[속보]** 한반도 중력 90도 기울어졌다"},
                {"start": 5.2, "end": 10.0, "text": "단 한 집만 평온했습니다"},
            ],
            "bgm_timeline": [{"stems": ["/loops/Caution Synth.caf"]}],
            "sfx_events": [{"file": "/sfx/Turntable Scratch 2.caf"}],
        }
        errs = ad_gate_a_lint.validate_no_campaign_reskin([sponge_reskin, piev_reskin])
        self.assertGreaterEqual(len(errs), 3, errs)

        noir_sponge = {
            "project_id": "sponge-noir",
            "a_genre_archetype": "noir_interrogation",
            "hook_window_sec": 10.0,
            "captions": [
                {"start": 0.0, "end": 5.0, "text": "형사님, 현장에 물 흔적이 사라졌습니다"},
            ],
            "bgm_timeline": [{"stems": ["/loops/Noir Upright Bass.caf"]}],
            "sfx_events": [{"file": "/sfx/Desk Slam.caf"}],
        }
        romance_piev = {
            "project_id": "piev-melodrama",
            "a_genre_archetype": "romance_breakup",
            "hook_window_sec": 10.0,
            "captions": [
                {"start": 0.0, "end": 5.0, "text": "오빠가 식탁을 90도로 엎던 밤"},
            ],
            "bgm_timeline": [{"stems": ["/loops/Acoustic Heartbreak.caf"]}],
            "sfx_events": [{"file": "/sfx/Violin Scrape.caf"}],
        }
        self.assertEqual(ad_gate_a_lint.validate_no_campaign_reskin([noir_sponge, romance_piev]), [])


class TestFlowAutomatorSpeedAndFocus(unittest.TestCase):
    def test_poll_wave_snapshot_uses_single_eval_and_parses_keys(self) -> None:
        fake_eval = {
            "text": "생성 중 45%\nnormal line",
            "policy_count": 1,
            "still_running": True,
            "srcs": [
                "https://flow.google.com/asb/KEY_ONE=s512-rw",
                "https://flow.google.com/asb/KEY_TWO=s512-rw",
                "https://flow.google.com/asb/KEY_ONE=s512-rw",
            ],
        }
        with patch.object(flow_automator, "evaluate_js", return_value=fake_eval) as m_eval:
            snap = flow_automator.poll_wave_snapshot(999, max_items=16)
        self.assertEqual(m_eval.call_count, 1)
        self.assertTrue(snap["still_running"])
        self.assertEqual(snap["policy_count"], 1)
        self.assertEqual(snap["keys"], ["KEY_ONE", "KEY_TWO"])

    def test_submit_reuses_settings_cache_and_calls_tab_focus(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            cfg = {
                "mode": "ingredients",
                "ar": "9:16",
                "res": "720p",
                "duration": 5,
                "model": "Omni 1.2 Flash",
                "est_credits": 15,
                "prompt": "One crisp 9:16 shot with zero readable text.",
                "rel_out": "clips/A1.mp4",
            }
            unit = {"id": "A1", "reference_ids": []}
            cache = {
                "sig": ("ingredients", "9:16", "720p", 5, "Omni 1.2 Flash"),
                "cost": 15,
            }
            dom = {
                "elements": [
                    {"role": "textbox", "name": "무엇을 만들고 싶으신가요?", "ref": "tb1"},
                    {"role": "button", "name": "생성 시작", "ref": "btn1"},
                ]
            }
            eval_returns = [
                "동영상 · 720p · 5초 crop_9_16 x1",
                "동영상 · 720p · 5초 crop_9_16 x1",
                {"hasOptions": False, "promptText": cfg["prompt"]},
                0,
            ]
            with patch.object(flow_automator, "ensure_tab_active") as m_focus, patch.object(
                flow_automator, "ensure_grid_view"
            ), patch.object(flow_automator, "clear_attachments"), patch.object(
                flow_automator, "attach_assets"
            ), patch.object(
                flow_automator, "ensure_video_settings_and_read_cost"
            ) as m_settings, patch.object(
                flow_automator, "evaluate_js", side_effect=eval_returns
            ), patch.object(
                flow_automator, "read_dom", return_value=dom
            ), patch.object(
                flow_automator, "ugot", return_value={}
            ), patch.object(
                flow_automator, "click_ref"
            ), patch.object(
                flow_automator.time, "sleep"
            ):
                cost, _ = flow_automator._submit_video_unit_to_flow(
                    123, td, unit, cfg, {}, 50, settings_cache=cache
                )
            self.assertEqual(cost, 15)
            self.assertEqual(m_settings.call_count, 0)
            m_focus.assert_called_once_with(123)


if __name__ == "__main__":
    unittest.main()
