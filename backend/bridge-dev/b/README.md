# B 훅 작업자 가이드 — 제품을 약하게 짐작하는 정보성 훅

## 이 유형의 정의

저장소 README의 교체 테스트 기준: **B = 제품을 약하게 짐작할 수 있는 훅. 제품으로 넘어가는 장면을 수정하면 다른 제품 광고에 연결할 수 있음.** 어긋난 정보로 시작해 브리지를 거쳐 반전 장면에서 제품이 탁 치는 구조입니다. 훅만 보고 제품을 살짝 짐작할 수 있으면 B, 짐작하기 어려우면 A입니다.

## 이 작업자가 받는 요청

공개 API 요청은 모두 백엔드가 받고, 백엔드는 프로젝트의 `selected_types`가 `["B"]`이면 **이 유형 작업자 코드**를 호출합니다. 작업자 코드로 들어오는 경우는 세 가지입니다.

| 들어오는 공개 API | 작업자가 하는 일 | 작업자가 반환 |
| --- | --- | --- |
| `POST /v1/projects/{id}/scenarios` | 시나리오 `count`개 생성 | `ScenarioItem[]` (`type: "B"`, `round`) |
| `POST /v1/projects/{id}/scenarios/{sid}/storyboard` | 장면별 콘티 이미지 생성 | `StoryboardFrame[]` |
| `POST /v1/projects/{id}/hooks` | 선택된 시나리오로 훅 영상 + TTS 생성 | 영상·음성·자막 파일(상태는 폴링 응답으로) |

시나리오 생성 시 작업자 코드가 받는 입력은 아래와 같습니다. 공개 API가 아니라 `POST /scenarios` 처리 중의 **내부 호출(제안 인터페이스)**이며, 필드 이름은 백엔드 구현에서 확정합니다. 예시: [`examples/01_worker-input.scenarios.json`](examples/01_worker-input.scenarios.json)

| 필드 | 설명 |
| --- | --- |
| `hook_type` | `"B"` 고정 |
| `product_info` | `ProductInput`(`name`, `category`, `verified_facts[]`, 선택 `price_or_offer`, `target_audience`). **`verified_facts`에 없는 사실은 쓰지 않는다** |
| `project_id`, `round`, `count` | 몇 번째 뽑기인지와 만들 개수 |
| `previous_scenarios[]` | 앞선 회차 시나리오. 더 뽑을 때 **같은 소재·구조를 반복하지 않기 위해** 참고 |

콘티와 훅 단계에서는 저장된 `ScenarioItem`(`scenario_id`로 조회)과 `tts` 옵션만 받으면 됩니다.

## 시나리오 생성 시 지켜야 할 유형 규칙

기준 문서: [`skills/shortform-ad-hooks-blueprint/SKILL.md`](../../../skills/shortform-ad-hooks-blueprint/SKILL.md)의 Track B(`B_info_hook_offset`)와 `skills/b-info-hook/SKILL.md`(현재 저장소에는 폴더가 없음. 있으면 함께 참고). 아래는 요약이며 충돌하면 blueprint가 우선입니다.

- **길이: B 훅은 15~20초** 안에서 내용에 맞게 정합니다. 공통 문서(`../api-guide.md`, `../PRD.md`)의 "훅 15초 이하"와 다른 B 전용 기준이며, 공통 기준으로 할지는 팀 합의가 필요합니다.

- **앵커 정하기.** 제품 핵심 기능 + 숫자 하나. 뽀모도로 타이머라면 "남은 시간이 빨간 부채꼴 면적으로 보인다(60분 = 360도)".
- **시작 단어와 앵커의 유사도 `hook_similarity_score` = 0.40~0.60.** 0.7 이상은 시작부터 광고 냄새가 나서 금지, 0.3 미만은 브리지가 억지스러워 금지. 값을 `ad_spec`에 기록한다.
- **시작은 제품과 무관한 놀라운 사실 + 숫자.** 시작 장면에 제품군 어휘(타이머, 시계 등)와 제품명을 쓰지 않는다. PAS형 도입("~하는 이유", "쏟아본 적", "바꿨어요")도 금지.
- **브리지 1~2개.** 인접 단어 유사도는 0.70 이상, 장면이 갈수록 앵커와의 유사도가 올라간다(예: 0.45 → 0.65 → 0.8). 같은 단위의 숫자 실(예: 도(°))이 이어지면 가장 좋다.
- **반전 장면에서 제품명이 처음 등장**하고 실물로 증명한다.
- **나레이션은 "~습니다"체**의 차분한 정보체. 자막은 짧은 구어, 한 줄 8자 안팎, 2줄 이내, 숫자는 아라비아 숫자(나레이션은 한글로 읽히게). 스펙 배너(`header_tag`)는 2개 이하.
- 사실은 출처를 확인할 수 있는 것만 쓴다. 검증 안 된 사실은 `fact_sources[].status`에 표시하고 "~라고 합니다"로 말한다. (이 가이드 예시의 자전 속도 수치는 예시이므로 실제 사용 전 출처 확인이 필요하다.)
- 권장 `ad_spec` 키: `track_archetype: "B_info_hook_offset"`, `hook_similarity_score`, `anchor`, `bridge_path[]`(`word`, `sim_to_anchor`), `adjacent_min_sim`, `number_thread`, `product_first_mention_beat`, `visual_style`(기본 `blender_3d_cutaway`), `fact_sources[]`.

