import { brand } from '../brand';

/**
 * 스플래시: 앱을 열고 로그인 상태를 확인하는 동안 화면 전체에 보여 준다.
 * 배경(하늘·잔디·냅다곰)과 로고를 따로 겹친다 — 로고는 배경과 함께 늘어나지 않아 늘 또렷하다.
 * 세로 화면은 곰을 가운데 둔 9:16 배경, 가로로 넓은 화면(데스크톱)은 가로 배경을 쓴다.
 */
export function SplashScreen() {
  return (
    <div className="n-splash" role="status" aria-label="냅다를 여는 중이에요">
      <picture>
        <source media="(min-aspect-ratio: 1/1)" srcSet={brand.splash.backgroundWide} />
        <img className="n-splash__bg" src={brand.splash.background} alt="" decoding="async" fetchPriority="high" />
      </picture>
      <img className="n-splash__logo" src={brand.splash.logo} alt="" width={900} height={576} decoding="async" />
    </div>
  );
}
