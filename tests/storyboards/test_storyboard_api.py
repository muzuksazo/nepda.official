"""FR-004 · On-demand storyboard generation API tests."""

import json
import unittest
from pathlib import Path

from app.config import Settings
from app.projects_router import _default_storyboard_generator
from app.storage import LocalStorageBackend
from tests.support.production import _make_sample_mp4_bytes
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

    def test_track_a_storyboard_never_leaks_raw_segment_ids(self) -> None:
        with temporary_directory() as td:
            root = Path(td)
            tpl_dir = root / "tpl_a"
            tpl_dir.mkdir(parents=True, exist_ok=True)
            tpl_mp4 = tpl_dir / "a_domino.mp4"
            tpl_mp4.write_bytes(_make_sample_mp4_bytes(duration=4.0, w=540, h=960))
            (tpl_dir / "manifest.json").write_text(
                json.dumps(
                    [
                        {
                            "id": "a_domino_test",
                            "filename": "a_domino.mp4",
                            "duration_sec": 4.0,
                            "default_hook_captions": [
                                "1cm 도미노가 시작됩니다",
                                "점점 거대해지는 연쇄 반응",
                                "마지막 조각이 쓰러지는 순간",
                            ],
                        }
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            settings = Settings(
                _env_file=None,
                work_root=str(root / "work"),
                output_dir=str(root / "outputs"),
                db_path=str(root / "napda.db"),
                track_a_template_dir=str(tpl_dir),
            )
            storage = LocalStorageBackend(root / "objects")
            gen = _default_storyboard_generator(settings, storage)
            project = {"project_id": "prj_sb_a", "user_id": "u1"}
            scenario = {
                "scenario_id": "scn_A_test",
                "type": "A",
                "ad_spec": {"track_a_template_id": "a_domino_test"},
                "beats": [
                    {"order": 1, "role": "video", "caption": "도미노가 시작됩니다", "visual": "도미노 1"},
                    {"order": 2, "role": "video", "caption": "50층 높이로 커집니다", "visual": "도미노 2"},
                    {"order": 3, "role": "silence_gap", "caption": "", "visual": "twist_gap"},
                    {"order": 4, "role": "source", "caption": "", "narration": "", "visual": "payoff_1"},
                ],
            }
            frames = gen(project, scenario, "default")
            self.assertEqual(len(frames), 4)
            for frame in frames:
                self.assertNotIn("payoff_1", frame["caption"])
                self.assertNotIn("twist_gap", frame["caption"])
                self.assertTrue(frame["image_url"].startswith("/v1/media/"))
