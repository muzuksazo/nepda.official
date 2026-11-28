import { useEffect, useRef, useState } from 'react';
import type { Meta, StoryObj } from '@storybook/react-vite';
import type { ThemeSetting } from '../NapdaProvider';
import { withDeviceFrame } from '../storybook/DeviceFrame';
import { setStorybookTheme } from '../storybook/themeGlobal';
import { sampleShare } from '../storybook/sampleShare';
import { useSampleComments } from '../storybook/useSampleComments';
import type { NavTab } from '../components';
import { ChargeResultScreen } from './ChargeResultScreen';
import { CommunityScreen } from './CommunityScreen';
import { CommunityViewerScreen } from './CommunityViewerScreen';
import { CreatorProfileScreen } from './CreatorProfileScreen';
import { CreditChargeScreen } from './CreditChargeScreen';
import { CreditHistoryScreen, type CreditEntry } from './CreditHistoryScreen';
import { GeneratingScreen } from './GeneratingScreen';
import { HomeScreen } from './HomeScreen';
import { HookTypeScreen } from './HookTypeScreen';
import { LoginScreen } from './LoginScreen';
import { NicknameScreen } from './NicknameScreen';
import { NotificationsScreen, type AppNotification } from './NotificationsScreen';
import type { HookType } from './flowData';
import { OnboardingScreen } from './OnboardingScreen';
import { ProductInfoScreen } from './ProductInfoScreen';
import { ProfileScreen } from './ProfileScreen';
import { MyVideosScreen, type MyVideosTab } from './MyVideosScreen';
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

type Step =
  | 'onboarding'
  | 'login'
  | 'nickname'
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
  | 'generating'
  | 'review'
  | 'thumbnail'
  | 'charge'
  | 'chargeResult'
  | 'notifications'
  | 'creditHistory'
  | 'creator';

/** 충전 화면으로 들어온 곳 (충전이 끝나면 여기로 돌아간다) */
type ChargeFrom = 'home' | 'profile' | 'upload' | 'creditHistory';

/** 흐름은 예시 내역에서 마지막 충전(100)을 빼고 시작한다 → 잔액이 적어 첫 영상에서 "모자람 → 충전"을 따라가 볼 수 있다 */
const FLOW_START_LEDGER = SAMPLE_CREDIT_HISTORY.slice(1);

