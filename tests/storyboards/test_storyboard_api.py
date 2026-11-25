"""FR-004 · On-demand storyboard generation API tests."""

import unittest
from pathlib import Path

from tests.support.projects_api import build_test_client, login_client
from tests.support.tempdirs import temporary_directory


class TestStoryboardAPI(unittest.TestCase):
    def test_generate_storyboard_attaches_frames_to_selected_scenario(self) -> None:
        with temporary_directory() as td:
            client = build_test_client(Path(td))
            login_client(client)

            pid = client.post(
                "/v1/projects",
                json={
                    "product": {
                        "name": "다꾸 스탬프 세트",
                        "category": "stationery",
                        "verified_facts": ["원터치 자동 잉크 리필"],
                    },
                    "selected_types": ["B"],
                },
            ).json()["project_id"]

            scns = client.post(f"/v1/projects/{pid}/scenarios", json={}).json()["scenarios"]
            sid = scns[0]["scenario_id"]

            sb = client.post(
                f"/v1/projects/{pid}/scenarios/{sid}/storyboard",
                json={"visual_style": "default"},
            )
            self.assertEqual(sb.status_code, 200, sb.text)
            payload = sb.json()
            self.assertEqual(payload["status"], "STORYBOARD_READY")
            self.assertEqual(len(payload["frames"]), 2)

            detail = client.get(f"/v1/projects/{pid}").json()
            self.assertEqual(len(detail["scenarios"][0]["storyboard_frames"]), 2)
