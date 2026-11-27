# 프론트엔드 CI/CD

운영 주소: https://napda.vercel.app

## 배포 흐름

1. `main` 대상 PR과 `main` push에서 `.github/workflows/ci-frontend.yml`이 실행됩니다.
2. Node.js 26에서 `npm ci`, `npm run lint`, `npm run build`를 실행합니다. 빌드에는 TypeScript 검사가 포함됩니다.
3. Vercel Git 연동이 브랜치의 미리보기와 `main`의 운영 빌드를 만듭니다. 빌드 자체에서도 린트와 타입 검사를 실행합니다.
4. 운영 도메인은 GitHub의 `Frontend Lint & Build` 검사 성공 후에만 새 배포로 전환됩니다.
5. Vercel이 성공한 배포를 GitHub에 알리면 `.github/workflows/cd-frontend.yml`이 HTML, JavaScript, `/health`, 비로그인 `/v1/auth/me` 응답을 확인합니다. 수동 실행 시에는 운영 주소를 확인합니다. 이 검사는 배포 후 상태를 보고하며 자동 롤백하지 않습니다.

백엔드 배포 워크플로와 `VERCEL_BACKEND_*` 시크릿은 별도로 관리합니다. 프론트 배포는 Vercel Git 연동을 사용하므로 GitHub Actions용 Vercel 토큰이 필요하지 않습니다.

## Vercel 프로젝트 설정

- 팀: `scpo2887-6104`
- 프로젝트: `napda-frontend`
- Git 저장소: `muzuksazo/nepda.official`
- Production Branch: `main`
- Root Directory: `frontend`
- Framework: `Vite`
- Node.js: `26.x`
- Install Command: `npm ci`
- Build Command: `npm run lint && npm run build`
- Output Directory: `dist`
- Deployment Check: `Frontend CI` — GitHub check `Frontend Lint & Build`, 운영 도메인 할당 차단, 제한 시간 900초

`frontend/vercel.json`의 `/v1/*`, `/health` rewrite가 `https://napda-api.vercel.app`으로 요청을 전달합니다. 프론트와 같은 출처로 요청하도록 운영 `VITE_API_BASE_URL`은 비워 둡니다.

Google 로그인을 활성화하려면 Vercel 프로젝트의 Production/Preview 환경에 공개 OAuth 웹 클라이언트 ID인 `VITE_GOOGLE_CLIENT_ID`를 설정하고 다시 배포해야 합니다. Google 허용 JavaScript 출처와 백엔드의 클라이언트 ID도 일치해야 합니다. `.env` 파일이나 비밀 키를 저장소에 올리지 않습니다.

## 확인 및 복구

```powershell
cd frontend
npm ci
npm run lint
npm run build
node scripts/check-deployment.mjs
```

CI가 실패하면 GitHub Actions 로그에서 실패 단계를 확인합니다. 배포 상태와 미리보기 주소는 Vercel의 `napda-frontend` 프로젝트에서 확인합니다. GitHub 검사가 취소되거나 시간 초과한 경우 해당 커밋의 Frontend CI를 다시 실행하고 Vercel 상태를 확인합니다.

운영 문제가 있으면 수정 PR을 병합하거나 Vercel에서 이전 정상 운영 배포로 되돌립니다. Vercel 롤백은 이후 자동 도메인 할당을 중지할 수 있으므로 복구 후 정상 배포를 다시 Promote하여 자동 배포 상태도 확인합니다.
