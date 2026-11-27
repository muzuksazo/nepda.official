import type { CSSProperties, ReactNode } from 'react';
import { MASCOT_META } from '../brand';

/** 9:16 세로 영상 프레임 (검정 바탕) */
export function VideoFrame({
  width,
  size = 'md',
  caption,
  children,
}: {
  width: number | string;
  size?: 'sm' | 'md';
  caption?: string;
  children?: ReactNode;
}) {
  return (
    <div className={`n-video${size === 'sm' ? ' n-video--sm' : ''}`} style={{ width }}>
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

/**
 * 냅다곰 크기 단계 = 보이는 높이(px). 화면마다 폭을 따로 정하지 않고 이 넷 중 하나만 쓴다.
 * lg: 빈 상태·결과처럼 화면 가운데 한 마리 · md: 탭 안 빈 목록 · sm: 제목 옆 · xs: 한 줄 상태 글 옆
 */
const MASCOT_HEIGHT = { xs: 44, sm: 56, md: 80, lg: 100 } as const;
export type MascotSize = keyof typeof MASCOT_HEIGHT;

/** 냅다곰 (장식, 화면당 한 마리). 제목 글자보다 튀지 않게 높이를 단계로만 정한다 */
export function Mascot({ src, size = 'lg' }: { src: string; size?: MascotSize }) {
  const meta = MASCOT_META[src] ?? { ratio: 1, heightScale: 1 };
  const height = Math.round(MASCOT_HEIGHT[size] * meta.heightScale);
  const width = Math.round(height * meta.ratio);
  return <img className="n-mascot" src={src} width={width} height={height} alt="" aria-hidden="true" />;
}
