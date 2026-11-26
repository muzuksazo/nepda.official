import { brand } from '../brand';
import {
  computeSerifOutlineFontSize,
  THUMBNAIL_HEIGHT,
  THUMBNAIL_WIDTH,
  type ThumbnailTemplateProps,
} from './presets';

const SANS_FONT = "'Pretendard Variable', Pretendard, 'Inter', -apple-system, BlinkMacSystemFont, sans-serif";
const SERIF_FONT = "'Bookk Myungjo', 'Noto Serif KR', serif";

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
  imageScale = 1,
  imageOffsetX = 0,
  imageOffsetY = 0,
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
    sy = (img.naturalHeight - sh) / 2;
  }

  ctx.save();
  ctx.beginPath();
  ctx.rect(dx, dy, dw, dh);
  ctx.clip();

  const cx = dx + dw / 2;
  const cy = dy + dh / 2;
  ctx.translate(cx + imageOffsetX, cy + imageOffsetY);
  ctx.scale(imageScale, imageScale);
  ctx.translate(-cx, -cy);
  ctx.drawImage(img, sx, sy, sw, sh, dx, dy, dw, dh);
  ctx.restore();
}

function drawBottomGradientIfNeeded(ctx: CanvasRenderingContext2D, visible?: boolean): void {
  if (!visible) return;
  const grad = ctx.createLinearGradient(0, 940, 0, 1920);
  grad.addColorStop(0, 'rgba(0,0,0,0)');
  grad.addColorStop(0.42, 'rgba(0,0,0,0.48)');
  grad.addColorStop(1, 'rgba(0,0,0,0.92)');
  ctx.fillStyle = grad;
  ctx.fillRect(0, 940, 1080, 980);
}

function drawBadgePill(ctx: CanvasRenderingContext2D, centerX: number | null, x: number, y: number, text: string): number {
  const clean = text.trim();
  if (!clean) return y;
  ctx.font = `800 28px ${SANS_FONT}`;
  const tw = ctx.measureText(clean).width;
  const padX = 26;
  const h = 56;
  const w = tw + padX * 2;
  const bx = centerX !== null ? centerX - w / 2 : x;

  roundRectPath(ctx, bx, y, w, h, 999);
  ctx.fillStyle = '#d6ff3f';
  ctx.fill();

  ctx.fillStyle = '#000000';
  ctx.textAlign = 'left';
  ctx.textBaseline = 'middle';
  ctx.fillText(clean, bx + padX, y + h / 2 + 1);
  return y + h + 18;
}

function drawSubtitlePill(
  ctx: CanvasRenderingContext2D,
  centerX: number | null,
  x: number,
  y: number,
  text: string,
  radius = 12,
  fontSize = 36,
  padX = 28,
  padY = 12,
): void {
  const clean = text.trim();
  if (!clean) return;
  ctx.font = `700 ${fontSize}px ${SANS_FONT}`;
  const tw = ctx.measureText(clean).width;
  const h = Math.round(fontSize * 1.25 + padY * 2);
  const w = tw + padX * 2;
  const bx = centerX !== null ? centerX - w / 2 : x;

  roundRectPath(ctx, bx, y, w, h, radius);
  ctx.fillStyle = '#020202';
  ctx.fill();

  ctx.fillStyle = '#ffffff';
  ctx.textAlign = 'left';
  ctx.textBaseline = 'middle';
  ctx.fillText(clean, bx + padX, y + h / 2 + 1);
}

function drawLineWithHighlight(
  ctx: CanvasRenderingContext2D,
  line: string,
  startX: number,
  y: number,
  baseColor: string,
  highlightWord: string | undefined,
  highlightColor: string,
  highlightBg?: string,
  strokeColor?: string,
  strokeWidth = 0,
  highlightStrokeColor?: string,
): void {
  const target = highlightWord?.trim();
  const segments =
    target && line.includes(target)
      ? (() => {
          const idx = line.indexOf(target);
          return [
            { text: line.slice(0, idx), isHi: false },
            { text: target, isHi: true },
            { text: line.slice(idx + target.length), isHi: false },
          ];
        })()
      : [{ text: line, isHi: false }];

  ctx.textAlign = 'left';
  let curX = startX;
  for (const seg of segments) {
    if (!seg.text) continue;
    const w = ctx.measureText(seg.text).width;
    if (seg.isHi && highlightBg) {
      const m = ctx.measureText(seg.text);
      const asc = m.actualBoundingBoxAscent || 40;
      const desc = m.actualBoundingBoxDescent || 10;
      ctx.fillStyle = highlightBg;
      roundRectPath(ctx, curX - 6, y - asc - 4, w + 12, asc + desc + 8, 8);
      ctx.fill();
    }
    const sc = seg.isHi && highlightStrokeColor ? highlightStrokeColor : strokeColor;
    if (sc && strokeWidth > 0) {
      ctx.save();
      ctx.shadowColor = 'transparent';
      ctx.shadowBlur = 0;
      ctx.lineJoin = 'round';
      ctx.lineWidth = strokeWidth;
      ctx.strokeStyle = sc;
      ctx.strokeText(seg.text, curX, y);
      ctx.restore();
    }
    ctx.fillStyle = seg.isHi ? highlightColor : baseColor;
    ctx.fillText(seg.text, curX, y);
    curX += w;
  }
}

