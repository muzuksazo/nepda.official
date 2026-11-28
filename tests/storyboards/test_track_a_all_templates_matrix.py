"""Dynamic All-Template Matrix E2E Tests for Track A templates.

Dynamically loads every template in `backend/data/templates/track_a/manifest.json`
so any newly added Track A template is automatically verified for:
1. Codec, pixel format, portrait geometry, duration, and file-size invariants (`ffprobe`).
2. Real `POST /v1/projects/{pid}/scenarios/{scn_id}/storyboard` API extraction
   (4 frames, valid 540x675 PNG > 5 KB via signed `/v1/media/...`, Korean captions
   with zero internal ID leaks and zero post-gap CTA leaks).
3. Fast 1-second FFmpeg render-pipeline compatibility probe (1080x1920, yuv420p).
"""

from __future__ import annotations

import io
import json
import re
import shutil
import subprocess
import sys
import unittest
from pathlib import Path
from typing import Any, Dict, List

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from fastapi.testclient import TestClient  # noqa: E402

from app.config import Settings  # noqa: E402
from app.projects_router import _build_default_ad_spec  # noqa: E402
from app.server import create_app  # noqa: E402
from tests.support.projects_api import fake_google_verifier, login_client  # noqa: E402
from tests.support.tempdirs import temporary_directory  # noqa: E402

TRACK_A_DIR = ROOT / "backend" / "data" / "templates" / "track_a"
MANIFEST_PATH = TRACK_A_DIR / "manifest.json"
MAX_TEMPLATE_BYTES = 12 * 1024 * 1024
KOREAN_RE = re.compile(r"[가-힣]")
FORBIDDEN_INTERNAL_TOKENS = ("payoff_1", "twist_gap", "hook_1", "hook_2", "silence_gap")
POST_GAP_CTA_SENTINEL = "지금 바로 구매 링크 댓글로 받기"


def _load_manifest_entries() -> List[Dict[str, Any]]:
    raw = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise AssertionError("Track A manifest.json must be a JSON array")
    return [entry for entry in raw if isinstance(entry, dict)]


def _ffprobe_json(path: Path) -> Dict[str, Any]:
    proc = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(proc.stdout)


def _first_video_stream(probe: Dict[str, Any]) -> Dict[str, Any]:
    for stream in probe.get("streams") or []:
        if stream.get("codec_type") == "video":
            return stream
    raise AssertionError("No video stream found in ffprobe output")


def _extract_duration(probe: Dict[str, Any], video_stream: Dict[str, Any]) -> float:
    for raw in (probe.get("format", {}).get("duration"), video_stream.get("duration")):
        if raw not in (None, "", "N/A"):
            return float(raw)
    raise AssertionError("Could not determine video duration from ffprobe output")


