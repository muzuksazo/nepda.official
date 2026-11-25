# 훅컷 (HookCut) & 숏폼 광고 스튜디오 모노레포

광고 영상 앞에 훅을 붙여 세로 숏폼(9:16)을 만드는 **HookCut 웹 프로토타입**과, 실물 기반 A/B/C 직교 숏폼 파이프라인(**스킬·CLI·캠페인 스펙 SSOT**)을 함께 관리하는 모노레포입니다.

## 1. HookCut 웹 프로토타입 (Vercel 루트 앱)
- 사이트: https://hookcut-sandy.vercel.app
- `index.html` · `three_render.js` · `render_bridge.js`: 브라우저에서 도는 편집 화면
- `api/`: Vercel 서버 함수. `GEMINI_API_KEY`, `HOOKCUT_PASSWORD` 환경 변수를 Vercel 설정에 넣어야 동작합니다. 키는 저장소에 올리지 마세요.
- 블렌더 렌더는 각자 PC의 로컬 서버가 필요합니다.

## 2. 숏폼 광고 스킬 & 파이프라인 (`skills/`, Vercel 빌드 제외)
- [`skills/shortform-ad-hooks-blueprint/`](skills/shortform-ad-hooks-blueprint/SKILL.md): 3-장르 직교 훅(`A` 무맥락 장르 탈취 반전 · `B` 50% 맥락 오차 정보성 훅 · `C` 실용 직격) 및 커버 디자인 설계 스킬
- [`skills/shortform-ad-remix-director/`](skills/shortform-ad-remix-director/SKILL.md): Google Flow 자동화(`flow_automator.py`), 3-버스 `-14.0 LUFS` 조립(`ad_remix_assemble.py`), 13항목 Gate A & 교차 리스킨 방지 린터(`ad_gate_a_lint.py`), `@picturebooksub` 기준 커버 빌더(`ad_thumbnail_builder.py`) 및 단위 테스트(`test_shortform_ad_tools.py`)

## 3. 캠페인 SSOT (`campaigns/`, Vercel 빌드 제외)
각 캠페인의 제품 팩트 원장(`00_product_facts.md`), 대본(`01_abc_script.md`), 타임라인·VO 스펙(`05_ad_spec*.json`, `audio/vo_*.json`), 자막(`.srt`), 커버/QA 검수 시트(`thumbnails_sheet.png`, `qa_*_strip.png`)를 버전 관리합니다.

## 4. 프로덕션 워커 & API (`production/`, Vercel 빌드 제외)
[`production/README.md`](production/README.md): Chrome Flow 자동화(`flow_automator.py`) 대신 공식 `google-genai>=3.0.0` SDK(`gemini-3.5-flash` · `gemini-nano-banana-2.1` · `gemini-omni-1.2-flash` · `gemini-3.8-flash-tts`)와 FastAPI · Docker FFmpeg 워커 · SQLite 상태 저장소 · S3/R2 스토리지를 묶은 프로덕션 실행 패키지입니다.

> **미디어 파일 정책**: 대용량 원본 촬영본(`source/`), AI 중간 클립(`clips/`), 최종 렌더링 영상(`final/*.mp4`) 및 `.wav`/`.mov` 바이너리는 `.gitignore` 로 제외되어 있으며, `.vercelignore` 를 통해 `skills/` 와 `campaigns/` 와 `production/` 는 Vercel 웹앱 배포 번들에 포함되지 않습니다.
