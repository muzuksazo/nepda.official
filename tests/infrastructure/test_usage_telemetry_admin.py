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
from app.storage import S3StorageBackend, _infer_content_type  # noqa: E402
from app.usage_telemetry import estimate_cost_usd, parse_pricing_overrides, pricing_catalog  # noqa: E402
from hookpipe.body_edit import make_body  # noqa: E402
from hookpipe.render import render_hook  # noqa: E402
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
                    generated = gen({**proj, "_ab_override": {"provider": "anthropic", "model": "claude-sonnet-5-5", "explicit": True}}, ["C"], "anthropic")
            store.append_scenarios(pid, generated)

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
            proj_row = summary["recent_projects"][0]
            self.assertIn("has_final_video", proj_row)
            self.assertIn("has_thumbnail", proj_row)
            self.assertIn("thumbnail_url", proj_row)
            self.assertIn("storyboard_count", proj_row)
            self.assertIn("hook_count", proj_row)
            by_stage = {row["stage"]: row for row in summary["by_stage"]}
            self.assertEqual(by_stage["scenario_c"]["stage_label"], "C안 시나리오 기획")
            self.assertTrue(by_stage["scenario_c"]["output_description"])
            self.assertEqual(by_stage["video_clip"]["stage_label"], "훅 영상 클립 생성")

            # Add storyboard (with object_key), tts (with object_key), video_clip (with object_key),
            # plus a hook artifact so video_clip without object_key exercises fallback matching.
            store.create_hook(
                hook_id="hook_match_01",
                project_id=pid,
                user_id=normal_user.user_id,
                scenario_id=generated[0]["scenario_id"],
                job_id="job_match_01",
                tts={"enabled": True, "voice": "test"},
                output_dir=str(root / "hook_out"),
                status="done",
            )
            store.update_hook(
                "hook_match_01",
                files={"hook_video": f"projects/{pid}/hooks/hook_match_01/hook.mp4"},
            )
            store.record_api_usage(
                project_id=pid,
                user_id=normal_user.user_id,
                hook_type="C",
                stage="storyboard",
                step_name="frame_01",
                provider="google",
                model="gemini-nano-banana-2.1",
                media_unit="image",
                media_qty=1.0,
                estimated_cost_usd=0.0336,
                unit_price_label="$0.0336 / image",
                metadata={
                    "prompt": "frame prompt",
                    "object_key": f"projects/{pid}/storyboards/sc_tel_c/frame_01.png",
                },
            )
            store.record_api_usage(
                project_id=pid,
                user_id=normal_user.user_id,
                hook_type="C",
                stage="video_clip",
                step_name="beat_2",
                provider="google",
                model="gemini-omni-flash-preview",
                media_unit="sec",
                media_qty=4.0,
                estimated_cost_usd=0.4,
                unit_price_label="$0.1 / sec",
                metadata={
                    "prompt": "clip prompt",
                    "clip_sec": 4,
                    "resolution": "720p",
                    "object_key": f"projects/{pid}/usage_artifacts/video_clip/beat_2_abc123.mp4",
                },
            )
            store.record_api_usage(
                project_id=pid,
                user_id=normal_user.user_id,
                hook_type="C",
                stage="tts",
                step_name="beat_1",
                provider="inworld",
                model="inworld-tts-2",
                media_unit="char",
                media_qty=20.0,
                estimated_cost_usd=0.0005,
                unit_price_label="$25 / 1M char",
                metadata={
                    "text": "이건 정말 신세계에요",
                    "voice": "test",
                    "object_key": f"projects/{pid}/usage_artifacts/tts/beat_1_abc123.mp3",
                },
            )

            # 4) API_BEARER_TOKEN also allowed for project drill-down
            det_res = client.get(
                f"/v1/admin/usage/projects/{pid}",
                headers={"Authorization": "Bearer adm-secret-token"},
            )
            self.assertEqual(det_res.status_code, 200, det_res.text)
            detail = det_res.json()
            self.assertEqual(detail["project"]["product_name"], "60분 비주얼 타이머")
            self.assertEqual(len(detail["events"]), 5)
            by_key = {(e["stage"], e.get("step_name")): e for e in detail["events"]}
            self.assertEqual(by_key[("scenario_c", "scenarios")]["stage_label"], "C안 시나리오 기획")
            self.assertIn("hook_titles", by_key[("scenario_c", "scenarios")]["metadata"])

            scn_match = by_key[("scenario_c", "scenarios")]["matched_artifact"]
            self.assertEqual(scn_match["media_type"], "text")
            self.assertTrue(scn_match["is_exact"])
            self.assertIn("C안 시나리오", scn_match["label"])

            sb_match = by_key[("storyboard", "frame_01")]["matched_artifact"]
            self.assertEqual(sb_match["media_type"], "image")
            self.assertTrue(sb_match["is_exact"])
            self.assertTrue(sb_match["preview_url"])

            vc_exact = by_key[("video_clip", "beat_2")]["matched_artifact"]
            self.assertEqual(vc_exact["media_type"], "video")
            self.assertTrue(vc_exact["is_exact"])
            self.assertIn("/v1/media", vc_exact["preview_url"])

            vc_fb = by_key[("video_clip", "beat_1")]["matched_artifact"]
            self.assertEqual(vc_fb["media_type"], "video")
            self.assertFalse(vc_fb["is_exact"])
            self.assertIn("/v1/media", vc_fb["preview_url"])

            tts_match = by_key[("tts", "beat_1")]["matched_artifact"]
            self.assertEqual(tts_match["media_type"], "audio")
            self.assertTrue(tts_match["is_exact"])
            self.assertIn("이건 정말 신세계에요", tts_match["text_preview"])

            sb_chips = {s["stage"]: s for s in detail["stage_breakdown"]}
            self.assertEqual(sb_chips["video_clip"]["calls"], 2)
            self.assertEqual(sb_chips["video_clip"]["cache_hits"], 1)
            self.assertAlmostEqual(sb_chips["video_clip"]["estimated_cost_usd"], 0.4, places=6)

            self.assertIsNotNone(detail["artifacts"])
            self.assertEqual(detail["artifacts"]["product"]["name"], "60분 비주얼 타이머")
            self.assertEqual(len(detail["artifacts"]["scenarios"]), 1)
            self.assertTrue(detail["artifacts"]["scenarios"][0]["scenario_id"].startswith("sc_tel_c"))
            self.assertGreaterEqual(len(detail["artifacts"]["scenarios"][0]["beats"]), 1)

    @unittest.skipUnless(tools_or_none() is not None, "ffmpeg required")
    def test_render_hook_publish_artifact_attaches_object_keys(self) -> None:
        tools = tools_or_none()
        assert tools is not None
        with temporary_directory() as td:
            root = Path(td)
            provider = FakeMediaProvider(tools)
            settings = Settings(
                _env_file=None,
                gemini_api_key="dummy-key",
                work_root=str(root / "work"),
                output_dir=str(root / "outputs"),
                db_path=str(root / "napda.db"),
                image_model="gemini-nano-banana-2.1",
                video_model="gemini-omni-flash-preview",
            )
            scenario = worker_scenario("C", "sc_pub_01")
            events: list[dict] = []
            published: list[tuple[str, str, str]] = []

            def _publish(stage: str, step_name: str, path: Path) -> str:
                key = f"projects/prj_pub/usage_artifacts/{stage}/{step_name}{path.suffix}"
                published.append((stage, step_name, key))
                return key

            render_hook(
                scenario,
                {"name": "60분 비주얼 타이머", "verified_facts": ["60분형 아날로그 타이머"]},
                root / "hook_out",
                provider=provider,
                settings=settings,
                tools=tools,
                on_usage=lambda **kw: events.append(kw),
                publish_artifact=_publish,
            )
            by_stage: dict[str, list[dict]] = {}
            for ev in events:
                by_stage.setdefault(ev["stage"], []).append(ev)
            self.assertTrue(by_stage.get("tts"))
            self.assertTrue(all((e.get("metadata") or {}).get("object_key") for e in by_stage["tts"]))
            self.assertTrue(by_stage.get("ref_image"))
            self.assertTrue(all((e.get("metadata") or {}).get("object_key") for e in by_stage["ref_image"]))
            self.assertTrue(by_stage.get("video_clip"))
            self.assertTrue(all((e.get("metadata") or {}).get("object_key") for e in by_stage["video_clip"]))
            self.assertGreaterEqual(len(published), 3)

    def test_s3_storage_sets_content_type_on_upload_and_presign(self) -> None:
        self.assertEqual(_infer_content_type("renders/job_1/master.mp4"), "video/mp4")
        self.assertEqual(_infer_content_type("thumbnails/t1/cover.png"), "image/png")
        self.assertEqual(_infer_content_type("usage/tts/beat_1.mp3"), "audio/mpeg")
        self.assertEqual(_infer_content_type("renders/job_1/final.srt"), "text/plain; charset=utf-8")

        fake_client = SimpleNamespace(
            upload_calls=[],
            presign_calls=[],
        )

        def _upload_file(filename, bucket, key, **kwargs):
            fake_client.upload_calls.append((filename, bucket, key, kwargs))

        def _generate_presigned_url(op, Params=None, ExpiresIn=3600):
            fake_client.presign_calls.append((op, Params, ExpiresIn))
            return f"https://r2.example/{Params['Bucket']}/{Params['Key']}?ct={Params.get('ResponseContentType', '')}"

        fake_client.upload_file = _upload_file
        fake_client.generate_presigned_url = _generate_presigned_url

        with temporary_directory() as td:
            sample = Path(td) / "master_with_cover.mp4"
            sample.write_bytes(b"ftypisom")
            settings = Settings(
                _env_file=None,
                storage_backend="r2",
                s3_bucket="napda",
                s3_endpoint_url="https://example.r2.cloudflarestorage.com",
                s3_access_key_id="k",
                s3_secret_access_key="s",
                gemini_api_key="dummy-key",
            )
            with patch("boto3.client", return_value=fake_client):
                backend = S3StorageBackend(settings)
            url = backend.upload_file(sample, "projects/p1/master_with_cover.mp4")

        self.assertEqual(len(fake_client.upload_calls), 1)
        self.assertEqual(
            fake_client.upload_calls[0][3],
            {"ExtraArgs": {"ContentType": "video/mp4"}},
        )
        self.assertEqual(
            fake_client.presign_calls[0][1]["ResponseContentType"],
            "video/mp4",
        )
        self.assertIn("ResponseContentType=video/mp4" if False else "ct=video/mp4", url)

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
