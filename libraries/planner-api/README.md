# 냅다 플래너 API·라이브러리

기존 `planner-ai-sdk/`를 `libraries/planner-api/`로 옮긴 npm 워크스페이스입니다. Claude·Gemini 기획 생성·비교, 제작 스키마, HTTP API, 백엔드 작업 전달을 담당합니다.

`src/index.ts`에서 기획·스키마·설정·워커 연결·서버 함수를 내보냅니다. 패키지 이름은 `@napda/planner-api`입니다.

## 설치·실행

저장소 루트에서 실행합니다.

```bash
npm ci
cp libraries/planner-api/.env.example libraries/planner-api/.env
npm run typecheck
npm run build
node --env-file=libraries/planner-api/.env --import tsx libraries/planner-api/src/server.ts
```

환경 파일에 사용할 공급자의 API 키와 `WORKER_BASE_URL`을 설정합니다. 기본 플래너 포트는 `8787`, 백엔드 주소는 `http://127.0.0.1:8080`입니다. 워커 인증을 사용하면 `WORKER_BEARER_TOKEN`을 백엔드의 `API_BEARER_TOKEN`과 맞춥니다.

| API | 역할 |
| --- | --- |
| `GET /health` | 공급자 설정·워커 주소 확인 |
| `POST /v1/plan` | 단일 공급자 기획 생성 |
| `POST /v1/compare` | Claude·Gemini 기획 비교 |
| `POST /v1/plan-and-render` | 기획 후 백엔드 `POST /v1/jobs`로 전달 |

## CLI

저장소 루트를 현재 디렉터리로 두고 실행하면 캠페인 상대 경로를 그대로 사용할 수 있습니다.

```bash
node --env-file=libraries/planner-api/.env --import tsx libraries/planner-api/src/cli.ts plan \
  --provider anthropic \
  --project-id sponge-claude \
  --facts prototypes/campaigns/pva-water-sponge-abc/00_product_facts.md \
  --out spec_claude.json
```

테스트는 루트 `tests/planning/`, `tests/infrastructure/`, `tests/integration/`에 모았습니다. `npm test` 또는 이 패키지의 `npm test`로 실행합니다. [테스트 기준](../../tests/README.md)을 참고하세요.
