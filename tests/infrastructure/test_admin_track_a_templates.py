"""Admin Track A template CRUD, auth guard, auto-seeding, ffprobe validation, and enabled filtering tests."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.auth import AuthenticatedUser, issue_session_token  # noqa: E402
from app.config import Settings  # noqa: E402
from app.project_store import ProjectStore  # noqa: E402
from app.projects_router import _load_track_a_manifest_entries  # noqa: E402
from app.server import create_app  # noqa: E402
from tests.support.production import _make_sample_mp4_bytes  # noqa: E402
from tests.support.tempdirs import temporary_directory  # noqa: E402


class TestAdminTrackATemplatesAPI(unittest.TestCase):
    def _build_client(self, root: Path) -> tuple[TestClient, Settings, str, str]:
        secret = "test-session-secret-32bytes-minimum"
        settings = Settings(
            _env_file=None,
            gemini_api_key="dummy-key",
            session_secret=secret,
            admin_emails="admin@napda.ai",
            api_bearer_token="adm-secret-token",
            work_root=str(root / "data" / "jobs"),
            output_dir=str(root / "data" / "outputs"),
            db_path=str(root / "data" / "napda.db"),
        )
        store = ProjectStore(settings.db_path)
        admin_user = AuthenticatedUser(user_id="usr_adm", email="admin@napda.ai", name="Admin")
        normal_user = AuthenticatedUser(user_id="usr_usr", email="normal@example.com", name="User")
        store.upsert_user(admin_user)
        store.upsert_user(normal_user)
        adm_tok, _ = issue_session_token(admin_user, secret, ttl_days=1)
        norm_tok, _ = issue_session_token(normal_user, secret, ttl_days=1)
        app = create_app(settings=settings, project_store=store)
        return TestClient(app), settings, adm_tok, norm_tok

    def test_auth_guard_auto_seed_crud_validation_and_enabled_filter(self) -> None:
        with temporary_directory() as td:
            root = Path(td)
            client, settings, adm_tok, norm_tok = self._build_client(root)
            adm_hdr = {"Authorization": f"Bearer {adm_tok}"}
            norm_hdr = {"Authorization": f"Bearer {norm_tok}"}
            bearer_hdr = {"Authorization": "Bearer adm-secret-token"}

            # 1) Auth guard: unauthenticated -> 401, non-admin -> 403
            self.assertEqual(client.get("/v1/admin/templates/track-a").status_code, 401)
            self.assertEqual(client.get("/v1/admin/templates/track-a", headers=norm_hdr).status_code, 403)

            # 2) Auto-seed into persistent managed dir on first read (when bundled templates exist)
            res = client.get("/v1/admin/templates/track-a", headers=adm_hdr)
            self.assertEqual(res.status_code, 200, res.text)
            seeded = res.json()["templates"]
            managed_dir = root / "data" / "templates" / "track_a"
            self.assertGreaterEqual(len(seeded), 10)
            self.assertTrue((managed_dir / "manifest.json").is_file())
            first_id = seeded[0]["id"]
            self.assertEqual(seeded[0]["video_url"], f"/v1/admin/templates/track-a/{first_id}/video")
            self.assertTrue(seeded[0]["enabled"])
            self.assertGreater(seeded[0]["width"], 0)
            self.assertGreater(seeded[0]["size_bytes"], 0)

            # Stream video via admin endpoint (works with API_BEARER_TOKEN too)
            vid_res = client.get(seeded[0]["video_url"], headers=bearer_hdr)
            self.assertEqual(vid_res.status_code, 200)
            self.assertEqual(vid_res.headers.get("content-type"), "video/mp4")
            self.assertGreater(len(vid_res.content), 10_000)

            # 3) Path traversal / invalid ID -> 400 INVALID_TEMPLATE_ID
            bad_id_res = client.get("/v1/admin/templates/track-a/..bad/video", headers=adm_hdr)
            self.assertEqual(bad_id_res.status_code, 400)
            self.assertEqual(bad_id_res.json()["detail"]["error"]["code"], "INVALID_TEMPLATE_ID")
            bad_del = client.delete("/v1/admin/templates/track-a/BAD_UPPER!", headers=adm_hdr)
            self.assertEqual(bad_del.status_code, 400)
            self.assertEqual(bad_del.json()["detail"]["error"]["code"], "INVALID_TEMPLATE_ID")

            # 4) Invalid / corrupt video upload -> 400 INVALID_TEMPLATE_VIDEO
            bad_upload = client.post(
                "/v1/admin/templates/track-a",
                headers=adm_hdr,
                data={
                    "id": "a_corrupt_test",
                    "title": "손상 파일 테스트",
                    "visual_summary": "corrupt payload",
                },
                files={"file": ("broken.mp4", b"not-a-valid-mp4-stream", "video/mp4")},
            )
            self.assertEqual(bad_upload.status_code, 400, bad_upload.text)
            self.assertEqual(bad_upload.json()["detail"]["error"]["code"], "INVALID_TEMPLATE_VIDEO")

            # Too short video (< 2.0s) -> 400 INVALID_TEMPLATE_VIDEO
            short_mp4 = _make_sample_mp4_bytes(duration=1.0, w=720, h=1280)
            short_upload = client.post(
                "/v1/admin/templates/track-a",
                headers=adm_hdr,
                data={
                    "id": "a_short_test",
                    "title": "너무 짧은 영상",
                    "visual_summary": "too short",
                },
                files={"file": ("short.mp4", short_mp4, "video/mp4")},
            )
            self.assertEqual(short_upload.status_code, 400, short_upload.text)
            self.assertEqual(short_upload.json()["detail"]["error"]["code"], "INVALID_TEMPLATE_VIDEO")

            # 5) Valid real FFmpeg MP4 upload -> 201
            valid_mp4 = _make_sample_mp4_bytes(duration=4.0, w=720, h=1280)
            created = client.post(
                "/v1/admin/templates/track-a",
                headers=adm_hdr,
                data={
                    "id": "a_custom_lab_3d",
                    "title": "커스텀 실험실 훅",
                    "a_genre_archetype": "absurd_physics",
                    "tags": "실험, 거품, 세정, foam",
                    "visual_summary": "3D lab foam eruption physics test",
                    "default_hook_captions": "비커에 용액을 한 방울 넣으면\n순식간에 천장까지 폭발합니다",
                    "enabled": "true",
                },
                files={"file": ("custom.mp4", valid_mp4, "video/mp4")},
            )
            self.assertEqual(created.status_code, 201, created.text)
            cj = created.json()
            self.assertEqual(cj["id"], "a_custom_lab_3d")
            self.assertEqual(cj["width"], 720)
            self.assertEqual(cj["height"], 1280)
            self.assertAlmostEqual(cj["duration_sec"], 4.0, delta=0.2)
            self.assertEqual(cj["tags"], ["실험", "거품", "세정", "foam"])
            self.assertEqual(len(cj["default_hook_captions"]), 2)
            self.assertTrue(cj["enabled"])

            # Duplicate ID -> 409 TEMPLATE_ALREADY_EXISTS
            dup = client.post(
                "/v1/admin/templates/track-a",
                headers=adm_hdr,
                data={
                    "id": "a_custom_lab_3d",
                    "title": "중복 테스트",
                    "visual_summary": "dup",
                },
                files={"file": ("custom.mp4", valid_mp4, "video/mp4")},
            )
            self.assertEqual(dup.status_code, 409, dup.text)
            self.assertEqual(dup.json()["detail"]["error"]["code"], "TEMPLATE_ALREADY_EXISTS")

            # 6) JSON PATCH toggle enabled=false & metadata edit -> excluded from _load_track_a_manifest_entries
            self.assertIn(
                "a_custom_lab_3d",
                [e["id"] for e in _load_track_a_manifest_entries(settings)],
            )
            patched = client.patch(
                "/v1/admin/templates/track-a/a_custom_lab_3d",
                headers=adm_hdr,
                json={
                    "enabled": False,
                    "title": "커스텀 실험실 훅 (수정)",
                    "tags": ["거품", "세정", "cleaning"],
                },
            )
            self.assertEqual(patched.status_code, 200, patched.text)
            pj = patched.json()
            self.assertFalse(pj["enabled"])
            self.assertEqual(pj["title"], "커스텀 실험실 훅 (수정)")
            self.assertEqual(pj["tags"], ["거품", "세정", "cleaning"])

            # Disabled template excluded from default enabled_only loader, still visible when enabled_only=False
            self.assertNotIn(
                "a_custom_lab_3d",
                [e["id"] for e in _load_track_a_manifest_entries(settings)],
            )
            self.assertIn(
                "a_custom_lab_3d",
                [e["id"] for e in _load_track_a_manifest_entries(settings, enabled_only=False)],
            )

            # 7) Multipart PATCH replacing video file + re-enabling
            replacement_mp4 = _make_sample_mp4_bytes(duration=6.0, w=1080, h=1920)
            mp_patched = client.patch(
                "/v1/admin/templates/track-a/a_custom_lab_3d",
                headers=adm_hdr,
                data={
                    "enabled": "true",
                    "default_hook_captions": json.dumps(["교체된 첫 문장", "교체된 두 번째 문장"], ensure_ascii=False),
                },
                files={"file": ("replacement.mp4", replacement_mp4, "video/mp4")},
            )
            self.assertEqual(mp_patched.status_code, 200, mp_patched.text)
            mj = mp_patched.json()
            self.assertTrue(mj["enabled"])
            self.assertEqual(mj["width"], 1080)
            self.assertEqual(mj["height"], 1920)
            self.assertAlmostEqual(mj["duration_sec"], 6.0, delta=0.2)
            self.assertEqual(mj["default_hook_captions"], ["교체된 첫 문장", "교체된 두 번째 문장"])

            # 8) DELETE removes entry from manifest.json and unlinks .mp4
            mp4_file = managed_dir / "a_custom_lab_3d.mp4"
            self.assertTrue(mp4_file.is_file())
            deleted = client.delete("/v1/admin/templates/track-a/a_custom_lab_3d", headers=adm_hdr)
            self.assertEqual(deleted.status_code, 200, deleted.text)
            self.assertEqual(deleted.json(), {"deleted": True, "id": "a_custom_lab_3d"})
            self.assertFalse(mp4_file.is_file())

            # Missing template -> 404
            self.assertEqual(
                client.delete("/v1/admin/templates/track-a/a_custom_lab_3d", headers=adm_hdr).status_code,
                404,
            )

    def test_admin_crud_mirrors_to_remote_template_storage_preserving_catalog(self) -> None:
        from app.track_a_templates import (
            create_track_a_template,
            delete_track_a_template,
            update_track_a_template,
        )

        class FakeRemoteStorage:
            def __init__(self, initial: dict[str, bytes]) -> None:
                self.objects = dict(initial)

            def upload_file(self, local_path: str | Path, object_key: str) -> str:
                self.objects[object_key] = Path(local_path).read_bytes()
                return f"https://r2.example/{object_key}"

            def download_file(self, object_key: str, local_path: str | Path) -> str:
                if object_key not in self.objects:
                    raise FileNotFoundError(object_key)
                dest = Path(local_path)
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(self.objects[object_key])
                return str(dest)

            def delete_object(self, object_key: str) -> bool:
                return self.objects.pop(object_key, None) is not None

        curated_catalog = {
            "version": 1,
            "templates": [
                {
                    "template_id": "a_dam_tape_3d",
                    "abstract_law": "curated law preserved",
                    "genre": "mock_documentary",
                    "hook_title": "Curated dam title",
                    "beats": [
                        {
                            "order": 1,
                            "role": "어긋난 시작",
                            "duration_sec": 10.0,
                            "visual": "dam",
                            "narration": "curated narration",
                            "caption": "curated caption",
                            "clip": "a_dam_tape_3d/beat_01.mp4",
                        },
                        {"order": 2, "role": "패턴 인터럽트", "duration_sec": 0.3, "visual": "정지", "narration": "", "caption": "", "clip": None},
                    ],
                }
            ],
        }
        remote = FakeRemoteStorage(
            {
                "templates/a/catalog.json": json.dumps(curated_catalog, ensure_ascii=False).encode("utf-8"),
            }
        )
        with temporary_directory() as td:
            root = Path(td)
            settings = Settings(
                _env_file=None,
                gemini_api_key="dummy-key",
                hook_a_templates="storage:templates/a",
                work_root=str(root / "data" / "jobs"),
                output_dir=str(root / "data" / "outputs"),
                db_path=str(root / "data" / "napda.db"),
            )
            eligible_mp4 = _make_sample_mp4_bytes(duration=9.0, w=720, h=1280)
            created = create_track_a_template(
                settings,
                file_bytes=eligible_mp4,
                template_id="a_r2_sync_demo",
                title="R2 동기화 데모",
                visual_summary="Synced 3D physics test",
                default_hook_captions=["테스트 자막 첫 줄"],
                template_storage=remote,
            )
            self.assertEqual(created["id"], "a_r2_sync_demo")
            self.assertIn("templates/a/a_r2_sync_demo/beat_01.mp4", remote.objects)
            self.assertIn("templates/a/manifest.json", remote.objects)

            cat_after_create = json.loads(remote.objects["templates/a/catalog.json"].decode("utf-8"))
            by_id = {t["template_id"]: t for t in cat_after_create["templates"]}
            self.assertIn("a_dam_tape_3d", by_id)
            self.assertEqual(by_id["a_dam_tape_3d"]["abstract_law"], "curated law preserved")
            self.assertEqual(by_id["a_r2_sync_demo"]["beats"][0]["clip"], "a_r2_sync_demo/beat_01.mp4")

            # Disabling removes from catalog.json
            update_track_a_template(
                settings,
                "a_r2_sync_demo",
                updates={"enabled": False},
                template_storage=remote,
            )
            cat_after_disable = json.loads(remote.objects["templates/a/catalog.json"].decode("utf-8"))
            self.assertNotIn("a_r2_sync_demo", {t["template_id"] for t in cat_after_disable["templates"]})

            # Deleting removes clip and keeps curated entries intact
            delete_track_a_template(settings, "a_r2_sync_demo", template_storage=remote)
            self.assertNotIn("templates/a/a_r2_sync_demo/beat_01.mp4", remote.objects)
            cat_after_delete = json.loads(remote.objects["templates/a/catalog.json"].decode("utf-8"))
            self.assertIn("a_dam_tape_3d", {t["template_id"] for t in cat_after_delete["templates"]})

    def test_hydrates_from_remote_catalog_json_fallback_when_manifest_missing(self) -> None:
        from app.track_a_templates import list_track_a_templates

        class CatalogOnlyRemoteStorage:
            def __init__(self, objects: dict[str, bytes]) -> None:
                self.objects = dict(objects)

            def download_file(self, object_key: str, local_path: str | Path) -> str:
                if object_key not in self.objects:
                    raise FileNotFoundError(object_key)
                dest = Path(local_path)
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(self.objects[object_key])
                return str(dest)

        clip_bytes = _make_sample_mp4_bytes(duration=9.5, w=720, h=1280)
        catalog_only = {
            "version": 1,
            "templates": [
                {
                    "template_id": "a_fallback_demo",
                    "abstract_law": "Pure physics law without product words",
                    "genre": "mock_documentary",
                    "hook_title": "카탈로그 폴백 테스트 제목",
                    "beats": [
                        {
                            "order": 1,
                            "role": "어긋난 시작",
                            "duration_sec": 9.5,
                            "visual": "physics scene",
                            "narration": "",
                            "caption": "첫 번째 자막",
                            "clip": "a_fallback_demo/beat_01.mp4",
                        },
                        {
                            "order": 2,
                            "role": "패턴 인터럽트",
                            "duration_sec": 0.3,
                            "visual": "정지",
                            "narration": "",
                            "caption": "",
                            "clip": None,
                        },
                    ],
                }
            ],
        }
        remote = CatalogOnlyRemoteStorage(
            {
                "templates/a/catalog.json": json.dumps(catalog_only, ensure_ascii=False).encode("utf-8"),
                "templates/a/a_fallback_demo/beat_01.mp4": clip_bytes,
            }
        )
        with temporary_directory() as td:
            root = Path(td)
            settings = Settings(
                _env_file=None,
                gemini_api_key="dummy-key",
                hook_a_templates="storage:templates/a",
                work_root=str(root / "data" / "jobs"),
                output_dir=str(root / "data" / "outputs"),
                db_path=str(root / "data" / "napda.db"),
            )
            listed = list_track_a_templates(settings, enabled_only=False, template_storage=remote)
            self.assertEqual(len(listed), 1)
            item = listed[0]
            self.assertEqual(item["id"], "a_fallback_demo")
            self.assertEqual(item["title"], "카탈로그 폴백 테스트 제목")
            self.assertEqual(item["a_genre_archetype"], "mock_documentary")
            self.assertEqual(item["default_hook_captions"], ["첫 번째 자막"])
            self.assertAlmostEqual(item["duration_sec"], 9.5, delta=0.2)
            self.assertTrue(item["enabled"])
            self.assertTrue((root / "data" / "templates" / "track_a" / "manifest.json").is_file())
            self.assertTrue((root / "data" / "templates" / "track_a" / "a_fallback_demo.mp4").is_file())


if __name__ == "__main__":
    unittest.main()
