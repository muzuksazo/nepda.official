import { useEffect, useRef, useState } from 'react';
import { useAuth } from './authContext';
import { initializeGis } from './gis';

export interface GoogleSignInButtonProps {
  theme?: 'outline' | 'filled_black';
  text?: 'signin_with' | 'signup_with' | 'continue_with' | 'signin';
  shape?: 'rectangular' | 'pill';
  size?: 'large' | 'medium' | 'small';
  className?: string;
}

export function GoogleSignInButton({
  theme = 'outline',
  text = 'continue_with',
  shape = 'pill',
  size = 'large',
  className,
}: GoogleSignInButtonProps) {
  const { clientId, signInWithCredential, isSubmitting, error } = useAuth();
  const containerRef = useRef<HTMLDivElement>(null);
  const [scriptError, setScriptError] = useState<string | null>(null);
  const [retryTick, setRetryTick] = useState(0);

  useEffect(() => {
    const el = containerRef.current;
    if (!clientId || !el) {
      return;
    }

    let cancelled = false;
    setScriptError(null);

    void initializeGis(clientId, (credential) => {
      void signInWithCredential(credential);
    })
      .then((gis) => {
        if (cancelled || !containerRef.current) {
          return;
        }
        const measured = containerRef.current.clientWidth || 320;
        const width = Math.min(400, Math.max(200, Math.round(measured)));
        containerRef.current.innerHTML = '';
        gis.renderButton(containerRef.current, {
          type: 'standard',
          theme,
          size,
          text,
          shape,
          width,
          locale: 'ko',
        });
      })
      .catch(() => {
        if (!cancelled) {
          setScriptError('구글 로그인 스크립트를 불러오지 못했어요.');
        }
      });

    return () => {
      cancelled = true;
      el.innerHTML = '';
    };
  }, [clientId, retryTick, shape, signInWithCredential, size, text, theme]);

  if (!clientId) {
    return (
      <div className={`napda-gis-slot${className ? ` ${className}` : ''}`}>
        <div className="napda-gis-notice" role="status">
          <code>frontend/.env.local</code>에 <code>VITE_GOOGLE_CLIENT_ID</code>를 설정하면
          공식 Google 로그인 버튼이 표시돼요. (백엔드 <code>GOOGLE_CLIENT_ID</code>와 동일한 값)
        </div>
      </div>
    );
  }

  return (
    <div className={`napda-gis-slot${className ? ` ${className}` : ''}`}>
      <div
        ref={containerRef}
        className="napda-gis-button"
        aria-busy={isSubmitting || undefined}
      />
      {isSubmitting ? (
        <p className="n-small n-muted" role="status">
          로그인하는 중...
        </p>
      ) : null}
      {scriptError ? (
        <div className="napda-gis-notice" role="alert">
          <p>{scriptError}</p>
          <button
            type="button"
            className="n-link-btn"
            onClick={() => setRetryTick((t) => t + 1)}
          >
            다시 불러오기
          </button>
        </div>
      ) : null}
      {error ? (
        <p className="napda-gis-error" role="alert">
          {error}
        </p>
      ) : null}
    </div>
  );
}
