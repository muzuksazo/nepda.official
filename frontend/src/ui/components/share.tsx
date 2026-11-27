import { useEffect, useId, useRef, useState, type KeyboardEvent } from 'react';
import { Check, Share, X } from '../icons';
import { Button } from './primitives';

/** 공유할 영상 (커뮤니티 영상) */
export interface ShareVideo {
  id: string;
  creatorName: string;
  productName: string;
  /** 썸네일 글자 — 미리보기 제목으로 쓴다 */
  caption?: string;
  thumbnailUrl?: string;
}

/**
 * 공유를 실제로 하는 쪽(앱)이 넘겨주는 것. 화면은 시트만 그리고, 링크 만들기·복사·기기 공유 창은 여기에 맡긴다.
 * 이 묶음을 넘기지 않으면 화면은 공유 버튼을 보여 주지 않는다.
 */
export interface ShareHandlers {
  /** 영상 공유 링크 (예: https://napda.app/v/v01) */
  shareUrlOf: (id: string) => string;
  /** 기기 공유 창(Web Share API, navigator.share)을 쓸 수 있으면 true → "카톡·인스타로 보내기" */
  canShareNative?: boolean;
  /** 기기 공유 창 열기. 보내고 나면 시트를 닫는다 */
  onShareNative?: (id: string) => void;
  /** 링크를 클립보드에 복사 */
  onCopyLink?: (id: string) => void;
}

export interface ShareSheetProps {
  /** 공유할 영상. null이면 닫힘 */
  video: ShareVideo | null;
  /** 이 영상의 공유 링크 */
  url: string;
  canShareNative?: boolean;
  onShareNative?: () => void;
  onCopyLink?: () => void;
  /** 닫기 · 바깥 누르기 · Esc */
  onClose: () => void;
}

/** 링크를 보이는 그대로 짧게: https://napda.app/v/v01 → napda.app/v/v01 */
function shortUrl(url: string): string {
  return url.replace(/^https?:\/\//, '').replace(/\/$/, '');
}

/**
 * 공유 시트 — 홈 피드·영상 보기의 공유(종이비행기) 버튼에서 올라온다.
 * 받는 사람에게 어떻게 보일지(링크 미리보기) → 보내기. 카톡·인스타 같은 앱 목록은 기기 공유 창에 맡기고,
 * 그 창을 못 쓰는 곳(PC·일부 앱 안 브라우저)에서는 링크 복사만 남긴다.
 */
export function ShareSheet({ video, ...rest }: ShareSheetProps) {
  return video ? <ShareSheetDialog key={video.id} video={video} {...rest} /> : null;
}

function ShareSheetDialog({
  video,
  url,
  canShareNative = false,
  onShareNative,
  onCopyLink,
  onClose,
}: Omit<ShareSheetProps, 'video'> & { video: ShareVideo }) {
  const titleId = useId();
  const sheetRef = useRef<HTMLDivElement>(null);
  const [isCopied, setIsCopied] = useState(false);
  // 시트를 연 버튼을 기억해 두었다가(뒤 화면이 잠기기 전에 읽는다) 닫힐 때 포커스를 돌려준다
  const [opener] = useState(() => (document.activeElement instanceof HTMLElement ? document.activeElement : null));

  useEffect(() => {
    sheetRef.current?.focus();
    return () => opener?.focus();
  }, [opener]);

  // "복사했어요"는 잠깐만 보여 주고 원래 글자로 돌아간다
  useEffect(() => {
    if (!isCopied) return;
    const timer = window.setTimeout(() => setIsCopied(false), 2400);
    return () => window.clearTimeout(timer);
  }, [isCopied]);

  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key === 'Escape') {
      event.stopPropagation();
      onClose();
      return;
    }
    if (event.key !== 'Tab') return;
    const buttons = sheetRef.current?.querySelectorAll<HTMLElement>('button:not(:disabled)');
    if (!buttons || buttons.length === 0) return;
    const first = buttons[0];
    const last = buttons[buttons.length - 1];
    const active = document.activeElement;
    if (event.shiftKey && (active === first || active === sheetRef.current)) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && active === last) {
      event.preventDefault();
      first.focus();
    }
  };

  const title = video.caption?.trim() || `${video.productName} 릴스`;
  const copyButton = (
    <Button
      label={isCopied ? '복사했어요' : '링크 복사'}
      variant={canShareNative ? 'secondary' : 'primary'}
      isBlock
      icon={isCopied ? <Check size={20} strokeWidth={2.5} aria-hidden="true" /> : undefined}
      onClick={() => {
        onCopyLink?.();
        setIsCopied(true);
      }}
    />
  );

  return (
    <div className="n-sheet-layer">
      <div className="n-sheet-backdrop" onClick={onClose} />
      <div
        ref={sheetRef}
        className="n-sheet n-share"
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
        onKeyDown={onKeyDown}
      >
        <div className="n-share__head">
          <h2 id={titleId} className="n-sheet__title">
            공유하기
          </h2>
          <button type="button" className="n-share__close" aria-label="닫기" onClick={onClose}>
            <X size={22} />
          </button>
        </div>

        {/* 받는 사람 쪽에 보일 링크 미리보기 (실제 모양은 카톡·인스타가 정한다) */}
        <div className="n-share__card">
          {video.thumbnailUrl ? (
            <img className="n-share__thumb" src={video.thumbnailUrl} alt="" />
          ) : (
            <span className="n-share__thumb" aria-hidden="true" />
          )}
          <span className="n-share__meta">
            <span className="n-share__title">{title}</span>
            <span className="n-share__sub">
              {video.creatorName} · {video.productName}
            </span>
            <span className="n-share__url">{shortUrl(url)}</span>
          </span>
        </div>

        <div className="n-sheet__actions">
          {canShareNative ? (
            <>
              <Button
                label="카톡·인스타로 보내기"
                isBlock
                icon={<Share size={20} aria-hidden="true" />}
                onClick={onShareNative}
              />
              {copyButton}
            </>
          ) : (
            <>
              {copyButton}
              <p className="n-share__hint">복사해서 카톡이나 인스타 DM에 붙여 넣어요.</p>
            </>
          )}
        </div>

        <p className="napda-visually-hidden" role="status">
          {isCopied ? '링크를 복사했어요' : ''}
        </p>
      </div>
    </div>
  );
}
