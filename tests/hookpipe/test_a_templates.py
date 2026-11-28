"""hookpipe · A 템플릿: 미리 만든 앞부분 + 요청마다 착지 장면. 모델·저장소는 대역 (과금 없음)."""

import json
import shutil
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List
from unittest.mock import patch

from tests.support.hookpipe import FakeMediaProvider, make_video, tools_or_none
from tests.support.tempdirs import temporary_directory

from app.config import Settings
from app.storage import build_hook_a_storage
from hookpipe import readiness as hookpipe_readiness
from hookpipe.a_templates import TemplateError, load_catalog, make_template_scenario
from hookpipe.media import probe
from hookpipe.render import render_hook
from hookpipe.service import HookPipeline
from hookpipe.workers import make_scenario_generator

TOOLS = tools_or_none()
PRODUCT = {"name": "물기제거 스펀지", "verified_facts": ["회색 직사각형 스펀지로, 한 손에 쥐어지는 크기다",
                                                   "세면대 가장자리에 남은 물기를 문질러 닦아 낸다"]}


def _template(tid: str, law: str) -> Dict[str, Any]:
    return {
        "template_id": tid,
        "abstract_law": law,
        "genre": "extreme_physics_experiment",
        "hook_title": "유리 바닥을 바깥부터 깨면",
        "beats": [
            {"order": 1, "role": "어긋난 시작", "duration_sec": 5.0, "visual": "유리 바닥 위 쇠구슬",
             "narration": "유리 바닥을 바깥부터 깨 봤습니다.", "caption": "바깥부터 깨면?", "clip": f"{tid}/beat_01.mp4"},
            {"order": 2, "role": "빌드업", "duration_sec": 6.0, "visual": "구슬이 한 점으로 모인다",
             "narration": "구슬이 알아서 한 점으로 모입니다.", "caption": "한 점으로", "clip": f"{tid}/beat_02.mp4"},
            {"order": 3, "role": "패턴 인터럽트", "duration_sec": 0.3, "visual": "정지", "narration": "", "caption": "",
             "clip": None},
        ],
    }


def _library(root: Path, tools: Any = None) -> Path:
    lib = root / "a_lib"
    templates = [_template("glass_01", "면적이 줄면 한 점으로 모인다"), _template("sand_02", "흘러내린 것은 한 번에 걷힌다")]
    for t in templates:
        for b in t["beats"]:
            if b["clip"]:
                target = lib / b["clip"]
                target.parent.mkdir(parents=True, exist_ok=True)
                if tools:
                    make_video(tools, target, seconds=b["duration_sec"], audio=False)
                else:
                    target.write_bytes(b"clip")
    (lib / "catalog.json").write_text(json.dumps({"version": 1, "templates": templates}, ensure_ascii=False), encoding="utf-8")
    return lib


def _writer(picks: List[Dict[str, Any]], seen: List[str]):
    def write(system: str, prompt: str) -> Dict[str, Any]:
        seen.append(prompt)
        return picks[min(len(seen), len(picks)) - 1]
    return write


GOOD = {
    "abstract_law": "흩어진 것이 한 번에 걷힌다", "template_id": "glass_01", "hook_title": "유리 바닥을 바깥부터 깨면",
    "replacement_test_note": "앞부분은 법칙만 보여 줘 다른 제품에도 붙는다", "product_taboo_keywords": ["스펀지", "세면대"],
    "landing": {"duration_sec": 5.0, "visual": "회색 스펀지로 세면대 가장자리를 쓱 닦는 손",
                "narration": "물기제거 스펀지로 가장자리를 한 번에 닦습니다.", "caption": "한 번에 쓱"},
}


