"""문제 장면의 구도 참고 이미지(Blender 블록아웃) 목록.

`../blockouts/catalog.json` 에 미리 렌더해 둔 블록아웃을 적어 둔다. 글 모델이 첫 장면(문제)과 같은 상황인 것을 하나 고르면
(`problem_blockout`), 그 장면에 `first_frame_ref`·`first_frame_prompt` 를 붙인다. 백엔드(backend/hookpipe)는 이 이미지를
이미지 모델로 같은 구도의 실사 화면으로 바꾸고, 영상 모델이 그 화면에서 시작하는 클립을 만든다.
고르지 않으면 아무것도 붙이지 않고, 그 장면은 지금까지처럼 글만으로 만들어진다. 쓰는 법은 ../blockouts/README.md.
"""
from __future__ import annotations

import json
from pathlib import Path

CATALOG_PATH = Path(__file__).resolve().parents[1] / "blockouts" / "catalog.json"


def load_catalog(path: Path | None = None) -> list[dict]:
    """목록을 읽는다. 파일이 없거나 깨졌으면 빈 목록 (구도 참고 없이 동작한다)."""
    try:
        data = json.loads((path or CATALOG_PATH).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return [b for b in data if isinstance(b, dict) and b.get("id") and b.get("image")] if isinstance(data, list) else []


def prompt_lines(catalog: list[dict]) -> list[str]:
    """사용자 프롬프트에 붙일 구도 목록. 목록이 비어 있으면 빈 리스트."""
    if not catalog:
        return ["첫 장면의 구도 참고 목록이 없습니다. problem_blockout 은 빈 문자열로 둡니다."]
    lines = ["첫 장면(문제)의 구도 참고 목록입니다. 첫 장면이 아래 중 하나와 같은 상황일 때만 problem_blockout 에 그 id 를 적고, "
             "아니면 빈 문자열로 둡니다. 구도에 맞추려고 문제 상황을 바꾸지 않습니다:"]
    lines += [f"- {b['id']}: {b.get('description', '')}" for b in catalog]
    return lines


def attach(scenario: dict, blockout_id: str, catalog: list[dict] | None = None) -> dict:
    """고른 블록아웃을 첫 장면에 붙인다. 목록에 없는 id 는 조용히 무시한다 (글 모델이 지어낸 값일 수 있다)."""
    chosen = next((b for b in (load_catalog() if catalog is None else catalog) if b["id"] == str(blockout_id or "").strip()), None)
    beats = scenario.get("beats") or []
    if not chosen or not beats:
        return scenario
    beats[0]["first_frame_ref"] = chosen["image"]
    if chosen.get("refine_prompt"):
        beats[0]["first_frame_prompt"] = chosen["refine_prompt"]
    scenario.setdefault("ad_spec", {})["problem_blockout"] = chosen["id"]
    return scenario
