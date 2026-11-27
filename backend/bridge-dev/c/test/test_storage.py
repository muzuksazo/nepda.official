"""R2 업로드·서명과 C CLI/API 연결 검증. 실제 네트워크·유료 생성 API는 호출하지 않는다."""
from __future__ import annotations

import contextlib
import io
import json
import os
import shutil
import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from botocore.stub import Stubber

from src import cli, server
from src.storage import CONTENT_TYPES, DeliveryStorage, StorageError, result_files


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "output"
        self.out = self.root / "proj_test" / "hook_C1"
        self.out.mkdir(parents=True)
        for name in ("hook.mp4", "tts.mp3", "hook.srt", "scenario.json", "storyboard_01.png"):
            (self.out / name).write_bytes(b"test-artifact")
        (self.out / "_work").mkdir()
        (self.out / "_work" / "vo.wav").write_bytes(b"private-cache")
        self.env = {"STORAGE_BACKEND": "s3", "C_STORAGE_BACKEND": "s3", "OUTPUT_DIR": str(self.root), "S3_BUCKET": "test-bucket",
                    "S3_ENDPOINT_URL": "https://test-account.r2.cloudflarestorage.com", "S3_ACCESS_KEY_ID": "test-access-key",
                    "S3_SECRET_ACCESS_KEY": "test-secret-key", "S3_PREFIX": "shortform-ad-studio/C", "S3_REGION": "auto", "S3_URL_EXPIRES_SEC": "3600"}
        env = patch.dict(os.environ, self.env)
        env.start()
        self.addCleanup(env.stop)
        self.storage = DeliveryStorage()
        self.addCleanup(self.storage.client.close)
        self.files = result_files(str(self.out))

    def uploads(self, stub):
        for name in ("hook.mp4", "tts.mp3", "hook.srt", "scenario.json", "storyboard_01.png"):
            stub.add_response("put_object", {}, {"Bucket": "test-bucket", "Key": f"shortform-ad-studio/C/proj_test/hook_C1/{name}",
                                                "Body": unittest.mock.ANY, "ContentType": CONTENT_TYPES[Path(name).suffix]})

    def test_uploads_only_deliverables_with_media_types_and_signed_urls(self):
        with Stubber(self.storage.client) as stub:
            self.uploads(stub)
            refs = self.storage.publish_files(self.files)
            stub.assert_no_pending_responses()
        urls = self.storage.download_files(refs)
        url = urlsplit(urls["hook_video"])
        query = parse_qs(url.query)
        self.assertEqual(url.path, "/test-bucket/shortform-ad-studio/C/proj_test/hook_C1/hook.mp4")
        self.assertEqual(query["X-Amz-Algorithm"], ["AWS4-HMAC-SHA256"])
        self.assertEqual(query["X-Amz-Expires"], ["3600"])
        self.assertNotIn("test-secret-key", json.dumps(urls))
        self.assertTrue(all(Path(path).is_file() for path in [self.files["hook_video"], self.files["tts_audio"]]))

    def test_local_mode_does_not_construct_an_s3_client(self):
        with patch.dict(os.environ, {"C_STORAGE_BACKEND": "local"}), patch("boto3.client") as client:
            storage = DeliveryStorage()
            self.assertEqual(storage.download_files(storage.publish_files(self.files)), self.files)
            client.assert_not_called()

    def test_missing_configuration_stops_before_rendering(self):
        with patch.dict(os.environ, {"S3_SECRET_ACCESS_KEY": ""}), patch.object(cli, "render_hook") as render, \
                patch.object(cli, "load_env"), patch("sys.argv", ["cli", "hook", "proj_test", "sc_C1"]):
            with self.assertRaisesRegex(StorageError, "S3_SECRET_ACCESS_KEY"):
                cli.main()
            render.assert_not_called()

    def test_paths_outside_output_are_rejected_before_any_upload(self):
        outside = Path(self.temp.name) / "private.mp4"
        outside.write_bytes(b"private")
        with patch.object(self.storage.client, "upload_file") as upload:
            with self.assertRaisesRegex(StorageError, "OUTPUT_DIR"):
                self.storage.publish_files({**self.files, "tts_audio": str(outside)})
            upload.assert_not_called()

    def test_connection_check_is_read_only(self):
        with Stubber(self.storage.client) as stub:
            stub.add_response("list_objects_v2", {"KeyCount": 0}, {"Bucket": "test-bucket", "Prefix": "shortform-ad-studio/C/", "MaxKeys": 1})
            self.storage.check_connection()
            stub.assert_no_pending_responses()

    def test_failed_upload_is_not_done_and_publish_retries_without_rendering(self):
        hook = {"project": "proj_test", "scenario": "sc_C1", "tts": {"enabled": False}, "dir": str(self.out), "files": {}, "error": None}
        project = {"product": {"name": "테스트 제품"}, "assets": {}, "scenarios": [{"scenario_id": "sc_C1"}]}
        with patch.dict(server.DB, {"projects": {"proj_test": project}, "hooks": {"hook_C1": hook}}, clear=True), \
                patch.object(server, "DeliveryStorage", return_value=self.storage), \
                patch.object(server, "render_hook", return_value={**self.files, "problem_engine": "blender"}), \
                contextlib.redirect_stderr(io.StringIO()):
            with Stubber(self.storage.client) as stub:
                stub.add_client_error("put_object", service_error_code="AccessDenied")
                server.run_hook("hook_C1")
            self.assertEqual(hook["status"], "failed")
            self.assertEqual(hook["error"]["code"], "STORAGE_UPLOAD_FAILED")
            self.assertTrue(Path(hook["files"]["hook_video"]).is_file())
            with Stubber(self.storage.client) as stub, patch.object(cli, "DeliveryStorage", return_value=self.storage), \
                    patch.object(cli, "load_env"), patch.object(cli, "render_hook") as render, \
                    patch("sys.argv", ["cli", "publish", "proj_test", "hook_C1"]), contextlib.redirect_stdout(io.StringIO()) as output:
                self.uploads(stub)
                self.assertEqual(cli.main(), 0)
                stub.assert_no_pending_responses()
                render.assert_not_called()
                self.assertIn("X-Amz-Signature", json.loads(output.getvalue())["files"]["hook_video"])

    def test_hook_polling_refreshes_remote_links_without_reuploading(self):
        hook = {"project": "proj_test", "status": "done", "dir": str(self.out), "error": None,
                "files": {"hook_video": "s3://test-bucket/shortform-ad-studio/C/proj_test/hook_C1/hook.mp4"}}
        handler = object.__new__(server.Handler)
        handler.headers = {"Host": "127.0.0.1:8080"}
        handler.storage = self.storage
        with patch.dict(server.DB, {"hooks": {"hook_C1": hook}}, clear=True), \
                patch.object(self.storage.client, "upload_file") as upload, \
                patch.object(self.storage.client, "generate_presigned_url", side_effect=["https://r2/hook.mp4?fresh=1", "https://r2/hook.mp4?fresh=2"]):
            _, first = handler.api("GET", "/v1/projects/proj_test/hooks/hook_C1")
            _, second = handler.api("GET", "/v1/projects/proj_test/hooks/hook_C1")
            self.assertNotEqual(first["files"]["hook_video"], second["files"]["hook_video"])
            self.assertTrue(hook["files"]["hook_video"].startswith("s3://"))
            upload.assert_not_called()

    def test_storyboard_api_uploads_images_before_returning_urls(self):
        frame = {"beat_order": 1, "image_url": str(self.out / "storyboard_01.png"), "caption": "테스트"}
        handler = object.__new__(server.Handler)
        handler.headers = {"Host": "127.0.0.1:8080"}
        handler.storage = self.storage
        with patch.dict(server.DB, {"projects": {"proj_test": {"scenarios": [{"scenario_id": "sc_C1"}], "assets": {}}}}, clear=True), \
                patch.object(server, "storyboard", return_value=[frame]), Stubber(self.storage.client) as stub:
            stub.add_response("put_object", {}, {"Bucket": "test-bucket", "Key": "shortform-ad-studio/C/proj_test/hook_C1/storyboard_01.png",
                                                "Body": unittest.mock.ANY, "ContentType": "image/png"})
            status, body = handler.api("POST", "/v1/projects/proj_test/scenarios/sc_C1/storyboard")
            stub.assert_no_pending_responses()
        self.assertEqual(status, 200)
        self.assertIn("X-Amz-Signature", body["frames"][0]["image_url"])
        self.assertEqual(body["frames"][0]["caption"], "테스트")

    @unittest.skipUnless(shutil.which("node"), "재생기 JavaScript 검증에는 Node.js가 필요합니다.")
    def test_player_preserves_signature_query_without_swallowing_next_field(self):
        # index.html의 <br>로 구분된 텍스트 노드를 재현한다. textContent 전체에는 줄바꿈이 없다.
        script = server.INJECT.replace("__PRESET__", "null").split("<script>", 1)[1].split("</script>", 1)[0]
        harness = r'''
const assert = require("node:assert/strict");
let observer, sources = [];
const url = "https://r2.example/bucket/hook.mp4?X-Amz-Signature=abc&X-Amz-Expires=3600";
const results = {querySelectorAll: () => [{childNodes: [
  {nodeType: 3, textContent: "hook_video: " + url}, {nodeType: 1},
  {nodeType: 3, textContent: "tts_audio: https://r2.example/tts.mp3?X-Amz-Signature=def"}
]}]};
global.location = {search: ""};
global.document = {
  getElementById: id => id === "results" ? results : id === "cPlayer" ? {appendChild: v => sources.push(v.src)} : null,
  createElement: () => ({style: {}})
};
global.MutationObserver = class {constructor(fn) {observer = fn;} observe() {}};
'''
        result = subprocess.run(["node", "-e", harness + script + "\nobserver(); observer(); assert.deepEqual(sources, [url]);"],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
