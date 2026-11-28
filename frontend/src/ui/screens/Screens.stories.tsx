import { useState } from 'react';
import type { Meta, StoryObj } from '@storybook/react-vite';
import { fn } from 'storybook/test';
import type { ThemeSetting } from '../NapdaProvider';
import { withDeviceFrame } from '../storybook/DeviceFrame';
import { setStorybookTheme } from '../storybook/themeGlobal';
import { sampleShare } from '../storybook/sampleShare';
import { useCreatorPeek } from '../storybook/useCreatorPeek';
import { useSampleComments } from '../storybook/useSampleComments';
import { ChargeResultScreen } from './ChargeResultScreen';
import { CommunityScreen, type CommunityVideo } from './CommunityScreen';
import { CreatorProfileScreen } from './CreatorProfileScreen';
import { CreditChargeScreen } from './CreditChargeScreen';
import { CreditHistoryScreen } from './CreditHistoryScreen';
import type { HookType as HookKind } from './flowData';
import { CommunityViewerScreen } from './CommunityViewerScreen';
import { GeneratingScreen } from './GeneratingScreen';
import { HomeScreen } from './HomeScreen';
import { HookTypeScreen } from './HookTypeScreen';
import { LoginScreen } from './LoginScreen';
import { NicknameScreen } from './NicknameScreen';
import { NotificationsScreen } from './NotificationsScreen';
import { OnboardingScreen } from './OnboardingScreen';
import { SplashScreen } from './SplashScreen';
import { ProductInfoScreen } from './ProductInfoScreen';
import { ProfileScreen, type ProfileScreenProps } from './ProfileScreen';
import { MyVideosScreen } from './MyVideosScreen';
import {
  filterCommunityByType,
  SAMPLE_BANNERS,
  SAMPLE_COMMENTS,
  SAMPLE_COMMUNITY,
  SAMPLE_COMPLETED,
  SAMPLE_CREDIT_EXPIRING,
  SAMPLE_CREDIT_HISTORY,
  SAMPLE_CREDIT_PACKAGES,
  SAMPLE_CREDITS_PER_VIDEO,
  SAMPLE_GUIDE_SCENES,
  SAMPLE_IN_PROGRESS,
  SAMPLE_LOGIN_SHOWCASE,
  SAMPLE_NOTIFICATIONS,
  SAMPLE_NOW,
  SAMPLE_STORYBOARD,
  SAMPLE_THUMBNAIL_CAPTION,
  SAMPLE_THUMBNAIL_TEMPLATES,
  SAMPLE_USER,
  sampleCreator,
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
  render: function Render() {
    // 피드 게시물의 프로필 원·닉네임을 누르면 그 사람 프로필이 열린다
    const peek = useCreatorPeek();
    if (peek.profileScreen) return peek.profileScreen;
    return (
      <HomeScreen
        banners={SAMPLE_BANNERS}
        onBannerSelect={fn()}
        inProgress={SAMPLE_IN_PROGRESS}
        completed={SAMPLE_COMPLETED}
        onCreate={fn()}
        onContinue={fn()}
        onDownloadAgain={fn()}
        onSeeAllMyVideos={fn()}
        credits={120}
        onCreditClick={fn()}
        unreadCount={SAMPLE_NOTIFICATIONS.filter((n) => !n.isRead).length}
        onNotificationsClick={fn()}
        profile={{ name: '냅다사장' }}
        onNavigate={fn()}
        feed={SAMPLE_COMMUNITY.slice(0, 4)}
        feedHasMore
        onLoadMoreFeed={fn()}
        onOpenFeed={fn()}
        onToggleFeedLike={fn()}
        share={sampleShare(true)}
        onOpenCreator={peek.onOpenCreator}
        onRemixFeed={fn()}
        onSeeAllFeed={fn()}
      />
    );
  },
};

/** 공유 시트: 기기 공유 창이 있는 폰 — "카톡·인스타로 보내기" + 링크 복사 */
export const HomeShare: Story = {
  name: '안3-1 홈 · 공유 시트',
  render: () => (
    <HomeScreen
      inProgress={SAMPLE_IN_PROGRESS}
      completed={SAMPLE_COMPLETED}
      credits={120}
      profile={{ name: '냅다사장' }}
      feed={SAMPLE_COMMUNITY.slice(0, 4)}
      share={{ ...sampleShare(true), onShareNative: fn(), onCopyLink: fn() }}
      initialShareFor="v01"
    />
  ),
};

