# NAPDA A · B · C 훅 워커 통합 계약 (`WORKER_CONTRACT.md`)

A안(무맥락 반전), B안(정보성 오프셋), C안(실용/공감 직격) 작업자 코드를 백엔드 코어([`../app/pipeline.py`](../app/pipeline.py))와 충돌·재작성 없이 병합하기 위한 표준 인터페이스 계약입니다.

---

## 1. 코어 vs 워커 책임 경계

| 계층 | 소유 대상 | 비소유(침범 금지) |
|---|---|---|
| **백엔드 코어** (`backend/app/`) | `POST /v1/product-info` + `selling-point-miner` 증거 수집·7일 캐시, 프로젝트/회차 DB, `selected_types` 라우팅(`WORKERS["A" \| "B" \| "C"]`), `OUTPUT_DIR/{project_id}/{hook_id}/` 파일 영구 저장, `FR-010` 본편 합치기 | A/B/C 개별 프롬프트·장르·유사도·금칙어 규칙 직접 수정 금지 |
| **훅 워커** (`bridge-dev/{a,b,c}/`) | `generate_scenarios(WorkerInput) -> ScenariosResponse`, `build_storyboard`, `render_hook` **3개 기능만 구현** | DB 접근, 타 유형(`A↔B↔C`) 규칙 수정, 제품 크롤링/PII 저장 금지 |

---

## 2. 언어·엔진 비의존 어댑터 규약 (재작성 금지)

백엔드는 **Python FastAPI**, B안은 **TypeScript(Claude + Three.js/Remotion)**, A안은 **TypeScript(블라인드 4단계) + Blender 5.1 / Google Flow** 등 각자 최적의 스택을 유지한 채 **표준 JSON 어댑터**로 연결합니다.

### 방식 1 — 표준 CLI 어댑터 (즉시 병합 권장)
```bash
# 1) 시나리오 생성 (FR-003)
<worker_cmd> generate --input worker_input.json --out scenarios_response.json
# Exit Code: 0 = 통과, 2 = 규칙 위반(에러 세부사항 stderr 출력), 1 = 런타임 오류

# 2) 규칙 정적 검증 (무과금 게이트)
<worker_cmd> check --spec scenarios_response.json [--input worker_input.json]
```

### 방식 2 — 내부 HTTP 마이크로서비스 어댑터 (스케일아웃 시)
- `POST /internal/workers/{a|b|c}/scenarios` (`body = WorkerInput`, `resp = ScenariosResponse`)
- `POST /internal/workers/{a|b|c}/storyboard`
- `POST /internal/workers/{a|b|c}/hooks`

---

## 3. 공통 `ScenarioItem` + 유형별 `ad_spec` 네임스페이스

### 공통 루트 필드 (`ScenarioItem`)
- `scenario_id`: string (`sc_...`)
- `round`: int (`>= 1`, `"더 뽑기"` 누적)
- `type`: `"A" | "B" | "C"`
- `hook_title`: string
- `hook_duration_sec`: float (`<= 15.0`, `sum(beats[].duration_sec)`와 `0.05s` 이내 일치)
- `body_duration_sec`: float
- `replacement_test_note`: string (교체 테스트 판정 근거 1줄)
- `beats[]`: `3~5`개 객체 (`order`, `role`, `duration_sec`, `visual`, `narration`, `caption`)
- `ad_spec`: 아래 유형별 스키마 중 해당 `track_archetype` 사용

### 유형별 `ad_spec` 전용 필드

| 유형 | `track_archetype` | 필수/권장 `ad_spec` 키 | 핵심 자동 검증 게이트 |
|---|---|---|---|
| **A (무맥락)** | `"A_bgrade_reversal"` | `a_genre_archetype`, `abstract_law`, `visual_style`, `product_taboo_keywords[]`, `category_taboo_keywords[]`, `reference_surface_taboo[]`, `silence_gap_sec`, `pre_twist_ratio`, `payoff_ratio` | 반전 전 비트 금칙어/카테고리 0%, `previous_scenarios` 장르 중복 차단, `silence_gap` `0.18~0.32s`, 착지 비중 `<= 55%` |
| **B (정보성)** | `"B_info_hook_offset"` | `hook_similarity_score`, `anchor`, `bridge_path[]`, `adjacent_min_sim`, `number_thread`, `product_first_mention_beat`, `product_taboo_keywords[]`, `fact_sources[]` | 시작 유사도 `0.40~0.60`, 인접 `>= 0.70`, `"~습니다"`체, 반전 전 제품명 차단, `3D scene3d` 검증 |
| **C (직격)** | `"C_direct_proof"` | `claim_ids[]`, `proof_first`, `cta{type, text}`, `disclosure` | `verified_facts` 인용(`F##`), 과장 문구 차단, 실물 동작 증명 선배치, 단일 CTA |

---

## 4. `FR-005` 미디어 출력 표준 (`OUTPUT_DIR/{project_id}/{hook_id}/`)

내부 렌더러가 **Blender 5.1 EEVEE**, **Remotion/Three.js**, **Google Flow** 중 무엇이든 완료(`done`) 시점에는 반드시 아래 동일 규격으로 저장합니다.

```text
OUTPUT_DIR/{project_id}/{hook_id}/
├── hook.mp4              # 1080x1920 (9:16), 30fps CFR H.264, <= 15s, 오디오 -14.0 LUFS
├── tts.mp3               # beats[].narration 합성 트랙
├── hook.srt              # beats[].caption 동기 자막 (한 줄 <= 22자, 2줄 이내, 이모지 금지)
├── scenario.json         # 채택된 ScenarioItem 원문
└── storyboard_01.png …   # beat_order별 9:16 콘티 이미지
```

---

## 5. 병합 전 체크리스트 (A · B · C · 백엔드)

- [ ] **입출력 동등성**: 각 워커가 `examples/01_worker-input.scenarios.json` 입력으로 `02_scenarios.response.json` 스키마를 100% 통과하는가?
- [ ] **무과금 Mock 테스트**: API 키 없이 `MockLanguageModelV4` 기반 `npm test`(또는 `pytest`)로 `1차 위반 → 자동 재시도 → 통과` 루프가 도는가?
- [ ] **중복 방지**: `previous_scenarios[]`를 넘겨 2회차(`--next`) 호출 시 이전 소재/장르를 피하는가?
- [ ] **교차 팩트 준수**: `verified_facts[]`에 없는 수치·기능(임의 `%`, 미확인 지속력 등)을 생성하지 않는가?