## 반환해야 할 응답 형태

필드 정의는 [`../api-guide.md`](../api-guide.md)와 [`openapi.json`](../../../contracts/openapi.json)이 기준입니다. 이 유형의 예시:

| 단계 | 반환 | 예시 |
| --- | --- | --- |
| 시나리오 | `{ round, scenarios[] }` — 각 `ScenarioItem`: `scenario_id`, `round`, `type: "B"`, `hook_title`, `hook_duration_sec`(B는 15~20), `body_duration_sec`, `replacement_test_note`, `beats[]`(`order`, `role`, `duration_sec`, `visual`, `narration`, `caption`), `ad_spec` | [`examples/02_scenarios.response.json`](examples/02_scenarios.response.json) |
| 콘티 | `{ frames[] }` — `beat_order`(= `beats[].order`), `image_url`, `caption` | [`examples/03_storyboard.response.json`](examples/03_storyboard.response.json) |
| 훅(폴링) | `{ status, files{hook_video, tts_audio, subtitles_srt, scenario_json, storyboard_images[]}, output_dir }` | [`examples/04_hook-status.done.json`](examples/04_hook-status.done.json) |

공통 규칙: 장면 길이 합 = `hook_duration_sec`, 장면 3~5개, `replacement_test_note`에는 교체 테스트 판정 근거를 한 줄로 씁니다. `ad_spec`에는 아래 "유형 규칙"에서 정한 키를 넣습니다(유형 규칙 검증과 이후 린트에 쓰이는 값).

## 결과 파일 저장 위치와 이름

훅이 `done`이 되면 아래 폴더에 저장합니다(`OUTPUT_DIR` 기본값은 미정, 여기서는 `output/`).

```text
OUTPUT_DIR/{project_id}/{hook_id}/
├── hook.mp4              훅 영상 (B는 15~20초, 9:16)
├── tts.mp3               나레이션 음성 (beats[].narration)
├── hook.srt              자막 (beats[].caption, 장면 시작·끝 시각 기준)
├── scenario.json         이 훅에 쓴 ScenarioItem 그대로 (b/examples/05_saved-scenario.json 참고)
└── storyboard_01.png …   콘티 이미지 (2자리 번호 = beat_order)
```

회차가 달라지면 `hook_id`가 다른 새 폴더가 생기고 기존 폴더는 지우지 않습니다.

## B 시나리오 작업자 코드 (FR-003, 로컬 실행)

시나리오 생성(+장면별 3D 명세)까지 구현되어 있습니다. 콘티 이미지(FR-004)와 훅 영상 렌더·TTS(FR-005)는 아직 없고, 3D 명세를 `video_test/pipeline` 입력(plan.json)으로 내보내는 데까지 합니다.
Vercel AI SDK(`ai`, `@ai-sdk/anthropic`)로 Claude를 호출합니다.

```text
1. 유사도 검색 (src/ideate.ts)
   앵커 선정 + 마인드맵(관점 4개, 단어 약 100개)
   → 단어마다 info(정보 가치)·앵커 유사도 채점
   → 시작 후보(0.40~0.60)·브리지 후보끼리 인접 유사도 채점
   → 경로 탐색: 시작 → 브리지 1~2개, 유사도 상승, 인접 0.70 이상, 마지막 브리지 0.70 이상
     점수 = info(시작) × 인접 최소 × (1 − 시작 유사도), 시작이 서로 다른 경로를 count개 고름
2. 시나리오 + 3D 장면 생성 (src/generate.ts) — 고른 경로를 그대로 쓰게 하고, 경로 값은 검색 결과로 덮어씀
3. 규칙 검사 (src/check.ts) — 위반이 있으면 위반 내용을 붙여 한 번 더 생성
4. 저장 — 회차 기록, 리포트(HTML), pipeline plan
```

