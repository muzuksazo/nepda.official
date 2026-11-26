import { useEffect, useId, useRef, useState, type KeyboardEvent, type ReactNode } from 'react';
import { Button } from './primitives';

export interface ConfirmSheetProps {
  isOpen: boolean;
  title: string;
  description?: string;
  /** 실행 버튼 문구 (예: "로그아웃", "탈퇴하기") */
  confirmLabel: string;
  /** 그만두는 버튼 문구 */
  cancelLabel?: string;
  /** 되돌릴 수 없는 행동이면 true: 그만두는 쪽을 눈에 띄는 1차 버튼으로 두고, 실행은 조용한 버튼으로 둔다 */
  isDestructive?: boolean;
  onConfirm: () => void;
  /** 그만두기 · 바깥 누르기 · Esc */
  onClose: () => void;
  /** 설명과 버튼 사이에 넣을 내용 (예: 필요한 크레딧 숫자) */
  children?: ReactNode;
}

/**
 * 아래에서 올라오는 확인 시트. 로그아웃·탈퇴처럼 한 번 더 물어봐야 하는 행동에 쓴다.
 * 뒤 화면은 MobileScreen의 isInert로 함께 잠근다.
 */
export function ConfirmSheet({ isOpen, ...rest }: ConfirmSheetProps) {
  return isOpen ? <ConfirmSheetDialog {...rest} /> : null;
}

function ConfirmSheetDialog({
  title,
  description,
  confirmLabel,
  cancelLabel = '취소',
  isDestructive,
  onConfirm,
  onClose,
  children,
}: Omit<ConfirmSheetProps, 'isOpen'>) {
  const titleId = useId();
  const descId = useId();
  const sheetRef = useRef<HTMLDivElement>(null);
  // 시트를 연 버튼을 기억해 두었다가(뒤 화면이 잠기기 전에 읽는다) 닫힐 때 포커스를 돌려준다
  const [opener] = useState(() => (document.activeElement instanceof HTMLElement ? document.activeElement : null));

  useEffect(() => {
    sheetRef.current?.focus();
    return () => opener?.focus();
  }, [opener]);

  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key === 'Escape') {
      event.stopPropagation();
      onClose();
      return;
    }
    if (event.key !== 'Tab') return;
    // Tab이 시트 밖으로 나가지 않게 처음·끝 버튼에서 되돌린다
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

  return (
    <div className="n-sheet-layer">
      <div className="n-sheet-backdrop" onClick={onClose} />
      <div
        ref={sheetRef}
        className="n-sheet"
        role="alertdialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={description ? descId : undefined}
        tabIndex={-1}
        onKeyDown={onKeyDown}
      >
        <h2 id={titleId} className="n-sheet__title">
          {title}
        </h2>
        {description ? (
          <p id={descId} className="n-sheet__desc">
            {description}
          </p>
        ) : null}
        {children}
        <div className="n-sheet__actions">
          {isDestructive ? (
            <>
              <Button label={cancelLabel} isBlock onClick={onClose} />
              <Button label={confirmLabel} variant="ghost" isBlock onClick={onConfirm} />
            </>
          ) : (
            <>
              <Button label={confirmLabel} isBlock onClick={onConfirm} />
              <Button label={cancelLabel} variant="ghost" isBlock onClick={onClose} />
            </>
          )}
        </div>
      </div>
    </div>
  );
}
