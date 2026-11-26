"""C 유형 규칙 검사. API 호출 없음.

errors 는 규칙 위반(종료 코드 2), warnings 는 사람이 볼 항목이다. 기준은 ../README.md 의 유형 규칙.
"""
from __future__ import annotations

import re

from .schema import HOOK_TYPE, MAX_BEATS, MAX_HOOK_SEC, MIN_BEATS, fact_ids

# verified_facts 에 근거가 있을 때만 쓸 수 있는 표현.
UNVERIFIED_PATTERNS = [
    (r"무소음|소음\s*없", "무소음"),
    (r"배터리|충전", "배터리"),
    (r"\d+\s*(dB|데시벨)", "소리 크기(dB)"),
    (r"\d+(\.\d+)?\s*(cm|mm|센티|밀리|kg|g\b|그램|ml|리터)", "치수·용량"),
    (r"\d[\d,]*\s*원|할인|특가|세일|최저가|무료\s*배송|\d+\s*%", "가격·할인"),
    (r"\d+\s*(개월|주|일)\s*(지속|사용|간다|가요)", "지속 기간"),
    (r"최고|1위|유일|완벽|100\s*%", "최상급 표현"),
]
SALES_PATTERNS = r"공구|공동구매|구매\s*링크|프로필\s*링크|지금\s*구매|주문하세요|쿠폰"
PROBLEM_ROLES = ("문제", "problem")
PROOF_ROLES = ("증명", "proof")
CTA_ROLES = ("cta", "CTA")
CAPTION_MAX_LINES, CAPTION_MAX_CHARS = 2, 22


def check_scenario(s: dict, product_info: dict) -> dict:
    errors: list[str] = []
    warnings: list[str] = []
    facts = fact_ids(product_info)
    fact_text = " ".join(facts.values())
    beats = s.get("beats") or []

    if s.get("type") != HOOK_TYPE:
        errors.append(f'type 이 "{HOOK_TYPE}" 가 아닙니다: {s.get("type")!r}')
    if not (MIN_BEATS <= len(beats) <= MAX_BEATS):
        errors.append(f"장면 수는 {MIN_BEATS}~{MAX_BEATS}개여야 합니다 (현재 {len(beats)}개).")
    total = round(sum(float(b.get("duration_sec", 0)) for b in beats), 2)
    if abs(total - float(s.get("hook_duration_sec", 0))) > 0.05:
        errors.append(f"장면 길이 합({total}초)이 hook_duration_sec({s.get('hook_duration_sec')}초)와 다릅니다.")
    if total > MAX_HOOK_SEC + 1e-6:
        errors.append(f"훅 길이가 {MAX_HOOK_SEC:g}초를 넘습니다 ({total}초).")
    if [b.get("order") for b in beats] != list(range(1, len(beats) + 1)):
        errors.append("beats[].order 는 1부터 순서대로여야 합니다.")
    if not str(s.get("replacement_test_note", "")).strip():
        errors.append("replacement_test_note(교체 테스트 판정 근거)가 비어 있습니다.")

    if beats:
        if not any(k in str(beats[0].get("role", "")) for k in PROBLEM_ROLES):
            errors.append(f"첫 장면은 문제 훅이어야 합니다 (role: {beats[0].get('role')!r}).")
        if len(beats) > 1 and not any(k in str(beats[1].get("role", "")) for k in PROOF_ROLES):
            errors.append(f"둘째 장면에 가장 강한 실물 증명을 둬야 합니다 (role: {beats[1].get('role')!r}).")
    cta_beats = [b for b in beats if any(k in str(b.get("role", "")) for k in CTA_ROLES)]
    if len(cta_beats) > 1:
        errors.append(f"CTA 장면은 하나여야 합니다 (현재 {len(cta_beats)}개).")
    if not cta_beats:
        warnings.append("CTA 장면이 없습니다. 본편에서 CTA 를 낼 계획이 아니면 추가하세요.")

    spec = s.get("ad_spec") or {}
    if spec.get("track_archetype") != "C_direct_proof":
        errors.append('ad_spec.track_archetype 은 "C_direct_proof" 여야 합니다.')
    if spec.get("disclosure") != "ai_assisted":
        errors.append('ad_spec.disclosure 는 "ai_assisted" 여야 합니다.')
    if (spec.get("cta") or {}).get("type") != "comment_engagement":
        errors.append('ad_spec.cta.type 은 "comment_engagement" 여야 합니다.')
    if not str((spec.get("cta") or {}).get("text", "")).strip():
        errors.append("ad_spec.cta.text 가 비어 있습니다.")
    if spec.get("proof_first") is not True:
        errors.append("ad_spec.proof_first 는 true 여야 합니다.")
    claims = spec.get("claim_ids") or []
    unknown = [c for c in claims if c not in facts]
    if unknown:
        errors.append(f"verified_facts 에 없는 근거 ID: {', '.join(unknown)}")
    if not (2 <= len(claims) <= 3) and len(facts) >= 2:
        warnings.append(f"검증된 장점은 2~3개를 권장합니다 (claim_ids {len(claims)}개).")

    for b in beats:
        n = b.get("order")
        text = f"{b.get('narration', '')} {b.get('caption', '')}"
        for pattern, label in UNVERIFIED_PATTERNS:
            m = re.search(pattern, text)
            if m and not re.search(pattern, fact_text):
                errors.append(f"장면 {n}: verified_facts 에 근거가 없는 표현({label}): “{m.group(0)}”")
        if re.search(SALES_PATTERNS, text):
            errors.append(f"장면 {n}: 판매·공동구매 표기는 쓸 수 없습니다 (댓글 유도만).")
        lines = str(b.get("caption", "")).split("\n")
        if len(lines) > CAPTION_MAX_LINES:
            errors.append(f"장면 {n}: 자막은 {CAPTION_MAX_LINES}줄 이내여야 합니다.")
        long_lines = [l for l in lines if len(l) > CAPTION_MAX_CHARS]
        if long_lines:
            warnings.append(f"장면 {n}: 자막 줄이 {CAPTION_MAX_CHARS}자를 넘습니다: “{long_lines[0]}”")
        if not str(b.get("narration", "")).strip():
            warnings.append(f"장면 {n}: 나레이션이 비어 있습니다.")
        # 한국어 나레이션은 초당 약 6~7음절. 장면 길이에 비해 너무 길면 음성이 빨라진다.
        syllables = len(re.findall(r"[가-힣]", str(b.get("narration", ""))))
        if float(b.get("duration_sec", 0)) and syllables / float(b["duration_sec"]) > 7.5:
            warnings.append(f"장면 {n}: 나레이션이 장면 길이에 비해 깁니다 ({syllables}음절 / {b['duration_sec']}초).")
    return {"errors": errors, "warnings": warnings}
