import {
  THUMBNAIL_HEIGHT,
  THUMBNAIL_WIDTH,
  type ThumbnailTemplateProps,
} from './presets';

const SANS_FONT = "'Pretendard Variable', Pretendard, -apple-system, BlinkMacSystemFont, sans-serif";

function loadImage(src: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.crossOrigin = 'anonymous';
    img.onload = () => resolve(img);
    img.onerror = () => reject(new Error(`이미지 로드 실패: ${src}`));
    img.src = src;
  });
}

function roundRectPath(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  w: number,
  h: number,
  r: number,
): void {
  const rad = Math.min(r, w / 2, h / 2);
  ctx.beginPath();
  ctx.moveTo(x + rad, y);
  ctx.arcTo(x + w, y, x + w, y + h, rad);
  ctx.arcTo(x + w, y + h, x, y + h, rad);
  ctx.arcTo(x, y + h, x, y, rad);
  ctx.arcTo(x, y, x + w, y, rad);
  ctx.closePath();
}

function drawCoverImage(
  ctx: CanvasRenderingContext2D,
  img: HTMLImageElement,
  dx: number,
  dy: number,
  dw: number,
  dh: number,
  focusY = 0.5,
): void {
  const srcRatio = img.naturalWidth / img.naturalHeight;
  const dstRatio = dw / dh;
  let sx = 0;
  let sy = 0;
  let sw = img.naturalWidth;
  let sh = img.naturalHeight;
  if (srcRatio > dstRatio) {
    sw = img.naturalHeight * dstRatio;
    sx = (img.naturalWidth - sw) / 2;
  } else {
    sh = img.naturalWidth / dstRatio;
    sy = (img.naturalHeight - sh) * focusY;
  }
  ctx.drawImage(img, sx, sy, sw, sh, dx, dy, dw, dh);
}

function drawHighlightedLines(
  ctx: CanvasRenderingContext2D,
  text: string,
  x: number,
  y: number,
  lineHeight: number,
  font: string,
  baseColor: string,
  accentColor: string,
  highlightWord?: string,
  align: 'left' | 'center' = 'left',
  markerBg?: string,
): void {
  ctx.font = font;
  ctx.textBaseline = 'top';
  const lines = text.split('\n');
  lines.forEach((line, idx) => {
    const ly = y + idx * lineHeight;
    const target = highlightWord?.trim();
    if (!target || !line.includes(target)) {
      ctx.fillStyle = baseColor;
      ctx.textAlign = align;
      ctx.fillText(line, x, ly);
      return;
    }

    const pos = line.indexOf(target);
    const parts: Array<{ str: string; color: string; isHighlight: boolean }> = [
      { str: line.slice(0, pos), color: baseColor, isHighlight: false },
      { str: target, color: accentColor, isHighlight: true },
      { str: line.slice(pos + target.length), color: baseColor, isHighlight: false },
    ];

    const markerPadX = markerBg ? 12 : 0;
    let curX = x;
    if (align === 'center') {
      const totalWidth = ctx.measureText(line).width + markerPadX * 2;
      curX = x - totalWidth / 2;
    }
    ctx.textAlign = 'left';
    for (const part of parts) {
      if (!part.str) continue;
      const textWidth = ctx.measureText(part.str).width;
      if (part.isHighlight && markerBg) {
        const boxH = Math.round(lineHeight * 0.9);
        const boxY = ly - Math.round((boxH - lineHeight * 0.83) / 2);
        ctx.fillStyle = markerBg;
        roundRectPath(ctx, curX, boxY, textWidth + markerPadX * 2, boxH, 12);
        ctx.fill();
        ctx.fillStyle = part.color;
        ctx.fillText(part.str, curX + markerPadX, ly);
        curX += textWidth + markerPadX * 2;
      } else {
        ctx.fillStyle = part.color;
        ctx.fillText(part.str, curX, ly);
        curX += textWidth;
      }
    }
  });
}

function drawPill(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  text: string,
  options: {
    bg: string;
    fg: string;
    font: string;
    padX?: number;
    height?: number;
    radius?: number;
    stroke?: string;
    dotColor?: string;
  },
): void {
  const { bg, fg, font, padX = 32, height = 68, radius = 999, stroke, dotColor } = options;
  ctx.font = font;
  const textW = ctx.measureText(text).width;
  const dotSpace = dotColor ? 28 : 0;
  const w = textW + padX * 2 + dotSpace;

  roundRectPath(ctx, x, y, w, height, radius);
  ctx.fillStyle = bg;
  ctx.fill();
  if (stroke) {
    ctx.lineWidth = 3;
    ctx.strokeStyle = stroke;
    ctx.stroke();
  }

  let textX = x + padX;
  if (dotColor) {
    ctx.beginPath();
    ctx.arc(x + padX + 8, y + height / 2, 8, 0, Math.PI * 2);
    ctx.fillStyle = dotColor;
    ctx.fill();
    textX += dotSpace;
  }

  ctx.fillStyle = fg;
  ctx.textAlign = 'left';
  ctx.textBaseline = 'middle';
  ctx.fillText(text, textX, y + height / 2 + 1);
}

