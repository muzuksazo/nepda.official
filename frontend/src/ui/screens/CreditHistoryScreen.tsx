import { useEffect, useId, useRef, useState, type ComponentType, type ReactNode } from 'react';
import { Button, CreditBalanceCard, MobileScreen, Note, PageHeader, Stack, Tabs } from '../components';
import { dayKey, formatClock, formatDate, formatDay, formatWon } from '../format';
import { Clock, Film, Gift, Lightning, Refund, type IconProps } from '../icons';

/**
 * 크레딧이 움직인 까닭.
 * charge: 돈 내고 충전 · bonus: 이벤트로 받은 크레딧 · use: 영상 만들기에 씀
 * refund: 영상을 못 만들어서 돌려받음 · expire: 쓸 수 있는 기간이 지나 사라짐
 */
export type CreditEntryKind = 'charge' | 'bonus' | 'use' | 'refund' | 'expire';

/** 크레딧 내역 한 줄 (API 미정 — 내역 조회 API가 아직 없다) */
export interface CreditEntry {
  id: string;
  kind: CreditEntryKind;
  /** 들어오면 +, 나가면 − (크레딧 단위) */
  amount: number;
  /** 이 일이 있은 뒤 남은 크레딧 */
  balance: number;
  /** ISO 시각 */
  createdAt: string;
  /** use·refund: 어떤 제품 영상인지 */
  productName?: string;
  /** charge: 결제한 금액(원) */
  price?: number;
  /** bonus·expire: 어떤 이벤트인지 (예: "블랙프라이데이 선물") */
  eventName?: string;
  /** charge·bonus: 이 크레딧을 언제까지 쓸 수 있는지 (ISO). 정책이 정해지기 전에는 비워 둔다 */
  expiresAt?: string;
}

export type CreditHistoryFilter = 'all' | 'charge' | 'use';

export interface CreditHistoryScreenProps {
  /** 지금 크레딧. 못 불러왔으면 undefined → "—" */
  credits?: number;
  /** 최신순 */
  entries: CreditEntry[];
  /** loading: 처음 불러오는 중 · error: 못 불러옴 */
  status?: 'ready' | 'loading' | 'error';
  /** 30일 안에 사라질 크레딧 (가장 빠른 날 기준). 있으면 잔액 카드 아래에 한 줄로 알려 준다 */
  expiring?: { credits: number; date: string };
  /** 아래에 더 불러올 내역이 있다 (맨 아래에 닿으면 onLoadMore) */
  hasMore?: boolean;
  isLoadingMore?: boolean;
  onLoadMore?: () => void;
  /** 처음 고를 탭 (스토리·테스트용) */
  initialFilter?: CreditHistoryFilter;
  /** 날짜를 셀 기준 시각 (스토리·테스트에서 "오늘·어제"를 고정할 때). 없으면 지금 */
  now?: Date;
  onBack?: () => void;
  onCharge?: () => void;
  onRetry?: () => void;
  /** 환불·유효기간 안내 */
  onOpenPolicy?: () => void;
}

interface KindMeta {
  title: string;
  icon: ComponentType<IconProps>;
  filter: Exclude<CreditHistoryFilter, 'all'>;
}

/** 탭 나누기: 충전 = 돈 내고 산 것 + 선물 받은 것 · 사용 = 영상에 쓴 것과 그 뒤에 일어난 일(돌려받음·사라짐) */
const KIND: Record<CreditEntryKind, KindMeta> = {
  charge: { title: '충전', icon: Lightning, filter: 'charge' },
  bonus: { title: '이벤트 선물', icon: Gift, filter: 'charge' },
  use: { title: '영상 만들기', icon: Film, filter: 'use' },
  refund: { title: '못 만들어서 돌려받음', icon: Refund, filter: 'use' },
  expire: { title: '기간 지나 사라짐', icon: Clock, filter: 'use' },
};

const TABS: { value: CreditHistoryFilter; label: string }[] = [
  { value: 'all', label: '전체' },
  { value: 'charge', label: '충전' },
  { value: 'use', label: '사용' },
];

