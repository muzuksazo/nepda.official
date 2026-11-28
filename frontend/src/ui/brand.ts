// 로고: asset/logo/logo.png (한글 '냅다' + 영문 NAPDA, 기울어진 손글씨형)
// 로고는 상단 헤더에만 한 번, 냅다곰은 감정이 있는 순간에만 한 화면에 한 마리.
import mascotClapboard from '../assets/brand/mascot-clapboard.webp';
import mascotHappy from '../assets/brand/mascot-happy.webp';
import mascotLying from '../assets/brand/mascot-lying.webp';
import mascotSurprised from '../assets/brand/mascot-surprised.webp';
import splashBgWide from '../assets/brand/splash-bg-wide.webp';
import splashBg from '../assets/brand/splash-bg.webp';
import splashLogo from '../assets/brand/splash-logo.webp';
import wordmarkBlack from '../assets/brand/wordmark-black.png';
import wordmarkWhite from '../assets/brand/wordmark-white.png';

export const brand = {
  wordmarkBlack,
  wordmarkWhite,
  // 스플래시: asset/Splash/의 배경(splash.png, 1672×941)과 로고(splash_logo.png)를 따로 두고 화면에서 겹친다.
  // 로고를 배경에 박지 않아 어떤 화면에서도 또렷하다. 배경 세로판은 곰을 가운데 두고 9:16으로 자른 뒤 2배로 키웠다(1058×1882)
  splash: { background: splashBg, backgroundWide: splashBgWide, logo: splashLogo },
  // 냅다곰: asset/Character/의 고화질 원본(1200×896 투명 PNG)을 잘라 WebP로 줄인 것.
  // 서 있는 곰(클래퍼보드·놀람·신남)은 가슴선까지 잘랐다 (배꼽까지 자르면 어정쩡해 보여서)
  mascot: {
    /** 빈 홈: 클래퍼보드를 들고 "찍자" (Holding Clapboard, 가슴선 — 클래퍼 윗부분까지) */
    clapboard: mascotClapboard,
    /** 생성 대기: 누워서 머리 굴리는 중 (Lying Down) */
    lying: mascotLying,
    /** 실패: 놀란 표정 (Surprised, 가슴선) */
    surprised: mascotSurprised,
    /** 완성: 웃으며 주먹 쥔 모습 (Happy, 가슴선) */
    happy: mascotHappy,
  },
} as const;

/**
 * 냅다곰 이미지별 가로÷세로 비율과 높이 보정. Mascot이 크기 단계(높이)에 곱해 쓴다.
 * 자른 위치와 자세가 달라 같은 높이면 얼굴 크기가 달라 보이므로, 선글라스 폭이 같아지도록 높이를 보정했다(클래퍼보드 기준 1).
 */
export const MASCOT_META: Record<string, { ratio: number; heightScale: number }> = {
  [mascotClapboard]: { ratio: 355 / 360, heightScale: 1 },
  [mascotSurprised]: { ratio: 453 / 360, heightScale: 0.9 },
  [mascotHappy]: { ratio: 516 / 360, heightScale: 0.785 },
  [mascotLying]: { ratio: 467 / 300, heightScale: 0.87 },
};
