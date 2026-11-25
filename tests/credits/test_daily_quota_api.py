"""FR-006 · Pre-run credit estimate & daily 3-render free beta limit tests."""

import unittest
from pathlib import Path

from tests.support.projects_api import build_test_client, login_client
from tests.support.tempdirs import temporary_directory


class TestDailyQuotaAPI(unittest.TestCase):
    def test_estimate_and_daily_three_render_limit(self) -> None:
        with temporary_directory() as td:
            client = build_test_client(Path(td), daily_render_limit=3)
            login_client(client, "quota-user:quota@example.com")

            pid = client.post(
                "/v1/projects",
                json={
                    "product": {
                        "name": "미니 라벨 프린터",
                        "category": "stationery",
                        "verified_facts": ["감열식 잉크 프리 인쇄"],
                    },
                    "selected_types": ["A"],
                    "flow_mode": "skip_drafts",
                },
            ).json()["project_id"]

            est = client.post(f"/v1/projects/{pid}/estimate", json={"resolution": "720p"})
            self.assertEqual(est.status_code, 200, est.text)
            self.assertEqual(est.json()["total_estimated_credits"], 32)
            self.assertEqual(est.json()["quota"]["daily_limit"], 3)
            self.assertEqual(est.json()["quota"]["remaining_today"], 3)

            client.post(
                f"/v1/projects/{pid}/uploads/complete",
                json={
                    "clips": [
                        {
                            "shot_no": 1,
                            "object_key": "uploads/raw.mp4",
                            "file_size_bytes": 1_000_000,
                            "duration_sec": 12.0,
                            "width": 1080,
                            "height": 1920,
                        }
                    ]
                },
            )

            # Submit 3 renders (allowed) -> 4th render returns 429 DAILY_QUOTA_EXCEEDED
            for expected_used in (1, 2, 3):
                r = client.post(
                    f"/v1/projects/{pid}/renders",
                    json={"skip_drafts": True, "selected_type": "A", "dry_run": True},
                )
                self.assertEqual(r.status_code, 202, r.text)
                self.assertEqual(r.json()["quota"]["used_today"], expected_used)

            blocked = client.post(
                f"/v1/projects/{pid}/renders",
                json={"skip_drafts": True, "selected_type": "A", "dry_run": True},
            )
            self.assertEqual(blocked.status_code, 429)
            self.assertEqual(blocked.json()["detail"]["error"]["code"], "DAILY_QUOTA_EXCEEDED")
