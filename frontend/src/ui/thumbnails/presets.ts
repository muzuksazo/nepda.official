import jetUmbrellaV1 from '../../assets/thumbnails/jet-umbrella-v1.webp';
import pievStudioFullshot from '../../assets/thumbnails/piev-studio-fullshot.webp';
import ps2EoljukahV2 from '../../assets/thumbnails/ps2-eoljukah-v2.webp';
import ps2EoljukahV3 from '../../assets/thumbnails/ps2-eoljukah-v3.webp';
import ps2SubwayHero from '../../assets/thumbnails/ps2-subway-hero.webp';
import ps2SubwayV3 from '../../assets/thumbnails/ps2-subway-v3.webp';

export type ThumbnailVariant = 'editorial' | 'viral-hook' | 'split-vs' | 'commerce';

export interface ThumbnailTemplateProps {
  /** 템플릿 레이아웃 유형 */
  variant: ThumbnailVariant;
  /** 상단 배지 텍스트 (비우면 숨김) */
  badge?: string;
  /** 메인 2줄 헤드라인 (줄바꿈 \n 지원, 비우면 숨김) */
  headline?: string;
  /** 헤드라인 중 라임(#d6ff3f)으로 강조할 단어 하나 */
  highlightWord?: string;
  /** 보조 카피 / 서브 키워드 / 하단 CTA 문구 */
  subtitle?: string;
  /** 메인 배경 또는 제품 이미지 URL */
  imageUrl?: string;
  /** 스플릿 VS 하단 이미지 URL */
  bottomImageUrl?: string;
  /** 스플릿 VS 하단 배지 라벨 */
  realityBadge?: string;
  /** 냅다 워드마크 로고 노출 여부 */
  showWordmark?: boolean;
  /** 인스타 릴스 UI 안전 영역 · 3:4 피드 크롭 가이드 표시 */
  showSafeZone?: boolean;
  /** 미리보기 축척 (실제 해상도는 항상 1080x1920) */
  scale?: number;
}

export const THUMBNAIL_WIDTH = 1080;
export const THUMBNAIL_HEIGHT = 1920;

export const VARIANT_PRESETS: Record<
  ThumbnailVariant,
  Omit<ThumbnailTemplateProps, 'scale' | 'showSafeZone'>
> = {
  editorial: {
    variant: 'editorial',
    badge: 'K-MEME · 2004 PS2',
    headline: "영하 15도 서울 카페\n전원 '얼죽아' 생존 미션",
    highlightWord: "'얼죽아'",
    subtitle: '',
    imageUrl: ps2EoljukahV3,
    showWordmark: true,
  },
  'viral-hook': {
    variant: 'viral-hook',
    badge: '만약에...?',
    headline: '시속 300km 제트엔진\n뒤에서 우산을 펴면?',
    highlightWord: '제트엔진',
    subtitle: '3초 안에 벌어지는 충격 실험 결과',
    imageUrl: jetUmbrellaV1,
    showWordmark: false,
  },
  'split-vs': {
    variant: 'split-vs',
    badge: '기대 · EXPECTATION',
    realityBadge: '현실 · REALITY',
    headline: 'K-드라마 vs 서울 2호선 현실',
    highlightWord: '서울 2호선',
    subtitle: '한국살이 2개월차 · PS2 밈 실화',
    imageUrl: ps2SubwayHero,
    bottomImageUrl: ps2SubwayV3,
    showWordmark: false,
  },
  commerce: {
    variant: 'commerce',
    badge: '실사용 검증 · 리얼 리뷰',
    headline: '90° 눕혀도\n한 방울도 안 흐릅니다',
    highlightWord: '한 방울',
    subtitle: '피에브 에어워셔 피톤치드 · 고체 젤',
    imageUrl: pievStudioFullshot,
    showWordmark: true,
  },
};

export interface ShowcasePreset {
  id: string;
  label: string;
  props: Omit<ThumbnailTemplateProps, 'scale' | 'showSafeZone'>;
}

export const PS2_GTA_SHOWCASE_PRESETS: ShowcasePreset[] = [
  {
    id: 'ep2-editorial',
    label: 'EP.2 · 영하 15도 얼죽아 (에디토리얼)',
    props: VARIANT_PRESETS.editorial,
  },
  {
    id: 'ep2-viral-hook',
    label: 'EP.2 · 전원 롱패딩 아아 충격 (바이럴 훅)',
    props: {
      variant: 'viral-hook',
      badge: '실화 미션 · -15°C',
      headline: '패딩 입고 전원 아이스?!\n강남 카페 첫 입성 실화',
      highlightWord: '아이스?!',
      subtitle: '영하 15도 한국살이 2개월차 데본',
      imageUrl: ps2EoljukahV2,
      showWordmark: true,
    },
  },
  {
    id: 'ep1-split-vs',
    label: 'EP.1 · 서울 2호선 출근길 (스플릿 VS)',
    props: VARIANT_PRESETS['split-vs'],
  },
];
