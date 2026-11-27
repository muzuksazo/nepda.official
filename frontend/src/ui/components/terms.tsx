import { useEffect, useId, useRef, useState, type KeyboardEvent } from 'react';
import { Check, X } from '../icons';
import { Button } from './primitives';
import { AGREEMENTS, NO_AGREEMENTS, type AgreementDoc, type Agreements } from './termsData';

export interface TermsSheetProps {
  isOpen: boolean;
  /** 필수 항목을 모두 체크하고 "동의하고 계속"을 눌렀을 때 (선택 항목 동의 여부도 함께) */
  onAgree: (agreements: Agreements) => void;
  /** 닫기 · 바깥 누르기 · Esc — 가입을 그만둔다 (로그인 화면에 그대로 남는다) */
  onClose: () => void;
  onOpenDoc?: (doc: AgreementDoc) => void;
  /** 처음부터 체크해 둘 항목 (스토리·테스트용) */
  initialAgreements?: Partial<Agreements>;
}

/**
 * 약관 동의 시트 — 구글로 처음 들어온 사람에게 한 번만 띄운다.
 * "모두 동의해요" 한 번으로 끝낼 수 있고, 항목마다 따로 고르거나 "보기"로 전문을 열 수 있다.
 * 필수를 모두 체크해야 "동의하고 계속"이 켜진다.
 */
export function TermsSheet({ isOpen, ...rest }: TermsSheetProps) {
  return isOpen ? <TermsSheetDialog {...rest} /> : null;
}

function TermsSheetDialog({ onAgree, onClose, onOpenDoc, initialAgreements }: Omit<TermsSheetProps, 'isOpen'>) {
  const titleId = useId();
  const sheetRef = useRef<HTMLDivElement>(null);
  const allRef = useRef<HTMLInputElement>(null);
  const [agreements, setAgreements] = useState<Agreements>({ ...NO_AGREEMENTS, ...initialAgreements });
  const [opener] = useState(() => (document.activeElement instanceof HTMLElement ? document.activeElement : null));

  const checkedCount = AGREEMENTS.filter((item) => agreements[item.key]).length;
  const isAll = checkedCount === AGREEMENTS.length;
  const isRequiredDone = AGREEMENTS.every((item) => !item.isRequired || agreements[item.key]);

  useEffect(() => {
    sheetRef.current?.focus();
    return () => opener?.focus();
  }, [opener]);

  // 일부만 체크했을 때 "모두 동의해요"는 반쯤 찬 상태로 보인다(스크린 리더에도 "일부 선택")
  useEffect(() => {
    if (allRef.current) allRef.current.indeterminate = checkedCount > 0 && !isAll;
  }, [checkedCount, isAll]);

  const setAll = (value: boolean) =>
    setAgreements(Object.fromEntries(AGREEMENTS.map((item) => [item.key, value])) as Agreements);

  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key === 'Escape') {
      event.stopPropagation();
      onClose();
      return;
    }
    if (event.key !== 'Tab') return;
    const focusables = sheetRef.current?.querySelectorAll<HTMLElement>('button:not(:disabled), input');
    if (!focusables || focusables.length === 0) return;
    const first = focusables[0];
    const last = focusables[focusables.length - 1];
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
        className="n-sheet n-terms"
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
        onKeyDown={onKeyDown}
      >
        <div className="n-terms__head">
          <h2 id={titleId} className="n-sheet__title">
            시작하기 전에
            <br />
            이것만 확인해요
          </h2>
          <button type="button" className="n-terms__close" aria-label="가입 그만두기" onClick={onClose}>
            <X size={22} />
          </button>
        </div>

        <label className="n-agree n-agree--all">
          <input ref={allRef} type="checkbox" checked={isAll} onChange={(e) => setAll(e.target.checked)} />
          <span className="n-agree__box" aria-hidden="true">
            <Check size={18} strokeWidth={3} />
          </span>
          <span className="n-agree__label">모두 동의해요</span>
        </label>

        <ul className="n-agree-list">
          {AGREEMENTS.map((item) => (
            <li key={item.key} className="n-agree-list__row">
              <label className="n-agree">
                <input
                  type="checkbox"
                  checked={agreements[item.key]}
                  onChange={(e) => setAgreements((prev) => ({ ...prev, [item.key]: e.target.checked }))}
                />
                <span className="n-agree__box" aria-hidden="true">
                  <Check size={18} strokeWidth={3} />
                </span>
                <span className="n-agree__text">
                  <span className="n-agree__label">
                    <span className={`n-agree__tag${item.isRequired ? '' : ' n-agree__tag--optional'}`}>
                      {item.isRequired ? '필수' : '선택'}
                    </span>
                    {item.label}
                  </span>
                  {item.hint ? <span className="n-agree__hint">{item.hint}</span> : null}
                </span>
              </label>
              {item.doc ? (
                <button
                  type="button"
                  className="n-agree__view"
                  aria-label={`${item.label.replace(/에 동의해요$|이에요$/, '')} 전문 보기`}
                  onClick={() => item.doc && onOpenDoc?.(item.doc)}
                >
                  보기
                </button>
              ) : null}
            </li>
          ))}
        </ul>

        <div className="n-sheet__actions">
          <Button label="동의하고 계속" isBlock isDisabled={!isRequiredDone} onClick={() => onAgree(agreements)} />
        </div>
      </div>
    </div>
  );
}
