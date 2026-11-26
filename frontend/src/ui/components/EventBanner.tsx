import { useCallback, useEffect, useRef, useState } from 'react';
import { ImageIcon, Pause, Play } from 'lucide-react';

import { BANNER_SIZE, MAX_BANNERS } from './bannerSpec';

export interface BannerItem {
  id: string;
  /** 배너 이미지. 없으면 규격 자리표시를 보여 준다 */
  imageUrl?: string;
  /** 이미지 대체 텍스트 (배너에 적힌 문구를 그대로) */
  alt: string;
}

export interface EventBannerProps {
  items: BannerItem[];
  /** 자동 회전 간격(ms) */
  intervalMs?: number;
  onSelect?: (id: string) => void;
}

/** 홈 상단 이벤트 배너(최대 3장): 자동 회전 + 손으로 넘기기 + 우측 하단 "1 / 3" 뱃지(누르면 일시정지) */
export function EventBanner({ items: allItems, intervalMs = 4000, onSelect }: EventBannerProps) {
  // 배너는 최대 3장까지만 보여 준다
  const items = allItems.slice(0, MAX_BANNERS);
  const trackRef = useRef<HTMLDivElement>(null);
  const [index, setIndex] = useState(0);
  const [userPaused, setUserPaused] = useState(false);
  const [hoverPaused, setHoverPaused] = useState(false);
  const [reducedMotion, setReducedMotion] = useState(
    () => typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches,
  );

  useEffect(() => {
    const mq = window.matchMedia('(prefers-reduced-motion: reduce)');
    const onChange = () => setReducedMotion(mq.matches);
    mq.addEventListener('change', onChange);
    return () => mq.removeEventListener('change', onChange);
  }, []);

  const goTo = useCallback((i: number) => {
    const el = trackRef.current;
    if (!el) return;
    el.scrollTo({ left: i * el.clientWidth, behavior: reducedMotion ? 'auto' : 'smooth' });
  }, [reducedMotion]);

  const paused = userPaused || hoverPaused || reducedMotion || items.length < 2;

  useEffect(() => {
    if (paused) return;
    const t = window.setInterval(() => goTo((index + 1) % items.length), intervalMs);
    return () => window.clearInterval(t);
  }, [paused, index, items.length, intervalMs, goTo]);

  const onScroll = () => {
    const el = trackRef.current;
    if (!el) return;
    setIndex(Math.round(el.scrollLeft / el.clientWidth));
  };

  return (
    <section
      className="n-banner"
      aria-roledescription="캐러셀"
      aria-label="이벤트 배너"
      onMouseEnter={() => setHoverPaused(true)}
      onMouseLeave={() => setHoverPaused(false)}
      onFocus={() => setHoverPaused(true)}
      onBlur={() => setHoverPaused(false)}
    >
      <div ref={trackRef} className="n-banner__track" onScroll={onScroll} aria-live={paused ? 'polite' : 'off'}>
        {items.map((item, i) => (
          <button
            key={item.id}
            type="button"
            className="n-banner__slide"
            aria-roledescription="슬라이드"
            aria-label={`${items.length}개 중 ${i + 1}번째: ${item.alt}`}
            onClick={() => onSelect?.(item.id)}
          >
            {item.imageUrl ? (
              <img src={item.imageUrl} alt="" />
            ) : (
              <span className="n-banner__placeholder">
                <ImageIcon size={22} aria-hidden="true" />
                <span>
                  배너 {i + 1} · {BANNER_SIZE.exportWidth}×{BANNER_SIZE.exportHeight}
                </span>
              </span>
            )}
          </button>
        ))}
      </div>
      {items.length > 1 ? (
        <button
          type="button"
          className="n-banner__badge"
          aria-label={userPaused ? '배너 자동 넘김 다시 시작' : '배너 자동 넘김 멈추기'}
          onClick={() => setUserPaused((p) => !p)}
        >
          <span className="n-num">
            {index + 1} / {items.length}
          </span>
          {userPaused ? <Play size={11} fill="currentColor" aria-hidden="true" /> : <Pause size={11} fill="currentColor" aria-hidden="true" />}
        </button>
      ) : null}
    </section>
  );
}
