# 냅다(NAPDA) MVP REST API 명세 v0.2

PRD v0.2([`../README.md`](../README.md)) 기준 **가이드 먼저형** 9단계 흐름과 기존 워커 API를 통합한 공식 API 명세서입니다.  
기계 판독용 OpenAPI 3.1 스키마는 [`openapi.json`](openapi.json)에서 확인할 수 있습니다.

> **v0.2 변경 요약** — A·B·C 훅 작업자 흐름(정보 캐싱 → 시나리오 → 콘티 → 선택 → 훅+TTS → 파일 저장, 시나리오 더 뽑기)을 위해 기존 v0.1을 최소 변경했습니다. 기존 엔드포인트는 모두 유지하고, 아래 §3·§5의 `v0.2` 표시만 추가·확장입니다. 이 흐름을 그대로 호출해 볼 수 있는 더미 화면은 [`../backend/bridge-dev/`](../backend/bridge-dev/README.md)입니다. 백엔드(`backend/`)는 아직 v0.2 경로를 구현하지 않았으며, `openapi.json`의 v0.2 항목은 FastAPI 자동 생성이 아니라 **손으로 추가한 계약**입니다.

---

## 1. 확정 정책 요약 (5대 결정 사항)

| 항목 | 확정 정책 | 코드/환경변수 |
| :--- | :--- | :--- |
| **FR-001 필수 입력** | **필수**: `product.name` + `product.category`(`living` \| `kitchen` \| `stationery`). **옵션**: `verified_facts`(핵심 특징), `price_or_offer`(가격/혜택), `target_audience`(타깃) | `ProductInput` |
| **FR-008 이어하기 인증** | **Google One Tap (+ Google 버튼 fallback)** — `POST /v1/auth/google`로 Google ID Token(JWT)을 `google-auth`로 검증 후 7일 서명 세션(`HttpOnly` 쿠키 `napda_session` + Bearer `access_token`) 발급 | `GOOGLE_CLIENT_ID`, `SESSION_SECRET`, `SESSION_TTL_DAYS=7` |
| **FR-009 업로드 제한** | 단일 파일 & 컷별 다중 파일 모두 허용(`1~20`개), **파일당 최대 100MB**, **총 길이 5~90초**. 가이드와 다른 비율/길이는 비차단 `warnings[]` 반환 | `MAX_UPLOAD_FILE_BYTES=104857600`, `MIN_UPLOAD_TOTAL_SEC=5.0`, `MAX_UPLOAD_TOTAL_SEC=90.0` |
| **FR-006 크레딧/무료 한도** | 결제 제외 무료 베타 — Google 계정(`user_id`)당 **일일 영상 생성 3회 제한** + 실행 전 단계별 예상 크레딧(`/estimate`) 표시 | `DAILY_RENDER_LIMIT=3` |
| **보관 기간(TTL)** | 프로젝트·업로드 원본·결과물 **생성일로부터 7일 보관 후 자동 만료** (`expires_at` 반환) | `RETENTION_TTL_DAYS=7` |
| **제품 정보 캐시 (v0.2)** | `POST /v1/product-info`의 결과를 정규화 해시 기준으로 잠시 캐싱. 만료 후에는 `product_info_id`로 프로젝트를 만들 수 없음(`404 PRODUCT_INFO_NOT_FOUND`) | `PRODUCT_INFO_CACHE_TTL_SEC=3600` |
| **훅 결과 파일 저장 위치 (v0.2)** | 훅 결과는 `OUTPUT_DIR/{project_id}/{hook_id}/` 아래 파일로 저장 | `OUTPUT_DIR` |

---

## 2. 인증 & 공통 에러 포맷

- **인증 헤더 또는 쿠키**:
  - `Authorization: Bearer <access_token>` 또는 브라우저 `napda_session` HttpOnly 쿠키
  - 미인증/타인 소유 프로젝트 접근 시 각각 `401 UNAUTHORIZED`, `404 PROJECT_NOT_FOUND` 반환
