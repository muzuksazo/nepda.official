import type { CSSProperties, ReactNode } from 'react';
import { brand } from '../brand';
import {
  computeSerifOutlineFontSize,
  SANS_FONT_FAMILY,
  SERIF_FONT_FAMILY,
  THUMBNAIL_HEIGHT,
  THUMBNAIL_WIDTH,
  type ThumbnailTemplateProps,
} from './presets';

function renderHighlightedLine(
  line: string,
  highlightWord: string | undefined,
  highlightStyle: CSSProperties,
): ReactNode {
  const target = highlightWord?.trim();
  if (!target || !line.includes(target)) return line;
  const idx = line.indexOf(target);
  const before = line.slice(0, idx);
  const after = line.slice(idx + target.length);
  return (
    <>
      {before}
      <span style={highlightStyle}>{target}</span>
      {after}
    </>
  );
}

const imageFillStyle: CSSProperties = {
  position: 'absolute',
  inset: 0,
  width: '100%',
  height: '100%',
  objectFit: 'cover',
  display: 'block',
};

function buildImageTransformStyle(
  scale = 1,
  offsetX = 0,
  offsetY = 0,
): CSSProperties {
  return {
    ...imageFillStyle,
    transform: `translate(${offsetX}px, ${offsetY}px) scale(${scale})`,
    transformOrigin: 'center center',
  };
}

function BottomGradientScrim({ visible }: { visible?: boolean }) {
  if (!visible) return null;
  return (
    <div
      style={{
        position: 'absolute',
        left: 0,
        right: 0,
        bottom: 0,
        height: 980,
        background:
          'linear-gradient(180deg, rgba(0,0,0,0) 0%, rgba(0,0,0,0.48) 42%, rgba(0,0,0,0.92) 100%)',
        pointerEvents: 'none',
        zIndex: 2,
      }}
    />
  );
}

const placeholderLabelStyle: CSSProperties = {
  fontSize: 30,
  fontWeight: 600,
  color: '#8a8a8a',
  letterSpacing: '-0.02em',
  textAlign: 'center',
  userSelect: 'none',
};

function EmptyBackdrop({ label }: { label: string }) {
  return (
    <div
      style={{
        position: 'absolute',
        inset: 0,
        background: 'radial-gradient(circle at 50% 45%, #232730 0%, #101216 75%)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
      }}
    >
      <span style={placeholderLabelStyle}>{label}</span>
    </div>
  );
}

function SafeZoneOverlay() {
  return (
    <div
      style={{
        position: 'absolute',
        inset: 0,
        pointerEvents: 'none',
        zIndex: 30,
      }}
    >
      {/* 피그마 #114:383 릴스 금지 영역 마스크 (단일 SVG evenodd 경로로 경계 이음매 없음) */}
      <svg
        width={1080}
        height={1920}
        viewBox="0 0 1080 1920"
        style={{ position: 'absolute', inset: 0, display: 'block' }}
      >
        <path
          fillRule="evenodd"
          fill="rgba(220, 24, 24, 0.5)"
          d="M0,0 H1080 V1920 H0 Z M63,168 H1016 V1094 H924 V1396 H63 Z"
        />
        <path
          fill="none"
          stroke="rgba(255, 72, 72, 0.85)"
          strokeWidth={2}
          d="M63,168 H1016 V1094 H924 V1396 H63 Z"
        />
      </svg>
      {/* 3:4 프로필 피드 크롭 기준선 (y: 240..1680) */}
      <div
        style={{
          position: 'absolute',
          left: 0,
          right: 0,
          top: 240,
          height: 1440,
          borderTop: '3px dashed rgba(214, 255, 63, 0.65)',
          borderBottom: '3px dashed rgba(214, 255, 63, 0.65)',
        }}
      />
      <div
        style={{
          position: 'absolute',
          left: 63,
          top: 112,
          backgroundColor: 'rgba(185, 28, 28, 0.92)',
          color: '#ffffff',
          fontSize: 22,
          fontWeight: 700,
          padding: '6px 14px',
          borderRadius: 999,
        }}
      >
        넘으면 안 되는 릴스 UI 영역
      </div>
    </div>
  );
}

function OptionalWordmark({ visible }: { visible?: boolean }) {
  if (!visible) return null;
  return (
    <img
      src={brand.wordmarkWhite}
      alt="NAPDA"
      draggable={false}
      style={{
        position: 'absolute',
        right: 96,
        top: 1410,
        height: 40,
        width: 'auto',
        opacity: 0.92,
        filter: 'drop-shadow(0 2px 10px rgba(0,0,0,0.65))',
        zIndex: 10,
        pointerEvents: 'none',
      }}
    />
  );
}

