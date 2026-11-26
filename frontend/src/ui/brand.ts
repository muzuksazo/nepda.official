// 로고: asset/logo/logo.png (한글 '냅다' + 영문 NAPDA, 기울어진 손글씨형)
// 로고는 상단 헤더에만 한 번, 냅다곰은 감정이 있는 순간에만 한 화면에 한 마리.
import mascotClapboard from '../assets/brand/mascot-clapboard.png';
import mascotHappy from '../assets/brand/mascot-happy.png';
import mascotLying from '../assets/brand/mascot-lying.png';
import mascotSurprised from '../assets/brand/mascot-surprised.png';
import wordmarkBlack from '../assets/brand/wordmark-black.png';
import wordmarkWhite from '../assets/brand/wordmark-white.png';

export const brand = {
  wordmarkBlack,
  wordmarkWhite,
  mascot: {
    /** 빈 홈: 클래퍼보드를 들고 "찍자" */
    clapboard: mascotClapboard,
    /** 생성 대기: 누워서 머리 굴리는 중 */
    lying: mascotLying,
    /** 결과 공개: 놀란 표정 "!!" */
    surprised: mascotSurprised,
    /** 완성·내려받기: 웃으며 손 든 상반신 */
    happy: mascotHappy,
  },
} as const;
