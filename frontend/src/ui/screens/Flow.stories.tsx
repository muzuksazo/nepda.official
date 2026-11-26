import { useState } from 'react';
import type { Meta, StoryObj } from '@storybook/react-vite';
import { withDeviceFrame } from '../storybook/DeviceFrame';
import type { NavTab } from '../components';
import { HomeScreen } from './HomeScreen';
import { HookTypeScreen } from './HookTypeScreen';
import type { HookType } from './flowData';
import { OnboardingScreen } from './OnboardingScreen';
import { ProductInfoScreen } from './ProductInfoScreen';
import { MyVideosScreen, type MyVideosTab } from './MyVideosScreen';
import { SAMPLE_BANNERS, SAMPLE_COMPLETED, SAMPLE_IN_PROGRESS } from './sampleProjects';
import { ScenarioScreen } from './ScenarioScreen';
import { ShootingGuideScreen } from './ShootingGuideScreen';
import { StoryboardScreen } from './StoryboardScreen';
import { ThumbnailDownloadScreen } from './ThumbnailDownloadScreen';
import { UploadVideoScreen } from './UploadVideoScreen';
import { VideoReviewScreen } from './VideoReviewScreen';

type Step =
  | 'onboarding'
  | 'home'
  | 'myVideos'
  | 'product'
  | 'hook'
  | 'scenario'
  | 'storyboard'
  | 'guide'
  | 'upload'
  | 'review'
  | 'thumbnail';

/** 버튼을 눌러 온보딩 → 홈 → 8단계 흐름을 끝까지 따라가 보는 클릭 프로토타입 */
function FlowPrototype() {
  const [step, setStep] = useState<Step>('onboarding');
  const [myTab, setMyTab] = useState<MyVideosTab>('inProgress');
  const [hookType, setHookType] = useState<HookType>('B');
  const [productName, setProductName] = useState('[제품 이름]');
  // 하단 내비게이션: 커뮤니티·프로필 화면은 아직 없어서 홈·내 영상만 옮겨 간다
  const navigate = (tab: NavTab) => {
    if (tab === 'home') setStep('home');
    if (tab === 'myVideos') {
      setMyTab('inProgress');
      setStep('myVideos');
    }
  };

  switch (step) {
    case 'onboarding':
      return <OnboardingScreen onStart={() => setStep('home')} />;
    case 'home':
      return (
        <HomeScreen
          credits={120}
          profile={{ name: '냅다사장' }}
          onNavigate={navigate}
          banners={SAMPLE_BANNERS}
          inProgress={SAMPLE_IN_PROGRESS}
          completed={[{ id: 'mine', productName, status: '영상과 썸네일을 만들었어요' }, ...SAMPLE_COMPLETED]}
          onCreate={() => setStep('product')}
          onContinue={() => setStep('upload')}
          onDownloadAgain={() => setStep('thumbnail')}
          onSeeAllInProgress={() => {
            setMyTab('inProgress');
            setStep('myVideos');
          }}
          onSeeAllCompleted={() => {
            setMyTab('completed');
            setStep('myVideos');
          }}
        />
      );
    case 'myVideos':
      return (
        <MyVideosScreen
          key={myTab}
          inProgress={SAMPLE_IN_PROGRESS}
          completed={[{ id: 'mine', productName, status: '영상과 썸네일을 만들었어요' }, ...SAMPLE_COMPLETED]}
          initialTab={myTab}
          onNavigate={navigate}
          onContinue={() => setStep('upload')}
          onDownloadAgain={() => setStep('thumbnail')}
        />
      );
    case 'product':
      return (
        <ProductInfoScreen
          onBack={() => setStep('home')}
          onNext={(v) => {
            setProductName(v.name);
            setStep('hook');
          }}
        />
      );
    case 'hook':
      return (
        <HookTypeScreen
          initialSelected={[hookType]}
          onBack={() => setStep('product')}
          onNext={(selected) => {
            setHookType(selected[0]);
            setStep('scenario');
          }}
          onSkipToVideo={() => setStep('guide')}
        />
      );
    case 'scenario':
      return (
        <ScenarioScreen
          hookType={hookType}
          onBack={() => setStep('hook')}
          onShootingGuide={() => setStep('guide')}
          onStoryboard={() => setStep('storyboard')}
        />
      );
    case 'storyboard':
      return <StoryboardScreen hookType={hookType} onBack={() => setStep('scenario')} onShootingGuide={() => setStep('guide')} />;
    case 'guide':
      return <ShootingGuideScreen onBack={() => setStep('scenario')} onUpload={() => setStep('upload')} />;
    case 'upload':
      return (
        <UploadVideoScreen
          hookType={hookType}
          onBack={() => setStep('guide')}
          onReviewGuide={() => setStep('guide')}
          onCreate={() => setStep('review')}
        />
      );
    case 'review':
      return <VideoReviewScreen onBack={() => setStep('upload')} onMakeThumbnail={() => setStep('thumbnail')} />;
    case 'thumbnail':
      return (
        <ThumbnailDownloadScreen
          onBack={() => setStep('review')}
          onDownloadVideo={() => setStep('home')}
          onDownloadThumbnail={() => setStep('home')}
        />
      );
  }
}

const meta = {
  title: 'NAPDA/흐름',
  decorators: [withDeviceFrame],
  parameters: { layout: 'fullscreen' },
} satisfies Meta;

export default meta;

export const ClickThrough: StoryObj<typeof meta> = {
  name: '전체 흐름 (클릭 프로토타입)',
  render: () => <FlowPrototype />,
};
