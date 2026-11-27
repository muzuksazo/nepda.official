import { useEffect, useId, useRef } from 'react';
import { brand } from '../brand';
import {
  BottomNav,
  Button,
  Mascot,
  MobileScreen,
  PageHeader,
  Stack,
  TabList,
  TabPanel,
  VideoTile,
  type NavTab,
  type TabItem,
} from '../components';
import { Plus } from '../icons';
import { HOOK_TYPES, type HookType } from './flowData';

/** 커뮤니티에 올라온 영상 한 편 (API 미정 — 공개·목록 API가 아직 없다) */
export interface CommunityVideo {
  id: string;
  productName: string;
  /** 공개 닉네임 (구글 실명이 아니다) */
  creatorName: string;
  hookType: HookType;
  /** 9:16 썸네일 (8단계에서 만든 썸네일) */
  thumbnailUrl?: string;
  videoUrl?: string;
  /** 썸네일 글자 */
  caption?: string;
  likeCount: number;
  isLiked?: boolean;
  /** 서버가 알려 준 댓글 수 (댓글 목록을 아직 안 불러왔을 때) */
  commentCount?: number;
}

export interface CommunityScreenProps {
  /** 추천 순서대로 온 영상들. 순서와 유형 거르기는 서버(추천 알고리즘)가 정한다 */
  items: CommunityVideo[];
  /** 고른 훅 유형. null이면 전체 */
  hookType: HookType | null;
  onHookTypeChange?: (hookType: HookType | null) => void;
  /** loading: 처음 불러오는 중 · error: 불러오기 실패 */
  status?: 'ready' | 'loading' | 'error';
  /** 아래에 더 불러올 영상이 있다 (맨 아래에 닿으면 onLoadMore) */
  hasMore?: boolean;
  isLoadingMore?: boolean;
  onLoadMore?: () => void;
  onOpenVideo?: (id: string) => void;
  onRetry?: () => void;
  /** 빈 상태의 "영상 만들기" */
  onCreate?: () => void;
  onNavigate?: (tab: NavTab) => void;
}

type TypeTab = 'all' | HookType;

const TYPE_TABS: TabItem<TypeTab>[] = [
  { value: 'all', label: '전체' },
  ...HOOK_TYPES.map(({ type }) => ({ value: type, label: `${type} 유형` })),
];

/** 탭 아래 한 줄: 전체는 추천 기준, 유형 탭은 그 유형이 어떤 훅인지 */
const TAB_INTRO: Record<TypeTab, string> = {
  all: '좋아할 만한 영상을 골라 보여 드려요.',
  ...(Object.fromEntries(HOOK_TYPES.map(({ type, description }) => [type, description])) as Record<HookType, string>),
};

const SKELETON_COUNT = 9;

interface CenteredStateProps {
  mascot: string;
  title: string;
  description: string;
  actionLabel?: string;
  onAction?: () => void;
}

/** 빈 상태·오류 안내: 냅다곰 + 제목 + 한 줄 + (선택) 버튼을 본문 가운데에 */
function CenteredState({ mascot, title, description, actionLabel, onAction }: CenteredStateProps) {
  return (
    <Stack gap={16} align="center" justify="center" style={{ flex: 1, textAlign: 'center', paddingBottom: 24 }}>
      <Mascot src={mascot} width={140} />
      <Stack gap={8} align="center">
        <h2 className="n-display">{title}</h2>
        <p className="n-muted">{description}</p>
      </Stack>
      {actionLabel ? <Button label={actionLabel} variant="secondary" size="md" onClick={onAction} /> : null}
    </Stack>
  );
}

/**
 * 안3-4 커뮤니티 — 다른 사람들이 냅다로 만든 영상을 둘러보는 탐색 그리드 (하단 내비게이션 '커뮤니티' 탭).
 * 정렬·카테고리 없이 추천 순서로 보여 주고, 위쪽 탭으로 훅 유형만 고른다.
 */
