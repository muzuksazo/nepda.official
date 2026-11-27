import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import './index.css';
import App from './App.tsx';
import { NapdaQueryProvider } from './api/NapdaQueryProvider.tsx';
import { AuthProvider } from './auth';
import { setAccessToken } from './api/mutator';

// 개발용 세션 토큰은 로컬 개발에서만 사용하고 운영에서는 로그인 세션을 사용한다.
const devToken = import.meta.env.DEV ? (import.meta.env.VITE_DEV_ACCESS_TOKEN as string | undefined) : undefined;
if (devToken) setAccessToken(devToken);

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <NapdaQueryProvider>
      <AuthProvider>
        <App />
      </AuthProvider>
    </NapdaQueryProvider>
  </StrictMode>,
);
