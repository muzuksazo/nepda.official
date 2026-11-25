# 미디어 도구

기존 숏폼 제작 스크립트를 공용 라이브러리 폴더로 옮겼습니다. 파일끼리의 로컬 import와 CLI 인자는 유지합니다.

| 도구 | 역할 |
| --- | --- |
| `ad_source_analyzer.py` | 원본 영상 분석·장면 자료 |
| `ad_flow_jobs.py` | 생성 작업 스펙 준비 |
| `ad_gate_a_lint.py` | 기존 캠페인·훅 검수 |
| `ad_audio_prep.py` | 음성 전처리 |
| `ad_remix_assemble.py` | FFmpeg 영상·음성 조립 |
| `ad_thumbnail_builder.py` | 썸네일·검수 시트 생성 |
| `ad_abc_sheet_builder.py` | 비교 시트 생성 |
| `flow_automator.py` | 기존 Flow 자동화 실험 |

저장소 루트에서 실행합니다.

```bash
.venv/bin/python libraries/media-tools/ad_gate_a_lint.py --help
.venv/bin/python libraries/media-tools/ad_remix_assemble.py --help
```

백엔드의 `SCRIPTS_DIR` 기본값은 이 폴더입니다. Docker에서는 `/app/scripts`로 복사합니다. PRD별 회귀 테스트는 `tests/planning/`, `tests/uploads/`, `tests/narration/`, `tests/generation/`, `tests/delivery/`에 있으며, Flow UI 실험 테스트는 `tests/prototypes/`에 있습니다.

기존 검수 규칙과 자동화 코드는 실험 이력입니다. 최종 생성 방식과 PRD의 정성적인 교체 테스트 기준은 추가 결정이 필요합니다.
