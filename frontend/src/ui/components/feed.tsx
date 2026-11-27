import { useEffect, useRef, useState } from 'react';
import { formatCount } from '../format';
import { Comment, Heart, Play, Share, Stars } from '../icons';
import { Avatar } from './layout';

export interface FeedPostProps {
  creatorName: string;
  productName: string;
  /** 훅 유형 (A·B·C) */
  hookType: string;
  thumbnailUrl?: string;
  videoUrl?: string;
  /** 썸네일 글자 — 글 본문으로도 쓴다 */
  caption?: string;
  likeCount: number;
  isLiked?: boolean;
  /** 댓글 수 */
  commentCount?: number;
  /** 영상을 눌렀을 때: 크게 보기 */
  onOpen?: () => void;
  onToggleLike?: (isLiked: boolean) => void;
  /** 프로필 원·닉네임을 눌렀을 때 → 만든 사람 프로필. 없으면 눌리지 않는다 */
  onOpenCreator?: () => void;
  /** 공유 시트 열기. 없으면 공유 버튼을 숨긴다 */
  onShare?: () => void;
  /** 댓글 시트 열기 */
  onOpenComments?: () => void;
  /** "이 훅으로 만들기" */
  onRemix?: () => void;
}

/** 영상이 화면에 이만큼 보이면 소리 없이 재생한다 */
const PLAY_THRESHOLD = 0.6;

/**
 * 홈 피드의 게시물 한 개 (인스타그램 홈 피드 형식).
 * 머리(만든 사람·제품·훅 유형) → 4:5 영상 → 행동 줄(좋아요·공유 · 이 훅으로 만들기) → 좋아요 수 → 글.
 */
export function FeedPost({
  creatorName,
  productName,
  hookType,
  thumbnailUrl,
  videoUrl,
  caption,
  likeCount,
  isLiked: initialIsLiked = false,
  commentCount = 0,
  onOpen,
  onToggleLike,
  onShare,
  onOpenCreator,
  onOpenComments,
  onRemix,
}: FeedPostProps) {
  const [isLiked, setIsLiked] = useState(initialIsLiked);
  const videoRef = useRef<HTMLVideoElement>(null);
  const shownLikes = likeCount + (isLiked === initialIsLiked ? 0 : isLiked ? 1 : -1);

  // 영상이 있는 게시물은 화면에 들어오면 소리 없이 재생하고, 벗어나면 멈춘다 (움직임 줄이기 설정이면 재생하지 않는다)
  useEffect(() => {
    const video = videoRef.current;
    if (!video || window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.intersectionRatio >= PLAY_THRESHOLD) video.play().catch(() => {});
        else video.pause();
      },
      { threshold: [0, PLAY_THRESHOLD] },
    );
    observer.observe(video);
    return () => observer.disconnect();
  }, [videoUrl]);

  return (
    <article className="n-post" aria-label={`${creatorName}의 ${productName} 영상`}>
      <header className="n-post__head">
        {onOpenCreator ? (
          <button
            type="button"
            className="n-creator-link"
            onClick={onOpenCreator}
            aria-label={`${creatorName} 프로필 보기, ${productName}`}
          >
            <Avatar name={creatorName} />
            <span className="n-post__who" aria-hidden="true">
              <span className="n-post__creator">{creatorName}</span>
              <span className="n-post__product">{productName}</span>
            </span>
          </button>
        ) : (
          <>
            <Avatar name={creatorName} />
            <div className="n-post__who">
              <span className="n-post__creator">{creatorName}</span>
              <span className="n-post__product">{productName}</span>
            </div>
          </>
        )}
        <button type="button" className="n-post__remix" aria-label={`${hookType} 유형 훅으로 만들기`} onClick={onRemix}>
          <span className="n-post__remix-type" aria-hidden="true">
            {hookType}
          </span>
          만들기
        </button>
      </header>

      <button type="button" className="n-post__media" onClick={onOpen} aria-label={`${caption ?? productName} 영상 크게 보기`}>
        {videoUrl ? (
          <video ref={videoRef} src={videoUrl} poster={thumbnailUrl} muted loop playsInline preload="metadata" aria-hidden="true" />
        ) : thumbnailUrl ? (
          <img src={thumbnailUrl} alt="" loading="lazy" decoding="async" />
        ) : (
          <span className="n-post__fallback">{caption ?? productName}</span>
        )}
        <span className="n-post__ai" aria-hidden="true">
          <Stars size={12} />
          AI 연출 포함
        </span>
        {videoUrl ? (
          <span className="n-post__kind" aria-hidden="true">
            <Play size={14} fill="currentColor" />
          </span>
        ) : null}
      </button>

      <div className="n-post__actions">
        <button
          type="button"
          className={`n-post__action${isLiked ? ' is-on' : ''}`}
          aria-pressed={isLiked}
          aria-label="좋아요"
          onClick={() => {
            setIsLiked(!isLiked);
            onToggleLike?.(!isLiked);
          }}
        >
          <Heart size={24} fill={isLiked ? 'currentColor' : 'none'} />
        </button>
        <button type="button" className="n-post__action" aria-label={`댓글 ${commentCount}개`} onClick={onOpenComments}>
          <Comment size={24} />
        </button>
        {onShare ? (
          <button type="button" className="n-post__action" aria-label="공유" onClick={onShare}>
            <Share size={24} />
          </button>
        ) : null}
      </div>

      <div className="n-post__body">
        <p className="n-post__likes n-num">좋아요 {formatCount(shownLikes)}개</p>
        {caption ? (
          <p className="n-post__caption">
            <b>{creatorName}</b> {caption}
          </p>
        ) : null}
        {commentCount > 0 ? (
          <button type="button" className="n-post__comments" onClick={onOpenComments}>
            댓글 {formatCount(commentCount)}개 모두 보기
          </button>
        ) : null}
      </div>
    </article>
  );
}
