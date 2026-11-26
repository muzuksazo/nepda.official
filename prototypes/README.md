# Prototypes

제품 요구사항이 확정되기 전의 웹 실험과 제작 자료를 모읍니다.

| 폴더 | 내용 |
| --- | --- |
| [hookcut](hookcut/README.md) | 기존 업로드 먼저형 편집 화면·브라우저 렌더링·Vercel API 구현 |
| `campaigns/` | 제품 팩트·시안 스펙·대본·자막·검수 이미지와 제작 실험 이력 |
| `zackd-jet-umbrella/` | Zack D. Films 스타일 제트기 우산 물리 시뮬레이션 3D 실험·검수 스트립 |
| `viral-3d-templates/` | 5대 바이럴 3D 물리 템플릿(T1~T5) Blender/Cycles 파이프라인·스펙·쇼케이스 검수 |
| `ps2-kr-subway/` | PS2 로우폴리 한국 일상 Ep.1 (2호선 왕십리역 지옥철) Blender 씬·VO 타임라인·검수 |
| `ps2-remarried-office/` | PS2 로우폴리 재혼황후 K-직장인 패러디 Blender 씬·3인 VO 타임라인·검수 |

폴더 이동으로 캠페인 내부의 `source/`, `clips/`, `audio/` 상대 경로는 바꾸지 않았습니다. 대용량 미디어는 계속 Git에서 제외합니다.

제품 프론트엔드는 `frontend/`, 백엔드는 `backend/`, 공용 도구는 `libraries/`, 기존 실험 회귀 테스트는 `tests/prototypes/`에서 관리합니다.
