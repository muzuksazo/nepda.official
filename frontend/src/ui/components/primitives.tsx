import { useId, useState, type CSSProperties, type ReactNode } from 'react';
import { Check, Clock, Info, Upload, X } from '../icons';

/* ---------- 레이아웃 ---------- */

export interface StackProps {
  gap?: number;
  direction?: 'column' | 'row';
  align?: CSSProperties['alignItems'];
  justify?: CSSProperties['justifyContent'];
  wrap?: boolean;
  style?: CSSProperties;
  as?: 'div' | 'section';
  children: ReactNode;
}

/** 간격만 정하는 묶음. gap은 px(4의 배수) */
export function Stack({ gap = 0, direction = 'column', align, justify, wrap, style, as: Tag = 'div', children }: StackProps) {
  return (
    <Tag
      className={direction === 'row' ? 'n-row' : 'n-stack'}
      style={{ gap, alignItems: align, justifyContent: justify, flexWrap: wrap ? 'wrap' : undefined, ...style }}
    >
      {children}
    </Tag>
  );
}

/* ---------- 버튼 ---------- */

export interface ButtonProps {
  label: string;
  /** tonal = 테두리 없는 회색 면 (1차 버튼 옆의 보조 행동) */
  variant?: 'primary' | 'secondary' | 'tonal' | 'ghost';
  size?: 'lg' | 'md' | 'sm';
  isBlock?: boolean;
  isDisabled?: boolean;
  icon?: ReactNode;
  onClick?: () => void;
}

/** 1차 = 검정 면(라이트)/흰 면(다크). 형광 라임은 버튼 면에 쓰지 않는다. */
export function Button({ label, variant = 'primary', size = 'lg', isBlock, isDisabled, icon, onClick }: ButtonProps) {
  return (
    <button
      type="button"
      className={`n-btn n-btn--${variant} n-btn--${size}${isBlock ? ' n-btn--block' : ''}`}
      disabled={isDisabled}
      onClick={onClick}
    >
      {icon}
      {label}
    </button>
  );
}

export interface IconButtonProps {
  label: string;
  icon: ReactNode;
  variant?: 'ghost' | 'solid';
  onClick?: () => void;
}

export function IconButton({ label, icon, variant = 'ghost', onClick }: IconButtonProps) {
  return (
    <button type="button" className={`n-icon-btn n-icon-btn--${variant}`} aria-label={label} onClick={onClick}>
      {icon}
    </button>
  );
}

/* ---------- 입력 ---------- */

export interface TextFieldProps {
  label: string;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  description?: string;
  isRequired?: boolean;
  isOptional?: boolean;
  isMultiline?: boolean;
  rows?: number;
  hasClear?: boolean;
  /** 넣을 수 있는 글자 수 한도 */
  maxLength?: number;
  /** 입력 아래 한 줄 (확인 결과·오류). 바뀌면 스크린 리더가 읽는다 */
  message?: ReactNode;
  /** error면 빨간 테두리 + 빨간 문구 (빨강은 입력 오류에만 쓴다) */
  messageTone?: 'neutral' | 'success' | 'error';
  /** 오른쪽 아래에 "5/12" 글자 수 (maxLength가 있을 때) */
  hasCounter?: boolean;
  autoComplete?: string;
}

