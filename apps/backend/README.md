# 냅다 백엔드·미디어 워커

기존 `production/`의 FastAPI 앱을 `apps/backend/`로 이동했습니다. API·작업 상태·저장소·미디어 생성·FFmpeg 조립을 담당합니다. 재사용 CLI는 `libraries/media-tools/`, 플래너 API는 `libraries/planner-api/`에서 관리합니다.

## 로컬 실행

저장소 루트 기준입니다. Python 3.11 이상, uv, FFmpeg·FFprobe를 준비합니다.

```bash
uv venv .venv --python 3.12
uv pip install --python .venv/bin/python -r apps/backend/requirements.txt
cp apps/backend/.env.example apps/backend/.env
.venv/bin/python -m uvicorn app.server:app --app-dir apps/backend --host 127.0.0.1 --port 8080
```

Windows에서는 Python 경로를 `.venv\Scripts\python.exe`로 바꿉니다. 설정 파일은 실행 위치와 관계없이 `apps/backend/.env`에서 읽고, 작업 파일·SQLite는 `apps/backend/data/`에 보관합니다. `SCRIPTS_DIR` 기본값은 저장소의 `libraries/media-tools/`입니다.

| API | 역할 |
| --- | --- |
| `GET /health` | 인증 모드·도구·기본 경로 확인 |
| `POST /v1/uploads/presign` | 업로드 URL 발급 |
| `POST /v1/jobs` | 제작 작업 접수 |
| `GET /v1/jobs`, `GET /v1/jobs/{job_id}` | 작업 조회 |
| `POST /v1/jobs/{job_id}/retry-unit/{unit_id}` | 생성 단위 재시도 |

`API_BEARER_TOKEN`을 설정하면 작업 API 인증을 사용합니다. 플래너의 `WORKER_BEARER_TOKEN`과 맞춥니다.

## CLI와 캠페인 자료

프로젝트·제품 정보·스펙 경로를 실제 파일로 지정합니다. 기존 제작 자료는 `prototypes/campaigns/`에 있습니다. 다음은 Bash/WSL 기준의 실행 예시입니다.

```bash
PYTHONPATH=apps/backend .venv/bin/python -m app.cli run-campaign \
  --campaign-id piev-v1 \
  --source /path/to/source.mp4 \
  --facts prototypes/campaigns/piev-airwasher-abc/00_product_facts.md \
  --spec prototypes/campaigns/piev-airwasher-abc/05_ad_spec_A.json \
  --res 720p --dry-run
```

## Docker

저장소 루트를 빌드 컨텍스트로 사용합니다.

```bash
docker build -f apps/backend/Dockerfile -t napda-backend .
```

컨테이너에는 백엔드와 `libraries/media-tools/`, FFmpeg, Noto CJK 글꼴이 포함됩니다. 컨테이너의 `SCRIPTS_DIR=/app/scripts`를 사용합니다.

## Google 인증

- API 키: `GOOGLE_GENAI_USE_VERTEXAI=false`, `GEMINI_API_KEY` 설정.
- Vertex AI: `GOOGLE_GENAI_USE_VERTEXAI=true`, `GOOGLE_CLOUD_PROJECT`, `GOOGLE_CLOUD_LOCATION` 설정과 실행 환경의 ADC 인증 사용.
- 서비스 계정 키 파일은 저장소에 보관하지 않습니다.

이 폴더는 기존 워커의 실행 위치를 정리한 것입니다. 최종 생성 방식과 PRD의 제품 흐름은 추가 개발이 필요합니다. [PRD별 테스트](../../tests/README.md)를 참고하세요.