/** 공유 시트: 기기 공유 창이 없는 곳(PC·일부 앱 안 브라우저) — 링크 복사만 */
export const HomeShareCopyOnly: Story = {
  name: '안3-1 홈 · 공유 시트 (링크 복사만)',
  render: () => (
    <HomeScreen
      inProgress={SAMPLE_IN_PROGRESS}
      completed={SAMPLE_COMPLETED}
      credits={120}
      profile={{ name: '냅다사장' }}
      feed={SAMPLE_COMMUNITY.slice(0, 4)}
      share={{ ...sampleShare(false), onCopyLink: fn() }}
      initialShareFor="v02"
    />
  ),
};

export const HomeFeed: Story = {
  name: '안3-1 홈 · 피드 내려 보기',
  render: function Render() {
    // 맨 아래에 닿으면 4개씩 더 불러온다 (예시 12개까지)
    const [count, setCount] = useState(4);
    const [isLoadingMore, setIsLoadingMore] = useState(false);
    const commentProps = useSampleComments(SAMPLE_COMMENTS, SAMPLE_USER.name);
    const peek = useCreatorPeek();
    if (peek.profileScreen) return peek.profileScreen;
    return (
      <HomeScreen
        {...commentProps}
        inProgress={SAMPLE_IN_PROGRESS}
        completed={SAMPLE_COMPLETED}
        credits={120}
        profile={{ name: '냅다사장' }}
        feed={SAMPLE_COMMUNITY.slice(0, count)}
        feedHasMore={count < SAMPLE_COMMUNITY.length}
        isFeedLoadingMore={isLoadingMore}
        onLoadMoreFeed={() => {
          setIsLoadingMore(true);
          window.setTimeout(() => {
            setCount((value) => Math.min(SAMPLE_COMMUNITY.length, value + 4));
            setIsLoadingMore(false);
          }, 700);
        }}
        onOpenFeed={fn()}
        onOpenCreator={peek.onOpenCreator}
        onRemixFeed={fn()}
        onSeeAllFeed={fn()}
      />
    );
  },
};

/** 알림 화면 스토리들이 함께 쓰는 기준 시각·콜백 */
const notificationArgs = { now: SAMPLE_NOW, onBack: fn(), onOpen: fn(), onMarkAllRead: fn() };

export const Notifications: Story = {
  name: '알림',
  render: function Render() {
    // 눌러 보면 읽음으로 바뀌고, "모두 읽음"이 동작한다
    const [items, setItems] = useState(SAMPLE_NOTIFICATIONS);
    return (
      <NotificationsScreen
        {...notificationArgs}
        items={items}
        onOpen={(target) => setItems((prev) => prev.map((n) => (n.id === target.id ? { ...n, isRead: true } : n)))}
        onMarkAllRead={() => setItems((prev) => prev.map((n) => ({ ...n, isRead: true })))}
      />
    );
  },
};

export const NotificationsAllRead: Story = {
  name: '알림 · 모두 읽음',
  render: () => <NotificationsScreen {...notificationArgs} items={SAMPLE_NOTIFICATIONS.map((n) => ({ ...n, isRead: true }))} />,
};

export const NotificationsEmpty: Story = {
  name: '알림 · 없음',
  render: () => <NotificationsScreen {...notificationArgs} items={[]} />,
};

export const NotificationsLoading: Story = {
  name: '알림 · 불러오는 중',
  render: () => <NotificationsScreen {...notificationArgs} items={[]} status="loading" />,
};

export const HomeComments: Story = {
  name: '안3-1 홈 · 피드 댓글',
  render: function Render() {
    const commentProps = useSampleComments(SAMPLE_COMMENTS, SAMPLE_USER.name);
    const peek = useCreatorPeek();
    if (peek.profileScreen) return peek.profileScreen;
    return (
      <HomeScreen
        {...commentProps}
        inProgress={SAMPLE_IN_PROGRESS}
        completed={SAMPLE_COMPLETED}
        credits={120}
        profile={{ name: SAMPLE_USER.name }}
        feed={SAMPLE_COMMUNITY.slice(0, 4)}
        onOpenCreator={peek.onOpenCreator}
        initialCommentsFor="v01"
      />
    );
  },
};

