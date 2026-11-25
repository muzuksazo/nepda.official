# 냅다(NAPDA) MVP REST API 명세 v0.1

PRD v0.2([`../README.md`](../README.md)) 기준 **가이드 먼저형** 9단계 흐름과 기존 워커 API를 통합한 공식 API 명세서입니다.  
기계 판독용 OpenAPI 3.1 스키마는 [`openapi.json`](openapi.json)에서 확인할 수 있습니다.

---

## 1. 확정 정책 요약 (5대 결정 사항)

| 항목 | 확정 정책 | 코드/환경변수 |
| :--- | :--- | :--- |
| **FR-001 필수 입력** | `product.name` + `product.category`(`living` \| `kitchen` \| `stationery`) + `product.verified_facts`(1개 이상). `one_liner`, `price_or_offer`, `target_audience`는 선택 | `ProductInput` |
| **FR-008 이어하기 인증** | **Google One Tap (+ Google 버튼 fallback)** — `POST /v1/auth/google`로 Google ID Token(JWT)을 `google-auth`로 검증 후 7일 서명 세션(`HttpOnly` 쿠키 `napda_session` + Bearer `access_token`) 발급 | `GOOGLE_CLIENT_ID`, `SESSION_SECRET`, `SESSION_TTL_DAYS=7` |
| **FR-009 업로드 제한** | 단일 파일 & 컷별 다중 파일 모두 허용(`1~20`개), **파일당 최대 100MB**, **총 길이 5~90초**. 가이드와 다른 비율/길이는 비차단 `warnings[]` 반환 | `MAX_UPLOAD_FILE_BYTES=104857600`, `MIN_UPLOAD_TOTAL_SEC=5.0`, `MAX_UPLOAD_TOTAL_SEC=90.0` |
| **FR-006 크레딧/무료 한도** | 결제 제외 무료 베타 — Google 계정(`user_id`)당 **일일 영상 생성 3회 제한** + 실행 전 단계별 예상 크레딧(`/estimate`) 표시 | `DAILY_RENDER_LIMIT=3` |
| **보관 기간(TTL)** | 프로젝트·업로드 원본·결과물 **생성일로부터 7일 보관 후 자동 만료** (`expires_at` 반환) | `RETENTION_TTL_DAYS=7` |

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
        "code": "INVALID_UPLOAD_LIMIT | DAILY_QUOTA_EXCEEDED | INVALID_STATE | PROJECT_NOT_FOUND | UNAUTHORIZED",
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
| **FR-001** | `POST /v1/projects` | 제품 정보 + 선택한 유형(`1~3`개) + `flow_mode`(`guide_first` \| `skip_drafts`)로 프로젝트 생성 (`201`) |
| **FR-008** | `GET /v1/projects` | 내 프로젝트 목록 최신순 조회 (촬영 후 다른 기기에서도 이어하기) |
| **FR-008** | `GET /v1/projects/{project_id}` | 프로젝트 상세 + 시나리오 + 촬영 가이드 + 업로드 상태 + 최신 잡 + `expires_at` 조회 |
| **FR-003** | `POST /v1/projects/{project_id}/scenarios` | 선택한 유형별 글 시나리오 생성 (`planner-api` 연동) |
| **FR-004** | `POST /v1/projects/{project_id}/scenarios/{scenario_id}/storyboard` | 선택형 이미지 콘티('그림으로 보기') 생성 |
| **FR-007** | `POST /v1/projects/{project_id}/filming-guide` | 최종 1개 시나리오 선택 → 장면별 촬영 가이드(`shots[]`) 생성 |
| **FR-006** | `POST /v1/projects/{project_id}/estimate` | 실행 전 단계별 예상 크레딧 및 오늘 남은 무료 생성 횟수 조회 |
| **FR-009** | `POST /v1/uploads/presign` | S3/R2 Presigned PUT URL 발급 |
| **FR-009** | `POST /v1/projects/{project_id}/uploads/complete` | 업로드 완료 검증 (100MB/파일, 5~90초 총합, `16:9` 등 비율 차이 시 비차단 `warnings` 반환) |
| **FR-005·010·011** | `POST /v1/projects/{project_id}/renders` | 훅 생성 + TTS + 본편 연결 잡 접수 (`202`, 한도 초과 시 `429`, `skip_drafts=true` 시 시나리오 생략 가능) |
| **FR-012·013·014** | `GET /v1/projects/{project_id}/deliverables` | 결과 영상 스트리밍/다운로드 URL, 썸네일 URL, AI 라벨 안내(`AI 연출 포함`), `expires_at` 반환 |

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
