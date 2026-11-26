import { useId, useRef, type KeyboardEvent, type ReactNode, type Ref } from 'react';

export interface TabItem<T extends string> {
  value: T;
  label: string;
  count?: number;
}

export interface TabListProps<T extends string> {
  /** TabPanel과 짝을 맞추는 id (useId로 만든 값을 양쪽에 넘긴다) */
  idBase: string;
  label: string;
  items: TabItem<T>[];
  value: T;
  onChange: (value: T) => void;
}

/** 밑줄 탭 줄: 고른 탭은 굵은 글자 + 라임 막대. 좌우 화살표 키로 탭을 옮긴다. 화면 위에 고정할 때는 이것만 헤더에 둔다. */
export function TabList<T extends string>({ idBase, label, items, value, onChange }: TabListProps<T>) {
  const refs = useRef<(HTMLButtonElement | null)[]>([]);

  const onKeyDown = (e: KeyboardEvent, i: number) => {
    if (e.key !== 'ArrowRight' && e.key !== 'ArrowLeft') return;
    e.preventDefault();
    const next = (i + (e.key === 'ArrowRight' ? 1 : -1) + items.length) % items.length;
    onChange(items[next].value);
    refs.current[next]?.focus();
  };

  return (
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
            id={`${idBase}-tab-${item.value}`}
            aria-selected={selected}
            aria-controls={`${idBase}-panel`}
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
  );
}

export interface TabPanelProps {
  /** TabList에 넘긴 것과 같은 id */
  idBase: string;
  /** 지금 고른 탭 값 */
  value: string;
  className?: string;
  ref?: Ref<HTMLDivElement>;
  children: ReactNode;
}

/** 고른 탭의 내용. TabList와 떨어진 자리(예: 헤더 아래 본문)에 둘 수 있다. */
export function TabPanel({ idBase, value, className = 'n-tabpanel', ref, children }: TabPanelProps) {
  return (
    <div ref={ref} role="tabpanel" id={`${idBase}-panel`} aria-labelledby={`${idBase}-tab-${value}`} className={className}>
      {children}
    </div>
  );
}

export interface TabsProps<T extends string> extends Omit<TabListProps<T>, 'idBase'> {
  /** 탭 패널 내용 (선택된 탭) */
  children: ReactNode;
}

/** 탭 줄과 내용을 바로 이어 붙인 기본형 */
export function Tabs<T extends string>({ children, ...listProps }: TabsProps<T>) {
  const id = useId();
  return (
    <>
      <TabList idBase={id} {...listProps} />
      <TabPanel idBase={id} value={listProps.value}>
        {children}
      </TabPanel>
    </>
  );
}
