# Vercel (`napda-api`) ↔ GCP Vertex AI Workload Identity(WIF) 연동 가이드

이 문서는 정적 서비스 계정 JSON 키 없이 Vercel 서버리스 백엔드(`napda-api`)가 GCP 크레딧으로 **Vertex AI (`google-genai`)** 를 호출하도록 연결하는 팀원용 설정 가이드입니다.

> **참고 (계정 분리 가능)**  
> 사용자 Google 로그인(OAuth / GIS)에 쓰는 Google 계정·GCP 프로젝트와, Vertex AI 비용/무료 크레딧을 쓰는 GCP 계정은 **서로 달라도 전혀 상관없습니다.**

---

## 사전 준비물
1. **결제 계정(또는 무료 크레딧)이 연결된 본인 명의 GCP 프로젝트** (`<GCP_PROJECT_ID>`, `<GCP_PROJECT_NUMBER>`)
2. **`napda-api`가 배포된 Vercel 팀 slug** (`<VERCEL_TEAM_SLUG>`)
   - 백엔드 디렉터리에서 `vercel teams ls` 또는 `cd backend && vercel project inspect napda-api`로 확인합니다.

---

## 1단계: GCP 프로젝트에 필수 API 3개 활성화
대상 GCP 프로젝트(`<GCP_PROJECT_ID>`)에서 아래 3개 API를 사용 설정합니다.
- **IAM Service Account Credentials API** (`iamcredentials.googleapis.com`)
- **Security Token Service API** (`sts.googleapis.com`)
- **Vertex AI API** (`aiplatform.googleapis.com`, 콘솔 검색 시 *Agent Platform API*로 표시될 수 있음)

---

## 2단계: Vertex AI 호출용 서비스 계정 생성
GCP 콘솔 **IAM 및 관리자 → 서비스 계정 → 서비스 계정 만들기**:
1. **서비스 계정 이름**: `NAPDA Vercel WIF`
2. **서비스 계정 ID**: `napda-vercel-wif`
   - 생성되는 이메일: `napda-vercel-wif@<GCP_PROJECT_ID>.iam.gserviceaccount.com`
3. **역할 부여**: **`Vertex AI 사용자`** (`roles/aiplatform.user` — 한국어 콘솔에서는 **`Agent Platform 사용자`**로 표시될 수 있음)

---

## 3단계: Workload Identity Pool & Vercel OIDC 공급업체 생성
GCP 콘솔 **IAM 및 관리자 → 워크로드 아이덴티티 제휴 → 풀 만들기**:
1. **풀 정보**
   - **이름**: `Vercel NAPDA Pool`
   - **풀 ID**: `vercel-napda-pool`
2. **풀에 공급업체 추가 (`OpenID Connect (OIDC)`)**
   - **제공자 이름**: `Vercel NAPDA API`
   - **제공업체 ID**: `vercel-napda-api`
   - **발급자(URL)**: `https://oidc.vercel.com/<VERCEL_TEAM_SLUG>`
   - **대상(Audiences)**: **허용된 잠재고객(Allowed audiences)** 선택 → `https://vercel.com/<VERCEL_TEAM_SLUG>`
3. **공급업체 속성 매핑**
   - `google.subject` = `assertion.sub`
4. 저장 후 풀/공급업체 상세에서 **전체 Provider 리소스 경로**를 확인합니다:
   ```text
   projects/<GCP_PROJECT_NUMBER>/locations/global/workloadIdentityPools/vercel-napda-pool/providers/vercel-napda-api
   ```

> **Vercel OIDC Issuer Mode 확인**  
> Vercel 대시보드 → `napda-api` 프로젝트 → **Settings → Security → Secure Backend Access with OIDC Federation**에서 **Issuer Mode**가 **`Team`** (`https://oidc.vercel.com/<VERCEL_TEAM_SLUG>`)으로 되어 있어야 위 발급자 URL과 일치합니다.

---

## 4단계: 서비스 계정 가장(`workloadIdentityUser`) 권한 부여
방금 만든 풀(`vercel-napda-pool`) 페이지에서 **액세스 권한 부여 → 서비스 계정을 사용하여 액세스 권한 부여**를 2회 진행해 `production`과 `preview` 환경을 허용합니다:
- **서비스 계정**: `napda-vercel-wif@<GCP_PROJECT_ID>.iam.gserviceaccount.com`
- **속성 매핑 키**: `subject`
- **속성 값**:
  1. `owner:<VERCEL_TEAM_SLUG>:project:napda-api:environment:production`
  2. `owner:<VERCEL_TEAM_SLUG>:project:napda-api:environment:preview`