| 파일 | 역할 |
| --- | --- |
| `src/schema.ts` | 입력(01_worker-input)·출력(ScenarioItem, 장면별 `scene3d`) zod 스키마 |
| `src/ideate.ts` | 유사도 검색·경로 탐색 (`video_test/pipeline/scripts/ideate.mjs`를 옮기고 경로 탐색 추가) |
| `src/prompt.ts` | B 규칙 + 3D 장면 규칙을 담은 프롬프트 |
| `src/generate.ts` | `generateScenarios(input)` — 백엔드가 import해서 부를 함수 |
| `src/check.ts` | 규칙 검사 (유사도, 브리지, 금지어, "~습니다"체, 자막, 길이 15~20초, 3D 움직임·오브젝트 수·금지 요소 등) |
| `src/cost.ts` | 단계별 토큰·비용(USD) 계산 |
| `src/report.ts` | 프로젝트 리포트 HTML (회차·시나리오·3D 명세 접기/펴기) |
| `src/pipeline-plan.ts` | 시나리오 → `video_test/pipeline` 의 plan.json 형식 |

```bash
cd backend/bridge-dev/b
npm install
cp .env.example .env        # ANTHROPIC_API_KEY 입력 (.env는 커밋되지 않음)

npm test                                                         # 가짜 모델로 전체 흐름 확인 (API 호출 없음)
npm run check -- examples/02_scenarios.response.json             # 규칙 검사만 (API 호출 없음)
npm run scenarios -- examples/01_worker-input.scenarios.json     # 1회차 생성 (Claude API 과금)
npm run scenarios -- examples/01_worker-input.scenarios.json --next   # 다음 회차 (앞선 시작 소재 제외)
npm run scenarios -- examples/01_worker-input.scenarios.json --next --cuts   # 다음 회차 + 장면 컷 이미지
npm run cuts -- proj_demo01 3                                    # 이미 만든 3회차의 컷 이미지만 렌더
npm run video -- proj_demo01 3                                   # 3회차 훅 영상(mp4) — 컷 단계 장면 코드 + TTS, Claude 호출 없음
npm run report -- proj_demo01                                    # 리포트만 다시 만들기
npx tsx test/cuts-render.ts                                      # 가짜 모델로 컷 렌더 경로 확인 (API 호출 없음, pipeline 필요)
```

결과 (`out/`은 커밋 안 함):

```text
out/{project_id}/
├── report.html                       회차별로 접고 펴는 리포트 (최신 회차가 위·펼침), 단계별 토큰·비용, 유사도 검색 결과
├── round-{n}.json                    회차 기록 (응답 + 검사 + 유사도 검색 + 비용)
└── round-{n}/
    ├── {scenario_id}.plan.json       video_test/pipeline 입력 (scene.visual = 3D 명세, scene.say = 나레이션)
    └── cuts/{scenario_id}/           컷 이미지 (--cuts / npm run cuts)
        ├── beat{n}_f{frame}.png      장면마다 처음·중간·끝 프레임 3장 (1080x1920, 자막·카운터 포함)
        └── beat{n}.tsx               그 장면의 React Three Fiber 코드
```

### 컷 이미지 (`--cuts`, `npm run cuts`)

