# bridge-dev — ABC 훅 작업자용 API 더미 화면과 가이드 (v0.2)

A·B·C 훅 작업자가 백엔드에 요청을 보내 보는 **단일 HTML**(`index.html`, 빌드·외부 CDN 없음)과, 각 유형 작업자가 API를 어떻게 받아 쓰고 무엇을 반환해야 하는지 적은 가이드 모음입니다. 백엔드 개발자는 이 화면이 보내는 요청(로그 패널·curl 복사)을 기준으로 API를 구현합니다. 계약은 [`../../contracts/api-spec.md`](../../contracts/api-spec.md) v0.2와 [`../../contracts/openapi.json`](../../contracts/openapi.json)입니다.

> 개발용 도구입니다. 제품 프론트엔드는 [`../../frontend/`](../../frontend/README.md)에서 개발합니다.

## 폴더 안내

```text
backend/bridge-dev/
├── README.md        이 문서: 목적, 실행, CORS·인증, 흐름도
├── PRD.md           ABC 훅 작업자 흐름 PRD (v0.2 개발 범위, 수용 기준, 미정 항목)
├── index.html       요청을 보내 보는 더미 화면 (Mock 모드 지원)
├── api-guide.md     공통: 엔드포인트별 요청/응답 필드, 상태 전이, 에러 포맷, 폴링, 파일 저장 규칙
├── dev_token.py     개발용 세션 토큰 발급
├── examples/        공통 예시 JSON (뽀모도로 타이머): product-info, 프로젝트, 선택, 훅, 에러
├── a/  README.md + examples/   A 훅 작업자 가이드 (제품과 무관한 훅)
├── b/  README.md + examples/   B 훅 작업자 가이드 (정보성 훅, 맥락 오차율 약 50%)
└── c/  README.md + examples/   C 훅 작업자 가이드 (제품 직결 훅)
```

| 읽는 사람 | 먼저 볼 것 |
| --- | --- |
| A·B·C 작업자 | 자기 유형 폴더 README → [`api-guide.md`](api-guide.md) → `index.html`로 확인 |
| 백엔드 개발자 | [`PRD.md`](PRD.md)의 수용 기준 → [`api-guide.md`](api-guide.md) → `index.html` 로그 |

## 흐름

```text
FR-001 POST /v1/product-info          ① 정보 가져오기 + 잠시 캐싱
  → POST /v1/projects                 ② 프로젝트 만들기 (product_info_id, selected_types:[내 유형 1개])
  → FR-003 POST …/scenarios           ② 시나리오 생성 (지금은 count=1)
  → FR-004 POST …/{sid}/storyboard    ③ 이미지 콘티
  → POST …/{sid}/select               ④ 시나리오 선택 (지금은 1개라 그것)
  → FR-005 POST …/hooks + GET …/hooks/{hook_id} 폴링   ⑤ 훅 + TTS
  → OUTPUT_DIR/{project_id}/{hook_id}/ 에 파일 저장    ← 여기까지가 이번 흐름
  + 시나리오 더 뽑기: ②(시나리오)→③→④→⑤ 를 n회 반복 (n = 1~10, 화면의 입력칸)
```

- 더 뽑기는 서버 전용 API가 아니라 **이 화면이 같은 엔드포인트를 반복 호출**합니다. `POST …/scenarios`를 다시 부르면 기존 시나리오가 지워지지 않고 추가(append)되며 응답의 `round`가 늘어납니다.
- FR-009 원본영상 만들기(편집)+TTS는 별도 트랙·미구현, FR-010 훅 합치기는 이번 흐름 밖(후속)이라 화면에서 비활성 카드로만 표시합니다.
- 기본 더미 데이터는 **뽀모도로 타이머**입니다. `prototypes/campaigns/digimore-timer-abc/00_product_facts.md`의 Verified/Whitelisted 사실만 쓰고 카테고리는 `stationery`입니다.

## 실행 방법

저장소 루트에서:

1. 파일로 열기: `backend/bridge-dev/index.html`을 브라우저로 엽니다. Mock 모드만 쓸 거면 이것으로 충분합니다. 실제 백엔드 호출은 아래 CORS 때문에 2번을 권장합니다.
2. 로컬 서버로 열기:
   ```bash
   python -m http.server 5500 --directory backend/bridge-dev
   # → http://127.0.0.1:5500/
   ```

화면 구성: 상단 설정(Base URL 기본 `http://127.0.0.1:8080`, Bearer 토큰, **Mock 모드** 토글, TTS voice) → A/B/C 선택 → 제품 정보 폼 → 단계 버튼 ①~⑤ + "시나리오 더 뽑기 n회" → 결과 → 요청/응답 로그. 로그에는 method, URL, 요청 body, 상태 코드, 응답 JSON, 걸린 시간이 있고 요청마다 **curl 복사** 버튼이 있습니다(토큰은 `$NAPDA_TOKEN` 변수로 치환). **결과 저장**은 제품 정보와 회차별 시나리오·콘티·선택·훅 결과를 JSON 파일로 내려받습니다.

### Mock 모드

기본값은 켜짐입니다. 백엔드 없이 명세 형태의 가짜 응답으로 끝까지 진행합니다(같은 입력의 `product-info` 재호출은 `cached: true`, 훅은 `queued → running → done`). Mock을 끄면 실제 `fetch`를 보내며, 404/405/501/401/네트워크 오류는 로그 항목 위에 빨간 안내로 표시됩니다.

## 인증