export const HomeCommentsEmpty: Story = {
  name: '안3-1 홈 · 피드 댓글 없음',
  render: () => (
    <HomeScreen
      inProgress={SAMPLE_IN_PROGRESS}
      completed={SAMPLE_COMPLETED}
      credits={120}
      profile={{ name: SAMPLE_USER.name }}
      feed={SAMPLE_COMMUNITY.slice(3, 6)}
      initialCommentsFor="v04"
      onAddComment={fn()}
    />
  ),
};

/** 내 영상: "선택" → 고르기 → "N개 지우기"를 누르면 이 스토리 안에서 실제로 목록에서 빠진다 */
function MyVideosWithDelete({ initialTab }: { initialTab?: 'inProgress' | 'completed' }) {
  const [deletedIds, setDeletedIds] = useState<ReadonlySet<string>>(() => new Set());
  return (
    <MyVideosScreen
      inProgress={SAMPLE_IN_PROGRESS.filter((p) => !deletedIds.has(p.id))}
      completed={SAMPLE_COMPLETED.filter((p) => !deletedIds.has(p.id))}
      initialTab={initialTab}
      onNavigate={fn()}
      onContinue={fn()}
      onDownloadAgain={fn()}
      onDelete={(ids) => setDeletedIds((prev) => new Set([...prev, ...ids]))}
    />
  );
}

export const MyVideos: Story = {
  name: '안3-2 내 영상 · 진행 중 탭',
  render: () => <MyVideosWithDelete />,
};

export const MyVideosCompleted: Story = {
  name: '안3-2 내 영상 · 완료 탭',
  render: () => <MyVideosWithDelete initialTab="completed" />,
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
  onCreditHistoryClick: fn(),
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
  name: '안3-4 탐색',
  render: () => <CommunityDemo />,
};

export const CommunityByType: Story = {
  name: '안3-4 탐색 · B 유형 탭',
  render: () => <CommunityDemo initialHookType="B" />,
};

export const CommunityLoading: Story = {
  name: '안3-4 탐색 · 불러오는 중',
  render: () => <CommunityScreen items={[]} hookType={null} status="loading" onNavigate={fn()} />,
};

export const CommunityLoadingMore: Story = {
  name: '안3-4 탐색 · 더 불러오는 중',
  render: () => (
    <CommunityScreen items={SAMPLE_COMMUNITY.slice(0, 6)} hookType={null} hasMore isLoadingMore onOpenVideo={fn()} onNavigate={fn()} />
  ),
};

export const CommunityEmpty: Story = {
  name: '안3-4 탐색 · 빈 상태',
  render: () => <CommunityScreen items={[]} hookType={null} onCreate={fn()} onNavigate={fn()} />,
};

/** 고른 유형에 올라온 영상이 없을 때. "전체 보기"를 누르면 전체 탭으로 돌아간다 */
export const CommunityNoMatch: Story = {
  name: '안3-4 탐색 · 이 유형은 아직 없음',
  render: () => <CommunityDemo items={SAMPLE_COMMUNITY.filter((video) => video.hookType !== 'C')} initialHookType="C" />,
};

export const CommunityError: Story = {
  name: '안3-4 탐색 · 불러오기 실패',
  render: () => <CommunityScreen items={[]} hookType={null} status="error" onRetry={fn()} onNavigate={fn()} />,
};

const viewerItems = SAMPLE_COMMUNITY;

/** 첫 영상에는 예시 영상이 있어 자동 재생(소리 꺼짐)·일시정지·소리 켜기를 볼 수 있다. 위아래로 넘기면 다음 영상 */
export const CommunityViewer: Story = {
  name: '안3-5 영상 보기',
  render: function Render() {
    const commentProps = useSampleComments(SAMPLE_COMMENTS, SAMPLE_USER.name);
    const peek = useCreatorPeek();
    if (peek.profileScreen) return peek.profileScreen;
    return (
      <CommunityViewerScreen
        {...commentProps}
        myName={SAMPLE_USER.name}
        items={viewerItems}
        onBack={fn()}
        onToggleLike={fn()}
        share={sampleShare(true)}
        onOpenCreator={peek.onOpenCreator}
        onReport={fn()}
        onRemix={fn()}
      />
    );
  },
};

