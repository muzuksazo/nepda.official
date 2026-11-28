"""Unit tests for Track A tiered Planner/Critic orchestrator, direct-cut mode, taboo-filter paradox fix, and catalog metadata."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.config import Settings  # noqa: E402
from app.track_a_templates import _build_catalog_entry, _entries_from_catalog_payload  # noqa: E402
from hookpipe.a_templates import (  # noqa: E402
    TemplateError,
    _resolve_critic_model,
    _resolve_executor_model,
    _resolve_planner_model,
    _split_taboo_keywords,
    _violations,
    make_template_scenario,
)
from tests.support.tempdirs import temporary_directory  # noqa: E402


TAPE_PRODUCT: Dict[str, Any] = {
    "name": "초강력 방수 테이프",
    "brand": "닥터픽스",
    "category": "생활용품",
    "verified_facts": [
        "물 새는 파이프에 감아 즉시 밀봉할 수 있다",
        "실내외 배관과 호스 보수에 사용할 수 있다",
    ],
}


def _make_catalog_dir(root: Path) -> Path:
    lib = root / "track_a_cat"
    templates = [
        {
            "template_id": "a_domino_docu_3d",
            "abstract_law": "작은 힘이 연쇄 증폭되면 거대한 충격을 만든다",
            "genre": "mock_documentary",
            "hook_title": "50층 거대 도미노 물리 실험",
            "tags": ["도미노", "연쇄", "증폭"],
            "beats": [
                {
                    "order": 1,
                    "role": "어긋난 시작",
                    "duration_sec": 9.88,
                    "visual": "Sunlit desert 3D domino chain crashing",
                    "narration": "일 센티미터 도미노를 두 배씩 키워 스무 개만 세우면, 마지막 조각은 아파트 오십 층 높이가 됩니다. 지면에 닿는 순간 지반이 흔들립니다.",
                    "caption": "1cm 도미노를 2배씩\n스무 개만 세우면,",
                    "caption_cues": [
                        "1cm 도미노를 2배씩\n스무 개만 세우면,",
                        "마지막 조각은 아파트 50층\n높이가 됩니다",
                        "지면에 닿는 순간, 반경 1km\n지반이 흔들립니다",
                    ],
                    "shows_product": False,
                    "clip": "a_domino_docu_3d/beat_01.mp4",
                },
                {
                    "order": 2,
                    "role": "패턴 인터럽트",
                    "duration_sec": 0.3,
                    "hold": True,
                    "visual": "정지",
                    "narration": "",
                    "caption": "",
                    "shows_product": False,
                    "clip": None,
                },
            ],
        },
        {
            "template_id": "a_dam_tape_3d",
            "abstract_law": "버티지 못하는 임시방편은 압력이 차오르는 순간 통째로 터진다",
            "genre": "mock_documentary",
            "hook_title": "100톤 수압 댐 균열 테이프 100겹 실험 (3D)",
            "tags": ["누수", "방수", "테이프", "밀봉", "수압"],
            "beats": [
                {
                    "order": 1,
                    "role": "어긋난 시작",
                    "duration_sec": 10.0,
                    "visual": "3D physics experiment inside a towering concrete dam wall with grey strips over a crack",
                    "narration": "댐 균열을 테이프 백 겹으로 막아두면 어떻게 될까요? 수압이 차오르는 순간 딱 삼 초 만에 통째로 터집니다. 임시방편으로 덮기만 하면 결국 더 크게 터집니다.",
                    "caption": "댐 균열을 테이프 100겹으로\n막아두면 어떻게 될까요?",
                    "caption_cues": [
                        "댐 균열을 테이프 100겹으로\n막아두면 어떻게 될까요?",
                        "수압이 차오르는 순간,\n딱 3초 만에 통째로 터집니다",
                        "임시방편으로 덮기만 하면\n결국 더 크게 터집니다",
                    ],
                    "shows_product": False,
                    "clip": "a_dam_tape_3d/beat_01.mp4",
                },
                {
                    "order": 2,
                    "role": "패턴 인터럽트",
                    "duration_sec": 0.3,
                    "hold": True,
                    "visual": "정지",
                    "narration": "",
                    "caption": "",
                    "shows_product": False,
                    "clip": None,
                },
            ],
        },
    ]
    for tpl in templates:
        for b in tpl["beats"]:
            if b.get("clip"):
                p = lib / b["clip"]
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_bytes(b"mp4")
    (lib / "catalog.json").write_text(
        json.dumps({"version": 1, "templates": templates}, ensure_ascii=False),
        encoding="utf-8",
    )
    return lib


def _good_direct_plan(*, front_narration: str | None = None, cues: List[str] | None = None, callback: str | None = None) -> Dict[str, Any]:
    return {
        "abstract_law": "버티지 못하는 임시방편은 압력이 차오르는 순간 한꺼번에 터진다",
        "template_id": "a_dam_tape_3d",
        "bridge_reason": "수압이 몰리는 댐 균열을 대충 덮어 터지는 물리 실험이 배관 누수 밀봉 실물과 바로 이어진다",
        "hook_title": "100톤 수압 댐 균열 100겹 실험",
        "replacement_test_note": "압력 누수 법칙이라 다른 밀폐·보수 제품에도 그대로 적용된다",
        "product_taboo_keywords": ["초강력 방수 테이프", "방수", "테이프", "파이프", "닥터픽스"],
        "front_narration": front_narration
        or "거대한 댐 균열을 접착띠 백 겹으로 덧대 두면 버틸 수 있을까요? 수압이 차오르는 순간 딱 삼 초 만에 통째로 터져 버립니다. 임시방편은 결국 더 크게 무너집니다.",
        "front_caption_cues": cues
        or [
            "댐 균열을 접착띠 100겹으로\n막아두면 어떻게 될까요?",
            "수압이 차오르는 순간,\n딱 3초 만에 통째로 터집니다",
            "임시방편으로 덮기만 하면\n결국 더 크게 무너집니다",
        ],
        "twist_callback_line": callback
        or "죄송해요, 물 새는 파이프 한 번에 감는 거 보여주려고 댐에 백 겹이나 붙였습니다.",
    }


def _pass_verdict() -> Dict[str, Any]:
    return {
        "passed": True,
        "scores": {
            "bridge_logic": 5,
            "tone_and_twist": 5,
            "double_zero_spoiler": 5,
            "visual_single_shot": 5,
            "fact_grounding": 5,
        },
        "defects": [],
        "fix_instructions": "",
    }


def _fail_verdict(defect: str, fix: str) -> Dict[str, Any]:
    return {
        "passed": False,
        "scores": {
            "bridge_logic": 4,
            "tone_and_twist": 2,
            "double_zero_spoiler": 4,
            "visual_single_shot": 5,
            "fact_grounding": 4,
        },
        "defects": [defect],
        "fix_instructions": fix,
    }


class TestTrackACriticOrchestrator(unittest.TestCase):
    def test_config_defaults_restore_direct_cut_and_neon_planner_critic(self) -> None:
        settings = Settings(_env_file=None, gemini_api_key="test")
        self.assertFalse(settings.hook_a_ai_landing)
        self.assertEqual(settings.hook_planner_llm, "gemini-4-neon")
        self.assertEqual(settings.hook_critic_llm, "gemini-4-neon")

        # Workers overlay with explicit=False should still route planner/critic to Neon, executor to Hydrogen
        overlay = SimpleNamespace(
            hook_planner_llm="gemini-4-neon",
            hook_critic_llm="gemini-4-neon",
            hook_worker_llm="gemini-4-hydrogen",
            _resolved_llm_model="gemini-4-hydrogen",
            _resolved_llm_explicit=False,
        )
        self.assertEqual(_resolve_planner_model(overlay, "gemini-4-hydrogen"), "gemini-4-neon")
        self.assertEqual(_resolve_critic_model(overlay), "gemini-4-neon")
        self.assertEqual(_resolve_executor_model(overlay, "gemini-4-hydrogen"), "gemini-4-hydrogen")

        # Explicit A/B override should be honored
        explicit_overlay = SimpleNamespace(
            hook_planner_llm="gemini-4-neon",
            hook_critic_llm="gemini-4-neon",
            hook_worker_llm="gemini-4-hydrogen",
            _resolved_llm_model="gemini-4-hydrogen",
            _resolved_llm_explicit=True,
        )
        self.assertEqual(_resolve_planner_model(explicit_overlay, "gemini-4-hydrogen"), "gemini-4-hydrogen")

    def test_direct_cut_default_emits_two_beats_and_shared_contract_fields(self) -> None:
        with temporary_directory() as td:
            lib = _make_catalog_dir(Path(td))
            settings = Settings(_env_file=None, hook_a_templates=str(lib))
            inp = {"project_id": "prj_direct01", "round": 1, "product_info": TAPE_PRODUCT, "previous_scenarios": []}
            calls: List[str] = []

            def fake_plan(_sys: str, _prompt: str) -> Dict[str, Any]:
                calls.append("plan")
                return _good_direct_plan()

            def fake_critic(_sys: str, _prompt: str) -> Dict[str, Any]:
                calls.append("critic")
                return _pass_verdict()

            def fake_exec(_sys: str, _prompt: str) -> Dict[str, Any]:
                calls.append("exec")
                return _good_direct_plan()

            out = make_template_scenario(
                inp,
                settings,
                None,
                Path(td) / "work",
                planner=fake_plan,
                critic=fake_critic,
                executor=fake_exec,
            )
            s = out["scenarios"][0]
            self.assertEqual(calls, ["plan", "critic"])
            self.assertEqual(len(s["beats"]), 2)
            self.assertAlmostEqual(s["hook_duration_sec"], 10.3, places=2)

            b1, b2 = s["beats"]
            self.assertEqual(b1["role"], "어긋난 시작")
            self.assertTrue(b1["prebuilt_clip"].endswith("a_dam_tape_3d/beat_01.mp4"))
            self.assertFalse(b1["shows_product"])
            self.assertEqual(len(b1["caption_cues"]), 3)
            self.assertEqual(b1["caption"], b1["caption_cues"][0])

            self.assertEqual(b2["role"], "패턴 인터럽트")
            self.assertTrue(b2["hold"])
            self.assertAlmostEqual(b2["duration_sec"], 0.3, places=2)
            self.assertEqual(b2["visual"], "정지")
            self.assertEqual(b2["narration"], "")
            self.assertEqual(b2["caption"], "")
            self.assertNotIn("prebuilt_clip", b2)

            spec = s["ad_spec"]
            self.assertEqual(spec["template_id"], "a_dam_tape_3d")
            self.assertEqual(spec["track_a_template_id"], "a_dam_tape_3d")
            self.assertTrue(spec["twist_callback_line"])
            self.assertTrue(spec["abstract_law"])
            self.assertFalse(spec["ai_landing"])
            self.assertTrue(spec["critic_verdict"]["passed"])

    def test_taboo_filter_paradox_allows_matching_template_and_paraphrases_beat1(self) -> None:
        with temporary_directory() as td:
            lib = _make_catalog_dir(Path(td))
            catalog = json.loads((lib / "catalog.json").read_text(encoding="utf-8"))
            dam_tpl = next(t for t in catalog["templates"] if t["template_id"] == "a_dam_tape_3d")

            strict, overlapping = _split_taboo_keywords(
                TAPE_PRODUCT,
                ["초강력 방수 테이프", "방수", "테이프", "파이프", "닥터픽스"],
                dam_tpl,
            )
            self.assertIn("테이프", overlapping)
            self.assertNotIn("테이프", strict)
            self.assertIn("초강력 방수 테이프", strict)
            self.assertIn("닥터픽스", strict)
            self.assertIn("방수", strict)
            self.assertIn("파이프", strict)

            # Even before paraphrase, _violations must NOT disqualify a_dam_tape_3d for generic '테이프'
            unparaphrased = _good_direct_plan(
                front_narration="거대한 댐 균열을 테이프 백 겹으로 덧대 두면 버틸 수 있을까요? 수압이 차오르는 순간 딱 삼 초 만에 통째로 터집니다. 임시방편은 결국 더 크게 무너집니다.",
                cues=[
                    "댐 균열을 테이프 100겹으로\n막아두면 어떻게 될까요?",
                    "수압이 차오르는 순간,\n딱 3초 만에 통째로 터집니다",
                ],
            )
            settings = Settings(_env_file=None, hook_a_templates=str(lib))
            inp = {"project_id": "prj_paradox", "round": 1, "product_info": TAPE_PRODUCT, "previous_scenarios": []}
            exec_prompts: List[str] = []

            def fake_plan(_sys: str, _prompt: str) -> Dict[str, Any]:
                return unparaphrased

            def fake_critic(_sys: str, _prompt: str) -> Dict[str, Any]:
                return _pass_verdict()

            def fake_exec(_sys: str, prompt: str) -> Dict[str, Any]:
                exec_prompts.append(prompt)
                return _good_direct_plan()

            out = make_template_scenario(
                inp,
                settings,
                None,
                Path(td) / "work",
                planner=fake_plan,
                critic=fake_critic,
                executor=fake_exec,
            )
            s = out["scenarios"][0]
            # Matching template a_dam_tape_3d won AND Hydrogen paraphrased '테이프' -> '접착띠'
            self.assertEqual(s["ad_spec"]["template_id"], "a_dam_tape_3d")
            self.assertEqual(s["ad_spec"]["track_a_template_id"], "a_dam_tape_3d")
            self.assertEqual(len(exec_prompts), 1)
            self.assertIn("테이프", exec_prompts[0])
            self.assertIn("접착띠", exec_prompts[0])
            self.assertNotIn("테이프", s["beats"][0]["narration"])
            self.assertIn("접착띠", s["beats"][0]["narration"])

            # Strict spoiler leak (brand or exact product name or '방수') MUST still fail _violations
            leaked_scenario = {
                **s,
                "beats": [
                    {**s["beats"][0], "narration": "거대한 댐 균열을 닥터픽스 방수 소재 백 겹으로 덧대 두면 어떻게 될까요? 수압이 차오르는 순간 통째로 터집니다."},
                    s["beats"][1],
                ],
            }
            errs = _violations(
                leaked_scenario,
                ["초강력 방수 테이프", "방수", "테이프", "닥터픽스"],
                ai_landing=False,
                template=dam_tpl,
                product=TAPE_PRODUCT,
            )
            self.assertTrue(any("스포일러" in e for e in errs), errs)

    def test_critic_loop_repairs_cliche_and_caps_at_max_two_revisions(self) -> None:
        with temporary_directory() as td:
            lib = _make_catalog_dir(Path(td))
            settings = Settings(_env_file=None, hook_a_templates=str(lib))
            inp = {"project_id": "prj_revise", "round": 1, "product_info": TAPE_PRODUCT, "previous_scenarios": []}

            # Case 1: Critic fails once + deterministic C-track cliché fails -> Hydrogen repairs -> Critic passes
            bad_draft = _good_direct_plan(callback="물 새는 파이프에 딱 좋아요! 완벽 방수 강력 추천합니다.")
            critic_calls = 0
            exec_calls = 0

            def critic_then_pass(_sys: str, prompt: str) -> Dict[str, Any]:
                nonlocal critic_calls
                critic_calls += 1
                if critic_calls == 1:
                    self.assertIn("딱 좋아요", prompt)
                    return _fail_verdict("C안식 클리셰와 미검증 과장('완벽 방수')", "능청스러운 반전 콜백 한 문장으로 고치세요.")
                return _pass_verdict()

            def exec_fix(_sys: str, prompt: str) -> Dict[str, Any]:
                nonlocal exec_calls
                exec_calls += 1
                self.assertIn("딱 좋아요", prompt)
                return _good_direct_plan()

            out = make_template_scenario(
                inp,
                settings,
                None,
                Path(td) / "work1",
                planner=lambda _s, _p: bad_draft,
                critic=critic_then_pass,
                executor=exec_fix,
            )
            self.assertEqual(critic_calls, 2)
            self.assertEqual(exec_calls, 1)
            self.assertEqual(out["scenarios"][0]["ad_spec"]["critic_verdict"]["revisions"], 1)

            # Case 2: Persistent critic failure stops strictly after 2 revisions (1 plan + 3 critic + 2 revise)
            counts = {"plan": 0, "critic": 0, "exec": 0}

            def always_plan(_s: str, _p: str) -> Dict[str, Any]:
                counts["plan"] += 1
                return _good_direct_plan()

            def always_fail(_s: str, _p: str) -> Dict[str, Any]:
                counts["critic"] += 1
                return _fail_verdict("반전 톤 부족", "더 능청스럽게 고치세요.")

            def always_exec(_s: str, _p: str) -> Dict[str, Any]:
                counts["exec"] += 1
                return _good_direct_plan()

            with self.assertRaises(TemplateError):
                make_template_scenario(
                    inp,
                    settings,
                    None,
                    Path(td) / "work2",
                    planner=always_plan,
                    critic=always_fail,
                    executor=always_exec,
                )
            self.assertEqual(counts, {"plan": 1, "critic": 3, "exec": 2})

    def test_ai_landing_opt_in_enforces_three_beat_and_3_5_to_4_5s_landing(self) -> None:
        with temporary_directory() as td:
            lib = _make_catalog_dir(Path(td))
            settings = Settings(_env_file=None, hook_a_templates=str(lib), hook_a_ai_landing=True)
            inp = {"project_id": "prj_optin", "round": 1, "product_info": TAPE_PRODUCT, "previous_scenarios": []}

            good_landing_plan = {
                **_good_direct_plan(),
                "landing": {
                    "duration_sec": 4.0,
                    "visual": "Close-up single shot of hands wrapping black waterproof tape around a leaking metal pipe under natural daylight.",
                    "narration": "물 새는 파이프에 감아 즉시 밀봉합니다.",
                    "caption": "물 새는 파이프 즉시 밀봉",
                },
            }
            out = make_template_scenario(
                inp,
                settings,
                None,
                Path(td) / "work",
                planner=lambda _s, _p: good_landing_plan,
                critic=lambda _s, _p: _pass_verdict(),
                executor=lambda _s, _p: good_landing_plan,
            )
            s = out["scenarios"][0]
            self.assertEqual(len(s["beats"]), 3)
            self.assertAlmostEqual(s["hook_duration_sec"], 14.3, places=2)
            self.assertTrue(s["beats"][2]["shows_product"])
            self.assertEqual(s["beats"][2]["role"], "담백한 실물 착지")
            self.assertTrue(s["ad_spec"]["ai_landing"])

            # 6.0s landing exceeds 3.5-4.5s rule when hook_a_ai_landing=True
            too_long_scenario = {
                **s,
                "beats": [s["beats"][0], s["beats"][1], {**s["beats"][2], "duration_sec": 6.0}],
            }
            errs = _violations(too_long_scenario, ["방수"], ai_landing=True, product=TAPE_PRODUCT)
            self.assertTrue(any("3.5~4.5초" in e for e in errs), errs)

    def test_usage_telemetry_records_neon_plan_critic_and_hydrogen_revise(self) -> None:
        with temporary_directory() as td:
            lib = _make_catalog_dir(Path(td))
            usage_events: List[Dict[str, Any]] = []
            settings = SimpleNamespace(
                hook_a_templates=str(lib),
                hook_a_ai_landing=False,
                hook_planner_llm="gemini-4-neon",
                hook_critic_llm="gemini-4-neon",
                hook_worker_llm="gemini-4-hydrogen",
                _resolved_llm_model="gemini-4-hydrogen",
                _resolved_llm_explicit=False,
                _on_usage=lambda **kw: usage_events.append(kw),
            )
            responses = [
                # 1) Neon Plan (deliberately has C-track cliché to trigger 1 Hydrogen revise)
                json.dumps(_good_direct_plan(callback="물 새는 파이프에 딱 좋아요!"), ensure_ascii=False),
                # 2) Neon Critic fails draft
                json.dumps(_fail_verdict("C안식 클리셰", "재치 있는 반전 콜백으로 교체"), ensure_ascii=False),
                # 3) Hydrogen Revise repairs draft
                json.dumps(_good_direct_plan(), ensure_ascii=False),
                # 4) Neon Critic passes revised draft
                json.dumps(_pass_verdict(), ensure_ascii=False),
            ]
            call_models: List[str] = []

            class FakeModels:
                def generate_content(self, *, model: str, contents: str, config: Any) -> Any:
                    idx = len(call_models)
                    call_models.append(model)
                    return SimpleNamespace(
                        text=responses[idx],
                        usage_metadata=SimpleNamespace(
                            prompt_token_count=1000 + idx * 100,
                            candidates_token_count=300 + idx * 50,
                            cached_content_token_count=0,
                            thoughts_token_count=200 if "neon" in model else 0,
                        ),
                    )

            fake_client = SimpleNamespace(models=FakeModels())
            inp = {"project_id": "prj_tel_a", "round": 1, "product_info": TAPE_PRODUCT, "previous_scenarios": []}
            with patch("app.genai_provider.build_genai_client", return_value=fake_client):
                out = make_template_scenario(
                    inp,
                    settings,
                    None,
                    Path(td) / "work",
                    model_override="gemini-4-hydrogen",  # simulates workers.py non-explicit overlay
                )

            self.assertEqual(out["scenarios"][0]["ad_spec"]["template_id"], "a_dam_tape_3d")
            self.assertEqual(
                call_models,
                ["gemini-4-neon", "gemini-4-neon", "gemini-4-hydrogen", "gemini-4-neon"],
            )
            self.assertEqual(len(usage_events), 4)
            self.assertEqual(
                [(e["stage"], e["step_name"], e["model"]) for e in usage_events],
                [
                    ("a_template", "plan_template", "gemini-4-neon"),
                    ("a_template", "critic_gate", "gemini-4-neon"),
                    ("a_template", "execute_revise", "gemini-4-hydrogen"),
                    ("a_template", "critic_gate", "gemini-4-neon"),
                ],
            )
            self.assertEqual(usage_events[0]["input_tokens"], 1000)
            self.assertEqual(usage_events[0]["output_tokens"], 300)
            self.assertEqual(usage_events[0]["thinking_tokens"], 200)
            self.assertEqual(usage_events[2]["thinking_tokens"], 0)

    def test_build_catalog_entry_populates_narration_and_caption_cues_and_manifest_office_fix(self) -> None:
        entry = {
            "id": "a_demo_physics",
            "title": "도미노 물리 실험",
            "duration_sec": 9.88,
            "a_genre_archetype": "mock_documentary",
            "tags": ["도미노", "스케일"],
            "visual_summary": "Desert 3D domino physics chain",
            "default_hook_captions": [
                "1cm 도미노를 2배씩 키워\n**스무 개만** 세우면,",
                "마지막 조각은 **아파트 50층**\n높이가 됩니다",
                "지면에 닿는 순간, 반경 1km\n**지반이 흔들립니다**",
            ],
        }
        cat_item = _build_catalog_entry(entry)
        b1, b2 = cat_item["beats"]
        self.assertTrue(b1["narration"])
        self.assertIn("스무 개만", b1["narration"])
        self.assertIn("지반이 흔들립니다", b1["narration"])
        self.assertNotIn("**", b1["narration"])
        self.assertEqual(len(b1["caption_cues"]), 3)
        self.assertFalse(b1["shows_product"])
        self.assertTrue(b2["hold"])
        self.assertFalse(b2["shows_product"])

        # Round-trip hydration preserves all caption cues
        roundtrip = _entries_from_catalog_payload({"version": 1, "templates": [cat_item]})
        self.assertEqual(len(roundtrip[0]["default_hook_captions"]), 3)

        # Manifest fix for a_office_revenge_drama: white document/letter instead of golden card
        manifest_path = ROOT / "backend" / "data" / "templates" / "track_a" / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        office = next(e for e in manifest if e.get("id") == "a_office_revenge_drama")
        self.assertNotIn("golden card", office["visual_summary"].lower())
        self.assertIn("white document", office["visual_summary"].lower())
        captions_joined = " ".join(office["default_hook_captions"])
        self.assertNotIn("한 장의 카드", captions_joined)
        self.assertIn("한 장의 서류", captions_joined)


if __name__ == "__main__":
    unittest.main()