- **표준 에러 포맷 (`HTTPException.detail`)**:
  ```json
  {
    "detail": {
      "error": {
        "code": "INVALID_UPLOAD_LIMIT | DAILY_QUOTA_EXCEEDED | INVALID_STATE | PROJECT_NOT_FOUND | UNAUTHORIZED | PRODUCT_INFO_NOT_FOUND | SCENARIO_NOT_FOUND | HOOK_NOT_FOUND",
        "message": "사람이 읽을 수 있는 한국어 안내 문구",
        "details": {}
      }
    }
  }
  ```

---

## 3. 엔드포인트 목록

### 인증 (`Auth`)
| Method & Path | 인증 | 설명 |
| :--- | :---: | :--- |
| `POST /v1/auth/google` | 불필요 | `{ "credential": "<Google ID Token>" }` 검증 → 유저 등록/갱신 + `napda_session` 쿠키 & `access_token` 발급 |
| `POST /v1/auth/logout` | 불필요 | `napda_session` 쿠키 삭제 (`204`) |
| `GET /v1/auth/me` | 필요 | 현재 로그인 유저 정보 및 오늘의 생성 한도(`quota`) 조회 |

### 기획·촬영 가이드·업로드·생성·결과 (`Projects`)
| FR | Method & Path | 설명 |
| :--- | :--- | :--- |
| **FR-002** | `GET /v1/hook-types` | A·B·C 훅 유형 설명 + 교체 테스트 기준 메타 조회 |
| **FR-001** | `POST /v1/product-info` | **신규(v0.2)** 제품 정보 가져오기 + 잠시 캐싱. `{ product, source_url? }` → `{ product_info_id, product, cached, cached_at, expires_at }`. 같은 입력(정규화 해시)이면 캐시 적중(`cached=true`) |
| **FR-001** | `POST /v1/projects` | **확장(v0.2)** `product` 대신 `product_info_id`도 허용(둘 중 하나). 선택한 유형(`1~3`개, ABC 작업자는 자기 유형 1개) + `flow_mode`(`guide_first` \| `skip_drafts`)로 프로젝트 생성 (`201`) |
| **FR-008** | `GET /v1/projects` | 내 프로젝트 목록 최신순 조회 (촬영 후 다른 기기에서도 이어하기) |
| **FR-008** | `GET /v1/projects/{project_id}` | 프로젝트 상세 + 시나리오 + 촬영 가이드 + 업로드 상태 + 최신 잡 + `expires_at` 조회 |
| **FR-003** | `POST /v1/projects/{project_id}/scenarios` | **확장(v0.2)** 선택한 유형별 글 시나리오 생성(`planner-api` 연동). 요청 `count`(기본 1). **다시 호출하면 기존 시나리오를 지우지 않고 추가(append)**, 응답에 `round`(몇 번째 뽑기) 포함 → '시나리오 더 뽑기' |
| **FR-004** | `POST /v1/projects/{project_id}/scenarios/{scenario_id}/storyboard` | 선택형 이미지 콘티('그림으로 보기') 생성 |
| — | `POST /v1/projects/{project_id}/scenarios/{scenario_id}/select` | **신규(v0.2)** 시나리오 선택 → `{ selected_scenario_id }`. FR-007 촬영 가이드의 선택과 별개 |
| **FR-007** | `POST /v1/projects/{project_id}/filming-guide` | 최종 1개 시나리오 선택 → 장면별 촬영 가이드(`shots[]`) 생성 |
| **FR-006** | `POST /v1/projects/{project_id}/estimate` | 실행 전 단계별 예상 크레딧 및 오늘 남은 무료 생성 횟수 조회 |
| **FR-009** | `POST /v1/uploads/presign` | S3/R2 Presigned PUT URL 발급 |
| **FR-009** | `POST /v1/projects/{project_id}/uploads/complete` | 업로드 완료 검증 (100MB/파일, 5~90초 총합, `16:9` 등 비율 차이 시 비차단 `warnings` 반환) |
| **FR-005** | `POST /v1/projects/{project_id}/hooks` | **신규(v0.2)** 훅 + TTS 생성 접수. `{ scenario_id, tts: { enabled, voice? } }` → `202 { hook_id, job_id, status }` |
| **FR-005** | `GET /v1/projects/{project_id}/hooks/{hook_id}` | **신규(v0.2)** 훅 상태 폴링. `{ status: queued\|running\|done\|failed, files: { hook_video, tts_audio, subtitles_srt, scenario_json, storyboard_images[] }, output_dir }` |
| — | `GET /v1/projects/{project_id}/outputs` | **신규(v0.2)** 프로젝트에 저장된 결과 파일 목록 |
| **FR-010 후속 (·011)** | `POST /v1/projects/{project_id}/renders` | 훅 합치기(훅 + TTS + 본편 연결) 잡 접수 — **이번 v0.2 흐름 밖, 기존 동작 유지** (`202`, 한도 초과 시 `429`, `skip_drafts=true` 시 시나리오 생략 가능) |
| **FR-012·013·014** | `GET /v1/projects/{project_id}/deliverables` | 결과 영상 스트리밍/다운로드 URL, 썸네일 URL, AI 라벨 안내(`AI 연출 포함`), `expires_at` 반환 |
| **FR-009 (별도)** | (미정) | **별도 트랙·미구현** 원본영상 만들기(편집) + TTS. 파이프라인이 없어 v0.2에서 경로를 정의하지 않음 |