const creatorArgs = { onBack: fn(), onOpenVideo: fn(), onRemix: fn() };

export const CreatorProfile: Story = {
  name: '만든 사람 프로필',
  render: () => {
    const { profile, videos } = sampleCreator('도마왕');
    return <CreatorProfileScreen {...creatorArgs} creator={profile} videos={videos} />;
  },
};

export const CreatorProfileOneVideo: Story = {
  name: '만든 사람 프로필 · 영상 한 편',
  render: () => {
    const { profile, videos } = sampleCreator('텀블러수집가');
    return <CreatorProfileScreen {...creatorArgs} creator={profile} videos={videos} />;
  },
};

export const CreatorProfileEmpty: Story = {
  name: '만든 사람 프로필 · 올린 영상 없음',
  render: () => (
    <CreatorProfileScreen {...creatorArgs} creator={{ name: '설거지장인', videoCount: 0, likeCount: 0 }} videos={[]} />
  ),
};

export const CreatorProfileLoading: Story = {
  name: '만든 사람 프로필 · 불러오는 중',
  render: () => <CreatorProfileScreen {...creatorArgs} videos={[]} status="loading" />,
};

export const CreatorProfileGone: Story = {
  name: '만든 사람 프로필 · 사라짐',
  render: () => <CreatorProfileScreen {...creatorArgs} videos={[]} status="gone" />,
};

export const CommunityViewerReport: Story = {
  name: '안3-5 영상 보기 · 신고 확인',
  render: () => <CommunityViewerScreen items={viewerItems} initialId="v03" initialIsReporting onBack={fn()} onReport={fn()} />,
};

export const HomeEmpty: Story = {
  name: '안3-1 홈 · 빈 상태',
  render: () => <HomeScreen inProgress={[]} completed={[]} onCreate={fn()} credits={30} onCreditClick={fn()} onNavigate={fn()} />,
};

export const Splash: Story = {
  name: '안0 스플래시',
  render: () => <SplashScreen />,
};

export const Onboarding: Story = {
  name: '안1-1 온보딩',
  render: () => <OnboardingScreen onStart={fn()} />,
};

/** 로그인 화면 스토리들이 함께 쓰는 콜백 */
const loginArgs = {
  showcase: SAMPLE_LOGIN_SHOWCASE,
  onSignIn: fn(),
  onCopyLink: fn(),
  onAgreeTerms: fn(),
  onCloseTerms: fn(),
  onOpenDoc: fn(),
};

export const Login: Story = {
  name: '로그인',
  render: () => <LoginScreen {...loginArgs} />,
};

export const LoginSigningIn: Story = {
  name: '로그인 · 들어가는 중',
  render: () => <LoginScreen {...loginArgs} isSigningIn />,
};

export const LoginError: Story = {
  name: '로그인 · 실패',
  render: () => <LoginScreen {...loginArgs} hasError />,
};

export const LoginExpired: Story = {
  name: '로그인 · 로그인이 풀렸을 때',
  render: () => <LoginScreen {...loginArgs} reason="expired" />,
};

export const LoginInAppBrowser: Story = {
  name: '로그인 · 앱 안 브라우저',
  render: () => <LoginScreen {...loginArgs} isInAppBrowser />,
};

export const SignupTerms: Story = {
  name: '회원가입 1 · 약관 동의 시트',
  render: () => <LoginScreen {...loginArgs} isTermsOpen />,
};

/** 회원가입 2단계 스토리들이 함께 쓰는 콜백 */
const nicknameArgs = { onBack: fn(), onNicknameChange: fn(), onSubmit: fn() };

export const SignupNickname: Story = {
  name: '회원가입 2 · 닉네임 정하기',
  render: () => <NicknameScreen {...nicknameArgs} initialNickname="냅다사장" availability="available" />,
};

export const SignupNicknameChecking: Story = {
  name: '회원가입 2 · 닉네임 확인 중',
  render: () => <NicknameScreen {...nicknameArgs} initialNickname="도마왕" availability="checking" />,
};