export function CommunityScreen({
  items,
  hookType,
  onHookTypeChange,
  status = 'ready',
  hasMore,
  isLoadingMore,
  onLoadMore,
  onOpenVideo,
  onRetry,
  onCreate,
  onNavigate,
}: CommunityScreenProps) {
  const tabsId = useId();
  const panelRef = useRef<HTMLDivElement>(null);
  const sentinelRef = useRef<HTMLDivElement>(null);
  const tab: TypeTab = hookType ?? 'all';
  const isEmpty = status === 'ready' && items.length === 0;

  const changeTab = (next: TypeTab) => {
    onHookTypeChange?.(next === 'all' ? null : next);
    // 목록이 통째로 바뀌므로 아래로 내려가 있었다면 맨 위부터 다시 보여 준다
    panelRef.current?.closest('.n-screen')?.scrollIntoView({ block: 'start' });
  };

  // 맨 아래 감지선이 화면에 들어오면 다음 영상들을 불러온다
  useEffect(() => {
    const sentinel = sentinelRef.current;
    if (!sentinel || !hasMore || isLoadingMore || !onLoadMore) return;
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) onLoadMore();
      },
      { rootMargin: '240px' },
    );
    observer.observe(sentinel);
    return () => observer.disconnect();
  }, [hasMore, isLoadingMore, onLoadMore]);

  const skeletonTiles = (count: number, keyPrefix: string) =>
    Array.from({ length: count }, (_, i) => (
      <li key={`${keyPrefix}-${i}`} aria-hidden="true">
        <span className="n-video-tile n-video-tile--skeleton n-shimmer" />
      </li>
    ));

  let body;
  if (status === 'error') {
    body = (
      <CenteredState
        mascot={brand.mascot.surprised}
        title="앗, 못 불러왔어요"
        description="연결을 확인하고 다시 눌러 주세요."
        actionLabel="다시 시도"
        onAction={onRetry}
      />
    );
  } else if (isEmpty && hookType !== null) {
    body = (
      <CenteredState
        mascot={brand.mascot.lying}
        title={`${hookType} 유형은 아직 없어요`}
        description="다른 유형부터 구경해 봐요."
        actionLabel="전체 보기"
        onAction={() => changeTab('all')}
      />
    );
  } else if (isEmpty) {
    body = <CenteredState mascot={brand.mascot.clapboard} title="아직 올라온 영상이 없어요" description="첫 주인공, 해볼래요?" />;
  } else {
    body = (
      <>
        <p className="n-explore-intro">{TAB_INTRO[tab]}</p>
        {status === 'loading' ? (
          <p className="napda-visually-hidden" role="status">
            영상을 불러오고 있어요
          </p>
        ) : null}
        <ul className="n-explore-grid" aria-label="커뮤니티 영상" aria-busy={status === 'loading' || isLoadingMore || undefined}>
          {status === 'loading'
            ? skeletonTiles(SKELETON_COUNT, 'first')
            : items.map((video) => (
                <li key={video.id}>
                  <VideoTile
                    thumbnailUrl={video.thumbnailUrl}
                    caption={video.caption}
                    label={`${video.productName}, ${video.creatorName}`}
                    likeCount={video.likeCount}
                    onClick={() => onOpenVideo?.(video.id)}
                  />
                </li>
              ))}
          {isLoadingMore ? skeletonTiles(3, 'more') : null}
        </ul>
        <div ref={sentinelRef} aria-hidden="true" />
      </>
    );
  }

  return (
    <MobileScreen
      header={
        <>
          <PageHeader title="커뮤니티" isTabRoot />
          <TabList idBase={tabsId} label="훅 유형" items={TYPE_TABS} value={tab} onChange={changeTab} />
        </>
      }
      footer={isEmpty && hookType === null ? <Button label="영상 만들기" isBlock icon={<Plus size={20} aria-hidden="true" />} onClick={onCreate} /> : undefined}
      bottomNav={<BottomNav active="community" onNavigate={onNavigate} />}
    >
      <TabPanel ref={panelRef} idBase={tabsId} value={tab} className="n-explore-panel">
        {body}
      </TabPanel>
    </MobileScreen>
  );
}
