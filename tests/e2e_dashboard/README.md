# NAPDA E2E 테스트 & 도메인별 스크린샷 · 녹화 대시보드 사용 가이드

- **라이브 대시보드**: **https://muzuksazo.github.io/nepda.official/**
- **역할 분배표 / 전체 명세**: [tests/E2E_TEST_PLAN.md](../E2E_TEST_PLAN.md)

팀원(`나`, `시우님`, `상윤님`) 누구나 본인이 맡은 기능·안(`A / B / C`)의 E2E 녹화 영상(`.mp4`)과 단계별 스크린샷(`.webp`)을 도메인별로 대시보드에 바로 올리고, 브라우저에서 **도메인 기능별 스크린샷 갤러리**(라이트박스 이전/다음 탐색 지원) 및 **배속 조절(`0.5x / 0.75x / 1x`) 인라인 `<video>` 플레이어**로 확인할 수 있습니다. `main` 브랜치에 푸시하면 GitHub Actions가 약 30초 내 자동 재배포합니다.

---

## 1. 파일 구조

| 경로 | 역할 |
|---|---|
| [`tests/e2e_dashboard/index.html`](./index.html) | 정적 대시보드 UI (도메인·담당자·환경·상태 필터, `0.5x/0.75x/1x` 배속 토글, 도메인별 스크린샷 갤러리 & 라이트박스, `poster` 포함 `<video>` 플레이어) |
| [`tests/e2e_recordings/manifest.json`](../e2e_recordings/manifest.json) | 대시보드 데이터 원본 (`domains` 도메인 분류, 오프라인 스위트 결과, 3인 담당자, `PASS`/`TODO` 케이스 + `screenshots[]` 목록) |
| [`tests/e2e_recordings/*.mp4`](../e2e_recordings/) | 실제 재생되는 기능별 `.mp4` 파일 (루트 `.gitignore`의 `!tests/e2e_recordings/*.mp4` 예외 허용, 화면 전환당 약 1.8~2.2초 체류) |
| [`tests/e2e_recordings/shots/`](../e2e_recordings/shots/) | 기능별 단계 `.webp` 스크린샷 (`shots/<feature_slug>/<step>.webp`) |
| [`.github/workflows/pages-e2e.yml`](../../.github/workflows/pages-e2e.yml) | 대시보드 자동 배포 워크플로 (`tests/e2e_dashboard/**`, `tests/e2e_recordings/**` 푸시 시 실행) |

---

## 2. 내 E2E 녹화 영상 & 스크린샷 올리는 3단계

### Step 1. 브라우저 호환 H.264 `.mp4` 변환 + 단계별 `.webp` 캡처
Playwright(`.webm`) 또는 macOS 화면 녹화(`.mov`) 원본을 브라우저에서 바로 재생되는 H.264(`yuv420p`) + `+faststart` 포맷으로 변환합니다. (모바일 화면 녹화는 `432×932` 권장, 1편당 1~2 MB 이내 유지, 사람이 따라 보기 편하도록 주요 화면 전환마다 약 `1.8~2.2초` 체류 권장)

```bash
ffmpeg -y -i input.webm \
  -c:v libx264 -preset fast -crf 22 -pix_fmt yuv420p -movflags +faststart \
  tests/e2e_recordings/abc_B_hook_e2e.mp4
```

단계별 핵심 화면은 `tests/e2e_recordings/shots/<feature_slug>/` 아래에 `01_<step>.webp`, `02_<step>.webp` 식으로 저장합니다. (`.webp`는 `.gitignore`에 차단되지 않으며 PNG 대비 약 10~30 KB 수준으로 가볍습니다.)

### Step 2. `manifest.json`에 `domain`, `poster`, `screenshots` 연결
파일명은 [`tests/E2E_TEST_PLAN.md`](../E2E_TEST_PLAN.md)의 명명 규칙(`abc_B_hook_e2e.mp4`, `abc_C_hook_e2e.mp4`, `<순번>_<local|live>_<feature>.mp4`)을 따릅니다.

`tests/e2e_recordings/manifest.json`의 `domains` 중 알맞은 `domain` ID가 지정되어 있는지 확인하고, `status`, `video`, `poster`, `durationSec`, `sizeKb`, `screenshots`를 채워 넣습니다.

**도메인 ID (`domains`) 목록:**
- `creation`: 영상 제작 · 8단계 위저드
- `discovery`: 홈 · 내 영상 · 탐색
- `billing`: 결제 · 크레딧 (Paddle)
- `auth`: 인증 · 온보딩
- `profile`: 프로필 · 테마 설정
- `live`: 실서버 배포 스모크

**수정 후 (`PASS` + 영상 + 도메인별 스크린샷 연결):**
```json
{
  "id": "E2E-ABC-B",
  "domain": "creation",
  "title": "B안 풀스택 E2E (B 유형 선택 → 시나리오/콘티/생성 → 결과 확인)",
  "owner": "siwoo",
  "env": "local",
  "status": "pass",
  "fr": "B안 · FR-003~005·010",
  "durationSec": 28.4,
  "sizeKb": 320,
  "video": "./recordings/abc_B_hook_e2e.mp4",
  "poster": "./recordings/shots/abc_B_hook_e2e/07_review.webp",
  "screenshots": [
    { "label": "1/8 제품 정보", "src": "./recordings/shots/abc_B_hook_e2e/01_product.webp" },
    { "label": "2/8 유형 선택 (B)", "src": "./recordings/shots/abc_B_hook_e2e/02_hook.webp" },
    { "label": "7/8 영상 확인", "src": "./recordings/shots/abc_B_hook_e2e/07_review.webp" }
  ],
  "checks": [
    "B 유형 훅 선택 → Blender 3D 시나리오·콘티 생성 확인",
    "촬영 영상 업로드 및 결과물·썸네일 확인 완료, 에러 0건"
  ]
}
```

