import jetUmbrellaV1 from '../../assets/thumbnails/jet-umbrella-v1.webp';
import pievStudioFullshot from '../../assets/thumbnails/piev-studio-fullshot.webp';
import ps2EoljukahV2 from '../../assets/thumbnails/ps2-eoljukah-v2.webp';
import ps2EoljukahV3 from '../../assets/thumbnails/ps2-eoljukah-v3.webp';
import ps2SubwayHero from '../../assets/thumbnails/ps2-subway-hero.webp';
import ps2SubwayV3 from '../../assets/thumbnails/ps2-subway-v3.webp';

export interface ImagePresetOption {
  id: string;
  label: string;
  url: string;
}

export const IMAGE_PRESET_OPTIONS: ImagePresetOption[] = [
  { id: 'ps2-eoljukah-v3', label: '얼죽아 v3', url: ps2EoljukahV3 },
  { id: 'ps2-eoljukah-v2', label: '얼죽아 v2', url: ps2EoljukahV2 },
  { id: 'jet-umbrella-v1', label: '제트엔진', url: jetUmbrellaV1 },
  { id: 'piev-studio', label: '피에브 풀샷', url: pievStudioFullshot },
  { id: 'ps2-subway-hero', label: '2호선 기대', url: ps2SubwayHero },
  { id: 'ps2-subway-v3', label: '2호선 현실', url: ps2SubwayV3 },
];

/** Figma 릴스 커버 4가지 제목 스타일 */
export type ThumbnailVariant = 'invert-box' | 'white-label' | 'serif-outline' | 'pov-bar';

export interface ThumbnailTemplateProps {
  /** 릴스 커버 제목 스타일 유형 (Figma 4종) */
  variant: ThumbnailVariant;
  /** 상단 소제목 · 배지 (스타일3에서는 상단 이탤릭 서브 문구, 비우면 숨김) */
  badge?: string;
  /** 메인 제목 (줄바꿈 \n 지원, 비우면 숨김) */
  headline?: string;
  /** 제목 중 라임(#d6ff3f)으로 강조할 단어 하나 (선택) */
  highlightWord?: string;
  /** 하단 캡션 / 제품명 (비우면 숨김) */
  subtitle?: string;
  /** 메인 배경 / 스틸컷 이미지 URL */
  imageUrl?: string;
  /** 하단 검은 그라데이션 스크림 표시 여부 (기본 꺼짐) */
  showBottomGradient?: boolean;
  /** 배경 이미지 확대/축소 배율 (기본 1) */
  imageScale?: number;
  /** 배경 이미지 가로 이동 (1080×1920 기준 px, 기본 0) */
  imageOffsetX?: number;
  /** 배경 이미지 세로 이동 (1080×1920 기준 px, 기본 0) */
  imageOffsetY?: number;
  /** 냅다 워드마크 로고 노출 여부 */
  showWordmark?: boolean;
  /** 인스타 릴스 UI 안전 영역 · 3:4 피드 크롭 가이드 표시 */
  showSafeZone?: boolean;
  /** 미리보기 축척 (실제 해상도는 항상 1080x1920) */
  scale?: number;
}

export const THUMBNAIL_WIDTH = 1080;
export const THUMBNAIL_HEIGHT = 1920;

export const SANS_FONT_FAMILY =
  "var(--font-sans, 'Pretendard Variable', Pretendard, 'Inter', sans-serif)";
export const SERIF_FONT_FAMILY = "'Bookk Myungjo', 'Noto Serif KR', serif";

/** 스타일 3 (대형 명조 외곽선) 글자 수에 맞춰 DOM·Canvas 동일 크기를 산출한다. */
export function computeSerifOutlineFontSize(headline: string): number {
  const maxChars = Math.max(
    ...headline.split('\n').map((l) => [...l.trim()].length),
    1,
  );
  if (maxChars <= 5) return 210;
  if (maxChars <= 8) return 152;
  return 112;
}

export const VARIANT_PRESETS: Record<
  ThumbnailVariant,
  Omit<ThumbnailTemplateProps, 'scale' | 'showSafeZone'>
> = {
  'invert-box': {
    variant: 'invert-box',
    badge: '',
    headline: "영하 15도 서울 카페\n전원 '얼죽아' 생존 미션",
    highlightWord: '',
    subtitle: '',
    imageUrl: ps2EoljukahV3,
    showWordmark: false,
  },
  'white-label': {
    variant: 'white-label',
    badge: '',
    headline: '시속 300km 제트엔진\n뒤에서 우산을 펴면?',
    highlightWord: '',
    subtitle: '',
    imageUrl: jetUmbrellaV1,
    showWordmark: false,
  },
  'serif-outline': {
    variant: 'serif-outline',
    badge: '냄새 덮지 말고 잡으세요!',
    headline: '피에브\n에어워셔',
    highlightWord: '',
    subtitle: '',
    imageUrl: pievStudioFullshot,
    showWordmark: false,
  },
  'pov-bar': {
    variant: 'pov-bar',
    badge: '',
    headline: 'POV: 한국 드라마 보고 왔는데\n출근길 서울 2호선에\n처음 타버린 나',
    highlightWord: '',
    subtitle: '',
    imageUrl: ps2SubwayHero,
    showWordmark: false,
  },
};

export interface ShowcasePreset {
  id: string;
  label: string;
  props: Omit<ThumbnailTemplateProps, 'scale' | 'showSafeZone'>;
}

export const PS2_GTA_SHOWCASE_PRESETS: ShowcasePreset[] = [
  {
    id: 'style-1-invert-box',
    label: '스타일 1 · 화이트/블랙 반전 2줄 박스',
    props: VARIANT_PRESETS['invert-box'],
  },
  {
    id: 'style-2-white-label',
    label: '스타일 2 · 좌측정렬 화이트 라벨 2줄',
    props: {
      variant: 'white-label',
      badge: '',
      headline: '패딩 입고\n아이스 아메리카노?',
      highlightWord: '',
      subtitle: '',
      imageUrl: ps2EoljukahV2,
      showWordmark: false,
    },
  },
  {
    id: 'style-3-serif-outline',
    label: '스타일 3 · 대형 명조 외곽선 임팩트',
    props: VARIANT_PRESETS['serif-outline'],
  },
  {
    id: 'style-4-pov-bar',
    label: '스타일 4 · 상단 블랙 바 POV 밈형',
    props: VARIANT_PRESETS['pov-bar'],
  },
];