const EMPTY_TEXT: Record<CreditHistoryFilter, { title: string; body: string }> = {
  all: { title: '아직 텅 비었어요', body: '충전하거나 영상을 만들면 여기 쌓여요.' },
  charge: { title: '충전한 적이 없어요', body: '충전하면 여기 쌓여요.' },
  use: { title: '아직 안 썼어요', body: '영상을 만들면 여기 쌓여요.' },
};

const n = (value: number) => value.toLocaleString('ko-KR');

/** 줄 아래 작은 글씨: 제품·이벤트·결제 금액 중 하나 + 시각 */
function detailOf(entry: CreditEntry): string | undefined {
  if (entry.kind === 'charge') return entry.price !== undefined ? `${formatWon(entry.price)} 결제` : undefined;
  if (entry.kind === 'bonus' || entry.kind === 'expire') return entry.eventName;
  return entry.productName;
}

/**
 * 크레딧 내역 — 내 정보의 크레딧 카드 "내역"과 충전 완료 알림에서 들어온다.
 * 맨 위에 지금 잔액(+ 곧 사라질 크레딧), 그 아래 날짜별로 묶은 내역. 줄마다 얼마가 들고 났는지와 그 뒤 남은 크레딧을 보여 준다.
 */
export function CreditHistoryScreen({
  credits,
  entries,
  status = 'ready',
  expiring,
  hasMore = false,
  isLoadingMore = false,
  onLoadMore,
  initialFilter = 'all',
  now,
  onBack,
  onCharge,
  onRetry,
  onOpenPolicy,
}: CreditHistoryScreenProps) {
  const [filter, setFilter] = useState<CreditHistoryFilter>(initialFilter);
  // 화면을 연 시각을 한 번만 잡아 둔다 (다시 그릴 때마다 "오늘"이 바뀌지 않게)
  const [openedAt] = useState(() => new Date());
  const base = now ?? openedAt;
  const sentinelRef = useRef<HTMLDivElement>(null);
  const idBase = useId();

  // 목록 맨 아래 감지선이 화면에 가까워지면 다음 내역을 불러온다 (홈 피드와 같은 방식)
  useEffect(() => {
    const sentinel = sentinelRef.current;
    if (!sentinel || !hasMore || isLoadingMore || !onLoadMore) return;
    const observer = new IntersectionObserver(
      (items) => {
        if (items.some((item) => item.isIntersecting)) onLoadMore();
      },
      { rootMargin: '300px' },
    );
    observer.observe(sentinel);
    return () => observer.disconnect();
  }, [hasMore, isLoadingMore, onLoadMore]);

  const shown = filter === 'all' ? entries : entries.filter((entry) => KIND[entry.kind].filter === filter);
  const groups: { key: string; title: string; items: CreditEntry[] }[] = [];
  for (const entry of shown) {
    const key = dayKey(entry.createdAt);
    const last = groups[groups.length - 1];
    if (last?.key === key) last.items.push(entry);
    else groups.push({ key, title: formatDay(entry.createdAt, base), items: [entry] });
  }

  let list: ReactNode;
  if (status === 'loading') {
    list = (
      <>
        <p className="napda-visually-hidden" role="status">
          내역을 불러오고 있어요
        </p>
        <ul className="n-ledger" aria-hidden="true">
          {Array.from({ length: 5 }, (_, i) => (
            <LedgerSkeleton key={i} />
          ))}
        </ul>
      </>
    );
  } else if (status === 'error') {
    list = (
      <div role="alert">
        <Note title="내역을 못 불러왔어요">
          <Stack gap={10} style={{ alignItems: 'flex-start' }}>
            <span className="n-small n-muted">크레딧은 그대로 있어요. 잠깐 뒤에 다시 해 봐요.</span>
            <Button label="다시 불러오기" variant="secondary" size="sm" onClick={onRetry} />
          </Stack>
        </Note>
      </div>
    );
  } else if (shown.length === 0) {
    list = (
      <div className="n-ledger-empty">
        <p className="n-ledger-empty__title">{EMPTY_TEXT[filter].title}</p>
        <p className="n-small n-muted">{EMPTY_TEXT[filter].body}</p>
      </div>
    );
  } else {
    list = (
      <>
        {groups.map((group) => (
          <section key={group.key} className="n-ledger-group" aria-labelledby={`${idBase}-${group.key}`}>
            <h3 id={`${idBase}-${group.key}`} className="n-ledger-group__title">
              {group.title}
            </h3>
            <ul className="n-ledger">
              {group.items.map((entry) => (
                <LedgerRow key={entry.id} entry={entry} now={base} />
              ))}
            </ul>
          </section>
        ))}
        {isLoadingMore ? (
          <>
            <ul className="n-ledger" aria-hidden="true">
              <LedgerSkeleton />
              <LedgerSkeleton />
            </ul>
            <p className="napda-visually-hidden" role="status">
              내역을 더 불러오고 있어요
            </p>
          </>
        ) : null}
        <div ref={sentinelRef} aria-hidden="true" />
      </>
    );
  }

  return (
    <MobileScreen header={<PageHeader title="크레딧 내역" onBack={onBack} />}>
      <CreditBalanceCard
        credits={status === 'loading' ? undefined : credits}
        onChargeClick={onCharge}
        note={
          expiring && expiring.credits > 0 ? (
            <p className="n-ledger-expiring">
              <Clock size={16} aria-hidden="true" />
              <span>
                {formatDate(expiring.date, base)}에 <b className="n-num">{n(expiring.credits)}</b> 크레딧 사라져요
              </span>
            </p>
          ) : undefined
        }
      />

      <Tabs<CreditHistoryFilter> label="내역 종류" items={TABS} value={filter} onChange={setFilter}>
        <div className="n-ledger-panel">{list}</div>
      </Tabs>

      <div className="n-row" style={{ gap: 8, flexWrap: 'wrap' }}>
        <Button label="환불·유효기간 안내" variant="ghost" size="sm" onClick={onOpenPolicy} />
      </div>
    </MobileScreen>
  );
}

