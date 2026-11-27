"""FR-006 · Pre-run credit estimate, daily 3-render free beta limit & paid render credit enforcement tests."""

import time
import unittest
from pathlib import Path

from tests.support.production import _make_sample_mp4_bytes
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

    def test_paid_render_enforces_credits_with_402_and_refunds_on_failure(self) -> None:
        with temporary_directory() as td:
            root = Path(td)
            client = build_test_client(root, daily_render_limit=5)
            login_client(client, "credit-user:credit@example.com")

            pid = client.post(
                "/v1/projects",
                json={
                    "product": {
                        "name": "초흡수 PVA 물걸레 스펀지",
                        "category": "living",
                        "verified_facts": ["물기 즉시 흡수"],
                    },
                    "selected_types": ["C"],
                    "flow_mode": "skip_drafts",
                },
            ).json()["project_id"]

            src_mp4 = root / "sample.mp4"
            src_mp4.write_bytes(_make_sample_mp4_bytes(duration=6.0, w=1080, h=1920))
            client.post(
                f"/v1/projects/{pid}/uploads/complete",
                json={
                    "clips": [
                        {
                            "shot_no": 1,
                            "object_key": "uploads/sample.mp4",
                            "local_path": str(src_mp4),
                        }
                    ]
                },
            )

            # 1) 0 credits + paid render -> 402 INSUFFICIENT_CREDITS (does NOT render for free)
            rejected = client.post(
                f"/v1/projects/{pid}/renders",
                json={"skip_drafts": True, "selected_type": "C", "dry_run": False},
            )
            self.assertEqual(rejected.status_code, 402, rejected.text)
            err = rejected.json()["detail"]["error"]
            self.assertEqual(err["code"], "INSUFFICIENT_CREDITS")
            self.assertEqual(err["details"]["required_credits"], 12)
            self.assertEqual(err["details"]["available_credits"], 0)
            self.assertEqual(err["details"]["shortfall"], 12)
            # Quota was NOT consumed on 402 rejection
            self.assertEqual(client.get(f"/v1/projects/{pid}").json()["quota"]["used_today"], 0)

            # 2) dry_run=True still succeeds at 0 credits with deducted_credits == 0
            dry_resp = client.post(
                f"/v1/projects/{pid}/renders",
                json={"skip_drafts": True, "selected_type": "C", "dry_run": True},
            )
            self.assertEqual(dry_resp.status_code, 202, dry_resp.text)
            self.assertEqual(dry_resp.json()["deducted_credits"], 0)
            dry_jid = dry_resp.json()["job_id"]
            for _ in range(50):
                j = client.get(f"/v1/jobs/{dry_jid}").json()
                if j["status"] in {"DRY_RUN_READY", "QC_READY", "FAILED"}:
                    break
                time.sleep(0.05)
            dry_job = client.get(f"/v1/jobs/{dry_jid}").json()
            self.assertEqual(dry_job["deducted_credits"], 0)
            self.assertEqual(dry_job["refunded_credits"], 0)

            # 3) Seed 20 credits -> paid render deducts 12; simulated failure refunds 12 & records refunded_credits
            project_store = client.app.state.project_store  # type: ignore[attr-defined]
            pipeline = client.app.state.pipeline  # type: ignore[attr-defined]
            project_store.refund_wallet_credits("credit-user", 20)
            self.assertEqual(client.get("/v1/billing/wallet").json()["credits"], 20)

            def _boom(*_args, **_kwargs):
                raise RuntimeError("simulated render failure")

            pipeline.run_campaign = _boom  # type: ignore[method-assign]
            paid_resp = client.post(
                f"/v1/projects/{pid}/renders",
                json={"skip_drafts": True, "selected_type": "C", "dry_run": False},
            )
            self.assertEqual(paid_resp.status_code, 202, paid_resp.text)
            self.assertEqual(paid_resp.json()["deducted_credits"], 12)
            paid_jid = paid_resp.json()["job_id"]

            for _ in range(50):
                detail = client.get(f"/v1/projects/{pid}").json()
                if detail["latest_job"] and detail["latest_job"]["status"] == "FAILED":
                    break
                time.sleep(0.05)

            detail = client.get(f"/v1/projects/{pid}").json()
            self.assertEqual(detail["latest_job"]["id"], paid_jid)
            self.assertEqual(detail["latest_job"]["status"], "FAILED")
            self.assertEqual(detail["latest_job"]["deducted_credits"], 12)
            self.assertEqual(detail["latest_job"]["refunded_credits"], 12)
            # Wallet refunded back to 20
            self.assertEqual(client.get("/v1/billing/wallet").json()["credits"], 20)
