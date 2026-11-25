"""Offline regression coverage organized by PRD area."""
from tests.support.media_tools import (
    GateACrossCampaignReskinCase,
    GateAOrthogonalGuardCase,
    ad_gate_a_lint,
    tempfile,
)
from tests.support.tempdirs import temporary_directory


class TestGateAOrthogonalGuard(GateAOrthogonalGuardCase):
    def test_gate_a_blocks_c_disguised_a_and_b_and_accepts_orthogonal(self) -> None:
        with temporary_directory() as td:
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




class TestGateACrossCampaignReskin(GateACrossCampaignReskinCase):
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


class TestGateAPrincipleAbstractionAndCategoryTaboo(GateAOrthogonalGuardCase):
    def test_accepts_brainrot_mechanisms_when_double_zero_holds(self) -> None:
        with temporary_directory() as td:
            fp = self._base_facts(td)
            for mech in ("brainrot_hypnosis", "deadpan_rhythmic_loop", "sensory_sync_loop"):
                spec = self._base_spec(
                    td,
                    "A_bgrade_reversal",
                    [
                        {"start": 0.0, "end": 4.5, "text": "359도에서 절대 안 멈추는 고리", "pop_badge": "수렴 카운트"},
                        {"start": 4.5, "end": 8.9, "text": "0.1도 남기고 갑자기 정적"},
                        {"start": 9.3, "end": 16.0, "text": "천 원 대형 블록 소분 스펀지"},
                    ],
                    taboo=["스펀지"],
                )
                spec["a_genre_archetype"] = mech
                spec["category_taboo_keywords"] = ["욕실", "세면대", "물기", "수건", "bathroom"]
                spec["reference_surface_taboo"] = ["나사", "screw", "소다팝", "soda pop"]
                spec["timeline"][0]["flow_ref_prompt"] = (
                    "Matte clay geometric ring rotating toward an empty center plinth, zero text."
                )
                spec["timeline"][0]["flow_video_prompt"] = (
                    "Continuous slow orbit as the ring approaches alignment, zero readable text."
                )
                checks, _ = ad_gate_a_lint.run_lint(spec, fp)
                self.assertTrue(all(not errs for _, _, errs in checks), (mech, checks))

    def test_blocks_category_clues_and_reference_surface_copies_in_track_a(self) -> None:
        with temporary_directory() as td:
            fp = self._base_facts(td)
            cat_spec = self._base_spec(
                td,
                "A_bgrade_reversal",
                [
                    {"start": 0.0, "end": 4.5, "text": "바닥 물기가 사라졌다", "pop_badge": "욕실 미스터리"},
                    {"start": 9.3, "end": 16.0, "text": "실물 스펀지 정리"},
                ],
                taboo=["스펀지"],
            )
            cat_spec["a_genre_archetype"] = "brainrot_hypnosis"
            cat_spec["category_taboo_keywords"] = ["욕실", "물기", "bathroom"]
            cat_spec["timeline"][0]["flow_ref_prompt"] = "Clay diorama inside a white bathroom vanity, no text."
            cat_checks, _ = ad_gate_a_lint.run_lint(cat_spec, fp)
            cat_c13 = [errs for idx, _, errs in cat_checks if idx == 13][0]
            self.assertGreaterEqual(len(cat_c13), 3, cat_c13)

            surf_spec = self._base_spec(
                td,
                "A_bgrade_reversal",
                [
                    {"start": 0.0, "end": 4.5, "text": "나사 100개가 뺑뺑 도는 중"},
                    {"start": 9.3, "end": 16.0, "text": "실물 스펀지 정리"},
                ],
                taboo=["스펀지"],
            )
            surf_spec["a_genre_archetype"] = "deadpan_rhythmic_loop"
            surf_spec["reference_surface_taboo"] = ["나사", "소다팝", "soda pop"]
            surf_spec["timeline"][1]["flow_video_prompt"] = "Dancing soda pop mascot waving in 3D, no text."
            surf_checks, _ = ad_gate_a_lint.run_lint(surf_spec, fp)
            surf_c13 = [errs for idx, _, errs in surf_checks if idx == 13][0]
            self.assertGreaterEqual(len(surf_c13), 2, surf_c13)

    def test_blocks_late_pre_bridge_product_spoiler_in_track_b(self) -> None:
        with temporary_directory() as td:
            fp = self._base_facts(td)
            spec_b = self._base_spec(
                td,
                "B_info_hook_offset",
                [
                    {"start": 0.0, "end": 4.4, "text": "6억 년 살아남은 동물"},
                    {"start": 4.4, "end": 7.9, "text": "바로 바다 스펀지 해면입니다"},
                    {"start": 7.98, "end": 12.38, "text": "미세한 구멍이 물을 빨아들입니다"},
                    {"start": 12.62, "end": 19.38, "text": "천 원 스펀지 블록 원리입니다"},
                ],
                sim=0.45,
                taboo=["스펀지"],
            )
            spec_b["timeline"][0]["duration"] = 7.90
            spec_b["timeline"][1]["duration"] = 4.48
            spec_b["timeline"][2]["duration"] = 0.24
            spec_b["timeline"][3]["duration"] = 7.00
            spec_b["hook_window_sec"] = 12.38
            checks_late_44, _ = ad_gate_a_lint.run_lint(spec_b, fp)
            c13_44 = [errs for idx, _, errs in checks_late_44 if idx == 13][0]
            self.assertTrue(any("pre" in e or "before bridge" in e for e in c13_44), c13_44)

            spec_b["captions"][1]["text"] = "바로 **해면동물**입니다"
            spec_b["captions"][2] = {"start": 7.98, "end": 12.38, "text": "스펀지 구조로 흡수합니다"}
            checks_late_798, _ = ad_gate_a_lint.run_lint(spec_b, fp)
            c13_798 = [errs for idx, _, errs in checks_late_798 if idx == 13][0]
            self.assertTrue(any("before bridge" in e for e in c13_798), c13_798)