/**
 * 1080×1920 해상도 PNG로 렌더링하고 즉시 브라우저 파일 다운로드를 실행한다.
 */
export async function exportThumbnailPng(
  props: Omit<ThumbnailTemplateProps, 'scale' | 'showSafeZone'>,
): Promise<void> {
  await document.fonts.ready;

  const canvas = document.createElement('canvas');
  canvas.width = THUMBNAIL_WIDTH;
  canvas.height = THUMBNAIL_HEIGHT;
  const ctx = canvas.getContext('2d');
  if (!ctx) {
    throw new Error('2D 캔버스 컨텍스트를 초기화할 수 없습니다.');
  }

  const [topImg, bottomImg] = await Promise.all([
    props.imageUrl ? loadImage(props.imageUrl).catch(() => null) : Promise.resolve(null),
    props.bottomImageUrl ? loadImage(props.bottomImageUrl).catch(() => null) : Promise.resolve(null),
  ]);

  const badgeText = props.badge?.trim() ?? '';
  const headlineText = props.headline?.trim() ?? '';
  const subtitleText = props.subtitle?.trim() ?? '';
  const realityText = props.realityBadge?.trim() ?? '';

  if (props.variant === 'editorial') {
    ctx.fillStyle = '#111317';
    ctx.fillRect(0, 0, 1080, 1920);
    if (topImg) drawCoverImage(ctx, topImg, 0, 0, 1080, 1920);

    const grad = ctx.createLinearGradient(0, 940, 0, 1920);
    grad.addColorStop(0, 'rgba(0,0,0,0)');
    grad.addColorStop(0.42, 'rgba(0,0,0,0.48)');
    grad.addColorStop(1, 'rgba(0,0,0,0.92)');
    ctx.fillStyle = grad;
    ctx.fillRect(0, 940, 1080, 980);

    if (badgeText) {
      drawPill(ctx, 96, 280, badgeText, {
        bg: '#d6ff3f',
        fg: '#000000',
        font: `800 30px ${SANS_FONT}`,
        radius: 16,
      });
    }

    if (headlineText) {
      ctx.save();
      ctx.shadowColor = 'rgba(0,0,0,0.85)';
      ctx.shadowBlur = 32;
      drawHighlightedLines(
        ctx,
        headlineText,
        96,
        1110,
        94,
        `800 80px ${SANS_FONT}`,
        '#ffffff',
        '#d6ff3f',
        props.highlightWord,
      );
      ctx.restore();
    }

    if (subtitleText) {
      ctx.font = `300 48px ${SANS_FONT}`;
      ctx.fillStyle = '#d4d4d4';
      ctx.textAlign = 'left';
      ctx.textBaseline = 'top';
      ctx.fillText(subtitleText, 96, headlineText ? 1326 : 1110);
    }
  } else if (props.variant === 'viral-hook') {
    ctx.fillStyle = '#12151c';
    ctx.fillRect(0, 0, 1080, 1920);
    if (topImg) drawCoverImage(ctx, topImg, 0, 0, 1080, 1920);

    const grad = ctx.createLinearGradient(0, 860, 0, 1920);
    grad.addColorStop(0, 'rgba(10,10,10,0)');
    grad.addColorStop(0.38, 'rgba(10,10,10,0.72)');
    grad.addColorStop(1, 'rgba(10,10,10,0.95)');
    ctx.fillStyle = grad;
    ctx.fillRect(0, 860, 1080, 1060);

    if (badgeText) {
      drawPill(ctx, 96, 296, badgeText, {
        bg: '#d6ff3f',
        fg: '#000000',
        font: `800 36px ${SANS_FONT}`,
        padX: 38,
        height: 76,
      });
    }

    if (headlineText || subtitleText) {
      const lineCount = headlineText ? headlineText.split('\n').length : 0;
      const barHeight = Math.max(56, lineCount * 88 + (subtitleText ? 54 : 0));
      roundRectPath(ctx, 96, 1080, 14, barHeight, 7);
      ctx.fillStyle = '#d6ff3f';
      ctx.fill();

      if (headlineText) {
        drawHighlightedLines(
          ctx,
          headlineText,
          136,
          1078,
          89,
          `800 74px ${SANS_FONT}`,
          '#ffffff',
          '#d6ff3f',
          props.highlightWord,
        );
      }

      if (subtitleText) {
        ctx.font = `500 36px ${SANS_FONT}`;
        ctx.fillStyle = '#d4d4d4';
        ctx.textAlign = 'left';
        ctx.textBaseline = 'top';
        ctx.fillText(subtitleText, 136, headlineText ? 1078 + lineCount * 89 + 24 : 1084);
      }
    }
  } else if (props.variant === 'split-vs') {
    ctx.fillStyle = '#1b2434';
    ctx.fillRect(0, 0, 1080, 954);
    if (topImg) drawCoverImage(ctx, topImg, 0, 0, 1080, 954, 0.25);

    ctx.fillStyle = '#241921';
    ctx.fillRect(0, 966, 1080, 954);
    if (bottomImg) drawCoverImage(ctx, bottomImg, 0, 966, 1080, 954, 0.06);

    ctx.fillStyle = '#d6ff3f';
    ctx.fillRect(0, 954, 1080, 12);

    ctx.beginPath();
    ctx.arc(540, 960, 80, 0, Math.PI * 2);
    ctx.fillStyle = '#d6ff3f';
    ctx.fill();
    ctx.lineWidth = 10;
    ctx.strokeStyle = '#0a0a0a';
    ctx.stroke();

    ctx.font = `900 64px ${SANS_FONT}`;
    ctx.fillStyle = '#000000';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText('VS', 540, 962);

    if (badgeText) {
      drawPill(ctx, 96, 290, badgeText, {
        bg: '#0a0a0a',
        fg: '#ffffff',
        font: `700 32px ${SANS_FONT}`,
        stroke: '#ffffff',
        height: 72,
      });
    }

    if (realityText) {
      drawPill(ctx, 96, 1044, realityText, {
        bg: '#d6ff3f',
        fg: '#000000',
        font: `800 32px ${SANS_FONT}`,
        stroke: '#0a0a0a',
        height: 72,
      });
    }

    if (headlineText || subtitleText) {
      roundRectPath(ctx, 72, 1256, 936, subtitleText && headlineText ? 196 : 136, 28);
      ctx.fillStyle = 'rgba(10, 10, 10, 0.92)';
      ctx.fill();
      ctx.lineWidth = 3;
      ctx.strokeStyle = '#d6ff3f';
      ctx.stroke();

      if (headlineText) {
        drawHighlightedLines(
          ctx,
          headlineText,
          540,
          1292,
          64,
          `800 54px ${SANS_FONT}`,
          '#ffffff',
          '#d6ff3f',
          props.highlightWord,
          'center',
        );
      }

      if (subtitleText) {
        ctx.font = `500 32px ${SANS_FONT}`;
        ctx.fillStyle = '#a6a6a6';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'top';
        ctx.fillText(subtitleText, 540, headlineText ? 1372 : 1306);
      }
    }
  } else {
    ctx.fillStyle = '#f7f7f5';
    ctx.fillRect(0, 0, 1080, 1920);
    if (topImg) {
      drawCoverImage(ctx, topImg, 0, 0, 1080, 1920);
    }

    const topGrad = ctx.createLinearGradient(0, 0, 0, 620);
    topGrad.addColorStop(0, 'rgba(247,247,245,0.92)');
    topGrad.addColorStop(0.62, 'rgba(247,247,245,0.68)');
    topGrad.addColorStop(1, 'rgba(247,247,245,0)');
    ctx.fillStyle = topGrad;
    ctx.fillRect(0, 0, 1080, 620);

    const botGrad = ctx.createLinearGradient(0, 1920, 0, 1340);
    botGrad.addColorStop(0, 'rgba(247,247,245,0.92)');
    botGrad.addColorStop(0.55, 'rgba(247,247,245,0.6)');
    botGrad.addColorStop(1, 'rgba(247,247,245,0)');
    ctx.fillStyle = botGrad;
    ctx.fillRect(0, 1340, 1080, 580);

    if (badgeText) {
      drawPill(ctx, 96, 280, badgeText, {
        bg: '#0a0a0a',
        fg: '#ffffff',
        font: `700 30px ${SANS_FONT}`,
        height: 70,
        dotColor: '#d6ff3f',
      });
    }

    if (headlineText) {
      drawHighlightedLines(
        ctx,
        headlineText,
        96,
        392,
        89,
        `800 74px ${SANS_FONT}`,
        '#0a0a0a',
        '#000000',
        props.highlightWord,
        'left',
        '#d6ff3f',
      );
    }

    if (subtitleText) {
      roundRectPath(ctx, 96, 1376, 888, 112, 56);
      ctx.fillStyle = '#0a0a0a';
      ctx.fill();

      ctx.font = `700 38px ${SANS_FONT}`;
      ctx.fillStyle = '#ffffff';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText(subtitleText, 540, 1433);
    }
  }

  const dataUrl = canvas.toDataURL('image/png');
  const a = document.createElement('a');
  a.href = dataUrl;
  a.download = `napda-thumbnail-${props.variant}.png`;
  a.click();
}
