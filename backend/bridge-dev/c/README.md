# C 훅 작업자 가이드 — 제품과 직접 연결된 훅

## 이 유형의 정의

저장소 README의 교체 테스트 기준: **C = 특정 제품과 직접 연결된 훅. 다른 제품 광고에 옮겨 붙이기 어려움.** 문제 상황으로 열고, 제품의 가장 강한 동작 증명을 앞에 둡니다.

## 이 작업자가 받는 요청

공개 API 요청은 모두 백엔드가 받고, 백엔드는 프로젝트의 `selected_types`가 `["C"]`이면 **이 유형 작업자 코드**를 호출합니다. 작업자 코드로 들어오는 경우는 세 가지입니다.

| 들어오는 공개 API | 작업자가 하는 일 | 작업자가 반환 |
| --- | --- | --- |
| `POST /v1/projects/{id}/scenarios` | 시나리오 `count`개 생성 | `ScenarioItem[]` (`type: "C"`, `round`) |
| `POST /v1/projects/{id}/scenarios/{sid}/storyboard` | 장면별 콘티 이미지 생성 | `StoryboardFrame[]` |
| `POST /v1/projects/{id}/hooks` | 선택된 시나리오로 훅 영상 + TTS 생성 | 영상·음성·자막 파일(상태는 폴링 응답으로) |

시나리오 생성 시 작업자 코드가 받는 입력은 아래와 같습니다. 공개 API가 아니라 `POST /scenarios` 처리 중의 **내부 호출(제안 인터페이스)**이며, 필드 이름은 백엔드 구현에서 확정합니다. 예시: [`examples/01_worker-input.scenarios.json`](examples/01_worker-input.scenarios.json)

| 필드 | 설명 |
| --- | --- |
| `hook_type` | `"C"` 고정 |
| `product_info` | `ProductInput`(`name`, `category`, `verified_facts[]`, 선택 `price_or_offer`, `target_audience`). **`verified_facts`에 없는 사실은 쓰지 않는다** |
| `project_id`, `round`, `count` | 몇 번째 뽑기인지와 만들 개수 |
| `previous_scenarios[]` | 앞선 회차 시나리오. 더 뽑을 때 **같은 소재·구조를 반복하지 않기 위해** 참고 |

콘티와 훅 단계에서는 저장된 `ScenarioItem`(`scenario_id`로 조회)과 `tts` 옵션만 받으면 됩니다.

## 시나리오 생성 시 지켜야 할 유형 규칙

기준 문서: [`skills/shortform-ad-hooks-blueprint/SKILL.md`](../../../skills/shortform-ad-hooks-blueprint/SKILL.md)의 Track C(`C_direct_proof`).

- **밝고 날것인 POV 문제 훅**으로 시작하고 곧바로 제품의 **가장 강한 실물 동작 증명**을 앞쪽에 둔다.
- 검증된 장점 2~3개를 `verified_facts`에서 골라 근거 ID(`F01`…)와 함께 쓴다. 증명 장면은 실제 제품 동작만 보여 준다(없는 기능을 연출하지 않는다).
- PAS(문제-자극-해결)·스펙 설득과 단일 CTA는 **C에만** 쓴다. A·B로 번지지 않게 한다.
- CTA는 하나. 광고 표시: `ad_spec.disclosure: "ai_assisted"`, 판매·공동구매 표기 없이 댓글 유도(`comment_engagement`) 방식.
- 금지: 미검증 주장(무소음, 배터리, 알람 dB, 치수, 가격·할인). 뽀모도로 타이머의 허용 문구는 `00_product_facts.md`의 Whitelisted 항목.
- 권장 `ad_spec` 키: `track_archetype: "C_direct_proof"`, `claim_ids[]`, `proof_first`, `cta{type, text}`, `disclosure`.

## 반환해야 할 응답 형태

