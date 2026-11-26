"""C 유형(C_direct_proof) 시나리오 프롬프트."""
from __future__ import annotations

from .schema import fact_ids

# 생성 문제 장면 템플릿 설명. 문제 훅 문구가 화면과 맞도록 모델에 알려 준다.
PROBLEM_TEMPLATES = {
    "spill_diffuser": "밝은 실내 테이블에서 지나가던 손이 액체형 리드 디퓨저를 쳐서 쓰러뜨리고, 병 입구에서 액체가 쏟아져 번지는 장면 (3D 생성, 약 3초)",
}

SYSTEM = """당신은 한국어 숏폼 광고의 C 유형 훅(C_direct_proof: 제품과 직접 연결된 훅) 시나리오 작가입니다.

C 유형이 지켜야 하는 것과 그 이유:
- 첫 장면은 밝고 날것인 POV 문제 상황입니다. 보는 사람이 자기 일로 느껴야 첫 3초를 넘깁니다.
- 둘째 장면에 제품의 가장 강한 실물 동작 증명을 둡니다. 문제를 본 직후에 해결되는 모습을 봐야 계속 봅니다.
- 그 문제는 이 제품의 고유한 특징으로만 풀려야 합니다. 다른 제품 광고에 옮겨 붙일 수 있으면 C 가 아닙니다.
- 제품에 대한 말은 입력의 검증된 사실에 있는 내용만 씁니다. 근거 없는 수치, 효능, 가격, 할인, 최상급 표현은 광고 심의와 신뢰를 깨뜨리므로 쓰지 않습니다.
- 증명 장면은 실제 제품이 실제로 하는 동작만 묘사합니다. 없는 기능을 연출하지 않습니다.
- CTA 는 댓글을 유도하는 질문 하나입니다. 판매, 공동구매, 구매 링크 표기는 넣지 않습니다.

형식:
- 장면은 3~5개, 길이 합은 15초 이하입니다. 장면마다 role 은 "문제", "가장 강한 증명", "장점", "CTA" 중에서 고릅니다. 첫 장면은 "문제", 둘째는 "가장 강한 증명", 마지막은 "CTA" 입니다.
- narration 은 말하듯 자연스러운 구어체로, 장면 길이 1초당 6음절 안팎입니다. 숫자는 한글로 읽히게 씁니다.
- caption 은 2줄 이내, 한 줄 22자 이내이고 줄바꿈은 \\n 입니다.
- visual 에는 무엇이 보이는지 쓰고, 근거가 되는 사실 ID 를 [F02] 처럼 붙입니다.
- claim_ids 에는 이 시나리오가 실제로 쓴 사실 ID 를 2~3개 넣습니다.
- pov_label 은 첫 장면 화면 위에 띄울 짧은 상황 설명입니다 (예: 디퓨저 옆을 지나가던 나).
- replacement_test_note 는 왜 다른 제품에 옮겨 붙일 수 없는지 한 줄로 씁니다.
- cta_text 는 마지막 장면의 댓글 유도 질문입니다."""


def build_user_prompt(inp: dict, violations: list[str] | None = None) -> str:
    product = inp["product_info"]
    lines = [
        f"제품: {product['name']} (카테고리: {product.get('category', '미정')})",
        "검증된 사실:",
        *[f"- [{fid}] {text}" for fid, text in fact_ids(product).items()],
    ]
    if product.get("target_audience"):
        lines.append(f"대상: {product['target_audience']}")
    assets = inp.get("assets") or {}
    template = assets.get("problem_template")
    if template in PROBLEM_TEMPLATES:
        lines += ["", f"첫 장면(문제)은 이 생성 영상으로 만들어집니다: {PROBLEM_TEMPLATES[template]}",
                  "문제 훅의 나레이션과 자막은 이 화면에 맞춰 주세요. 첫 장면 길이는 3초로 합니다."]
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
