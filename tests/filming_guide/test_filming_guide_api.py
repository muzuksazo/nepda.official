"""FR-007 · Filming guide creation, track-aware tips & target_body_duration formula tests."""

import unittest
from pathlib import Path

from app.filming_guide_service import build_filming_guide, compute_target_body_duration
from tests.support.projects_api import build_test_client, login_client
from tests.support.tempdirs import temporary_directory


class TestFilmingGuideAPI(unittest.TestCase):
    def test_selects_single_scenario_and_builds_shot_guide(self) -> None:
        with temporary_directory() as td:
            client = build_test_client(Path(td))
            login_client(client)

            pid = client.post(
                "/v1/projects",
                json={
                    "product": {
                        "name": "자석 케이블 정리기",
                        "category": "living",
                        "verified_facts": ["강력 자석 부착", "원핸드 탈착"],
                    },
                    "selected_types": ["A", "B"],
                },
            ).json()["project_id"]

            scns = client.post(f"/v1/projects/{pid}/scenarios", json={}).json()["scenarios"]
            chosen_sid = scns[0]["scenario_id"]

            fg = client.post(
                f"/v1/projects/{pid}/filming-guide",
                json={"scenario_id": chosen_sid},
            )
            self.assertEqual(fg.status_code, 200, fg.text)
            body = fg.json()
            self.assertEqual(body["status"], "GUIDE_READY")
            self.assertEqual(body["selected_scenario_id"], chosen_sid)
            self.assertGreaterEqual(len(body["shots"]), 3)
            # fake_scenario_generator emits beats totaling 15.0s -> 30 - 15 = 15.0s
            self.assertAlmostEqual(body["target_body_duration_sec"], 15.0, places=1)
            self.assertAlmostEqual(sum(s["duration_sec"] for s in body["shots"]), 15.0, places=1)

    def test_target_body_duration_formula_and_track_metadata(self) -> None:
        project = {
            "project_id": "prj_test",
            "product": {
                "name": "피에브 에어워셔",
                "category": "living",
                "verified_facts": ["피톤치드 분해 탈취", "350ml 대용량", "전용 리필 가능"],
            },
        }

        # Ignore unreliable body_duration_sec=0; 12s hook -> 18s body
        scn_c = {
            "scenario_id": "scn_C_1",
            "type": "C",
            "hook_title": "욕실 냄새 직격",
            "hook_duration_sec": 12.0,
            "body_duration_sec": 0.0,
            "beats": [
                {"order": 1, "duration_sec": 4.0, "visual": "욕실 문제"},
                {"order": 2, "duration_sec": 8.0, "visual": "실물 분사"},
            ],
            "ad_spec": {
                "claim_ids": ["F02", "F01"],
                "cta": {"type": "comment_engagement", "text": "냄새 고민 댓글로 남겨주세요"},
            },
        }
        guide_c = build_filming_guide(project, scn_c)
        self.assertEqual(guide_c["target_body_duration_sec"], 18.0)
        self.assertAlmostEqual(sum(s["duration_sec"] for s in guide_c["shots"]), 18.0, places=1)
        self.assertEqual(guide_c["shots"][0]["fact_ref"], "F02")
        self.assertIn("댓글", guide_c["shots"][-1]["framing_tip"])

        # Track B 20s hook -> clamp to min 10.0s body
        scn_b = {
            "scenario_id": "scn_B_1",
            "type": "B",
            "hook_title": "자연 원리",
            "hook_duration_sec": 20.0,
            "body_duration_sec": 18.0,
            "beats": [
                {"order": 1, "duration_sec": 10.0, "visual": "원리"},
                {"order": 2, "duration_sec": 10.0, "visual": "브리지"},
            ],
            "ad_spec": {"product_first_mention_beat": 3},
        }
        self.assertEqual(compute_target_body_duration(scn_b), 10.0)
        guide_b = build_filming_guide(project, scn_b)
        self.assertEqual(guide_b["target_body_duration_sec"], 10.0)
        self.assertIn("장면 3", guide_b["shots"][0]["framing_tip"])

        # 22s hook -> still minimum 10.0s
        scn_long = {"beats": [{"order": 1, "duration_sec": 22.0}]}
        self.assertEqual(compute_target_body_duration(scn_long), 10.0)
