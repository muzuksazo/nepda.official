import type { Decorator } from '@storybook/react-vite';

/** 화면 스토리를 390×844 모바일 틀 안에 보여 준다 (Figma 프레임 크기). */
export const withDeviceFrame: Decorator = (Story) => (
  <div className="n-device">
    <Story />
  </div>
);