> [!IMPORTANT]
> `video`, `poster`, `screenshots[].src` 경로는 GitHub Pages 배포 번들 기준이므로 반드시 `./recordings/...` 상대 경로여야 합니다.

JSON 문법 오류 확인:
```bash
python3 -m json.tool tests/e2e_recordings/manifest.json > /dev/null && echo "manifest.json OK"
```

### Step 3. (선택) 로컬 미리보기 후 `main`에 푸시
GitHub Actions가 빌드할 `_site/` 구조와 동일하게 복사해 로컬 브라우저에서 먼저 확인할 수 있습니다.

```bash
rm -rf /tmp/napda_e2e_site && mkdir -p /tmp/napda_e2e_site/recordings
cp -r tests/e2e_dashboard/* /tmp/napda_e2e_site/
cp -r tests/e2e_recordings/* /tmp/napda_e2e_site/recordings/
python3 -m http.server 4179 --directory /tmp/napda_e2e_site
# 브라우저에서 http://127.0.0.1:4179 접속
```

문제가 없으면 해당 파일만 커밋·푸시합니다 (`Deploy E2E Dashboard (GitHub Pages)` 워크플로가 자동 실행됩니다).

```bash
git add tests/e2e_recordings/<파일명>.mp4 tests/e2e_recordings/shots/<feature_slug> tests/e2e_recordings/manifest.json
git commit -m "docs(tests): add <TC_ID> E2E recording and screenshots"
git push origin main
```

---

## 3. `manifest.json` 필드 레퍼런스

| 필드 | 필수 여부 | 허용 값 / 설명 |
|---|---|---|
| `domains[]` | 루트 필수 | 도메인 탭·갤러리 그룹 정의 (`id`, `name`, `description`) |
| `id` | 케이스 필수 | 테스트 케이스 ID (예: `E2E-ABC-B`, `E2E-L09a`) |
| `domain` | 케이스 필수 | `"creation"` \| `"discovery"` \| `"billing"` \| `"auth"` \| `"profile"` \| `"live"` |
| `title` | 케이스 필수 | 카드 및 표에 표시할 한국어 제목 |
| `owner` | 케이스 필수 | `"me"` (나 · A안) \| `"siwoo"` (시우님 · B안) \| `"sangyoon"` (상윤님 · C안) |
| `env` | 케이스 필수 | `"local"` \| `"live"` |
| `status` | 케이스 필수 | `"pass"` \| `"todo"` |
| `fr` | 케이스 필수 | 관련 FR/트랙 배지 문자열 (예: `"FR-003 · FR-005"`) |
| `video` | `pass` 영상 시 필수 | `"./recordings/<파일명>.mp4"` (`null` 또는 생략 시 하단 체크리스트 표에만 표시) |
| `poster` | `video` 있을 때 권장 | 비디오 썸네일 포스터 `"./recordings/shots/<feature>/<step>.webp"` (초기 흰 로딩 화면 방지) |
| `screenshots[]` | `pass` 시 권장 | 단계별 캡처 배열 `[{ "label": "단계명", "src": "./recordings/shots/<feature>/<step>.webp" }]` |
| `expectedVideo` | `todo` 시 권장 | 예정 파일명 (예: `"abc_B_hook_e2e.mp4"`) |
| `durationSec`, `sizeKb` | `video` 있을 때 | 재생 시간(초), 파일 크기(KB) |
| `checks` | 권장 | 검증한 핵심 항목 문자열 배열 (`string[]`) |

---

## 4. 자주 겪는 문제 (FAQ)

- **`index.html`을 더블클릭(`file://`)으로 열었더니 "manifest.json 로드 실패"가 뜹니다.**
  - 브라우저 보안 정책상 `file://`에서는 `fetch('./recordings/manifest.json')`가 차단됩니다. 위 Step 3의 `python3 -m http.server` 또는 https://muzuksazo.github.io/nepda.official/ 를 이용하세요.
- **영상 소리는 나오는데 화면이 검거나 재생이 안 됩니다.**
  - 원본 코덱이 H.265/HEVC이거나 `yuv444p`인 경우가 많습니다. Step 1의 `ffmpeg` 명령(`-c:v libx264 -pix_fmt yuv420p -movflags +faststart`)으로 재인코딩하면 모든 브라우저에서 재생됩니다.
- **`.mp4` 파일을 `git add` 할 때 `.gitignore` 때문에 무시됩니다.**
  - 루트 [`.gitignore`](../../.gitignore)에 `!tests/e2e_recordings/*.mp4`가 등록되어 있습니다. 반드시 [`tests/e2e_recordings/`](../e2e_recordings/) 폴더 **바로 아래**에 1단계 깊이로 두세요.
- **절대 커밋하면 안 되는 것**: `.env` 파일, API 키/세션 시크릿, `.db` 임시 파일, 수십 MB 이상의 대용량 원본 미디어 파일.
