import { useState, type ComponentType } from 'react';
import { brand } from '../brand';
import { Button, Mascot, MobileScreen, PageHeader, Stack } from '../components';
import { formatRelativeTime } from '../format';
import { Alert, Bell, Clock, Heart, Lightning, Play, type IconProps } from '../icons';

/** 알림 종류 — 종류마다 아이콘이 다르고, 누르면 가는 곳이 다르다 */
export type NotificationKind =
  /** 영상 완성 → 그 영상의 썸네일·내려받기 */
  | 'videoReady'
  /** 영상 만들기 실패(크레딧은 돌려줌) → 영상 올리기 */
  | 'videoFailed'
  /** 보관 기간이 곧 끝남 → 내 영상 완료 탭 */
  | 'expiring'
  /** 크레딧 충전 완료 → 크레딧 내역 */
  | 'creditCharged'
  /** 커뮤니티에 올린 영상에 좋아요 → 영상 보기 */
  | 'communityLike'
  /** 공지·이벤트 */
  | 'notice';

/** 알림 한 건 (API 미정 — 알림 목록·읽음 처리 API가 아직 없다) */
export interface AppNotification {
  id: string;
  kind: NotificationKind;
  title: string;
  body?: string;
  /** ISO 시각 */
  createdAt: string;
  isRead: boolean;
  /** 눌렀을 때 열 대상 (프로젝트·영상 id 등) */
  targetId?: string;
}

export interface NotificationsScreenProps {
  /** 최신순 */
  items: AppNotification[];
  /** loading: 처음 불러오는 중 */
  status?: 'ready' | 'loading';
  /** 상대 시각을 셀 기준 시각 (스토리·테스트에서 고정할 때). 없으면 지금 */
  now?: Date;
  onBack?: () => void;
  /** 알림 하나를 눌렀을 때: 읽음으로 바꾸고 해당 화면으로 보낸다 */
  onOpen?: (notification: AppNotification) => void;
  onMarkAllRead?: () => void;
}

const KIND_ICON: Record<NotificationKind, ComponentType<IconProps>> = {
  videoReady: Play,
  videoFailed: Alert,
  expiring: Clock,
  creditCharged: Lightning,
  communityLike: Heart,
  notice: Bell,
};

type GroupKey = 'today' | 'week' | 'older';
const GROUP_TITLE: Record<GroupKey, string> = { today: '오늘', week: '이번 주', older: '이전' };

function groupOf(iso: string, now: Date): GroupKey {
  const then = new Date(iso);
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  if (then.getTime() >= startOfToday) return 'today';
  if (then.getTime() >= startOfToday - 6 * 86400000) return 'week';
  return 'older';
}

/** 스크린 리더용 한 줄: 문장부호로 끝나지 않는 조각에만 마침표를 붙여 이어 읽는다 */
function sentences(parts: string[]): string {
  return parts
    .filter(Boolean)
    .map((part) => (/[.!?]$/.test(part) ? part : `${part}.`))
    .join(' ');
}

/** 알림 — 상단 GNB의 종에서 들어온다. 오늘 · 이번 주 · 이전으로 묶어 최신순으로 보여 준다 */
export function NotificationsScreen({ items, status = 'ready', now, onBack, onOpen, onMarkAllRead }: NotificationsScreenProps) {
  // 화면을 연 시각을 한 번만 잡아 둔다 (다시 그릴 때마다 시각이 바뀌지 않게)
  const [openedAt] = useState(() => new Date());
  const base = now ?? openedAt;
  const unread = items.filter((item) => !item.isRead).length;
  const header = (
    <PageHeader
      title="알림"
      onBack={onBack}
      endContent={
        status === 'ready' && items.length > 0 ? (
          <Button label="모두 읽음" variant="ghost" size="sm" isDisabled={unread === 0} onClick={onMarkAllRead} />
        ) : undefined
      }
    />
  );

  if (status === 'loading') {
    return (
      <MobileScreen header={header}>
        <p className="napda-visually-hidden" role="status">
          알림을 불러오고 있어요
        </p>
        <ul className="n-noti-list" aria-hidden="true">
          {Array.from({ length: 5 }, (_, i) => (
            <li key={i} className="n-noti n-noti--skeleton">
              <span className="n-noti__icon n-shimmer" />
              <span className="n-noti__text">
                <span className="n-shimmer n-noti__bar" style={{ width: '70%' }} />
                <span className="n-shimmer n-noti__bar" style={{ width: '45%' }} />
              </span>
            </li>
          ))}
        </ul>
      </MobileScreen>
    );
  }

  if (items.length === 0) {
    return (
      <MobileScreen header={header}>
        <Stack gap={16} align="center" justify="center" style={{ flex: 1, textAlign: 'center', paddingBottom: 24 }}>
          <Mascot src={brand.mascot.lying} width={150} />
          <Stack gap={8} align="center">
            <h2 className="n-display">아직 조용해요</h2>
            <p className="n-muted">영상이 다 되면 여기서 바로 알려 드려요.</p>
          </Stack>
        </Stack>
      </MobileScreen>
    );
  }

  const groups = (['today', 'week', 'older'] as const)
    .map((key) => ({ key, items: items.filter((item) => groupOf(item.createdAt, base) === key) }))
    .filter((group) => group.items.length > 0);

  return (
    <MobileScreen header={header}>
      {groups.map((group) => (
        <section key={group.key} className="n-noti-group" aria-labelledby={`noti-${group.key}`}>
          <h2 id={`noti-${group.key}`} className="n-noti-group__title">
            {GROUP_TITLE[group.key]}
          </h2>
          <ul className="n-noti-list">
            {group.items.map((item) => {
              const Icon = KIND_ICON[item.kind];
              const time = formatRelativeTime(item.createdAt, base);
              return (
                <li key={item.id}>
                  <button
                    type="button"
                    className={`n-noti${item.isRead ? '' : ' is-unread'}`}
                    aria-label={sentences([item.isRead ? '' : '안 읽음', item.title, item.body ?? '', time])}
                    onClick={() => onOpen?.(item)}
                  >
                    <span className={`n-noti__icon n-noti__icon--${item.kind}`} aria-hidden="true">
                      <Icon size={20} />
                    </span>
                    <span className="n-noti__text" aria-hidden="true">
                      <span className="n-noti__title">{item.title}</span>
                      {item.body ? <span className="n-noti__body">{item.body}</span> : null}
                      <span className="n-noti__time">{time}</span>
                    </span>
                    {item.isRead ? null : <span className="n-noti__dot" aria-hidden="true" />}
                  </button>
                </li>
              );
            })}
          </ul>
        </section>
      ))}
    </MobileScreen>
  );
}
