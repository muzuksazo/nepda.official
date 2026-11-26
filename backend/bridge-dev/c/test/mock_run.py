"""API · Blender · ffmpeg 없이 도는 흐름 확인.  c/ 폴더에서: python -m test.mock_run"""
from __future__ import annotations

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.check import check_scenario            # noqa: E402
from src.generate import generate_scenarios     # noqa: E402
from src.render import _caption_chunks, write_srt  # noqa: E402
from src.schema import InputError, parse_worker_input  # noqa: E402

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
read = lambda *p: json.load(open(os.path.join(HERE, *p), encoding="utf-8"))
failures: list[str] = []


def expect(name: str, cond: bool, detail: str = "") -> None:
    print(("  ok  " if cond else "  FAIL ") + name + (f"  ({detail})" if detail and not cond else ""))
    if not cond:
        failures.append(name)


print("1. 입력 형태")
inp = read("examples", "01_worker-input.scenarios.json")
parsed = parse_worker_input(inp)
expect("예시 입력을 읽는다", parsed["hook_type"] == "C" and parsed["count"] == 1)
try:
    parse_worker_input({**inp, "hook_type": "B"})
    expect("다른 유형은 거절한다", False)
except InputError:
    expect("다른 유형은 거절한다", True)
try:
    parse_worker_input({**inp, "product_info": {"name": "x", "verified_facts": []}})
    expect("사실이 없으면 거절한다", False)
except InputError:
    expect("사실이 없으면 거절한다", True)

print("2. 오프라인 시나리오 생성 (API 호출 없음)")
run = generate_scenarios({**inp, "count": 2}, offline=True)
scenarios = run["response"]["scenarios"]
expect("요청한 개수만큼 만든다", len(scenarios) == 2)
expect("응답 round 와 항목 round 가 같다", all(s["round"] == run["response"]["round"] for s in scenarios))
expect("scenario_id 가 서로 다르다", len({s["scenario_id"] for s in scenarios}) == 2)
for s, c in zip(scenarios, run["checks"]):
    expect(f"규칙 검사 통과: {s['scenario_id']}", not c["errors"], "; ".join(c["errors"]))
    expect("장면 길이 합 = hook_duration_sec ≤ 15", abs(sum(b["duration_sec"] for b in s["beats"]) - s["hook_duration_sec"]) < 0.01 and s["hook_duration_sec"] <= 15)

print("3. 저장소 예시 응답 검사")
example = read("examples", "02_scenarios.response.json")
for s in example["scenarios"]:
    c = check_scenario(s, inp["product_info"])
    expect(f"예시 통과: {s['scenario_id']}", not c["errors"], "; ".join(c["errors"]))

print("4. 규칙 위반을 잡는다")
bad = json.loads(json.dumps(scenarios[0]))
bad["beats"][1]["narration"] = "무소음이고 지금 50% 할인 중입니다."
bad["beats"][0]["role"] = "장점"
bad["ad_spec"]["claim_ids"] = ["F99"]
errors = check_scenario(bad, inp["product_info"])["errors"]
expect("미검증 표현(무소음)", any("무소음" in e for e in errors))
expect("가격·할인", any("가격" in e for e in errors))
expect("첫 장면이 문제가 아님", any("첫 장면" in e for e in errors))
expect("없는 근거 ID", any("F99" in e for e in errors))
long = json.loads(json.dumps(scenarios[0]))
long["beats"][0]["duration_sec"] = 9.0
long["hook_duration_sec"] = round(sum(b["duration_sec"] for b in long["beats"]), 2)
expect("15초 초과", any("15" in e for e in check_scenario(long, inp["product_info"])["errors"]))

print("5. 자막")
words = [("디퓨저,", 0.1, 0.5), ("또", 0.6, 0.8), ("쏟았어요.", 0.8, 1.7)]
chunks = _caption_chunks(words, 0.0, 3.0, 0.07, 1.0, 0.12)
expect("문장부호에서 끊는다", [c[2] for c in chunks] == ["디퓨저,", "또 쏟았어요."], str(chunks))
expect("시간이 장면 안에 있다", all(0 <= a < b <= 3.0 for a, b, _ in chunks), str(chunks))
with tempfile.TemporaryDirectory() as d:
    path = os.path.join(d, "hook.srt")
    write_srt(path, scenarios[0]["beats"])
    srt = open(path, encoding="utf-8").read()
expect("SRT 는 장면당 한 개", srt.count("-->") == len(scenarios[0]["beats"]))
expect("SRT 첫 장면은 0초부터", "00:00:00,000 --> 00:00:03,000" in srt, srt[:80])

print(f"\n{'모두 통과' if not failures else '실패 ' + str(len(failures)) + '건: ' + ', '.join(failures)}")
sys.exit(1 if failures else 0)
