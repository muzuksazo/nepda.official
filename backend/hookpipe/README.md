# hookpipe — 훅 영상 파이프라인

A·B·C 세 트랙의 작업물을 하나의 길로 잇는 백엔드 코드입니다. 트랙별 코드(`backend/bridge-dev/{a,b,c}`)는 고치지 않고 부르기만 합니다.

```text
제품 정보 ─▶ 시나리오 (유형별 작업자) ─▶ 훅 영상 (영상 모델) ─▶ 본편 붙이기 ─▶ 최종 영상
            workers.py                 render.py              body.py
```

## 무엇을 하나

| 단계 | 파일 | 하는 일 |
| --- | --- | --- |
| 시나리오 | `workers.py` | 유형별 작업자를 부릅니다. A·B는 Node 명령, C는 Python 함수입니다. 작업자를 못 쓰면 기존 planner-api로 넘어갑니다. |
| 훅 영상 | `render.py`, `prompts.py`, `captions.py` | 장면마다 영상 모델 클립을 만들고, 나레이션과 자막을 얹어 규격 파일로 저장합니다. |
| 본편 붙이기 | `body.py` | 올린 촬영 영상을 규격에 맞추고(길이, 화면, 소리 크기) 훅 뒤에 붙입니다. |
| 서버 연결 | `service.py` | `backend/app`의 `POST /hooks`, `POST /renders`가 부르는 진입점입니다. |

영상·이미지·음성 생성은 서버의 `app/genai_provider.py`(`GenAIMediaProvider`)를 그대로 씁니다. 파일 저장도 서버의 `storage`를 씁니다.

## 서버에서 바뀐 곳 (`backend/app`)

- `server.py`: 시나리오 생성기를 작업자 연결로 바꾸고, `HookPipeline`을 만들어 라우터에 넘깁니다.
- `projects_router.py`
  - `POST /v1/projects/{id}/hooks`: scenario.json과 자막만 쓰던 임시 구현을 `HookPipeline.process_hook`으로 바꿨습니다.
  - `POST /v1/projects/{id}/renders`: 작업자 시나리오(`ad_spec`에 `timeline`이 없는 것)는 `HookPipeline.process_render`로 갑니다. planner-api 시나리오와 `skip_drafts`는 기존 경로 그대로입니다.
- `config.py`: 아래 설정이 추가됐습니다.

## 훅 결과 파일

`OUTPUT_DIR/{project_id}/{hook_id}/` ([WORKER_CONTRACT.md](../bridge-dev/WORKER_CONTRACT.md) 4절)

| 파일 | 내용 |
| --- | --- |
| `hook.mp4` | 1080x1920, 30fps, H.264, 소리 -14 LUFS, 자막 포함 |
| `tts.mp3` | 나레이션 트랙 (나레이션이 있을 때만) |
| `hook.srt` | 자막 (한 줄 22자 이하, 2줄 이내) |
| `scenario.json` | 채택된 시나리오 원문 |
| `storyboard_NN.png` | 장면별 대표 화면 (완성된 훅에서 뽑음) |
| `render_meta.json` | 장면별 프롬프트·길이·경고 |
| `final.mp4`, `final.srt` | 본편까지 붙인 최종 영상 (`POST /renders` 뒤) |
| `_work/` | 중간 파일. 같은 폴더로 다시 만들면 이미 받은 클립을 재사용합니다. |

## 정해 둔 규칙

- **훅 길이:** 20초 이하(`HOOK_MAX_SEC`). 하한은 각 트랙의 검사에 맡깁니다.
- **제품 참고 이미지:** 올린 촬영 영상에서 컷 2장을 뽑아 제품이 나오는 장면에 넣습니다. 올린 영상이 없으면 제품 사실 문장만으로 그립니다.
- **제품이 나오는 장면:** B는 `ad_spec.product_first_mention_beat`부터, C는 "문제" 장면을 뺀 전부, A는 마지막 장면입니다.
- **나레이션이 장면보다 길 때:** 1.3배까지 빠르게 읽고, 그래도 길면 장면을 늘립니다.
- **본편:** 올린 순서(`shot_no`)대로 잇습니다. 촬영 가이드 길이(`target_body_duration_sec`)를 넘으면 각 클립의 앞부분을 같은 비율로 씁니다. 가로 영상은 흐린 배경 위에 얹습니다.
- **과금 방어:** 훅 하나에서 요청하는 클립 길이 합이 `HOOK_MAX_CLIP_SEC_PER_HOOK`(기본 45초)을 넘으면 영상 모델을 부르기 전에 멈춥니다. 같은 시나리오로 다시 `POST /renders`를 부르면 훅은 다시 만들지 않습니다.

## 설정 (`backend/.env`)

| 이름 | 기본값 | 뜻 |
| --- | --- | --- |
| `HOOK_WORKER_MODE` | `auto` | `auto`: 작업자 호출 후 실패하면 planner-api. `off`: planner-api만. |
| `HOOK_WORKERS_DIR` | `backend/bridge-dev` | 작업자 폴더 위치 |
| `HOOK_WORKER_TIMEOUT_SEC` | `900` | A·B 작업자 한 번의 제한 시간 |
| `HOOK_RENDER_MODE` | `video_model` | `dry_run`이면 과금 호출 없이 scenario.json과 hook.srt만 씁니다. |
| `HOOK_MAX_SEC` | `20` | 훅 길이 상한 |
| `HOOK_CLIP_RESOLUTION` | `720p` | 영상 모델 클립 해상도 |
| `HOOK_BURN_CAPTIONS` | `true` | 자막을 영상에 구울지 |
| `HOOK_MAX_CLIP_SEC_PER_HOOK` | `45` | 훅 하나의 클립 길이 합 상한 |
| `BODY_MAX_SEC` | `60` | 본편 길이 상한 |
| `FFMPEG_BIN`, `FFPROBE_BIN` | PATH | ffmpeg 위치. ffprobe는 없어도 됩니다. |

## 작업자를 쓰려면

| 유형 | 준비 |
| --- | --- |
| A | Node 22 이상, `backend/bridge-dev/a`에서 `npm ci`, 환경변수 `ANTHROPIC_API_KEY` |
| B | Node 22 이상, `backend/bridge-dev/b`에서 `npm ci`, `b/.env`에 키 |
| C | 서버 가상환경에 `pip install anthropic`, 환경변수 또는 `c/.env`에 `ANTHROPIC_API_KEY` |

준비가 안 된 유형은 오류 대신 planner-api로 넘어가고, 서버 로그에 이유가 남습니다.

## 테스트

```bash
.venv/bin/python scripts/test-python.py hookpipe
```

영상·음성 모델은 대역으로 바꾸고 ffmpeg는 실제로 돌립니다. 과금 호출은 없습니다. ffmpeg가 없으면 조립 테스트는 건너뜁니다.

## 아직 하지 않은 것

- 실제 영상 모델·TTS 호출로 만든 결과 확인 (과금이 필요해 대역으로만 검증했습니다).
- 본편용 나레이션·자막, 훅과 본편 사이 전환 효과, 끝 CTA 카드.
- 썸네일. `/deliverables`의 `thumbnail`은 비어 있습니다.
- 배포 이미지: `Dockerfile`은 `hookpipe`만 복사합니다. 작업자를 쓰려면 Node와 `bridge-dev` 폴더를 이미지에 넣어야 합니다.
- 공통 규약 문서의 훅 길이(15초 이하)는 팀 결정(15~20초)에 맞춰 고쳐야 합니다.
