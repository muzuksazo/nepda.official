import { Children, useRef, useState, type ReactNode } from 'react';

export interface CarouselProps {
  /** 스크린 리더용 영역 이름 */
  label: string;
  children: ReactNode;
}

/**
 * 가로로 넘기는 카드 묶음. 다음 카드가 오른쪽에 살짝 보여 넘길 수 있다는 걸 알려 주고,
 * 아래 점으로 현재 위치를 보여 준다. 가로 스크롤은 이 영역 안에서만 일어난다.
 */
export function Carousel({ label, children }: CarouselProps) {
  const items = Children.toArray(children);
  const trackRef = useRef<HTMLDivElement>(null);
  const [index, setIndex] = useState(0);

  const onScroll = () => {
    const el = trackRef.current;
    if (!el || items.length < 2) return;
    const step = el.scrollWidth / items.length;
    setIndex(Math.min(items.length - 1, Math.round(el.scrollLeft / step)));
  };

  return (
    <div className="n-carousel">
      <div
        ref={trackRef}
        className={`n-carousel__track${items.length === 1 ? ' is-single' : ''}`}
        role="region"
        aria-roledescription="캐러셀"
        aria-label={label}
        tabIndex={0}
        onScroll={onScroll}
      >
        {items.map((item, i) => (
          <div
            key={i}
            className="n-carousel__item"
            role="group"
            aria-roledescription="슬라이드"
            aria-label={`${items.length}개 중 ${i + 1}번째`}
          >
            {item}
          </div>
        ))}
      </div>
      {items.length > 1 ? (
        <div className="n-carousel__dots" aria-hidden="true">
          {items.map((_, i) => (
            <span key={i} className={`n-carousel__dot${i === index ? ' is-on' : ''}`} />
          ))}
        </div>
      ) : null}
    </div>
  );
}
