"""API 없이 도는 흐름 확인.  c/ 폴더에서: python -m test.mock_run"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import types

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import generate as gen                 # noqa: E402
from src.check import check_scenario            # noqa: E402
from src.generate import generate_scenarios     # noqa: E402
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
for bad_input, name in (({**inp, "hook_type": "B"}, "다른 유형은 거절한다"),
                        ({**inp, "product_info": {"name": "x", "verified_facts": []}}, "사실이 없으면 거절한다")):
    try:
        parse_worker_input(bad_input)
        expect(name, False)
    except InputError:
        expect(name, True)

print("2. 오프라인 시나리오 생성 (API 호출 없음)")
run = generate_scenarios({**inp, "count": 2}, offline=True)
scenarios = run["response"]["scenarios"]
expect("요청한 개수만큼 만든다", len(scenarios) == 2)
expect("응답 round 와 항목 round 가 같다", all(s["round"] == run["response"]["round"] for s in scenarios))
expect("scenario_id 가 서로 다르다", len({s["scenario_id"] for s in scenarios}) == 2)
for s, c in zip(scenarios, run["checks"]):
    expect(f"규칙 검사 통과: {s['scenario_id']}", not c["errors"], "; ".join(c["errors"]))
    expect("훅 길이 15~20초", 15 <= s["hook_duration_sec"] <= 20, str(s["hook_duration_sec"]))
    expect("CTA 는 본편 뒤로", s["ad_spec"]["cta"]["placement"] == "after_body")

print("3. 저장소 예시 응답 검사")
for s in read("examples", "02_scenarios.response.json")["scenarios"]:
    c = check_scenario(s, inp["product_info"])
    expect(f"예시 통과: {s['scenario_id']}", not c["errors"], "; ".join(c["errors"]))

print("4. 규칙 위반을 잡는다")
base = scenarios[0]


def errors_of(change) -> list[str]:
    s = json.loads(json.dumps(base))
    change(s)
    s["hook_duration_sec"] = round(sum(b["duration_sec"] for b in s["beats"]), 2)
    return check_scenario(s, inp["product_info"])["errors"]


def unverified(s):
    s["beats"][1]["narration"] = "무소음이고 지금 50% 할인 중입니다."
errs = errors_of(unverified)
expect("미검증 표현(무소음)", any("무소음" in e for e in errs))
expect("가격·할인", any("가격" in e for e in errs))
expect("첫 장면이 문제가 아님", any("첫 장면" in e for e in errors_of(lambda s: s["beats"][0].update(role="장점"))))
expect("없는 근거 ID", any("F99" in e for e in errors_of(lambda s: s["ad_spec"].update(claim_ids=["F99"]))))
expect("20초 초과", any("15~20" in e for e in errors_of(lambda s: s["beats"][0].update(duration_sec=9.0))))
expect("15초 미만", any("15~20" in e for e in errors_of(lambda s: s["beats"][2].update(duration_sec=1.0))))
expect("자막 22자 초과는 오류", any("22자" in e for e in errors_of(lambda s: s["beats"][0].update(caption="가" * 23))))
expect("나레이션이 너무 길면 오류",
       any("나레이션이" in e for e in errors_of(lambda s: s["beats"][0].update(narration="가" * 40))))
expect("훅 안의 CTA 장면은 오류",
       any("CTA" in e for e in errors_of(lambda s: s["beats"][2].update(role="CTA"))))
expect("훅 안의 댓글 유도는 오류",
       any("댓글" in e for e in errors_of(lambda s: s["beats"][2].update(narration="댓글로 알려 주세요"))))

print("5. Gemini 경로 (가짜 응답, 과금 없음)")
calls = {}


class FakeModels:
    def generate_content(self, **kwargs):
        calls.update(kwargs)
        draft = gen.offline_drafts(parse_worker_input(inp))
        return types.SimpleNamespace(text=json.dumps({"scenarios": draft}, ensure_ascii=False), usage_metadata=None)


fake_google = types.ModuleType("google")
fake_genai = types.ModuleType("google.genai")
fake_types = types.ModuleType("google.genai.types")
fake_genai.Client = lambda api_key, **kw: types.SimpleNamespace(models=FakeModels())
fake_types.GenerateContentConfig = lambda **kw: kw
fake_types.HttpOptions = lambda **kw: kw
fake_types.HttpRetryOptions = lambda **kw: kw
fake_genai.types = fake_types
fake_google.genai = fake_genai
saved = {k: sys.modules.get(k) for k in ("google", "google.genai", "google.genai.types")}
sys.modules.update({"google": fake_google, "google.genai": fake_genai, "google.genai.types": fake_types})
try:
    grun = generate_scenarios(inp, model="gemini-4-hydrogen", gemini_api_key="dummy")
finally:
    for k, v in saved.items():
        if v is None:
            sys.modules.pop(k, None)
        else:
            sys.modules[k] = v
expect("Gemini 로 부른다", calls.get("model") == "gemini-4-hydrogen")
expect("같은 출력 스키마를 쓴다", calls["config"]["response_json_schema"]["required"] == ["scenarios"])
expect("결과가 규칙을 통과한다", not grun["checks"][0]["errors"], "; ".join(grun["checks"][0]["errors"]))

print("6. 명령 (계약 형식)")
with tempfile.TemporaryDirectory() as d:
    out = os.path.join(d, "scenarios_response.json")
    proc = subprocess.run([sys.executable, "-m", "src.cli", "generate", "--input", "examples/01_worker-input.scenarios.json",
                           "--out", out, "--offline"], cwd=HERE, capture_output=True, text=True, encoding="utf-8")
    expect("generate --input --out 은 0 으로 끝난다", proc.returncode == 0, proc.stderr[-300:])
    expect("결과 파일을 쓴다", os.path.exists(out))
    proc = subprocess.run([sys.executable, "-m", "src.cli", "check", "--spec", out, "--input",
                           "examples/01_worker-input.scenarios.json"], cwd=HERE, capture_output=True, text=True, encoding="utf-8")
    expect("check --spec --input 은 0 으로 끝난다", proc.returncode == 0, proc.stderr[-300:])
    proc = subprocess.run([sys.executable, "-m", "src.cli", "check", "--spec", "examples/01_worker-input.scenarios.json"],
                          cwd=HERE, capture_output=True, text=True, encoding="utf-8")
    expect("시나리오가 없는 파일을 주면 통과시키지 않는다", proc.returncode == 2, str(proc.returncode))

print("7. 구도 참고 이미지 (블록아웃)")
from src.blockouts import load_catalog, prompt_lines  # noqa: E402
from src.generate import offline_drafts  # noqa: E402
from src.prompt import build_user_prompt  # noqa: E402
from src.schema import to_scenario_item  # noqa: E402

catalog = load_catalog()
expect("목록을 읽는다", any(b["id"] == "phone_distract" for b in catalog))
expect("목록의 이미지 파일이 저장소에 있다", all(os.path.isfile(os.path.join(os.path.dirname(HERE), b["image"])) for b in catalog))
expect("프롬프트에 구도 목록이 들어간다", "phone_distract" in build_user_prompt(parsed))
expect("목록이 비면 빈 문자열로 두라고 알린다", "빈 문자열" in prompt_lines([])[0])
draft = offline_drafts(parsed)[0]
picked = to_scenario_item({**draft, "problem_blockout": "phone_distract"}, scenario_id="sc_demo_C1_01", round_no=1)
expect("고른 구도를 첫 장면에 붙인다", picked["beats"][0].get("first_frame_ref") == "c/blockouts/phone_distract.png"
       and bool(picked["beats"][0].get("first_frame_prompt")) and picked["ad_spec"].get("problem_blockout") == "phone_distract")
expect("다른 장면에는 붙이지 않는다", all("first_frame_ref" not in b for b in picked["beats"][1:]))
expect("구도를 붙여도 규칙 검사를 통과한다", not check_scenario(picked, inp["product_info"])["errors"])
for value, name in (("", "고르지 않으면 붙이지 않는다"), ("no_such_blockout", "목록에 없는 id 는 무시한다")):
    item = to_scenario_item({**draft, "problem_blockout": value}, scenario_id="sc_demo_C1_02", round_no=1)
    expect(name, "first_frame_ref" not in item["beats"][0] and "problem_blockout" not in item["ad_spec"])
legacy = {k: v for k, v in draft.items() if k != "problem_blockout"}
expect("problem_blockout 이 없는 초안도 받는다",
       "first_frame_ref" not in to_scenario_item(legacy, scenario_id="sc_demo_C1_03", round_no=1)["beats"][0])

print(f"\n{'모두 통과' if not failures else '실패 ' + str(len(failures)) + '건: ' + ', '.join(failures)}")
sys.exit(1 if failures else 0)
