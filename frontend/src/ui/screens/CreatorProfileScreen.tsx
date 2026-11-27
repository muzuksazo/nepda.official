import { useEffect, useRef, type ReactNode } from 'react';
import { brand } from '../brand';
import { Avatar, Button, Mascot, MobileScreen, PageHeader, SectionTitle, Stack, VideoTile } from '../components';
import { formatCount } from '../format';
import type { CommunityVideo } from './CommunityScreen';
import type { HookType } from './flowData';

/** 커뮤니티에 보이는 만든 사람 (API 미정 — 사람별 공개 프로필 API가 아직 없다) */
export interface CreatorProfile {
  /** 공개 닉네임 */
  name: string;
  imageUrl?: string;
  /** 커뮤니티에 올려 둔 영상 수 */
  videoCount: number;
  /** 올린 영상들이 받은 좋아요를 모두 더한 수 */
  likeCount: number;
  /** 가장 많이 쓴 훅 유형 (영상이 없으면 없음) */
  mainHookType?: HookType;
}

export interface CreatorProfileScreenProps {
  /** 불러오기 전에는 undefined */
  creator?: CreatorProfile;
  /** 이 사람이 올린 영상 (최신순) */
  videos: CommunityVideo[];
  /** loading: 처음 불러오는 중 · gone: 탈퇴했거나 찾을 수 없음 */
  status?: 'ready' | 'loading' | 'gone';
  /** 아래에 더 불러올 영상이 있다 (맨 아래에 닿으면 onLoadMore) */
  hasMore?: boolean;
  isLoadingMore?: boolean;
  onLoadMore?: () => void;
  onBack?: () => void;
  /** 영상 한 칸을 눌렀을 때 → 영상 보기 (이 사람 영상만 위아래로 넘긴다) */
  onOpenVideo?: (id: string) => void;
  /** "나도 B 유형으로 만들기" → 그 훅 유형을 고른 채로 만들기 시작 */
  onRemix?: (hookType: HookType) => void;
}

/**
 * 만든 사람 프로필 — 홈 피드·영상 보기에서 닉네임(또는 프로필 원)을 누르면 온다.
 * 위에 프로필 원 + 숫자 셋(영상 · 좋아요 · 주로 쓰는 훅), 아래에 올린 영상 그리드.
 * 팔로우는 없다 — 냅다 커뮤니티는 "잘 된 훅을 보고 따라 만드는 곳"이라 이 사람이 주로 쓰는 훅으로 바로 만들게 한다.
 */
export function CreatorProfileScreen({
  creator,
  videos,
  status = 'ready',
  hasMore = false,
  isLoadingMore = false,
  onLoadMore,
  onBack,
  onOpenVideo,
  onRemix,
}: CreatorProfileScreenProps) {
  const sentinelRef = useRef<HTMLDivElement>(null);

  // 그리드 맨 아래 감지선이 화면에 가까워지면 다음 영상을 불러온다 (커뮤니티 탐색과 같은 방식)
  useEffect(() => {
    const sentinel = sentinelRef.current;
    if (!sentinel || !hasMore || isLoadingMore || !onLoadMore) return;
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) onLoadMore();
      },
      { rootMargin: '400px' },
    );
    observer.observe(sentinel);
    return () => observer.disconnect();
  }, [hasMore, isLoadingMore, onLoadMore]);

  const header = <PageHeader title={status === 'ready' && creator ? creator.name : ''} onBack={onBack} />;

  if (status === 'gone') {
    return (
      <MobileScreen header={header}>
        <Stack gap={16} align="center" justify="center" style={{ flex: 1, textAlign: 'center', paddingBottom: 24 }}>
          <Mascot src={brand.mascot.surprised} width={140} />
          <Stack gap={8} align="center">
            <h2 className="n-display">사라진 프로필이에요</h2>
            <p className="n-muted">탈퇴했거나 찾을 수 없는 사람이에요.</p>
          </Stack>
          <Button label="돌아가기" variant="secondary" size="md" onClick={onBack} />
        </Stack>
      </MobileScreen>
    );
  }

  const isLoading = status === 'loading' || !creator;
  const tiles = (count: number, keyPrefix: string) =>
    Array.from({ length: count }, (_, i) => (
      <li key={`${keyPrefix}-${i}`} aria-hidden="true">
        <span className="n-video-tile n-video-tile--skeleton n-shimmer" />
      </li>
    ));

  let grid: ReactNode;
  if (isLoading) {
    grid = <ul className="n-explore-grid">{tiles(6, 'first')}</ul>;
  } else if (videos.length === 0) {
    grid = <p className="n-creator__empty">아직 올린 영상이 없어요.</p>;
  } else {
    grid = (
      <>
        <ul className="n-explore-grid" aria-label={`${creator.name}님이 올린 영상`} aria-busy={isLoadingMore || undefined}>
          {videos.map((video) => (
            <li key={video.id}>
              <VideoTile
                thumbnailUrl={video.thumbnailUrl}
                caption={video.caption}
                label={`${video.productName}, ${video.hookType} 유형`}
                likeCount={video.likeCount}
                onClick={() => onOpenVideo?.(video.id)}
              />
            </li>
          ))}
          {isLoadingMore ? tiles(3, 'more') : null}
        </ul>
        {isLoadingMore ? (
          <p className="napda-visually-hidden" role="status">
            영상을 더 불러오고 있어요
          </p>
        ) : null}
        <div ref={sentinelRef} aria-hidden="true" />
      </>
    );
  }

  const mainHookType = creator?.mainHookType;

  return (
    <MobileScreen
      header={header}
      footer={
        !isLoading && mainHookType ? (
          <Button label={`나도 ${mainHookType} 유형으로 만들기`} isBlock onClick={() => onRemix?.(mainHookType)} />
        ) : undefined
      }
    >
      {isLoading ? (
        <>
          <p className="napda-visually-hidden" role="status">
            프로필을 불러오고 있어요
          </p>
          <div className="n-creator" aria-hidden="true">
            <span className="n-avatar n-avatar--lg n-shimmer" />
            <div className="n-creator__stats">
              {[0, 1, 2].map((i) => (
                <span key={i} className="n-shimmer n-creator__bar" />
              ))}
            </div>
          </div>
        </>
      ) : (
        <section className="n-creator" aria-label={`${creator.name} 프로필`}>
          <Avatar name={creator.name} imageUrl={creator.imageUrl} size="lg" />
          {/* 숫자를 위에 크게, 이름을 아래에 작게 (읽는 순서는 "영상 4"처럼 이름 → 숫자) */}
          <dl className="n-creator__stats">
            <div className="n-creator__stat">
              <dt>영상</dt>
              <dd className="n-num">{formatCount(creator.videoCount)}</dd>
            </div>
            <div className="n-creator__stat">
              <dt>좋아요</dt>
              <dd className="n-num">{formatCount(creator.likeCount)}</dd>
            </div>
            <div className="n-creator__stat">
              <dt>주로 쓰는 훅</dt>
              <dd>{creator.mainHookType ? `${creator.mainHookType} 유형` : '–'}</dd>
            </div>
          </dl>
        </section>
      )}

      <Stack gap={0}>
        <SectionTitle title="올린 영상" count={isLoading ? undefined : creator.videoCount} />
        {grid}
      </Stack>
    </MobileScreen>
  );
}
