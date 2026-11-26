import type { CSSProperties, ReactNode } from 'react';
import { brand } from '../brand';
import {
  THUMBNAIL_HEIGHT,
  THUMBNAIL_WIDTH,
  type ThumbnailTemplateProps,
} from './presets';

function renderHighlightedText(
  text: string,
  highlightWord?: string,
  accentColor = '#d6ff3f',
  asMarker = false,
): ReactNode {
  const lines = text.split('\n');
  return lines.map((line, lineIdx) => {
    const content =
      highlightWord && highlightWord.trim().length > 0 && line.includes(highlightWord)
        ? splitHighlight(line, highlightWord, accentColor, asMarker)
        : line;
    return (
      <span key={lineIdx} style={{ display: 'block' }}>
        {content}
      </span>
    );
  });
}

function splitHighlight(
  line: string,
  target: string,
  accentColor: string,
  asMarker = false,
): ReactNode {
  const idx = line.indexOf(target);
  if (idx === -1) return line;
  const before = line.slice(0, idx);
  const after = line.slice(idx + target.length);
  return (
    <>
      {before}
      <span
        style={
          asMarker
            ? {
                backgroundColor: accentColor,
                color: '#000000',
                padding: '2px 12px',
                borderRadius: 12,
                display: 'inline-block',
                lineHeight: 1.08,
              }
            : { color: accentColor }
        }
      >
        {target}
      </span>
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

const placeholderLabelStyle: CSSProperties = {
  fontSize: 30,
  fontWeight: 600,
  color: '#8a8a8a',
  letterSpacing: '-0.02em',
  textAlign: 'center',
  userSelect: 'none',
};

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
      {/* 3:4 프로필 피드 크롭 영역 (y: 240..1680) */}
      <div
        style={{
          position: 'absolute',
          left: 0,
          right: 0,
          top: 240,
          height: 1440,
          borderTop: '3px dashed rgba(214, 255, 63, 0.7)',
          borderBottom: '3px dashed rgba(214, 255, 63, 0.7)',
        }}
      />
      {/* 릴스 안전 영역 (x: 96..984, y: 260..1500) */}
      <div
        style={{
          position: 'absolute',
          left: 96,
          top: 260,
          width: 888,
          height: 1240,
          border: '3px solid rgba(56, 189, 248, 0.78)',
          borderRadius: 24,
        }}
      />
      <div
        style={{
          position: 'absolute',
          left: 96,
          top: 204,
          backgroundColor: 'rgba(10, 10, 10, 0.85)',
          color: '#38bdf8',
          fontSize: 22,
          fontWeight: 700,
          padding: '6px 14px',
          borderRadius: 999,
        }}
      >
        REELS SAFE ZONE (96..984 × 260..1500)
      </div>
    </div>
  );
}

/**
 * 1080×1920 릴스·쇼츠 썸네일 템플릿 컴포넌트.
 * 냅다 DESIGN.md 토큰(#0a0a0a / #ffffff / #d6ff3f 포인트 1단어·배지)을 따른다.
 */
