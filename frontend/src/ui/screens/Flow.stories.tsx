import { useState } from 'react';
import type { Meta, StoryObj } from '@storybook/react-vite';
import type { ThemeSetting } from '../NapdaProvider';
import { withDeviceFrame } from '../storybook/DeviceFrame';
import { setStorybookTheme } from '../storybook/themeGlobal';
import type { NavTab } from '../components';
import { CommunityScreen } from './CommunityScreen';
import { CommunityViewerScreen } from './CommunityViewerScreen';
import { HomeScreen } from './HomeScreen';
import { HookTypeScreen } from './HookTypeScreen';
import type { HookType } from './flowData';
import { OnboardingScreen } from './OnboardingScreen';
import { ProductInfoScreen } from './ProductInfoScreen';
import { ProfileScreen } from './ProfileScreen';
import { MyVideosScreen, type MyVideosTab } from './MyVideosScreen';
import {
  filterCommunityByType,
  SAMPLE_BANNERS,
  SAMPLE_COMMUNITY,
  SAMPLE_COMPLETED,
  SAMPLE_GUIDE_SCENES,
  SAMPLE_IN_PROGRESS,
  SAMPLE_STORYBOARD,
  SAMPLE_THUMBNAIL_CAPTION,
  SAMPLE_THUMBNAIL_TEMPLATES,
  SAMPLE_USER,
} from './sampleProjects';
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
  | 'community'
  | 'communityViewer'
  | 'profile'
  | 'product'
  | 'hook'
  | 'scenario'
  | 'storyboard'
  | 'guide'
  | 'upload'
  | 'review'
  | 'thumbnail';

/** 버튼을 눌러 온보딩 → 홈 → 8단계 흐름을 끝까지 따라가 보는 클릭 프로토타입 */
function FlowPrototype({ themeMode }: { themeMode: ThemeSetting }) {
  const [step, setStep] = useState<Step>('onboarding');
  const [myTab, setMyTab] = useState<MyVideosTab>('inProgress');
  const [hookType, setHookType] = useState<HookType>('B');
  const [productName, setProductName] = useState('[제품 이름]');
  const [communityType, setCommunityType] = useState<HookType | null>(null);
  const [viewerId, setViewerId] = useState<string>();
  const communityItems = filterCommunityByType(SAMPLE_COMMUNITY, communityType);
  // 하단 내비게이션: 네 탭 모두 옮겨 간다
  const navigate = (tab: NavTab) => {
    if (tab === 'home') setStep('home');
    if (tab === 'myVideos') {
      setMyTab('inProgress');
      setStep('myVideos');
    }
    if (tab === 'community') setStep('community');
    if (tab === 'profile') setStep('profile');
  };
  const completed = [{ id: 'mine', productName, status: '영상과 썸네일을 만들었어요' }, ...SAMPLE_COMPLETED];

  switch (step) {
    case 'onboarding':
      return <OnboardingScreen onStart={() => setStep('home')} />;
    case 'home':
      return (
        <HomeScreen
          credits={120}
          profile={{ name: SAMPLE_USER.name }}
          onProfileClick={() => setStep('profile')}
          onNavigate={navigate}
          banners={SAMPLE_BANNERS}
          inProgress={SAMPLE_IN_PROGRESS}
          completed={completed}
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
          completed={completed}
          initialTab={myTab}
          onNavigate={navigate}
          onContinue={() => setStep('upload')}
          onDownloadAgain={() => setStep('thumbnail')}
        />
      );
    case 'community':
      return (
        <CommunityScreen
          items={communityItems}
          hookType={communityType}
          onHookTypeChange={setCommunityType}
          onOpenVideo={(id) => {
            setViewerId(id);
            setStep('communityViewer');
          }}
          onCreate={() => setStep('product')}
          onNavigate={navigate}
        />
      );
    case 'communityViewer':
      return (
        <CommunityViewerScreen
          items={communityItems}
          initialId={viewerId}
          onBack={() => setStep('community')}
          // "이 훅으로 만들기": 같은 훅 유형을 고른 채로 만들기 흐름을 시작한다
          onRemix={(video) => {
            setHookType(video.hookType);
            setStep('product');
          }}
        />
      );
    case 'profile':
      return (
        <ProfileScreen
          user={SAMPLE_USER}
          credits={120}
          videoCounts={{ inProgress: SAMPLE_IN_PROGRESS.length, completed: completed.length }}
          retentionDays={7}
          themeMode={themeMode}
          onThemeModeChange={setStorybookTheme}
          onNavigate={navigate}
          onOpenMyVideos={(tab) => {
            setMyTab(tab);
            setStep('myVideos');
          }}
          onLogout={() => setStep('onboarding')}
          onDeleteAccount={() => setStep('onboarding')}
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
      return <StoryboardScreen hookType={hookType} scenes={SAMPLE_STORYBOARD} onBack={() => setStep('scenario')} onShootingGuide={() => setStep('guide')} />;
    case 'guide':
      return <ShootingGuideScreen scenes={SAMPLE_GUIDE_SCENES} onBack={() => setStep('scenario')} onUpload={() => setStep('upload')} />;
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
          templates={SAMPLE_THUMBNAIL_TEMPLATES}
          initialCaption={SAMPLE_THUMBNAIL_CAPTION}
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
  // 화면 모드는 Storybook 툴바의 '모드' 값을 쓰고, 내 정보에서 바꾸면 툴바와 화면이 함께 바뀐다
  render: (_args, { globals }) => <FlowPrototype themeMode={globals.napdaMode} />,
};
