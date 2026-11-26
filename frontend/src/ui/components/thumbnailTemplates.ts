/**
 * 썸네일 템플릿 — 팀이 직접 만들어서 넣는다. 앱은 받은 순서대로 캐러셀에 보여 주기만 한다.
 *
 * 미리보기 이미지 규격 (디자이너 전달용)
 * - 비율 9:16 고정, 제작 사이즈 540 × 960px, WebP(권장) 또는 PNG
 * - 화면에서는 약 140 × 249px로 보인다(390px 화면 기준). 작게 보이므로 글자는 크고 굵게
 * - 오른쪽 위 120 × 120px(제작 사이즈 기준)은 선택 체크 원이 덮으니 중요한 요소를 두지 않는다
 * - 모서리는 앱이 둥글게 자르므로 이미지는 각진 채로 넣는다
 */
export interface ThumbnailTemplate {
  /** 템플릿 id (썸네일을 만들 때 서버에 보낸다) */
  id: string;
  /** 캐러셀에서 미리보기 아래에 보이는 이름. 짧게 (4자 안팎) */
  name: string;
  /** 어떤 모양인지 한 줄. 스크린 리더가 이름 뒤에 읽는다 */
  description?: string;
  /** 미리보기 이미지. 없으면 빈 자리로 보인다 */
  previewUrl?: string;
}

export const THUMBNAIL_TEMPLATE_PREVIEW_SIZE = { width: 540, height: 960 } as const;

/** 썸네일 글자 수 한도 (임시값 — 정해진 규격이 없다) */
export const THUMBNAIL_CAPTION_MAX = 24;
