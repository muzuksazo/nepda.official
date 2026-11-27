import type { ShareHandlers } from '../components';

/** 예시 공유 주소. 실제 도메인과 영상 공유 주소 규칙은 아직 정해지지 않았다 */
const shareUrlOf = (id: string) => `https://napda.app/v/${id}`;

/**
 * 스토리·프로토타입용 공유 처리기: 실제 브라우저 기능(클립보드 · 기기 공유 창)을 부른다.
 * canShareNative를 넘기면 그 값으로 고정한다 (스토리에서 "기기 공유 창이 있는 폰"과 "PC"를 나눠 보려고).
 */
export function sampleShare(canShareNative?: boolean): ShareHandlers {
  return {
    shareUrlOf,
    canShareNative: canShareNative ?? (typeof navigator !== 'undefined' && typeof navigator.share === 'function'),
    onShareNative: (id) => {
      // 사용자가 공유 창을 닫으면 AbortError가 난다 — 실패가 아니므로 아무것도 하지 않는다
      navigator.share?.({ title: '냅다로 만든 릴스 광고', url: shareUrlOf(id) }).catch(() => undefined);
    },
    onCopyLink: (id) => {
      navigator.clipboard?.writeText(shareUrlOf(id)).catch(() => undefined);
    },
  };
}