필드 정의는 [`../api-guide.md`](../api-guide.md)와 [`openapi.json`](../../../contracts/openapi.json)이 기준입니다. 이 유형의 예시:

| 단계 | 반환 | 예시 |
| --- | --- | --- |
| 시나리오 | `{ round, scenarios[] }` — 각 `ScenarioItem`: `scenario_id`, `round`, `type: "C"`, `hook_title`, `hook_duration_sec`(≤15), `body_duration_sec`, `replacement_test_note`, `beats[]`(`order`, `role`, `duration_sec`, `visual`, `narration`, `caption`), `ad_spec` | [`examples/02_scenarios.response.json`](examples/02_scenarios.response.json) |
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
├── scenario.json         이 훅에 쓴 ScenarioItem 그대로 (c/examples/05_saved-scenario.json 참고)
└── storyboard_01.png …   콘티 이미지 (2자리 번호 = beat_order)
```

회차가 달라지면 `hook_id`가 다른 새 폴더가 생기고 기존 폴더는 지우지 않습니다.

## C 작업자 코드 (FR-003 · FR-004 · FR-005, 로컬 실행)

시나리오 생성, 콘티 이미지, 훅 영상 + TTS 까지 구현되어 있습니다. Python 표준 라이브러리로 돌고, 시나리오 생성에 `anthropic`, Google Cloud 인증에 `google-auth` 패키지를 씁니다.

```text
1. 시나리오 (src/generate.py) — Claude 로 C 규칙에 맞는 시나리오 count 개 생성
   → 규칙 검사 (src/check.py). 위반이 있으면 위반 내용을 붙여 한 번 더 생성
2. 콘티 (src/render.py: storyboard) — 장면마다 대표 화면 한 장에 자막을 얹어 저장
3. 훅 (src/render.py: render_hook)
   화면: 문제 장면 = 생성 영상 (Blender 가 첫 프레임을 렌더 → Google Veo 가 영상으로 생성)
         나머지 장면 = 실물 제품 영상 (증명은 실물만)
   음성: Inworld TTS, 단어별 타임스탬프로 화면 자막을 2어절 안팎씩 끊어 맞춤
   합성: ffmpeg (자막 번인, 배경음·효과음, "AI 연출 포함" 배지)
   → hook.mp4 · tts.mp3 · hook.srt · scenario.json · storyboard_NN.png
```

| 파일 | 역할 |
| --- | --- |
| `src/schema.py` | 입력(01_worker-input) 확인, ScenarioItem 조립, Claude 구조화 출력 스키마 |
| `src/prompt.py` | C 규칙 프롬프트, 문제 장면 템플릿 설명 |
| `src/generate.py` | `generate_scenarios(input)` — 백엔드가 import 해서 부를 함수 (FR-003) |
| `src/check.py` | 규칙 검사 (장면 3~5개, 15초, 문제→증명 순서, 근거 ID, 미검증·판매 표현, 자막 길이, 단일 CTA) |
| `src/render.py` | `storyboard(scenario, assets, out_dir)` (FR-004), `render_hook(scenario, assets, out_dir, tts=…)` (FR-005) |
| `src/tts.py` | Inworld TTS 호출과 캐시 |
| `src/blender_scene.py` | 문제 장면 템플릿 `spill_diffuser` (Blender 안에서 실행: 강체 물리, 흐르는 액체, 손) |
| `src/veo.py` | 문제 장면 생성 영상: Blender 첫 프레임 → Google Veo (Vertex AI REST, 이미지→영상), 결과 캐시 |
| `src/assets.py` | 문제 장면용 무료(CC0) 에셋 내려받기 |
| `src/cli.py` | 명령줄 실행 |
| `test/mock_run.py` | API·Blender·ffmpeg 없이 도는 흐름 확인 |

필요한 프로그램: Python 3.10 이상, ffmpeg·ffprobe(자막 번인용 libass 포함), 문제 장면 템플릿을 쓸 때는 Blender 4.2 이상.

```bash
cd backend/bridge-dev/c
pip install -r requirements.txt
cp .env.example .env        # ANTHROPIC_API_KEY, INWORLD_API_KEY 입력 (.env 는 커밋되지 않음)