function OptionalBadgePill({ text }: { text?: string }) {
  const clean = text?.trim();
  if (!clean) return null;
  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        backgroundColor: '#d6ff3f',
        color: '#000000',
        fontSize: 28,
        fontWeight: 800,
        letterSpacing: '-0.02em',
        padding: '10px 26px',
        borderRadius: 999,
        marginBottom: 18,
      }}
    >
      {clean}
    </span>
  );
}

function OptionalSubtitlePill({ text }: { text?: string }) {
  const clean = text?.trim();
  if (!clean) return null;
  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        backgroundColor: '#020202',
        color: '#ffffff',
        fontSize: 36,
        fontWeight: 700,
        letterSpacing: '-0.02em',
        padding: '12px 28px',
        borderRadius: 12,
        marginTop: 22,
      }}
    >
      {clean}
    </span>
  );
}

type CanvasCommonProps = Pick<
  ThumbnailTemplateProps,
  | 'badge'
  | 'headline'
  | 'highlightWord'
  | 'subtitle'
  | 'imageUrl'
  | 'showBottomGradient'
  | 'imageScale'
  | 'imageOffsetX'
  | 'imageOffsetY'
  | 'showWordmark'
>;

/**
 * 1080×1920 Figma 릴스 커버 4가지 제목 스타일 템플릿 컴포넌트.
 * 하단 검은 그라데이션 스크림은 기본 꺼짐이며 토글로 켜고 끌 수 있다.
 */
export function ThumbnailTemplate({
  variant,
  badge,
  headline,
  highlightWord,
  subtitle,
  imageUrl,
  showBottomGradient = false,
  imageScale = 1,
  imageOffsetX = 0,
  imageOffsetY = 0,
  showWordmark = false,
  showSafeZone = false,
  scale = 0.33,
}: ThumbnailTemplateProps) {
  const outerW = Math.round(THUMBNAIL_WIDTH * scale);
  const outerH = Math.round(THUMBNAIL_HEIGHT * scale);

  const canvasProps: CanvasCommonProps = {
    badge,
    headline,
    highlightWord,
    subtitle,
    imageUrl,
    showBottomGradient,
    imageScale,
    imageOffsetX,
    imageOffsetY,
    showWordmark,
  };

  return (
    <div
      style={{
        width: outerW,
        height: outerH,
        position: 'relative',
        overflow: 'hidden',
        borderRadius: 16,
        boxShadow: '0 12px 36px rgb(0 0 0 / 0.24)',
        backgroundColor: '#000000',
        flexShrink: 0,
      }}
    >
      <div
        style={{
          width: THUMBNAIL_WIDTH,
          height: THUMBNAIL_HEIGHT,
          transform: `scale(${scale})`,
          transformOrigin: 'top left',
          position: 'relative',
          overflow: 'hidden',
          fontFamily: SANS_FONT_FAMILY,
        }}
      >
        {variant === 'invert-box' && <InvertBoxCanvas {...canvasProps} />}
        {variant === 'white-label' && <WhiteLabelCanvas {...canvasProps} />}
        {variant === 'serif-outline' && <SerifOutlineCanvas {...canvasProps} />}
        {variant === 'pov-bar' && <PovBarCanvas {...canvasProps} />}
        {showSafeZone && <SafeZoneOverlay />}
      </div>
    </div>
  );
}

