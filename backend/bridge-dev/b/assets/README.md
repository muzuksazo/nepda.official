# B 에셋

3D 장면에 쓰는 무료 에셋이다. 용량이 커서(약 380MB) 모델 파일은 커밋하지 않는다(`b/.gitignore`). 아래 스크립트로 다시 받을 수 있다.
미리보기: `assets/gallery.html` (브라우저로 열기, `python -I scripts/assets/asset_gallery.py assets` 로 다시 만듦).

| 폴더 | 출처 | 라이선스 | 내용 | 다시 받기 (b/ 에서) |
|---|---|---|---|---|
| `quaternius/base_character.glb` | Quaternius Universal Animation Library (poly.pizza 경유) | CC0 | 마네킹 1명, 동작 45개 | 커밋됨 |
| `quaternius/uacp/` | Quaternius Ultimate Animated Character Pack (Google Drive) | CC0 | 2~3등신 직업 캐릭터 52개, 동작 17개 | Drive 에서 glTF 폴더를 직접 받아 풀기 |
| `kenney/<팩>/` | kenney.nl 3D 팩 23개 | CC0 | 모델 약 2,300개 (가구·음식·자연·우주·도시·공장·기차·배 등) + 미리보기 PNG | `bash scripts/assets/fetch_kenney.sh` |
| `polyhaven/hdri/` | polyhaven.com 스튜디오 HDRI 6개 (1k) | CC0 | 자연스러운 조명·반사용 | `bash scripts/assets/fetch_polyhaven.sh` |
| `polypizza/` | poly.pizza 키워드 80개 × 상위 3개 | **모델마다 다름** (`catalog.json` 의 `license`) | 프리즘·시계·전구·지구본·책·사과 등 236개 | `python -I scripts/assets/polypizza_fetch.py assets/polypizza 3` |

## Poly Pizza 라이선스 주의
- `catalog.json` 에 모델별 제목·작가·라이선스·원본 주소를 남겼다. 2026-11-26 기준 CC0 51개, CC-BY 185개.
- **CC-BY** 모델을 영상에 쓰면 영상 설명 등에 작가 표기가 필요하다 (예: "Clock by jeremy, CC-BY, poly.pizza").
- 라이선스는 페이지 문구로 자동 판별했다. 실제 서비스에 쓰기 전에 원본 페이지에서 다시 확인한다.
- 키워드 검색 결과라 이름과 다른 물건이 섞여 있다 (예: "prism" → 수정 결정, 무지개).

## 못 받은 것
- KayKit (itch.io, 가격 자유·0원 가능): 자동 다운로드가 막혀 있다. 필요하면 itch.io 페이지에서 직접 받는다.
- 3dicons: Gumroad 에서 이메일 입력이 필요하다.
