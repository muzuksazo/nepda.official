# C 훅 작업자 가이드 — 제품과 직접 연결된 훅

## 이 유형의 정의

저장소 README의 교체 테스트 기준: **C = 특정 제품과 직접 연결된 훅.** 다른 제품 광고에 옮겨 붙이기 어려움. 문제 상황으로 열고, 제품의 가장 강한 동작 증명을 앞에 둡니다.

## 이 작업자가 받는 요청

공개 API 요청은 모두 백엔드가 받고, 백엔드는 프로젝트의 `selected_types`가 `["C"]`이면 이 유형 작업자 코드를 호출합니다. 작업자 코드로 들어오는 경우는 세 가지입니다.

| 들어오는 공개 API | 작업자가 하는 일 | 작업자가 반환 |
|---|---|---|
| `POST /v1/projects/{id}/scenarios` | 시나리오 `count`개 생성 | `ScenarioItem[]` (`type: "C"`, `round`) |
| `POST /v1/projects/{id}/scenarios/{sid}/storyboard` | 장면별 콘티 이미지 생성 | `StoryboardFrame[]` |
| `POST /v1/projects/{id}/hooks` | 선택된 시나리오로 훅 영상 + TTS 생성 | 영상·음성·자막 파일(상태는 폴링 응답으로) |

시나리오 생성 시 작업자 코드가 받는 입력은 아래와 같습니다. 공개 API가 아니라 `POST /scenarios` 처리 중의 **내부 호출(제안 인터페이스)**이며, 필드 이름은 백엔드 구현에서 확정합니다. 예시: `examples/01_worker-input.scenarios.json`

| 필드 | 설명 |
|---|---|
| `hook_type` | `"C"` 고정 |
| `product_info` | `ProductInput`(`name`, `category`, `verified_facts[]`, 선택 `price_or_offer`, `target_audience`). `verified_facts`에 없는 사실은 쓰지 않는다 |
| `project_id`, `round`, `count` | 몇 번째 뽑기인지와 만들 개수 |
| `previous_scenarios[]` | 앞선 회차 시나리오. 더 뽑을 때 같은 소재·구조를 반복하지 않기 위해 참고 |

콘티와 훅 단계에서는 저장된 `ScenarioItem`(`scenario_id`로 조회)과 `tts` 옵션만 받으면 됩니다.

## 시나리오 생성 시 지켜야 할 유형 규칙

기준 문서: `skills/shortform-ad-hooks-blueprint/SKILL.md`의 Track C(`C_direct_proof`).

- 밝고 날것인 POV 문제 훅으로 시작하고 곧바로 제품의 가장 강한 실물 동작 증명을 앞쪽에 둔다.
- 검증된 장점 2~3개를 `verified_facts`에서 골라 근거 ID(`F01`…)와 함께 쓴다. 증명 장면은 실제 제품 동작만 보여 준다(없는 기능을 연출하지 않는다).
- PAS(문제-자극-해결)·스펙 설득과 단일 CTA는 C에만 쓴다. A·B로 번지지 않게 한다.
- CTA는 하나. 광고 표시: `ad_spec.disclosure: "ai_assisted"`, 판매·공동구매 표기 없이 댓글 유도(`comment_engagement`) 방식.
- 금지: 미검증 주장(무소음, 배터리, 알람 dB, 치수, 가격·할인). 뽀모도로 타이머의 허용 문구는 `00_product_facts.md`의 Whitelisted 항목.
- 권장 `ad_spec` 키: `track_archetype: "C_direct_proof"`, `claim_ids[]`, `proof_first`, `cta{type, text}`, `disclosure`.

## 반환해야 할 응답 형태

필드 정의는 `../api-guide.md`와 `openapi.json`이 기준입니다. 이 유형의 예시:

| 단계 | 반환 | 예시 |
|---|---|---|
| 시나리오 | `{ round, scenarios[] }` — 각 `ScenarioItem`: `scenario_id`, `round`, `type: "C"`, `hook_title`, `hook_duration_sec`(≤15), `body_duration_sec`, `replacement_test_note`, `beats[]`(`order`, `role`, `duration_sec`, `visual`, `narration`, `caption`), `ad_spec` | `examples/02_scenarios.response.json` |
| 콘티 | `{ frames[] }` — `beat_order`(= `beats[].order`), `image_url`, `caption` | `examples/03_storyboard.response.json` |
| 훅(폴링) | `{ status, files{hook_video, tts_audio, subtitles_srt, scenario_json, storyboard_images[]}, output_dir }` | `examples/04_hook-status.done.json` |

공통 규칙: 장면 길이 합 = `hook_duration_sec` ≤ 15초, 장면 3~5개, `replacement_test_note`에는 교체 테스트 판정 근거를 한 줄로 씁니다. `ad_spec`에는 위 "유형 규칙"에서 정한 키를 넣습니다(유형 규칙 검증과 이후 린트에 쓰이는 값).

## 결과 파일 저장 위치와 이름

훅이 `done`이 되면 아래 폴더에 저장합니다(`OUTPUT_DIR` 기본값은 미정, 여기서는 `output/`).

```text
OUTPUT_DIR/{project_id}/{hook_id}/
├── hook.mp4              훅 영상 (15초 이하, 9:16)
├── tts.mp3               나레이션 음성 (beats[].narration)
├── hook.srt              자막 (beats[].caption, 장면 시작·끝 시각 기준)
├── scenario.json         이 훅에 쓴 ScenarioItem 그대로 (c/examples/05_saved-scenario.json 참고)
└── storyboard_01.png …   콘티 이미지 (2자리 번호 = beat_order)
```

회차가 달라지면 `hook_id`가 다른 새 폴더가 생기고 기존 폴더는 지우지 않습니다.

## index.html로 테스트하기

1. `python -m http.server 5500 --directory backend/bridge-dev` 후 `http://127.0.0.1:5500/`를 엽니다(파일로 열어도 됩니다).
2. 훅 유형에서 **C**를 선택합니다. 제품 정보는 뽀모도로 타이머가 미리 채워져 있습니다.
3. Mock으로 흐름을 먼저 확인합니다: "처음부터 끝까지(1회)" 또는 "시나리오 더 뽑기 n회". 오른쪽 로그에서 요청 body와 응답 형태를 봅니다.
4. 내 코드로 확인: Mock을 끄고 Base URL을 백엔드로, Bearer 토큰에 `python backend/bridge-dev/dev_token.py --user worker-c` 결과를 넣고 같은 버튼을 누릅니다. 응답이 위 예시와 다르면 로그의 curl 복사로 재현합니다. CORS와 인증은 `../README.md`를 참고하세요.
5. 끝나면 "결과 저장"으로 회차별 결과를 JSON으로 받아 예시와 비교합니다.

## 저장소의 C 캠페인 예시

- `prototypes/campaigns/digimore-timer-abc/05_ad_spec_C.json` (뽀모도로 직격)
- 같은 폴더의 `audio/vo_plan_C.json`, `final/ad_C_pomodoro_direct.srt`, `05_lint_report_C.md`, `00_product_facts.md`
