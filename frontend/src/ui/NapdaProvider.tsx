import { useSyncExternalStore, type ReactNode } from 'react';
import './styles.css';

/** 실제로 그려지는 모드 */
export type ThemeMode = 'light' | 'dark';
/** 사용자가 고르는 화면 모드: 기기 설정을 따르거나(system) 직접 고른다 */
export type ThemeSetting = ThemeMode | 'system';

const DARK_QUERY = '(prefers-color-scheme: dark)';

function subscribeSystemDark(onChange: () => void) {
  const query = window.matchMedia(DARK_QUERY);
  query.addEventListener('change', onChange);
  return () => query.removeEventListener('change', onChange);
}

const getSystemDark = () => window.matchMedia(DARK_QUERY).matches;
const getServerSystemDark = () => false;

export interface NapdaProviderProps {
  /** 'system'이면 기기의 라이트/다크 설정을 따라가고, 기기 설정이 바뀌면 바로 반영한다 */
  mode?: ThemeSetting;
  children: ReactNode;
}

/** 앱·스토리북 공통 루트: 냅다 토큰(/DESIGN.md)과 라이트/다크 모드 */
export function NapdaProvider({ mode = 'light', children }: NapdaProviderProps) {
  const isSystemDark = useSyncExternalStore(subscribeSystemDark, getSystemDark, getServerSystemDark);
  const resolved: ThemeMode = mode === 'system' ? (isSystemDark ? 'dark' : 'light') : mode;
  return (
    <div className="napda-root" data-theme={resolved}>
      {children}
    </div>
  );
}
