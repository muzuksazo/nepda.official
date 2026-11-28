# 인수인계: Gemini 연결 문제 (2026-11-27 저녁 기준)

## 한 줄 요약

Modal 서버는 지금 Gemini 를 **Vertex AI(WIF)** 로 부르도록 켜져 있는데, 우리 코드의 모델 이름이 AI Studio 기준이라
**Vertex 에서 "모델 없음"으로 전부 실패**한다. 그래서 서버의 Gemini 기능(시나리오 A/B 의 Gemini 쪽, 이미지, 영상, 본편 대본)이 동작하지 않는다.
Claude 경로는 정상이다.

## 배경: Gemini 를 부르는 두 창구

| | AI Studio (API 키) | Vertex AI (WIF, 여원님 연결) |
|---|---|---|
| 인증 | `GEMINI_API_KEY` | Modal 컨테이너 신원 토큰 → GCP Workload Identity (키 없음) |
| 결제 | AI Studio 선불 크레딧 (GCP 가입 크레딧 사용 불가) | GCP 결제 계정, 가입 크레딧 사용 가능 |
| 모델 이름 | `gemini-4-hydrogen`, `gemini-nano-banana-2.1`, `gemini-omni-flash-preview` | **`location=global`(`aiplatform.googleapis.com`)에 위 3개 모두 개방되어 있음** (`us-central1`에는 없음) |
| 우리 시스템에서 성공한 적 | 있음 (오전 PC 고래 훅 전체, 오후 Modal 시나리오 2회) | **20:58 실검증 성공 (`global`)**: 텍스트 `gemini-4-hydrogen` (1.45s), 이미지 `gemini-nano-banana-2.1` via `generate_content` (14.23s) |

전환 스위치: Modal Secret `napda-backend` 의 `GOOGLE_GENAI_USE_VERTEXAI` (지금 `true`).
코드: `backend/app/genai_provider.py` 의 `build_genai_client`, B 작업자 `bridge-dev/b/src/wif.ts`, C 작업자 `bridge-dev/c/src/generate.py`.

## 오늘 겪은 순서와 상태

| # | 증상 | 원인 | 상태 |
|---|---|---|---|
| 1 | 이미지 호출이 8분 넘게 응답 없음 | Gemini 쪽 지연 | 요청 시간 제한·재시도, 참고 이미지 90초 상한 추가 (해결) |
| 2 | `RESOURCE_EXHAUSTED`, 이어서 `402 prepayment credits are depleted` | AI Studio 선불 크레딧 소진 | 충전됨. 단 영상은 충전 뒤에도 `RESOURCE_EXHAUSTED` 로 실패 (미해결, 할당량 의심) |
| 3 | `google.subject exceeds the 127 bytes limit` | WIF 매핑이 `assertion.sub`(약 150바이트) | 여원님이 GCP 매핑을 `assertion.workspace_id + ':' + assertion.container_id` 로 변경 (해결, 18:50 무렵 확인) |
| 4 | `'image/png' is not supported ... Supported values: 'image/jpeg'` | Vertex 이미지 응답은 JPEG 만 | 시험 코드 JPEG 로 수정 (훅 파이프라인은 원래 JPEG) |
| 5 | `Publisher model .../gemini-4-hydrogen was not found` (404) | Modal Secret의 `GOOGLE_CLOUD_LOCATION`이 `us-central1`로 남아 있었음 (`global` 엔드포인트에서는 `gemini-4-hydrogen` / `gemini-nano-banana-2.1` / `gemini-omni-flash-preview` 모두 200 OK 확인) | **원인 확인 (`GOOGLE_CLOUD_LOCATION=global` 변경 필요)** |
| 6 | `Model 'gemini-nano-banana-2.1' is not supported by the Interactions API` | Vertex AI에서는 `gemini-nano-banana-2.1`이 Interactions API 미지원 (`models.generate_content`로 14.23s 정상 생성 확인) | **`genai_provider.py` 수정 완료** (Vertex 모드일 때 `models.generate_content` 자동 라우팅 + PNG→JPEG 변환) |
| 7 | `gemini-omni-flash-preview` (`interactions.create`) 30s 클라이언트 타임아웃 | Vertex `global`에 모델(`200`)은 존재하나 Interactions API 비디오 요청 응답 지연; `veo-3.1-generate-001` / `veo-3.1-fast-generate-001`은 `us-central1`에 존재 | **추후 확인 필요** (`video_timeout` / `generate_videos`) |
| 8 | AI Studio 키로 이미지(`gemini-nano-banana-2.1`)를 다시 부르자 첫 장에서 1시간 응답 없음 (실행 제한 3600초로 끊김, 19:08~20:09) | 불명 (1번과 같은 양상) | Vertex `generate_content` 경로에서는 14.23s 응답 확인 |

