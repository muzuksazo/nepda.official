"""C 훅 작업자 CLI.  c/ 폴더에서 `python -m src.cli <명령>` 으로 실행한다."""
from __future__ import annotations

import glob
import json
import os
import sys
import time

from . import veo
from .assets import assets_dir, fetch_all
from .check import check_scenario
from .generate import generate_scenarios
from .render import RenderError, first_frame, render_hook, storyboard
from .schema import InputError, parse_worker_input
from .tts import TtsError

USAGE = """사용법 (backend/bridge-dev/c 에서):
  python -m src.cli scenarios <입력.json> [--next] [--count N] [--offline] [--force]
      시나리오 생성 → 규칙 검사. Claude API 호출(과금). --offline 은 API 없이 사실 문장으로 초안만 만든다.
      --next  이 프로젝트의 다음 회차로 실행 (앞선 회차 시나리오를 피함)
  python -m src.cli check <시나리오응답.json> [--input <입력.json>]
      이미 있는 응답을 규칙만 검사. API 호출 없음.
  python -m src.cli import <시나리오응답.json> --input <입력.json> [--force]
      이미 있는 시나리오 응답(직접 쓴 것, 백엔드에 저장된 것)을 회차 기록으로 가져온다. API 호출 없음.
  python -m src.cli storyboard <project_id> <scenario_id>
      장면별 콘티 이미지 생성 (FR-004).
  python -m src.cli hook <project_id> <scenario_id> [--voice ID] [--no-tts] [--hook-id ID] [--engine auto|veo|blender]
      훅 영상 + TTS 생성 (FR-005). Inworld TTS 호출(과금).
      문제 장면: Blender 가 첫 프레임을 렌더하고 Google Veo(Vertex AI, 과금)가 영상으로 만든다.
      GOOGLE_CLOUD_PROJECT 가 없으면 Blender 물리 렌더만으로 만든다.
  python -m src.cli veo [템플릿] [--generate] [--seconds N]
      Google Cloud 설정·인증 확인. --generate 를 붙이면 문제 장면 한 편을 실제로 생성한다 (과금).
  python -m src.cli assets
      문제 장면에 쓰는 무료(CC0) 3D 에셋 내려받기 (약 100MB, 한 번만).

기록: out/<project_id>/round-<n>.json        결과 파일: <OUTPUT_DIR>/<project_id>/<hook_id>/ (기본 output/)"""

OUT = os.path.abspath("out")


def load_env(path: str = ".env") -> None:
    if not os.path.exists(path):
        return
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def arg(flag: str) -> str | None:
    return sys.argv[sys.argv.index(flag) + 1] if flag in sys.argv and sys.argv.index(flag) + 1 < len(sys.argv) else None


def has(flag: str) -> bool:
    return flag in sys.argv


def read_json(path: str):
    return json.load(open(path, encoding="utf-8"))


def write_json(path: str, data) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def load_runs(project_id: str) -> list[dict]:
    return [read_json(p) for p in sorted(glob.glob(os.path.join(OUT, project_id, "round-*.json")))]


def find_scenario(project_id: str, scenario_id: str) -> tuple[dict, dict, dict]:
    for run in load_runs(project_id):
        for s in run["response"]["scenarios"]:
            if s["scenario_id"] == scenario_id:
                return s, run.get("assets") or {}, run
    raise InputError(f"out/{project_id}/ 에 시나리오 {scenario_id} 가 없습니다. 먼저 scenarios 를 실행하세요.")


def print_checks(rows: list[dict]) -> bool:
    ok = True
    for r in rows:
        print(f"\n■ {r['title']}")
        if not r["errors"] and not r["warnings"]:
            print("  통과")
        for e in r["errors"]:
            print(f"  ✗ {e}")
        for w in r["warnings"]:
            print(f"  △ {w}")
        ok = ok and not r["errors"]
    return ok


def output_dir(project_id: str, leaf: str) -> str:
    return os.path.join(os.environ.get("OUTPUT_DIR", "output"), project_id, leaf)


