import { useState } from 'react';
import { setAccessToken } from './api/mutator';
import { NapdaApp } from './app/NapdaApp';
import { NapdaProvider, type ThemeSetting } from './ui/NapdaProvider';

// 로그인 화면을 연결하기 전까지 쓰는 개발용 세션 토큰 (backend/bridge-dev/dev_token.py 로 발급).
// 없으면 서버의 napda_session 쿠키에 맡긴다.
const devToken = import.meta.env.VITE_DEV_ACCESS_TOKEN as string | undefined;
if (devToken) setAccessToken(devToken);

function App() {
  const [themeMode, setThemeMode] = useState<ThemeSetting>('system');
  return (
    <NapdaProvider mode={themeMode}>
      <NapdaApp themeMode={themeMode} onThemeModeChange={setThemeMode} />
    </NapdaProvider>
  );
}

export default App;
