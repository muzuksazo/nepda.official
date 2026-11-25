# API 사용 가이드 (공통 · v0.2)

A·B·C 작업자가 공통으로 따르는 API 사용법입니다. 스키마의 기준은 [`../../contracts/openapi.json`](../../contracts/openapi.json), 정책은 [`../../contracts/api-spec.md`](../../contracts/api-spec.md)이며, 이 문서는 필드 설명과 규칙을 풀어 쓴 것입니다. 예시는 모두 [`examples/`](examples/)(뽀모도로 타이머)에 있습니다. v0.2 경로는 아직 백엔드에 구현되지 않았고, 이 폴더의 [`index.html`](index.html)이 보내는 요청이 구현 기준입니다.

## 1. 공통

- Base URL 기본값: `http://127.0.0.1:8080`
- 인증: `Authorization: Bearer <세션 토큰>`. 개발 토큰은 `python backend/bridge-dev/dev_token.py` ([README](README.md#인증))
- 본문은 `application/json`, 시간은 ISO 8601 문자열
- 에러 형식(기존 v0.1과 같음):

  ```json
  { "detail": { "error": { "code": "INVALID_STATE", "message": "한국어 안내", "details": {} } } }
  ```

  | 코드 | HTTP | 언제 |
  | --- | --- | --- |
  | `UNAUTHORIZED` | 401 | 토큰이 없거나 틀림 |
  | `PROJECT_NOT_FOUND` | 404 | 없는 프로젝트이거나 남의 프로젝트 |
  | `PRODUCT_INFO_NOT_FOUND` | 404 | `product_info_id`가 없거나 캐시 만료 ([예시](examples/07_error.product-info-expired.json)) |
  | `SCENARIO_NOT_FOUND` | 404 | 이 프로젝트에 없는 `scenario_id` |
  | `HOOK_NOT_FOUND` | 404 | 이 프로젝트에 없는 `hook_id` |
  | `INVALID_STATE` | 409 | 선택하지 않은 시나리오로 훅을 만들려는 경우 등 ([예시](examples/07_error.invalid-state.json)) |
  | `VALIDATION_ERROR`(FastAPI 422) | 422 | 필드 누락·형식 오류 |

## 2. 호출 순서

```text
POST /v1/product-info                           ① 정보 가져오기(+캐싱)
POST /v1/projects                               ② 프로젝트 (selected_types 에 내 유형 1개)
POST /v1/projects/{id}/scenarios                ③ 시나리오 (다시 부르면 append, round+1)
POST /v1/projects/{id}/scenarios/{sid}/storyboard   ④ 이미지 콘티
POST /v1/projects/{id}/scenarios/{sid}/select       ⑤ 선택
POST /v1/projects/{id}/hooks                    ⑥ 훅+TTS 접수 (202)
GET  /v1/projects/{id}/hooks/{hook_id}          ⑦ 폴링 → done → 파일 저장 완료
GET  /v1/projects/{id}/outputs                  ⑧ 저장된 결과 목록
```

"시나리오 더 뽑기 n회"는 ③→④→⑤→⑥→⑦을 클라이언트가 n번 반복하는 것입니다. 서버에 반복 전용 API는 없습니다.

## 3. 엔드포인트별 필드

### ① `POST /v1/product-info` → 200

| 구분 | 필드 | 타입 | 설명 |
| --- | --- | --- | --- |
| 요청 | `product.name` | string(1~120) | **필수** |
| 요청 | `product.category` | `living`\|`kitchen`\|`stationery` | **필수** |
| 요청 | `product.verified_facts` | string[](≤20) | 검증된 핵심 특징. **작업자는 여기 있는 사실만 광고 문구에 쓴다** |
| 요청 | `product.price_or_offer`, `product.target_audience` | string?(≤120) | 선택 |
| 요청 | `source_url` | string? | 상세 페이지 URL(선택) |
| 응답 | `product_info_id` | string | 이후 프로젝트 생성에 사용 |
| 응답 | `product` | ProductInput | 정규화되어 저장된 값 |
| 응답 | `cached` | bool | 같은 입력(정규화 해시)이면 `true` |
| 응답 | `cached_at`, `expires_at` | ISO 8601 | 만료는 `PRODUCT_INFO_CACHE_TTL_SEC`(기본 3600초) 뒤 |

예시: [요청](examples/01_product-info.request.json) · [응답](examples/01_product-info.response.json) · [캐시 적중](examples/01_product-info.response.cached.json)

### ② `POST /v1/projects` → 201

| 필드 | 설명 |
| --- | --- |
| `product_info_id` 또는 `product` | 둘 중 하나는 필수. 둘 다 오면 `product_info_id` 우선(권장, 구현 시 확정) |
| `selected_types` | `["A"]`처럼 **자기 유형 1개**만 보냄(스키마상 1~3개 허용) |
| `flow_mode` | 기본 `guide_first`. 이 흐름에서는 그대로 둠 |

응답은 `ProjectSummary`(`project_id`, `status: PRODUCT_SAVED`, `selected_scenario_id: null`, `expires_at` …). 예시: [요청](examples/02_create-project.request.json) · [응답](examples/02_create-project.response.json)

### ③ `POST /v1/projects/{id}/scenarios` → 200

| 구분 | 필드 | 설명 |
| --- | --- | --- |
| 요청 | `types` | 생략하면 프로젝트의 `selected_types`. ABC 작업자는 `["B"]`처럼 1개 |
| 요청 | `count` | 1~5, 기본 1 |
| 요청 | `provider` | `anthropic`\|`google`(기존 필드, 기본 `anthropic`) |
| 응답 | `round` | 이 프로젝트에서 몇 번째 뽑기인지(1부터). 호출할 때마다 +1 |
| 응답 | `scenarios[]` | **누적 전체 목록**. 기존 것은 지워지지 않음. 새로 만든 항목은 `round`가 응답 `round`와 같음 |
| 응답 | `status` | `SCENARIOS_READY` |

`ScenarioItem` 필드:

| 필드 | 설명 |
| --- | --- |
| `scenario_id` | 프로젝트 안에서 유일 |
| `round` | 만들어진 회차 |
| `type` | `A`\|`B`\|`C` |
| `hook_title` | 훅 제목(사람이 읽는 용) |
| `hook_duration_sec`, `body_duration_sec` | 훅 길이(15초 이하)와 본편 길이 |
| `replacement_test_note` | 교체 테스트 판정 근거 한 줄 |
| `beats[]` | 장면 목록. `order`, `role`, `duration_sec`, `visual`, `narration`(나레이션), `caption`(자막) |
| `ad_spec` | 유형별 부가 정보(자유 객체). 유형별 권장 키는 `a/`, `b/`, `c/` README 참고 |

장면 길이의 합은 `hook_duration_sec`과 같아야 합니다. `narration`은 TTS가 읽을 문장, `caption`은 화면 자막(줄바꿈 `\n`, 2줄 이내)입니다. 예시는 유형별 폴더: [A](a/examples/02_scenarios.response.json) · [B](b/examples/02_scenarios.response.json) · [C](c/examples/02_scenarios.response.json)

### ④ `POST /v1/projects/{id}/scenarios/{sid}/storyboard` → 200

요청 `{ "visual_style": "default" }`(선택). 응답 `frames[]`: `beat_order`(장면 번호와 1:1), `image_url`, `caption`. 상태는 `STORYBOARD_READY`. `image_url`을 URL로 줄지 서버 경로로 줄지는 미정입니다([PRD](PRD.md#미정-항목)). 예시: [A](a/examples/03_storyboard.response.json) · [B](b/examples/03_storyboard.response.json) · [C](c/examples/03_storyboard.response.json)

### ⑤ `POST /v1/projects/{id}/scenarios/{sid}/select` → 200

요청 body 없음. 응답 `{ project_id, selected_scenario_id }`. 프로젝트의 `selected_scenario_id`가 갱신됩니다. 한 프로젝트에서 여러 회차를 돌리면 가장 최근에 선택한 시나리오가 현재 선택입니다. FR-007 촬영 가이드의 최종 선택과는 별개입니다. [예시](examples/05_select.response.json)

### ⑥ `POST /v1/projects/{id}/hooks` → 202

| 필드 | 설명 |
| --- | --- |
| `scenario_id` | **선택(select)된** 시나리오만 허용. 아니면 `409 INVALID_STATE` |
| `tts.enabled` | 기본 `true` |
| `tts.voice` | 선택. 비우면 서버 기본 목소리(공급자·기본값은 [미정](PRD.md#미정-항목)) |

응답 `{ hook_id, job_id, status: "queued" }`. 프로젝트 상태는 `HOOK_RENDERING`이 됩니다. 예시: [요청](examples/06_hooks.request.json) · [응답](examples/06_hooks.response.json)

### ⑦ `GET /v1/projects/{id}/hooks/{hook_id}` → 200 (폴링)

| 필드 | 설명 |
| --- | --- |
| `status` | `queued` → `running` → `done` 또는 `failed` |
| `files` | `done`일 때 채워짐. `hook_video`, `tts_audio`, `subtitles_srt`, `scenario_json`, `storyboard_images[]`. 진행 중에는 비어 있거나 `storyboard_images: []`만 있을 수 있음 |
| `output_dir` | 저장 폴더(서버 기준 경로) |
| `error` | `failed`일 때 사람이 읽을 사유 |

폴링 규칙: 2초 간격(이 화면 기준), 최대 약 4분. `done`이 되면 프로젝트 상태는 `HOOK_READY`, `failed`면 `FAILED`가 아니라 **훅만 실패**로 두고 프로젝트는 `STORYBOARD_READY`로 되돌립니다(권장, 구현 시 확정). 예시: [running](examples/06_hook-status.running.json) · [failed](examples/06_hook-status.failed.json) · done은 유형별 폴더([A](a/examples/04_hook-status.done.json) · [B](b/examples/04_hook-status.done.json) · [C](c/examples/04_hook-status.done.json))

### ⑧ `GET /v1/projects/{id}/outputs` → 200

`{ project_id, outputs: [{ hook_id, scenario_id, output_dir, files, created_at }] }`. 이 화면은 호출하지 않고 명세만 정의합니다.

## 4. 상태 전이

```text
PRODUCT_SAVED ─(scenarios)→ SCENARIOS_READY ─(storyboard)→ STORYBOARD_READY ─(select, hooks)→ HOOK_RENDERING ─→ HOOK_READY
       ▲                         ▲                                                                    │
       └──── 더 뽑기: scenarios 를 다시 호출하면 SCENARIOS_READY 로 ◀───────────────────────────────────┘
```

기존 v0.1 상태(`GUIDE_READY`, `UPLOADS_READY`, `RENDERING`, `DELIVERABLE_READY`, `FAILED`)는 그대로입니다(FR-010 후속).

## 5. 결과 파일 저장 규칙

훅이 `done`이 되면 백엔드는 아래 폴더에 파일을 저장합니다. `OUTPUT_DIR` 기본값은 [미정](PRD.md#미정-항목)이고, 이 문서에서는 `output/`으로 적습니다.

```text
OUTPUT_DIR/{project_id}/{hook_id}/
├── hook.mp4              훅 영상(15초 이하, 9:16)
├── tts.mp3               나레이션 음성
├── hook.srt              자막(장면 caption 기준)
├── scenario.json         이 훅에 쓴 ScenarioItem 그대로
└── storyboard_01.png …   콘티 이미지(2자리 번호, beat_order와 같음)
```

- `files.*` 값은 이 파일들의 경로입니다. 같은 프로젝트에서 더 뽑으면 `hook_id`가 다른 새 폴더가 생기고 기존 폴더는 지우지 않습니다.
- 7일 보관 정책(`RETENTION_TTL_DAYS`)과 같이 갈지는 [미정](PRD.md#미정-항목)입니다.
- 이 화면의 "결과 저장"은 이와 별개로, 화면이 받은 응답을 JSON 한 파일로 내려받는 기능입니다.

## 6. 작업자가 지킬 공통 규칙

1. 제품 사실은 `product.verified_facts`에 있는 것만 씁니다. 근거 없는 스펙·가격·할인·"무소음" 같은 주장은 쓰지 않습니다(뽀모도로 타이머의 금지 항목은 `prototypes/campaigns/digimore-timer-abc/00_product_facts.md`의 Unverified).
2. 훅 길이는 15초 이하, 장면은 3~5개입니다.
3. 나레이션과 자막은 분리해서 씁니다. 자막은 짧은 구어, 나레이션은 유형별 규칙(B는 "~습니다")을 따릅니다.
4. 응답은 openapi.json 스키마와 일치해야 합니다. 모르는 필드는 `ad_spec`에 넣고 상위 필드를 늘리지 않습니다.
5. 광고 표시: AI 연출이 들어간 결과는 `ad_spec.disclosure: "ai_assisted"`(또는 동등한 표시)를 남깁니다.