/** 스타일 1: 화이트/블랙 반전 2줄 박스 (#101:842 · #114:389) */
function InvertBoxCanvas({
  badge,
  headline,
  highlightWord,
  subtitle,
  imageUrl,
  showBottomGradient,
  imageScale,
  imageOffsetX,
  imageOffsetY,
  showWordmark,
}: CanvasCommonProps) {
  const lines = headline?.trim() ? headline.split('\n').filter((l) => l.length > 0) : [];

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%', backgroundColor: '#111317', overflow: 'hidden' }}>
      {imageUrl ? (
        <img
          src={imageUrl}
          alt="배경 이미지"
          draggable={false}
          style={buildImageTransformStyle(imageScale, imageOffsetX, imageOffsetY)}
        />
      ) : (
        <EmptyBackdrop label="배경 스틸컷 / 영상 캡처 영역 (1080×1920)" />
      )}

      <BottomGradientScrim visible={showBottomGradient} />

      {(badge?.trim() || lines.length > 0 || subtitle?.trim()) && (
        <div
          style={{
            position: 'absolute',
            left: 64,
            right: 64,
            top: 296,
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            zIndex: 4,
            pointerEvents: 'none',
          }}
        >
          <OptionalBadgePill text={badge} />
          {lines.map((line, idx) => {
            const isOdd = idx % 2 === 1;
            return (
              <div
                key={idx}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  backgroundColor: isOdd ? '#020202' : '#ffffff',
                  color: isOdd ? '#ffffff' : '#111111',
                  fontSize: 78,
                  fontWeight: 500,
                  lineHeight: 1.16,
                  letterSpacing: '-0.03em',
                  padding: '10px 22px',
                  maxWidth: '100%',
                  textAlign: 'center',
                }}
              >
                <span>
                  {renderHighlightedLine(
                    line,
                    highlightWord,
                    isOdd
                      ? { color: '#d6ff3f', fontWeight: 700 }
                      : {
                          backgroundColor: '#d6ff3f',
                          color: '#000000',
                          padding: '0 8px',
                          borderRadius: 8,
                          fontWeight: 700,
                        },
                  )}
                </span>
              </div>
            );
          })}
          <OptionalSubtitlePill text={subtitle} />
        </div>
      )}

      <OptionalWordmark visible={showWordmark} />
    </div>
  );
}

/** 스타일 2: 좌측정렬 화이트 라벨 2줄 (#105:263) */
function WhiteLabelCanvas({
  badge,
  headline,
  highlightWord,
  subtitle,
  imageUrl,
  showBottomGradient,
  imageScale,
  imageOffsetX,
  imageOffsetY,
  showWordmark,
}: CanvasCommonProps) {
  const lines = headline?.trim() ? headline.split('\n').filter((l) => l.length > 0) : [];

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%', backgroundColor: '#12151c', overflow: 'hidden' }}>
      {imageUrl ? (
        <img
          src={imageUrl}
          alt="배경 이미지"
          draggable={false}
          style={buildImageTransformStyle(imageScale, imageOffsetX, imageOffsetY)}
        />
      ) : (
        <EmptyBackdrop label="배경 스틸컷 / 영상 캡처 영역 (1080×1920)" />
      )}

      <BottomGradientScrim visible={showBottomGradient} />

      {(badge?.trim() || lines.length > 0 || subtitle?.trim()) && (
        <div
          style={{
            position: 'absolute',
            left: 68,
            right: 68,
            top: 340,
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'flex-start',
            gap: 0,
            zIndex: 4,
            pointerEvents: 'none',
          }}
        >
          <OptionalBadgePill text={badge} />
          {lines.map((line, idx) => (
            <div
              key={idx}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                backgroundColor: '#ffffff',
                color: '#000000',
                fontSize: 92,
                fontWeight: 700,
                lineHeight: 1.12,
                letterSpacing: '-0.03em',
                padding: '10px 20px',
                maxWidth: '100%',
              }}
            >
              <span>
                {renderHighlightedLine(line, highlightWord, {
                  backgroundColor: '#d6ff3f',
                  color: '#000000',
                  padding: '0 8px',
                  borderRadius: 8,
                })}
              </span>
            </div>
          ))}
          <OptionalSubtitlePill text={subtitle} />
        </div>
      )}

      <OptionalWordmark visible={showWordmark} />
    </div>
  );
}

