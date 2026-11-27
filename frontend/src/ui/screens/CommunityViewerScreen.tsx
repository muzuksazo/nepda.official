import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { Avatar, Badge, Button, CommentSheet, ConfirmSheet, ShareSheet, type ShareHandlers, type VideoComment } from '../components';
import { formatCount } from '../format';
import { Alert, ChevronLeft, Comment, Heart, Play, Share, SoundOff, SoundOn, Stars } from '../icons';
import type { CommunityVideo } from './CommunityScreen';

export interface CommunityViewerScreenProps {
  /** 탐색 그리드와 같은 순서의 영상들 */
  items: CommunityVideo[];
  /** 처음 보여 줄 영상 (그리드에서 누른 영상). 없으면 첫 영상 */
  initialId?: string;
  onBack?: () => void;
  onToggleLike?: (id: string, isLiked: boolean) => void;
  /** 프로필 원·닉네임을 눌렀을 때 → 만든 사람 프로필 */
  onOpenCreator?: (creatorName: string) => void;
  /** 공유 시트에 쓸 링크·복사·기기 공유 창. 없으면 공유 버튼을 숨긴다 */
  share?: ShareHandlers;
  onReport?: (id: string) => void;
  /** "이 훅으로 만들기": 같은 훅 유형으로 새 영상 만들기를 시작한다 (영상·시나리오를 복사하지 않는다) */
  onRemix?: (video: CommunityVideo) => void;
  /** 화면에 보이는 영상이 바뀔 때 */
  onActiveChange?: (id: string) => void;
  /** 처음부터 신고 확인 시트를 열어 둔다 (스토리·테스트용) */
  initialIsReporting?: boolean;
  /** 영상별 댓글 (불러온 것만) */
  comments?: Record<string, VideoComment[]>;
  /** 댓글 입력 줄에 보일 내 닉네임 */
  myName?: string;
  onAddComment?: (videoId: string, text: string) => void;
  onDeleteComment?: (videoId: string, commentId: string) => void;
}

/** 내려받기 API의 AI 라벨 문구(label_text). 커뮤니티에서는 모든 영상에 항상 붙인다 */
const AI_LABEL = 'AI 연출 포함';

/**
 * 안3-5 영상 보기 — 커뮤니티 영상을 한 편씩 크게 보고 위아래로 넘긴다.
 * 영상 화면이라 앱의 라이트/다크 설정과 상관없이 늘 어두운 바탕을 쓴다.
 */
