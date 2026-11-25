"""FR-009 · Upload validation (100MB/file, 5-90s total, single/multi-clip & guide mismatch warnings)."""

import unittest
from pathlib import Path

from tests.support.projects_api import build_test_client, login_client
from tests.support.tempdirs import temporary_directory


class TestUploadValidationAPI(unittest.TestCase):
    def test_enforces_size_and_duration_bounds_and_emits_aspect_warnings(self) -> None:
        with temporary_directory() as td:
            client = build_test_client(Path(td))
            login_client(client)

            pid = client.post(
                "/v1/projects",
                json={
                    "product": {
                        "name": "스텐 양념통",
                        "category": "kitchen",
                        "verified_facts": ["밀폐 실리콘 패킹"],
                    },
                    "selected_types": ["C"],
                },
            ).json()["project_id"]

            # Over 100MB -> 400
            too_big = client.post(
                f"/v1/projects/{pid}/uploads/complete",
                json={
                    "clips": [
                        {
                            "shot_no": 1,
                            "object_key": "uploads/big.mp4",
                            "file_size_bytes": 101 * 1024 * 1024,
                            "duration_sec": 12.0,
                            "width": 1080,
                            "height": 1920,
                        }
                    ]
                },
            )
            self.assertEqual(too_big.status_code, 400)
            self.assertEqual(too_big.json()["detail"]["error"]["code"], "INVALID_UPLOAD_LIMIT")

            # Too short (<5s) -> 400
            too_short = client.post(
                f"/v1/projects/{pid}/uploads/complete",
                json={
                    "clips": [
                        {
                            "shot_no": 1,
                            "object_key": "uploads/short.mp4",
                            "file_size_bytes": 1024,
                            "duration_sec": 3.5,
                            "width": 1080,
                            "height": 1920,
                        }
                    ]
                },
            )
            self.assertEqual(too_short.status_code, 400)

            # Multi-clip 16:9 horizontal -> non-blocking ASPECT_16_9 warning
            ok_multi = client.post(
                f"/v1/projects/{pid}/uploads/complete",
                json={
                    "clips": [
                        {
                            "shot_no": 1,
                            "object_key": "uploads/cut1.mp4",
                            "file_size_bytes": 4_000_000,
                            "duration_sec": 6.0,
                            "width": 1920,
                            "height": 1080,
                        },
                        {
                            "shot_no": 2,
                            "object_key": "uploads/cut2.mp4",
                            "file_size_bytes": 5_000_000,
                            "duration_sec": 8.0,
                            "width": 1080,
                            "height": 1920,
                        },
                    ]
                },
            )
            self.assertEqual(ok_multi.status_code, 200, ok_multi.text)
            res = ok_multi.json()
            self.assertEqual(res["upload_status"], "WARNING")
            self.assertEqual(res["total_duration_sec"], 14.0)
            self.assertEqual(res["warnings"][0]["code"], "ASPECT_16_9")
            self.assertEqual(res["metadata"][0]["recommended_framing"], "blur-bleed")
