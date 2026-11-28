"""C 훅 작업자 CLI (WORKER_CONTRACT.md 2절).  c/ 폴더에서 `python -m src.cli <명령>` 으로 실행한다.

훅 영상·나레이션·본편은 backend/hookpipe 가 만든다. 이 작업자는 시나리오(FR-003)만 만든다.
"""
from __future__ import annotations

import json
import os
import sys

from .check import check_scenario
from .generate import generate_scenarios
from .schema import InputError, parse_worker_input

USAGE = """사용법 (backend/bridge-dev/c 에서):
  python -m src.cli generate --input <입력.json> [--out <결과.json>] [--count N] [--model M] [--offline]
      시나리오 생성 → 규칙 검사. 글 모델 호출(과금). --model gemini-… 이면 Gemini, 기본은 C_MODEL(Claude).
      --offline 은 모델 없이 사실 문장으로 초안만 만든다 (흐름 확인용).
  python -m src.cli check --spec <시나리오응답.json> [--input <입력.json>]
      이미 있는 응답을 규칙만 검사. 모델 호출 없음.
종료 코드: 0 통과 · 2 규칙 위반 · 1 실행 오류"""


def load_env(path: str = ".env") -> None:
    if not os.path.exists(path):
        return
    for line in open(path, encoding="utf-8-sig"):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def flag(name: str) -> str | None:
    if name in sys.argv:
        i = sys.argv.index(name)
        if i + 1 < len(sys.argv) and not sys.argv[i + 1].startswith("--"):
            return sys.argv[i + 1]
    return None


def read_json(path: str):
    with open(path, encoding="utf-8-sig") as f:
        return json.load(f)


def write_json(path: str, data) -> None:
    folder = os.path.dirname(os.path.abspath(path))
    os.makedirs(folder, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def print_checks(rows: list[dict]) -> bool:
    ok = bool(rows)
    for r in rows:
        print(f"\n■ {r['title']}", file=sys.stderr)
        if not r["errors"] and not r["warnings"]:
            print("  통과", file=sys.stderr)
        for e in r["errors"]:
            print(f"  ✗ {e}", file=sys.stderr)
        for w in r["warnings"]:
            print(f"  △ {w}", file=sys.stderr)
        ok = ok and not r["errors"]
    return ok


def main() -> int:
    load_env()
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    log = lambda m: print(m, file=sys.stderr)
    try:
        if cmd == "generate":
            in_path = flag("--input")
            if not in_path:
                print(USAGE, file=sys.stderr)
                return 1
            data = read_json(in_path)
            if flag("--count"):
                data["count"] = int(flag("--count"))
            run = generate_scenarios(data, offline="--offline" in sys.argv, model=flag("--model"), log=log)
            response = run["response"]
            if flag("--out"):
                write_json(flag("--out"), response)
                log(f"저장: {flag('--out')}")
            else:
                print(json.dumps(response, ensure_ascii=False, indent=2))
            for st in run["steps"]:
                cost = "단가 미상" if st["costUsd"] is None else f"${st['costUsd']:.4f}"
                log(f"  {st['step']}: {st['model']} 입력 {st['inputTokens']} / 출력 {st['outputTokens']}  {cost}  {st['ms'] / 1000:.1f}초")
            rows = [{"title": s["hook_title"], **c} for s, c in zip(response["scenarios"], run["checks"])]
            return 0 if print_checks(rows) else 2

        if cmd == "check":
            spec_path = flag("--spec")
            if not spec_path:
                print(USAGE, file=sys.stderr)
                return 1
            response = read_json(spec_path)
            scenarios = response.get("scenarios") if isinstance(response, dict) else None
            if not scenarios:
                log(f"{spec_path} 에 scenarios 가 없습니다. --spec 에는 시나리오 응답 파일을 주세요.")
                return 2
            if flag("--input"):
                product = parse_worker_input(read_json(flag("--input")))["product_info"]
            else:
                # 입력이 없으면 근거 ID 만 자리로 채운다. 근거 없는 표현 검사는 사실 문장이 없어 엄격하게 된다.
                log("--input 이 없어 제품 사실 없이 검사합니다 (근거 ID 확인 생략).")
                highest = max([int(c[1:]) for s in scenarios for c in (s.get("ad_spec") or {}).get("claim_ids") or []
                               if str(c)[1:].isdigit()] + [0])
                product = {"name": "", "verified_facts": [f"(입력 없음 {i})" for i in range(1, highest + 1)]}
            rows = [{"title": s.get("hook_title", ""), **check_scenario(s, product)} for s in scenarios]
            return 0 if print_checks(rows) else 2
    except InputError as exc:
        log(f"입력 오류: {exc}")
        return 1
    except Exception as exc:  # 실행 오류 (모델 호출 실패 등)
        log(f"실행 오류: {exc}")
        return 1
    print(USAGE, file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