def main() -> int:
    load_env()
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        print(USAGE)
        return 1
    cmd = args[0]
    log = lambda m: print(m, file=sys.stderr)

    if cmd == "assets":
        fetch_all(log)
        return 0

    if cmd == "check" and len(args) >= 2:
        res = read_json(args[1])
        inp = parse_worker_input(read_json(arg("--input") or "examples/01_worker-input.scenarios.json"))
        rows = [{"title": s.get("hook_title", ""), **check_scenario(s, inp["product_info"])} for s in res.get("scenarios", [])]
        return 0 if print_checks(rows) else 2

    if cmd == "import" and len(args) >= 2:
        res = read_json(args[1])
        inp = parse_worker_input(read_json(arg("--input") or "examples/01_worker-input.scenarios.json"))
        checks = [check_scenario(s, inp["product_info"]) for s in res["scenarios"]]
        record = os.path.join(OUT, inp["project_id"], f"round-{int(res.get('round', 1))}.json")
        if os.path.exists(record) and not has("--force"):
            log(f"{record} 가 이미 있습니다. 덮어쓰려면 --force.")
            return 1
        write_json(record, {"response": {"project_id": inp["project_id"], "status": "SCENARIOS_READY", "round": int(res.get("round", 1)),
                                         "scenarios": res["scenarios"]},
                            "checks": checks, "steps": [], "assets": inp["assets"], "product_name": inp["product_info"]["name"], "offline": True})
        ok = print_checks([{"title": s["hook_title"], **c} for s, c in zip(res["scenarios"], checks)])
        print(f"기록: {record}")
        return 0 if ok else 2

    if cmd == "scenarios" and len(args) >= 2:
        data = read_json(args[1])
        if arg("--count"):
            data["count"] = int(arg("--count"))
        prev = load_runs(str(data.get("project_id", "")))
        if has("--next"):
            data["round"] = max([r["response"]["round"] for r in prev] + [0]) + 1
            data["previous_scenarios"] = list(data.get("previous_scenarios") or []) + [s for r in prev for s in r["response"]["scenarios"]]
        if not has("--offline") and not (os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")):
            log("ANTHROPIC_API_KEY 가 없습니다. c/.env.example 을 c/.env 로 복사해 키를 넣거나, 흐름만 볼 거면 --offline 을 쓰세요.")
            return 1
        record = os.path.join(OUT, str(data.get("project_id")), f"round-{int(data.get('round', 1))}.json")
        if os.path.exists(record) and not has("--force"):
            log(f"{record} 가 이미 있습니다. 다음 회차는 --next, 덮어쓰려면 --force.")
            return 1
        run = generate_scenarios(data, offline=has("--offline"), log=log)
        write_json(record, run)
        ok = print_checks([{"title": s["hook_title"], **c} for s, c in zip(run["response"]["scenarios"], run["checks"])])
        print(f"\n{run['response']['round']}회차 · 시나리오 {len(run['response']['scenarios'])}개")
        for s in run["response"]["scenarios"]:
            print(f"  {s['scenario_id']}  {s['hook_title']}  ({s['hook_duration_sec']}초, 장면 {len(s['beats'])}개)")
        for st in run["steps"]:
            cost = "단가 미상" if st["costUsd"] is None else f"${st['costUsd']:.4f}"
            print(f"  비용 {st['step']}: {st['model']} 입력 {st['inputTokens']} / 출력 {st['outputTokens']}  {cost}  {st['ms'] / 1000:.1f}초")
        print(f"기록: {record}")
        return 0 if ok else 2

    if cmd == "storyboard" and len(args) >= 3:
        scenario, assets, _ = find_scenario(args[1], args[2])
        frames = storyboard(scenario, assets, output_dir(args[1], args[2]), log)
        print(json.dumps({"project_id": args[1], "scenario_id": args[2], "status": "STORYBOARD_READY", "frames": frames}, ensure_ascii=False, indent=2))
        return 0

    if cmd == "hook" and len(args) >= 3:
        scenario, assets, _ = find_scenario(args[1], args[2])
        hook_id = arg("--hook-id") or f"hook_{args[2].removeprefix('sc_')}_{time.strftime('%m%d%H%M%S')}"
        out_dir = output_dir(args[1], hook_id)
        started = time.time()
        tts = {"enabled": not has("--no-tts"), "voice": arg("--voice")}
        if arg("--engine"):
            assets = {**assets, "problem_engine": arg("--engine")}
        try:
            files = render_hook(scenario, assets, out_dir, tts=tts, log=log)
            engine = files.pop("problem_engine", None)
            status = {"hook_id": hook_id, "status": "done", "files": files, "output_dir": out_dir.replace("\\", "/"),
                      "problem_engine": engine, "error": None}
        except (RenderError, TtsError) as e:
            status = {"hook_id": hook_id, "status": "failed", "files": {"storyboard_images": []}, "output_dir": out_dir.replace("\\", "/"),
                      "error": {"code": "HOOK_RENDER_FAILED", "message": str(e)}}
        print(json.dumps(status, ensure_ascii=False, indent=2))
        log(f"⏱ {time.time() - started:.0f}초")
        return 0 if status["status"] == "done" else 1

    if cmd == "veo":
        template = args[1] if len(args) > 1 else "spill_diffuser"
        print(f"프로젝트: {veo.project() or '(GOOGLE_CLOUD_PROJECT 없음)'}  지역: {veo.location()}  모델: {veo.model()}")
        try:
            if not veo.configured():
                raise veo.VeoError("GOOGLE_CLOUD_PROJECT 가 없습니다. c/.env 에 Google Cloud 프로젝트 ID 를 넣으세요.")
            veo.access_token()
            print("인증: 통과 (액세스 토큰 발급됨)")
            if not has("--generate"):
                print("여기까지는 과금이 없습니다. 실제로 한 편 만들어 보려면 --generate 를 붙이세요 (과금).")
                return 0
            seconds = float(arg("--seconds") or 3)
            clip = veo.generate(template, first_frame(template, log), os.path.join(assets_dir(), "cache", "veo"), seconds, log=log)
            print(f"생성됨: {clip}")
            return 0
        except veo.VeoError as e:
            log(str(e))
            return 1

    print(USAGE)
    return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (InputError, RenderError, TtsError, RuntimeError, FileNotFoundError) as e:
        print(e, file=sys.stderr)
        sys.exit(1)
