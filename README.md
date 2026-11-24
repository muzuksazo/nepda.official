# 훅컷 (HookCut)

광고 영상 앞에 훅을 붙여 세로 숏폼(9:16)을 만드는 프로토타입입니다.

- 사이트: https://hookcut-sandy.vercel.app
- `index.html` · `three_render.js` · `render_bridge.js`: 브라우저에서 도는 편집 화면
- `api/`: Vercel 서버 함수. `GEMINI_API_KEY`, `HOOKCUT_PASSWORD` 환경 변수를 Vercel 설정에 넣어야 동작합니다. 키는 저장소에 올리지 마세요.
- 블렌더 렌더는 각자 PC의 로컬 서버가 필요합니다.