export function CommunityViewerScreen({
  items,
  initialId,
  onBack,
  onToggleLike,
  share,
  onOpenCreator,
  onReport,
  onRemix,
  onActiveChange,
  initialIsReporting = false,
  comments = {},
  myName,
  onAddComment,
  onDeleteComment,
}: CommunityViewerScreenProps) {
  const [activeId, setActiveId] = useState<string | undefined>(initialId ?? items[0]?.id);
  const [likeOverrides, setLikeOverrides] = useState<Record<string, boolean>>({});
  const [isMuted, setIsMuted] = useState(true);
  const [pausedId, setPausedId] = useState<string | null>(null);
  const [isReporting, setIsReporting] = useState(initialIsReporting);
  const [isCommenting, setIsCommenting] = useState(false);
  const [isSharing, setIsSharing] = useState(false);
  // 시트(신고·댓글·공유)가 떠 있으면 뒤 화면을 잠그고 영상을 멈춘다
  const isSheetOpen = isReporting || isCommenting || isSharing;
  const [toast, setToast] = useState<string | null>(null);

  const feedRef = useRef<HTMLDivElement>(null);
  const itemRefs = useRef(new Map<string, HTMLElement>());
  const videoRefs = useRef(new Map<string, HTMLVideoElement>());
  const shouldMoveFocusRef = useRef(false);
  // 부모가 매번 새 함수를 넘겨도 "보는 영상이 바뀔 때"만 알리도록 최신 콜백을 따로 들고 있는다
  const onActiveChangeRef = useRef(onActiveChange);
  useEffect(() => {
    onActiveChangeRef.current = onActiveChange;
  });

  const activeIndex = Math.max(
    0,
    items.findIndex((video) => video.id === activeId),
  );

  // 그리드에서 누른 영상이 처음부터 화면에 오도록 맞춘다
  useLayoutEffect(() => {
    const feed = feedRef.current;
    const first = initialId ? itemRefs.current.get(initialId) : undefined;
    if (feed && first) feed.scrollTop = first.offsetTop;
  }, [initialId]);

  // 화면의 60% 이상을 차지한 영상을 "지금 보는 영상"으로 삼는다
  useEffect(() => {
    const feed = feedRef.current;
    if (!feed) return;
    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries.find((entry) => entry.isIntersecting);
        const id = visible?.target.getAttribute('data-id');
        if (!id) return;
        // 넘기기 전 영상 안에 포커스가 있었으면, 넘긴 뒤 새 영상으로 포커스를 따라 옮긴다
        const focused = document.activeElement;
        shouldMoveFocusRef.current = focused instanceof HTMLElement && focused !== feed && feed.contains(focused);
        setPausedId(null);
        setActiveId(id);
      },
      { root: feed, threshold: 0.6 },
    );
    itemRefs.current.forEach((element) => observer.observe(element));
    return () => observer.disconnect();
  }, [items]);

  useEffect(() => {
    if (!activeId) return;
    onActiveChangeRef.current?.(activeId);
    if (shouldMoveFocusRef.current) {
      shouldMoveFocusRef.current = false;
      itemRefs.current.get(activeId)?.focus({ preventScroll: true });
    }
  }, [activeId]);

  // 지금 보는 영상만 재생하고 나머지는 멈춘다
  useEffect(() => {
    videoRefs.current.forEach((video, id) => {
      video.muted = isMuted;
      if (id === activeId && pausedId !== id && !isSheetOpen) {
        // 자동 재생이 막히면(브라우저 정책) 멈춘 채로 두고, 사용자가 눌러 재생한다
        video.play().catch(() => setPausedId(id));
      } else {
        video.pause();
      }
    });
  }, [activeId, pausedId, isMuted, isSheetOpen, items]);

  useEffect(() => {
    if (!toast) return;
    const timer = window.setTimeout(() => setToast(null), 2600);
    return () => window.clearTimeout(timer);
  }, [toast]);

  if (items.length === 0) {
    return (
      <div className="n-viewer" data-theme="dark">
        <div className="n-viewer__top">
          <button type="button" className="n-viewer__icon-btn" aria-label="뒤로" onClick={onBack}>
            <ChevronLeft size={26} />
          </button>
        </div>
        <p className="n-viewer__empty">볼 수 있는 영상이 없어요.</p>
      </div>
    );
  }

  return (
    <div className="n-viewer" data-theme="dark">
      <div className="n-viewer__top" inert={isSheetOpen}>
        <button type="button" className="n-viewer__icon-btn" aria-label="뒤로" onClick={onBack}>
          <ChevronLeft size={26} />
        </button>
        <span className="n-viewer__count n-num" aria-hidden="true">
          <b>{activeIndex + 1}</b> / {items.length}
        </span>
        <button type="button" className="n-viewer__icon-btn" aria-label="이 영상 신고" onClick={() => setIsReporting(true)}>
          <Alert size={22} />
        </button>
      </div>

      <div ref={feedRef} className="n-viewer__feed" role="group" aria-label="커뮤니티 영상. 위아래로 넘겨요" tabIndex={0} inert={isSheetOpen}>
        {items.map((video, index) => {
          const isActive = video.id === activeId;
          const wasLiked = video.isLiked ?? false;
          const isLiked = likeOverrides[video.id] ?? wasLiked;
          const likeCount = video.likeCount + (isLiked === wasLiked ? 0 : isLiked ? 1 : -1);
          const isPaused = pausedId === video.id;
          return (
            <article
              key={video.id}
              ref={(element) => {
                if (element) itemRefs.current.set(video.id, element);
                else itemRefs.current.delete(video.id);
              }}
              className="n-viewer__item"
              data-id={video.id}
              aria-label={`${items.length}개 중 ${index + 1}번째. ${video.productName}, ${video.creatorName}`}
              tabIndex={-1}
              inert={!isActive}
            >
              <div className="n-viewer__stage">
                <div className="n-viewer__media">
                  {video.videoUrl ? (
                    <video
                      ref={(element) => {
                        if (element) videoRefs.current.set(video.id, element);
                        else videoRefs.current.delete(video.id);
                      }}
                      src={video.videoUrl}
                      poster={video.thumbnailUrl}
                      aria-label={video.caption ?? video.productName}
                      loop
                      muted
                      playsInline
                      preload={isActive ? 'auto' : 'metadata'}
                    />
                  ) : video.thumbnailUrl ? (
                    <img src={video.thumbnailUrl} alt={video.caption ?? video.productName} />
                  ) : (
                    <span className="n-viewer__fallback">{video.caption ?? video.productName}</span>
                  )}

                  {video.videoUrl ? (
                    <button
                      type="button"
                      className="n-viewer__tap"
                      aria-label={isPaused ? '재생' : '일시정지'}
                      onClick={() => setPausedId(isPaused ? null : video.id)}
                    >
                      {isPaused ? (
                        <span className="n-viewer__play" aria-hidden="true">
                          <Play size={28} fill="currentColor" />
                        </span>
                      ) : null}
                    </button>
                  ) : null}

                  <span className="n-viewer__ai">
                    <Stars size={14} />
                    {AI_LABEL}
                  </span>

                  <div className="n-viewer__rail">
                    <button
                      type="button"
                      className={`n-viewer__action${isLiked ? ' is-on' : ''}`}
                      aria-pressed={isLiked}
                      aria-label={`좋아요 ${formatCount(likeCount)}개`}
                      onClick={() => {
                        setLikeOverrides((prev) => ({ ...prev, [video.id]: !isLiked }));
                        onToggleLike?.(video.id, !isLiked);
                      }}
                    >
                      <Heart size={22} fill={isLiked ? 'currentColor' : 'none'} />
                      <span className="n-viewer__action-count n-num" aria-hidden="true">
                        {formatCount(likeCount)}
                      </span>
                    </button>
                    <button
                      type="button"
                      className="n-viewer__action"
                      aria-label={`댓글 ${comments[video.id]?.length ?? video.commentCount ?? 0}개`}
                      onClick={() => setIsCommenting(true)}
                    >
                      <Comment size={22} />
                      <span className="n-viewer__action-count n-num" aria-hidden="true">
                        {formatCount(comments[video.id]?.length ?? video.commentCount ?? 0)}
                      </span>
                    </button>
                    {share ? (
                      <button type="button" className="n-viewer__action" aria-label="공유" onClick={() => setIsSharing(true)}>
                        <Share size={22} />
                      </button>
                    ) : null}
                    {video.videoUrl ? (
                      <button
                        type="button"
                        className="n-viewer__action"
                        aria-label={isMuted ? '소리 켜기' : '소리 끄기'}
                        onClick={() => setIsMuted((muted) => !muted)}
                      >
                        {isMuted ? <SoundOff size={22} /> : <SoundOn size={22} />}
                      </button>
                    ) : null}
                  </div>
                </div>
              </div>

              <div className="n-viewer__panel">
                <div className="n-viewer__meta">
                  {onOpenCreator ? (
                    <button
                      type="button"
                      className="n-creator-link"
                      onClick={() => onOpenCreator(video.creatorName)}
                      aria-label={`${video.creatorName} 프로필 보기, ${video.productName}`}
                    >
                      <Avatar name={video.creatorName} />
                      <span className="n-viewer__who" aria-hidden="true">
                        <span className="n-viewer__creator">{video.creatorName}</span>
                        <span className="n-viewer__product">{video.productName}</span>
                      </span>
                    </button>
                  ) : (
                    <>
                      <Avatar name={video.creatorName} />
                      <div className="n-viewer__who">
                        <span className="n-viewer__creator">{video.creatorName}</span>
                        <span className="n-viewer__product">{video.productName}</span>
                      </div>
                    </>
                  )}
                  <Badge tone="brand">{video.hookType} 유형</Badge>
                </div>
                <Button label="이 훅으로 만들기" isBlock onClick={() => onRemix?.(video)} />
              </div>
            </article>
          );
        })}
      </div>

      <div className="n-viewer__status" role="status">
        {toast ? <span className="n-toast">{toast}</span> : null}
      </div>

      <ConfirmSheet
        isOpen={isReporting}
        title="이 영상을 신고할까요?"
        description="운영팀이 확인하고, 문제가 있으면 내려요."
        confirmLabel="신고하기"
        onConfirm={() => {
          setIsReporting(false);
          if (activeId) onReport?.(activeId);
          setToast('신고를 접수했어요');
        }}
        onClose={() => setIsReporting(false)}
      />

      <CommentSheet
        isOpen={isCommenting}
        comments={activeId ? (comments[activeId] ?? []) : []}
        myName={myName}
        onSubmit={(text) => activeId && onAddComment?.(activeId, text)}
        onDelete={(id) => activeId && onDeleteComment?.(activeId, id)}
        onClose={() => setIsCommenting(false)}
      />

      <ShareSheet
        video={isSharing && share ? (items.find((item) => item.id === activeId) ?? null) : null}
        url={activeId && share ? share.shareUrlOf(activeId) : ''}
        canShareNative={share?.canShareNative}
        onShareNative={() => {
          if (!activeId) return;
          share?.onShareNative?.(activeId);
          setIsSharing(false);
        }}
        onCopyLink={() => activeId && share?.onCopyLink?.(activeId)}
        onClose={() => setIsSharing(false)}
      />
    </div>
  );
}