python -m test.mock_run                                              # 흐름 확인 (API 호출 없음)
python -m src.cli check examples/02_scenarios.response.json          # 규칙 검사만 (API 호출 없음)
python -m src.cli assets                                             # 문제 장면용 에셋 받기 (약 80MB, 한 번만)

python -m src.cli scenarios examples/piev/01_worker-input.scenarios.json          # 1회차 생성 (Claude API 과금)
python -m src.cli scenarios examples/piev/01_worker-input.scenarios.json --next   # 다음 회차 (앞선 소재 제외)
python -m src.cli storyboard proj_piev01 <scenario_id>                            # 콘티 이미지
python -m src.cli veo                                                             # Google Cloud 설정·인증 확인 (과금 없음)
python -m src.cli hook proj_piev01 <scenario_id>                                  # 훅 영상 + TTS (Inworld·Veo 과금)
```

### 문제 장면: Blender + Google Veo

문제 장면은 두 단계로 만듭니다. Blender 가 장면(테이블, 디퓨저, 조명, 카메라 구도)의 첫 프레임을 렌더하고, 그 이미지를 Vertex AI 의 Veo 에 넘겨 같은 구도에서 손이 병을 쳐서 쏟는 영상을 받습니다. 구도와 소품은 Blender 가 정하고 움직임과 질감은 Veo 가 만듭니다.

| 설정 | 내용 |
| --- | --- |
| `GOOGLE_CLOUD_PROJECT` | Google Cloud 프로젝트 ID. 이 작업자는 `project-453b367f-b616-4471-aef` 를 씁니다(`.env.example` 기본값). 결제 계정 연결과 Vertex AI API 사용 설정이 필요합니다 |
| 인증 | 서비스 계정 키 경로를 `GOOGLE_APPLICATION_CREDENTIALS` 에 넣거나 `gcloud auth application-default login` |
| `C_VEO_MODEL` | 기본 `veo-3.1-fast-generate-001`. 품질 우선이면 `veo-3.1-generate-001` |
| `C_PROBLEM_ENGINE` | `auto`(기본) · `veo` · `blender`. 입력의 `assets.problem_engine` 이나 `hook --engine` 으로도 정합니다 |

- `auto` 는 `GOOGLE_CLOUD_PROJECT` 가 있으면 Veo 를 쓰고, 없거나 호출이 실패하면 Blender 물리 렌더(전 프레임)로 대신합니다. `veo` 는 실패하면 오류로 끝납니다. 어느 쪽으로 만들었는지는 `hook` 결과의 `problem_engine` 에 나옵니다.
- Veo 는 4·6·8초로만 생성하므로 장면 길이를 덮는 가장 짧은 길이로 요청하고(3초 장면 → 4초) 장면 길이에 맞춰 빠르게 돌립니다. 초 단위로 과금됩니다.
- 같은 첫 프레임·프롬프트·설정이면 `assets/cache/veo/` 의 영상을 다시 쓰므로 두 번 과금되지 않습니다. 새로 뽑으려면 그 파일을 지우세요.
- `storyboard` 명령은 Veo 를 부르지 않습니다. 만들어 둔 영상이 있으면 그 화면을, 없으면 Blender 프레임을 씁니다.
- `python -m src.cli veo --generate` 는 문제 장면 한 편만 실제로 생성해 봅니다 (과금).

키 없이 끝까지 확인하려면 `scenarios … --offline`(사실 문장으로 만든 초안) 또는 `import examples/piev/02_scenarios.response.json --input examples/piev/01_worker-input.scenarios.json`(직접 쓴 시나리오 가져오기)을 쓰고, 훅은 `--no-tts` 로 실행합니다.

### 입력 확장: `product_info.selling_points` (소구포인트)

구매자가 이 제품을 사는 이유를 입력으로 받아, 문제 장면을 거기에서 고르게 합니다. 지금은 사람이 넣고, 나중에 리뷰 수집 서비스가 같은 형태로 채우면 됩니다. 예시: [`examples/piev/05_worker-input.round3.json`](examples/piev/05_worker-input.round3.json)

```json
"selling_points": [
  { "point": "탈취·악취 제거", "source": "11번가 구매 후기", "evidence": ["화장실에서는 청량한 향기가 납니다."] }
]
```

- `point` 만 필수이고 문자열 하나로 줘도 됩니다. `evidence` 는 그 소구포인트가 나온 후기 원문으로, 문제 장면의 장소와 상황을 고르는 데 씁니다.
- 소구포인트는 방향일 뿐 근거가 아닙니다. 제품에 대한 말은 여전히 `verified_facts` 에 있는 내용만 쓰고, 규칙 검사도 그대로 적용됩니다.
- 시나리오가 겨냥한 소구포인트는 `ad_spec.selling_point` 에 남습니다. 입력 목록에 없는 값이면 검사에서 경고가 납니다.

### 입력 확장: `assets`

가이드의 제안 인터페이스에 없는 필드입니다. 영상에 쓸 소재를 알려 줍니다. 예시: [`examples/piev/01_worker-input.scenarios.json`](examples/piev/01_worker-input.scenarios.json)

| 필드 | 설명 |
| --- | --- |
| `assets.product_footage` | 실물 제품 영상 경로. 둘째 장면부터 장면 길이 비율로 나눠 이어 씁니다. 길이가 모자라면 0.85배속까지 늘리고 나머지는 정지 화면 |
| `assets.problem_template` | 첫 장면(문제)에 쓸 생성 영상 템플릿. `spill_diffuser`(손이 액체 디퓨저를 쳐서 쏟는 장면, 3초), `evaporate_diffuser`(액체 디퓨저가 며칠 사이 바닥까지 줄어드는 타임랩스, 4초. 예시: `examples/piev/03_…`, `04_…`), `drain_smell`(욕실 배수구 냄새, 방향제를 뿌려도 다시 올라옴, 최대 10초. 예시: `05_…`~`07_…`). role 이 "문제"인 장면이 처음부터 이어지면 그 장면들에 걸쳐 한 영상으로 씁니다 |
| `assets.problem_engine` | 문제 장면을 만드는 방법. `auto`(기본) · `veo` · `blender` |

둘 다 없으면 자막만 있는 단색 카드로 만들어집니다. 화면에 띄우는 상황 라벨은 `ad_spec.pov_label` 에 들어갑니다.

### 결과와 기록

```text
out/{project_id}/round-{n}.json            회차 기록 (응답 + 규칙 검사 + 비용 + assets)
{OUTPUT_DIR}/{project_id}/{scenario_id}/   storyboard 명령의 콘티 이미지
{OUTPUT_DIR}/{project_id}/{hook_id}/       hook 명령의 결과 (위 "결과 파일 저장 위치와 이름"과 같은 구성)
assets/                                    내려받은 에셋과 문제 장면 렌더 캐시 (커밋 안 함)
```

- `OUTPUT_DIR` 기본값은 `output`(c/ 기준)이고 `.env` 로 바꿉니다. `out/`, `output/`, `assets/` 는 커밋하지 않습니다.
- 모델은 `.env` 의 `C_MODEL`(기본 `claude-opus-5-5`), 목소리는 `C_TTS_VOICE` 또는 `hook --voice`.
- 문제 장면은 처음 한 번만 Blender 로 렌더하고(물리 계산 포함 1~2분) `assets/cache/` 의 프레임을 다시 씁니다. 장면을 고쳤으면 그 폴더를 지우세요.
- 에셋은 Poly Haven(텍스처·HDRI·소품)과 Blender Human Base Meshes(손)이고 모두 CC0 입니다. 받지 않아도 기본 도형으로 만들어집니다.
- 화면 자막은 음성에 맞춰 끊어 넣고, `hook.srt` 는 가이드대로 장면당 한 개(`beats[].caption`, 장면 시작·끝 시각)입니다.
- 검사 결과의 ✗는 규칙 위반(종료 코드 2), △는 사람이 볼 경고입니다.
- 아직 없는 것: 백엔드(`backend/app`) 연결, 훅 작업 큐·폴링 상태 저장, `spill_diffuser` 외의 문제 장면 템플릿.

## 더미 화면에서 C 작업자 코드 돌리기 (로컬 서버)

`src/server.py` 는 bridge-dev 더미 화면이 부르는 API(`/v1/product-info`, `/v1/projects`, `…/scenarios`, `…/storyboard`, `…/select`, `…/hooks`)를 이 작업자 코드로 처리하는 개발용 서버입니다. 공용 `index.html` 은 수정하지 않고 읽어서 내주기만 하며, 같은 서버에서 화면을 내주므로 CORS 설정이 필요 없습니다.

```bash
cd backend/bridge-dev/c
C_PRODUCT_FOOTAGE=<실물 영상 경로> C_PROBLEM_TEMPLATE=drain_smell \
C_SCENARIO_FILES=examples/piev/06_scenarios.round3.response.json python -m src.server
# http://127.0.0.1:8080/?preset=piev          C 유형·실제 호출·피에브 제품 정보가 채워진 화면
# http://127.0.0.1:8080/?preset=piev&run=1    열자마자 "처음부터 끝까지" 실행
```

- 화면이 보내지 않는 값(실물 영상, 문제 장면 템플릿)은 환경변수로 받습니다.
- 시나리오는 `ANTHROPIC_API_KEY` 가 있으면 Claude 로 생성하고, 없으면 `C_SCENARIO_FILES` 의 준비된 응답을 회차마다 돌려 쓰며, 그것도 없으면 오프라인 초안을 냅니다. 어느 쪽인지는 응답의 `scenario_source` 에 나옵니다.
- 콘티 이미지와 훅 결과 파일은 `/files/…` 주소로 내주고, 훅이 끝나면 화면 아래에 영상 재생기가 붙습니다.
- 인증을 확인하지 않고 상태를 메모리에만 두는 개발용입니다. `backend/app` 과의 연결은 아닙니다.

## index.html로 테스트하기

1. `python -m http.server 5500 --directory backend/bridge-dev` 후 `http://127.0.0.1:5500/`를 엽니다(파일로 열어도 됩니다).
2. **훅 유형**에서 **C**를 선택합니다. 제품 정보는 뽀모도로 타이머가 미리 채워져 있습니다.
3. Mock으로 흐름을 먼저 확인합니다: "처음부터 끝까지(1회)" 또는 "시나리오 더 뽑기 n회". 오른쪽 로그에서 요청 body와 응답 형태를 봅니다.
4. 내 코드로 확인: Mock을 끄고 Base URL을 백엔드로, Bearer 토큰에 `python backend/bridge-dev/dev_token.py --user worker-c` 결과를 넣고 같은 버튼을 누릅니다. 응답이 위 예시와 다르면 로그의 curl 복사로 재현합니다. CORS와 인증은 [`../README.md`](../README.md)를 참고하세요.
5. 끝나면 "결과 저장"으로 회차별 결과를 JSON으로 받아 예시와 비교합니다.

## 저장소의 C 캠페인 예시

- `prototypes/campaigns/digimore-timer-abc/05_ad_spec_C.json` (뽀모도로 직격)
- 같은 폴더의 `audio/vo_plan_C.json`, `final/ad_C_pomodoro_direct.srt`, `05_lint_report_C.md`, `00_product_facts.md`