/** 버튼을 눌러 온보딩 → 홈 → 8단계 흐름을 끝까지 따라가 보는 클릭 프로토타입 */
function FlowPrototype({ themeMode }: { themeMode: ThemeSetting }) {
  const [step, setStep] = useState<Step>('onboarding');
  const [myTab, setMyTab] = useState<MyVideosTab>('inProgress');
  const [hookType, setHookType] = useState<HookType>('B');
  const [productName, setProductName] = useState('[제품 이름]');
  const [communityType, setCommunityType] = useState<HookType | null>(null);
  const [viewerId, setViewerId] = useState<string>();
  // 영상 보기에서 뒤로 가면 돌아갈 곳 (홈 피드 · 커뮤니티)
  const [viewerFrom, setViewerFrom] = useState<'home' | 'community' | 'creator'>('community');
  // 만든 사람 프로필: 누구의 프로필인지와, 뒤로 가면 돌아갈 곳 (영상 보기에서 왔으면 그때 보던 영상으로)
  const [creatorName, setCreatorName] = useState('도마왕');
  const [creatorReturn, setCreatorReturn] = useState<
    { step: 'home' } | { step: 'communityViewer'; viewerFrom: 'home' | 'community'; viewerId?: string }
  >({ step: 'home' });
  const [feedCount, setFeedCount] = useState(4);
  const commentProps = useSampleComments(SAMPLE_COMMENTS, SAMPLE_USER.name);
  const communityItems = filterCommunityByType(SAMPLE_COMMUNITY, communityType);
  // 크레딧: 영상 한 편에 SAMPLE_CREDITS_PER_VIDEO씩 쓴다.
  // 잔액을 일부러 적게 잡아 첫 영상에서 "모자람 → 충전 → 다시 만들기"를 따라가 볼 수 있다
  const [credits, setCredits] = useState(FLOW_START_LEDGER[0].balance);
  // 크레딧 내역: 충전 · 영상 만들기 · 실패해서 돌려받기가 일어날 때마다 맨 위에 한 줄씩 쌓인다
  const [ledger, setLedger] = useState<CreditEntry[]>(FLOW_START_LEDGER);
  const addLedger = (entry: Omit<CreditEntry, 'id' | 'balance' | 'createdAt'>) =>
    setLedger((prev) => [
      { ...entry, id: `flow-${prev.length}`, balance: (prev[0]?.balance ?? 0) + entry.amount, createdAt: new Date().toISOString() },
      ...prev,
    ]);
  const [historyFrom, setHistoryFrom] = useState<'profile' | 'notifications'>('profile');
  const [uploadFiles, setUploadFiles] = useState<File[]>([]);
  const [isSigningIn, setIsSigningIn] = useState(false);
  // 처음 로그인하면 가입(약관 → 닉네임)을 거치고, 로그아웃 뒤 다시 들어오면 바로 홈으로 간다
  const [isMember, setIsMember] = useState(false);
  const [isTermsOpen, setIsTermsOpen] = useState(false);
  const [nicknameState, setNicknameState] = useState<'idle' | 'checking' | 'available' | 'taken'>('available');
  const nicknameTimer = useRef<number | undefined>(undefined);
  const [notifications, setNotifications] = useState<AppNotification[]>(SAMPLE_NOTIFICATIONS);
  // 영상 만들기 잡 흉내: 잠깐 차례를 기다린 뒤 0→100%. 다른 화면에 가 있어도 계속 돌고, 끝나면 알림이 온다
  // 두 번째로 만드는 영상은 "본편에 이어 붙이기"에서 일부러 실패시켜 실패 화면 → 크레딧 환불까지 따라가 볼 수 있다
  const [job, setJob] = useState<{
    status: 'queued' | 'running' | 'done' | 'failed';
    progress: number;
    willFail?: boolean;
    productName?: string;
  } | null>(null);
  const jobCount = useRef(0);
  const jobStatus = job?.status;
  const jobRef = useRef(job);
  useEffect(() => {
    jobRef.current = job;
  });
  useEffect(() => {
    if (!jobStatus || jobStatus === 'done' || jobStatus === 'failed') return;
    const timer = window.setInterval(() => {
      const prev = jobRef.current;
      if (!prev) return;
      let next: NonNullable<typeof prev>;
      if (prev.status === 'queued') next = { ...prev, status: 'running', progress: 0 };
      else {
        const progress = Math.min(100, prev.progress + 3);
        if (prev.willFail && progress >= 66) next = { ...prev, status: 'failed', progress };
        else next = progress >= 100 ? { ...prev, status: 'done', progress: 100 } : { ...prev, progress };
      }
      jobRef.current = next;
      setJob(next);
      // 실패하면 쓴 크레딧을 바로 돌려준다
      if (next.status === 'failed') {
        setCredits((value) => value + SAMPLE_CREDITS_PER_VIDEO);
        addLedger({ kind: 'refund', amount: SAMPLE_CREDITS_PER_VIDEO, productName: next.productName });
      }
    }, 300);
    return () => window.clearInterval(timer);
  }, [jobStatus]);
  const startJob = () => {
    jobCount.current += 1;
    setCredits((value) => value - SAMPLE_CREDITS_PER_VIDEO);
    addLedger({ kind: 'use', amount: -SAMPLE_CREDITS_PER_VIDEO, productName });
    setJob({ status: 'queued', progress: 0, willFail: jobCount.current === 2, productName });
    setStep('generating');
  };
  // 잡이 끝난 순간 사용자가 어느 화면에 있는지 (만드는 중 화면을 보고 있으면 알림을 보내지 않는다)
  const stepRef = useRef(step);
  useEffect(() => {
    stepRef.current = step;
  });
  useEffect(() => {
    if ((jobStatus !== 'done' && jobStatus !== 'failed') || stepRef.current === 'generating') return;
    const isFailed = jobStatus === 'failed';
    setNotifications((prev) => [
      {
        id: `made-${prev.length}`,
        kind: isFailed ? 'videoFailed' : 'videoReady',
        title: isFailed ? '영상을 못 만들었어요' : '영상 나왔어요!',
        body: isFailed ? `쓴 크레딧 ${SAMPLE_CREDITS_PER_VIDEO}는 돌려드렸어요. 다시 해 볼까요?` : '훅 붙여서 완성했어요. 썸네일만 고르면 끝.',
        createdAt: new Date().toISOString(),
        isRead: false,
      },
      ...prev,
    ]);
  }, [jobStatus]);
  // 알림을 누르면 읽음으로 바꾸고, 종류에 따라 그 화면으로 보낸다
  const openNotification = (target: AppNotification) => {
    setNotifications((prev) => prev.map((n) => (n.id === target.id ? { ...n, isRead: true } : n)));
    if (target.kind === 'videoReady') setStep('thumbnail');
    if (target.kind === 'videoFailed') {
      // 지금 실패한 잡이 없으면(예시 알림) 예시 실패 상태로 연다
      if (job?.status !== 'failed') setJob({ status: 'failed', progress: 66 });
      setStep('generating');
    }
    if (target.kind === 'expiring') {
      setMyTab('completed');
      setStep('myVideos');
    }
    if (target.kind === 'creditCharged') {
      setHistoryFrom('notifications');
      setStep('creditHistory');
    }
    if (target.kind === 'communityLike') {
      setViewerId(target.targetId);
      setStep('communityViewer');
    }
  };
  const [charge, setCharge] = useState<{ from: ChargeFrom; shortfall?: number; before: number; added: number; isDone: boolean }>({
    from: 'home',
    before: 0,
    added: 0,
    isDone: false,
  });
  const openCharge = (from: ChargeFrom, shortfall?: number) => {
    setCharge({ from, shortfall, before: credits, added: 0, isDone: false });
    setStep('charge');
  };
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
      return <OnboardingScreen onStart={() => setStep('login')} />;
    case 'login':
      return (
        <LoginScreen
          showcase={SAMPLE_LOGIN_SHOWCASE}
          isSigningIn={isSigningIn}
          onSignIn={() => {
            // 구글 창은 흉내만 낸다: 잠깐 "들어가는 중"을 보여 준 뒤, 처음이면 약관 시트 · 아니면 홈
            setIsSigningIn(true);
            window.setTimeout(() => {
              setIsSigningIn(false);
              if (isMember) setStep('home');
              else setIsTermsOpen(true);
            }, 1200);
          }}
          isTermsOpen={isTermsOpen}
          onAgreeTerms={() => {
            setIsTermsOpen(false);
            setStep('nickname');
          }}
          onCloseTerms={() => setIsTermsOpen(false)}
        />
      );
    case 'nickname':
      return (
        <NicknameScreen
          initialNickname={SAMPLE_USER.name}
          availability={nicknameState}
          onNicknameChange={(name) => {
            // 서버 중복 확인을 흉내: 잠깐 확인 중 → "도마왕"은 이미 있는 이름
            window.clearTimeout(nicknameTimer.current);
            setNicknameState('checking');
            nicknameTimer.current = window.setTimeout(() => setNicknameState(name === '도마왕' ? 'taken' : 'available'), 500);
          }}
          onBack={() => setStep('login')}
          onSubmit={() => {
            setIsMember(true);
            setStep('home');
          }}
        />
      );
    case 'home':
      return (
        <HomeScreen
          credits={credits}
          onCreditClick={() => openCharge('home')}
          unreadCount={notifications.filter((n) => !n.isRead).length}
          onNotificationsClick={() => setStep('notifications')}
          feed={SAMPLE_COMMUNITY.slice(0, feedCount)}
          share={sampleShare()}
          feedHasMore={feedCount < SAMPLE_COMMUNITY.length}
          onLoadMoreFeed={() => setFeedCount((value) => Math.min(SAMPLE_COMMUNITY.length, value + 4))}
          onOpenFeed={(id) => {
            setCommunityType(null);
            setViewerId(id);
            setViewerFrom('home');
            setStep('communityViewer');
          }}
          onRemixFeed={(video) => {
            setHookType(video.hookType);
            setStep('product');
          }}
          onOpenCreator={(name) => {
            setCreatorName(name);
            setCreatorReturn({ step: 'home' });
            setStep('creator');
          }}
          onSeeAllFeed={() => setStep('community')}
          {...commentProps}
          profile={{ name: SAMPLE_USER.name }}
          onProfileClick={() => setStep('profile')}
          onNavigate={navigate}
          banners={SAMPLE_BANNERS}
          inProgress={SAMPLE_IN_PROGRESS}
          completed={completed}
          onCreate={() => setStep('product')}
          onContinue={(id) => {
            // 이어 만들 제품 이름을 들고 간다 (크레딧 내역에 "어떤 영상에 썼는지"로 남는다)
            const project = SAMPLE_IN_PROGRESS.find((p) => p.id === id);
            if (project) setProductName(project.productName);
            setStep('upload');
          }}
          onDownloadAgain={() => setStep('thumbnail')}
          onSeeAllMyVideos={() => {
            setMyTab('inProgress');
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
            setViewerFrom('community');
            setStep('communityViewer');
          }}
          onCreate={() => setStep('product')}
          onNavigate={navigate}
        />
      );
    case 'communityViewer':
      return (
        <CommunityViewerScreen
          {...commentProps}
          myName={SAMPLE_USER.name}
          items={viewerFrom === 'creator' ? sampleCreator(creatorName).videos : communityItems}
          initialId={viewerId}
          share={sampleShare()}
          onBack={() => setStep(viewerFrom)}
          onActiveChange={setViewerId}
          onOpenCreator={(name) => {
            // 프로필에서 열어 본 영상이면 같은 사람이라 그냥 프로필로 돌아간다
            if (viewerFrom !== 'creator') {
              setCreatorName(name);
              setCreatorReturn({ step: 'communityViewer', viewerFrom, viewerId });
            }
            setStep('creator');
          }}
          // "이 훅으로 만들기": 같은 훅 유형을 고른 채로 만들기 흐름을 시작한다
          onRemix={(video) => {
            setHookType(video.hookType);
            setStep('product');
          }}
        />
      );
    case 'creator': {
      const { profile, videos } = sampleCreator(creatorName);
      return (
        <CreatorProfileScreen
          creator={profile}
          videos={videos}
          onBack={() => {
            if (creatorReturn.step === 'communityViewer') {
              setViewerFrom(creatorReturn.viewerFrom);
              setViewerId(creatorReturn.viewerId);
            }
            setStep(creatorReturn.step);
          }}
          onOpenVideo={(id) => {
            setViewerId(id);
            setViewerFrom('creator');
            setStep('communityViewer');
          }}
          onRemix={(type) => {
            setHookType(type);
            setStep('product');
          }}
        />
      );
    }
    case 'profile':
      return (
        <ProfileScreen
          user={SAMPLE_USER}
          credits={credits}
          onChargeClick={() => openCharge('profile')}
          onCreditHistoryClick={() => {
            setHistoryFrom('profile');
            setStep('creditHistory');
          }}
          videoCounts={{ inProgress: SAMPLE_IN_PROGRESS.length, completed: completed.length }}
          retentionDays={7}
          themeMode={themeMode}
          onThemeModeChange={setStorybookTheme}
          onNavigate={navigate}
          onOpenMyVideos={(tab) => {
            setMyTab(tab);
            setStep('myVideos');
          }}
          onLogout={() => setStep('login')}
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
          scenario={'[예시 훅 시나리오]\n1. 시선을 끄는 첫 장면 (3초)\n2. 제품 핵심 장점을 한눈에 보여 주기 (5초)'}
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
          initialFiles={uploadFiles}
          cost={SAMPLE_CREDITS_PER_VIDEO}
          credits={credits}
          onBack={() => setStep('guide')}
          onReviewGuide={() => setStep('guide')}
          onCreate={() => {
            setUploadFiles([]);
            startJob();
          }}
          onCharge={(files, shortfall) => {
            // 충전하고 돌아오면 고른 영상이 그대로 남아 있게 들고 간다
            setUploadFiles(files);
            openCharge('upload', shortfall);
          }}
        />
      );
    case 'charge':
      return (
        <CreditChargeScreen
          credits={credits}
          packages={SAMPLE_CREDIT_PACKAGES}
          creditsPerVideo={SAMPLE_CREDITS_PER_VIDEO}
          shortfall={charge.shortfall}
          onBack={() => setStep(charge.from)}
          onPay={(pkg) => {
            // 결제창은 흉내만 낸다: 잠깐 "결제 확인 중"을 보여 준 뒤 잔액에 넣는다
            setCharge((prev) => ({ ...prev, before: credits, added: pkg.credits, isDone: false }));
            setStep('chargeResult');
            window.setTimeout(() => {
              setCredits((value) => value + pkg.credits);
              addLedger({ kind: 'charge', amount: pkg.credits, price: pkg.price });
              setCharge((prev) => ({ ...prev, isDone: true }));
            }, 1500);
          }}
        />
      );
    case 'notifications':
      return (
        <NotificationsScreen
          items={notifications}
          now={SAMPLE_NOW}
          onBack={() => setStep('home')}
          onOpen={openNotification}
          onMarkAllRead={() => setNotifications((prev) => prev.map((n) => ({ ...n, isRead: true })))}
        />
      );
    case 'creditHistory':
      return (
        <CreditHistoryScreen
          credits={credits}
          entries={ledger}
          expiring={SAMPLE_CREDIT_EXPIRING}
          onBack={() => setStep(historyFrom)}
          onCharge={() => openCharge('creditHistory')}
        />
      );
    case 'chargeResult':
      return (
        <ChargeResultScreen
          status={charge.isDone ? 'done' : 'confirming'}
          before={charge.before}
          added={charge.added}
          isResumingVideo={charge.from === 'upload'}
          onDone={() => setStep(charge.from)}
        />
      );
    case 'generating':
      return (
        <GeneratingScreen
          status={job?.status ?? 'done'}
          queuePosition={1}
          progress={job?.status === 'running' ? job.progress : undefined}
          stageIndex={job && job.progress >= 85 ? 2 : job && job.progress >= 55 ? 1 : 0}
          remainingSeconds={job ? Math.round(((100 - job.progress) / 100) * 150) : undefined}
          productName={productName}
          refundedCredits={job?.status === 'failed' ? SAMPLE_CREDITS_PER_VIDEO : undefined}
          credits={credits}
          retryCost={SAMPLE_CREDITS_PER_VIDEO}
          onBack={() => setStep('home')}
          onWaitAtHome={() => setStep('home')}
          onViewVideo={() => {
            setJob(null);
            setStep('review');
          }}
          onRetry={() => {
            // 크레딧이 모자라면 충전부터
            if (credits < SAMPLE_CREDITS_PER_VIDEO) openCharge('upload', SAMPLE_CREDITS_PER_VIDEO - credits);
            else startJob();
          }}
          onReupload={() => setStep('upload')}
          onReviewGuide={() => setStep('guide')}
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
