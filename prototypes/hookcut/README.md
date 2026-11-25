# 업로드 먼저형 프로토타입

기존 루트 웹앱을 파일 내용 그대로 모은 폴더입니다.

```text
index.html          편집 화면
three_render.js     브라우저 3D 렌더
render_bridge.js    로컬 Blender 연결
api/copy.py         영상 정보·광고 문구 API 구현
api/remix.js        훅 기획 API 구현
```

저장소 루트의 `vercel.json`은 `scripts/build-prototype.mjs`로 정적 파일 3개만 `dist/prototype/`에 복사합니다. 루트 `api/`는 기존 `/api/copy`, `/api/remix` 주소를 이 폴더의 구현에 연결하는 얇은 호환 진입점입니다. 기존 Vercel 프로젝트의 루트 디렉터리는 저장소 최상위를 유지합니다.

```bash
node scripts/build-prototype.mjs
.venv/bin/python -m http.server 3000 --bind 127.0.0.1 --directory dist/prototype
```

위 정적 서버는 화면 확인용입니다. AI API는 Vercel에서 실행하며 `GEMINI_API_KEY`, `HOOKCUT_PASSWORD` 설정을 사용합니다. Blender 보조 서버는 저장소에 포함되어 있지 않습니다.

이 프로토타입의 업로드 먼저형·일괄 출력·Blender 연결은 PRD의 프로덕션 구현 완료를 의미하지 않습니다.
