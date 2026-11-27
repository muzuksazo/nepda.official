"""hookpipe · 과금·ffmpeg 없이 확인하는 규칙: 자막, 본편 길이 배분, 제품 장면 판정, 작업자 연결."""

import unittest
from types import SimpleNamespace
from typing import Any, Dict, List

from fastapi import HTTPException

from tests.support.hookpipe import BACKEND, worker_scenario

from hookpipe.body import plan_body_segments
from hookpipe.media import gain_to_target
from hookpipe.captions import build_srt, merge_srt, parse_srt, srt_timestamp, wrap_caption
from hookpipe.prompts import beat_prompt, clean_visual, ordered_beats, product_beat_orders
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

    def test_body_srt_is_shifted_by_the_hook_length_and_renumbered(self) -> None:
        hook = "1\n00:00:00,000 --> 00:00:03,000\n훅 자막\n"
        body = "\ufeff1\r\n00:00:00,500 --> 00:00:02,000\r\n본편 첫 줄\r\n둘째 줄\r\n\r\n2\r\n00:00:02,000 --> 00:00:04,250\r\n본편 둘째\r\n"
        self.assertEqual(parse_srt(body)[0], (0.5, 2.0, "본편 첫 줄\n둘째 줄"))
        merged = merge_srt([(hook, 0.0), (body, 17.04)])
        self.assertEqual([c[0] for c in parse_srt(merged)], [0.0, 17.54, 19.04])
        self.assertIn("3\n00:00:19,040 --> 00:00:21,290\n본편 둘째", merged)

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
        self.assertLess(cut[0], cut[1])

    def test_short_cuts_survive_shortening_and_overflow_drops_from_the_end(self) -> None:
        # 긴 컷 하나와 짧은 컷 둘: 짧은 컷이 사라지지 않고 긴 컷에서 더 깎인다
        cut = plan_body_segments([40.0, 3.0, 2.0], 13.0)
        self.assertAlmostEqual(sum(cut), 13.0, places=2)
        self.assertTrue(all(c >= 1.0 for c in cut), cut)
        # 3초짜리 15개를 13초에: 1초씩 13개까지만 쓰고 뒤의 둘은 뺀다 (첫 컷만 남는 일은 없다)
        many = plan_body_segments([3.0] * 15, 13.0)
        self.assertEqual([c > 0 for c in many], [True] * 13 + [False] * 2)
        self.assertLessEqual(sum(many), 13.0 + 1e-6)
        # 1초보다 짧은 컷은 제한이 없으면 그대로 둔다
        self.assertEqual(plan_body_segments([0.8, 5.0], None), [0.8, 5.0])

    def test_gain_is_capped_so_quiet_footage_noise_is_not_blown_up(self) -> None:
        self.assertEqual(gain_to_target(None), 0.0)
        self.assertEqual(gain_to_target(-20.0), 6.0)
        self.assertEqual(gain_to_target(-5.0), -9.0)
        self.assertEqual(gain_to_target(-55.0), 20.0)

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
        # 나레이션 문장은 영상 모델에 넘기지 않는다 (모델이 화면에 글자로 그려 넣는다)
        self.assertNotIn(ordered_beats(scenario)[0]["narration"], story)
        self.assertIn("Subtitles are added later", story)

    def test_worker_tags_are_not_sent_to_the_video_model(self) -> None:
        self.assertEqual(clean_visual("[포커스: 전체→시각화] 일곱 색 원이 사라진다"), "일곱 색 원이 사라진다")
        self.assertEqual(clean_visual("타이머 다이얼을 돌리는 손 클로즈업 [F02] [F05]"), "타이머 다이얼을 돌리는 손 클로즈업")
        scenario = worker_scenario("B")
        scenario["beats"][0]["visual"] = "[포커스: 전체] 바닷속 문어 한 마리"
        prompt = beat_prompt(scenario, ordered_beats(scenario)[0], 1, 3)
        self.assertIn("THIS SHOT (1/3): 바닷속 문어 한 마리", prompt)
        self.assertNotIn("포커스", prompt)

    def test_soften_prompt_replaces_cross_sections_only_when_present(self) -> None:
        from hookpipe.prompts import soften_prompt

        soft = soften_prompt("THIS SHOT: 고래 입안의 빗살 사이로 물이 나가는 단면 시각화")
        self.assertNotIn("단면", soft)
        self.assertIn("no cutaway", soft)
        self.assertEqual(soften_prompt("THIS SHOT: 바닷속 고래"), "THIS SHOT: 바닷속 고래")
        self.assertNotIn("cutaway", soften_prompt("style: blender_3d_cutaway").split("\n")[0])

    def test_only_scenarios_without_a_timeline_use_hookpipe(self) -> None:
        self.assertTrue(is_worker_scenario(worker_scenario()))
        legacy = worker_scenario()
        legacy["ad_spec"] = {"timeline": [{"id": "x"}]}
        self.assertFalse(is_worker_scenario(legacy))
        self.assertFalse(is_worker_scenario(None))