### 내부 워커 API (`Jobs`, 기존 유지)
- `GET /health`, `POST /v1/jobs`, `GET /v1/jobs`, `GET /v1/jobs/{job_id}`, `POST /v1/jobs/{job_id}/retry-unit/{unit_id}`

---

## 4. 프로젝트 상태 전이

```text
PRODUCT_SAVED
  ├──▶ SCENARIOS_READY ──▶ (선택: STORYBOARD_READY) ──▶ GUIDE_READY ──▶ UPLOADS_READY
  └──(skip_drafts)────────────────────────────────────────────────────────▶ UPLOADS_READY
                                                                                │
                                                                                ▼
                                                   RENDERING ──▶ DELIVERABLE_READY / FAILED
```

**v0.2 추가 — ABC 훅 작업자 흐름 상태:**

```text
PRODUCT_SAVED ──▶ SCENARIOS_READY ──▶ STORYBOARD_READY ──▶ (select) ──▶ HOOK_RENDERING ──▶ HOOK_READY / FAILED
                        ▲                                                                        │
                        └──── 시나리오 더 뽑기: POST /scenarios 재호출(append, round+1) ◀────────┘
```

- `POST /scenarios`는 `HOOK_READY`에서도 다시 호출할 수 있으며, 호출되면 상태가 `SCENARIOS_READY`로 돌아가고 기존 시나리오·훅 결과는 보존됩니다.
- `POST /hooks`는 `select`된 시나리오에만 허용됩니다(아니면 `409 INVALID_STATE`).
- 훅 상태(`queued|running|done|failed`)는 훅마다 따로 갖고, 프로젝트 상태는 `HOOK_RENDERING → HOOK_READY`를 따릅니다.

---

## 5. ABC 훅 작업자 흐름 (v0.2)

A·B·C 훅 작업자가 각자 자기 유형 1개로 백엔드를 호출해 보는 개발 흐름입니다. 호출해 볼 수 있는 단일 HTML은 [`../backend/bridge-dev/index.html`](../backend/bridge-dev/index.html)이며, **이 HTML이 보내는 요청이 백엔드 구현 기준**입니다.

```text
FR-001 POST /v1/product-info            정보 가져오기 + 잠시 캐싱
  → POST /v1/projects                   product_info_id + selected_types:[내 유형]
  → FR-003 POST …/scenarios             시나리오 생성 (지금은 count=1)
  → FR-004 POST …/scenarios/{sid}/storyboard   이미지 콘티
  → POST …/scenarios/{sid}/select       만들어진 시나리오 선택 (지금은 1개라 그것)
  → FR-005 POST …/hooks → GET …/hooks/{hook_id} (폴링)   훅 + TTS
  → 결과 파일 저장: OUTPUT_DIR/{project_id}/{hook_id}/   ← 이번 흐름의 끝
  + 시나리오 더 뽑기: 위 사이클(시나리오→콘티→선택→훅)을 n회 반복 (n은 사용자가 선택)
```

