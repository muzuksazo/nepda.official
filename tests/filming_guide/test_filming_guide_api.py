"""FR-007 · Filming guide creation & single-type lock tests."""

import unittest
from pathlib import Path

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
            self.assertGreater(body["target_body_duration_sec"], 0)
