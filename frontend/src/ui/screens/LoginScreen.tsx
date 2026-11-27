import { useEffect, useState, type ReactNode } from 'react';
import { brand } from '../brand';
import { BrandHeader, Button, Mascot, MobileScreen, Note, Stack, TermsSheet, type AgreementDoc, type Agreements } from '../components';
import { Check } from '../icons';

export interface LoginScreenProps {
  /** welcome: 처음 들어오거나 로그아웃한 뒤 · expired: 로그인이 풀려서(세션 7일) 다시 들어올 때 */
  reason?: 'welcome' | 'expired';
  /** 위쪽에 부채꼴로 펼쳐 보여 줄 냅다 영상 썸네일 3장 (9:16). 없으면 냅다곰 */
  showcase?: readonly string[];
  /** 구글이 계정을 돌려준 뒤 서버 확인(POST /v1/auth/google)을 기다리는 중 */
  isSigningIn?: boolean;
  /** 로그인이 실패했을 때. 사용자가 구글 창을 그냥 닫은 것은 실패가 아니다 — 아무것도 띄우지 않는다 */
  hasError?: boolean;
  /** 인스타그램·카카오톡 같은 앱 안 브라우저라서 구글 로그인이 막힐 수 있을 때 */
  isInAppBrowser?: boolean;
  /** 로그인 버튼 (signInSlot을 넣지 않았을 때의 대신 버튼) */
  onSignIn?: () => void;
  /**
   * 로그인 버튼 자리. 실제 앱은 여기에 Google 공식 버튼(GIS renderButton)을 넣는다 — 구글 로고 버튼을 직접 그리지 않는다.
   * 권장 설정: theme 'filled_black' · size 'large' · shape 'pill' · text 'continue_with' · locale 'ko' · width 화면 너비(최대 400)
   */
  signInSlot?: ReactNode;
  /** 앱 안 브라우저일 때 "주소 복사" */
  onCopyLink?: () => void;
  /** 구글로 처음 들어온 사람: 약관 동의 시트를 띄운다 */
  isTermsOpen?: boolean;
  /** 필수 약관에 모두 동의하고 "동의하고 계속"을 눌렀을 때 → 닉네임 정하기로 */
  onAgreeTerms?: (agreements: Agreements) => void;
  /** 약관 시트를 닫았을 때 (가입을 그만둔다) */
  onCloseTerms?: () => void;
  onOpenDoc?: (doc: AgreementDoc) => void;
}

/**
 * 로그인 — 구글 계정 하나로 가입과 로그인을 같이 한다 (비밀번호·입력 칸 없음).
 * 이미 가입한 사람은 바로 홈으로, 처음인 사람은 약관 시트 → 닉네임 정하기를 거친다.
 */
export function LoginScreen({
  reason = 'welcome',
  showcase = [],
  isSigningIn = false,
  hasError = false,
  isInAppBrowser = false,
  onSignIn,
  signInSlot,
  onCopyLink,
  isTermsOpen = false,
  onAgreeTerms,
  onCloseTerms,
  onOpenDoc,
}: LoginScreenProps) {
  const [isCopied, setIsCopied] = useState(false);
  const isExpired = reason === 'expired';
  const hasShowcase = !isExpired && showcase.length >= 3;

  // "복사했어요"는 잠깐만 보여 주고 원래 글자로 돌아간다
  useEffect(() => {
    if (!isCopied) return;
    const timer = window.setTimeout(() => setIsCopied(false), 2400);
    return () => window.clearTimeout(timer);
  }, [isCopied]);

  let actions: ReactNode;
  if (isSigningIn) {
    // 확인하는 동안에는 버튼을 잠가 두 번 눌리지 않게 한다
    actions = <Button label="들어가는 중…" isBlock isDisabled />;
  } else if (isInAppBrowser) {
    actions = (
      <>
        <Button
          label={isCopied ? '복사했어요' : '주소 복사'}
          isBlock
          icon={isCopied ? <Check size={22} strokeWidth={2.5} aria-hidden="true" /> : undefined}
          onClick={() => {
            onCopyLink?.();
            setIsCopied(true);
          }}
        />
        {/* 앱 안 브라우저 판별이 틀릴 수도 있어 막다른 길로 두지 않는다 */}
        <Button label="그래도 여기서 로그인해 보기" variant="ghost" size="md" isBlock onClick={onSignIn} />
      </>
    );
  } else {
    actions = (
      <>
        {signInSlot ? (
          <div className="n-login__google">{signInSlot}</div>
        ) : (
          <Button label={isExpired ? '구글 계정으로 다시 로그인' : '구글 계정으로 계속하기'} isBlock onClick={onSignIn} />
        )}
        {isExpired ? null : <p className="n-login__note">처음이면 바로 가입돼요</p>}
      </>
    );
  }

  return (
    <>
      <MobileScreen
        isInert={isTermsOpen}
        header={<BrandHeader />}
        footer={
          <>
            {isInAppBrowser && !isSigningIn ? (
              <Note title="이 앱 안에서는 구글 로그인이 막혀 있어요">
                <span className="n-small n-muted">복사해서 Safari나 Chrome에 붙여 넣어요.</span>
              </Note>
            ) : null}
            {hasError && !isSigningIn && !isInAppBrowser ? (
              <div role="alert">
                <Note title="로그인이 안 됐어요">
                  <span className="n-small n-muted">잠깐 뒤에 다시 눌러 주세요.</span>
                </Note>
              </div>
            ) : null}

            {actions}

            <p className="napda-visually-hidden" role="status">
              {isSigningIn ? '로그인하고 있어요' : isCopied ? '주소를 복사했어요' : ''}
            </p>
          </>
        }
      >
        <Stack gap={28} align="center" justify="center" style={{ flex: 1, textAlign: 'center' }}>
          {hasShowcase ? (
            // 냅다로 만든 릴스 세 장을 부채꼴로: 무엇을 만드는 서비스인지 한눈에 보인다 (장식)
            <div className="n-login__showcase" aria-hidden="true">
              {showcase.slice(0, 3).map((src, i) => (
                <img key={src} className={`n-login__card n-login__card--${i}`} src={src} alt="" />
              ))}
            </div>
          ) : (
            <Mascot src={isExpired ? brand.mascot.lying : brand.mascot.happy} />
          )}

          <Stack gap={8} align="center">
            <h2 className="n-display n-display--xl">
              {isExpired ? (
                '로그인이 풀렸어요'
              ) : (
                <>
                  릴스 광고,
                  <br />
                  <span className="n-mark">냅다</span> 만들어 볼까요?
                </>
              )}
            </h2>
            <p className="n-muted">
              {isExpired ? '다시 들어오면 만들던 영상이 그대로 있어요.' : '구글 계정 하나면 가입도 로그인도 끝.'}
            </p>
          </Stack>
        </Stack>
      </MobileScreen>

      <TermsSheet
        isOpen={isTermsOpen}
        onAgree={(agreements) => onAgreeTerms?.(agreements)}
        onClose={() => onCloseTerms?.()}
        onOpenDoc={onOpenDoc}
      />
    </>
  );
}
