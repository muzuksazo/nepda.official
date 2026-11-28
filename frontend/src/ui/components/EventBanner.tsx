import { useState, type UIEvent } from 'react';
import { ImageIcon } from '../icons';

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
  onSelect?: (id: string) => void;
}

/**
 * 홈 상단 이벤트 배너(최대 3장): 자동으로 넘어가지 않고 첫 장에 멈춰 있다. 손으로 밀어 넘기고,
 * 우측 하단 "1 / 3" 뱃지로 지금 몇 번째인지 보여 준다.
 */
export function EventBanner({ items: allItems, onSelect }: EventBannerProps) {
  // 배너는 최대 3장까지만 보여 준다
  const items = allItems.slice(0, MAX_BANNERS);
  const [index, setIndex] = useState(0);

  const onScroll = (e: UIEvent<HTMLDivElement>) => {
    const el = e.currentTarget;
    setIndex(Math.round(el.scrollLeft / el.clientWidth));
  };

  return (
    <section className="n-banner" aria-roledescription="캐러셀" aria-label="이벤트 배너">
      <div className="n-banner__track" onScroll={onScroll} aria-live="polite">
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
        <span className="n-banner__badge" aria-hidden="true">
          <span className="n-num">
            {index + 1} / {items.length}
          </span>
        </span>
      ) : null}
    </section>
  );
}
