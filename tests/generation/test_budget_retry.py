"""Offline regression coverage organized by PRD area."""
from tests.support.production import (
    BudgetExceededError,
    GenAIMediaProvider,
    GenAIMediaProviderCase,
    Path,
    Settings,
    SimpleNamespace,
    _FakeInteractions,
    _FakeModels,
    execute_jobs_file,
    json,
    tempfile,
)
from tests.support.tempdirs import temporary_directory


class TestGenAIMediaProvider(GenAIMediaProviderCase):
    def test_execute_jobs_budget_cap_and_surgical_retry(self) -> None:
        with temporary_directory() as td:
            proj = Path(td)
            jobs_file = proj / "05_jobs.json"
            jobs_payload = {
                "project_id": "test-jobs",
                "aspect_ratio": "9:16",
                "resolution": "720p",
                "anchors": [],
                "references": [
                    {
                        "id": "R_A1",
                        "file": "refs/R_A1.png",
                        "prompt": "One dark noir studio desk, zero readable text.",
                        "settings": {"aspect_ratio": "9:16"},
                    }
                ],
                "units": [
                    {
                        "id": "G_A1",
                        "reference_ids": ["R_A1"],
                        "settings": {"aspect_ratio": "9:16", "resolution": "720p", "duration_sec": 5},
                        "est_credits": 15,
                        "outputs": ["clips/G_A1_t1.mp4"],
                        "prompt": "Smooth slow push-in, zero readable text.",
                    },
                    {
                        "id": "G_A2",
                        "reference_ids": ["R_A1"],
                        "settings": {"aspect_ratio": "9:16", "resolution": "720p", "duration_sec": 5},
                        "est_credits": 15,
                        "outputs": ["clips/G_A2_t1.mp4"],
                        "prompt": "Static medium framing, zero readable text.",
                    },
                ],
            }
            jobs_file.write_text(json.dumps(jobs_payload), encoding="utf-8")

            fake_client = SimpleNamespace(
                interactions=_FakeInteractions(png_bytes=self.png_bytes, mp4_bytes=self.mp4_bytes),
                models=_FakeModels(),
            )
            settings = Settings(
                _env_file=None,
                gemini_api_key="dummy",
                google_genai_use_vertexai=False,
                poll_interval_sec=0.0,
                video_timeout_sec=10.0,
            )
            provider = GenAIMediaProvider(settings, client=fake_client)

            # Budget cap triggers BEFORE any paid video calls
            with self.assertRaises(BudgetExceededError):
                execute_jobs_file(jobs_file, proj, provider, max_credits=20)
            video_calls = [
                c for c in fake_client.interactions.created if c.get("response_format", {}).get("type") == "video"
            ]
            self.assertEqual(len(video_calls), 0)

            # Now run within budget
            rep = execute_jobs_file(jobs_file, proj, provider, concurrency=2, max_credits=50)
            self.assertEqual(rep["total_est_credits"], 30)
            self.assertEqual(len(rep["units"]), 2)
            self.assertTrue((proj / "clips" / "G_A1_t1.mp4").exists())
            self.assertTrue((proj / "generation_report.json").exists())

            # Surgical retry of G_A2 only
            rep_retry = execute_jobs_file(
                jobs_file, proj, provider, skip_existing=False, only_unit_ids=["G_A2"]
            )
            self.assertEqual([u["id"] for u in rep_retry["units"]], ["G_A2"])
