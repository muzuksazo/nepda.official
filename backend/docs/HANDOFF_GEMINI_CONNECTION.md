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
| 모델 이름 | `gemini-4-hydrogen`, `gemini-nano-banana-2.1`, `gemini-omni-flash-preview` | 프로젝트·지역(us-central1)에 열린 이름이어야 함. 위 이름들은 **없음** |
| 우리 시스템에서 성공한 적 | 있음 (오전 PC 고래 훅 전체, 오후 Modal 시나리오 2회) | **없음** |

전환 스위치: Modal Secret `napda-backend` 의 `GOOGLE_GENAI_USE_VERTEXAI` (지금 `true`).
코드: `backend/app/genai_provider.py` 의 `build_genai_client`, B 작업자 `bridge-dev/b/src/wif.ts`, C 작업자 `bridge-dev/c/src/generate.py`.

## 오늘 겪은 순서와 상태

| # | 증상 | 원인 | 상태 |
|---|---|---|---|
| 1 | 이미지 호출이 8분 넘게 응답 없음 | Gemini 쪽 지연 | 요청 시간 제한·재시도, 참고 이미지 90초 상한 추가 (해결) |
| 2 | `RESOURCE_EXHAUSTED`, 이어서 `402 prepayment credits are depleted` | AI Studio 선불 크레딧 소진 | 충전됨. 단 영상은 충전 뒤에도 `RESOURCE_EXHAUSTED` 로 실패 (미해결, 할당량 의심) |
| 3 | `google.subject exceeds the 127 bytes limit` | WIF 매핑이 `assertion.sub`(약 150바이트) | 여원님이 GCP 매핑을 `assertion.workspace_id + ':' + assertion.container_id` 로 변경 (해결, 18:50 무렵 확인) |
| 4 | `'image/png' is not supported ... Supported values: 'image/jpeg'` | Vertex 이미지 응답은 JPEG 만 | 시험 코드 JPEG 로 수정 (훅 파이프라인은 원래 JPEG) |
| 5 | `Publisher model .../gemini-4-hydrogen was not found` (404) | AI Studio 모델 이름을 Vertex 에 그대로 씀 | **미해결 — 지금 막힌 곳** |
| 6 | `Model 'gemini-nano-banana-2.1' is not supported by the Interactions API` | 위와 같음 (이미지 모델) | **미해결** |

| 7 | AI Studio 키로 이미지(`gemini-nano-banana-2.1`)를 다시 부르자 첫 장에서 1시간 응답 없음 (실행 제한 3600초로 끊김, 19:08~20:09) | 불명 (1번과 같은 양상) | **미해결** — 지금은 Gemini 이미지가 두 창구 모두 안 된다 |

5·6 때문에 실패하는 곳: B·C 시나리오 작업자(Gemini 선택 시), 본편 대본(`BODY_LLM` 이 gemini 일 때), 참고 이미지(`IMAGE_MODEL`),
영상 클립(`VIDEO_MODEL`), A 템플릿 고르기.

## 다음 사람이 할 일

1. **Vertex 에서 쓸 수 있는 모델 이름 확정** (글 / 이미지 / 영상)
   - 여원님 문서·설정에는 글 모델로 `gemini-3.5-flash` 가 적혀 있다. 실제로 Vertex 에서 돌려 본 이름을 여원님께 확인.
   - 이미지는 Gemini 이미지 모델 또는 Imagen, 영상은 Veo 가 Vertex 쪽 후보. 프로젝트에서 사용 허가(약관·할당량)가 필요할 수 있다.
   - 확인 방법(무료, 조회만): 서버 이미지 안에서 `build_genai_client(Settings()).models.get(model=이름)` 을 후보마다 호출.
     `models.list()` 전체 조회는 Vertex 에서 끝나지 않았다(15분 이상).
2. **Modal Secret `napda-backend` 에 Vertex 이름 넣기**: `HOOK_WORKER_GEMINI_MODEL`, `BODY_LLM`, `IMAGE_MODEL`, `VIDEO_MODEL`
   (설정 이름은 `backend/app/config.py`).
3. **Interactions API 지원 확인**: 이미지·영상은 `interactions.create` 로 부른다. Vertex 에서 해당 모델이 Interactions API 를 지원하지 않으면
   `generate_content`(이미지) / `generate_videos`(Veo) 경로를 `genai_provider.py` 에 추가해야 한다.
4. **급하면 임시로 AI Studio 로 되돌리기**: Secret 에서 `GOOGLE_GENAI_USE_VERTEXAI=false` → 기존 이름 그대로 동작 (크레딧·할당량 확인 필요).

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