class TemplateScenario(unittest.TestCase):
    def test_picks_a_template_and_writes_only_the_landing_beat(self) -> None:
        with temporary_directory() as td:
            lib = _library(Path(td))
            settings = SimpleNamespace(hook_a_templates=str(lib))
            seen: List[str] = []
            inp = {"project_id": "proj_x01", "round": 1, "product_info": PRODUCT, "previous_scenarios": []}
            result = make_template_scenario(inp, settings, None, Path(td) / "work", writer=_writer([GOOD], seen))
            s = result["scenarios"][0]
            self.assertEqual(s["type"], "A")
            self.assertEqual(s["ad_spec"]["template_id"], "glass_01")
            self.assertEqual(s["ad_spec"]["source"], "template")
            self.assertAlmostEqual(s["hook_duration_sec"], 16.3)
            self.assertEqual([b["order"] for b in s["beats"]], [1, 2, 3, 4])
            self.assertTrue(s["beats"][0]["prebuilt_clip"].endswith("beat_01.mp4"))
            self.assertNotIn("prebuilt_clip", s["beats"][2])  # 0.3초 정지 장면은 앞 장면을 멈춘다
            self.assertNotIn("prebuilt_clip", s["beats"][3])  # 착지 장면은 요청마다 만든다
            self.assertIn("회색 직사각형 스펀지", seen[0])
            self.assertIn("glass_01", seen[0])

    def test_rule_violations_are_sent_back_and_retried(self) -> None:
        with temporary_directory() as td:
            lib = _library(Path(td))
            settings = SimpleNamespace(hook_a_templates=str(lib))
            unknown = dict(GOOD, template_id="nope")
            too_long = dict(GOOD, landing=dict(GOOD["landing"], duration_sec=9.5))
            inp = {"project_id": "proj_x01", "round": 1, "product_info": PRODUCT, "previous_scenarios": []}
            seen: List[str] = []
            ok = make_template_scenario(inp, settings, None, Path(td), writer=_writer([unknown, GOOD], seen))
            self.assertEqual(ok["scenarios"][0]["ad_spec"]["template_id"], "glass_01")
            self.assertIn("목록에 없는 template_id", seen[1])
            with self.assertRaises(TemplateError):
                make_template_scenario(inp, settings, None, Path(td), writer=_writer([too_long, too_long], []))

    def test_previous_templates_are_offered_last(self) -> None:
        with temporary_directory() as td:
            lib = _library(Path(td))
            settings = SimpleNamespace(hook_a_templates=str(lib))
            seen: List[str] = []
            prev = [{"type": "A", "ad_spec": {"template_id": "glass_01"}}]
            inp = {"project_id": "proj_x01", "round": 2, "product_info": PRODUCT, "previous_scenarios": prev}
            make_template_scenario(inp, settings, None, Path(td), writer=_writer([dict(GOOD, template_id="sand_02")], seen))
            self.assertNotIn("glass_01 |", seen[0])

    def test_catalog_is_read_from_storage_keys(self) -> None:
        with temporary_directory() as td:
            lib = _library(Path(td))
            downloads: List[str] = []

            class Storage:
                def download_file(self, key: str, dest: Any) -> str:
                    downloads.append(key)
                    Path(dest).parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(lib / key.split("templates/a/", 1)[1], dest)
                    return str(dest)

            settings = SimpleNamespace(hook_a_templates="storage:templates/a")
            catalog = load_catalog(settings, Storage(), Path(td) / "work")
            self.assertEqual(downloads, ["templates/a/catalog.json"])
            self.assertEqual(len(catalog["templates"]), 2)
            inp = {"project_id": "proj_x01", "round": 1, "product_info": PRODUCT, "previous_scenarios": []}
            s = make_template_scenario(inp, settings, Storage(), Path(td) / "work", writer=_writer([GOOD], []))["scenarios"][0]
            self.assertEqual(s["beats"][0]["prebuilt_clip"], "templates/a/glass_01/beat_01.mp4")

    def test_missing_catalog_falls_back_to_the_realtime_worker(self) -> None:
        realtime: List[str] = []

        def node_worker(worker_input: Dict[str, Any], settings: Any) -> Dict[str, Any]:
            realtime.append(worker_input["hook_type"])
            return {"scenarios": []}

        class EmptyStorage:
            def download_file(self, key: str, dest: Any) -> str:
                raise FileNotFoundError(key)

        settings = SimpleNamespace(hook_a_templates="storage:templates/a", hook_a_mode="template", hook_worker_mode="auto",
                                   hook_max_sec=20.0, work_root="")
        store = SimpleNamespace(list_scenarios=lambda pid: [])
        gen = make_scenario_generator(settings, store, workers={"A": node_worker}, storage=EmptyStorage(),
                                      fallback=lambda p, t, prov: [{"scenario_id": "planner", "type": "A"}])
        gen({"project_id": "proj_x01", "product": PRODUCT}, ["A"], "anthropic")
        self.assertEqual(realtime, ["A"])


