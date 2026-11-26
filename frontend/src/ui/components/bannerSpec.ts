/**
 * 이벤트 배너 규격 (디자이너 전달용)
 * - 표시 영역: 350 × 167px (390px 화면 기준, 비율 21:10 고정, 최대 440 × 210px)
 * - 제작 사이즈: 1050 × 500px (@3x), PNG 또는 WebP
 * - 안전 영역: 오른쪽 아래 120 × 72px(@3x 기준)는 "1 / 5" 뱃지가 덮으니 글자·로고를 두지 않는다
 */
/** 한 번에 보여 주는 배너는 최대 3장 ("1 / 3") */
export const MAX_BANNERS = 3;

export const BANNER_SIZE = { width: 350, height: 167, exportWidth: 1050, exportHeight: 500 } as const;
