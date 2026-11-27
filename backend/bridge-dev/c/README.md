# C 훅 작업자 — 제품과 직접 연결된 훅 (시나리오 전용)

## 이 유형의 정의

저장소 README의 교체 테스트 기준: **C = 특정 제품과 직접 연결된 훅. 다른 제품 광고에 옮겨 붙이기 어려움.** 문제 상황으로 열고, 제품의 가장 강한 동작 증명을 앞에 둡니다.

## 이 작업자가 하는 일

시나리오(FR-003)만 만듭니다. 콘티·훅 영상·나레이션·본편 붙이기는 [`backend/hookpipe`](../../hookpipe/README.md)가 A·B·C 공통으로 만듭니다.

이전에 있던 Blender 장면, Veo·Gemini Omni 문제 장면 템플릿(디퓨저·옷장·배수구), PIEV 개발 서버, R2 저장소 코드는 hookpipe로 대체되어 지웠습니다. Blender를 다시 쓸 때는 커밋 `f3c2de0`에서 `src/render.py`, `src/blender_scene*.py`를 되살리면 됩니다.

백엔드는 `backend/hookpipe/workers.py`에서 `generate_scenarios()`를 같은 프로세스 안에서 부릅니다.

## 입력

예시: [`examples/01_worker-input.scenarios.json`](examples/01_worker-input.scenarios.json)

| 필드 | 설명 |
| --- | --- |
| `hook_type` | `"C"` 고정 |
| `product_info` | `name`, `category`, `verified_facts[]`(1개 이상 필수), 선택 `selling_points[]`, `target_audience`. **`verified_facts`에 없는 사실은 쓰지 않는다** |
| `project_id`, `round`, `count` | 몇 번째 뽑기인지와 만들 개수(1~5) |
| `previous_scenarios[]` | 앞선 회차 시나리오. 같은 문제 상황·구조를 반복하지 않기 위해 참고 |

## 유형 규칙 (`src/check.py`, 위반이면 1번 다시 생성)

- 훅 길이 **15~20초**(팀 결정), 장면 3~5개, 장면 길이 합 = `hook_duration_sec`.
- 첫 장면 "문제"(밝고 날것인 POV), 둘째 장면 "가장 강한 증명", 나머지는 "장점".
- **훅 안에는 CTA 장면과 댓글 유도를 두지 않는다.** 훅 뒤에 본편이 붙기 때문이다. 댓글 질문은 `ad_spec.cta.text`(`placement: "after_body"`)에 두고 최종 영상 맨 끝에 쓴다.
- 근거 ID(`F01`…)는 `verified_facts` 순서대로. 없는 ID를 쓰면 오류.
- 미검증 표현(무소음, 배터리, dB, 치수·용량, 가격·할인, 지속 기간, 최상급)과 판매·공동구매 표기는 오류.
- 자막 2줄 이내, 한 줄 22자 이내. 나레이션은 초당 7.5음절 이하. 셋 다 오류.
- `ad_spec`: `track_archetype: "C_direct_proof"`, `claim_ids[]`, `proof_first: true`, `cta{type: "comment_engagement", text, placement}`, `disclosure: "ai_assisted"`, `pov_label`.

## 응답

[`examples/02_scenarios.response.json`](examples/02_scenarios.response.json) 형태입니다(`{project_id, status, round, scenarios[]}`).

## 실행 (계약 CLI, `backend/bridge-dev/c`에서)

```bash
python -m src.cli generate --input examples/01_worker-input.scenarios.json --out out/scenarios_response.json
python -m src.cli generate --input examples/01_worker-input.scenarios.json --model gemini-4-hydrogen
python -m src.cli generate --input examples/01_worker-input.scenarios.json --offline   # 모델 호출 없이 흐름만
python -m src.cli check --spec out/scenarios_response.json --input examples/01_worker-input.scenarios.json
```

종료 코드: 0 통과, 2 규칙 위반, 1 실행 오류. 키는 `.env.example`을 `.env`로 복사해 넣습니다.

글 모델은 기본이 Claude(`C_MODEL`)이고, `--model gemini-…`(또는 백엔드의 `HOOK_WORKER_LLM`)이면 같은 프롬프트·출력 스키마로 Gemini를 씁니다.

## 테스트 (모델 호출 없음)

```bash
python -m test.mock_run
```

## 파일

| 파일 | 역할 |
| --- | --- |
| `src/generate.py` | 시나리오 생성 (Claude 또는 Gemini, 위반 시 1번 재생성, `--offline` 초안) |
| `src/prompt.py` | 시스템 프롬프트와 사용자 프롬프트 |
| `src/check.py` | 유형 규칙 검사 |
| `src/schema.py` | 입력 확인, 출력 스키마, `ScenarioItem` 변환 |
| `src/cli.py` | 계약 CLI (`generate`, `check`) |

## 첫 장면의 구도 참고 이미지 (Blender 블록아웃)

첫 장면(문제)을 정해 둔 구도에서 시작하게 할 수 있습니다. `blockouts/catalog.json` 에 미리 렌더한 Blender 블록아웃을 등록해 두면, 글 모델이 첫 장면과 같은 상황인 것을 `problem_blockout` 으로 고르고, 그 장면에 `first_frame_ref`·`first_frame_prompt` 가 붙습니다. 훅을 만들 때 백엔드(`backend/hookpipe`)가 이미지 모델로 같은 구도의 실사 첫 프레임을 만들고 영상 모델이 그 화면에서 이어 만듭니다. 고르지 않으면 지금까지처럼 글만으로 만듭니다. 동작 순서, 새 구도 추가 방법, 비용, 확인 범위는 [blockouts/README.md](blockouts/README.md) 에 있습니다.