export function ThumbnailTemplate({
  variant,
  badge,
  headline,
  highlightWord,
  subtitle,
  imageUrl,
  bottomImageUrl,
  realityBadge = '현실 · REALITY',
  showWordmark = true,
  showSafeZone = false,
  scale = 0.33,
}: ThumbnailTemplateProps) {
  const outerW = Math.round(THUMBNAIL_WIDTH * scale);
  const outerH = Math.round(THUMBNAIL_HEIGHT * scale);

  return (
    <div
      style={{
        width: outerW,
        height: outerH,
        position: 'relative',
        overflow: 'hidden',
        borderRadius: 16,
        boxShadow: '0 12px 36px rgb(0 0 0 / 0.24)',
        backgroundColor: variant === 'commerce' ? '#f7f7f5' : '#0a0a0a',
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
          fontFamily: "var(--font-sans, 'Pretendard Variable', Pretendard, sans-serif)",
        }}
      >
        {variant === 'editorial' && (
          <EditorialCanvas
            badge={badge}
            headline={headline}
            highlightWord={highlightWord}
            subtitle={subtitle}
            imageUrl={imageUrl}
            showWordmark={showWordmark}
          />
        )}
        {variant === 'viral-hook' && (
          <ViralHookCanvas
            badge={badge}
            headline={headline}
            highlightWord={highlightWord}
            subtitle={subtitle}
            imageUrl={imageUrl}
            showWordmark={showWordmark}
          />
        )}
        {variant === 'split-vs' && (
          <SplitVsCanvas
            badge={badge}
            realityBadge={realityBadge}
            headline={headline}
            highlightWord={highlightWord}
            subtitle={subtitle}
            imageUrl={imageUrl}
            bottomImageUrl={bottomImageUrl}
          />
        )}
        {variant === 'commerce' && (
          <CommerceCanvas
            badge={badge}
            headline={headline}
            highlightWord={highlightWord}
            subtitle={subtitle}
            imageUrl={imageUrl}
            showWordmark={showWordmark}
          />
        )}
        {showSafeZone && <SafeZoneOverlay />}
      </div>
    </div>
  );
}

function EditorialCanvas({
  badge,
  headline,
  highlightWord,
  subtitle,
  imageUrl,
  showWordmark,
}: Pick<ThumbnailTemplateProps, 'badge' | 'headline' | 'highlightWord' | 'subtitle' | 'imageUrl' | 'showWordmark'>) {
  return (
    <div style={{ position: 'relative', width: '100%', height: '100%', backgroundColor: '#111317' }}>
      {imageUrl ? (
        <img src={imageUrl} alt="배경 이미지" style={imageFillStyle} />
      ) : (
        <div
          style={{
            position: 'absolute',
            inset: 0,
            background: 'radial-gradient(circle at 50% 35%, #232730 0%, #101216 70%)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            paddingBottom: 260,
          }}
        >
          <span style={placeholderLabelStyle}>배경 스틸컷 / 영상 캡처 영역 (1080×1920)</span>
        </div>
      )}

      {/* 하단 가독성 그라디언트 스크림 */}
      <div
        style={{
          position: 'absolute',
          left: 0,
          right: 0,
          bottom: 0,
          height: 980,
          background:
            'linear-gradient(180deg, rgba(0,0,0,0) 0%, rgba(0,0,0,0.48) 42%, rgba(0,0,0,0.92) 100%)',
        }}
      />

      {/* 상단 배지 + 선택적 워드마크 */}
      <div
        style={{
          position: 'absolute',
          left: 96,
          right: 96,
          top: 280,
          display: 'flex',
          alignItems: 'center',
          justifyContent: badge?.trim() ? 'space-between' : 'flex-end',
        }}
      >
        {badge?.trim() && (
          <span
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              backgroundColor: '#d6ff3f',
              color: '#000000',
              fontSize: 30,
              fontWeight: 800,
              letterSpacing: '-0.02em',
              padding: '16px 32px',
              borderRadius: 16,
            }}
          >
            {badge}
          </span>
        )}
        {showWordmark && (
          <img
            src={brand.wordmarkWhite}
            alt="NAPDA"
            style={{ height: 40, width: 'auto', opacity: 0.92 }}
          />
        )}
      </div>

      {/* 하단 타이포 */}
      {(headline?.trim() || subtitle?.trim()) && (
        <div style={{ position: 'absolute', left: 96, right: 96, top: 1110 }}>
          {headline?.trim() && (
            <h1
              style={{
                margin: 0,
                color: '#ffffff',
                fontSize: 80,
                fontWeight: 800,
                lineHeight: 1.18,
                letterSpacing: '-0.03em',
                textShadow: '0 8px 40px rgba(0,0,0,0.85)',
              }}
            >
              {renderHighlightedText(headline, highlightWord)}
            </h1>
          )}
          {subtitle?.trim() && (
            <p
              style={{
                margin: headline?.trim() ? '28px 0 0' : 0,
                color: '#d4d4d4',
                fontSize: 48,
                fontWeight: 300,
                letterSpacing: '-0.02em',
                lineHeight: 1.25,
              }}
            >
              {subtitle}
            </p>
          )}
        </div>
      )}
    </div>
  );
}