5·6 때문에 실패하던 곳: Modal Secret `napda-backend`의 `GOOGLE_CLOUD_LOCATION=global` 전환 및 이번 `genai_provider.py` 패치 배포 후 텍스트·이미지는 Vertex 경로로 동작합니다.

## 다음 사람이 할 일

1. **Modal Secret `napda-backend`에서 `GOOGLE_CLOUD_LOCATION=global`로 변경 (필수)**:
   - GCP WIF 토큰 발급(`iamcredentials.googleapis.com GenerateAccessToken`)은 이미 Audit Log상 정상 동작 중이며, 모델(`gemini-4-hydrogen`, `gemini-nano-banana-2.1`, `gemini-omni-flash-preview`)은 모두 `global` 엔드포인트에 열려 있습니다.
2. **영상 생성 경로 점검 (`gemini-omni-flash-preview` vs `veo-3.1-*`)**:
   - `gemini-omni-flash-preview`가 Vertex `global` Interactions API에서 타임아웃될 경우 `us-central1`의 `veo-3.1-fast-generate-001` / `veo-3.1-generate-001`(`generate_videos`) 사용을 검토합니다.
3. **급하면 임시로 AI Studio 로 되돌리기**: Secret 에서 `GOOGLE_GENAI_USE_VERTEXAI=false` → AI Studio 크레딧/할당량 사용.

## 확인 도구

- 시나리오 A/B (같은 제품으로 Claude / Gemini 각각): `POST /v1/projects/{id}/scenarios` 에 `{"provider": "anthropic" | "google", "model": ...}`.
  결과 시나리오의 `ad_spec.llm_provider / llm_model` 에 실제 쓴 모델이 남는다.
  2026-11-27 결과: anthropic 은 B·C 92초에 성공, google 은 404(위 5번).
- 스틸컷 비교 (같은 시나리오·같은 묘사로 FLUX / Gemini):
  `python backend/selfhosted/still_cycle.py <product.json> <out> --types B --engine gemini --scenario <cycle.json> --same-captions <cycle.json> --ref <제품사진>`
  `STILL_GEMINI_VIA=apikey` 를 붙이면 Vertex 대신 AI Studio 키로 부른다.

## 같이 알아둘 것

- **Modal 자동 배포(`cd-modal.yml`)가 아직 성공한 적 없다.** 배포 전 테스트에서 `tests/hookpipe/test_render_and_attach.py::ApiFlow::test_render_builds_hook_then_attaches_uploaded_body`
  하나가 실패한다(결과 URL 이 서명된 `/v1/media/...` 로 바뀐 뒤 테스트가 로컬 파일 경로를 기대). ffmpeg 가 있는 CI 에서만 돈다. 따로 고칠 것.
  그 전까지 Modal 배포는 수동: `modal deploy backend/modal_app.py`.
- Claude 키(`ANTHROPIC_API_KEY`)는 Secret 에 있고, Claude 경로(시나리오·본편 대본·장면 묘사 변환)는 정상이다.
- 키·토큰 값은 이 문서와 저장소에 없다. 전부 Modal Secret 에 있다.