export const SignupNicknameTaken: Story = {
  name: '회원가입 2 · 이미 있는 닉네임',
  render: () => <NicknameScreen {...nicknameArgs} initialNickname="도마왕" availability="taken" />,
};

export const SignupNicknameInvalid: Story = {
  name: '회원가입 2 · 규칙에 안 맞는 닉네임',
  render: () => <NicknameScreen {...nicknameArgs} initialNickname="도마 왕!" />,
};

export const SignupNicknameEmpty: Story = {
  name: '회원가입 2 · 닉네임 비었을 때',
  render: () => <NicknameScreen {...nicknameArgs} />,
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

/** 영상 올리기 스토리들이 함께 쓰는 예시 영상·콜백 */
const uploadArgs = {
  hookType: 'B' as const,
  onBack: fn(),
  onReviewGuide: fn(),
  onCreate: fn(),
  onCharge: fn(),
};
const sampleUpload = () => new File([''], '본편_촬영.mp4', { type: 'video/mp4' });

export const UploadVideo: Story = {
  name: '안1-7 영상 올리기',
  render: () => <UploadVideoScreen {...uploadArgs} cost={SAMPLE_CREDITS_PER_VIDEO} credits={120} />,
};

export const UploadVideoSelected: Story = {
  name: '안1-7 영상 올리기 · 영상 고른 뒤',
  render: () => <UploadVideoScreen {...uploadArgs} initialFiles={[sampleUpload()]} cost={SAMPLE_CREDITS_PER_VIDEO} credits={120} />,
};

export const UploadVideoShort: Story = {
  name: '안1-7 영상 올리기 · 크레딧 모자람',
  render: () => (
    <UploadVideoScreen {...uploadArgs} initialFiles={[sampleUpload()]} cost={SAMPLE_CREDITS_PER_VIDEO} credits={5} initialIsShort />
  ),
};

/** 크레딧 충전 스토리들이 함께 쓰는 묶음·콜백 */
const chargeArgs = {
  packages: SAMPLE_CREDIT_PACKAGES,
  creditsPerVideo: SAMPLE_CREDITS_PER_VIDEO,
  onBack: fn(),
  onPay: fn(),
  onOpenPolicy: fn(),
};

const creditHistoryArgs = { now: SAMPLE_NOW, onBack: fn(), onCharge: fn(), onRetry: fn(), onOpenPolicy: fn() };

export const CreditHistory: Story = {
  name: '크레딧 내역',
  render: () => (
    <CreditHistoryScreen {...creditHistoryArgs} credits={104} entries={SAMPLE_CREDIT_HISTORY} expiring={SAMPLE_CREDIT_EXPIRING} />
  ),
};

export const CreditHistoryUse: Story = {
  name: '크레딧 내역 · 사용 탭',
  render: () => <CreditHistoryScreen {...creditHistoryArgs} credits={104} entries={SAMPLE_CREDIT_HISTORY} initialFilter="use" />,
};

export const CreditHistoryLoadMore: Story = {
  name: '크레딧 내역 · 이어 불러오기',
  render: function Render() {
    // 처음 5줄만 받고, 맨 아래로 내리면 0.8초 뒤 나머지를 붙인다
    const [count, setCount] = useState(5);
    const [isLoadingMore, setIsLoadingMore] = useState(false);
    return (
      <CreditHistoryScreen
        {...creditHistoryArgs}
        credits={104}
        entries={SAMPLE_CREDIT_HISTORY.slice(0, count)}
        hasMore={count < SAMPLE_CREDIT_HISTORY.length}
        isLoadingMore={isLoadingMore}
        onLoadMore={() => {
          setIsLoadingMore(true);
          window.setTimeout(() => {
            setCount(SAMPLE_CREDIT_HISTORY.length);
            setIsLoadingMore(false);
          }, 800);
        }}
      />
    );
  },
};

export const CreditHistoryEmpty: Story = {
  name: '크레딧 내역 · 없음',
  render: () => <CreditHistoryScreen {...creditHistoryArgs} credits={0} entries={[]} />,
};

export const CreditHistoryLoading: Story = {
  name: '크레딧 내역 · 불러오는 중',
  render: () => <CreditHistoryScreen {...creditHistoryArgs} entries={[]} status="loading" />,
};

export const CreditHistoryError: Story = {
  name: '크레딧 내역 · 못 불러옴',
  render: () => <CreditHistoryScreen {...creditHistoryArgs} credits={104} entries={[]} status="error" />,
};

export const CreditCharge: Story = {
  name: '크레딧 충전',
  render: () => <CreditChargeScreen {...chargeArgs} credits={120} />,
};

export const CreditChargeShort: Story = {
  name: '크레딧 충전 · 영상 만들다 모자라서 들어옴',
  render: () => <CreditChargeScreen {...chargeArgs} credits={5} shortfall={7} />,
};

export const CreditChargeFailed: Story = {
  name: '크레딧 충전 · 결제 실패',
  render: () => <CreditChargeScreen {...chargeArgs} credits={5} shortfall={7} hasPaymentError />,
};

export const CreditChargePaying: Story = {
  name: '크레딧 충전 · 결제창 여는 중',
  render: () => <CreditChargeScreen {...chargeArgs} credits={120} isPaying />,
};

export const ChargeConfirming: Story = {
  name: '크레딧 충전 · 결제 확인 중',
  render: () => <ChargeResultScreen status="confirming" before={5} added={30} />,
};

export const ChargeDone: Story = {
  name: '크레딧 충전 · 완료 (영상 만들다 옴)',
  render: () => <ChargeResultScreen status="done" before={5} added={30} isResumingVideo onDone={fn()} />,
};

/** 영상 만드는 중 스토리들이 함께 쓰는 콜백 */
const generatingArgs = { productName: '실리콘 접이식 도마', onBack: fn(), onWaitAtHome: fn(), onViewVideo: fn() };

export const GeneratingQueued: Story = {
  name: '안1-7a 영상 만드는 중 · 차례 기다림',
  render: () => <GeneratingScreen {...generatingArgs} status="queued" queuePosition={2} />,
};

export const Generating: Story = {
  name: '안1-7a 영상 만드는 중',
  render: () => <GeneratingScreen {...generatingArgs} status="running" progress={34} stageIndex={0} remainingSeconds={110} />,
};

export const GeneratingAlmost: Story = {
  name: '안1-7a 영상 만드는 중 · 거의 다 됨',
  render: () => <GeneratingScreen {...generatingArgs} status="running" progress={92} stageIndex={2} remainingSeconds={10} />,
};

export const GeneratingNoProgress: Story = {
  name: '안1-7a 영상 만드는 중 · 진행률 모를 때',
  render: () => <GeneratingScreen {...generatingArgs} status="running" stageIndex={1} />,
};

export const GeneratingFailed: Story = {
  name: '안1-7a 영상 만들기 실패 · 일시적 오류',
  render: () => (
    <GeneratingScreen
      {...generatingArgs}
      status="failed"
      stageIndex={1}
      refundedCredits={12}
      credits={105}
      retryCost={12}
      onRetry={fn()}
      onContact={fn()}
    />
  ),
};

export const GeneratingFailedVideo: Story = {
  name: '안1-7a 영상 만들기 실패 · 영상 문제',
  render: () => (
    <GeneratingScreen
      {...generatingArgs}
      status="failed"
      stageIndex={0}
      failure={{ kind: 'video', detail: '영상이 5초보다 짧아요. 조금만 더 길게 찍어 주세요.' }}
      refundedCredits={12}
      credits={105}
      onReupload={fn()}
      onReviewGuide={fn()}
      onContact={fn()}
    />
  ),
};

export const GeneratingDone: Story = {
  name: '안1-7a 영상 만드는 중 · 다 됨',
  render: () => <GeneratingScreen {...generatingArgs} status="done" />,
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
  name: '안1-9 썸네일·내려받기 · 탐색 올리기 동의',
  render: () => <ThumbnailDownloadScreen {...thumbnailArgs} initialIsConfirmingPublish />,
};

export const ThumbnailDownloadPublic: Story = {
  name: '안1-9 썸네일·내려받기 · 탐색 공개 중',
  render: () => <ThumbnailDownloadScreen {...thumbnailArgs} initialIsPublic />,
};
