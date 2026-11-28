"""Tests for per-stage usage telemetry, cost estimation, Admin API auth, and worker capture."""

from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.auth import AuthenticatedUser, issue_session_token  # noqa: E402
from app.config import Settings  # noqa: E402
from app.project_store import ProjectStore  # noqa: E402
from app.server import create_app  # noqa: E402
from app.usage_telemetry import estimate_cost_usd, parse_pricing_overrides, pricing_catalog  # noqa: E402
from hookpipe.body_edit import make_body  # noqa: E402
from hookpipe.workers import _SettingsOverlay, make_scenario_generator, run_worker_c  # noqa: E402
from tests.support.hookpipe import FakeMediaProvider, fake_body_writer, make_video, tools_or_none, worker_scenario  # noqa: E402
from tests.support.tempdirs import temporary_directory  # noqa: E402


class TestUsageTelemetryAndAdmin(unittest.TestCase):
    def test_estimate_cost_usd_models_thinking_cache_and_overrides(self) -> None:
        # Gemini 3.5 Flash: $1.5/1M in, $9.0/1M out (+thinking billed at output rate)
        usd, label = estimate_cost_usd(
            "gemini-3.5-flash",
            input_tokens=100_000,
            output_tokens=20_000,
            thinking_tokens=30_000,
        )
        self.assertEqual(label, "$1.5/$9 / 1M tok")
        # 0.1 * 1.5 + 0.05 * 9 = 0.15 + 0.45 = 0.60
        self.assertAlmostEqual(usd or 0.0, 0.6, places=6)

        # Cache hit is always $0
        usd_cached, label_cached = estimate_cost_usd(
            "gemini-3.5-flash",
            input_tokens=100_000,
            output_tokens=20_000,
            cache_hit=True,
        )
        self.assertEqual(usd_cached, 0.0)
        self.assertEqual(label_cached, "cache_hit ($0)")

        # Built-in media pricing: image, video sec, and Inworld TTS char
        usd_img, label_img = estimate_cost_usd(
            "gemini-nano-banana-2.1",
            media_unit="image",
            media_qty=3.0,
        )
        self.assertAlmostEqual(usd_img or 0.0, 0.1008, places=6)
        self.assertEqual(label_img, "$0.0336 / image")

        usd_vid, label_vid = estimate_cost_usd(
            "gemini-omni-flash-preview",
            media_unit="sec",
            media_qty=12.0,
        )
        self.assertAlmostEqual(usd_vid or 0.0, 1.2, places=6)
        self.assertEqual(label_vid, "$0.1 / sec")

        usd_tts, label_tts = estimate_cost_usd(
            "inworld-tts-2",
            media_unit="char",
            media_qty=1000.0,
        )
        self.assertAlmostEqual(usd_tts or 0.0, 0.025, places=6)
        self.assertEqual(label_tts, "$25 / 1M char")

        # Unknown model still returns None instead of fabricated pricing
        usd_unknown, label_unknown = estimate_cost_usd(
            "unknown-custom-video-model",
            media_unit="sec",
            media_qty=12.0,
        )
        self.assertIsNone(usd_unknown)
        self.assertEqual(label_unknown, "단가 미등록")

        # Pricing overrides JSON supports per-unit media pricing override
        overrides = parse_pricing_overrides(
            json.dumps({"gemini-omni-flash-preview": {"per_unit": 0.05, "unit": "sec"}})
        )
        usd_ov, label_ov = estimate_cost_usd(
            "gemini-omni-flash-preview",
            media_unit="sec",
            media_qty=12.0,
            overrides=overrides,
        )
        self.assertAlmostEqual(usd_ov or 0.0, 0.6, places=6)
        self.assertEqual(label_ov, "$0.05 / sec")

        catalog_by_model = {row["model"]: row for row in pricing_catalog()}
        for expected_model, expected_unit in [
            ("gemini-nano-banana-2.1", "image"),
            ("gemini-omni-flash-preview", "sec"),
            ("inworld-tts-2", "char"),
        ]:
            self.assertIn(expected_model, catalog_by_model)
            self.assertEqual(catalog_by_model[expected_model]["kind"], "media_per_unit")
            self.assertEqual(catalog_by_model[expected_model]["unit"], expected_unit)
            self.assertEqual(catalog_by_model[expected_model]["source"], "builtin")

    def test_admin_auth_and_end_to_end_worker_usage_capture(self) -> None:
        with temporary_directory() as td:
            root = Path(td)
            secret = "test-session-secret-32bytes-minimum"
            settings = Settings(
                _env_file=None,
                gemini_api_key="dummy-key",
                session_secret=secret,
                admin_emails="admin@napda.ai",
                api_bearer_token="adm-secret-token",
                usd_krw_rate=1400.0,
                hook_workers_dir=str(BACKEND / "bridge-dev"),
                work_root=str(root / "work"),
                output_dir=str(root / "outputs"),
                db_path=str(root / "napda.db"),
            )
            store = ProjectStore(settings.db_path)
            admin_user = AuthenticatedUser(user_id="usr_admin", email="admin@napda.ai", name="Admin")
            normal_user = AuthenticatedUser(user_id="usr_norm", email="user@example.com", name="User")
            store.upsert_user(admin_user)
            store.upsert_user(normal_user)

            proj = store.create_project(
                "prj_tel01",
                normal_user.user_id,
                flow_mode="guide_first",
                product={
                    "name": "60분 비주얼 타이머",
                    "category": "stationery",
                    "verified_facts": ["60분형 아날로그 타이머"],
                },
                selected_types=["C"],
            )
            pid = proj["project_id"]

            # Simulate scenario worker C returning steps[] telemetry
            c_generate = SimpleNamespace(
                generate_scenarios=lambda data, **_kw: {
                    "response": {
                        "project_id": data["project_id"],
                        "status": "SCENARIOS_READY",
                        "round": 1,
                        "scenarios": [worker_scenario("C", "sc_tel_c")],
                    },
                    "checks": [{"errors": []}],
                    "steps": [
                        {
                            "step": "scenarios",
                            "model": "claude-sonnet-5-5",
                            "inputTokens": 5000,
                            "outputTokens": 1200,
                            "costUsd": 0.022,
                            "ms": 840,
                        }
                    ],
                }
            )
            gen = make_scenario_generator(settings, store, workers={"C": run_worker_c})
            with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-test"}, clear=True):
                with patch("hookpipe.workers._import_c_generate", return_value=c_generate):
                    gen({**proj, "_ab_override": {"provider": "anthropic", "model": "claude-sonnet-5-5", "explicit": True}}, ["C"], "anthropic")

            # Also record a video clip cache hit to test media summary
            store.record_api_usage(
                project_id=pid,
                user_id=normal_user.user_id,
                hook_type="C",
                stage="video_clip",
                step_name="beat_1",
                provider="google",
                model="gemini-omni-flash-preview",
                media_unit="sec",
                media_qty=4.0,
                estimated_cost_usd=0.0,
                unit_price_label="cache_hit ($0)",
                cache_hit=True,
                latency_ms=0,
            )

            app = create_app(settings=settings, project_store=store)
            client = TestClient(app)

            # 1) Unauthenticated -> 401
            self.assertEqual(client.get("/v1/admin/usage/summary").status_code, 401)

            # 2) Non-admin user -> 403
            norm_tok, _ = issue_session_token(normal_user, secret, ttl_days=1)
            self.assertEqual(
                client.get("/v1/admin/usage/summary", headers={"Authorization": f"Bearer {norm_tok}"}).status_code,
                403,
            )

            # 3) Allowlisted admin email -> 200
            adm_tok, _ = issue_session_token(admin_user, secret, ttl_days=1)
            res = client.get("/v1/admin/usage/summary", headers={"Authorization": f"Bearer {adm_tok}"})
            self.assertEqual(res.status_code, 200, res.text)
            summary = res.json()
            self.assertEqual(summary["totals"]["total_calls"], 2)
            self.assertEqual(summary["totals"]["cache_hits"], 1)
            self.assertEqual(summary["totals"]["input_tokens"], 5000)
            self.assertEqual(summary["totals"]["output_tokens"], 1200)
            # 5000 * $2/1M + 1200 * $10/1M = 0.01 + 0.012 = 0.022
            self.assertAlmostEqual(summary["totals"]["estimated_cost_usd"], 0.022, places=6)
            self.assertEqual(summary["recent_projects"][0]["project_id"], pid)
            self.assertEqual(summary["usd_krw_rate"], 1400.0)

            # 4) API_BEARER_TOKEN also allowed for project drill-down
            det_res = client.get(
                f"/v1/admin/usage/projects/{pid}",
                headers={"Authorization": "Bearer adm-secret-token"},
            )
            self.assertEqual(det_res.status_code, 200, det_res.text)
            detail = det_res.json()
            self.assertEqual(detail["project"]["product_name"], "60분 비주얼 타이머")
            self.assertEqual(len(detail["events"]), 2)
            self.assertEqual(detail["events"][0]["stage"], "scenario_c")
            self.assertEqual(detail["events"][0]["model"], "claude-sonnet-5-5")

    @unittest.skipUnless(tools_or_none() is not None, "ffmpeg required")
    def test_make_body_records_body_tts_usage(self) -> None:
        tools = tools_or_none()
        assert tools is not None
        with temporary_directory() as td:
            root = Path(td)
            clip = make_video(tools, root / "clip.mp4", seconds=6.0, width=360, height=640)
            provider = FakeMediaProvider(tools)
            provider.tts_label = "inworld:inworld-tts-2"
            events: list[dict] = []
            base_settings = Settings(
                _env_file=None,
                gemini_api_key="dummy-key",
                work_root=str(root / "work"),
                output_dir=str(root / "outputs"),
                db_path=str(root / "napda.db"),
                body_target_sec=10.0,
            )
            overlay = _SettingsOverlay(base_settings, _on_usage=lambda **kw: events.append(kw))
            make_body(
                [clip],
                {"name": "60분 비주얼 타이머", "verified_facts": ["60분형 아날로그 타이머"]},
                root / "body",
                provider=provider,
                settings=overlay,
                tools=tools,
                writer=fake_body_writer,
            )
            tts_events = [e for e in events if e.get("stage") == "body_tts"]
            self.assertEqual(len(tts_events), 2)
            self.assertEqual(tts_events[0]["provider"], "inworld")
            self.assertEqual(tts_events[0]["model"], "inworld-tts-2")
            self.assertEqual(tts_events[0]["media_unit"], "char")
            self.assertGreater(tts_events[0]["media_qty"], 0.0)


if __name__ == "__main__":
    unittest.main()
