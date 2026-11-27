"""FR-002·003·005 · Hook types catalog and scenario generation API tests."""

import unittest
from pathlib import Path

from app.projects_router import _build_beats_from_spec, _safe_beat_caption
from tests.support.projects_api import build_test_client, login_client
from tests.support.tempdirs import temporary_directory


class TestHookTypesAndScenariosAPI(unittest.TestCase):
    def test_hook_types_catalog_and_scenario_generation(self) -> None:
        with temporary_directory() as td:
            client = build_test_client(Path(td))
            login_client(client)

            ht = client.get("/v1/hook-types")
            self.assertEqual(ht.status_code, 200)
            types_list = ht.json()["types"]
            self.assertEqual([t["type"] for t in types_list], ["A", "B", "C"])

            proj = client.post(
                "/v1/projects",
                json={
                    "product": {
                        "name": "주방용 실리콘 수세미",
                        "category": "kitchen",
                        "verified_facts": ["끓는 물 소독 가능"],
                    },
                    "selected_types": ["A", "C"],
                },
            ).json()

            scn_resp = client.post(
                f"/v1/projects/{proj['project_id']}/scenarios",
                json={"provider": "anthropic"},
            )
            self.assertEqual(scn_resp.status_code, 200, scn_resp.text)
            data = scn_resp.json()
            self.assertEqual(data["status"], "SCENARIOS_READY")
            self.assertEqual([s["type"] for s in data["scenarios"]], ["A", "C"])

    def test_build_beats_skips_silence_gap_computes_source_duration_and_hides_internal_ids(self) -> None:
        spec = {
            "timeline": [
                {"id": "hook_1", "type": "video", "duration": 4.9, "flow_ref_prompt": "3D 도미노 시작"},
                {"id": "hook_2", "type": "video", "duration": 4.98, "flow_ref_prompt": "50층 도미노 낙하"},
                {"id": "twist_gap", "type": "silence_gap", "duration": 0.25},
                {"id": "payoff_1", "type": "source", "src_start": 0.0, "src_end": 6.5},
            ],
            "captions": [
                {"start": 0.0, "end": 4.8, "text": "1cm 도미노를 2배씩 키우면"},
                {"start": 4.9, "end": 9.8, "text": "마지막 조각은 아파트 50층 높이"},
                {"start": 10.2, "end": 16.5, "text": "물기 즉시 흡수, 댓글로 링크 받기"},
            ],
        }
        beats = _build_beats_from_spec(spec, product_name="초흡수 PVA 물걸레 스펀지")
        self.assertEqual(len(beats), 4)

        # silence_gap must NOT consume spoken captions or leak twist_gap
        gap_beat = beats[2]
        self.assertEqual(gap_beat["role"], "silence_gap")
        self.assertEqual(gap_beat["duration_sec"], 0.25)
        self.assertEqual(gap_beat["caption"], "")
        self.assertEqual(gap_beat["narration"], "")
        self.assertNotIn("twist_gap", gap_beat["visual"])

        # payoff_1 gets the 3rd spoken caption, src_end - src_start = 6.5s, and never leaks payoff_1
        payoff_beat = beats[3]
        self.assertEqual(payoff_beat["role"], "source")
        self.assertAlmostEqual(payoff_beat["duration_sec"], 6.5, places=2)
        self.assertEqual(payoff_beat["caption"], "물기 즉시 흡수, 댓글로 링크 받기")
        self.assertEqual(payoff_beat["narration"], "물기 즉시 흡수, 댓글로 링크 받기")
        self.assertNotIn("payoff_1", payoff_beat["visual"])

        # _safe_beat_caption rejects raw internal IDs even from legacy scenarios
        self.assertEqual(_safe_beat_caption({"caption": "", "narration": "", "visual": "payoff_1"}), "")
        self.assertEqual(_safe_beat_caption({"caption": "", "narration": "", "visual": "twist_gap"}), "")
        self.assertEqual(
            _safe_beat_caption({"caption": "", "narration": "", "visual": "물기 즉시 흡수 시연"}),
            "물기 즉시 흡수 시연",
        )