function ViralHookCanvas({
  badge,
  headline,
  highlightWord,
  subtitle,
  imageUrl,
  showWordmark,
}: Pick<ThumbnailTemplateProps, 'badge' | 'headline' | 'highlightWord' | 'subtitle' | 'imageUrl' | 'showWordmark'>) {
  return (
    <div style={{ position: 'relative', width: '100%', height: '100%', backgroundColor: '#12151c' }}>
      {imageUrl ? (
        <img src={imageUrl} alt="바이럴 훅 배경" style={imageFillStyle} />
      ) : (
        <div
          style={{
            position: 'absolute',
            inset: 0,
            background: 'linear-gradient(160deg, #1b2230 0%, #0f1117 65%)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            paddingBottom: 320,
          }}
        >
          <span style={placeholderLabelStyle}>바이럴 훅 1프레임 스틸컷 (1080×1920)</span>
        </div>
      )}

      <div
        style={{
          position: 'absolute',
          left: 0,
          right: 0,
          bottom: 0,
          height: 1060,
          background:
            'linear-gradient(180deg, rgba(10,10,10,0) 0%, rgba(10,10,10,0.72) 38%, rgba(10,10,10,0.95) 100%)',
        }}
      />

      <div
        style={{
          position: 'absolute',
          left: 96,
          right: 96,
          top: 296,
          display: 'flex',
          alignItems: 'center',
          justifyContent: badge?.trim() ? 'space-between' : 'flex-end',
        }}
      >
        {badge?.trim() && (
          <span
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              backgroundColor: '#d6ff3f',
              color: '#000000',
              fontSize: 36,
              fontWeight: 800,
              letterSpacing: '-0.02em',
              padding: '16px 38px',
              borderRadius: 999,
            }}
          >
            {badge}
          </span>
        )}
        {showWordmark && (
          <img src={brand.wordmarkWhite} alt="NAPDA" style={{ height: 38, opacity: 0.85 }} />
        )}
      </div>

      {/* 세로 라임 포인트 바 + 2줄 헤드라인 */}
      {(headline?.trim() || subtitle?.trim()) && (
        <div
          style={{
            position: 'absolute',
            left: 96,
            right: 96,
            top: 1080,
            display: 'flex',
            alignItems: 'stretch',
            gap: 26,
          }}
        >
          <div
            style={{
              width: 14,
              borderRadius: 999,
              backgroundColor: '#d6ff3f',
              flexShrink: 0,
            }}
          />
          <div style={{ flex: 1 }}>
            {headline?.trim() && (
              <h1
                style={{
                  margin: 0,
                  color: '#ffffff',
                  fontSize: 74,
                  fontWeight: 800,
                  lineHeight: 1.2,
                  letterSpacing: '-0.03em',
                  textShadow: '0 6px 28px rgba(0,0,0,0.8)',
                }}
              >
                {renderHighlightedText(headline, highlightWord)}
              </h1>
            )}
            {subtitle?.trim() && (
              <p
                style={{
                  margin: headline?.trim() ? '24px 0 0' : 0,
                  color: '#d4d4d4',
                  fontSize: 36,
                  fontWeight: 500,
                  letterSpacing: '-0.02em',
                }}
              >
                {subtitle}
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function SplitVsCanvas({
  badge,
  realityBadge,
  headline,
  highlightWord,
  subtitle,
  imageUrl,
  bottomImageUrl,
}: Pick<
  ThumbnailTemplateProps,
  'badge' | 'realityBadge' | 'headline' | 'highlightWord' | 'subtitle' | 'imageUrl' | 'bottomImageUrl'
>) {
  return (
    <div style={{ position: 'relative', width: '100%', height: '100%', backgroundColor: '#0a0a0a' }}>
      {/* 상단 50% 비교 컷 */}
      <div
        style={{
          position: 'absolute',
          left: 0,
          top: 0,
          width: 1080,
          height: 954,
          overflow: 'hidden',
          background: 'linear-gradient(180deg, #1b2434 0%, #111622 100%)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        {imageUrl ? (
          <img
            src={imageUrl}
            alt="상단 비교 컷"
            style={{ ...imageFillStyle, objectPosition: 'center 25%' }}
          />
        ) : (
          <span style={placeholderLabelStyle}>상단 비교 컷 (기대 / BEFORE)</span>
        )}
      </div>

      {/* 하단 50% 비교 컷 */}
      <div
        style={{
          position: 'absolute',
          left: 0,
          top: 966,
          width: 1080,
          height: 954,
          overflow: 'hidden',
          background: 'linear-gradient(180deg, #241921 0%, #140f13 100%)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          paddingBottom: 180,
        }}
      >
        {bottomImageUrl ? (
          <img
            src={bottomImageUrl}
            alt="하단 비교 컷"
            style={{ ...imageFillStyle, objectPosition: 'center 6%' }}
          />
        ) : (
          <span style={{ ...placeholderLabelStyle, color: '#a38d98' }}>하단 비교 컷 (현실 / AFTER)</span>
        )}
      </div>

      {/* 라임 구분선 + 중앙 VS */}
      <div
        style={{
          position: 'absolute',
          left: 0,
          top: 954,
          width: 1080,
          height: 12,
          backgroundColor: '#d6ff3f',
        }}
      />
      <div
        style={{
          position: 'absolute',
          left: 460,
          top: 880,
          width: 160,
          height: 160,
          borderRadius: 999,
          backgroundColor: '#d6ff3f',
          border: '10px solid #0a0a0a',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontSize: 64,
          fontWeight: 900,
          color: '#000000',
          letterSpacing: '-0.03em',
          boxSizing: 'border-box',
        }}
      >
        VS
      </div>

      {/* 상단 기대 배지 */}
      {badge?.trim() && (
        <div
          style={{
            position: 'absolute',
            left: 96,
            top: 290,
            backgroundColor: '#0a0a0a',
            border: '3px solid #ffffff',
            color: '#ffffff',
            fontSize: 32,
            fontWeight: 700,
            padding: '16px 34px',
            borderRadius: 999,
          }}
        >
          {badge}
        </div>
      )}

      {/* 하단 현실 배지 */}
      {realityBadge?.trim() && (
        <div
          style={{
            position: 'absolute',
            left: 96,
            top: 1044,
            backgroundColor: '#d6ff3f',
            border: '3px solid #0a0a0a',
            color: '#000000',
            fontSize: 32,
            fontWeight: 800,
            padding: '16px 34px',
            borderRadius: 999,
          }}
        >
          {realityBadge}
        </div>
      )}

      {/* 하단 펀치라인 카드 */}
      {(headline?.trim() || subtitle?.trim()) && (
        <div
          style={{
            position: 'absolute',
            left: 72,
            right: 72,
            top: 1256,
            backgroundColor: 'rgba(10, 10, 10, 0.92)',
            border: '3px solid #d6ff3f',
            borderRadius: 28,
            padding: '34px 44px',
            textAlign: 'center',
          }}
        >
          {headline?.trim() && (
            <h1
              style={{
                margin: 0,
                color: '#ffffff',
                fontSize: 54,
                fontWeight: 800,
                letterSpacing: '-0.03em',
                lineHeight: 1.2,
              }}
            >
              {renderHighlightedText(headline, highlightWord)}
            </h1>
          )}
          {subtitle?.trim() && (
            <p
              style={{
                margin: headline?.trim() ? '14px 0 0' : 0,
                color: '#a6a6a6',
                fontSize: 32,
                fontWeight: 500,
                letterSpacing: '-0.02em',
              }}
            >
              {subtitle}
            </p>
          )}
        </div>
      )}
    </div>
  );
}

function CommerceCanvas({
  badge,
  headline,
  highlightWord,
  subtitle,
  imageUrl,
  showWordmark,
}: Pick<ThumbnailTemplateProps, 'badge' | 'headline' | 'highlightWord' | 'subtitle' | 'imageUrl' | 'showWordmark'>) {
  return (
    <div style={{ position: 'relative', width: '100%', height: '100%', backgroundColor: '#f7f7f5' }}>
      {/* 풀샷 스튜디오 배경 이미지 */}
      {imageUrl ? (
        <img
          src={imageUrl}
          alt="제품 스튜디오 풀샷"
          style={{ ...imageFillStyle, objectPosition: 'center center' }}
        />
      ) : (
        <div
          style={{
            position: 'absolute',
            left: 96,
            top: 636,
            width: 888,
            height: 690,
            borderRadius: 36,
            backgroundColor: '#ffffff',
            border: '3px dashed #cfcfcf',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          <span style={placeholderLabelStyle}>제품 스튜디오 풀샷 이미지 영역 (1080×1920)</span>
        </div>
      )}

      {/* 상단/하단 타이포 가독성 소프트 그라디언트 */}
      <div
        style={{
          position: 'absolute',
          left: 0,
          right: 0,
          top: 0,
          height: 620,
          background:
            'linear-gradient(180deg, rgba(247,247,245,0.92) 0%, rgba(247,247,245,0.68) 62%, rgba(247,247,245,0) 100%)',
        }}
      />
      <div
        style={{
          position: 'absolute',
          left: 0,
          right: 0,
          bottom: 0,
          height: 580,
          background:
            'linear-gradient(0deg, rgba(247,247,245,0.92) 0%, rgba(247,247,245,0.6) 55%, rgba(247,247,245,0) 100%)',
        }}
      />

      {/* 상단 신뢰 배지 + 블랙 워드마크 */}
      <div
        style={{
          position: 'absolute',
          left: 96,
          right: 96,
          top: 280,
          display: 'flex',
          alignItems: 'center',
          justifyContent: badge?.trim() ? 'space-between' : 'flex-end',
        }}
      >
        {badge?.trim() && (
          <span
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 14,
              backgroundColor: '#0a0a0a',
              color: '#ffffff',
              fontSize: 30,
              fontWeight: 700,
              padding: '16px 32px',
              borderRadius: 999,
            }}
          >
            <span
              style={{
                width: 16,
                height: 16,
                borderRadius: 999,
                backgroundColor: '#d6ff3f',
                display: 'inline-block',
              }}
            />
            {badge}
          </span>
        )}
        {showWordmark && (
          <img src={brand.wordmarkBlack} alt="NAPDA" style={{ height: 36, opacity: 0.9 }} />
        )}
      </div>

      {/* 메인 헤드라인 */}
      {headline?.trim() && (
        <h1
          style={{
            position: 'absolute',
            left: 96,
            right: 96,
            top: 392,
            margin: 0,
            color: '#0a0a0a',
            fontSize: 74,
            fontWeight: 800,
            lineHeight: 1.2,
            letterSpacing: '-0.03em',
          }}
        >
          {renderHighlightedText(headline, highlightWord, '#d6ff3f', true)}
        </h1>
      )}

      {/* 하단 제품명/혜택 배너 */}
      {subtitle?.trim() && (
        <div
          style={{
            position: 'absolute',
            left: 96,
            top: 1376,
            width: 888,
            height: 112,
            borderRadius: 999,
            backgroundColor: '#0a0a0a',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: 16,
          }}
        >
          <span
            style={{
              width: 14,
              height: 14,
              borderRadius: 999,
              backgroundColor: '#d6ff3f',
              display: 'inline-block',
            }}
          />
          <span
            style={{
              color: '#ffffff',
              fontSize: 38,
              fontWeight: 700,
              letterSpacing: '-0.02em',
            }}
          >
            {subtitle}
          </span>
        </div>
      )}
    </div>
  );
}
