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
