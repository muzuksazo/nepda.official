import { useEffect, useRef, useState } from 'react';
import { Plus } from '../icons';
import {
  AppHeaderActions,
  BottomNav,
  BrandHeader,
  Button,
  Carousel,
  CommentSheet,
  EventBanner,
  FeedPost,
  Mascot,
  MobileScreen,
  ProjectCard,
  SectionTitle,
  ShareSheet,
  Stack,
  type NavTab,
  type BannerItem,
  type ShareHandlers,
  type VideoComment,
} from '../components';
import { brand } from '../brand';
import type { CommunityVideo } from './CommunityScreen';

export interface InProgressProject {
  id: string;
  productName: string;
  status: string;
  completedSteps: number;
  nextStep: string;
}

export interface CompletedProject {
  id: string;
  productName: string;
  status: string;
}

export interface HomeScreenProps {
  inProgress: InProgressProject[];
  completed: CompletedProject[];
  onCreate?: () => void;
  onContinue?: (id: string) => void;
  onDownloadAgain?: (id: string) => void;
  /** 상단 이벤트 배너 (없으면 영역을 숨긴다) */
  banners?: BannerItem[];
  onBannerSelect?: (id: string) => void;
  /** 내 영상 화살표 → 내 영상 탭 */
  onSeeAllMyVideos?: () => void;
  /** 상단 크레딧 잔액 (못 불러왔으면 생략) */
  credits?: number;
  onCreditClick?: () => void;
  /** 상단 알림 종: 안 읽은 알림 수 */
  unreadCount?: number;
  onNotificationsClick?: () => void;
  /** 상단 프로필 (사진이 없으면 닉네임 첫 글자) */
  profile?: { name?: string; imageUrl?: string };
  onProfileClick?: () => void;
  /** 하단 내비게이션 이동 */
  onNavigate?: (tab: NavTab) => void;
  /** 완료 아래 피드: 커뮤니티 영상 (추천 순서). 비어 있으면 섹션을 숨긴다 */
  feed?: CommunityVideo[];
  /** 아래에 더 불러올 피드가 있다 (맨 아래에 닿으면 onLoadMoreFeed) */
  feedHasMore?: boolean;
  isFeedLoadingMore?: boolean;
  onLoadMoreFeed?: () => void;
  /** 피드 영상 크게 보기 */
  onOpenFeed?: (id: string) => void;
  onToggleFeedLike?: (id: string, isLiked: boolean) => void;
  /** 피드 게시물의 프로필 원·닉네임 → 만든 사람 프로필 */
  onOpenCreator?: (creatorName: string) => void;
  /** 공유 시트에 쓸 링크·복사·기기 공유 창. 없으면 피드에 공유 버튼을 숨긴다 */
  share?: ShareHandlers;
  /** "이 훅으로 만들기" */
  onRemixFeed?: (video: CommunityVideo) => void;
  /** 피드 제목 옆 화살표 → 커뮤니티 탭 */
  onSeeAllFeed?: () => void;
  /** 영상별 댓글 (불러온 것만). 없으면 영상의 commentCount로 수만 보여 준다 */
  comments?: Record<string, VideoComment[]>;
  onAddComment?: (videoId: string, text: string) => void;
  onDeleteComment?: (videoId: string, commentId: string) => void;
  /** 처음부터 이 영상의 댓글 시트를 열어 둔다 (스토리·테스트용) */
  initialCommentsFor?: string;
  /** 처음부터 이 영상의 공유 시트를 열어 둔다 (스토리·테스트용) */
  initialShareFor?: string;
}