@unittest.skipUnless(TOOLS, "ffmpeg 가 필요합니다")
class TemplateRender(unittest.TestCase):
    def test_template_hook_buys_a_clip_only_for_the_landing_beat(self) -> None:
        with temporary_directory() as td:
            root = Path(td)
            lib = _library(root, TOOLS)
            settings = SimpleNamespace(hook_a_templates=str(lib), hook_assets_dir=str(root / "assets"),
                                       output_dir=str(root / "out"), hook_max_sec=20.0, hook_clip_resolution="720p",
                                       hook_burn_captions=True, hook_max_clip_sec_per_hook=45, video_model="fake",
                                       tts_model="fake", ffmpeg_bin=None, ffprobe_bin=None)
            inp = {"project_id": "proj_x01", "round": 1, "product_info": PRODUCT, "previous_scenarios": []}
            scenario = make_template_scenario(inp, settings, None, root, writer=_writer([GOOD], []))["scenarios"][0]
            pipeline = HookPipeline(settings, None, None, SimpleNamespace(download_file=lambda k, d: None))
            provider = FakeMediaProvider(TOOLS)
            result = render_hook(scenario, PRODUCT, root / "hook", provider=provider, settings=settings, tools=TOOLS,
                                 resolve_asset=lambda ref: pipeline.resolve_asset(ref, root / "work"))
            self.assertEqual([c["duration_sec"] for c in provider.video_calls], [5])  # 착지 장면 하나만
            self.assertEqual([b["prebuilt"] for b in result.beats], [True, True, False, False])
            self.assertEqual(len(provider.tts_calls), 3)  # 앞부분 나레이션도 같은 목소리로 새로 만든다
            self.assertAlmostEqual(probe(TOOLS, root / "hook" / "hook.mp4").duration, 16.3, delta=0.3)