class TtsProviderSwitch(unittest.TestCase):
    def test_inworld_maps_the_default_gemini_voice_and_keeps_explicit_voices(self) -> None:
        from hookpipe.tts import InworldTts, MediaWithTts, TtsError

        settings = SimpleNamespace(inworld_api_key="k", inworld_voice_id="iw_voice", tts_default_voice="Kore")
        tts = InworldTts(settings)
        self.assertEqual(tts.voice_for(None), "iw_voice")
        self.assertEqual(tts.voice_for("Kore"), "iw_voice")
        self.assertEqual(tts.voice_for("other__voice"), "other__voice")
        with self.assertRaises(TtsError):
            InworldTts(SimpleNamespace(inworld_api_key="", inworld_voice_id="v"))

        media = SimpleNamespace(generate_video_clip=lambda *a, **k: "video")
        both = MediaWithTts(media, tts)
        self.assertEqual(both.generate_video_clip(), "video")
        self.assertEqual(both.tts_extension, ".mp3")
        self.assertTrue(both.tts_label.startswith("inworld:"))


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
        dup = worker_scenario("B", "sc_dup")
        dup["beats"][1]["order"] = 1
        noorder = worker_scenario("B", "sc_noorder")
        del noorder["beats"][0]["order"]
        good["rule_violations"] = ["반전 전 제품명 노출"]
        items = normalize_scenarios(
            {"scenarios": [good, long, {"scenario_id": "broken"}, dup, noorder]}, "B", max_hook_sec=20.0
        )
        self.assertEqual(len(items), 1)
        # 서버가 꼬리를 붙여 고유하게 만들고, 작업자가 준 ID 와 규칙 위반은 ad_spec 에 남긴다
        self.assertRegex(items[0]["scenario_id"], r"^sc_demo_B1_01_[0-9a-f]{6}$")
        self.assertEqual(items[0]["ad_spec"]["worker_scenario_id"], "sc_demo_B1_01")
        self.assertEqual(items[0]["ad_spec"]["rule_violations"], ["반전 전 제품명 노출"])
        self.assertNotIn("rule_violations", items[0])
        again = normalize_scenarios({"scenarios": [worker_scenario("B")]}, "B", max_hook_sec=20.0)
        self.assertNotEqual(again[0]["scenario_id"], items[0]["scenario_id"])
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
        self.assertEqual([(i["type"], i["ad_spec"]["worker_scenario_id"]) for i in items], [("A", "sc_A"), ("B", "sc_B")])
        self.assertEqual([w["round"] for w in seen], [3, 3])
        by_type = {w["hook_type"]: w for w in seen}  # 유형끼리 동시에 돌아 호출 순서는 정해져 있지 않다
        self.assertEqual(len(by_type["A"]["previous_scenarios"]), 1)
        self.assertEqual(by_type["B"]["previous_scenarios"], [])

        # 한 요청에서 여러 개를 뽑을 때: 방금 만든 것도 이전 시나리오로 작업자에게 넘어간다
        seen.clear()
        gen(dict(project, pending_scenarios=[{"type": "B", "scenario_id": "just_made"}]), ["B"], "anthropic")
        self.assertEqual([s["scenario_id"] for s in seen[0]["previous_scenarios"]], ["just_made"])

    def test_deadline_stops_waiting_for_a_hung_call(self) -> None:
        import threading
        import time

        from hookpipe.render import _call_with_deadline

        release = threading.Event()
        started = time.monotonic()
        with self.assertRaises(TimeoutError):
            _call_with_deadline(lambda: release.wait(10), 0.2, "멈춘 호출")
        self.assertLess(time.monotonic() - started, 2.0)
        release.set()
        self.assertEqual(_call_with_deadline(lambda: 7, 1.0, "보통 호출"), 7)
        with self.assertRaises(ValueError):
            _call_with_deadline(lambda: (_ for _ in ()).throw(ValueError("x")), 1.0, "오류")

    def test_body_writer_follows_body_llm(self) -> None:
        from types import SimpleNamespace
        from unittest.mock import MagicMock, patch

        from hookpipe import body_edit

        self.assertIn("gemini", body_edit.default_script_writer(SimpleNamespace(body_llm="gemini-4-hydrogen")).__qualname__)
        fake = MagicMock()
        fake.messages.create.return_value = SimpleNamespace(
            stop_reason="end_turn", content=[SimpleNamespace(type="text", text='{"lines": []}')])
        with patch("anthropic.Anthropic", return_value=fake):
            out = body_edit.default_script_writer(SimpleNamespace(body_llm="claude-opus-5-5"))("대본", [])
        self.assertEqual(out, {"lines": []})
        sent = fake.messages.create.call_args.kwargs
        self.assertEqual(sent["model"], "claude-opus-5-5")
        self.assertEqual(sent["output_config"]["format"]["schema"], body_edit.BODY_SCRIPT_SCHEMA)

    def test_selfhosted_prompts_follow_service_rules(self) -> None:
        from hookpipe.prompts import first_frame_prompt, motion_prompt

        scenario = {"type": "B", "ad_spec": {"visual_style": "blender_3d_physics"}}
        beat = {"order": 1, "visual": "[포커스: 전체] 고래가 물을 삼킨다", "narration": "이 문장은 넣지 않는다"}
        frame = first_frame_prompt(scenario, beat)
        self.assertIn("3D animation", frame)
        self.assertIn("not clay", frame)
        self.assertIn("bottom third", frame)
        self.assertIn("No text", frame)
        self.assertNotIn("[포커스", frame)
        self.assertNotIn("blender", frame)
        self.assertNotIn("이 문장은", frame)
        with_product = first_frame_prompt(scenario, beat, product={"name": "스펀지"}, shows_product=True,
                                          has_product_reference=True)
        self.assertIn("reference photo", with_product)
        motion = motion_prompt({"type": "C"}, beat)
        self.assertIn("smartphone", motion)
        self.assertIn("no speech", motion)
        self.assertNotIn("이 문장은", motion)

    def test_types_run_at_the_same_time(self) -> None:
        import threading

        both_started = threading.Barrier(2, timeout=5)  # 하나씩 돌면 두 번째가 오지 않아 BrokenBarrierError

        def waits_for_the_other(worker_input: Dict[str, Any], settings: Any) -> Dict[str, Any]:
            both_started.wait()
            ht = worker_input["hook_type"]
            return {"scenarios": [worker_scenario(ht, f"sc_{ht}")]}

        gen = make_scenario_generator(_settings(), _Store(), workers={"B": waits_for_the_other, "C": waits_for_the_other})
        items = gen(PROJECT, ["C", "B"], "anthropic")
        self.assertEqual([i["type"] for i in items], ["C", "B"])  # 결과는 요청한 순서대로

    def test_one_failed_type_does_not_discard_the_types_already_generated(self) -> None:
        def ok(worker_input: Dict[str, Any], settings: Any) -> Dict[str, Any]:
            return {"scenarios": [worker_scenario("A", "sc_A")]}

        def crash(worker_input: Dict[str, Any], settings: Any) -> Dict[str, Any]:
            raise TypeError("unexpected shape")  # WorkerError 가 아닌 예외도 대체 경로로 간다

        def failing_fallback(project: Dict[str, Any], types: List[str], provider: str) -> List[Dict[str, Any]]:
            raise HTTPException(status_code=502, detail={"error": {"code": "PLANNER_UNAVAILABLE", "message": "꺼짐"}})

        gen = make_scenario_generator(_settings(), _Store(), fallback=failing_fallback, workers={"A": ok, "C": crash})
        items = gen(PROJECT, ["A", "C"], "anthropic")
        self.assertEqual([i["type"] for i in items], ["A"])
        with self.assertRaises(HTTPException) as ctx:
            gen(PROJECT, ["C"], "anthropic")
        self.assertIn("TypeError", ctx.exception.detail["error"]["message"])

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