/** 안3-1 홈 */
export function HomeScreen({
  inProgress,
  completed,
  onCreate,
  onContinue,
  onDownloadAgain,
  onSeeAllMyVideos,
  banners = [],
  onBannerSelect,
  credits,
  onCreditClick,
  unreadCount,
  onNotificationsClick,
  profile,
  onProfileClick,
  onNavigate,
  feed = [],
  feedHasMore,
  isFeedLoadingMore,
  onLoadMoreFeed,
  onOpenFeed,
  onToggleFeedLike,
  share,
  onOpenCreator,
  onRemixFeed,
  onSeeAllFeed,
  comments = {},
  onAddComment,
  onDeleteComment,
  initialCommentsFor,
  initialShareFor,
}: HomeScreenProps) {
  const sentinelRef = useRef<HTMLDivElement>(null);
  const [commentsFor, setCommentsFor] = useState<string | null>(initialCommentsFor ?? null);
  const [shareFor, setShareFor] = useState<string | null>(initialShareFor ?? null);
  const shareVideo = shareFor ? (feed.find((video) => video.id === shareFor) ?? null) : null;
  const commentCountOf = (video: CommunityVideo) => comments[video.id]?.length ?? video.commentCount ?? 0;

  // 피드 맨 아래 감지선이 화면에 가까워지면 다음 게시물을 불러온다
  useEffect(() => {
    const sentinel = sentinelRef.current;
    if (!sentinel || !feedHasMore || isFeedLoadingMore || !onLoadMoreFeed) return;
    const observer = new IntersectionObserver((entries) => {
      if (entries.some((entry) => entry.isIntersecting)) onLoadMoreFeed();
    }, { rootMargin: '400px' });
    observer.observe(sentinel);
    return () => observer.disconnect();
  }, [feedHasMore, isFeedLoadingMore, onLoadMoreFeed]);

  const isEmpty = inProgress.length === 0 && completed.length === 0;
  const header = (
    <BrandHeader
      endContent={
        <AppHeaderActions
          credits={credits}
          onCreditClick={onCreditClick}
          unreadCount={unreadCount}
          onNotificationsClick={onNotificationsClick}
          profile={profile}
          onProfileClick={onProfileClick}
        />
      }
    />
  );
  const bottomNav = <BottomNav active="home" onNavigate={onNavigate} />;
  const createButton = <Button label="영상 만들기" isBlock icon={<Plus size={20} aria-hidden="true" />} onClick={onCreate} />;

  if (isEmpty) {
    return (
      <MobileScreen header={header} footer={createButton} bottomNav={bottomNav}>
        <Stack gap={16} align="center" justify="center" style={{ flex: 1, textAlign: 'center', paddingBottom: 24 }}>
          <Mascot src={brand.mascot.clapboard} width={140} />
          <Stack gap={8} align="center">
            <h2 className="n-display">
              첫 광고, <span className="n-mark">냅다</span> 만들어 볼까요?
            </h2>
            <p className="n-muted">제품만 알려 주면 훅은 저희가 붙여요.</p>
          </Stack>
        </Stack>
      </MobileScreen>
    );
  }

  return (
    <>
      <MobileScreen header={header} bottomNav={bottomNav} isInert={commentsFor !== null || shareVideo !== null}>
        {banners.length > 0 ? (
          <div style={{ marginBottom: -8 }}>
            <EventBanner items={banners} onSelect={onBannerSelect} />
          </div>
        ) : null}
        {createButton}

        {/* 내 영상: 진행 중(이어 할 것)을 앞에, 완료를 뒤에 한 줄로 */}
        <Stack gap={12} as="section">
          <SectionTitle title="내 영상" count={inProgress.length + completed.length} onSeeAll={onSeeAllMyVideos} />
          <Carousel label="내 영상">
            {[
              ...inProgress.map((p) => (
                <ProjectCard
                  key={p.id}
                  productName={p.productName}
                  status={p.status}
                  completedSteps={p.completedSteps}
                  nextStep={p.nextStep}
                  actionLabel="이어하기"
                  onAction={() => onContinue?.(p.id)}
                />
              )),
              ...completed.map((p) => (
                <ProjectCard
                  key={p.id}
                  productName={p.productName}
                  status={p.status}
                  actionLabel="다시 받기"
                  onAction={() => onDownloadAgain?.(p.id)}
                />
              )),
            ]}
          </Carousel>
        </Stack>

        {/* 다른 사장님들이 냅다로 만든 영상: 내리면서 계속 본다 */}
        {feed.length > 0 ? (
          <Stack gap={16} as="section" style={{ marginTop: 8 }}>
            <SectionTitle title="구경하기" onSeeAll={onSeeAllFeed} />
            <div className="n-feed" aria-busy={isFeedLoadingMore || undefined}>
              {feed.map((video) => (
                <FeedPost
                  key={video.id}
                  creatorName={video.creatorName}
                  productName={video.productName}
                  hookType={video.hookType}
                  thumbnailUrl={video.thumbnailUrl}
                  videoUrl={video.videoUrl}
                  caption={video.caption}
                  likeCount={video.likeCount}
                  isLiked={video.isLiked}
                  onOpen={() => onOpenFeed?.(video.id)}
                  onToggleLike={(isLiked) => onToggleFeedLike?.(video.id, isLiked)}
                  onShare={share ? () => setShareFor(video.id) : undefined}
                  onOpenCreator={onOpenCreator ? () => onOpenCreator(video.creatorName) : undefined}
                  commentCount={commentCountOf(video)}
                  onOpenComments={() => setCommentsFor(video.id)}
                  onRemix={() => onRemixFeed?.(video)}
                />
              ))}
              {isFeedLoadingMore ? (
                <div className="n-post n-post--skeleton" aria-hidden="true">
                  <div className="n-post__head">
                    <span className="n-avatar n-shimmer" />
                    <span className="n-shimmer" style={{ width: 120, height: 14, borderRadius: 6 }} />
                  </div>
                  <span className="n-post__media n-shimmer" />
                </div>
              ) : null}
            </div>
            {isFeedLoadingMore ? (
              <p className="napda-visually-hidden" role="status">
                영상을 더 불러오고 있어요
              </p>
            ) : null}
            <div ref={sentinelRef} aria-hidden="true" />
            {!feedHasMore ? <p className="n-small n-muted" style={{ textAlign: 'center', padding: '8px 0 4px' }}>여기까지 다 봤어요!</p> : null}
          </Stack>
        ) : null}
      </MobileScreen>

      <CommentSheet
        isOpen={commentsFor !== null}
        comments={commentsFor ? (comments[commentsFor] ?? []) : []}
        myName={profile?.name}
        onSubmit={(text) => commentsFor && onAddComment?.(commentsFor, text)}
        onDelete={(id) => commentsFor && onDeleteComment?.(commentsFor, id)}
        onClose={() => setCommentsFor(null)}
      />

      <ShareSheet
        video={share ? shareVideo : null}
        url={shareVideo && share ? share.shareUrlOf(shareVideo.id) : ''}
        canShareNative={share?.canShareNative}
        onShareNative={() => {
          if (!shareVideo) return;
          share?.onShareNative?.(shareVideo.id);
          setShareFor(null);
        }}
        onCopyLink={() => shareVideo && share?.onCopyLink?.(shareVideo.id)}
        onClose={() => setShareFor(null)}
      />
    </>
  );
}
