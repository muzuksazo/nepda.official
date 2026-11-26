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

print("5-1. 소구포인트 입력")
from src.prompt import build_user_prompt  # noqa: E402

sp_inp = read("examples", "piev", "05_worker-input.round3.json")
sp = parse_worker_input(sp_inp)
expect("소구포인트를 읽는다", sp["selling_points"][0]["point"] == "탈취·악취 제거" and len(sp["selling_points"][0]["evidence"]) == 3)
expect("문자열만 줘도 된다", parse_worker_input({**inp, "product_info": {**inp["product_info"], "selling_points": ["탈취"]}})
       ["selling_points"] == [{"point": "탈취", "source": "", "evidence": []}])
expect("없으면 빈 목록", parsed["selling_points"] == [])
text = build_user_prompt(sp)
expect("프롬프트에 소구포인트와 근거가 들어간다", "탈취·악취 제거" in text and "청량한 향기" in text)
sp_run = generate_scenarios(sp_inp, offline=True)
expect("시나리오에 겨냥한 소구포인트가 남는다", sp_run["response"]["scenarios"][0]["ad_spec"].get("selling_point") == "탈취·악취 제거")
expect("소구포인트가 없으면 필드를 넣지 않는다", "selling_point" not in scenarios[0]["ad_spec"])

print("6. Veo 문제 장면 (가짜 응답, 과금 없음)")
import base64  # noqa: E402

from src import veo  # noqa: E402

calls: list[tuple[str, dict]] = []
fake_mp4 = b"\x00" * 20000


def fake_post(url: str, body: dict, token: str) -> dict:
    calls.append((url, body))
    if url.endswith(":predictLongRunning"):
        return {"name": "projects/p/locations/us-central1/publishers/google/models/m/operations/op1"}
    done = sum(1 for u, _ in calls if u.endswith(":fetchPredictOperation")) >= 2
    return {"name": body["operationName"], "done": True,
            "response": {"videos": [{"bytesBase64Encoded": base64.b64encode(fake_mp4).decode(), "mimeType": "video/mp4"}]}} if done \
        else {"name": body["operationName"]}


saved = {k: os.environ.get(k) for k in ("GOOGLE_CLOUD_PROJECT", "GOOGLE_ACCESS_TOKEN", "GOOGLE_CLOUD_LOCATION", "C_VEO_MODEL")}
real_post = veo._post
with tempfile.TemporaryDirectory() as d:
    image = os.path.join(d, "first.jpg")
    open(image, "wb").write(b"\xff\xd8fake-jpeg")
    os.environ.pop("GOOGLE_CLOUD_PROJECT", None)
    expect("프로젝트가 없으면 꺼져 있다", not veo.configured())
    os.environ.update({"GOOGLE_CLOUD_PROJECT": "demo-project", "GOOGLE_ACCESS_TOKEN": "test-token"})
    os.environ.pop("GOOGLE_CLOUD_LOCATION", None)
    os.environ.pop("C_VEO_MODEL", None)
    veo._post = fake_post
    try:
        clip = veo.generate("spill_diffuser", image, os.path.join(d, "cache"), 3.0, log=lambda m: None, poll_sec=0)
        url, body = calls[0]
        expect("Vertex AI 주소", url == "https://us-central1-aiplatform.googleapis.com/v1/projects/demo-project/locations/us-central1"
                                    "/publishers/google/models/veo-3.1-fast-generate-001:predictLongRunning", url)
        expect("첫 프레임 이미지를 보낸다", body["instances"][0]["image"]["mimeType"] == "image/jpeg"
               and base64.b64decode(body["instances"][0]["image"]["bytesBase64Encoded"]) == b"\xff\xd8fake-jpeg")
        expect("3초 장면은 4초·세로로 요청", body["parameters"]["durationSeconds"] == 4 and body["parameters"]["aspectRatio"] == "9:16")
        expect("끝날 때까지 기다렸다 저장한다", open(clip, "rb").read() == fake_mp4 and len(calls) == 3, str(len(calls)))
        veo.generate("spill_diffuser", image, os.path.join(d, "cache"), 3.0, log=lambda m: None, poll_sec=0)
        expect("같은 요청은 캐시를 쓴다 (재과금 없음)", len(calls) == 3, str(len(calls)))
        veo._post = lambda url, body, token: {"name": "op2", "done": True, "response": {"raiMediaFilteredCount": 1,
                                                                                         "raiMediaFilteredReasons": ["blocked"]}}
        try:
            veo.generate("spill_diffuser", image, os.path.join(d, "cache2"), 3.0, log=lambda m: None, poll_sec=0)
            expect("안전 필터에 걸리면 오류", False)
        except veo.VeoError as e:
            expect("안전 필터에 걸리면 오류", "blocked" in str(e), str(e))
    finally:
        veo._post = real_post
        for k, v in saved.items():
            os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)
expect("장면 길이 → Veo 길이", [veo.pick_duration(x) for x in (3, 4, 4.5, 7, 12)] == [4, 4, 6, 8, 8])

print(f"\n{'모두 통과' if not failures else '실패 ' + str(len(failures)) + '건: ' + ', '.join(failures)}")
sys.exit(1 if failures else 0)