class TestTrackAAllTemplatesMatrix(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not MANIFEST_PATH.is_file():
            raise unittest.SkipTest(
                f"Track A manifest absent in stripped checkout: {MANIFEST_PATH}"
            )
        if not shutil.which("ffprobe") or not shutil.which("ffmpeg"):
            raise unittest.SkipTest("ffmpeg/ffprobe required for Track A matrix verification")
        cls.entries = _load_manifest_entries()

    def test_all_templates_codec_geometry_and_manifest_parity(self) -> None:
        self.assertGreater(len(self.entries), 0, "manifest.json must contain at least 1 template")
        seen_ids = set()

        for entry in self.entries:
            tpl_id = str(entry.get("id") or "").strip()
            with self.subTest(template_id=tpl_id):
                self.assertTrue(tpl_id, "Template entry missing id")
                self.assertNotIn(tpl_id, seen_ids, f"Duplicate template id: {tpl_id}")
                seen_ids.add(tpl_id)

                filename = str(entry.get("filename") or "").strip()
                self.assertTrue(filename.endswith(".mp4"), f"Expected .mp4 filename, got {filename!r}")
                mp4_path = TRACK_A_DIR / filename
                self.assertTrue(mp4_path.is_file(), f"Template MP4 missing: {mp4_path}")

                size_bytes = mp4_path.stat().st_size
                self.assertGreater(size_bytes, 1024, f"Template MP4 unexpectedly tiny: {size_bytes}")
                self.assertLessEqual(
                    size_bytes,
                    MAX_TEMPLATE_BYTES,
                    f"{tpl_id} exceeds 12 MB limit ({size_bytes} bytes)",
                )

                probe = _ffprobe_json(mp4_path)
                vstream = _first_video_stream(probe)
                self.assertEqual(
                    vstream.get("codec_name"),
                    "h264",
                    f"{tpl_id} codec must be h264, got {vstream.get('codec_name')}",
                )
                self.assertEqual(
                    vstream.get("pix_fmt"),
                    "yuv420p",
                    f"{tpl_id} pix_fmt must be yuv420p, got {vstream.get('pix_fmt')}",
                )

                width = int(vstream.get("width") or 0)
                height = int(vstream.get("height") or 0)
                self.assertGreater(width, 0, f"{tpl_id} width must be > 0")
                self.assertGreater(height, width, f"{tpl_id} must be portrait, got {width}x{height}")

                probed_dur = _extract_duration(probe, vstream)
                manifest_dur = float(entry.get("duration_sec") or 0.0)
                self.assertGreaterEqual(probed_dur, 2.0, f"{tpl_id} duration < 2.0s: {probed_dur}")
                self.assertLessEqual(probed_dur, 30.0, f"{tpl_id} duration > 30.0s: {probed_dur}")
                self.assertLessEqual(
                    abs(probed_dur - manifest_dur),
                    0.35,
                    f"{tpl_id} duration drift: probed={probed_dur:.3f}s vs manifest={manifest_dur:.3f}s",
                )

    def test_all_templates_storyboard_api_extraction(self) -> None:
        self.assertGreater(len(self.entries), 0)

        active_template: Dict[str, Any] = {}

        def _matrix_scenario_generator(
            project: Dict[str, Any], hook_types: List[str], provider: str
        ) -> List[Dict[str, Any]]:
            _ = (hook_types, provider)
            entry = active_template["entry"]
            tpl_id = str(entry["id"])
            tpl_dur = float(entry.get("duration_sec") or 5.0)
            spec = _build_default_ad_spec(
                project,
                "A",
                source_video="source/sample.mp4",
                source_duration=15.0,
                voice_id="Kore",
            )
            spec["track_a_template_id"] = tpl_id
            default_caps = [str(c) for c in (entry.get("default_hook_captions") or []) if str(c).strip()]
            first_cap = default_caps[0] if default_caps else "놀라운 3D 물리 실험이 시작됩니다"
            return [
                {
                    "scenario_id": f"scn_A_{tpl_id}",
                    "type": "A",
                    "hook_title": str(entry.get("title") or tpl_id),
                    "hook_duration_sec": tpl_dur,
                    "body_duration_sec": 12.0,
                    "replacement_test_note": f"matrix verification for {tpl_id}",
                    "beats": [
                        {
                            "order": 1,
                            "role": "video",
                            "duration_sec": round(tpl_dur / 2.0, 2),
                            "visual": str(entry.get("title") or "3D 물리 훅 장면"),
                            "narration": first_cap,
                            "caption": first_cap,
                        },
                        {
                            "order": 2,
                            "role": "silence_gap",
                            "duration_sec": 0.25,
                            "visual": "twist_gap",
                            "narration": "",
                            "caption": "",
                        },
                        {
                            "order": 3,
                            "role": "source",
                            "duration_sec": 6.0,
                            "visual": "payoff_1",
                            "narration": POST_GAP_CTA_SENTINEL,
                            "caption": POST_GAP_CTA_SENTINEL,
                        },
                    ],
                    "storyboard_frames": [],
                    "ad_spec": spec,
                }
            ]

        with temporary_directory() as td:
            root = Path(td)
            settings = Settings(
                _env_file=None,
                gemini_api_key="dummy-key",
                google_client_id="dummy-client-id.apps.googleusercontent.com",
                session_secret="test-session-secret-32bytes-minimum",
                daily_render_limit=20,
                hook_render_mode="dry_run",
                work_root=str(root / "work"),
                output_dir=str(root / "outputs"),
                db_path=str(root / "napda.db"),
                track_a_template_dir=str(TRACK_A_DIR),
            )
            app = create_app(
                settings=settings,
                google_token_verifier=fake_google_verifier,
                scenario_generator=_matrix_scenario_generator,
                storyboard_generator=None,  # Exercise real _default_storyboard_generator!
            )
            client = TestClient(app)
            login_client(client)

            for entry in self.entries:
                tpl_id = str(entry["id"])
                active_template["entry"] = entry
                with self.subTest(template_id=tpl_id):
                    proj_resp = client.post(
                        "/v1/projects",
                        json={
                            "product": {
                                "name": f"매트릭스 테스트 제품 ({tpl_id})",
                                "category": "living",
                                "verified_facts": ["실제 3D 스토리보드 추출 검증"],
                            },
                            "selected_types": ["A"],
                        },
                    )
                    self.assertEqual(proj_resp.status_code, 201, proj_resp.text)
                    pid = proj_resp.json()["project_id"]

                    scn_resp = client.post(f"/v1/projects/{pid}/scenarios", json={})
                    self.assertEqual(scn_resp.status_code, 200, scn_resp.text)
                    scenarios = scn_resp.json()["scenarios"]
                    self.assertEqual(len(scenarios), 1)
                    scn_id = scenarios[0]["scenario_id"]

                    sb_resp = client.post(
                        f"/v1/projects/{pid}/scenarios/{scn_id}/storyboard",
                        json={"visual_style": "default"},
                    )
                    self.assertEqual(sb_resp.status_code, 200, f"{tpl_id}: {sb_resp.text}")
                    payload = sb_resp.json()
                    self.assertEqual(payload["status"], "STORYBOARD_READY")

                    frames = payload["frames"]
                    self.assertEqual(len(frames), 4, f"{tpl_id}: expected 4 storyboard frames")

                    for frame in frames:
                        caption = str(frame.get("caption") or "").strip()
                        self.assertTrue(caption, f"{tpl_id} frame {frame.get('beat_order')} empty caption")
                        self.assertRegex(
                            caption,
                            KOREAN_RE,
                            f"{tpl_id} frame {frame.get('beat_order')} caption must contain Korean: {caption!r}",
                        )
                        for forbidden in FORBIDDEN_INTERNAL_TOKENS:
                            self.assertNotIn(
                                forbidden,
                                caption.lower(),
                                f"{tpl_id} leaked internal token {forbidden!r} in {caption!r}",
                            )
                        self.assertNotIn(
                            "구매 링크",
                            caption,
                            f"{tpl_id} leaked post-gap CTA in {caption!r}",
                        )
                        self.assertNotIn(
                            "댓글로",
                            caption,
                            f"{tpl_id} leaked post-gap CTA in {caption!r}",
                        )

                        img_url = str(frame.get("image_url") or "")
                        self.assertTrue(
                            img_url.startswith("/v1/media/"),
                            f"{tpl_id} unexpected image_url: {img_url!r}",
                        )
                        media_resp = client.get(img_url)
                        self.assertEqual(
                            media_resp.status_code,
                            200,
                            f"{tpl_id} failed downloading {img_url}: {media_resp.status_code}",
                        )
                        raw_bytes = media_resp.content
                        self.assertGreater(
                            len(raw_bytes),
                            5 * 1024,
                            f"{tpl_id} frame PNG too small ({len(raw_bytes)} bytes)",
                        )
                        with Image.open(io.BytesIO(raw_bytes)) as img:
                            self.assertEqual(img.format, "PNG", f"{tpl_id} frame not PNG")
                            self.assertEqual(
                                img.size,
                                (540, 675),
                                f"{tpl_id} frame size mismatch: {img.size}",
                            )

    def test_all_templates_ffmpeg_render_compatibility_probe(self) -> None:
        self.assertGreater(len(self.entries), 0)

        with temporary_directory() as td:
            out_root = Path(td)
            for entry in self.entries:
                tpl_id = str(entry["id"])
                mp4_path = TRACK_A_DIR / str(entry["filename"])
                out_mp4 = out_root / f"{tpl_id}_probe.mp4"
                with self.subTest(template_id=tpl_id):
                    proc = subprocess.run(
                        [
                            "ffmpeg",
                            "-y",
                            "-v",
                            "error",
                            "-i",
                            str(mp4_path),
                            "-t",
                            "1.0",
                            "-vf",
                            "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1",
                            "-c:v",
                            "libx264",
                            "-preset",
                            "ultrafast",
                            "-pix_fmt",
                            "yuv420p",
                            "-an",
                            str(out_mp4),
                        ],
                        capture_output=True,
                        text=True,
                    )
                    self.assertEqual(
                        proc.returncode,
                        0,
                        f"{tpl_id} ffmpeg trim+scale failed: {proc.stderr}",
                    )
                    self.assertTrue(out_mp4.is_file(), f"{tpl_id} probe output missing")
                    self.assertGreater(out_mp4.stat().st_size, 1024, f"{tpl_id} probe output empty")

                    probe = _ffprobe_json(out_mp4)
                    vstream = _first_video_stream(probe)
                    self.assertEqual(vstream.get("codec_name"), "h264")
                    self.assertEqual(vstream.get("pix_fmt"), "yuv420p")
                    self.assertEqual(int(vstream.get("width") or 0), 1080)
                    self.assertEqual(int(vstream.get("height") or 0), 1920)
                    dur = _extract_duration(probe, vstream)
                    self.assertGreater(dur, 0.5, f"{tpl_id} probe output duration too short: {dur}")


if __name__ == "__main__":
    unittest.main()