/** 스타일 3: 대형 명조 외곽선 임팩트 (#105:264 · #105:265) */
function SerifOutlineCanvas({
  badge,
  headline,
  highlightWord,
  subtitle,
  imageUrl,
  showBottomGradient,
  imageScale,
  imageOffsetX,
  imageOffsetY,
  showWordmark,
}: CanvasCommonProps) {
  const headlineText = headline?.trim() ?? '';
  const lines = headlineText ? headlineText.split('\n') : [];
  const fontSize = computeSerifOutlineFontSize(headlineText || '제목');

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%', backgroundColor: '#141414', overflow: 'hidden' }}>
      {imageUrl ? (
        <img
          src={imageUrl}
          alt="배경 이미지"
          draggable={false}
          style={buildImageTransformStyle(imageScale, imageOffsetX, imageOffsetY)}
        />
      ) : (
        <EmptyBackdrop label="배경 스틸컷 / 제품 풀샷 영역 (1080×1920)" />
      )}

      <BottomGradientScrim visible={showBottomGradient} />

      {(badge?.trim() || lines.length > 0 || subtitle?.trim()) && (
        <div
          style={{
            position: 'absolute',
            left: 56,
            right: 56,
            top: 235,
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            textAlign: 'center',
            gap: 16,
            zIndex: 4,
            pointerEvents: 'none',
          }}
        >
          {badge?.trim() && (
            <div
              style={{
                fontFamily: SERIF_FONT_FAMILY,
                fontStyle: 'italic',
                fontWeight: 700,
                fontSize: 52,
                lineHeight: 1.2,
                letterSpacing: '-0.02em',
                color: '#ffffff',
                WebkitTextStroke: '10px #000000',
                paintOrder: 'stroke fill',
                filter: 'drop-shadow(0 4px 14px rgba(0,0,0,0.45))',
              }}
            >
              {badge}
            </div>
          )}

          {lines.length > 0 && (
            <h1
              style={{
                margin: 0,
                fontFamily: SERIF_FONT_FAMILY,
                fontWeight: 700,
                fontSize,
                lineHeight: 1.06,
                letterSpacing: '-0.03em',
                color: '#000000',
                WebkitTextStroke: '22px #ffffff',
                paintOrder: 'stroke fill',
                filter: 'drop-shadow(0 8px 20px rgba(0,0,0,0.32))',
              }}
            >
              {lines.map((line, i) => (
                <span key={i} style={{ display: 'block' }}>
                  {renderHighlightedLine(line, highlightWord, {
                    color: '#d6ff3f',
                    WebkitTextStroke: '22px #000000',
                    paintOrder: 'stroke fill',
                  })}
                </span>
              ))}
            </h1>
          )}

          <OptionalSubtitlePill text={subtitle} />
        </div>
      )}

      <OptionalWordmark visible={showWordmark} />
    </div>
  );
}

/** 스타일 4: 상단 블랙 바 POV 밈형 (#121:404) */
function PovBarCanvas({
  badge,
  headline,
  highlightWord,
  subtitle,
  imageUrl,
  showBottomGradient,
  imageScale,
  imageOffsetX,
  imageOffsetY,
  showWordmark,
}: CanvasCommonProps) {
  const headlineText = headline?.trim() ?? '';
  const lines = headlineText ? headlineText.split('\n') : [];

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%', backgroundColor: '#000000' }}>
      {/* 상단 솔리드 블랙 바 (3:4·9:16 안전 영역 y >= 250 내부에 2~3줄 POV 텍스트 배치) */}
      <div
        style={{
          position: 'absolute',
          left: 0,
          right: 0,
          top: 0,
          height: 560,
          backgroundColor: '#000000',
          padding: '248px 72px 28px',
          boxSizing: 'border-box',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          textAlign: 'center',
          zIndex: 4,
          pointerEvents: 'none',
        }}
      >
        <OptionalBadgePill text={badge} />
        {lines.length > 0 && (
          <h1
            style={{
              margin: 0,
              color: '#ffffff',
              fontSize: 60,
              fontWeight: 700,
              lineHeight: 1.32,
              letterSpacing: '-0.025em',
            }}
          >
            {lines.map((line, i) => (
              <span key={i} style={{ display: 'block' }}>
                {renderHighlightedLine(line, highlightWord, { color: '#d6ff3f' })}
              </span>
            ))}
          </h1>
        )}
      </div>

      {/* 하단 이미지 영역 (그라데이션 토글 지원) */}
      <div
        style={{
          position: 'absolute',
          left: 0,
          right: 0,
          top: 560,
          height: 1360,
          overflow: 'hidden',
          backgroundColor: '#111317',
        }}
      >
        {imageUrl ? (
          <img
            src={imageUrl}
            alt="본문 이미지"
            draggable={false}
            style={buildImageTransformStyle(imageScale, imageOffsetX, imageOffsetY)}
          />
        ) : (
          <EmptyBackdrop label="이미지 / 영상 캡처 영역 (1080×1360)" />
        )}
      </div>

      <BottomGradientScrim visible={showBottomGradient} />

      {/* 선택적 하단 블랙 캡션 박스 */}
      {subtitle?.trim() && (
        <div
          style={{
            position: 'absolute',
            left: 72,
            right: 72,
            top: 1340,
            display: 'flex',
            justifyContent: 'center',
            zIndex: 6,
            pointerEvents: 'none',
          }}
        >
          <span
            style={{
              backgroundColor: '#000000',
              color: '#ffffff',
              fontSize: 44,
              fontWeight: 700,
              lineHeight: 1.25,
              letterSpacing: '-0.02em',
              padding: '14px 28px',
              textAlign: 'center',
            }}
          >
            {subtitle}
          </span>
        </div>
      )}

      <OptionalWordmark visible={showWordmark} />
    </div>
  );
}
