import type { ReactNode } from 'react';
import './styles.css';

export type ThemeMode = 'light' | 'dark';

export interface NapdaProviderProps {
  mode?: ThemeMode;
  children: ReactNode;
}

/** 앱·스토리북 공통 루트: 냅다 토큰(/DESIGN.md)과 라이트/다크 모드 */
export function NapdaProvider({ mode = 'light', children }: NapdaProviderProps) {
  return (
    <div className="napda-root" data-theme={mode}>
      {children}
    </div>
  );
}
