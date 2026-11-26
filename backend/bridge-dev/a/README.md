# A 훅 작업자 가이드 — 제품과 무관한 훅

## 이 유형의 정의

저장소 README의 교체 테스트 기준: **A = 제품과 무관한 훅. 훅을 그대로 다른 제품 광고에 연결할 수 있음.** 훅만 보고 제품을 짐작하기 어려워야 하고, 제품은 마지막에 담백하게 나옵니다.

## 이 작업자가 받는 요청

공개 API 요청은 모두 백엔드가 받고, 백엔드는 프로젝트의 `selected_types`가 `["A"]`이면 **이 유형 작업자 코드**를 호출합니다. 작업자 코드로 들어오는 경우는 세 가지입니다.

| 들어오는 공개 API | 작업자가 하는 일 | 작업자가 반환 |
| --- | --- | --- |
| `POST /v1/projects/{id}/scenarios` | 시나리오 `count`개 생성 | `ScenarioItem[]` (`type: "A"`, `round`) |
| `POST /v1/projects/{id}/scenarios/{sid}/storyboard` | 장면별 콘티 이미지 생성 | `StoryboardFrame[]` |
| `POST /v1/projects/{id}/hooks` | 선택된 시나리오로 훅 영상 + TTS 생성 | 영상·음성·자막 파일(상태는 폴링 응답으로) |

시나리오 생성 시 작업자 코드가 받는 입력은 아래와 같습니다. 공개 API가 아니라 `POST /scenarios` 처리 중의 **내부 호출(제안 인터페이스)**이며, 필드 이름은 백엔드 구현에서 확정합니다. 예시: [`examples/01_worker-input.scenarios.json`](examples/01_worker-input.scenarios.json)

| 필드 | 설명 |
| --- | --- |
| `hook_type` | `"A"` 고정 |
| `product_info` | `ProductInput`(`name`, `category`, `verified_facts[]`, 선택 `price_or_offer`, `target_audience`). **`verified_facts`에 없는 사실은 쓰지 않는다** |
| `project_id`, `round`, `count` | 몇 번째 뽑기인지와 만들 개수 |
| `previous_scenarios[]` | 앞선 회차 시나리오. 더 뽑을 때 **같은 소재·구조를 반복하지 않기 위해** 참고 |

콘티와 훅 단계에서는 저장된 `ScenarioItem`(`scenario_id`로 조회)과 `tts` 옵션만 받으면 됩니다.

## 시나리오 생성 시 지켜야 할 유형 규칙

기준 문서: [`skills/principle-only-hook-abstraction/SKILL.md`](../../../skills/principle-only-hook-abstraction/SKILL.md), [`skills/shortform-ad-hooks-blueprint/SKILL.md`](../../../skills/shortform-ad-hooks-blueprint/SKILL.md)의 Track A(`A_bgrade_reversal`). 아래는 요약이며 충돌하면 skills 문서가 우선입니다.

- **원리만 추출, 표면 복제 금지.** 예시·유행(밈·캐릭터·곡·IP)의 구체적 사물은 베끼지 않고 "왜 스크롤을 멈추는가"만 가져와 새 세계를 만든다.
- **낯선 장르 또는 최면/리듬 원형**을 고른다(`a_genre_archetype`). 예: `courtroom_trial`, `noir_interrogation`, `sports_var`, `mock_documentary`, `absurd_skit`, `brainrot_hypnosis`, `deadpan_rhythmic_loop`, `sensory_sync_loop` … 직전 캠페인과 같은 장르·골격(재난 뉴스 "속보입니다" 등)을 재사용하지 않는다.
- **제품 단서 0%.** 반전 전 구간(전체의 약 45~60%)의 자막·나레이션·시각 설명에 제품 키워드(`product_taboo_keywords`)와 카테고리·사용 공간 단서가 없어야 한다. 뽀모도로 타이머라면 타이머·시계·다이얼·원판·뽀모도로·공부·집중 같은 말.
- **패턴 인터럽트:** 반전 직전 0.18~0.32초 무음(`silence_gap`) + 장르에 맞는 컷 효과음.
- **담백한 착지:** 반전 뒤 제품은 짧고 차분하게(전체의 55% 이하). 스펙 나열("딱 좋아요", "가성비 끝장") 금지.
- 권장 `ad_spec` 키: `track_archetype: "A_bgrade_reversal"`, `a_genre_archetype`, `visual_style`(기본 `blender_clay_diorama`), `product_taboo_keywords[]`, `silence_gap_sec`, `pre_twist_ratio`, `payoff_ratio`.

## 반환해야 할 응답 형태

필드 정의는 [`../api-guide.md`](../api-guide.md)와 [`openapi.json`](../../../contracts/openapi.json)이 기준입니다. 이 유형의 예시:

| 단계 | 반환 | 예시 |
| --- | --- | --- |
| 시나리오 | `{ round, scenarios[] }` — 각 `ScenarioItem`: `scenario_id`, `round`, `type: "A"`, `hook_title`, `hook_duration_sec`(≤15), `body_duration_sec`, `replacement_test_note`, `beats[]`(`order`, `role`, `duration_sec`, `visual`, `narration`, `caption`), `ad_spec` | [`examples/02_scenarios.response.json`](examples/02_scenarios.response.json) |
| 콘티 | `{ frames[] }` — `beat_order`(= `beats[].order`), `image_url`, `caption` | [`examples/03_storyboard.response.json`](examples/03_storyboard.response.json) |
| 훅(폴링) | `{ status, files{hook_video, tts_audio, subtitles_srt, scenario_json, storyboard_images[]}, output_dir }` | [`examples/04_hook-status.done.json`](examples/04_hook-status.done.json) |

공통 규칙: 장면 길이 합 = `hook_duration_sec` ≤ 15초, 장면 3~5개, `replacement_test_note`에는 교체 테스트 판정 근거를 한 줄로 씁니다. `ad_spec`에는 아래 "유형 규칙"에서 정한 키를 넣습니다(유형 규칙 검증과 이후 린트에 쓰이는 값).

## 결과 파일 저장 위치와 이름

훅이 `done`이 되면 아래 폴더에 저장합니다(`OUTPUT_DIR` 기본값은 미정, 여기서는 `output/`).

```text
OUTPUT_DIR/{project_id}/{hook_id}/
├── hook.mp4              훅 영상 (15초 이하, 9:16)
├── tts.mp3               나레이션 음성 (beats[].narration)
├── hook.srt              자막 (beats[].caption, 장면 시작·끝 시각 기준)
├── scenario.json         이 훅에 쓴 ScenarioItem 그대로 (a/examples/05_saved-scenario.json 참고)
└── storyboard_01.png …   콘티 이미지 (2자리 번호 = beat_order)
```

회차가 달라지면 `hook_id`가 다른 새 폴더가 생기고 기존 폴더는 지우지 않습니다.

## index.html로 테스트하기

1. `python -m http.server 5500 --directory backend/bridge-dev` 후 `http://127.0.0.1:5500/`를 엽니다(파일로 열어도 됩니다).
2. **훅 유형**에서 **A**를 선택합니다. 제품 정보는 뽀모도로 타이머가 미리 채워져 있습니다.
3. Mock으로 흐름을 먼저 확인합니다: "처음부터 끝까지(1회)" 또는 "시나리오 더 뽑기 n회". 오른쪽 로그에서 요청 body와 응답 형태를 봅니다.
4. 내 코드로 확인: Mock을 끄고 Base URL을 백엔드로, Bearer 토큰에 `python backend/bridge-dev/dev_token.py --user worker-a` 결과를 넣고 같은 버튼을 누릅니다. 응답이 위 예시와 다르면 로그의 curl 복사로 재현합니다. CORS와 인증은 [`../README.md`](../README.md)를 참고하세요.
5. 끝나면 "결과 저장"으로 회차별 결과를 JSON으로 받아 예시와 비교합니다.

## 저장소의 A 캠페인 예시

- `prototypes/campaigns/digimore-timer-abc/05_ad_spec_A.json` (집중 스크롤), `05_ad_spec_A_absurd.json` (황당 피자)
- 같은 폴더의 `audio/vo_plan_A.json`, `final/ad_A_absurd_pizza.srt`, `final/ad_A_focus_scroll.srt`, `thumbs_spec.json`
- 이미 쓴 장르는 반복하지 않습니다. 이 가이드의 예시는 새 장르(`courtroom_trial`)입니다.

---

## A 시나리오 작업자 코드 (FR-003 · 4단계 블라인드 파이프라인)

제품 정보에 LLM이 끌려 Track C로 붕괴하는 문제를 구조적으로 막기 위해 Stage 2(`ideate.ts`)에 제품명·카테고리·검증사실을 전달하지 않는 **4단계 분리 파이프라인**과 [`../WORKER_CONTRACT.md`](../WORKER_CONTRACT.md) 표준 CLI 어댑터를 구현해 두었습니다.

```text
1. abstract.ts  : 제품 정보 -> 순수 물리/인지 법칙 1줄(abstract_law) + 3종 금칙어 추출
2. archetypes.ts: previous_scenarios에 없는 A안 장르 원형(14종 중 택1) 배정
3. ideate.ts    : ★ 블라인드 창작 — abstract_law + 장르 + 금칙어만으로 0~10초 훅 생성 (제품 미전달)
4. bridge.ts    : 담백한 실물 착지(<=55%) 결합 -> check.ts Double-Zero 검문 + 위반 시 자동 재시도
```

```bash
cd backend/bridge-dev/a
npm install
cp .env.example .env        # ANTHROPIC_API_KEY 입력

npm run typecheck           # TypeScript strict 검사
npm test                    # Mock 4단계 블라인드 격리 + 금칙어 재시도 E2E 검증 (API 과금 없음)
npm run check -- examples/02_scenarios.response.json examples/01_worker-input.scenarios.json
npm run scenarios -- --input examples/01_worker-input.scenarios.json --out out/a_scenarios.json
```
