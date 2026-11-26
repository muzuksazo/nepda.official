"""hookpipe · 과금·ffmpeg 없이 확인하는 규칙: 자막, 본편 길이 배분, 제품 장면 판정, 작업자 연결."""

import unittest
from types import SimpleNamespace
from typing import Any, Dict, List

from fastapi import HTTPException

from tests.support.hookpipe import BACKEND, worker_scenario

from hookpipe.body import plan_body_segments
from hookpipe.captions import build_srt, srt_timestamp, wrap_caption
from hookpipe.prompts import beat_prompt, ordered_beats, product_beat_orders
from hookpipe.service import is_worker_scenario
from hookpipe.workers import (
    WorkerError,
    _import_c_generate,
    build_worker_input,
    make_scenario_generator,
    normalize_scenarios,
)


def _settings(**overrides: Any) -> SimpleNamespace:
    base = dict(hook_worker_mode="auto", hook_max_sec=20.0, hook_workers_dir=str(BACKEND / "bridge-dev"),
                hook_worker_timeout_sec=5.0)
    base.update(overrides)
    return SimpleNamespace(**base)


class _Store:
    def __init__(self, scenarios: List[Dict[str, Any]] | None = None) -> None:
        self.scenarios = scenarios or []

    def list_scenarios(self, project_id: str) -> List[Dict[str, Any]]:
        return list(self.scenarios)


PROJECT = {
    "project_id": "proj_demo01",
    "scenario_round": 0,
    "product": {
        "name": "60분 비주얼 타이머",
        "category": "stationery",
        "verified_facts": ["60분형 아날로그 타이머", " "],
        "price_or_offer": None,
        "target_audience": "",
    },
}


class CaptionRules(unittest.TestCase):
    def test_wraps_to_22_chars_and_two_lines(self) -> None:
        wrapped = wrap_caption("숫자를 읽지 않아도 남은 시간이 한눈에 보이는 빨간 원판 타이머입니다 정말로요 " * 2)
        lines = wrapped.split("\n")
        self.assertLessEqual(len(lines), 2)
        self.assertTrue(all(len(line) <= 22 for line in lines), lines)
        self.assertTrue(lines[-1].endswith("…"))
        self.assertEqual(wrap_caption("짧은 자막"), "짧은 자막")
        self.assertEqual(wrap_caption("가" * 30).split("\n")[0], "가" * 22)

    def test_timestamps_do_not_lose_a_second_near_rounding_edges(self) -> None:
        self.assertEqual(srt_timestamp(9.999999999999998), "00:00:10,000")
        self.assertEqual(srt_timestamp(2.9996), "00:00:03,000")
        self.assertEqual(srt_timestamp(3725.5), "01:02:05,500")

    def test_srt_skips_empty_captions_and_numbers_the_rest(self) -> None:
        srt = build_srt([(0.0, 3.0, "첫 줄"), (3.0, 6.0, ""), (6.0, 9.0, "셋째 줄")])
        self.assertIn("1\n00:00:00,000 --> 00:00:03,000\n첫 줄", srt)
        self.assertIn("2\n00:00:06,000 --> 00:00:09,000\n셋째 줄", srt)
        self.assertNotIn("3\n", srt)


class BodyAndPromptRules(unittest.TestCase):
    def test_body_is_shortened_proportionally_only_when_over_the_limit(self) -> None:
        self.assertEqual(plan_body_segments([4.0, 6.0], 20.0), [4.0, 6.0])
        self.assertEqual(plan_body_segments([4.0, 6.0], None), [4.0, 6.0])
        cut = plan_body_segments([10.0, 30.0], 13.0)
        self.assertAlmostEqual(sum(cut), 13.0, places=2)
        self.assertAlmostEqual(cut[0] / cut[1], 10.0 / 30.0, places=2)

    def test_product_beats_by_hook_type(self) -> None:
        b = worker_scenario("B")
        self.assertEqual(product_beat_orders(b), [3])
        a = worker_scenario("A")
        a["ad_spec"] = {"track_archetype": "A_bgrade_reversal"}
        self.assertEqual(product_beat_orders(a), [3])
        c = worker_scenario("C")
        c["ad_spec"] = {}
        c["beats"][0]["role"] = "문제"
        self.assertEqual(product_beat_orders(c), [2, 3])

    def test_product_prompt_requires_matching_the_reference_only_when_one_exists(self) -> None:
        scenario = worker_scenario("B")
        beat = ordered_beats(scenario)[-1]
        product = PROJECT["product"]
        with_ref = beat_prompt(scenario, beat, 3, 3, product=product, shows_product=True, has_product_reference=True)
        without = beat_prompt(scenario, beat, 3, 3, product=product, shows_product=True, has_product_reference=False)
        self.assertIn("EXACTLY like the product in the reference photos", with_ref)
        self.assertNotIn("reference photos", without)
        self.assertIn("60분형 아날로그 타이머", without)
        story = beat_prompt(scenario, ordered_beats(scenario)[0], 1, 3, product=product, shows_product=False)
        self.assertNotIn("60분 비주얼 타이머", story)

    def test_only_scenarios_without_a_timeline_use_hookpipe(self) -> None:
        self.assertTrue(is_worker_scenario(worker_scenario()))
        legacy = worker_scenario()
        legacy["ad_spec"] = {"timeline": [{"id": "x"}]}
        self.assertFalse(is_worker_scenario(legacy))
        self.assertFalse(is_worker_scenario(None))


