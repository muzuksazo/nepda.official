# B 훅 작업자 가이드 — 제품을 약하게 짐작하는 정보성 훅

## 이 유형의 정의

저장소 README의 교체 테스트 기준: **B = 제품을 약하게 짐작할 수 있는 훅. 제품으로 넘어가는 장면을 수정하면 다른 제품 광고에 연결할 수 있음.** 어긋난 정보로 시작해 브리지를 거쳐 반전 장면에서 제품이 탁 치는 구조입니다. 훅만 보고 제품을 살짝 짐작할 수 있으면 B, 짐작하기 어려우면 A입니다.

## 이 작업자가 받는 요청

공개 API 요청은 모두 백엔드가 받고, 백엔드는 프로젝트의 `selected_types`가 `["B"]`이면 **이 유형 작업자 코드**를 호출합니다. 작업자 코드로 들어오는 경우는 세 가지입니다.

| 들어오는 공개 API | 작업자가 하는 일 | 작업자가 반환 |
| --- | --- | --- |
| `POST /v1/projects/{id}/scenarios` | 시나리오 `count`개 생성 | `ScenarioItem[]` (`type: "B"`, `round`) |
| `POST /v1/projects/{id}/scenarios/{sid}/storyboard` | 장면별 콘티 이미지 생성 | `StoryboardFrame[]` |
| `POST /v1/projects/{id}/hooks` | 선택된 시나리오로 훅 영상 + TTS 생성 | 영상·음성·자막 파일(상태는 폴링 응답으로) |

시나리오 생성 시 작업자 코드가 받는 입력은 아래와 같습니다. 공개 API가 아니라 `POST /scenarios` 처리 중의 **내부 호출(제안 인터페이스)**이며, 필드 이름은 백엔드 구현에서 확정합니다. 예시: [`examples/01_worker-input.scenarios.json`](examples/01_worker-input.scenarios.json)

| 필드 | 설명 |
| --- | --- |
| `hook_type` | `"B"` 고정 |
| `product_info` | `ProductInput`(`name`, `category`, `verified_facts[]`, 선택 `price_or_offer`, `target_audience`). **`verified_facts`에 없는 사실은 쓰지 않는다** |
| `project_id`, `round`, `count` | 몇 번째 뽑기인지와 만들 개수 |
| `previous_scenarios[]` | 앞선 회차 시나리오. 더 뽑을 때 **같은 소재·구조를 반복하지 않기 위해** 참고 |

콘티와 훅 단계에서는 저장된 `ScenarioItem`(`scenario_id`로 조회)과 `tts` 옵션만 받으면 됩니다.

## 시나리오 생성 시 지켜야 할 유형 규칙

기준 문서: [`skills/shortform-ad-hooks-blueprint/SKILL.md`](../../../skills/shortform-ad-hooks-blueprint/SKILL.md)의 Track B(`B_info_hook_offset`)와 `skills/b-info-hook/SKILL.md`(현재 저장소에는 폴더가 없음. 있으면 함께 참고). 아래는 요약이며 충돌하면 blueprint가 우선입니다.

- **앵커 정하기.** 제품 핵심 기능 + 숫자 하나. 뽀모도로 타이머라면 "남은 시간이 빨간 부채꼴 면적으로 보인다(60분 = 360도)".
- **시작 단어와 앵커의 유사도 `hook_similarity_score` = 0.40~0.60.** 0.7 이상은 시작부터 광고 냄새가 나서 금지, 0.3 미만은 브리지가 억지스러워 금지. 값을 `ad_spec`에 기록한다.
- **시작은 제품과 무관한 놀라운 사실 + 숫자.** 시작 장면에 제품군 어휘(타이머, 시계 등)와 제품명을 쓰지 않는다. PAS형 도입("~하는 이유", "쏟아본 적", "바꿨어요")도 금지.
- **브리지 1~2개.** 인접 단어 유사도는 0.70 이상, 장면이 갈수록 앵커와의 유사도가 올라간다(예: 0.45 → 0.65 → 0.8). 같은 단위의 숫자 실(예: 도(°))이 이어지면 가장 좋다.
- **반전 장면에서 제품명이 처음 등장**하고 실물로 증명한다.
- **나레이션은 "~습니다"체**의 차분한 정보체. 자막은 짧은 구어, 한 줄 8자 안팎, 2줄 이내, 숫자는 아라비아 숫자(나레이션은 한글로 읽히게). 스펙 배너(`header_tag`)는 2개 이하.
- 사실은 출처를 확인할 수 있는 것만 쓴다. 검증 안 된 사실은 `fact_sources[].status`에 표시하고 "~라고 합니다"로 말한다. (이 가이드 예시의 자전 속도 수치는 예시이므로 실제 사용 전 출처 확인이 필요하다.)
- 권장 `ad_spec` 키: `track_archetype: "B_info_hook_offset"`, `hook_similarity_score`, `anchor`, `bridge_path[]`(`word`, `sim_to_anchor`), `adjacent_min_sim`, `number_thread`, `product_first_mention_beat`, `visual_style`(기본 `blender_3d_cutaway`), `fact_sources[]`.