- n회 반복은 **클라이언트가 위 엔드포인트를 반복 호출**해 처리합니다. 서버에 사이클 전용 엔드포인트는 없습니다.
- FR-009(원본영상 만들기 + TTS)는 별도 트랙이며 미구현, FR-010(훅 합치기)은 이번 흐름 밖(후속)입니다. 기존 `POST /v1/projects/{id}/renders`는 그대로 둡니다.
- 기본 더미 데이터는 뽀모도로 타이머(`prototypes/campaigns/digimore-timer-abc/00_product_facts.md`의 검증된 사실만, 카테고리 `stationery`)입니다.

### 5.1 요청·응답 예시

**`POST /v1/product-info`** (`200`)

```json
// 요청
{ "product": { "name": "60분 비주얼 아날로그 타이머", "category": "stationery",
               "verified_facts": ["다이얼을 돌리면 빨간 부채꼴 원판이 채워진다"] },
  "source_url": null }
// 응답
{ "product_info_id": "pinfo_ab12", "product": { "...": "요청과 동일" },
  "cached": false, "cached_at": "2026-11-25T10:00:00+00:00", "expires_at": "2026-11-25T11:00:00+00:00" }
```

**`POST /v1/projects`** (`201`) — `product` 또는 `product_info_id` 중 하나

```json
{ "product_info_id": "pinfo_ab12", "selected_types": ["B"], "flow_mode": "guide_first" }
```

**`POST /v1/projects/{id}/scenarios`** (`200`) — 다시 호출하면 append

```json
// 요청
{ "types": ["B"], "count": 1 }
// 응답 (scenarios 는 누적 전체, round 는 이번 회차)
{ "project_id": "proj_1", "status": "SCENARIOS_READY", "round": 2,
  "scenarios": [ { "scenario_id": "sc_1", "round": 1, "type": "B", "...": "ScenarioItem" },
                 { "scenario_id": "sc_2", "round": 2, "type": "B", "...": "ScenarioItem" } ] }
```

**`POST /v1/projects/{id}/scenarios/{sid}/select`** (`200`, 요청 body 없음)

```json
{ "project_id": "proj_1", "selected_scenario_id": "sc_2" }
```

**`POST /v1/projects/{id}/hooks`** (`202`)

```json
// 요청
{ "scenario_id": "sc_2", "tts": { "enabled": true, "voice": "ko-KR-SunHiNeural" } }
// 응답
{ "hook_id": "hook_1", "job_id": "job_1", "status": "queued" }
```

**`GET /v1/projects/{id}/hooks/{hook_id}`** (`200`) — `done`이면 파일이 저장된 상태

```json
{ "hook_id": "hook_1", "status": "done", "output_dir": "output/proj_1/hook_1",
  "files": { "hook_video": "output/proj_1/hook_1/hook.mp4", "tts_audio": "output/proj_1/hook_1/tts.mp3",
             "subtitles_srt": "output/proj_1/hook_1/hook.srt", "scenario_json": "output/proj_1/hook_1/scenario.json",
             "storyboard_images": ["output/proj_1/hook_1/storyboard_01.png"] } }
```

**`GET /v1/projects/{id}/outputs`** (`200`)

```json
{ "project_id": "proj_1", "outputs": [ { "hook_id": "hook_1", "output_dir": "output/proj_1/hook_1", "files": { "...": "HookFiles" } } ] }
```

### 5.2 구현 시 확정할 사항 (백엔드 담당)

- `product`와 `product_info_id`가 함께 오면 어느 쪽을 우선할지(권장: `product_info_id`).
- 훅 결과 파일 제공 방식: `output_dir`는 서버 로컬 경로 표기입니다. 브라우저 내려받기가 필요하면 `files.*`를 URL로 바꾸거나 별도 다운로드 경로를 추가해야 합니다.
- `OUTPUT_DIR`의 기본값과 §1의 7일 보관 정책 적용 여부.
- 인증: 프로젝트 API는 세션 토큰(`Authorization: Bearer`)이 필요합니다. 개발용 토큰 발급은 [`../backend/bridge-dev/README.md`](../backend/bridge-dev/README.md)를 참고하세요.