class DedicatedHookAR2Tests(unittest.TestCase):
    def test_build_hook_a_storage_returns_fallback_when_unset(self) -> None:
        settings = Settings(storage_backend="local", gemini_api_key="test")
        fallback = object()
        self.assertIs(build_hook_a_storage(settings, fallback), fallback)  # type: ignore[arg-type]

    def test_build_hook_a_storage_uses_dedicated_r2_settings_and_strips_bucket_suffix(self) -> None:
        calls: List[Dict[str, Any]] = []

        def fake_boto_client(service: str, **kwargs: Any) -> object:
            calls.append({"service": service, **kwargs})
            return object()

        settings = Settings(
            storage_backend="r2",
            s3_bucket="main-bucket",
            s3_endpoint_url="https://main.r2.cloudflarestorage.com",
            s3_access_key_id="main-key",
            s3_secret_access_key="main-secret",
            s3_prefix="main-prefix",
            hook_a_r2_bucket="track-a-bucket",
            hook_a_r2_endpoint_url="https://owner2.r2.cloudflarestorage.com/track-a-bucket/",
            hook_a_r2_access_key_id="owner2-key",
            hook_a_r2_secret_access_key="owner2-secret",
            hook_a_r2_prefix="/custom-a/",
        )
        with patch.dict(sys.modules, {"boto3": SimpleNamespace(client=fake_boto_client)}):
            backend = build_hook_a_storage(settings, object())  # type: ignore[arg-type]

        self.assertEqual(backend.bucket, "track-a-bucket")  # type: ignore[attr-defined]
        self.assertEqual(backend.prefix, "custom-a")  # type: ignore[attr-defined]
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["endpoint_url"], "https://owner2.r2.cloudflarestorage.com")
        self.assertEqual(calls[0]["aws_access_key_id"], "owner2-key")
        self.assertEqual(calls[0]["aws_secret_access_key"], "owner2-secret")
        self.assertEqual(calls[0]["region_name"], "auto")

    def test_resolve_asset_routes_track_a_keys_to_template_storage(self) -> None:
        with temporary_directory() as td:
            root = Path(td)
            main_calls: List[str] = []
            tpl_calls: List[str] = []

            class DummyStorage:
                def __init__(self, log: List[str], payload: bytes) -> None:
                    self._log = log
                    self._payload = payload

                def download_file(self, key: str, dest: Any) -> str:
                    self._log.append(key)
                    p = Path(dest)
                    p.parent.mkdir(parents=True, exist_ok=True)
                    p.write_bytes(self._payload)
                    return str(p)

            main_storage = DummyStorage(main_calls, b"main")
            tpl_storage = DummyStorage(tpl_calls, b"tpl")
            settings = SimpleNamespace(
                hook_a_templates="storage:templates/a",
                hook_assets_dir=str(root / "assets"),
                output_dir=str(root / "out"),
                tts_provider="gemini",
            )
            pipe = HookPipeline(settings, None, None, main_storage, template_storage=tpl_storage)

            p1 = pipe.resolve_asset("templates/a/glass_01/beat_01.mp4", root / "w1")
            p2 = pipe.resolve_asset("other/asset.mp4", root / "w2")
            self.assertIsNotNone(p1)
            self.assertEqual(p1.read_bytes(), b"tpl")  # type: ignore[union-attr]
            self.assertIsNotNone(p2)
            self.assertEqual(p2.read_bytes(), b"main")  # type: ignore[union-attr]
            self.assertEqual(tpl_calls, ["templates/a/glass_01/beat_01.mp4"])
            self.assertEqual(main_calls, ["other/asset.mp4"])

    def test_readiness_uses_template_storage_and_validates_missing_fields(self) -> None:
        with temporary_directory() as td:
            lib = _library(Path(td))

            class FakeTplStorage:
                def download_file(self, key: str, dest: Any) -> str:
                    shutil.copyfile(lib / key.split("templates/a/", 1)[1], dest)
                    return str(dest)

            class FakeModels:
                def get(self, *, model: str) -> object:
                    return {"name": model}

            fake_client = SimpleNamespace(models=FakeModels())
            bad_settings = Settings(
                storage_backend="r2",
                google_genai_use_vertexai=True,
                hook_worker_llm="gemini-4-hydrogen",
                hook_a_mode="template",
                hook_a_templates="storage:templates/a",
                hook_a_r2_bucket="track-a-bucket",
                session_secret="not-default-secret",
                tts_provider="gemini",
            )
            with patch("app.genai_provider.build_genai_client", return_value=fake_client):
                res = hookpipe_readiness.check(
                    bad_settings,
                    object(),
                    deep=True,
                    template_storage=FakeTplStorage(),
                )
            self.assertEqual(res["config"]["hook_a_storage"], "dedicated_r2")
            self.assertEqual(res["config"]["hook_a_r2_bucket"], "track-a-bucket")
            self.assertEqual(res["deep"]["a_templates"], 2)
            self.assertTrue(any("HOOK_A_R2_ENDPOINT_URL" in p for p in res["problems"]))
            self.assertNotIn("owner2-secret", json.dumps(res))


if __name__ == "__main__":
    unittest.main()
