# Modal 계정 옮기기 (2026-11-28 기준)

영상 파이프라인 전체를 다른 Modal 계정(워크스페이스)으로 옮기는 절차입니다. 코드는 그대로 쓰고, **비밀값·모델 파일·배포**만 새 계정에서 다시 합니다.
키 값은 이 문서와 저장소에 없습니다. 옮기는 사람이 원래 값을 따로 받아 넣습니다.

## 지금 Modal 에 있는 것

| 종류 | 이름 | 내용 |
|---|---|---|
| 앱 | `napda-backend` | 백엔드 API(FastAPI) + 훅 파이프라인, CPU. `backend/modal_app.py` |
| 앱 | `napda-flux3-klein` | FLUX 이미지(스틸컷), H100. `infra/modal-flux3/modal_app.py` |
| 앱 | `napda-minimax` | MiniMax-H3 영상 클립, H100. `backend/selfhosted/minimax_modal.py` (지금은 시험 실행기가 그때그때 띄움) |
| 볼륨 | `napda-data` | 서버 DB·작업 파일 |
| 볼륨 | `minimax-models` | MiniMax 모델 약 42GB (터보 LoRA 포함) |
| 볼륨 | `flux-models` | FLUX 가중치 약 52GB |
| Secret | `napda-backend` | 아래 키 목록 |
| Secret | `flux3-klein-secrets` | `MODAL_API_TOKEN` (FLUX 서비스 호출 인증) |

## 1. 새 계정 로그인

```
pip install modal
modal token new          # 브라우저에서 새 계정으로 로그인
modal profile current    # 새 계정인지 확인
```

## 2. Secret 다시 만들기 (Modal 웹 → Secrets)

**`napda-backend`** — 키 이름(값은 원래 계정에서 받아 옴):

- 인증·세션: `SESSION_SECRET`, `GOOGLE_CLIENT_ID`, `SESSION_TTL_DAYS`, `API_BEARER_TOKEN`
- 저장소(R2): `STORAGE_BACKEND`(=r2), `R2_BUCKET`, `R2_ENDPOINT_URL`, `R2_REGION`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_PREFIX`(=`/`)
- 글 모델: `ANTHROPIC_API_KEY`, `HOOK_WORKER_LLM`, `BODY_LLM`
- 음성: `TTS_PROVIDER`(=inworld), `INWORLD_API_KEY`, `INWORLD_VOICE_ID`
- 이미지·영상 모델 이름: `IMAGE_MODEL`, `VIDEO_MODEL`
- 모델 다운로드: `HF_TOKEN` (FLUX 약관에 동의한 Hugging Face 계정)
- 기타: `RETENTION_TTL_DAYS`, `DAILY_RENDER_LIMIT`
- Gemini 를 쓸 때만: `GEMINI_API_KEY` 또는 Vertex 용 `GOOGLE_GENAI_USE_VERTEXAI`, `GOOGLE_CLOUD_PROJECT`, `GOOGLE_CLOUD_LOCATION`, `GCP_WORKLOAD_IDENTITY_PROVIDER`, `GCP_SERVICE_ACCOUNT_EMAIL` (5번 참고)

**`flux3-klein-secrets`** — `MODAL_API_TOKEN` 하나 (아무 긴 난수). 같은 값을 백엔드 쪽 `FLUX3_API_TOKEN` 으로도 씁니다.

## 3. 모델 파일 다시 받기 (CPU, 합쳐서 10분 안팎)

```
modal run backend/selfhosted/minimax_modal.py::download
MODAL_FLUX3_VOLUME=flux-models MODAL_FLUX3_QUANT= MODAL_FLUX3_ENABLE_PUP=false MODAL_FLUX3_SECRET=napda-backend \
  modal run infra/modal-flux3/modal_app.py::download_weights
```

`napda-data`(DB) 는 새로 시작해도 됩니다. 옮겨야 하면 `modal volume get napda-data / ./backup` 으로 받아 새 계정에서 `modal volume put` 합니다.

## 4. 배포

```
modal deploy backend/modal_app.py
MODAL_FLUX3_VOLUME=flux-models MODAL_FLUX3_QUANT= MODAL_FLUX3_ENABLE_PUP=false MODAL_FLUX3_GPU=H100 MODAL_FLUX3_SCALEDOWN_SEC=120 \
  modal deploy infra/modal-flux3/modal_app.py
modal deploy backend/selfhosted/minimax_modal.py
```

배포가 끝나면 주소가 바뀝니다: `https://<새 워크스페이스>--napda-backend-api.<지역>.modal.run`

- 프론트: `VITE_API_BASE_URL` 을 새 주소로
- GitHub Variables: `MODAL_BACKEND_URL` 을 새 주소로
- GitHub Secrets: `MODAL_TOKEN_ID`, `MODAL_TOKEN_SECRET` 를 새 계정 토큰(Modal → Settings → API Tokens)으로 → 이후 main 에 합치면 `cd-modal.yml` 이 자동 배포

## 5. Gemini(Vertex) 를 쓸 때만

GCP 연결(WIF)이 **Modal 워크스페이스 ID 에 묶여** 있습니다. 새 워크스페이스로 옮기면 GCP 의 Workload Identity 풀에 새 워크스페이스용 공급업체를 추가하고, 속성 매핑을
`google.subject = assertion.workspace_id + ':' + assertion.container_id` 로 둡니다(127바이트 제한). 자세한 절차는 `backend/GCP_WIF_SETUP.md` 7·8단계.

## 6. 확인

1. `GET <새 주소>/health` → `status: ok`, `GET <새 주소>/health?deep=true`(Bearer `API_BEARER_TOKEN`) → `hookpipe.ready: true`
2. 훅 한 편: `python backend/selfhosted/hook_cycle.py <product.json> <out> --type B --steps 8 --ref <제품사진> --footage <촬영본>...`
   (시나리오 → 스틸컷 → 클립 → 조립 → 본편까지. 약 6~8분, 약 $0.5~1)

## 비용 메모

- GPU 는 요청이 있을 때만 켜지고 2분 뒤 꺼집니다(H100 시간당 약 $4). 훅 한 편 약 $0.5~1.
- 볼륨 약 100GB 를 보관합니다. 계정 요금제에 따라 저장 비용이 붙을 수 있습니다.
