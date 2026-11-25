# PRD 기준 테스트 구조

[PRD](https://climbing-domain-5ca.notion.site/PRD-v0-1-NAPDA-4237f7364375801ebd14d6f65ccd8aa1)의 기능 요구사항(FR)과 사용자 흐름에 따라 테스트를 모읍니다. 기존 Python 18개와 Node 4개 회귀 테스트를 기능별로 이동했으며, 아직 없는 제품 기능은 아래에 명시합니다.

| 폴더 | PRD 범위 | 현재 검증·남은 작업 |
| --- | --- | --- |
| `product_info/` | FR-001 제품 정보 | 수용 기준 정리 · 제품 폼 테스트 대기 |
| `planning/` | FR-002·003·005, BR-001~003 | 기존 스키마·기획 모의 응답·훅 검수 회귀 · 새 교체 테스트의 정성 기준은 미정 |
| `storyboards/` | FR-004 이미지 콘티 | UI 수용 기준 정리 · SDK 이미지 생성은 generation의 기존 테스트에서 검증 |
| `filming_guide/` | FR-007 촬영 가이드 | 수용 기준 정리 · 기능 테스트 대기 |
| `uploads/` | FR-009 원본 업로드 | 기존 원본 분석 회귀 · 제품 업로드 제한·검증은 미정 |
| `generation/` | FR-005·010, BR-004·006 | 기존 이미지·영상 생성, 예산 상한·재시도, 스타일 회귀 |
| `narration/` | FR-011 내레이션 | 기존 음성 전처리 회귀 · 공급자·목소리 선정은 미정 |
| `delivery/` | FR-012·013·014 | 기존 썸네일·안전 영역 회귀 · 다운로드 UI·AI 라벨 안내 테스트 대기 |
| `workflow/` | FR-008·015 | 이어하기 제안·업로드 먼저형 보류 · 제품 흐름 테스트 대기 |
| `credits/` | FR-006 | 크레딧 표시·차등 적용 정책 미정 · 과금 구현 없음 |
| `integration/` | FR-009~013의 기술 연결 | 플래너→워커 전달, API 인증, dry-run, 실제 FFmpeg 조립을 모의 생성 공급자로 검증 |
| `infrastructure/` | 공통 실행 기반 | 인증 모드·설정·재배치된 파일 경로 검증 |
| `prototypes/` | 기존 실험 | Flow UI 모의 동작, Vercel 호환 진입점·정적 빌드 검증 |
| `support/` | 공통 픽스처 | 모의 공급자·샘플 영상·캠페인 자료 |

## 실행

저장소 루트에서 Python 의존성을 설치하고 `npm ci`를 실행한 뒤 사용합니다.

```bash
.venv/bin/python scripts/test-python.py
npm test
npm run typecheck
npm run build
```

Windows에서는 Python 경로를 `.venv\Scripts\python.exe`로 바꿉니다. Python 실행기는 자식 프로세스의 UTF-8을 설정하고, Windows에서 기본 한글 글꼴을 테스트용으로 사용합니다. FFmpeg·FFprobe가 필요합니다.

특정 영역만 실행할 수 있습니다.

```bash
.venv/bin/python scripts/test-python.py planning
node scripts/test-node.mjs planning
```

실행 테스트가 없는 폴더에는 `README.md`로 수용 기준과 보류 상태만 기록합니다. 빈 테스트나 항상 통과하는 테스트를 만들지 않습니다. 기존 테스트 통과는 새 PRD 전체 구현 완료나 실제 생성 품질·원가 검증을 의미하지 않습니다. 유료 생성 API는 모의 응답으로 대체합니다.
