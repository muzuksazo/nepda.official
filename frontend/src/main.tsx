import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App.tsx'
import { NapdaQueryProvider } from './api/NapdaQueryProvider.tsx'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <NapdaQueryProvider>
      <App />
    </NapdaQueryProvider>
  </StrictMode>,
)
