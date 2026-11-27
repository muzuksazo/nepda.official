"""Offline regression coverage organized by PRD area."""
from tests.support.production import (
    Path,
    ProductionPipelineAndAPICase,
    Settings,
    create_app,
    json,
    tempfile,
    time,
)
from tests.support.tempdirs import temporary_directory


class TestProductionPipelineAndAPI(ProductionPipelineAndAPICase):
    def test_fastapi_endpoints_and_bearer_auth(self) -> None:
        from fastapi.testclient import TestClient

        with temporary_directory() as td:
            root = Path(td)
            settings = Settings(
                _env_file=None,
                gemini_api_key="dummy",
                api_bearer_token="secret-token-123",
                work_root=str(root / "work"),
                db_path=str(root / "jobs.db"),
            )
            app = create_app(settings=settings)
            client = TestClient(app)

            h = client.get("/health")
            self.assertEqual(h.status_code, 200)
            self.assertEqual(h.json()["status"], "ok")
            self.assertEqual(h.json()["auth_mode"], "ai_studio")

            # Auth guard blocks unauthenticated requests
            unauth = client.get("/v1/jobs")
            self.assertEqual(unauth.status_code, 401)

            in_dir = root / "inputs"
            in_dir.mkdir()
            src, facts, spec = self._write_valid_campaign_inputs(in_dir, a_genre="romance_breakup")

            headers = {"Authorization": "Bearer secret-token-123"}
            post = client.post(
                "/v1/jobs",
                headers=headers,
                json={
                    "campaign_id": "api-dry-run",
                    "source_video": str(src),
                    "facts_path": str(facts),
                    "spec_path": str(spec),
                    "dry_run": True,
                },
            )
            self.assertEqual(post.status_code, 202, post.text)
            jid = post.json()["job_id"]

            final_job = None
            for _ in range(80):
                g = client.get(f"/v1/jobs/{jid}", headers=headers)
                self.assertEqual(g.status_code, 200)
                final_job = g.json()
                if final_job["status"] in {"DRY_RUN_READY", "QC_READY", "FAILED"}:
                    break
                time.sleep(0.1)

            self.assertIsNotNone(final_job)
            self.assertEqual(final_job["status"], "DRY_RUN_READY", final_job)
            self.assertTrue(final_job["lint"]["passed"])

            # Inline spec_data + facts_markdown handoff (from planner-ai-sdk)
            inline_spec = json.loads(spec.read_text(encoding="utf-8"))
            inline_spec["project_id"] = "ai-sdk-inline-camp"
            inline_spec["a_genre_archetype"] = "courtroom_trial"
            post_inline = client.post(
                "/v1/jobs",
                headers=headers,
                json={
                    "campaign_id": "ai-sdk-inline-camp",
                    "source_video": str(src),
                    "facts_markdown": facts.read_text(encoding="utf-8"),
                    "spec_data": inline_spec,
                    "dry_run": True,
                },
            )
            self.assertEqual(post_inline.status_code, 202, post_inline.text)
            inline_jid = post_inline.json()["job_id"]
            inline_job = None
            for _ in range(80):
                g2 = client.get(f"/v1/jobs/{inline_jid}", headers=headers)
                inline_job = g2.json()
                if inline_job["status"] in {"DRY_RUN_READY", "QC_READY", "FAILED"}:
                    break
                time.sleep(0.1)
            self.assertIsNotNone(inline_job)
            self.assertEqual(inline_job["status"], "DRY_RUN_READY", inline_job)
            self.assertTrue(inline_job["lint"]["passed"])
