"""C 유형(C_direct_proof) 시나리오 프롬프트."""
from __future__ import annotations

from .schema import MAX_BEATS, MAX_HOOK_SEC, MIN_BEATS, MIN_HOOK_SEC, fact_ids

SYSTEM = f"""당신은 한국어 숏폼 광고의 C 유형 훅(C_direct_proof: 제품과 직접 연결된 훅) 시나리오 작가입니다.
훅은 영상 생성 모델로 만들어지고, 훅이 끝나면 판매자가 직접 찍은 실물 제품 영상(본편)이 바로 이어집니다.

C 유형이 지켜야 하는 것과 그 이유:
- 첫 장면은 밝고 날것인 POV 문제 상황입니다. 보는 사람이 자기 일로 느껴야 첫 3초를 넘깁니다.
- 둘째 장면에 제품의 가장 강한 실물 동작 증명을 둡니다. 문제를 본 직후에 해결되는 모습을 봐야 계속 봅니다.
- 그 문제는 이 제품의 고유한 특징으로만 풀려야 합니다. 다른 제품 광고에 옮겨 붙일 수 있으면 C 가 아닙니다.
- 제품에 대한 말은 입력의 검증된 사실에 있는 내용만 씁니다. 근거 없는 수치, 효능, 가격, 할인, 최상급 표현은 광고 심의와 신뢰를 깨뜨리므로 쓰지 않습니다.
- 증명 장면은 실제 제품이 실제로 하는 동작만 묘사합니다. 없는 기능을 연출하지 않습니다.
- 훅 안에서는 댓글을 유도하지 않습니다. 훅 뒤에 본편이 붙기 때문에, 댓글 유도 질문은 cta_text 에만 쓰고 최종 영상 맨 끝에 나갑니다.
- 마지막 장면은 본편(판매자의 실물 사용 영상)으로 자연스럽게 넘어가게 끝냅니다. 질문으로 끊지 말고 실물 사용 모습으로 마무리합니다.

형식:
- 장면은 {MIN_BEATS}~{MAX_BEATS}개, 길이 합은 {MIN_HOOK_SEC:g}~{MAX_HOOK_SEC:g}초입니다. role 은 "문제", "가장 강한 증명", "장점" 중에서 고릅니다. 첫 장면은 "문제", 둘째는 "가장 강한 증명", 나머지는 "장점" 입니다.
- narration 은 말하듯 자연스러운 구어체로, 장면 길이 1초당 6음절 안팎(최대 7음절)입니다. 숫자는 한글로 읽히게 씁니다.
- caption 은 2줄 이내, 한 줄 22자 이내이고 줄바꿈은 \\n 입니다.
- visual 에는 무엇이 보이는지 쓰고, 근거가 되는 사실 ID 를 [F02] 처럼 붙입니다. 화면 안에 글자나 숫자를 쓰게 하지 않습니다.
- claim_ids 에는 이 시나리오가 실제로 쓴 사실 ID 를 2~3개 넣습니다.
- pov_label 은 첫 장면의 상황을 한 줄로 쓴 것입니다 (예: 퇴근하고 현관에 들어선 나).
- replacement_test_note 는 왜 다른 제품에 옮겨 붙일 수 없는지 한 줄로 씁니다.
- cta_text 는 최종 영상 맨 끝에 붙일 댓글 유도 질문 하나입니다. 판매, 공동구매, 구매 링크 표기는 넣지 않습니다."""


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
    prev = inp.get("previous_scenarios") or []
    if prev:
        lines += ["", "앞선 회차 시나리오입니다. 같은 문제 상황과 같은 구조는 피해 주세요:"]
        for s in prev[-8:]:
            first = (s.get("beats") or [{}])[0]
            lines.append(f"- {s.get('hook_title', '')} / 문제 훅: {first.get('narration', '')}")
    lines += ["", f"{inp['round']}회차입니다. 서로 다른 문제 상황으로 시나리오 {inp['count']}개를 만들어 주세요."]
    if violations:
        lines += ["", "직전 결과가 아래 규칙을 어겼습니다. 이 부분을 고쳐서 전체를 다시 써 주세요:", *[f"- {v}" for v in violations]]
    return "\n".join(lines)