- 장면마다 Claude가 3D 명세를 React Three Fiber 코드로 쓰고(장면끼리 동시에), 금지 패턴·타입 검사를 통과하지 못하면 오류를 붙여 최대 3번 다시 씁니다. 끝내 실패한 장면은 기본 도형으로 렌더하고 리포트에 표시합니다.
- 렌더는 **`video_test/pipeline`의 Remotion 프로젝트**(`SceneTest` 컴포지션)를 빌려 씁니다. 다른 위치면 `B_PIPELINE_DIR`로 지정합니다. 렌더하는 동안만 `pipeline/src/generated/`를 쓰고 끝나면 원래대로 되돌립니다. pipeline은 팀 저장소 밖이라 **이 단계는 pipeline 폴더가 있는 컴퓨터에서만** 됩니다.
- 모델은 `B_SCENE_MODEL`(없으면 `B_MODEL`), 재시도 횟수는 `B_SCENE_MAX_TRIES`(기본 3).
- 실측(3회차, 장면 4개, 모두 1차 통과): 비용 $0.37, 소요 약 1분 20초(코드 생성 최장 54초 + 타입 검사 3초 + 번들·렌더 23초). 처음 렌더할 때 Remotion이 headless Chrome(약 131MB)을 내려받습니다.
- 리포트: 시나리오 위쪽에 장면별 중간 프레임 스트립, 장면 표에 3컷 썸네일과 코드 링크. `index.html` "기록 불러오기"에서는 콘티 자리에 컷이 보입니다(#2 이후 버전).
- 소요 시간 합계에서 동시에 실행된 단계(장면별 코드 생성)는 가장 긴 것만 더합니다.

### 훅 영상 (`npm run video`)

- 컷 단계에서 저장한 장면 코드(`cuts/<scenario_id>/beat{n}.tsx`)를 그대로 쓰고, `video_test/pipeline`의 `scripts/tts.mjs`(Edge TTS, ko-KR-SunHiNeural +25%)로 나레이션을 만든 뒤 Remotion `HookVideo`로 **훅만** 렌더합니다(본편·음악 없음). Claude 호출이 없어 비용은 $0입니다.
- 음성이 장면보다 길면 장면이 늘어납니다(+0.25초). 장면별 계획/최종 길이는 리포트에 나옵니다.
- 결과: `out/<project_id>/round-{n}/video/hook_<scenario_id>.mp4`(1080x1920, 30fps, AAC 음성)와 장면별 음성 wav. 리포트에서 바로 재생됩니다.
- 실측(3회차, 15초 훅): TTS 25초 + 번들·렌더 27초 = 52초. 한 회차를 시나리오 → 컷 → 영상까지 하면 약 6분, 약 $1입니다.
- 렌더하는 동안만 `pipeline/src/generated/`와 `pipeline/public/tts/`를 쓰고 끝나면 원래대로 되돌립니다.

- 모델은 `.env`의 `B_MODEL`(기본 `claude-opus-5-5`). 유사도 검색 단계만 바꾸려면 `B_IDEA_MODEL`. 원화 표시는 `B_USD_KRW`(환율)를 넣었을 때만.
- 비용은 표준 단가로 계산한 추정치입니다(캐시 할인 미반영). 실제 청구액은 Claude Console의 Usage에서 확인합니다. 참고: 2회차 실측 약 $0.49(호출 5번, 입력 1.6만·출력 2.1만 토큰).
- 검사 결과의 ✗는 규칙 위반(종료 코드 2), △는 사람이 볼 경고(출처 확인 필요, 긴 자막 줄 등)입니다.
- 유사도 값은 임베딩이 아니라 Claude가 같은 기준표로 한꺼번에 매긴 추정치입니다.
- 시작 단어는 앵커 유사도 0.40~0.60이면서 **용도 영역 유사도 0.35 이하**여야 합니다. 용도 영역(usage_domains)은 제품을 언제·무엇에 쓰는지와 그 제품군의 역사·기법 유래까지 포함하며, 아이디어 단계에서 Claude가 제품마다 정합니다.
- 반전 나레이션은 한 문장, 공백 제외 35자 이내(핵심 특징 하나)여야 검사를 통과합니다.
- `index.html`에서 보기: "기록 불러오기"로 `out/<project_id>/round-N.json`을 고르면 결과 목록에 B 작업자 CLI 기록(비용·소요 시간·규칙 검사 포함)으로 들어갑니다. 기록은 그 브라우저에 보관됩니다.

## index.html로 테스트하기

1. `python -m http.server 5500 --directory backend/bridge-dev` 후 `http://127.0.0.1:5500/`를 엽니다(파일로 열어도 됩니다).
2. **훅 유형**에서 **B**를 선택합니다. 제품 정보는 뽀모도로 타이머가 미리 채워져 있습니다.
3. Mock으로 흐름을 먼저 확인합니다: "처음부터 끝까지(1회)" 또는 "시나리오 더 뽑기 n회". 오른쪽 로그에서 요청 body와 응답 형태를 봅니다.
4. 내 코드로 확인: Mock을 끄고 Base URL을 백엔드로, Bearer 토큰에 `python backend/bridge-dev/dev_token.py --user worker-b` 결과를 넣고 같은 버튼을 누릅니다. 응답이 위 예시와 다르면 로그의 curl 복사로 재현합니다. CORS와 인증은 [`../README.md`](../README.md)를 참고하세요.
5. 끝나면 "결과 저장"으로 회차별 결과를 JSON으로 받아 예시와 비교합니다.

## 저장소의 B 캠페인 예시

- `prototypes/campaigns/digimore-timer-abc/05_ad_spec_B.json` (다큐 트위스트), `05_ad_spec_B_subtle.json` (은근한 분위기)
- 같은 폴더의 `audio/vo_plan_B.json`, `final/ad_B_docu_twist.srt`, `final/ad_B_subtle_vibe.srt`
- `prototypes/campaigns/piev-airwasher-abc/01_abc_script.md`, `pva-water-sponge-abc/01_abc_script.md`: 유형을 `b-info-hook`으로 기록한 다른 제품 예(시작 유사도 0.45 → 브리지 0.70 → 제품 반전)
- 참고: 기존 타이머 B안은 시작부터 시간 이야기라 유사도가 높게(약 0.75) 평가된 사례입니다. 이 가이드 예시(지구 자전 → 15도 → 부채꼴 → 제품)가 새 기준에 맞춘 것입니다.
