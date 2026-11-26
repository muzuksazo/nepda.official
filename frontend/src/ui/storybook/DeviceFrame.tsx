import type { Decorator } from '@storybook/react-vite';

/** 화면 스토리를 390×844 모바일 틀 안에 보여 준다 (Figma 프레임 크기, 아이폰 14).
 *  아래 34px 안전 영역과 홈 인디케이터 막대를 함께 그려 실제 기기의 하단 여백을 확인한다. */
export const withDeviceFrame: Decorator = (Story) => (
  <div className="n-device">
    <div className="n-device__scroll">
      <Story />
    </div>
    <span className="n-device__home" aria-hidden="true" />
  </div>
);
