# 냅다 프론트엔드

프로덕션 프론트엔드의 개발 위치입니다. 기존 코드에는 PRD의 가이드 먼저형 UI가 없어 이 폴더에는 아직 실행 앱을 추가하지 않았습니다.

[PRD](https://climbing-domain-5ca.notion.site/PRD-v0-1-NAPDA-4237f7364375801ebd14d6f65ccd8aa1)의 제품 정보 → 유형·시나리오·콘티 → 촬영 가이드 → 촬영·업로드 → 결과·내려받기 흐름을 이곳에 구현합니다.

- UI·프론트엔드 코드는 이 폴더에서 관리합니다.
- 서버·미디어 워커는 `apps/backend/`에서 관리합니다.
- 플래너 계약·스키마는 `libraries/planner-api/`에서 관리합니다.
- 사용자 흐름 테스트는 루트 `tests/`의 PRD별 폴더에 추가합니다.

기존 실험 화면은 [프로토타입](../../prototypes/hookcut/README.md)에서 확인합니다.
