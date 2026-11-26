import { useState } from 'react';
import type { Meta, StoryObj } from '@storybook/react-vite';
import { fn } from 'storybook/test';
import type { ThemeSetting } from '../NapdaProvider';
import { withDeviceFrame } from '../storybook/DeviceFrame';
import { setStorybookTheme } from '../storybook/themeGlobal';
import { CommunityScreen, type CommunityVideo } from './CommunityScreen';
import type { HookType as HookKind } from './flowData';
import { CommunityViewerScreen } from './CommunityViewerScreen';
import { HomeScreen } from './HomeScreen';
import { HookTypeScreen } from './HookTypeScreen';
import { OnboardingScreen } from './OnboardingScreen';
import { ProductInfoScreen } from './ProductInfoScreen';
import { ProfileScreen, type ProfileScreenProps } from './ProfileScreen';
import { MyVideosScreen } from './MyVideosScreen';
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
      credits={120}
      onCreditClick={fn()}
      profile={{ name: '냅다사장' }}
      onProfileClick={fn()}
      onNavigate={fn()}
    />
  ),
};

export const MyVideos: Story = {
  name: '안3-2 내 영상 · 진행 중 탭',
  render: () => (
    <MyVideosScreen inProgress={SAMPLE_IN_PROGRESS} completed={SAMPLE_COMPLETED} onNavigate={fn()} onContinue={fn()} onDownloadAgain={fn()} />
  ),
};

export const MyVideosCompleted: Story = {
  name: '안3-2 내 영상 · 완료 탭',
  render: () => (
    <MyVideosScreen
      inProgress={SAMPLE_IN_PROGRESS}
      completed={SAMPLE_COMPLETED}
      initialTab="completed"
      onNavigate={fn()}
      onContinue={fn()}
      onDownloadAgain={fn()}
    />
  ),
};

/** 내 정보 스토리 공통 값. 화면 모드는 Storybook 툴바의 '모드'와 같은 값을 쓰고, 화면에서 바꾸면 바로 적용된다. */
const profileProps = (themeMode: ThemeSetting): ProfileScreenProps => ({
  user: SAMPLE_USER,
  credits: 120,
  videoCounts: { inProgress: SAMPLE_IN_PROGRESS.length, completed: SAMPLE_COMPLETED.length },
  retentionDays: 7,
  themeMode,
  onThemeModeChange: setStorybookTheme,
  onNavigate: fn(),
  onChargeClick: fn(),
  onOpenMyVideos: fn(),
  onOpenDoc: fn(),
  onLogout: fn(),
  onDeleteAccount: fn(),
  onSignIn: fn(),
});

export const Profile: Story = {
  name: '안3-3 내 정보',
  render: (_args, { globals }) => <ProfileScreen {...profileProps(globals.napdaMode)} />,
};

/** 막 가입한 사용자: 크레딧은 없지만 온보딩 무료 제작 1회가 남아 있다 */
export const ProfileFreeVideo: Story = {
  name: '안3-3 내 정보 · 첫 영상 무료 남음',
  render: (_args, { globals }) => (
    <ProfileScreen {...profileProps(globals.napdaMode)} credits={0} hasFreeVideo videoCounts={{ inProgress: 0, completed: 0 }} />
  ),
};

export const ProfileNoCredits: Story = {
  name: '안3-3 내 정보 · 크레딧 없음',
  render: (_args, { globals }) => <ProfileScreen {...profileProps(globals.napdaMode)} credits={0} />,
};

export const ProfileLoading: Story = {
  name: '안3-3 내 정보 · 불러오는 중',
  render: (_args, { globals }) => (
    <ProfileScreen {...profileProps(globals.napdaMode)} user={undefined} credits={undefined} videoCounts={undefined} isLoading />
  ),
};

export const ProfileSignedOut: Story = {
  name: '안3-3 내 정보 · 로그인 전',
  render: (_args, { globals }) => <ProfileScreen {...profileProps(globals.napdaMode)} user={null} />,
};

export const ProfileLogoutConfirm: Story = {
  name: '안3-3 내 정보 · 로그아웃 확인',
  render: (_args, { globals }) => <ProfileScreen {...profileProps(globals.napdaMode)} initialConfirm="logout" />,
};

export const ProfileDeleteConfirm: Story = {
  name: '안3-3 내 정보 · 탈퇴 확인',
  render: (_args, { globals }) => <ProfileScreen {...profileProps(globals.napdaMode)} initialConfirm="delete" />,
};

/** 탭을 누르면 예시 목록이 그 훅 유형으로 걸러진다 */
function CommunityDemo({ items = SAMPLE_COMMUNITY, initialHookType = null }: { items?: CommunityVideo[]; initialHookType?: HookKind | null }) {
  const [hookType, setHookType] = useState<HookKind | null>(initialHookType);
  return (
    <CommunityScreen
      items={filterCommunityByType(items, hookType)}
      hookType={hookType}
      onHookTypeChange={setHookType}
      onOpenVideo={fn()}
      onNavigate={fn()}
    />
  );
}

export const Community: Story = {
  name: '안3-4 커뮤니티',
  render: () => <CommunityDemo />,
};