*(로컬에서 `vercel env pull`의 `development` OIDC 토큰까지 테스트하려면 `:environment:development`도 추가로 허용하면 되며, 일반 로컬 개발은 `.env`의 `GEMINI_API_KEY` + `GOOGLE_GENAI_USE_VERTEXAI=false` 사용을 권장합니다.)*

---

## 5단계: Vercel (`napda-api`) 환경변수 등록 및 재배포
Vercel 대시보드(`napda-api` → Settings → Environment Variables, **Production / Preview** 모두) 또는 CLI(`backend/` 기준)로 아래 5개를 등록합니다. JSON 키 파일은 필요 없습니다.

| 변수명 | 값 |
| --- | --- |
| `GOOGLE_GENAI_USE_VERTEXAI` | `true` |
| `GOOGLE_CLOUD_PROJECT` | `<GCP_PROJECT_ID>` |
| `GOOGLE_CLOUD_LOCATION` | `us-central1` |
| `GCP_WORKLOAD_IDENTITY_PROVIDER` | `projects/<GCP_PROJECT_NUMBER>/locations/global/workloadIdentityPools/vercel-napda-pool/providers/vercel-napda-api` |
| `GCP_SERVICE_ACCOUNT_EMAIL` | `napda-vercel-wif@<GCP_PROJECT_ID>.iam.gserviceaccount.com` |

CLI 등록 예시 (`backend/` 디렉터리에서 실행):
```bash
for env_name in production preview; do
  BRANCH_ARG=()
  [ "$env_name" = "preview" ] && BRANCH_ARG=("")
  vercel env add GOOGLE_GENAI_USE_VERTEXAI "$env_name" "${BRANCH_ARG[@]}" --value "true" --force --yes --non-interactive
  vercel env add GOOGLE_CLOUD_PROJECT "$env_name" "${BRANCH_ARG[@]}" --value "<GCP_PROJECT_ID>" --force --yes --non-interactive
  vercel env add GOOGLE_CLOUD_LOCATION "$env_name" "${BRANCH_ARG[@]}" --value "us-central1" --force --yes --non-interactive
  vercel env add GCP_WORKLOAD_IDENTITY_PROVIDER "$env_name" "${BRANCH_ARG[@]}" --value "projects/<GCP_PROJECT_NUMBER>/locations/global/workloadIdentityPools/vercel-napda-pool/providers/vercel-napda-api" --force --yes --non-interactive
  vercel env add GCP_SERVICE_ACCOUNT_EMAIL "$env_name" "${BRANCH_ARG[@]}" --value "napda-vercel-wif@<GCP_PROJECT_ID>.iam.gserviceaccount.com" --force --yes --non-interactive
done
```

환경변수 등록 후 `napda-api`를 재배포(`vercel deploy --prod` 또는 `main` 푸시)한 뒤 헬스체크에서 모드를 확인합니다:
```bash
curl -fsS https://napda-api.vercel.app/health
# "auth_mode": "vertex_ai" 확인
```

---

## 6단계: 비용 분리 라벨 · 지출 한도(Spend Cap) · 일시 정지
- **자동 결제 라벨 (`app: napda`)**: 백엔드([`genai_provider.py`](./app/genai_provider.py))의 `models.generate_content` 호출(플래너·TTS)에는 자동으로 `labels={"app": "napda", "component": "planner|tts"}`가 포함됩니다(`GCP_BILLING_APP_LABEL`로 변경 가능). GCP 콘솔 **결제 → 보고서 → 필터 → 라벨 (`app: napda`)**로 해당 프로젝트 내 다른 서비스와 비용을 구분할 수 있습니다. *(이미지·비디오용 `interactions.create`는 SDK 스키마상 `labels`를 지원하지 않으므로 Cloud Audit Logs에서 서비스 계정 이메일로 구분하세요.)*
- **예산 및 지출 한도(Budgets & caps)**: GCP **결제 → Budgets & caps**에서 해당 프로젝트의 Vertex AI 서비스에 **지출 한도 적용(Spend Cap)**을 걸어두면 예상치 못한 과금을 막을 수 있습니다.
- **즉시 차단/일시 정지**: Vercel 코드를 건드리지 않고 GCP **워크로드 아이덴티티 제휴 → `vercel-napda-pool` → 풀 상태 토글 끄기** 또는 공급업체 사용 중지로 즉시 호출을 차단할 수 있습니다.