## 반환해야 할 응답 형태

필드 정의는 [`../api-guide.md`](../api-guide.md)와 [`openapi.json`](../../../contracts/openapi.json)이 기준입니다. 이 유형의 예시:

| 단계 | 반환 | 예시 |
| --- | --- | --- |
| 시나리오 | `{ round, scenarios[] }` — 각 `ScenarioItem`: `scenario_id`, `round`, `type: "B"`, `hook_title`, `hook_duration_sec`(≤15), `body_duration_sec`, `replacement_test_note`, `beats[]`(`order`, `role`, `duration_sec`, `visual`, `narration`, `caption`), `ad_spec` | [`examples/02_scenarios.response.json`](examples/02_scenarios.response.json) |
| 콘티 | `{ frames[] }` — `beat_order`(= `beats[].order`), `image_url`, `caption` | [`examples/03_storyboard.response.json`](examples/03_storyboard.response.json) |
| 훅(폴링) | `{ status, files{hook_video, tts_audio, subtitles_srt, scenario_json, storyboard_images[]}, output_dir }` | [`examples/04_hook-status.done.json`](examples/04_hook-status.done.json) |

공통 규칙: 장면 길이 합 = `hook_duration_sec` ≤ 15초, 장면 3~5개, `replacement_test_note`에는 교체 테스트 판정 근거를 한 줄로 씁니다. `ad_spec`에는 아래 "유형 규칙"에서 정한 키를 넣습니다(유형 규칙 검증과 이후 린트에 쓰이는 값).

## 결과 파일 저장 위치와 이름

훅이 `done`이 되면 아래 폴더에 저장합니다(`OUTPUT_DIR` 기본값은 미정, 여기서는 `output/`).

```text
OUTPUT_DIR/{project_id}/{hook_id}/
├── hook.mp4              훅 영상 (15초 이하, 9:16)
├── tts.mp3               나레이션 음성 (beats[].narration)
├── hook.srt              자막 (beats[].caption, 장면 시작·끝 시각 기준)
├── scenario.json         이 훅에 쓴 ScenarioItem 그대로 (b/examples/05_saved-scenario.json 참고)
└── storyboard_01.png …   콘티 이미지 (2자리 번호 = beat_order)
```

회차가 달라지면 `hook_id`가 다른 새 폴더가 생기고 기존 폴더는 지우지 않습니다.

## index.html로 테스트하기

1. `python -m http.server 5500 --directory backend/bridge-dev` 후 `http://127.0.0.1:5500/`를 엽니다(파일로 열어도 됩니다).
2. **훅 유형**에서 **B**를 선택합니다. 제품 정보는 뽀모도로 타이머가 미리 채워져 있습니다.
3. Mock으로 흐름을 먼저 확인합니다: "처음부터 끝까지(1회)" 또는 "시나리오 더 뽑기 n회". 오른쪽 로그에서 요청 body와 응답 형태를 봅니다.
4. 내 코드로 확인: Mock을 끄고 Base URL을 백엔드로, Bearer 토큰에 `python backend/bridge-dev/dev_token.py --user worker-b` 결과를 넣고 같은 버튼을 누릅니다. 응답이 위 예시와 다르면 로그의 curl 복사로 재현합니다. CORS와 인증은 [`../README.md`](../README.md)를 참고하세요.
5. 끝나면 "결과 저장"으로 회차별 결과를 JSON으로 받아 예시와 비교합니다.

## 저장소의 B 캠페인 예시

- `prototypes/campaigns/digimore-timer-abc/05_ad_spec_B.json` (다큐 트위스트), `05_ad_spec_B_subtle.json` (은근한 분위기)
- 같은 폴더의 `audio/vo_plan_B.json`, `final/ad_B_docu_twist.srt`, `final/ad_B_subtle_vibe.srt`
- `prototypes/campaigns/piev-airwasher-abc/01_abc_script.md`, `pva-water-sponge-abc/01_abc_script.md`: 유형을 `b-info-hook`으로 기록한 다른 제품 예(시작 유사도 0.45 → 브리지 0.70 → 제품 반전)
- 참고: 기존 타이머 B안은 시작부터 시간 이야기라 유사도가 높게(약 0.75) 평가된 사례입니다. 이 가이드 예시(지구 자전 → 15도 → 부채꼴 → 제품)가 새 기준에 맞춘 것입니다.
