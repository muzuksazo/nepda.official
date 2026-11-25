# PRD: ABC 훅 작업자 개발 흐름 (v0.2 개발 범위)

> 원본 제품 요구사항(PRD)은 Notion에 있습니다: [PRD v0.1 NAPDA](https://climbing-domain-5ca.notion.site/PRD-v0-1-NAPDA-4237f7364375801ebd14d6f65ccd8aa1). 이 문서는 그 PRD의 **훅 기획·생성 구간을 A·B·C 작업자가 병렬로 개발하기 위한 개발 범위**를 정리한 것이며, 루트 [`README.md`](../../README.md)의 PRD v0.2 요약(가이드 먼저형 9단계, A·B·C 교체 테스트)과 충돌하지 않게 썼습니다. 충돌이 보이면 Notion 원본과 README가 우선입니다. 아래 "Notion 반영 요약"은 원본에 옮길 변경 후보입니다.

## 배경

냅다는 제품 정보로 광고의 첫 장면인 **훅**을 기획하고 촬영한 본편과 연결해 30초 안팎의 릴스를 만드는 서비스입니다. 훅 유형은 A·B·C이며 교체 테스트(훅을 다른 제품 광고에 옮겨 붙일 수 있는가)로 구분합니다.

| 유형 | 제품과의 관계 | 교체 테스트 |
| --- | --- | --- |
| A | 제품과 무관한 훅 | 훅을 그대로 다른 제품 광고에 연결할 수 있음 |
| B | 제품을 약하게 짐작할 수 있는 훅 | 제품으로 넘어가는 장면을 수정하면 다른 제품 광고에 연결할 수 있음 |
| C | 특정 제품과 직접 연결된 훅 | 다른 제품 광고에 옮겨 붙이기 어려움 |

유형별로 훅 기획 방식이 크게 다르므로, 세 작업자가 같은 API 계약 위에서 각자의 유형을 만들고 백엔드 개발자가 그 계약을 구현합니다. 훅 합치기·본편 편집은 이번 범위에서 다루지 않습니다.

## 범위

**이번 범위 (v0.2)**

```text
FR-001 정보 가져오기 + 잠시 캐싱
  → FR-003 정보 기반 시나리오 생성 (지금은 1개)
  → FR-004 이미지 콘티 생성
  → 만들어진 시나리오 선택 (지금은 1개라 그것을 선택)
  → FR-005 훅 만들기 + TTS
  → 결과를 파일로 저장 (여기까지가 이번 흐름)
  + 시나리오 더 뽑기: 위 사이클(시나리오→콘티→선택→훅)을 n회 반복 (n은 사용자가 선택)
```

**범위 밖**

| 항목 | 상태 | 비고 |
| --- | --- | --- |
| FR-009 원본영상 만들기(편집) + TTS | **별도 트랙·미구현** | 파이프라인이 없음. 명세에서는 "별도·미구현"으로만 표시하고 더미 화면에서는 비활성 카드로 둠 |
| FR-010 훅 합치기 | **후속** | 기존 `POST /v1/projects/{id}/renders`는 그대로 유지 |
| A·B·C 세 편을 모두 영상으로 생성 | 제외 | README의 PRD 요약과 동일 |
| 결제·자동 게시·앱 | 제외 | README의 제외 항목과 동일 |

## 사용자(작업자)와 역할 분담

| 역할 | 맡는 일 | 문서 |
| --- | --- | --- |
| A 훅 작업자 | 제품과 무관한 훅(무맥락 반전) 시나리오·콘티·훅 생성 규칙 구현 | [`a/README.md`](a/README.md) |
| B 훅 작업자 | 제품을 약하게 짐작하는 정보성 훅(맥락 오차율 약 50%) 구현 | [`b/README.md`](b/README.md) |
| C 훅 작업자 | 제품 직결 훅(문제→증명→장점) 구현 | [`c/README.md`](c/README.md) |
| 백엔드 개발자 | v0.2 엔드포인트·캐시·상태 전이·결과 파일 저장 구현, 유형별 작업자 코드 호출 연결 | [`api-guide.md`](api-guide.md), `contracts/` |

각 작업자는 `selected_types`에 자기 유형 1개만 담아 프로젝트를 만들고, 서로의 유형 규칙은 건드리지 않습니다. 공통 필드와 에러 형식은 [`api-guide.md`](api-guide.md)가 기준입니다.

## 기본 더미 데이터

**뽀모도로 타이머**(60분 비주얼 아날로그 타이머), 카테고리 `stationery`. `prototypes/campaigns/digimore-timer-abc/00_product_facts.md`의 Verified/Whitelisted 사실만 씁니다. 미검증 사실(무소음, 배터리, 알람 dB, 치수, 가격·할인)은 쓰지 않습니다. 예시 JSON은 [`examples/`](examples/)와 `a/ b/ c/examples/`에 있습니다.

## 기능 요구사항과 수용 기준

### FR-001 제품 정보 가져오기 + 잠시 캐싱

- `POST /v1/product-info`가 `{ product, source_url? }`를 받아 `{ product_info_id, product, cached, cached_at, expires_at }`를 돌려준다.
- `POST /v1/projects`가 `product` 대신 `product_info_id`도 받는다(둘 중 하나).

수용 기준
- [ ] 같은 입력(정규화 해시)을 다시 보내면 `cached: true`와 같은 `product_info_id`가 온다.
- [ ] 캐시는 `PRODUCT_INFO_CACHE_TTL_SEC`(기본 3600)초 뒤 만료되고, 만료된 id로 프로젝트를 만들면 `404 PRODUCT_INFO_NOT_FOUND`다.
- [ ] `product.name`·`product.category`가 없으면 422다.
- [ ] `product`와 `product_info_id`가 모두 없으면 422다.

### FR-003 정보 기반 시나리오 생성

- 유형별 작업자가 제품 정보로 시나리오(`ScenarioItem`)를 만든다. 지금은 `count=1`.
- 다시 호출하면 기존 시나리오를 지우지 않고 추가(append)하고 `round`를 올린다.

수용 기준
- [ ] 응답에 `round`가 있고, `scenarios[]`는 누적 전체이며 새 항목의 `round`가 응답 `round`와 같다.
- [ ] 두 번째 호출 뒤에도 첫 번째 시나리오가 그대로 남아 있다.
- [ ] 각 시나리오는 유형 규칙(`a/ b/ c/` README)을 지킨다. 훅 15초 이하, 장면 3~5개, 장면 길이 합 = `hook_duration_sec`.
- [ ] 제품 사실은 `verified_facts` 안에서만 쓴다.

### FR-004 이미지 콘티 생성

수용 기준
- [ ] `frames[]`의 `beat_order`가 시나리오의 `beats[].order`와 1:1이다.
- [ ] 상태가 `STORYBOARD_READY`가 된다.

### 시나리오 선택 (신규)

수용 기준
- [ ] `POST …/scenarios/{sid}/select`가 `{ selected_scenario_id }`를 돌려주고 프로젝트에 저장한다.
- [ ] 없는 `sid`는 `404 SCENARIO_NOT_FOUND`다.

### FR-005 훅 만들기 + TTS

수용 기준
- [ ] 선택하지 않은 시나리오로 `POST …/hooks`를 보내면 `409 INVALID_STATE`다.
- [ ] 접수는 `202 { hook_id, job_id, status: "queued" }`이고, 상태는 `queued → running → done|failed`로 폴링할 수 있다.
- [ ] `done`이면 프로젝트 상태가 `HOOK_READY`다.
- [ ] 나레이션은 장면 길이 안에 읽힌다. 훅 영상은 15초 이하다.

### 결과를 파일로 저장 (신규)

수용 기준
- [ ] `done`일 때 `OUTPUT_DIR/{project_id}/{hook_id}/`에 `hook.mp4`, `tts.mp3`, `hook.srt`, `scenario.json`, `storyboard_NN.png`가 있고 `files`가 그 경로를 가리킨다.
- [ ] 더 뽑으면 새 `hook_id` 폴더가 생기고 기존 폴더는 그대로다.
- [ ] `GET …/outputs`가 프로젝트의 저장된 훅 목록을 돌려준다.

### 시나리오 더 뽑기 n회

- 서버에 반복 전용 API는 없다. 클라이언트가 시나리오→콘티→선택→훅 사이클을 n번 호출한다(화면 입력은 1~10).

수용 기준
- [ ] n=2로 돌리면 `round` 1·2의 시나리오·콘티·선택·훅이 각각 남고, 훅 결과 폴더가 2개다.
- [ ] 한 회차가 실패해도 이전 회차 결과는 보존된다.

## 결과 파일 저장 규칙 (요약)

```text
OUTPUT_DIR/{project_id}/{hook_id}/{hook.mp4, tts.mp3, hook.srt, scenario.json, storyboard_01.png …}
```

자세한 설명은 [`api-guide.md` §5](api-guide.md#5-결과-파일-저장-규칙)입니다.

## 미정 항목

- 제품 정보 캐시 유지 시간(임시 1시간)과 캐시 키 기준.
- `product`와 `product_info_id`가 함께 올 때의 우선순위(권장: `product_info_id`).
- "더 뽑기" 서버 상한(화면은 1~10, 한 호출 `count`는 1~5)과 횟수별 크레딧·일일 한도(FR-006) 적용.
- `OUTPUT_DIR` 기본값, 7일 보관 정책 적용 여부, 사용자에게 파일을 내려주는 방식(`files.*`를 URL로 줄지 서버 경로로 줄지).
- `storyboard.image_url`의 형식(URL/경로/데이터 URI)과 콘티 이미지 생성 도구.
- TTS 공급자·기본 목소리와 `tts.voice` 허용 값.
- 훅 생성 실패·재시도·화면 이탈 시 처리, 실패 후 프로젝트 상태.
- 훅 영상 생성 도구(생성형 영상 모델 / Remotion·Three.js)와 길이 비율. README의 PRD 요약과 같은 미결 항목입니다.
- 훅 API의 인증 방식(세션 토큰 권장, 워커 `API_BEARER_TOKEN`과의 관계).

## Notion 반영 요약

원본 PRD에 옮길 변경 후보입니다.

| 기능 | 현재 PRD | 변경 제안 |
| --- | --- | --- |
| 제품 정보 입력 (FR-001) | 확정 · 필수 입력 항목은 미정 | "정보 가져오기(URL 등) + 잠시 캐싱" 추가. 캐시 시간은 임시 1시간 |
| 글 시나리오 (FR-003) | 글을 선택한 유형만 만들지, 세 유형 모두 만들지 미정 | 개발 흐름에서는 작업자별 유형 1개·시나리오 1개씩, "더 뽑기"로 누적 |
| 시나리오 선택 | 없음 | 콘티까지 본 뒤 하나를 선택하는 단계 추가(FR-007 촬영 가이드의 선택과 별개) |
| 훅 생성 + TTS (FR-005) | 확정 · 생성 방식 미정 | 선택한 시나리오로 훅 + TTS 생성, 결과를 파일로 저장 |
| 원본영상 만들기 + TTS (FR-009) | 원본 업로드·분석 | 원본영상 편집 + TTS는 별도 트랙·파이프라인 미구현으로 표시 |
| 훅 합치기 (FR-010) | 확정 | 이번 개발 흐름 밖(후속). 기존 `renders` 동작 유지 |

API 변경 요약: 신규 `POST /v1/product-info`, `…/scenarios/{sid}/select`, `…/hooks`, `GET …/hooks/{hook_id}`, `GET …/outputs` / 확장 `POST /v1/projects`(`product_info_id`), `POST …/scenarios`(`count`, append, `round`) / 상태 전이 `HOOK_RENDERING → HOOK_READY` 추가. 자세한 내용은 [`contracts/api-spec.md`](../../contracts/api-spec.md) v0.2.
