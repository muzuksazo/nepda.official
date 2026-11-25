# 냅다 (NAPDA)

**셀러·소상공인을 위한 훅 기획·제작 웹 서비스**

냅다는 제품 정보를 바탕으로 광고의 첫 장면인 **훅**을 기획하고, 촬영 가이드에 따라 준비한 본편과 연결해 **30초 안팎의 인스타그램 릴스 영상과 썸네일**을 만드는 것을 목표로 합니다. A·B·C 유형의 시안을 글과 이미지 콘티로 먼저 살펴보고, 원하는 방향을 골라 제작하는 **모바일 우선 웹 서비스**입니다.

[제품 요구사항(PRD)](https://climbing-domain-5ca.notion.site/PRD-v0-1-NAPDA-4237f7364375801ebd14d6f65ccd8aa1) · [기존 웹 프로토타입](https://hookcut-sandy.vercel.app)

> 제품 방향은 2026년 11월 25일 작성된 PRD의 본문 v0.2 초안을 기준으로 합니다. 아래의 **확정**은 회의에서 합의한 요구사항 상태이며, 구현 완료를 뜻하지 않습니다. 현재 코드는 [현재 구현과 개발 구성](#현재-구현과-개발-구성)에서 안내합니다.

## 해결하려는 문제와 사용자

광고처럼 느껴지는 첫 몇 초에 시청자가 영상을 넘기는 상황에서, 셀러·소상공인은 관심을 끌 훅을 꾸준히 기획할 시간·비용·제작 역량이 부족합니다. 냅다는 제품 정보를 바탕으로 시안을 단계별로 검토하고, 촬영할 장면을 안내하는 흐름을 제안합니다.

| 항목 | MVP 기준 |
| --- | --- |
| 사용자 | 숏폼 광고를 직접 만드는 셀러·소상공인 |
| 제품 카테고리 | 자취·주방·문구 |
| 게시 플랫폼 | 인스타그램 릴스 |
| 서비스 형태 | 모바일 화면을 우선하는 웹 서비스 |

시안 확인을 통해 원치 않는 영상 생성에 드는 비용을 줄일 수 있다는 가치는 아직 검증할 가설입니다.

## MVP 사용자 흐름

우선 완성할 흐름은 **가이드 먼저형**입니다. 다음 순서는 PRD에서 단계별 시안과 촬영 가이드를 연결한 작업 가설이며, 세부 생성 시점은 추가 결정이 필요합니다.

1. **제품 정보 입력** — 광고할 제품의 정보를 입력합니다.
2. **A·B·C 유형 선택** — 유형 설명과 예시를 보고 하나 이상을 고릅니다.
3. **글 시나리오 확인** — 훅의 이야기와 연출 방향을 검토합니다.
4. **이미지 콘티 확인** — 원하면 ‘그림으로 보기’로 장면 구성을 확인합니다.
5. **촬영 가이드 확인** — 촬영할 장면과 장면별 길이를 안내받습니다.
6. **직접 촬영** — 서비스 밖에서 가이드에 맞춰 본편을 촬영합니다.
7. **영상 업로드** — 촬영한 영상을 서비스에 올립니다.
8. **훅 생성·본편 연결** — 30초 안팎의 결과 영상을 재생해 확인합니다.
9. **썸네일·영상 내려받기** — 게시에 사용할 파일을 저장합니다.

시안 검토가 필요 없는 사용자를 위해 중간 시안을 건너뛰고 영상까지 만드는 경로도 요구사항에 포함합니다. 촬영 후 돌아왔을 때의 이어하기 방식은 제안 단계입니다.

### A·B·C는 ‘교체 테스트’로 구분합니다

유형은 훅을 다른 제품 광고에 옮겨 붙일 수 있는 정도로 판단합니다.

| 유형 | 제품과의 관계 | 교체 테스트 |
| --- | --- | --- |
| A | 제품과 무관한 훅 | 훅을 그대로 다른 제품 광고에 연결할 수 있음 |
| B | 제품을 약하게 짐작할 수 있는 훅 | 제품으로 넘어가는 장면을 수정하면 다른 제품 광고에 연결할 수 있음 |
| C | 특정 제품과 직접 연결된 훅 | 다른 제품 광고에 옮겨 붙이기 어려움 |

훅만 보고 제품을 살짝 짐작할 수 있으면 B, 짐작하기 어려우면 A로 구분합니다. B에서 허용할 전환 장면의 수정 범위는 미정입니다. 여러 유형을 검토할 수 있지만, **A·B·C 세 편을 모두 영상으로 생성하는 방식은 이번 범위에서 제외**합니다.

## 기능 범위와 상태

| 기능 | PRD 상태와 남은 결정 |
| --- | --- |
| 제품 정보 입력·유형 안내와 선택 | 확정 · 필수 입력 항목은 미정 |
| 글 시나리오·선택형 이미지 콘티 | 확정 · 글을 선택한 유형만 만들지, 세 유형 모두 만들지는 미정 |
| 중간 시안을 건너뛰고 영상까지 생성 | 확정 |
| 촬영 가이드 | 확정 · 장면과 길이 등 구체적인 안내 내용은 제안 |
| 원본 업로드·훅 생성·본편 연결 | 확정 · 업로드 제한과 영상 생성 방식은 미정 |
| 익숙한 숏폼 TTS 목소리 | 방향 확정 · 공급자와 도구는 미정 |
| 결과 재생·영상과 썸네일 내려받기 | 확정 · 썸네일 배경 생성과 글자 수정은 제안 |

- **제안**: 이어하기, 하루 생성 횟수 제한, 내려받기 화면의 AI 라벨 안내.
- **보류**: 업로드 먼저형 흐름. 가이드 먼저형을 완성한 뒤 시간이 남으면 추가합니다.
- **후속 검토**: 캡션 자동 작성, 성과 리포트, 유튜브용 썸네일 규격.
- **제외**: 결제, 인스타그램 자동 게시, 네이티브 앱, 파인튜닝 모델, 기존 인기 영상 재가공.

## 제작 방식과 검증 목표

**최종 영상 생성 방식은 아직 정하지 않았습니다.** 생성형 영상 모델(Google Flow 등)과 Remotion·Three.js를 후보로 두고 품질, 생성 원가와 처리 시간을 비교합니다. Blender와 영상 모델을 함께 쓰는 구성은 현재 PRD에서 잠정 제외한 안입니다.

내레이션은 숏폼에서 익숙한 TTS 목소리를 사용하는 방향이며, 공급자별 비용과 이용 조건을 확인한 뒤 도구를 결정합니다.

| 항목 | 목표와 측정 상태 |
| --- | --- |
| 전체 영상 길이 | 30초 안팎 |
| 영상 한 편 생성 원가 | 5,100원 이하의 임시 상한 · 실측 후 재검토 |
| 생성 시간 | 실험에서 측정 · 목표값 미정 |
| 노출·클릭 성과 | 발표 전에는 측정하지 않음 |
| 데모 완주 | 제품 정보 입력부터 내려받기까지 1회 완주 · 제안 |

5,100원은 검증된 실제 단가나 판매 가격이 아닙니다. 글·콘티·썸네일·목소리 비용을 원가 상한에 포함할지는 추가 결정이 필요합니다.

### 추가로 결정할 항목

- 영상 생성 도구와 훅 영상의 생성 시점.
- 훅 길이와 본편의 길이 비율.
- 단계별 크레딧 표시·차등 적용 범위와 결제 제외 방침의 정합성.
- 업로드 영상의 길이·용량 상한, 가이드와 다른 영상의 처리 방식.
- 촬영 후 복귀 방법, 데이터 보관 위치·기간, 생성 실패·재시도·화면 이탈 시 처리.

## 폴더 구조

```text
apps/                       프로덕션 앱
  frontend/                 PRD 가이드 먼저형 UI 개발 위치
  backend/                  FastAPI API·미디어 워커
libraries/                  재사용 API·라이브러리
  planner-api/              TypeScript 기획 API·스키마·워커 연결
  media-tools/              분석·검수·음성·조립·썸네일 CLI
prototypes/                 기존 프로토타입·제작 실험
  hookcut/                  업로드 먼저형 웹 화면·렌더링·API 구현
  campaigns/                제품 정보·대본·스펙·검수 자료
tests/                      PRD 기능·사용자 흐름별 테스트
  product_info/             제품 정보
  planning/                 A·B·C 선택·시나리오·기획
  storyboards/              이미지 콘티
  filming_guide/            촬영 가이드
  uploads/                  원본 업로드·분석
  generation/               생성·합치기·예산·재시도
  narration/                내레이션·음성
  delivery/                 결과·썸네일·내려받기
  workflow/                 이어하기·전체 흐름
  credits/                  미정 크레딧 정책
  infrastructure/           설정·인증·공통 실행 경로
  integration/              플래너→백엔드·조립 통합 검증
  prototypes/               기존 실험·배포 호환 검증
  support/                  공통 픽스처·모의 공급자
skills/                     기획·제작 지침
scripts/                    루트 빌드·테스트 실행기
api/                        기존 Vercel URL 호환 진입점
Makefile                    설치·개발·검증 명령
vercel.json                 기존 웹 프로토타입 배포 설정
```

[앱 구성](apps/README.md) · [공용 라이브러리](libraries/README.md) · [프로토타입](prototypes/README.md) · [PRD별 테스트](tests/README.md)

## 현재 구현과 개발 구성

기존 업로드 먼저형 웹앱은 `prototypes/hookcut/`로 모았습니다. `apps/backend/`에는 기존 production 워커를 옮겼고, `apps/frontend/`는 PRD의 가이드 먼저형 UI를 개발할 위치로 분리했습니다. 가이드 먼저형 프론트엔드는 아직 구현되어 있지 않습니다.

| 구성 | 현재 역할 | 실행 위치 |
| --- | --- | --- |
| 프로덕션 프론트엔드 | PRD 기반 UI 개발 위치 | `apps/frontend/` |
| 백엔드 | 작업 API·저장소·생성·검수·조립 | `apps/backend/` · `8080` |
| 플래너 API·라이브러리 | Claude·Gemini 기획·비교·스펙·워커 연결 | `libraries/planner-api/` · `8787` |
| 미디어 도구 | 분석·검수·음성·영상·썸네일 CLI | `libraries/media-tools/` |
| 기존 웹 프로토타입 | 업로드 먼저형 편집·브라우저 렌더·Blender 연결 | `prototypes/hookcut/` |

기존 Blender 렌더 브리지는 `http://localhost:8000`의 별도 보조 서버를 사용합니다. 보조 서버는 저장소에 포함되어 있지 않습니다. 이 연결은 PRD에서 확정한 생성 방식이 아닙니다.

## 개발 시작하기

Python 3.11 이상, uv, Node.js 20.6 이상, npm, FFmpeg·FFprobe를 준비합니다. 아래는 저장소 루트·Bash/WSL 기준입니다.

```bash
git clone https://github.com/muzuksazo/nepda.official.git
cd nepda.official
uv venv .venv --python 3.12
uv pip install --python .venv/bin/python -r apps/backend/requirements.txt
npm ci
cp apps/backend/.env.example apps/backend/.env
cp libraries/planner-api/.env.example libraries/planner-api/.env
```

Windows PowerShell에서는 Python 실행 경로를 `.venv\Scripts\python.exe`로 바꾸고, 환경 파일은 다음 명령으로 준비합니다.

```powershell
Copy-Item apps/backend/.env.example apps/backend/.env
Copy-Item libraries/planner-api/.env.example libraries/planner-api/.env
```

각 환경 파일에 사용할 공급자의 키와 설정을 입력합니다. 플래너의 `WORKER_BASE_URL`을 백엔드 주소로 지정하고, 인증을 사용하면 `WORKER_BEARER_TOKEN`과 백엔드의 `API_BEARER_TOKEN`을 맞춥니다.

**터미널 1 — 백엔드**

```bash
.venv/bin/python -m uvicorn app.server:app --app-dir apps/backend --host 127.0.0.1 --port 8080
```

**터미널 2 — 플래너 API**

```bash
node --env-file=libraries/planner-api/.env --import tsx libraries/planner-api/src/server.ts
```

자세한 사용법은 [백엔드 문서](apps/backend/README.md)와 [플래너 문서](libraries/planner-api/README.md)를 참고하세요.

### 검증

```bash
.venv/bin/python scripts/test-python.py
npm test
npm run typecheck
npm run build
node scripts/build-prototype.mjs
```

Bash/WSL 또는 Make가 설치된 환경에서는 `make setup-python`, `make setup-node`, `make test-all`, `make dev-worker`, `make dev-planner`도 사용할 수 있습니다.

기존 테스트는 PRD 영역에 맞게 재배치했습니다. 미구현·미정 기능은 수용 기준을 문서로 남기며, 실행 테스트가 있는 영역과 구분합니다. [범위와 상태](tests/README.md)를 확인하세요.

## 프로토타입 배포와 제작 자료

기존 Vercel 프로젝트는 저장소 루트를 유지합니다. 정적 빌드는 `prototypes/hookcut/`의 웹 파일 3개를 `dist/prototype/`에 복사하고, 루트 `api/`는 기존 API 주소를 프로토타입 구현에 연결합니다. `GEMINI_API_KEY`, `HOOKCUT_PASSWORD`는 기존 웹 API 설정 이름입니다.

원본 영상·중간 클립·최종 영상·오디오·작업 DB·환경 파일은 `.gitignore`로 제외합니다. 캠페인 스펙·자막·검수 이미지는 `prototypes/campaigns/`에서 관리합니다. 프로덕션 앱·라이브러리·테스트·캠페인 자료는 기존 웹 프로토타입 배포 번들에서 제외합니다.
