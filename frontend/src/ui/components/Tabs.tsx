import { useId, useRef, type KeyboardEvent, type ReactNode } from 'react';

export interface TabItem<T extends string> {
  value: T;
  label: string;
  count?: number;
}

export interface TabsProps<T extends string> {
  label: string;
  items: TabItem<T>[];
  value: T;
  onChange: (value: T) => void;
  /** 탭 패널 내용 (선택된 탭) */
  children: ReactNode;
}

/** 밑줄 탭: 고른 탭은 굵은 글자 + 라임 막대. 좌우 화살표 키로 탭을 옮긴다. */
export function Tabs<T extends string>({ label, items, value, onChange, children }: TabsProps<T>) {
  const id = useId();
  const refs = useRef<(HTMLButtonElement | null)[]>([]);

  const onKeyDown = (e: KeyboardEvent, i: number) => {
    if (e.key !== 'ArrowRight' && e.key !== 'ArrowLeft') return;
    e.preventDefault();
    const next = (i + (e.key === 'ArrowRight' ? 1 : -1) + items.length) % items.length;
    onChange(items[next].value);
    refs.current[next]?.focus();
  };

  return (
    <>
      <div className="n-tabs" role="tablist" aria-label={label}>
        {items.map((item, i) => {
          const selected = item.value === value;
          return (
            <button
              key={item.value}
              ref={(el) => {
                refs.current[i] = el;
              }}
              type="button"
              role="tab"
              id={`${id}-tab-${item.value}`}
              aria-selected={selected}
              aria-controls={`${id}-panel`}
              tabIndex={selected ? 0 : -1}
              className={`n-tab${selected ? ' is-on' : ''}`}
              onClick={() => onChange(item.value)}
              onKeyDown={(e) => onKeyDown(e, i)}
            >
              {item.label}
              {item.count !== undefined ? <span className="n-tab__count">{item.count}</span> : null}
            </button>
          );
        })}
      </div>
      <div role="tabpanel" id={`${id}-panel`} aria-labelledby={`${id}-tab-${value}`} className="n-tabpanel">
        {children}
      </div>
    </>
  );
}
