import { useId } from 'react';
import { ArrowRight, Check, Lightning } from '../icons';
import { formatWon } from '../format';
import { Badge } from './primitives';

/** 충전 묶음 하나 (가격·크기는 아직 정해지지 않았다 — 예시 값) */
export interface CreditPackage {
  id: string;
  credits: number;
  /** 원 단위 가격 */
  price: number;
  /** "많이 골라요" 배지 */
  isPopular?: boolean;
}

/** 크레딧 숫자 앞의 번개 원 (상단 배지와 같은 모양) */
export function CreditIcon({ size = 'md' }: { size?: 'md' | 'lg' }) {
  return (
    <span className={`n-credit__icon n-credit-icon--${size}`} aria-hidden="true">
      <Lightning size={size === 'lg' ? 14 : 12} strokeWidth={2.5} fill="currentColor" />
    </span>
  );
}

export interface CreditPackagePickerProps {
  label: string;
  packages: readonly CreditPackage[];
  value: string | null;
  onChange: (id: string) => void;
  /** 영상 한 편에 드는 크레딧. 있으면 "영상 약 N편"을 함께 보여 준다 */
  creditsPerVideo?: number;
}

/** 충전 묶음 고르기: 세로로 쌓은 카드 중 하나만 고른다 (라디오 그룹). 고른 카드는 라임 틴트 면 + 체크 */
export function CreditPackagePicker({ label, packages, value, onChange, creditsPerVideo }: CreditPackagePickerProps) {
  const name = useId();
  return (
    <fieldset className="n-field" style={{ border: 0, padding: 0, margin: 0 }}>
      <legend className="n-field__label" style={{ marginBottom: 8, padding: 0 }}>
        {label}
      </legend>
      <div className="n-packages">
        {packages.map((pkg) => {
          const videos = creditsPerVideo ? Math.floor(pkg.credits / creditsPerVideo) : undefined;
          const credits = pkg.credits.toLocaleString('ko-KR');
          const price = formatWon(pkg.price);
          return (
            <label key={pkg.id} className="n-package">
              <input
                type="radio"
                name={name}
                value={pkg.id}
                checked={value === pkg.id}
                aria-label={`${credits} 크레딧, ${price}${videos ? `, 영상 약 ${videos}편` : ''}${pkg.isPopular ? ', 많이 골라요' : ''}`}
                onChange={() => onChange(pkg.id)}
              />
              <span className="n-package__check" aria-hidden="true">
                <Check size={18} strokeWidth={3} />
              </span>
              <span className="n-package__main" aria-hidden="true">
                {/* 라임 번개는 잔액·합계에만 쓰고, 묶음 카드에서는 숫자 + "크레딧"으로 읽게 한다 */}
                <span className="n-package__credits">
                  <span className="n-num">{credits}</span>
                  <span className="n-package__unit">크레딧</span>
                  {pkg.isPopular ? <Badge tone="brand">많이 골라요</Badge> : null}
                </span>
                {videos ? <span className="n-package__videos">영상 약 {videos}편</span> : null}
              </span>
              <span className="n-package__price n-num" aria-hidden="true">
                {price}
              </span>
            </label>
          );
        })}
      </div>
    </fieldset>
  );
}

/** 잔액이 어떻게 바뀌는지: 5 → 105. 앞 숫자는 흐리게, 뒤 숫자는 크게 */
export function CreditChange({ from, to }: { from: number; to: number }) {
  return (
    <p className="n-credit-change" aria-label={`충전 전 ${from.toLocaleString('ko-KR')}, 지금 ${to.toLocaleString('ko-KR')} 크레딧`}>
      <span className="n-credit-change__from n-num" aria-hidden="true">
        {from.toLocaleString('ko-KR')}
      </span>
      <ArrowRight size={20} aria-hidden="true" />
      <span className="n-credit-change__to" aria-hidden="true">
        <CreditIcon size="lg" />
        <span className="n-num">{to.toLocaleString('ko-KR')}</span>
      </span>
    </p>
  );
}