export const CommunityByType: Story = {
  name: '안3-4 커뮤니티 · B 유형 탭',
  render: () => <CommunityDemo initialHookType="B" />,
};

export const CommunityLoading: Story = {
  name: '안3-4 커뮤니티 · 불러오는 중',
  render: () => <CommunityScreen items={[]} hookType={null} status="loading" onNavigate={fn()} />,
};

export const CommunityLoadingMore: Story = {
  name: '안3-4 커뮤니티 · 더 불러오는 중',
  render: () => (
    <CommunityScreen items={SAMPLE_COMMUNITY.slice(0, 6)} hookType={null} hasMore isLoadingMore onOpenVideo={fn()} onNavigate={fn()} />
  ),
};

export const CommunityEmpty: Story = {
  name: '안3-4 커뮤니티 · 빈 상태',
  render: () => <CommunityScreen items={[]} hookType={null} onCreate={fn()} onNavigate={fn()} />,
};

/** 고른 유형에 올라온 영상이 없을 때. "전체 보기"를 누르면 전체 탭으로 돌아간다 */
export const CommunityNoMatch: Story = {
  name: '안3-4 커뮤니티 · 이 유형은 아직 없음',
  render: () => <CommunityDemo items={SAMPLE_COMMUNITY.filter((video) => video.hookType !== 'C')} initialHookType="C" />,
};

export const CommunityError: Story = {
  name: '안3-4 커뮤니티 · 불러오기 실패',
  render: () => <CommunityScreen items={[]} hookType={null} status="error" onRetry={fn()} onNavigate={fn()} />,
};

const viewerItems = SAMPLE_COMMUNITY;

/** 첫 영상에는 예시 영상이 있어 자동 재생(소리 꺼짐)·일시정지·소리 켜기를 볼 수 있다. 위아래로 넘기면 다음 영상 */
export const CommunityViewer: Story = {
  name: '안3-5 영상 보기',
  render: () => (
    <CommunityViewerScreen items={viewerItems} onBack={fn()} onToggleLike={fn()} onShare={fn()} onReport={fn()} onRemix={fn()} />
  ),
};

export const CommunityViewerReport: Story = {
  name: '안3-5 영상 보기 · 신고 확인',
  render: () => <CommunityViewerScreen items={viewerItems} initialId="v03" initialIsReporting onBack={fn()} onReport={fn()} />,
};

export const HomeEmpty: Story = {
  name: '안3-1 홈 · 빈 상태',
  render: () => <HomeScreen inProgress={[]} completed={[]} onCreate={fn()} credits={30} onCreditClick={fn()} onProfileClick={fn()} onNavigate={fn()} />,
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

/** 그림을 그리는 동안: 장면 설명 자리에 스켈레톤이 반짝인다 */
export const Storyboard: Story = {
  name: '안1-5 그림 콘티',
  render: () => <StoryboardScreen hookType="B" onBack={fn()} onShootingGuide={fn()} />,
};

export const StoryboardFilled: Story = {
  name: '안1-5 그림 콘티 · 설명 채움',
  render: () => <StoryboardScreen hookType="B" scenes={SAMPLE_STORYBOARD} onBack={fn()} onShootingGuide={fn()} />,
};

export const ShootingGuide: Story = {
  name: '안1-6 촬영 가이드',
  render: () => <ShootingGuideScreen scenes={SAMPLE_GUIDE_SCENES} onBack={fn()} onUpload={fn()} />,
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

/** 썸네일 화면 스토리들이 함께 쓰는 예시 템플릿·글자·콜백 */
const thumbnailArgs = {
  templates: SAMPLE_THUMBNAIL_TEMPLATES,
  initialCaption: SAMPLE_THUMBNAIL_CAPTION,
  onBack: fn(),
  onDownloadVideo: fn(),
  onDownloadThumbnail: fn(),
  onTemplateChange: fn(),
  onPublicChange: fn(),
};

export const ThumbnailDownload: Story = {
  name: '안1-9 썸네일·내려받기',
  render: () => <ThumbnailDownloadScreen {...thumbnailArgs} />,
};

export const ThumbnailDownloadLastPicked: Story = {
  name: '안1-9 썸네일·내려받기 · 뒤쪽 시안을 골라 둠',
  render: () => <ThumbnailDownloadScreen {...thumbnailArgs} initialTemplateId="split" />,
};

export const ThumbnailDownloadNoPreview: Story = {
  name: '안1-9 썸네일·내려받기 · 템플릿 이미지 넣기 전',
  render: () => (
    <ThumbnailDownloadScreen
      {...thumbnailArgs}
      templates={SAMPLE_THUMBNAIL_TEMPLATES.map((template) => ({ ...template, previewUrl: undefined }))}
    />
  ),
};

export const ThumbnailDownloadPublishConfirm: Story = {
  name: '안1-9 썸네일·내려받기 · 커뮤니티 올리기 동의',
  render: () => <ThumbnailDownloadScreen {...thumbnailArgs} initialIsConfirmingPublish />,
};

export const ThumbnailDownloadPublic: Story = {
  name: '안1-9 썸네일·내려받기 · 커뮤니티 공개 중',
  render: () => <ThumbnailDownloadScreen {...thumbnailArgs} initialIsPublic />,
};
