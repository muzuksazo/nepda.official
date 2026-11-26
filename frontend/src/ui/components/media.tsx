import type { CSSProperties, ReactNode } from 'react';

/** 9:16 세로 영상 프레임 (검정 바탕) */
export function VideoFrame({
  width,
  size = 'md',
  topContent,
  caption,
  children,
}: {
  width: number | string;
  size?: 'sm' | 'md';
  topContent?: ReactNode;
  caption?: string;
  children?: ReactNode;
}) {
  return (
    <div className={`n-video${size === 'sm' ? ' n-video--sm' : ''}`} style={{ width }}>
      {topContent ? <div className="n-video__top">{topContent}</div> : null}
      {children}
      {caption ? <span className="n-video__bottom">{caption}</span> : null}
    </div>
  );
}

/** 이미지가 아직 없을 때의 자리. 기본은 옅은 라임 틴트(작은 썸네일), sketch는 점 격자 스케치북(큰 그림 콘티) */
export function MediaPlaceholder({
  ratio,
  width = '100%',
  variant = 'tint',
  children,
  style,
}: {
  ratio: string;
  width?: number | string;
  variant?: 'tint' | 'sketch';
  children?: ReactNode;
  style?: CSSProperties;
}) {
  return (
    <div className={`n-media${variant === 'sketch' ? ' n-media--sketch' : ''}`} style={{ width, aspectRatio: ratio, ...style }}>
      {children}
    </div>
  );
}

/** 냅다곰 (장식, 화면당 한 마리) */
export function Mascot({ src, width }: { src: string; width: number }) {
  return <img className="n-mascot" src={src} width={width} alt="" aria-hidden="true" />;
}
