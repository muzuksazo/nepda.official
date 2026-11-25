# Shortform Ad Production Worker (`google-genai` SDK)

어제 로컬 Chrome Flow(`flow_automator.py`) 기반으로 실행하던 숏폼 광고 파이프라인을 **공식 `google-genai>=3.0.0` Python SDK + FastAPI + Docker FFmpeg 워커**로 전환한 프로덕션 서비스입니다.  
기존 루트의 HookCut Vercel 웹앱(`index.html`, `api/*`, `vercel.json`)과는 완전히 분리되어 있습니다(`.vercelignore` 제외).

## 1. 로컬 개발 환경 세팅 (`uv` 권장)

```bash
cd production
uv venv .venv --python 3.11
source .venv/bin/activate
uv pip install -r requirements.txt
cp .env.example .env  # GEMINI_API_KEY 입력
```

### 서버 실행 & 배치 CLI
```bash
# 1) FastAPI 컨트롤 서버 실행
uvicorn app.server:app --host 0.0.0.0 --port 8080

# 2) 기존 05_jobs.json 을 google-genai SDK 로 직접 실행 (flow_automator.py 대체)
python -m app.cli run-jobs \
  --jobs ../campaigns/piev-airwasher-abc/05_jobs.json \
  --project ../campaigns/piev-airwasher-abc \
  --source /path/to/source.mp4 \
  --concurrency 3 \
  --max-credits 180

# 3) 전체 파이프라인 단건 배치 실행 (Cloud Run Jobs 용)
python -m app.cli run-campaign \
  --campaign-id piev-v1 \
  --source /path/to/source.mp4 \
  --facts ../campaigns/piev-airwasher-abc/00_product_facts.md \
  --spec ../campaigns/piev-airwasher-abc/05_ad_spec.json \
  --res 720p --dry-run
```

## 2. Docker 빌드 (Cloud Run / Cloud Run Jobs 공용)

레포 루트(`<REPO_ROOT>`, 즉 `nepda.oficial` 최상위)에서 빌드합니다:

```bash
docker build -f production/Dockerfile -t gcr.io/<PROJECT_ID>/shortform-ad-worker:latest .
```

컨테이너에는 `ffmpeg`, `fonts-noto-cjk`, `skills/shortform-ad-remix-director/scripts/`, `production/app/` 가 모두 포함됩니다.

## 3. 인증 전환 (AI Studio API Key ↔ Vertex AI + Workload Identity)

코드를 수정할 필요 없이 환경변수만 바꾸면 `build_genai_client(settings)` 가 전환됩니다:

- **AI Studio (`GEMINI_API_KEY`)**: `GOOGLE_GENAI_USE_VERTEXAI=false`, `GEMINI_API_KEY=...`
- **GCP Cloud Run (키 파일 없는 Attached Service Account)**:
  - `GOOGLE_GENAI_USE_VERTEXAI=true`
  - `GOOGLE_CLOUD_PROJECT=<PROJECT_ID>`
  - `GOOGLE_CLOUD_LOCATION=us-central1`
  - Cloud Run 서비스/잡에 Vertex AI User 권한이 있는 Service Account 를 연결하면 자동 ADC 인증됩니다.
- **Vercel ↔ GCP 연동**: Vercel OIDC Provider 를 GCP Workload Identity Pool 에 연결(WIF)하면 `service-account.json` 없이 Cloud Run Jobs 트리거 / Cloud Tasks 발행 / GCS 업로드를 수행할 수 있습니다.
