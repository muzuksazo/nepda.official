# Shortform Ad Planner (`Vercel ai-sdk`, TypeScript)

`nepda.oficial` 모노레포에서 **Claude (`@ai-sdk/anthropic`) ↔ Gemini (`@ai-sdk/google`) 멀티 프로바이더 A/B 기획·검수**를 담당하는 TypeScript 패키지입니다.  
생성된 `05_ad_spec.json` 스펙은 [`../production/`](../production/README.md) (`google-genai` 이미지·영상·TTS + Gate A + FFmpeg 워커) HTTP API(`POST /v1/jobs`)로 직접 넘겨 렌더링합니다.

## 1. 설치 및 빌드

```bash
cd planner-ai-sdk
npm install
cp .env.example .env   # ANTHROPIC_API_KEY, GEMINI_API_KEY 설정
npm run typecheck
npm test
```

## 2. 주요 실행 명령

```bash
# 1) Claude vs Gemini A/B 동시 기획 비교
npm run compare -- \
  --project-id sponge-ab \
  --facts ../campaigns/pva-water-sponge-abc/00_product_facts.md \
  --source ../campaigns/pva-water-sponge-abc/source/sponge_04_wipe.mp4 \
  --style blender_clay_diorama

# 2) 단일 프로바이더로 스펙 생성 후 파일 저장
npm run plan -- \
  --provider anthropic \
  --project-id sponge-claude \
  --facts ../campaigns/pva-water-sponge-abc/00_product_facts.md \
  --out ./spec_claude.json

# 3) HTTP 컨트롤 서버 실행 (기본 127.0.0.1:8787 -> Worker 127.0.0.1:8080)
npm run serve
```

## 3. 엔드포인트
- `GET /health` — Claude / Gemini 키 설정 여부 및 워커 연결 대상 확인
- `POST /v1/plan` — 단일 프로바이더(`anthropic` | `google`) `05_ad_spec.json` 생성
- `POST /v1/compare` — Claude vs Gemini 동시 생성 및 Markdown 비교표 반환
- `POST /v1/plan-and-render` — AI SDK로 기획 생성 후 `production` 워커(`/v1/jobs`)에 인라인 스펙(`spec_data`) 전송