class WorkerConnection(unittest.TestCase):
    def test_worker_input_drops_empty_values_and_filters_previous_by_type(self) -> None:
        previous = [{"type": "A", "scenario_id": "a1"}, {"type": "B", "scenario_id": "b1"}]
        inp = build_worker_input(PROJECT, "B", round_no=2, previous_scenarios=previous)
        self.assertEqual(inp["hook_type"], "B")
        self.assertEqual(inp["round"], 2)
        self.assertEqual(inp["product_info"], {"name": "60분 비주얼 타이머", "category": "stationery",
                                                "verified_facts": ["60분형 아날로그 타이머"]})
        self.assertEqual([s["scenario_id"] for s in inp["previous_scenarios"]], ["b1"])

    def test_normalize_keeps_worker_fields_and_drops_overlong_hooks(self) -> None:
        good = worker_scenario("B")
        good["beats"][0]["scene3d"] = {"fact_shown": "심장 세 개"}
        long = worker_scenario("B", "sc_long")
        long["beats"][0]["duration_sec"] = 18.0
        items = normalize_scenarios({"scenarios": [good, long, {"scenario_id": "broken"}]}, "B", max_hook_sec=20.0)
        self.assertEqual([i["scenario_id"] for i in items], ["sc_demo_B1_01"])
        self.assertEqual(items[0]["hook_duration_sec"], 9.0)
        self.assertEqual(items[0]["beats"][0]["scene3d"], {"fact_shown": "심장 세 개"})
        self.assertEqual(items[0]["storyboard_frames"], [])

    def test_generator_routes_each_type_to_its_worker_with_next_round(self) -> None:
        seen: List[Dict[str, Any]] = []

        def fake_worker(worker_input: Dict[str, Any], settings: Any) -> Dict[str, Any]:
            seen.append(worker_input)
            ht = worker_input["hook_type"]
            return {"scenarios": [worker_scenario(ht, f"sc_{ht}")]}

        project = dict(PROJECT, scenario_round=2)
        gen = make_scenario_generator(_settings(), _Store([{"type": "A", "scenario_id": "old"}]),
                                      workers={"A": fake_worker, "B": fake_worker})
        items = gen(project, ["A", "B"], "anthropic")
        self.assertEqual([(i["type"], i["scenario_id"]) for i in items], [("A", "sc_A"), ("B", "sc_B")])
        self.assertEqual([w["round"] for w in seen], [3, 3])
        self.assertEqual(len(seen[0]["previous_scenarios"]), 1)
        self.assertEqual(seen[1]["previous_scenarios"], [])

    def test_worker_failure_falls_back_and_reports_both_errors_when_fallback_fails(self) -> None:
        def broken(worker_input: Dict[str, Any], settings: Any) -> Dict[str, Any]:
            raise WorkerError("node 없음")

        def fallback(project: Dict[str, Any], types: List[str], provider: str) -> List[Dict[str, Any]]:
            return [{"scenario_id": f"planner_{types[0]}", "type": types[0]}]

        gen = make_scenario_generator(_settings(), _Store(), fallback=fallback, workers={"A": broken})
        self.assertEqual(gen(PROJECT, ["A"], "anthropic")[0]["scenario_id"], "planner_A")

        def failing_fallback(project: Dict[str, Any], types: List[str], provider: str) -> List[Dict[str, Any]]:
            raise HTTPException(status_code=502, detail={"error": {"code": "PLANNER_UNAVAILABLE", "message": "기획 서버 꺼짐"}})

        gen = make_scenario_generator(_settings(), _Store(), fallback=failing_fallback, workers={"A": broken})
        with self.assertRaises(HTTPException) as ctx:
            gen(PROJECT, ["A"], "anthropic")
        message = ctx.exception.detail["error"]["message"]
        self.assertEqual(ctx.exception.detail["error"]["code"], "HOOK_WORKER_UNAVAILABLE")
        self.assertIn("node 없음", message)
        self.assertIn("기획 서버 꺼짐", message)

    def test_off_mode_never_calls_workers(self) -> None:
        def explode(worker_input: Dict[str, Any], settings: Any) -> Dict[str, Any]:
            raise AssertionError("worker must not be called")

        gen = make_scenario_generator(
            _settings(hook_worker_mode="off"), _Store(),
            fallback=lambda p, t, prov: [{"scenario_id": "planner", "type": t[0]}], workers={"C": explode},
        )
        self.assertEqual(gen(PROJECT, ["C"], "anthropic")[0]["scenario_id"], "planner")

    def test_c_worker_code_loads_in_process_and_its_offline_draft_passes_normalize(self) -> None:
        generate = _import_c_generate(BACKEND / "bridge-dev" / "c")
        inp = build_worker_input(PROJECT, "C", round_no=1, previous_scenarios=[])
        run = generate.generate_scenarios(inp, offline=True)
        items = normalize_scenarios(run["response"], "C", max_hook_sec=20.0)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["type"], "C")
        self.assertEqual(items[0]["ad_spec"]["track_archetype"], "C_direct_proof")
        self.assertAlmostEqual(items[0]["hook_duration_sec"], sum(b["duration_sec"] for b in items[0]["beats"]))


if __name__ == "__main__":
    unittest.main()
