"""C 유형(C_direct_proof) 시나리오 프롬프트."""
from __future__ import annotations

import os

from .schema import fact_ids

# 생성 문제 장면 템플릿 설명. 문제 훅 문구가 화면과 맞도록 모델에 알려 준다.
PROBLEM_TEMPLATES = {
    "spill_diffuser": "밝은 실내 테이블에서 지나가던 손이 액체형 리드 디퓨저를 쳐서 쓰러뜨리고, 병 입구에서 액체가 쏟아져 번지는 장면 (3D 생성, 약 3초)",
    "cat_spill_diffuser": "밝은 거실 테이블에서 고양이가 액체형 리드 디퓨저를 앞발로 툭 쳐서 쓰러뜨리고, 병 입구에서 액체가 쏟아져 번지는 장면 (생성 영상, 약 3.5초)",
    "spray_panic": "밝은 거실. 손이 방향제 스프레이를 사방으로 급하게 뿌려 하얀 분무가 방을 채우는 장면 (생성 영상, 약 3.5초)",
    "carry_drip": "밝은 거실. 손이 리드 디퓨저를 들어 옮기다 병이 기울어 액체가 줄줄 흘러 테이블에 자국이 남는 장면 (생성 영상, 약 3.5초)",
    "reed_flip": "밝은 거실. 두 손이 리드 스틱을 뽑아 뒤집다가 오일이 손가락과 테이블에 뚝뚝 떨어지는 장면 (생성 영상, 약 3.5초)",
    "evaporate_diffuser": "밝은 실내 테이블 위 액체형 리드 디퓨저의 며칠짜리 타임랩스. 처음 채운 높이에 붙인 테이프는 그대로인데 "
                          "액체만 바닥까지 줄어들고 막대가 말라 간다 (3D 생성, 약 4초)",
    "phone_distract": "밝은 책상. 펜을 내려놓은 손이 옆에 있던 스마트폰을 집어 엄지로 계속 넘겨 보고, 펼친 노트는 그대로인 장면 (생성 영상, 약 3.5초)",
    "drain_smell": "욕실 불을 켜고 들어선 POV. 바닥 배수구에서 냄새가 물결 모양 연기로 올라오고 카메라가 움찔 물러난다 (3D 생성, 약 3.5초)",
    "closet_musty": "장마철 방에서 옷장 문을 여는 POV. 빽빽이 걸린 옷 사이에서 꿉꿉한 냄새가 옅은 연기처럼 새어 나오고 카메라가 살짝 물러난다 (생성 영상, 약 3.5초)",
}
PROBLEM_TEMPLATES["phone_distract_blockout"] = PROBLEM_TEMPLATES["phone_distract_desk"] = PROBLEM_TEMPLATES["phone_distract"]
PROBLEM_SECONDS = {"phone_distract_desk": 3.5, "phone_distract_blockout": 3.5, "phone_distract": 3.5, "spill_diffuser": 3, "evaporate_diffuser": 4, "drain_smell": 3.5, "closet_musty": 3.5, "cat_spill_diffuser": 3.5, "spray_panic": 3.5, "carry_drip": 3.5, "reed_flip": 3.5}

SKILL_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "skills", "c-direct-proof-hook", "SKILL.md")


def skill_path() -> str:
    return os.environ.get("C_SKILL_PATH", "").strip() or SKILL_PATH


def system_prompt() -> str:
    """시나리오 규칙. 코드에 적지 않고 스킬 파일(SKILL.md)의 본문을 읽는다. 맨 위 머리말(--- … ---)과 안내 인용문(>)은 뺀다."""
    path = skill_path()
    try:
        text = open(path, encoding="utf-8").read()
    except OSError as e:
        raise RuntimeError(f"C 스킬 파일을 읽지 못했습니다: {path}") from e
    if text.startswith("---"):
        text = text.split("---", 2)[2]
    lines = [ln for ln in text.splitlines() if not ln.startswith(">")]
    body = "\n".join(lines).strip()
    if not body:
        raise RuntimeError(f"C 스킬 파일이 비어 있습니다: {path}")
    return body


def build_user_prompt(inp: dict, violations: list[str] | None = None) -> str:
    product = inp["product_info"]
    lines = [
        f"제품: {product['name']} (카테고리: {product.get('category', '미정')})",
        "검증된 사실:",
        *[f"- [{fid}] {text}" for fid, text in fact_ids(product).items()],
    ]
    points = inp.get("selling_points") or []
    if points:
        lines += ["", "소구포인트 (구매자가 이 제품을 사는 이유. 문제 상황은 여기에서 고릅니다):"]
        for p in points:
            lines.append(f"- {p['point']}" + (f" (출처: {p['source']})" if p["source"] else ""))
            lines += [f"    근거: “{e}”" for e in p["evidence"][:4]]
        lines += ["소구포인트는 어떤 문제 상황으로 시작할지 정하는 방향입니다. 근거에 나온 장소와 상황을 문제 장면으로 쓰세요.",
                  "제품에 대한 말은 여전히 검증된 사실에 있는 내용만 쓰고, 소구포인트의 수치나 효능을 사실처럼 옮기지 않습니다.",
                  "selling_point 에는 이 시나리오가 겨냥한 소구포인트를 위 목록의 문장 그대로 적습니다."]
    else:
        lines.append("소구포인트 입력이 없습니다. selling_point 는 빈 문자열로 둡니다.")
    if product.get("target_audience"):
        lines.append(f"대상: {product['target_audience']}")
    assets = inp.get("assets") or {}
    template = assets.get("problem_template")
    if template in PROBLEM_TEMPLATES:
        lines += ["", f"첫 장면(문제)은 이 생성 영상으로 만들어집니다: {PROBLEM_TEMPLATES[template]}",
                  f"문제 훅의 나레이션과 자막은 이 화면에 맞춰 주세요. 첫 장면 길이는 {PROBLEM_SECONDS[template]}초로 합니다."]
    if assets.get("product_footage"):
        lines.append("둘째 장면부터는 실물 제품 영상 한 컷을 이어서 씁니다. visual 은 그 영상에 나올 법한 실물 장면으로 써 주세요.")
    prev = inp.get("previous_scenarios") or []
    if prev:
        lines += ["", "앞선 회차 시나리오입니다. 같은 소재와 같은 구조는 피해 주세요:"]
        for s in prev[-8:]:
            first = (s.get("beats") or [{}])[0]
            lines.append(f"- {s.get('hook_title', '')} / 문제 훅: {first.get('narration', '')}")
    lines += ["", f"{inp['round']}회차입니다. 서로 다른 문제 상황으로 시나리오 {inp['count']}개를 만들어 주세요."]
    if violations:
        lines += ["", "직전 결과가 아래 규칙을 어겼습니다. 이 부분을 고쳐서 전체를 다시 써 주세요:", *[f"- {v}" for v in violations]]
    return "\n".join(lines)