프로젝트 API(`/v1/projects/*`)는 **세션 토큰**을 요구합니다(`backend/app/projects_router.py`의 `require_user`). 정식 경로는 Google One Tap 로그인(`POST /v1/auth/google`)이지만, 개발 중에는 `backend/app/auth.py`와 같은 HMAC-SHA256 형식으로 직접 발급합니다.

```bash
python backend/bridge-dev/dev_token.py                              # 서버 기본 SESSION_SECRET(dev-insecure-change-me)용
SESSION_SECRET=<backend/.env 값> python backend/bridge-dev/dev_token.py   # .env에서 secret을 바꿨다면
python backend/bridge-dev/dev_token.py --user worker-b              # 작업자별로 uid를 나눠 프로젝트를 분리
```

출력된 문자열을 화면의 **Bearer 토큰** 칸에 붙여 넣습니다. 서버의 `SESSION_SECRET`과 토큰을 만들 때 쓴 값이 같아야 하고 유효기간은 기본 7일입니다. (`backend/app/auth.py`의 `verify_session_token`으로 검증되는 것을 확인했습니다.)

참고: 워커 API(`/v1/jobs*`, `/v1/uploads/presign`)는 별개로 `API_BEARER_TOKEN`(`backend/.env`, 비어 있으면 인증 없음)을 씁니다. 이 화면은 프로젝트 API만 호출하므로 세션 토큰을 씁니다. 훅 API(v0.2)의 인증 방식은 백엔드 구현에서 정하되, 프로젝트 소유자를 구분해야 하므로 세션 토큰을 권장합니다.

## CORS 주의

현재 `backend/app/server.py`에는 **CORS 미들웨어가 없습니다**(`CORSMiddleware`/`allow_origins` 설정 없음). 브라우저에서 다른 origin의 백엔드를 `fetch`하면 서버가 응답해도 브라우저가 막고, 이 화면에는 "네트워크 오류 — CORS 차단일 수 있습니다"로 표시됩니다. 실제 백엔드를 호출하려면 백엔드 담당이 개발 환경에 한해 아래 origin을 허용해야 합니다(`Authorization` 헤더와 `Content-Type: application/json`을 쓰므로 preflight `OPTIONS`도 통과해야 함).

| 여는 방식 | 허용할 origin |
| --- | --- |
| `python -m http.server 5500` | `http://127.0.0.1:5500`, `http://localhost:5500` |
| `index.html`을 파일로 열기 | `null` (`file://`의 origin. 개발 중에만 허용하거나 위 방식을 쓰세요) |

허용 헤더 `Authorization`, `Content-Type`, 허용 메서드 `GET`, `POST`, `OPTIONS`. 쿠키 인증은 쓰지 않으므로 `allow_credentials`는 필요 없습니다. CORS 없이 확인하려면 Mock 모드를 쓰거나 로그의 curl로 요청을 재현하세요.

## 엔드포인트 (이 화면이 호출하는 것)

| 단계 | FR | Method & Path | 변경 | 요청 → 응답 요약 |
| --- | --- | --- | --- | --- |
| ① | FR-001 | `POST /v1/product-info` | 신규 | `{ product, source_url? }` → `{ product_info_id, product, cached, cached_at, expires_at }` |
| ② | FR-001 | `POST /v1/projects` | 확장 | `{ product_info_id, selected_types:["B"], flow_mode }` (`product`도 허용) → `201 ProjectSummary` |
| ② | FR-003 | `POST /v1/projects/{id}/scenarios` | 확장 | `{ types, count }` → `{ round, scenarios[] }` (append) |
| ③ | FR-004 | `POST /v1/projects/{id}/scenarios/{sid}/storyboard` | 유지 | `{ visual_style }` → `{ frames[] }` |
| ④ | — | `POST /v1/projects/{id}/scenarios/{sid}/select` | 신규 | (body 없음) → `{ selected_scenario_id }` |
| ⑤ | FR-005 | `POST /v1/projects/{id}/hooks` | 신규 | `{ scenario_id, tts:{enabled, voice?} }` → `202 { hook_id, job_id, status }` |
| ⑤ | FR-005 | `GET /v1/projects/{id}/hooks/{hook_id}` | 신규 | → `{ status, files{…}, output_dir }` (폴링, Mock 0.2초 / 실제 2초 간격) |
| — | — | `GET /v1/projects/{id}/outputs` | 신규 | 저장된 결과 파일 목록. 화면에서는 호출하지 않고 명세만 정의 |
| 별도 | FR-009 | (미정) | 별도·미구현 | 원본영상 편집 + TTS |
| 후속 | FR-010 | 기존 `POST /v1/projects/{id}/renders` | 유지 | 훅 합치기 |

필드 설명과 예시는 [`api-guide.md`](api-guide.md), 상태 전이는 [`api-spec.md` §4·§5](../../contracts/api-spec.md)를 보세요.

## 백엔드 구현 메모

- 화면은 `scenarios` 응답에서 `round`가 이번 `response.round`와 같은 항목(없으면 마지막 항목)을 이번 회차 시나리오로 씁니다. 그래서 `ScenarioItem.round`와 응답 `round`를 모두 채워 주세요.
- `POST …/hooks`는 `select`된 시나리오가 아니면 `409 INVALID_STATE`를 기대합니다(Mock 동작 기준).
- 오류 본문은 기존 형식 `{ "detail": { "error": { "code", "message", "details" } } }`를 따릅니다.
- 유형별 작업자 코드로 넘기는 입력(`hook_type`, `product_info` 등)은 제안 인터페이스입니다. 각 유형 README와 `*/examples/01_worker-input.scenarios.json`을 참고해 확정하세요.
