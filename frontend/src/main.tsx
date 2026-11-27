import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import './index.css';
import App from './App.tsx';
import { NapdaQueryProvider } from './api/NapdaQueryProvider.tsx';
import { AuthProvider } from './auth';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <NapdaQueryProvider>
      <AuthProvider>
        <App />
      </AuthProvider>
    </NapdaQueryProvider>
  </StrictMode>,
);
