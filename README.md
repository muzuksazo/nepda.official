# 냅다

**본편 영상에 시선을 붙잡는 훅을 더하는 숏폼 광고 제작 스튜디오**

냅다는 제품·가게의 광고 영상을 바탕으로 훅을 기획하고, 문구와 장면을 다듬어 **9:16 세로 숏폼**으로 만드는 웹 프로토타입입니다. 서로 다른 A·B·C 기획을 비교하고, 영상과 썸네일을 함께 준비할 수 있습니다.

[웹 프로토타입 열기](https://hookcut-sandy.vercel.app)

## 주요 기능

- **영상 기반 AI 기획**: 본편 영상에서 제품·가게 정보와 주요 장면을 읽어 훅과 광고 구성을 제안합니다.
- **A·B·C 훅 비교**: 반전형·정보형·실용형 기획을 선택하고 미리보기로 비교합니다.
- **문구·장면 편집**: 광고 문구, 본편 구간과 순서, 훅에 사용할 사진을 수정합니다.
- **영상·썸네일 출력**: 선택한 안을 내보내거나 A·B·C 영상과 썸네일을 한 번에 준비합니다.
- **여러 제작 방식**: 브라우저의 Three.js 렌더링, 로컬 Blender 연결, Google Flow를 활용하는 작업 흐름을 제공합니다.

## 사용 흐름

1. **본편 영상 올리기** — 광고에 사용할 제품·가게 영상을 선택합니다.
2. **AI로 훅 기획하기** — 영상에서 읽은 정보와 제안된 구성을 확인합니다.
3. **A·B·C 중 선택하기** — 원하는 방향을 고르고 문구·사진·본편 구간을 다듬습니다.
4. **미리보기와 내보내기** — 결과를 확인하고 영상·썸네일을 저장합니다.

### A·B·C 기획 방향

| 유형 | 방향 | 구성 예시 |
| --- | --- | --- |
| A · 반전형 | 제품과 거리가 있는 장르로 시작해 광고로 전환 | 엉뚱한 상황이나 장르 연출 → 제품 등장 |
| B · 정보형 | 제품과 연결되는 문제·정보로 관심 유도 | 궁금증이나 정보 제시 → 제품과 연결 |
| C · 실용형 | 제품의 용도와 사용 장면을 바로 전달 | 문제 상황 → 사용 방법과 제품 |

세부 기획 기준은 [훅 설계 가이드](skills/shortform-ad-hooks-blueprint/SKILL.md)에서 관리합니다.

## 구성과 실행 범위

이 저장소는 웹 편집기, AI 기획 서버, 미디어 워커와 캠페인 제작 자료를 함께 관리하는 모노레포입니다.

| 구성 | 역할 | 실행 방식 |
| --- | --- | --- |
| 웹 편집기 | 영상 업로드·훅 선택·문구 편집·미리보기·내보내기 | 루트 웹앱을 Vercel에 배포 |
| AI 기획 서버 | Claude·Gemini로 기획 생성 및 비교, 제작 스펙 전달 | `planner-ai-sdk/` · 기본 포트 `8787` |
| 미디어 워커 | Google Gen AI SDK로 이미지·영상·음성 생성, 검수와 FFmpeg 조립, 작업 상태·파일 관리 | `production/` · 기본 포트 `8080` |
| 제작 도구·캠페인 | 훅 설계, 제작·검수 스크립트, 제품 정보·대본·타임라인 관리 | `skills/`, `campaigns/` |

웹 편집기와 기획 서버·미디어 워커는 각각 실행하는 구성입니다. 루트 웹앱을 배포해도 두 서버가 함께 실행되지는 않습니다.

### Blender와 Google Cloud

- **Blender**: 웹 편집기의 렌더 브리지는 사용자 PC의 `http://localhost:8000` 보조 서버에 연결합니다. Blender와 보조 서버가 필요하며, 보조 서버 실행 파일은 현재 이 저장소에 포함되어 있지 않습니다.
- **Google Flow**: 웹 편집기에서 프롬프트를 복사해 Flow로 이동하고, 생성한 영상을 다시 가져와 사용할 수 있습니다.
- **Google Cloud / Vertex AI**: 미디어 워커는 API 키 방식과 Vertex AI 인증 방식을 지원합니다. 프로젝트·리전·인증 설정과 Docker 실행 방법은 [워커 문서](production/README.md)를 참고하세요.

## 개발 시작하기

### 웹 편집기

Vercel 프로젝트의 루트를 이 저장소 최상위로 설정합니다. AI 기능을 사용하려면 Vercel 환경변수에 `GEMINI_API_KEY`를 설정합니다. `HOOKCUT_PASSWORD`는 웹 API의 접근 비밀번호 설정입니다.

`HookCut` 계열 코드 식별자와 환경변수 이름은 기존 구현에 사용되는 기술 명칭이며, 서비스명은 **냅다**입니다.

### AI 기획 서버·미디어 워커

아래 명령은 **Bash / WSL 기준**입니다. Python 3.11, `uv`, Node.js 20.6 이상과 npm을 준비하고, 실제 미디어 조립에는 FFmpeg가 필요합니다.

```bash
git clone https://github.com/muzuksazo/nepda.official.git
cd nepda.official
make setup-python
make setup-node
cp production/.env.example production/.env
cp planner-ai-sdk/.env.example planner-ai-sdk/.env
```

각 `.env`에 사용할 공급자의 API 키와 모델 설정을 입력합니다. 기획 서버에서 워커를 호출하려면 `WORKER_BASE_URL`을 워커 주소로 설정하고, 워커 인증을 사용한다면 `WORKER_BEARER_TOKEN`과 워커의 `API_BEARER_TOKEN`을 맞춥니다.

**터미널 1 — 미디어 워커**

```bash
cd production
.venv/bin/uvicorn app.server:app --host 127.0.0.1 --port 8080
```

**터미널 2 — AI 기획 서버**

```bash
cd planner-ai-sdk
node --env-file=.env --import tsx src/server.ts
```

기획 서버는 셸 환경변수를 읽으므로, 위 명령은 `--env-file`로 `.env`를 명시적으로 불러옵니다.

각 서버의 `GET /health`로 설정·연결 정보를 확인할 수 있습니다. 설치를 마친 뒤 저장소 루트에서 검증 명령을 실행합니다.

```bash
make test-all
make check-health
```

자세한 CLI·API 사용법은 [기획 서버 문서](planner-ai-sdk/README.md)와 [미디어 워커 문서](production/README.md)를 참고하세요.

## 저장소 구조

```text
index.html          웹 편집기
three_render.js     브라우저 3D 렌더링
render_bridge.js    로컬 Blender 보조 서버 연결
api/                Vercel 웹 API
planner-ai-sdk/     TypeScript · Vercel AI SDK 기획 서버
production/         Python · Google Gen AI SDK 미디어 워커
skills/             훅 설계·생성·조립·검수·커버 제작 도구
campaigns/          제품 정보·대본·제작 스펙·자막·검수 자료
Makefile            설치·개발 실행·검증 명령
vercel.json         웹앱 함수 설정
```

캠페인별 제품 정보는 `00_product_facts.md`, 제작 기준은 `05_ad_spec*.json` 등에서 관리합니다. 관련 자료는 각 캠페인 폴더에서 확인할 수 있습니다. 생성·조립·검수·커버 제작 도구는 [제작·검수 가이드](skills/shortform-ad-remix-director/SKILL.md)를 참고하세요.

## 제작 자료와 배포 정책

- API 키와 비밀번호는 환경변수로 관리합니다. `.env`와 실제 인증 정보는 저장소에 올리지 않습니다.
- 원본 촬영본(`source/`), AI 중간 클립(`clips/`), 최종 영상과 오디오 등은 `.gitignore`로 제외합니다. 저장소에는 제작 스펙·자막·검수 자료를 함께 관리합니다.
- `skills/`, `campaigns/`, `production/`, `planner-ai-sdk/`, `Makefile`은 `.vercelignore`에 따라 웹앱 배포 번들에서 제외합니다.