/** 라벨은 항상 입력 위에 보인다(placeholder로 라벨을 대신하지 않는다) */
export function TextField({
  label,
  value,
  onChange,
  placeholder,
  description,
  isRequired,
  isOptional,
  isMultiline,
  rows = 3,
  hasClear,
  maxLength,
  message,
  messageTone = 'neutral',
  hasCounter,
  autoComplete,
}: TextFieldProps) {
  const id = useId();
  const descId = description ? `${id}-desc` : undefined;
  const messageId = `${id}-msg`;
  const isError = messageTone === 'error' && Boolean(message);
  const showFoot = message !== undefined || (hasCounter && maxLength);
  const common = {
    id,
    className: `n-input${isError ? ' is-invalid' : ''}`,
    value,
    placeholder,
    required: isRequired,
    maxLength,
    autoComplete,
    'aria-invalid': isError || undefined,
    'aria-describedby': [descId, showFoot ? messageId : undefined].filter(Boolean).join(' ') || undefined,
  };
  return (
    <div className="n-field">
      <label className="n-field__label" htmlFor={id}>
        {label}
        {isRequired ? <span className="n-field__hint">필수</span> : null}
        {isOptional ? <span className="n-field__hint">선택</span> : null}
      </label>
      {description ? (
        <p className="n-field__desc" id={descId}>
          {description}
        </p>
      ) : null}
      {isMultiline ? (
        <textarea {...common} rows={rows} onChange={(e) => onChange(e.target.value)} />
      ) : hasClear ? (
        <div className="n-input-wrap">
          <input {...common} type="text" onChange={(e) => onChange(e.target.value)} />
          {value ? (
            <span className="n-input-clear">
              <IconButton label={`${label} 지우기`} icon={<X size={18} />} onClick={() => onChange('')} />
            </span>
          ) : null}
        </div>
      ) : (
        <input {...common} type="text" onChange={(e) => onChange(e.target.value)} />
      )}
      {showFoot ? (
        <div className="n-field__foot">
          <p id={messageId} className={`n-field__msg n-field__msg--${messageTone}`} aria-live="polite">
            {message}
          </p>
          {hasCounter && maxLength ? (
            <span className="n-field__count n-num" aria-hidden="true">
              {value.length}/{maxLength}
            </span>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

export interface ChoiceChipsProps {
  label: string;
  options: readonly string[];
  value: string | null;
  onChange: (value: string) => void;
}

/** 하나만 고르는 선택지 (라디오 그룹) — 균등 타일, 선택되면 연라임 면 + 작은 체크 */
export function ChoiceChips({ label, options, value, onChange }: ChoiceChipsProps) {
  const name = useId();
  return (
    <fieldset className="n-field" style={{ border: 0, padding: 0, margin: 0 }}>
      <legend className="n-field__label" style={{ marginBottom: 8, padding: 0 }}>
        {label}
      </legend>
      <div className="n-chips">
        {options.map((opt) => (
          <label key={opt} className="n-chip">
            <input type="radio" name={name} value={opt} checked={value === opt} onChange={() => onChange(opt)} />
            <span className="n-chip__tile">
              <span className="n-chip__check" aria-hidden="true">
                <Check size={18} strokeWidth={3} />
              </span>
              {opt}
            </span>
          </label>
        ))}
      </div>
    </fieldset>
  );
}

export interface FilePickerProps {
  label: string;
  accept: string;
  value: File | null;
  onChange: (file: File | null) => void;
  placeholder: string;
  description?: string;
  isOptional?: boolean;
  isLabelHidden?: boolean;
  variant?: 'dropzone' | 'compact';
}

/** 파일 선택: 드롭존(끌어다 놓기 가능) 또는 한 줄짜리 */
export function FilePicker({
  label,
  accept,
  value,
  onChange,
  placeholder,
  description,
  isOptional,
  isLabelHidden,
  variant = 'dropzone',
}: FilePickerProps) {
  const id = useId();
  const [isOver, setIsOver] = useState(false);
  const className = [
    'n-drop',
    variant === 'compact' && 'n-drop--compact',
    isOver && 'is-over',
    value && 'is-filled',
  ]
    .filter(Boolean)
    .join(' ');

  return (
    <div className="n-field">
      <label className={isLabelHidden ? 'napda-visually-hidden' : 'n-field__label'} htmlFor={id}>
        {label}
        {isOptional ? <span className="n-field__hint">선택</span> : null}
      </label>
      {description ? <p className="n-field__desc">{description}</p> : null}
      <div
        className={className}
        onDragOver={(e) => {
          e.preventDefault();
          setIsOver(true);
        }}
        onDragLeave={() => setIsOver(false)}
        onDrop={() => setIsOver(false)}
      >
        <input id={id} type="file" accept={accept} onChange={(e) => onChange(e.target.files?.[0] ?? null)} />
        {value ? <Check size={variant === 'compact' ? 18 : 28} /> : <Upload size={variant === 'compact' ? 18 : 28} />}
        <span className={variant === 'compact' ? undefined : 'n-small'}>
          {value ? value.name : placeholder}
        </span>
        {value && variant === 'dropzone' ? <span className="n-caption">바꾸려면 다시 눌러요</span> : null}
      </div>
    </div>
  );
}

/* ---------- 표시 ---------- */

export interface BadgeProps {
  tone?: 'neutral' | 'brand' | 'pending';
  icon?: ReactNode;
  children: ReactNode;
}

/** brand = 검정 면 + 라임 글자(작은 강조), pending = 회색 점선(기획 미정 표시) */
export function Badge({ tone = 'neutral', icon, children }: BadgeProps) {
  return (
    <span className={`n-badge n-badge--${tone}`}>
      {icon}
      {children}
    </span>
  );
}

/** 기획에서 아직 정해지지 않은 값(OQ/FR 번호) — 출시 전 모두 사라질 표시 */
export function PendingBadge({ children }: { children: string }) {
  return (
    <Badge tone="pending" icon={<Clock size={12} aria-hidden="true" />}>
      {children}
    </Badge>
  );
}

/** 칸이 끊어진 게이지: max칸 중 value칸을 라임으로 채운다 */
export function ProgressBar({ value, max, label }: { value: number; max: number; label: string }) {
  return (
    <div className="n-progress" role="progressbar" aria-label={label} aria-valuemin={0} aria-valuemax={max} aria-valuenow={value}>
      {Array.from({ length: max }, (_, i) => (
        <span key={i} className={`n-progress__seg${i < value ? ' is-on' : ''}`} />
      ))}
    </div>
  );
}

/** 아직 생성되지 않은 글 자리. widths는 각 줄 너비(%) */
export function SkeletonText({ widths }: { widths: number[] }) {
  return (
    <div className="n-skeleton" aria-hidden="true">
      {widths.map((w, i) => (
        <span key={i} style={{ width: `${w}%` }} />
      ))}
    </div>
  );
}

/** 회색 안내 상자 (주황·파랑 같은 상태색 대신) */
export function Note({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="n-note" role="note">
      <Info size={18} aria-hidden="true" />
      <div className="n-stack" style={{ gap: 6, alignItems: 'flex-start' }}>
        <span className="n-semibold">{title}</span>
        {children}
      </div>
    </div>
  );
}

export function Card({ padding = 16, children }: { padding?: number; children: ReactNode }) {
  return (
    <div className="n-card" style={{ padding }}>
      {children}
    </div>
  );
}

export interface SelectCardProps {
  label: string;
  isSelected: boolean;
  onChange: (isSelected: boolean) => void;
  children: ReactNode;
}

/** 여러 개 고를 수 있는 카드. 카드 전체가 체크박스 라벨이다. */
export function SelectCard({ label, isSelected, onChange, children }: SelectCardProps) {
  return (
    <label className="n-select-card">
      <input type="checkbox" aria-label={label} checked={isSelected} onChange={(e) => onChange(e.target.checked)} />
      {children}
    </label>
  );
}

/** 선택 카드 오른쪽의 체크 원 (선택되면 검정 원 + 라임 체크) */
export function CheckMark() {
  return (
    <span className="n-check" aria-hidden="true">
      <Check size={24} strokeWidth={2.5} />
    </span>
  );
}

export interface SwitchProps {
  label: string;
  description?: string;
  isChecked: boolean;
  onChange: (isChecked: boolean) => void;
}

/** 켜고 끄는 스위치 한 줄: 왼쪽에 이름·설명, 오른쪽에 스위치. 켜짐은 라임 면 + 검정 손잡이(위치로도 구분된다) */
export function Switch({ label, description, isChecked, onChange }: SwitchProps) {
  const labelId = useId();
  const descId = useId();
  return (
    <div className="n-switch-row">
      <div className="n-switch-row__text">
        <span id={labelId} className="n-switch-row__label">
          {label}
        </span>
        {description ? (
          <span id={descId} className="n-switch-row__desc">
            {description}
          </span>
        ) : null}
      </div>
      <button
        type="button"
        role="switch"
        className="n-switch"
        aria-checked={isChecked}
        aria-labelledby={labelId}
        aria-describedby={description ? descId : undefined}
        onClick={() => onChange(!isChecked)}
      >
        <span className="n-switch__knob" />
      </button>
    </div>
  );
}
