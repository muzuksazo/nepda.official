import type { Meta, StoryObj } from '@storybook/react-vite';
import { fn } from 'storybook/test';
import { withDeviceFrame } from '../storybook/DeviceFrame';
import { HomeScreen } from './HomeScreen';
import { HookTypeScreen } from './HookTypeScreen';
import { OnboardingScreen } from './OnboardingScreen';
import { ProductInfoScreen } from './ProductInfoScreen';
import { MyVideosScreen } from './MyVideosScreen';
import { SAMPLE_BANNERS, SAMPLE_COMPLETED, SAMPLE_IN_PROGRESS } from './sampleProjects';
import { ScenarioScreen } from './ScenarioScreen';
import { ShootingGuideScreen } from './ShootingGuideScreen';
import { StoryboardScreen } from './StoryboardScreen';
import { ThumbnailDownloadScreen } from './ThumbnailDownloadScreen';
import { UploadVideoScreen } from './UploadVideoScreen';
import { VideoReviewScreen } from './VideoReviewScreen';

/**
 * Figma 와이어프레임(안1-1 ~ 안1-9, 안3-1)의 화면 구조를 냅다 디자인(/DESIGN.md)으로 구현한 화면들.
 * /DESIGN.md 토큰으로 직접 만든 냅다 컴포넌트를 쓴다. 툴바에서 라이트/다크를 바꿀 수 있다.
 */
const meta = {
  title: 'NAPDA/화면',
  decorators: [withDeviceFrame],
  parameters: { layout: 'fullscreen' },
} satisfies Meta;

export default meta;
type Story = StoryObj<typeof meta>;

export const Home: Story = {
  name: '안3-1 홈',
  render: () => (
    <HomeScreen
      banners={SAMPLE_BANNERS}
      onBannerSelect={fn()}
      inProgress={SAMPLE_IN_PROGRESS}
      completed={SAMPLE_COMPLETED}
      onCreate={fn()}
      onContinue={fn()}
      onDownloadAgain={fn()}
      onSeeAllInProgress={fn()}
      onSeeAllCompleted={fn()}
    />
  ),
};

export const MyVideos: Story = {
  name: '안3-2 내 영상 · 만드는 중 탭',
  render: () => (
    <MyVideosScreen inProgress={SAMPLE_IN_PROGRESS} completed={SAMPLE_COMPLETED} onBack={fn()} onContinue={fn()} onDownloadAgain={fn()} />
  ),
};

export const MyVideosCompleted: Story = {
  name: '안3-2 내 영상 · 완성 탭',
  render: () => (
    <MyVideosScreen
      inProgress={SAMPLE_IN_PROGRESS}
      completed={SAMPLE_COMPLETED}
      initialTab="completed"
      onBack={fn()}
      onContinue={fn()}
      onDownloadAgain={fn()}
    />
  ),
};

export const HomeEmpty: Story = {
  name: '안3-1 홈 · 빈 상태',
  render: () => <HomeScreen inProgress={[]} completed={[]} onCreate={fn()} />,
};

export const Onboarding: Story = {
  name: '안1-1 온보딩',
  render: () => <OnboardingScreen onStart={fn()} />,
};

export const ProductInfo: Story = {
  name: '안1-2 제품 정보',
  render: () => <ProductInfoScreen initialValue={{ category: '주방' }} onBack={fn()} onNext={fn()} />,
};

export const HookType: Story = {
  name: '안1-3 유형 선택',
  render: () => <HookTypeScreen initialSelected={['B']} onBack={fn()} onNext={fn()} onSkipToVideo={fn()} />,
};

export const Scenario: Story = {
  name: '안1-4 시나리오 글',
  render: () => <ScenarioScreen hookType="B" onBack={fn()} onShootingGuide={fn()} onStoryboard={fn()} />,
};

export const Storyboard: Story = {
  name: '안1-5 그림 콘티',
  render: () => <StoryboardScreen hookType="B" onBack={fn()} onShootingGuide={fn()} />,
};

export const ShootingGuide: Story = {
  name: '안1-6 촬영 가이드',
  render: () => <ShootingGuideScreen onBack={fn()} onUpload={fn()} />,
};

export const UploadVideo: Story = {
  name: '안1-7 영상 올리기',
  render: () => <UploadVideoScreen hookType="B" onBack={fn()} onReviewGuide={fn()} onCreate={fn()} />,
};

export const UploadVideoSelected: Story = {
  name: '안1-7 영상 올리기 · 영상 고른 뒤',
  render: () => (
    <UploadVideoScreen hookType="B" initialFile={new File([''], '본편_촬영.mp4', { type: 'video/mp4' })} onBack={fn()} onReviewGuide={fn()} onCreate={fn()} />
  ),
};

export const VideoReview: Story = {
  name: '안1-8 영상 확인',
  render: () => <VideoReviewScreen onBack={fn()} onPlay={fn()} onMakeThumbnail={fn()} />,
};

export const ThumbnailDownload: Story = {
  name: '안1-9 썸네일·내려받기',
  render: () => <ThumbnailDownloadScreen onBack={fn()} onDownloadVideo={fn()} onDownloadThumbnail={fn()} />,
};