function LedgerRow({ entry, now }: { entry: CreditEntry; now: Date }) {
  const meta = KIND[entry.kind];
  const Icon = meta.icon;
  const isIn = entry.amount > 0;
  const amount = n(Math.abs(entry.amount));
  const detail = detailOf(entry);
  // 사라짐은 날이 바뀌는 0시에 일어나 시각이 뜻이 없다 — 날짜 묶음만으로 충분하다
  const time = entry.kind === 'expire' ? undefined : formatClock(entry.createdAt);
  const expiry = entry.expiresAt ? `${formatDate(entry.expiresAt, now)}까지 써요` : undefined;
  // 스크린 리더는 기호(+, −) 대신 말로 읽는다
  const readout = [
    meta.title,
    detail,
    time,
    `${amount} 크레딧 ${isIn ? '들어옴' : '나감'}`,
    `남은 크레딧 ${n(entry.balance)}`,
    expiry,
  ]
    .filter(Boolean)
    .join(', ');

  return (
    <li className={`n-ledger__row n-ledger__row--${entry.kind}`}>
      <span className="napda-visually-hidden">{readout}</span>
      <span className="n-ledger__icon" aria-hidden="true">
        <Icon size={20} />
      </span>
      <span className="n-ledger__main" aria-hidden="true">
        <span className="n-ledger__title">{meta.title}</span>
        <span className="n-ledger__sub">{[detail, time].filter(Boolean).join(' · ')}</span>
        {expiry ? <span className="n-ledger__expiry">{expiry}</span> : null}
      </span>
      <span className="n-ledger__side" aria-hidden="true">
        <span className={`n-ledger__amount n-num${isIn ? ' is-in' : ''}`}>
          {isIn ? '+' : '−'}
          {amount}
        </span>
        <span className="n-ledger__balance n-num">남은 {n(entry.balance)}</span>
      </span>
    </li>
  );
}

function LedgerSkeleton() {
  return (
    <li className="n-ledger__row">
      <span className="n-ledger__icon n-shimmer" />
      <span className="n-ledger__main">
        <span className="n-shimmer n-ledger__bar" style={{ width: '45%' }} />
        <span className="n-shimmer n-ledger__bar" style={{ width: '65%' }} />
      </span>
      <span className="n-shimmer n-ledger__bar" style={{ width: 48 }} />
    </li>
  );
}