/**
 * 1080×1920 해상도 PNG로 렌더링하고 즉시 브라우저 파일 다운로드를 실행한다.
 */
export async function exportThumbnailPng(
  props: Omit<ThumbnailTemplateProps, 'scale' | 'showSafeZone'>,
): Promise<void> {
  await document.fonts.load("700 180px 'Bookk Myungjo'").catch(() => {});
  await document.fonts.ready;

  const canvas = document.createElement('canvas');
  canvas.width = THUMBNAIL_WIDTH;
  canvas.height = THUMBNAIL_HEIGHT;
  const ctx = canvas.getContext('2d');
  if (!ctx) {
    throw new Error('2D 캔버스 컨텍스트를 초기화할 수 없습니다.');
  }

  const [img, wordmarkImg] = await Promise.all([
    props.imageUrl ? loadImage(props.imageUrl).catch(() => null) : Promise.resolve(null),
    props.showWordmark ? loadImage(brand.wordmarkWhite).catch(() => null) : Promise.resolve(null),
  ]);

  const badgeText = props.badge?.trim() ?? '';
  const headlineText = props.headline?.trim() ?? '';
  const subtitleText = props.subtitle?.trim() ?? '';
  const lines = headlineText ? headlineText.split('\n').filter((l) => l.length > 0) : [];
  const imgScale = props.imageScale ?? 1;
  const imgOffX = props.imageOffsetX ?? 0;
  const imgOffY = props.imageOffsetY ?? 0;

  if (props.variant === 'invert-box') {
    ctx.fillStyle = '#111317';
    ctx.fillRect(0, 0, 1080, 1920);
    if (img) drawCoverImage(ctx, img, 0, 0, 1080, 1920, imgScale, imgOffX, imgOffY);
    drawBottomGradientIfNeeded(ctx, props.showBottomGradient);

    let curY = drawBadgePill(ctx, 540, 540, 296, badgeText);
    const fontSize = 78;
    const boxHeight = Math.round(fontSize * 1.16 + 20);
    ctx.font = `500 ${fontSize}px ${SANS_FONT}`;
    ctx.textBaseline = 'middle';

    lines.forEach((line, idx) => {
      const isOdd = idx % 2 === 1;
      const tw = ctx.measureText(line).width;
      const bw = Math.min(952, tw + 44);
      const bx = 540 - bw / 2;
      ctx.fillStyle = isOdd ? '#020202' : '#ffffff';
      ctx.fillRect(bx, curY, bw, boxHeight);

      drawLineWithHighlight(
        ctx,
        line,
        540 - tw / 2,
        curY + boxHeight / 2 + 2,
        isOdd ? '#ffffff' : '#111111',
        props.highlightWord,
        isOdd ? '#d6ff3f' : '#000000',
        isOdd ? undefined : '#d6ff3f',
      );
      curY += boxHeight;
    });

    if (subtitleText) {
      drawSubtitlePill(ctx, 540, 540, curY + 22, subtitleText);
    }
  } else if (props.variant === 'white-label') {
    ctx.fillStyle = '#12151c';
    ctx.fillRect(0, 0, 1080, 1920);
    if (img) drawCoverImage(ctx, img, 0, 0, 1080, 1920, imgScale, imgOffX, imgOffY);
    drawBottomGradientIfNeeded(ctx, props.showBottomGradient);

    let curY = drawBadgePill(ctx, null, 68, 340, badgeText);
    const fontSize = 92;
    const boxHeight = Math.round(fontSize * 1.12 + 20);
    ctx.font = `700 ${fontSize}px ${SANS_FONT}`;
    ctx.textBaseline = 'middle';

    for (const line of lines) {
      const tw = ctx.measureText(line).width;
      const bw = Math.min(944, tw + 40);
      ctx.fillStyle = '#ffffff';
      ctx.fillRect(68, curY, bw, boxHeight);

      drawLineWithHighlight(
        ctx,
        line,
        68 + 20,
        curY + boxHeight / 2 + 2,
        '#000000',
        props.highlightWord,
        '#000000',
        '#d6ff3f',
      );
      curY += boxHeight;
    }

    if (subtitleText) {
      drawSubtitlePill(ctx, null, 68, curY + 22, subtitleText);
    }
  } else if (props.variant === 'serif-outline') {
    ctx.fillStyle = '#141414';
    ctx.fillRect(0, 0, 1080, 1920);
    if (img) drawCoverImage(ctx, img, 0, 0, 1080, 1920, imgScale, imgOffX, imgOffY);
    drawBottomGradientIfNeeded(ctx, props.showBottomGradient);

    let curY = 235;
    if (badgeText) {
      ctx.save();
      ctx.font = `italic 700 52px ${SERIF_FONT}`;
      ctx.textBaseline = 'top';
      ctx.textAlign = 'center';
      ctx.shadowColor = 'rgba(0,0,0,0.45)';
      ctx.shadowBlur = 14;
      ctx.shadowOffsetY = 4;
      ctx.lineJoin = 'round';
      ctx.lineWidth = 10;
      ctx.strokeStyle = '#000000';
      ctx.strokeText(badgeText, 540, curY);
      ctx.fillStyle = '#ffffff';
      ctx.fillText(badgeText, 540, curY);
      ctx.restore();
      curY += 78;
    }

    if (lines.length > 0) {
      const fontSize = computeSerifOutlineFontSize(headlineText);
      const lineHeight = Math.round(fontSize * 1.06);
      ctx.save();
      ctx.font = `700 ${fontSize}px ${SERIF_FONT}`;
      ctx.textBaseline = 'top';
      ctx.shadowColor = 'rgba(0,0,0,0.32)';
      ctx.shadowBlur = 20;
      ctx.shadowOffsetY = 8;

      for (const line of lines) {
        const tw = ctx.measureText(line).width;
        drawLineWithHighlight(
          ctx,
          line,
          540 - tw / 2,
          curY,
          '#000000',
          props.highlightWord,
          '#d6ff3f',
          undefined,
          '#ffffff',
          22,
          '#000000',
        );
        curY += lineHeight;
      }
      ctx.restore();
    }

    if (subtitleText) {
      drawSubtitlePill(ctx, 540, 540, curY + 22, subtitleText);
    }
  } else {
    // pov-bar: 상단 솔리드 블랙 바 + 하단 이미지
    ctx.fillStyle = '#000000';
    ctx.fillRect(0, 0, 1080, 1920);
    if (img) drawCoverImage(ctx, img, 0, 560, 1080, 1360, imgScale, imgOffX, imgOffY);
    drawBottomGradientIfNeeded(ctx, props.showBottomGradient);

    ctx.fillStyle = '#000000';
    ctx.fillRect(0, 0, 1080, 560);

    const fontSize = 60;
    const lineHeight = Math.round(fontSize * 1.32);
    const badgeH = badgeText ? 74 : 0;
    const blockH = badgeH + lines.length * lineHeight;
    let curY = 248 + Math.max(0, (284 - blockH) / 2);

    if (badgeText) {
      curY = drawBadgePill(ctx, 540, 540, curY, badgeText);
    }

    ctx.font = `700 ${fontSize}px ${SANS_FONT}`;
    ctx.textBaseline = 'top';
    for (const line of lines) {
      const tw = ctx.measureText(line).width;
      drawLineWithHighlight(
        ctx,
        line,
        540 - tw / 2,
        curY,
        '#ffffff',
        props.highlightWord,
        '#d6ff3f',
      );
      curY += lineHeight;
    }

    if (subtitleText) {
      drawSubtitlePill(ctx, 540, 540, 1340, subtitleText, 0, 44, 28, 14);
    }
  }

  if (wordmarkImg && wordmarkImg.naturalWidth > 0 && wordmarkImg.naturalHeight > 0) {
    const h = 40;
    const w = Math.round((wordmarkImg.naturalWidth / wordmarkImg.naturalHeight) * h);
    ctx.save();
    ctx.globalAlpha = 0.92;
    ctx.shadowColor = 'rgba(0,0,0,0.65)';
    ctx.shadowBlur = 10;
    ctx.drawImage(wordmarkImg, 1080 - 96 - w, 1410, w, h);
    ctx.restore();
  }

  const dataUrl = canvas.toDataURL('image/png');
  const a = document.createElement('a');
  a.href = dataUrl;
  a.download = `napda-thumbnail-${props.variant}.png`;
  a.click();
}
