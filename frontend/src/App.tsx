import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useCallback, useEffect, useMemo, useRef, useState, useSyncExternalStore } from 'react';
import { AdminUsagePage } from './admin/AdminUsagePage';
import { readScenarioAbOverride } from './api/abConfig';
import { customFetch, NapdaApiError } from './api/mutator';
import {
  getBillingOrderV1BillingOrdersOrderIdGet,
  getGetWalletV1BillingWalletGetQueryKey,
  useCreateBillingCheckoutV1BillingCheckoutPost,
  useGetBillingConfigV1BillingConfigGet,
  useGetWalletV1BillingWalletGet,
} from './api/generated/billing/billing';
import { presignUploadV1UploadsPresignPost } from './api/generated/default/default';
import { getDeliverablesV1ProjectsProjectIdDeliverablesGet } from './api/generated/delivery/delivery';
import { createFilmingGuideV1ProjectsProjectIdFilmingGuidePost } from './api/generated/filming-guide/filming-guide';
import { createRenderV1ProjectsProjectIdRendersPost } from './api/generated/generation/generation';
import {
  generateScenariosV1ProjectsProjectIdScenariosPost,
  generateStoryboardV1ProjectsProjectIdScenariosScenarioIdStoryboardPost,
  selectScenarioV1ProjectsProjectIdScenariosScenarioIdSelectPost,
} from './api/generated/planning/planning';
import {
  createProjectV1ProjectsPost,
  getListProjectsV1ProjectsGetQueryKey,
  getProjectV1ProjectsProjectIdGet,
  useListProjectsV1ProjectsGet,
} from './api/generated/projects/projects';
import { completeUploadsV1ProjectsProjectIdUploadsCompletePost } from './api/generated/uploads/uploads';
import {
  CreateProjectRequestFlowMode,
  ProductInputCategory,
  type CreateCheckoutRequestPackageId,
  type CreateRenderRequestSelectedType,
  type DeliverablesResponse,
  type GenerateScenariosRequest,
  type ProjectSummary,
  type ProjectSummaryStatus,
  type ScenarioItem,
} from './api/generated/model';
import { GoogleSignInButton, useAuth } from './auth';
import { openPaddleCheckout } from './billing';
import { NapdaProvider, type ThemeSetting } from './ui/NapdaProvider';
import {
  formatThumbnailHeadline,
  InfoSheet,
  type AgreementDoc,
  type BannerItem,
  type CreditPackage,
  type NavTab,
  type ShareHandlers,
  type VideoComment,
} from './ui/components';
import event5 from './assets/events/event5.webp';
import event2 from './assets/events/event2.webp';
import event3 from './assets/events/event3.webp';
import showcase01 from './assets/samples/community/thumb-01.webp';
import showcase02 from './assets/samples/community/thumb-02.webp';
import showcase03 from './assets/samples/community/thumb-03.webp';
import {
  ChargeResultScreen,
  CommunityScreen,
  CommunityViewerScreen,
  CreatorProfileScreen,
  CreditChargeScreen,
  CreditHistoryScreen,
  GeneratingScreen,
  HomeScreen,
  HookTypeScreen,
  LoginScreen,
  MyVideosScreen,
  NicknameScreen,
  NotificationsScreen,
  OnboardingScreen,
  ProductInfoScreen,
  ProfileScreen,
  ScenarioScreen,
  ShootingGuideScreen,
  SplashScreen,
  StoryboardScreen,
  ThumbnailDownloadScreen,
  UploadVideoScreen,
  VideoReviewScreen,
  type AppNotification,
  type CommunityVideo,
  type CompletedProject,
  type CreatorProfile,
  type CreditEntry,
  type HookType,
  type InProgressProject,
  type MyVideosTab,
  type NicknameScreenProps,
  type ProductInfo,
  type ProfileDoc,
} from './ui/screens';
import type { GuideScene } from './ui/screens/ShootingGuideScreen';
import type { StoryboardScene } from './ui/screens/StoryboardScreen';
import { exportThumbnailPng } from './ui/thumbnails/exportThumbnailPng';
import type { ThumbnailVariant } from './ui/thumbnails/presets';

const DARK_QUERY = '(prefers-color-scheme: dark)';
const SUPPORT_EMAIL = 'dudnjsckrgo@gmail.com';
const DEFAULT_AI_DISCLOSURE_GUIDE = "인스타그램 게시 시 'AI 정보' 라벨 활성화를 권장합니다.";
const DEFAULT_CREDITS_PER_VIDEO = 12;
const DEFAULT_CREDIT_PACKAGES: readonly CreditPackage[] = [
  { id: 'c30', credits: 30, price: 4900 },
  { id: 'c100', credits: 100, price: 12900, isPopular: true },
  { id: 'c300', credits: 300, price: 33000 },
];
const COMMUNITY_VIDEOS_QUERY_KEY = ['community', 'videos'] as const;
const HOME_BANNERS: BannerItem[] = [
  { id: 'b1', imageUrl: event5, alt: '블랙 프라이데이' },
  {
    id: 'b2',
    imageUrl: event3,
    alt: '냅다 광고 뽑기 이벤트. 오늘은 또 무슨 광고가 나올까? 랜덤 미션에 도전하고 크레딧을 받아보세요! 이벤트 참여하기',
  },
  {
    id: 'b3',
    imageUrl: event2,
    alt: '미친 광고 공모전. 세상에서 가장 어이없는 광고에 도전하세요! 지금 바로 참여하기',
  },
];
const LOGIN_FALLBACK_SHOWCASE = [showcase02, showcase01, showcase03] as const;

function mapCommunityVideos(
  raw: CommunityVideoApiItem[],
  likedOverrides: Record<string, boolean>,
): CommunityVideo[] {
  return raw.map((item) => {
    const isLiked = likedOverrides[item.id] ?? false;
    return {
      id: item.id,
      productName: item.product_name,
      creatorName: item.creator_name || '냅다사장',
      hookType: (item.hook_type === 'A' || item.hook_type === 'B' || item.hook_type === 'C'
        ? item.hook_type
        : 'A') as HookType,
      thumbnailUrl: item.thumbnail_url ?? undefined,
      videoUrl: item.video_url ?? undefined,
      caption: item.caption || item.title || item.product_name,
      likeCount: (item.like_count ?? 0) + (isLiked ? 1 : 0),
      isLiked,
    };
  });
}

function normalizeFigmaVariant(id: string | null | undefined): ThumbnailVariant {
  if (id === 'invert-box' || id === 'white-label' || id === 'serif-outline' || id === 'pov-bar') {
    return id;
  }
  if (id === 'stroke_bold' || id === 'stroke') return 'serif-outline';
  if (id === 'line_blocks' || id === 'blocks') return 'white-label';
  if (id === 'panel_card' || id === 'card') return 'invert-box';
  if (id === 'split') return 'pov-bar';
  return 'invert-box';
}

interface DeliverableThumbnailState {
  imageUrl?: string;
  downloadUrl?: string;
  style: ThumbnailVariant;
  highlightWord?: string;
  badge?: string;
  candidateImageUrls: string[];
  candidateKeys: string[];
}

interface CommunityVideoApiItem {
  id: string;
  project_id: string;
  hook_type: string;
  title: string;
  caption: string;
  product_name: string;
  creator_name: string;
  thumbnail_url: string | null;
  video_url: string | null;
  like_count: number;
  created_at: string;
}

function buildCreatorProfile(
  name: string,
  allVideos: CommunityVideo[],
): { profile: CreatorProfile; videos: CommunityVideo[] } {
  const videos = allVideos.filter((v) => v.creatorName === name);
  const counts = new Map<HookType, number>();
  for (const v of videos) {
    counts.set(v.hookType, (counts.get(v.hookType) ?? 0) + 1);
  }
  const mainHookType = [...counts.entries()].sort((a, b) => b[1] - a[1])[0]?.[0];
  return {
    profile: {
      name,
      videoCount: videos.length,
      likeCount: videos.reduce((sum, v) => sum + v.likeCount, 0),
      mainHookType,
    },
    videos,
  };
}

interface InfoSheetState {
  title: string;
  description: string;
  actionLabel?: string;
  onAction?: () => void;
}

function subscribeSystemDark(onChange: () => void) {
  const query = window.matchMedia(DARK_QUERY);
  query.addEventListener('change', onChange);
  return () => query.removeEventListener('change', onChange);
}

const getSystemDark = () => window.matchMedia(DARK_QUERY).matches;
const getServerSystemDark = () => false;

const COMPLETED_STATUSES = new Set<ProjectSummaryStatus>([
  'HOOK_READY',
  'DELIVERABLE_READY',
]);

const PROGRESS_COPY: Record<
  Exclude<ProjectSummaryStatus, 'HOOK_READY' | 'DELIVERABLE_READY'>,
  { completedSteps: number; status: string; nextStep: string }
> = {
  PRODUCT_SAVED: { completedSteps: 1, status: '제품 정보를 저장했어요', nextStep: '훅 유형 고르기' },
  SCENARIOS_READY: { completedSteps: 3, status: '시나리오 글을 확인하고 있어요', nextStep: '촬영 가이드 받기' },
  STORYBOARD_READY: { completedSteps: 4, status: '그림 콘티를 확인했어요', nextStep: '촬영 가이드 받기' },
  GUIDE_READY: { completedSteps: 5, status: '촬영 가이드를 받았어요', nextStep: '찍은 영상 올리기' },
  UPLOADS_READY: { completedSteps: 6, status: '영상을 올렸어요', nextStep: '영상 만들기' },
  HOOK_RENDERING: { completedSteps: 7, status: '훅 영상을 만들고 있어요', nextStep: '잠시 후 확인하기' },
  RENDERING: { completedSteps: 7, status: '영상을 만들고 있어요', nextStep: '잠시 후 확인하기' },
  FAILED: { completedSteps: 6, status: '생성에 실패했어요', nextStep: '다시 시도하기' },
};

/** 스플래시를 보여 주는 최소 시간 */
const SPLASH_MIN_MS = 1200;

function splitProjects(projects: ProjectSummary[]): {
  inProgress: InProgressProject[];
  completed: CompletedProject[];
} {
  const inProgress: InProgressProject[] = [];
  const completed: CompletedProject[] = [];

  for (const project of projects) {
    const thumbnailUrl = project.thumbnail_url ?? undefined;
    if (COMPLETED_STATUSES.has(project.status)) {
      completed.push({
        id: project.project_id,
        productName: project.product_name,
        status: '영상과 썸네일을 만들었어요',
        thumbnailUrl,
      });
    } else {
      const meta = PROGRESS_COPY[project.status as keyof typeof PROGRESS_COPY] ?? {
        completedSteps: 1,
        status: '작업 중이에요',
        nextStep: '이어하기',
      };
      inProgress.push({
        id: project.project_id,
        productName: project.product_name,
        status: meta.status,
        completedSteps: meta.completedSteps,
        nextStep: meta.nextStep,
        thumbnailUrl,
      });
    }
  }

  return { inProgress, completed };
}

function mapCategoryToApi(category: string | null): ProductInputCategory {
  if (category === '주방') return ProductInputCategory.kitchen;
  if (category === '문구') return ProductInputCategory.stationery;
  return ProductInputCategory.living;
}

function parseFactsFromIntro(name: string, intro: string): string[] {
  const raw = intro
    .split(/[\n.,!?]+/)
    .map((s) => s.trim())
    .filter(Boolean);
  if (raw.length > 0) return raw.slice(0, 10);
  return [`${name.trim()} 핵심 특징`];
}

function formatScenarioText(scn: ScenarioItem): string {
  const lines = scn.beats.map((b) => {
    const body = (b.caption || b.narration || b.visual || '')
      .replace(/\\n|\n/g, ' ')
      .replace(/\*\*/g, '')
      .trim();
    return `${b.order}. ${body} (${b.duration_sec}초)`;
  });
  return [`[${scn.hook_title}]`, ...lines].join('\n');
}

function triggerFileDownload(url: string, filename: string): void {
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.rel = 'noopener';
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
}

function buildShareHandlers(): ShareHandlers {
  const shareUrlOf = (id: string) => `${window.location.origin}/v/${id}`;
  return {
    shareUrlOf,
    canShareNative: typeof navigator !== 'undefined' && typeof navigator.share === 'function',
    onShareNative: (id) => {
      navigator.share?.({ title: '냅다로 만든 릴스 광고', url: shareUrlOf(id) }).catch(() => undefined);
    },
    onCopyLink: (id) => {
      navigator.clipboard?.writeText(shareUrlOf(id)).catch(() => undefined);
    },
  };
}

function getStorageFlag(key: string): string | null {
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
}

function setStorageFlag(key: string, value: string): void {
  try {
    window.localStorage.setItem(key, value);
  } catch {
    // Ignore storage quota errors in restricted browsers.
  }
}

type ChargeFrom = 'home' | 'profile' | 'upload' | 'creditHistory';
type CreationStep =
  | 'product'
  | 'hook'
  | 'scenario'
  | 'storyboard'
  | 'guide'
  | 'upload'
  | 'generating'
  | 'review'
  | 'thumbnail';

type OverlayScreen =
  | { type: 'notifications' }
  | { type: 'creditHistory'; from: 'profile' | 'notifications' }
  | {
      type: 'communityViewer';
      from: 'home' | 'community' | 'creator';
      videoId?: string;
      creatorName?: string;
    }
  | {
      type: 'creator';
      name: string;
      returnTo:
        | { type: 'home' }
        | { type: 'communityViewer'; from: 'home' | 'community'; videoId?: string };
    };

interface ChargeFlowState {
  stage: 'charge' | 'confirming' | 'done';
  from: ChargeFrom;
  shortfall?: number;
  before: number;
  added: number;
  isPaying: boolean;
  hasPaymentError: boolean;
}

/** 렌더 완료를 묻는 시간: 처음 5분은 자주, 30분이 지나면 묻기를 멈춘다 (pollRenderCompletion) */
const RENDER_POLL_FAST_MS = 5 * 60 * 1000;
const RENDER_POLL_LIMIT_MS = 30 * 60 * 1000;

interface GeneratingJobState {
  status: 'queued' | 'running' | 'done' | 'failed' | 'canceled';
  progress: number;
  stageIndex: number;
  remainingSeconds?: number;
  failure?: { kind: 'temporary' | 'video'; detail?: string };
  refundedCredits?: number;
}

export function App() {
  const auth = useAuth();
  // 스플래시는 앱을 처음 열 때 로그인 확인이 끝나고도 최소 1.2초는 보여 준다 (그림이 번쩍하고 사라지지 않게)
  const [isSplashMinDone, setIsSplashMinDone] = useState(false);
  useEffect(() => {
    const timer = window.setTimeout(() => setIsSplashMinDone(true), SPLASH_MIN_MS);
    return () => window.clearTimeout(timer);
  }, []);
  const queryClient = useQueryClient();
  const [themeMode, setThemeMode] = useState<ThemeSetting>('system');
  const [activeTab, setActiveTab] = useState<NavTab>('home');
  const [myTab, setMyTab] = useState<MyVideosTab>('inProgress');
  const [communityHookType, setCommunityHookType] = useState<HookType | null>(null);
  const [chargeState, setChargeState] = useState<ChargeFlowState | null>(null);
  const [overlayScreen, setOverlayScreen] = useState<OverlayScreen | null>(null);
  const [infoSheet, setInfoSheet] = useState<InfoSheetState | null>(null);

  // Onboarding / Login / Signup flow
  const [authEntryStep, setAuthEntryStep] = useState<'onboarding' | 'login'>('onboarding');
  const [termsAgreed, setTermsAgreed] = useState(false);
  const [nicknameStatus, setNicknameStatus] =
    useState<NicknameScreenProps['availability']>('available');
  const [nicknameOverrides, setNicknameOverrides] = useState<Record<string, string>>({});
  const [onboardedUsers, setOnboardedUsers] = useState<Record<string, boolean>>({});
  const nicknameTimerRef = useRef<number | undefined>(undefined);

  // Notifications / Credit ledger / Community comments & feed likes
  const [commentsByVideo, setCommentsByVideo] = useState<Record<string, VideoComment[]>>({});
  const [likedVideoIds, setLikedVideoIds] = useState<Record<string, boolean>>({});
  const [homeFeedCount, setHomeFeedCount] = useState(4);
  const [notifications, setNotifications] = useState<AppNotification[]>([]);
  const [creditLedger, setCreditLedger] = useState<CreditEntry[]>([]);
  const [publicProjectIds, setPublicProjectIds] = useState<Record<string, boolean>>({});
  const [publishedCaption, setPublishedCaption] = useState<string>('');

  // 8-step creation flow state
  const [creationStep, setCreationStep] = useState<CreationStep | null>(null);
  const creationStepRef = useRef<CreationStep | null>(null);
  const [projectId, setProjectId] = useState<string | null>(null);
  const [productInfo, setProductInfo] = useState<Partial<ProductInfo>>({});
  const [hookType, setHookType] = useState<HookType>('A');
  const [skippedDrafts, setSkippedDrafts] = useState(false);
  const [scenarioId, setScenarioId] = useState<string | null>(null);
  const [scenarioText, setScenarioText] = useState<string | undefined>(undefined);
  const [storyboardScenes, setStoryboardScenes] = useState<StoryboardScene[] | undefined>(undefined);
  const [storyboardLoading, setStoryboardLoading] = useState(false);
  const [storyboardError, setStoryboardError] = useState<string | null>(null);
  const [guideScenes, setGuideScenes] = useState<GuideScene[] | undefined>(undefined);
  const [uploadFiles, setUploadFiles] = useState<File[]>([]);
  const [videoUrl, setVideoUrl] = useState<string | undefined>(undefined);
  const [videoDownloadUrl, setVideoDownloadUrl] = useState<string | undefined>(undefined);
  const [deliverableThumb, setDeliverableThumb] = useState<DeliverableThumbnailState | null>(null);
  const [aiDisclosureGuide, setAiDisclosureGuide] = useState<string | undefined>(undefined);
  const [isDownloadingThumb, setIsDownloadingThumb] = useState(false);
  const [thumbError, setThumbError] = useState<string | null>(null);
  const [genJob, setGenJob] = useState<GeneratingJobState | null>(null);
  const [isCancelingRender, setIsCancelingRender] = useState(false);

  const pollCancelRef = useRef<(() => void) | null>(null);
  const renderPollCancelRef = useRef<(() => void) | null>(null);
  const renderAbortRef = useRef<AbortController | null>(null);
  const activeRenderJobIdRef = useRef<string | null>(null);
  const commentSeqRef = useRef(0);
  const notifSeqRef = useRef(0);
  const ledgerSeqRef = useRef(0);

  useEffect(() => {
    creationStepRef.current = creationStep;
  }, [creationStep]);

  useEffect(() => {
    return () => {
      pollCancelRef.current?.();
      renderPollCancelRef.current?.();
      renderAbortRef.current?.abort();
      if (nicknameTimerRef.current) {
        window.clearTimeout(nicknameTimerRef.current);
      }
    };
  }, []);

  const isSystemDark = useSyncExternalStore(
    subscribeSystemDark,
    getSystemDark,
    getServerSystemDark,
  );
  const isDark = themeMode === 'dark' || (themeMode === 'system' && isSystemDark);
  const gisTheme = isDark ? 'filled_black' : 'outline';

  const projectsQuery = useListProjectsV1ProjectsGet(undefined, {
    query: {
      enabled: auth.status === 'authenticated',
      retry: false,
    },
  });

  const homeFeedQuery = useQuery({
    queryKey: [...COMMUNITY_VIDEOS_QUERY_KEY, 'home'],
    queryFn: async () => {
      const res = await customFetch<{
        status: number;
        data: { items: CommunityVideoApiItem[] };
      }>('/v1/community/videos?limit=50');
      return res.data.items;
    },
    retry: false,
  });

  const communityQuery = useQuery({
    queryKey: [...COMMUNITY_VIDEOS_QUERY_KEY, communityHookType ?? 'all'],
    queryFn: async () => {
      const qs = communityHookType
        ? `?hook_type=${encodeURIComponent(communityHookType)}&limit=50`
        : '?limit=50';
      const res = await customFetch<{
        status: number;
        data: { items: CommunityVideoApiItem[] };
      }>(`/v1/community/videos${qs}`);
      return res.data.items;
    },
    enabled: auth.status === 'authenticated',
    retry: false,
  });

  const billingConfigQuery = useGetBillingConfigV1BillingConfigGet({
    query: {
      retry: false,
      staleTime: 60_000,
    },
  });

  const walletQuery = useGetWalletV1BillingWalletGet({
    query: {
      enabled: auth.status === 'authenticated',
      retry: false,
    },
  });

  const checkoutMutation = useCreateBillingCheckoutV1BillingCheckoutPost();

  const billingConfig =
    billingConfigQuery.data?.status === 200 ? billingConfigQuery.data.data : undefined;
  const wallet = walletQuery.data?.status === 200 ? walletQuery.data.data : undefined;
  const walletCredits = wallet?.credits ?? 0;
  const isInternalAccount = Boolean(wallet?.is_internal);
  const creditsPerVideo = billingConfig?.credits_per_video ?? DEFAULT_CREDITS_PER_VIDEO;

  const creditPackages = useMemo<CreditPackage[]>(() => {
    if (!billingConfig?.packages?.length) {
      return [...DEFAULT_CREDIT_PACKAGES];
    }
    return billingConfig.packages.map((p) => ({
      id: p.id,
      credits: p.credits,
      price: p.price,
      isPopular: Boolean(p.is_popular),
    }));
  }, [billingConfig]);

  const homeFeedVideos = useMemo<CommunityVideo[]>(
    () => mapCommunityVideos(homeFeedQuery.data ?? [], likedVideoIds),
    [homeFeedQuery.data, likedVideoIds],
  );

  const communityVideos = useMemo<CommunityVideo[]>(
    () => mapCommunityVideos(communityQuery.data ?? [], likedVideoIds),
    [communityQuery.data, likedVideoIds],
  );

  const loginShowcase = useMemo<readonly string[]>(() => {
    const liveThumbs = homeFeedVideos
      .map((v) => v.thumbnailUrl)
      .filter((u): u is string => Boolean(u))
      .slice(0, 3);
    if (liveThumbs.length >= 3) return liveThumbs;
    return [
      ...liveThumbs,
      ...LOGIN_FALLBACK_SHOWCASE.slice(0, 3 - liveThumbs.length),
    ];
  }, [homeFeedVideos]);

  const shareHandlers = useMemo<ShareHandlers>(() => buildShareHandlers(), []);

  const openInfoDocument = useCallback(
    (doc: ProfileDoc | AgreementDoc) => {
      if (doc === 'privacy') {
        const opened = window.open('/privacy.html', '_blank');
        if (opened) {
          opened.opener = null;
        } else {
          window.location.assign('/privacy.html');
        }
        return;
      }
      if (doc === 'terms') {
        setInfoSheet({
          title: '이용약관',
          description: [
            '• 냅다(NAPDA)는 입력한 제품 정보와 촬영 영상을 바탕으로 숏폼 광고 훅 영상과 썸네일을 제작하는 서비스입니다.',
            '• 완성된 영상과 썸네일은 생성일로부터 7일간 보관되며, 기간이 지나면 자동으로 삭제됩니다.',
            '• 결제한 크레딧은 영상 제작 완료 시 차감되며, 시스템 오류로 제작에 실패한 경우 자동으로 환불됩니다.',
            `• 약관 및 서비스 관련 문의: ${SUPPORT_EMAIL}`,
          ].join('\n'),
        });
        return;
      }
      if (doc === 'aiLabel' || doc === 'ai') {
        setInfoSheet({
          title: 'AI 라벨 안내',
          description: [
            aiDisclosureGuide || DEFAULT_AI_DISCLOSURE_GUIDE,
            '• 냅다로 제작한 영상의 훅 구간에는 AI 생성 이미지·음성·영상이 포함될 수 있습니다.',
            '• 인스타그램 릴스 게시 화면에서 [고급 설정 → AI 정보 레이블 추가]를 켜고 게시해 주세요.',
          ].join('\n'),
        });
        return;
      }
      if (doc === 'marketing') {
        setInfoSheet({
          title: '이벤트·혜택 알림 안내',
          description: '새로운 훅 템플릿 출시와 크레딧 할인 이벤트 소식을 안내해 드립니다. 원하지 않으시면 동의하지 않아도 서비스 이용에 제한이 없어요.',
        });
        return;
      }
      setInfoSheet({
        title: '도움말·문의',
        description: [
          '영상 제작이나 결제 중 문제가 생기면 아래 이메일로 문의해 주세요.',
          `이메일: ${SUPPORT_EMAIL}`,
          '프로젝트 이름과 발생 시각을 함께 보내 주시면 더 빠르게 확인해 드려요.',
        ].join('\n'),
        actionLabel: '이메일 주소 복사',
        onAction: () => {
          navigator.clipboard?.writeText(SUPPORT_EMAIL).catch(() => undefined);
          setInfoSheet(null);
        },
      });
    },
    [aiDisclosureGuide],
  );

  const openCreditPolicy = useCallback(() => {
    setInfoSheet({
      title: '환불·유효기간 안내',
      description: [
        '• 영상 1편 제작 시 12 크레딧이 사용됩니다. 시나리오 글, 그림 콘티, 촬영 가이드는 무료입니다.',
        '• 시스템 오류로 영상 제작에 실패하면 차감된 크레딧은 자동으로 돌려드립니다.',
        '• 사용하지 않은 충전 크레딧의 결제 취소·환불은 결제일로부터 7일 이내에 고객지원으로 요청해 주세요.',
        `• 결제·환불 문의: ${SUPPORT_EMAIL}`,
      ].join('\n'),
      actionLabel: '이메일 주소 복사',
      onAction: () => {
        navigator.clipboard?.writeText(SUPPORT_EMAIL).catch(() => undefined);
        setInfoSheet(null);
      },
    });
  }, []);

  const openDeleteAccountSupport = useCallback(() => {
    setInfoSheet({
      title: '회원 탈퇴 안내',
      description: [
        '계정과 프로젝트 데이터의 안전한 영구 삭제를 위해 탈퇴는 고객지원 이메일로 접수하고 있어요.',
        `가입하신 구글 이메일과 함께 ${SUPPORT_EMAIL}로 탈퇴를 요청해 주시면 확인 후 모든 데이터를 삭제해 드립니다.`,
      ].join('\n'),
      actionLabel: '이메일 주소 복사',
      onAction: () => {
        navigator.clipboard?.writeText(SUPPORT_EMAIL).catch(() => undefined);
        setInfoSheet(null);
      },
    });
  }, []);

  const appendNotification = useCallback((entry: Omit<AppNotification, 'id' | 'createdAt' | 'isRead'>) => {
    notifSeqRef.current += 1;
    setNotifications((prev) => [
      {
        ...entry,
        id: `live-notif-${notifSeqRef.current}`,
        createdAt: new Date().toISOString(),
        isRead: false,
      },
      ...prev,
    ]);
  }, []);

  const appendLedgerEntry = useCallback((entry: Omit<CreditEntry, 'id' | 'createdAt'>) => {
    ledgerSeqRef.current += 1;
    setCreditLedger((prev) => [
      {
        ...entry,
        id: `live-ledger-${ledgerSeqRef.current}`,
        createdAt: new Date().toISOString(),
      },
      ...prev,
    ]);
  }, []);

  const applyDeliverables = useCallback((data: DeliverablesResponse) => {
    if (data.video?.stream_url) {
      setVideoUrl(data.video.stream_url);
      setVideoDownloadUrl(data.video.download_url ?? data.video.stream_url);
    }
    if (data.ai_disclosure?.instagram_guide) {
      setAiDisclosureGuide(data.ai_disclosure.instagram_guide);
    }
    const thumb = data.thumbnail;
    if (thumb) {
      const style = normalizeFigmaVariant(thumb.style);
      setDeliverableThumb({
        imageUrl: thumb.image_url ?? undefined,
        downloadUrl: thumb.download_url ?? thumb.image_url ?? undefined,
        style,
        highlightWord: thumb.highlight_word ?? undefined,
        badge: thumb.badge ?? undefined,
        candidateImageUrls: Array.isArray(thumb.candidate_image_urls) ? thumb.candidate_image_urls : [],
        candidateKeys: Array.isArray(thumb.candidate_keys) ? thumb.candidate_keys : [],
      });
    } else {
      setDeliverableThumb(null);
    }
    setThumbError(null);
  }, []);

  const openCharge = useCallback(
    (from: ChargeFrom, shortfall?: number) => {
      pollCancelRef.current?.();
      setChargeState({
        stage: 'charge',
        from,
        shortfall,
        before: wallet?.credits ?? 0,
        added: 0,
        isPaying: false,
        hasPaymentError: false,
      });
    },
    [wallet?.credits],
  );

  const handleToggleVideoLike = useCallback((id: string, isLiked: boolean) => {
    setLikedVideoIds((prev) => ({ ...prev, [id]: isLiked }));
  }, []);

  const handleBannerSelect = useCallback(
    (bannerId: string) => {
      if (bannerId === 'b1') {
        openCharge('home');
        return;
      }
      const banner = HOME_BANNERS.find((b) => b.id === bannerId);
      setInfoSheet({
        title: bannerId === 'b2' ? '냅다 광고 뽑기 이벤트' : '미친 광고 공모전',
        description:
          banner?.alt ??
          '새로운 이벤트와 크레딧 혜택을 확인하고 나만의 릴스 광고를 만들어 보세요.',
        actionLabel: '지금 만들어 보기',
        onAction: () => {
          setInfoSheet(null);
          setActiveTab('home');
        },
      });
    },
    [openCharge],
  );

  const startNewCreation = useCallback((initialType: HookType = 'A') => {
    renderPollCancelRef.current?.();
    renderAbortRef.current?.abort();
    renderAbortRef.current = null;
    activeRenderJobIdRef.current = null;
    setIsCancelingRender(false);
    setChargeState(null);
    setOverlayScreen(null);
    setProjectId(null);
    setProductInfo({});
    setPublishedCaption('');
    setHookType(initialType);
    setSkippedDrafts(false);
    setScenarioId(null);
    setScenarioText(undefined);
    setStoryboardScenes(undefined);
    setStoryboardLoading(false);
    setStoryboardError(null);
    setGuideScenes(undefined);
    setUploadFiles([]);
    setVideoUrl(undefined);
    setVideoDownloadUrl(undefined);
    setDeliverableThumb(null);
    setAiDisclosureGuide(undefined);
    setThumbError(null);
    setGenJob(null);
    setCreationStep('product');
  }, []);

  const pollRenderCompletion = useCallback(
    (pid: string, nameForNotice?: string) => {
      renderPollCancelRef.current?.();
      let cancelled = false;
      renderPollCancelRef.current = () => {
        cancelled = true;
      };

      const run = async () => {
        // 서버가 "만드는 중"이라고 하는 동안은 계속 기다린다. 실패 화면은 서버가 FAILED 라고 할 때만.
        // 시간을 정해 두고 실패로 바꾸면, Gemini 경로처럼 오래 걸리는 렌더가 서버에선 도는데
        // 화면만 "본편에 이어 붙이기에서 멈췄어요"가 됐다(2026-11-28).
        // 처음 5분은 1.5초마다, 그 뒤는 서버 부담을 줄이려 5초마다 묻는다.
        // 30분이 지나면 묻기만 멈추고 화면은 "만드는 중"으로 둔다(완성되면 홈의 내 영상에 뜬다).
        const startedAt = Date.now();
        while (Date.now() - startedAt < RENDER_POLL_LIMIT_MS) {
          if (cancelled) return;
          try {
            const projRes = await getProjectV1ProjectsProjectIdGet(pid);
            if (cancelled) return;
            if (projRes.status === 200) {
              const proj = projRes.data;
              const jobObj = proj.latest_job as
                | {
                    status?: string;
                    stage?: string;
                    error?: string;
                    deducted_credits?: number;
                    refunded_credits?: number;
                  }
                | null
                | undefined;
              const stageKey = jobObj?.stage || '';

              if (proj.status === 'DELIVERABLE_READY' || jobObj?.status === 'QC_READY') {
                const delivRes = await getDeliverablesV1ProjectsProjectIdDeliverablesGet(pid);
                if (cancelled) return;
                if (delivRes.status === 200 && delivRes.data.video?.stream_url) {
                  applyDeliverables(delivRes.data);
                  setGenJob({
                    status: 'done',
                    progress: 100,
                    stageIndex: 2,
                    remainingSeconds: 0,
                  });
                  void queryClient.invalidateQueries({
                    queryKey: getListProjectsV1ProjectsGetQueryKey(),
                  });
                  void queryClient.invalidateQueries({
                    queryKey: getGetWalletV1BillingWalletGetQueryKey(),
                  });
                  if (creationStepRef.current !== 'generating') {
                    appendNotification({
                      kind: 'videoReady',
                      title: '영상 나왔어요!',
                      body: `${nameForNotice || proj.product.name} · 훅 붙여서 완성했어요. 썸네일만 고르면 끝.`,
                      targetId: pid,
                    });
                  }
                  return;
                }
              }

              if (proj.status === 'FAILED' || jobObj?.status === 'FAILED') {
                const refunded =
                  typeof jobObj?.refunded_credits === 'number' ? jobObj.refunded_credits : 0;
                setGenJob({
                  status: 'failed',
                  progress: 42,
                  stageIndex: 0,
                  failure: {
                    kind: 'temporary',
                    detail: jobObj?.error || '영상 합성 중 오류가 발생했어요.',
                  },
                  refundedCredits: refunded > 0 ? refunded : undefined,
                });
                if (refunded > 0) {
                  appendLedgerEntry({
                    kind: 'refund',
                    amount: refunded,
                    balance: walletCredits + refunded,
                    productName: nameForNotice || proj.product.name,
                  });
                }
                void queryClient.invalidateQueries({
                  queryKey: getListProjectsV1ProjectsGetQueryKey(),
                });
                void queryClient.invalidateQueries({
                  queryKey: getGetWalletV1BillingWalletGetQueryKey(),
                });
                if (creationStepRef.current !== 'generating') {
                  appendNotification({
                    kind: 'videoFailed',
                    title: '영상을 못 만들었어요',
                    body:
                      refunded > 0
                        ? `${nameForNotice || proj.product.name} · 쓴 크레딧 ${refunded}는 돌려드렸어요. 다시 해 볼까요?`
                        : `${nameForNotice || proj.product.name} · 다시 시도해 볼까요?`,
                    targetId: pid,
                  });
                }
                return;
              }

              if (jobObj?.status === 'CANCELED') {
                const refunded =
                  typeof jobObj?.refunded_credits === 'number' ? jobObj.refunded_credits : 0;
                activeRenderJobIdRef.current = null;
                setIsCancelingRender(false);
                setGenJob((prev) => ({
                  status: 'canceled',
                  progress: prev?.progress ?? 30,
                  stageIndex: prev?.stageIndex ?? 0,
                  refundedCredits: refunded > 0 ? refunded : undefined,
                }));
                if (refunded > 0) {
                  appendLedgerEntry({
                    kind: 'refund',
                    amount: refunded,
                    balance: walletCredits + refunded,
                    productName: nameForNotice || proj.product.name,
                  });
                }
                void queryClient.invalidateQueries({
                  queryKey: getListProjectsV1ProjectsGetQueryKey(),
                });
                void queryClient.invalidateQueries({
                  queryKey: getGetWalletV1BillingWalletGetQueryKey(),
                });
                return;
              }

              if (stageKey === 'ASSEMBLING') {
                setGenJob({
                  status: 'running',
                  progress: 78,
                  stageIndex: 1,
                  remainingSeconds: 25,
                });
              } else if (stageKey === 'GENERATING' || stageKey === 'LINTING') {
                setGenJob({
                  status: 'running',
                  progress: 52,
                  stageIndex: 0,
                  remainingSeconds: 50,
                });
              } else if (stageKey === 'ANALYZING' || stageKey === 'PLANNING') {
                setGenJob({
                  status: 'running',
                  progress: 28,
                  stageIndex: 0,
                  remainingSeconds: 80,
                });
              }
            }
          } catch {
            // Keep polling across transient network errors.
          }
          const waitMs = Date.now() - startedAt < RENDER_POLL_FAST_MS ? 1500 : 5000;
          await new Promise((resolve) => window.setTimeout(resolve, waitMs));
        }
      };

      void run();
    },
    [appendLedgerEntry, appendNotification, applyDeliverables, queryClient, walletCredits],
  );

  const openExistingProject = useCallback(
    async (pid: string, target: 'continue' | 'download') => {
      try {
        const res = await getProjectV1ProjectsProjectIdGet(pid);
        if (res.status !== 200) {
          if (target === 'download') {
            setInfoSheet({
              title: '영상을 불러오지 못했어요',
              description: '프로젝트 정보를 확인하지 못했어요. 잠시 후 다시 시도해 주세요.',
            });
          }
          return;
        }
        const proj = res.data;
        setOverlayScreen(null);
        setProjectId(pid);
        setProductInfo({
          name: proj.product.name,
          intro: (proj.product.verified_facts || []).join(', '),
        });
        setPublicProjectIds((prev) => ({
          ...prev,
          [pid]: Boolean(proj.is_public),
        }));
        setPublishedCaption(proj.public_caption ?? '');
        const firstType = (proj.selected_types?.[0] as HookType | undefined) ?? 'A';
        setHookType(firstType);
        setStoryboardError(null);
        setStoryboardLoading(false);
        setThumbError(null);

        const selScn =
          proj.scenarios?.find((s) => s.scenario_id === proj.selected_scenario_id) ?? proj.scenarios?.[0];
        if (selScn) {
          setScenarioId(selScn.scenario_id);
          setScenarioText(formatScenarioText(selScn));
          setSkippedDrafts(false);
          if (selScn.storyboard_frames && selScn.storyboard_frames.length > 0) {
            setStoryboardScenes(
              selScn.storyboard_frames.map((f) => ({
                imageUrl: f.image_url ?? undefined,
                caption: f.caption,
              })),
            );
          } else {
            setStoryboardScenes(undefined);
          }
        } else {
          setScenarioId(null);
          setScenarioText(undefined);
          setStoryboardScenes(undefined);
          setSkippedDrafts(!proj.filming_guide?.shots?.length);
        }

        if (proj.filming_guide?.shots?.length) {
          setGuideScenes(
            proj.filming_guide.shots.map((sh) => ({
              instruction: `${sh.title} — ${sh.framing_tip}`,
              duration: `${sh.duration_sec}초`,
            })),
          );
        } else {
          setGuideScenes(undefined);
        }

        if (proj.status === 'DELIVERABLE_READY' || target === 'download') {
          try {
            const deliv = await getDeliverablesV1ProjectsProjectIdDeliverablesGet(pid);
            if (deliv.status === 200 && deliv.data.video?.stream_url) {
              applyDeliverables(deliv.data);
              setGenJob({ status: 'done', progress: 100, stageIndex: 2, remainingSeconds: 0 });
              setCreationStep(target === 'download' ? 'thumbnail' : 'review');
              return;
            }
          } catch (delivErr) {
            if (target === 'download') {
              const detail =
                delivErr instanceof NapdaApiError && delivErr.status === 404
                  ? '아직 완성된 영상이 없거나 보관 기간(7일)이 지나 내려받을 수 없어요.'
                  : '영상 파일을 불러오지 못했어요. 잠시 후 다시 시도해 주세요.';
              setInfoSheet({
                title: '영상을 불러오지 못했어요',
                description: detail,
              });
              return;
            }
          }
          if (target === 'download') {
            setInfoSheet({
              title: '영상을 불러오지 못했어요',
              description: '아직 완성된 영상이 준비되지 않았어요. 잠시 후 다시 확인해 주세요.',
            });
            return;
          }
        }
        if (proj.status === 'RENDERING') {
          activeRenderJobIdRef.current = proj.latest_job_id ?? null;
          setIsCancelingRender(false);
          setGenJob({ status: 'running', progress: 42, stageIndex: 0, remainingSeconds: 60 });
          setCreationStep('generating');
          pollRenderCompletion(pid, proj.product.name);
          return;
        }
        if (proj.filming_guide?.shots?.length) {
          setCreationStep('upload');
        } else if (proj.status === 'STORYBOARD_READY' && selScn?.storyboard_frames?.length) {
          setCreationStep('storyboard');
        } else if (selScn) {
          setCreationStep('scenario');
        } else {
          setCreationStep('hook');
        }
      } catch {
        setInfoSheet({
          title: '프로젝트를 열지 못했어요',
          description: '네트워크 상태를 확인한 뒤 다시 시도해 주세요.',
        });
      }
    },
    [applyDeliverables, pollRenderCompletion],
  );

  const handleProductNext = useCallback(
    async (info: ProductInfo) => {
      setProductInfo(info);
      if (projectId) {
        setCreationStep('hook');
        return;
      }
      const res = await createProjectV1ProjectsPost({
        product: {
          name: info.name.trim(),
          category: mapCategoryToApi(info.category),
          verified_facts: parseFactsFromIntro(info.name, info.intro),
        },
        selected_types: [hookType],
        flow_mode: CreateProjectRequestFlowMode.guide_first,
      });
      if (res.status === 201) {
        setProjectId(res.data.project_id);
        setCreationStep('hook');
        void queryClient.invalidateQueries({ queryKey: getListProjectsV1ProjectsGetQueryKey() });
      }
    },
    [hookType, projectId, queryClient],
  );

  const handleHookNext = useCallback(
    async (selected: HookType[]) => {
      const primary = selected[0] ?? 'A';
      setHookType(primary);
      setSkippedDrafts(false);
      setScenarioText(undefined);
      setScenarioId(null);
      setStoryboardScenes(undefined);
      setStoryboardError(null);
      setCreationStep('scenario');
      if (!projectId) return;
      try {
        const ab = readScenarioAbOverride();
        const res = await generateScenariosV1ProjectsProjectIdScenariosPost(projectId, {
          types: [primary] as GenerateScenariosRequest['types'],
          ...(ab.provider ? { provider: ab.provider } : {}),
          ...(ab.model ? { model: ab.model } : {}),
          count: 1,
        } as GenerateScenariosRequest);
        if (res.status === 200 && res.data.scenarios.length > 0) {
          const matched =
            [...res.data.scenarios].reverse().find((s) => s.type === primary) ??
            res.data.scenarios[res.data.scenarios.length - 1];
          setScenarioId(matched.scenario_id);
          setScenarioText(formatScenarioText(matched));
        }
      } catch (err) {
        setScenarioText(
          err instanceof Error
            ? `시나리오 생성 중 문제가 생겼어요: ${err.message}`
            : '시나리오 생성 중 문제가 생겼어요.',
        );
      }
    },
    [projectId],
  );

  const handleGoStoryboard = useCallback(
    async (force = false) => {
      setCreationStep('storyboard');
      if (!force && storyboardScenes && storyboardScenes.length > 0) {
        setStoryboardError(null);
        return;
      }
      if (!projectId || !scenarioId) {
        setStoryboardError('시나리오를 먼저 불러와 주세요.');
        return;
      }
      setStoryboardLoading(true);
      setStoryboardError(null);
      if (force) {
        setStoryboardScenes(undefined);
      }
      try {
        const res = await generateStoryboardV1ProjectsProjectIdScenariosScenarioIdStoryboardPost(
          projectId,
          scenarioId,
          {
            visual_style: hookType === 'B' ? 'blender_3d_cutaway' : 'blender_clay_diorama',
          },
        );
        if (res.status === 200 && res.data.frames.length > 0) {
          setStoryboardScenes(
            res.data.frames.map((f) => ({
              imageUrl: f.image_url ?? undefined,
              caption: f.caption,
            })),
          );
        } else {
          setStoryboardError('그림 콘티를 만들지 못했어요. 다시 시도해 주세요.');
        }
      } catch (err) {
        setStoryboardError(
          err instanceof Error
            ? err.message
            : '그림 콘티를 불러오는 중 문제가 생겼어요. 잠시 후 다시 시도해 주세요.',
        );
      } finally {
        setStoryboardLoading(false);
      }
    },
    [hookType, projectId, scenarioId, storyboardScenes],
  );

  const handleGoShootingGuide = useCallback(async () => {
    setCreationStep('guide');
    if (!projectId || !scenarioId) return;
    try {
      await selectScenarioV1ProjectsProjectIdScenariosScenarioIdSelectPost(projectId, scenarioId);
      const res = await createFilmingGuideV1ProjectsProjectIdFilmingGuidePost(projectId, {
        scenario_id: scenarioId,
      });
      if (res.status === 200) {
        setGuideScenes(
          res.data.shots.map((sh) => ({
            instruction: `${sh.title} — ${sh.framing_tip}`,
            duration: `${sh.duration_sec}초`,
          })),
        );
      }
    } catch {
      // Keep default guide skeleton on transient error.
    }
  }, [projectId, scenarioId]);

  const handleUploadAndRender = useCallback(
    async (files: File[]) => {
      if (!projectId || !auth.user || files.length === 0) return;
      renderPollCancelRef.current?.();
      renderAbortRef.current?.abort();
      const abortController = new AbortController();
      renderAbortRef.current = abortController;
      activeRenderJobIdRef.current = null;
      setIsCancelingRender(false);

      setUploadFiles(files);
      setVideoUrl(undefined);
      setVideoDownloadUrl(undefined);
      setDeliverableThumb(null);
      setThumbError(null);
      setGenJob({ status: 'queued', progress: 8, stageIndex: 0, remainingSeconds: 110 });
      setCreationStep('generating');

      let failedAsVideoProblem = true;
      try {
        // 고른 영상마다 업로드 주소를 받아 올린다. 순서 = 컷 번호 (서버가 이 순서로 본편을 편집한다)
        const uploaded = await Promise.all(
          files.map(async (file, index) => {
            const shotNo = index + 1;
            const cleanName = (file.name || 'clip.mp4').replace(/[^a-zA-Z0-9._-]+/g, '_');
            const objKey = `uploads/${auth.user!.user_id}/${projectId}/shot_${String(shotNo).padStart(2, '0')}_${Date.now()}_${cleanName}`;
            const presignRes = await presignUploadV1UploadsPresignPost(
              {
                object_key: objKey,
                content_type: file.type || 'video/mp4',
              },
              { signal: abortController.signal },
            );
            if (presignRes.status !== 200) {
              throw new Error('업로드 주소를 발급받지 못했어요.');
            }
            const uploadUrl = presignRes.data.upload_url;
            const isExternalPresign =
              /^https?:\/\//i.test(uploadUrl) && !uploadUrl.startsWith(window.location.origin);
            const putRes = await fetch(uploadUrl, {
              method: 'PUT',
              headers: { 'Content-Type': file.type || 'video/mp4' },
              body: file,
              credentials: isExternalPresign ? 'omit' : 'include',
              signal: abortController.signal,
            });
            if (!putRes.ok) {
              throw new Error(`올린 영상을 전송하지 못했어요 (HTTP ${putRes.status})`);
            }
            return { shot_no: shotNo, object_key: presignRes.data.object_key, file_size_bytes: file.size };
          }),
        );
        if (abortController.signal.aborted) return;

        const completeRes = await completeUploadsV1ProjectsProjectIdUploadsCompletePost(
          projectId,
          { clips: uploaded },
          { signal: abortController.signal },
        );
        if (completeRes.status !== 200) {
          throw new Error('올린 영상의 길이와 해상도를 확인할 수 없어요.');
        }
        if (abortController.signal.aborted) return;

        failedAsVideoProblem = false;
        setGenJob({ status: 'running', progress: 20, stageIndex: 0, remainingSeconds: 90 });

        const renderRes = await createRenderV1ProjectsProjectIdRendersPost(
          projectId,
          {
            scenario_id: scenarioId,
            selected_type: hookType as CreateRenderRequestSelectedType,
            skip_drafts: !scenarioId,
            resolution: '720p',
            dry_run: false,
          },
          { signal: abortController.signal },
        );
        if (renderRes.status !== 202) {
          throw new Error('영상 제작 요청에 실패했어요.');
        }
        activeRenderJobIdRef.current = renderRes.data.job_id ?? null;
        if (abortController.signal.aborted) return;

        const deducted =
          typeof renderRes.data.deducted_credits === 'number'
            ? renderRes.data.deducted_credits
            : isInternalAccount
              ? 0
              : creditsPerVideo;
        if (deducted > 0) {
          const remaining = Math.max(0, walletCredits - deducted);
          appendLedgerEntry({
            kind: 'use',
            amount: -deducted,
            balance: remaining,
            productName: productInfo.name || '내 영상',
          });
        }
        void queryClient.invalidateQueries({ queryKey: getGetWalletV1BillingWalletGetQueryKey() });
        pollRenderCompletion(projectId, productInfo.name);
      } catch (err) {
        if (
          abortController.signal.aborted ||
          (err instanceof DOMException && err.name === 'AbortError')
        ) {
          return;
        }
        if (
          err instanceof NapdaApiError &&
          (err.status === 402 || err.code === 'INSUFFICIENT_CREDITS')
        ) {
          const detailShortfall =
            typeof err.details?.shortfall === 'number'
              ? err.details.shortfall
              : Math.max(1, creditsPerVideo - walletCredits);
          setGenJob(null);
          void queryClient.invalidateQueries({
            queryKey: getGetWalletV1BillingWalletGetQueryKey(),
          });
          openCharge('upload', detailShortfall);
          return;
        }
        const detail = err instanceof Error ? err.message : '영상 제작 요청 중 오류가 발생했어요.';
        setGenJob({
          status: 'failed',
          progress: 15,
          stageIndex: 0,
          failure: {
            kind: failedAsVideoProblem ? 'video' : 'temporary',
            detail,
          },
        });
      }
    },
    [
      appendLedgerEntry,
      auth.user,
      creditsPerVideo,
      hookType,
      isInternalAccount,
      openCharge,
      pollRenderCompletion,
      productInfo.name,
      projectId,
      queryClient,
      scenarioId,
      walletCredits,
    ],
  );

  const handleCancelRender = useCallback(async () => {
    setIsCancelingRender(true);
    renderAbortRef.current?.abort();
    renderPollCancelRef.current?.();
    const jobIdToCancel = activeRenderJobIdRef.current;
    try {
      if (projectId) {
        const res = await customFetch<{
          status: number;
          data: {
            refunded_credits?: number;
            credits?: number;
          };
        }>(`/v1/projects/${projectId}/renders/cancel`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(jobIdToCancel ? { job_id: jobIdToCancel } : {}),
        });
        const refunded =
          typeof res.data?.refunded_credits === 'number' ? res.data.refunded_credits : 0;
        if (refunded > 0) {
          const nextBal =
            typeof res.data?.credits === 'number' ? res.data.credits : walletCredits + refunded;
          appendLedgerEntry({
            kind: 'refund',
            amount: refunded,
            balance: nextBal,
            productName: productInfo.name || '내 영상',
          });
        }
        activeRenderJobIdRef.current = null;
        setGenJob((prev) => ({
          status: 'canceled',
          progress: prev?.progress ?? 20,
          stageIndex: prev?.stageIndex ?? 0,
          refundedCredits: refunded > 0 ? refunded : undefined,
        }));
      } else {
        setGenJob((prev) => ({
          status: 'canceled',
          progress: prev?.progress ?? 10,
          stageIndex: prev?.stageIndex ?? 0,
        }));
      }
      void queryClient.invalidateQueries({ queryKey: getListProjectsV1ProjectsGetQueryKey() });
      void queryClient.invalidateQueries({ queryKey: getGetWalletV1BillingWalletGetQueryKey() });
    } catch {
      setGenJob((prev) => ({
        status: 'canceled',
        progress: prev?.progress ?? 20,
        stageIndex: prev?.stageIndex ?? 0,
      }));
    } finally {
      setIsCancelingRender(false);
    }
  }, [appendLedgerEntry, productInfo.name, projectId, queryClient, walletCredits]);

  const handleDownloadThumbnail = useCallback(
    async (templateId: string | null, caption: string) => {
      if (!projectId) return;
      const variant = normalizeFigmaVariant(templateId ?? deliverableThumb?.style);
      const formattedHeadline = formatThumbnailHeadline(
        caption.trim() || productInfo.name || '지금 확인',
      );
      const lines = formattedHeadline
        .split('\n')
        .map((s) => s.trim())
        .filter(Boolean)
        .slice(0, 3);
      const sourceImageKey = deliverableThumb?.candidateKeys[0];
      setIsDownloadingThumb(true);
      setThumbError(null);
      try {
        const res = await customFetch<{
          status: number;
          data: {
            download_url?: string | null;
            image_url?: string | null;
            style?: string | null;
            highlight_word?: string | null;
            badge?: string | null;
            candidate_image_urls?: string[];
            candidate_keys?: string[];
          };
        }>(`/v1/projects/${projectId}/thumbnail`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            headline_lines: lines.length > 0 ? lines : [productInfo.name || '지금 확인'],
            style: variant,
            ...(deliverableThumb?.highlightWord
              ? { highlight_word: deliverableThumb.highlightWord }
              : {}),
            ...(deliverableThumb?.badge ? { badge: deliverableThumb.badge } : {}),
            ...(sourceImageKey ? { source_image_key: sourceImageKey } : {}),
          }),
        });
        const newImageUrl = res.data?.image_url ?? undefined;
        const newDownloadUrl = res.data?.download_url || newImageUrl;
        const nextCandidateUrls = Array.isArray(res.data?.candidate_image_urls)
          ? res.data.candidate_image_urls
          : (deliverableThumb?.candidateImageUrls ?? []);
        const nextCandidateKeys = Array.isArray(res.data?.candidate_keys)
          ? res.data.candidate_keys
          : (deliverableThumb?.candidateKeys ?? []);
        const nextHighlightWord =
          res.data?.highlight_word ?? deliverableThumb?.highlightWord;
        const nextBadge = res.data?.badge ?? deliverableThumb?.badge;

        setDeliverableThumb((prev) => ({
          imageUrl: newImageUrl ?? prev?.imageUrl,
          downloadUrl: newDownloadUrl ?? prev?.downloadUrl,
          style: variant,
          highlightWord: nextHighlightWord,
          badge: nextBadge,
          candidateImageUrls: nextCandidateUrls,
          candidateKeys: nextCandidateKeys,
        }));
        void queryClient.invalidateQueries({
          queryKey: getListProjectsV1ProjectsGetQueryKey(),
        });
        void queryClient.invalidateQueries({
          queryKey: COMMUNITY_VIDEOS_QUERY_KEY,
        });
        try {
          const delivRes = await getDeliverablesV1ProjectsProjectIdDeliverablesGet(projectId);
          if (delivRes.status === 200) {
            applyDeliverables(delivRes.data);
          }
        } catch {
          // ignore deliverable refresh failure after thumbnail creation
        }

        const cleanBgUrl = nextCandidateUrls[0] || newImageUrl || deliverableThumb?.imageUrl;
        try {
          await exportThumbnailPng({
            variant,
            badge: nextBadge,
            headline: formattedHeadline,
            highlightWord: nextHighlightWord,
            imageUrl: cleanBgUrl,
          });
        } catch {
          if (newDownloadUrl) {
            triggerFileDownload(newDownloadUrl, `napda-thumbnail-${variant}.png`);
          } else {
            throw new Error('썸네일 PNG를 저장하지 못했어요. 다시 시도해 주세요.');
          }
        }
      } catch (err) {
        setThumbError(
          err instanceof Error
            ? err.message
            : '썸네일을 만드는 중 문제가 생겼어요. 잠시 후 다시 시도해 주세요.',
        );
      } finally {
        setIsDownloadingThumb(false);
      }
    },
    [
      applyDeliverables,
      deliverableThumb,
      productInfo.name,
      projectId,
      queryClient,
    ],
  );

  const handleTogglePublish = useCallback(
    async (nextIsPublic: boolean, caption?: string) => {
      if (!projectId) return;
      const trimmedCaption = caption?.trim() || productInfo.name || null;
      setPublicProjectIds((prev) => ({ ...prev, [projectId]: nextIsPublic }));
      if (trimmedCaption) {
        setPublishedCaption(trimmedCaption);
      }
      try {
        const res = await customFetch<{
          status: number;
          data: { project_id: string; is_public: boolean; caption: string | null };
        }>(`/v1/projects/${projectId}/publish`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            is_public: nextIsPublic,
            caption: trimmedCaption,
          }),
        });
        setPublicProjectIds((prev) => ({
          ...prev,
          [projectId]: Boolean(res.data?.is_public),
        }));
        if (res.data?.caption !== undefined && res.data.caption !== null) {
          setPublishedCaption(res.data.caption);
        }
        void queryClient.invalidateQueries({
          queryKey: getListProjectsV1ProjectsGetQueryKey(),
        });
        void queryClient.invalidateQueries({
          queryKey: COMMUNITY_VIDEOS_QUERY_KEY,
        });
      } catch (err) {
        setPublicProjectIds((prev) => ({ ...prev, [projectId]: !nextIsPublic }));
        setInfoSheet({
          title: '공개 설정을 바꾸지 못했어요',
          description:
            err instanceof Error
              ? err.message
              : '탐색 공개 상태를 저장하지 못했어요. 잠시 후 다시 시도해 주세요.',
        });
      }
    },
    [productInfo.name, projectId, queryClient],
  );

  const pollOrderCompletion = useCallback(
    (orderId: string, expectedAdded: number, expectedPrice?: number) => {
      pollCancelRef.current?.();
      let cancelled = false;
      pollCancelRef.current = () => {
        cancelled = true;
      };

      const run = async () => {
        for (let attempt = 0; attempt < 20; attempt += 1) {
          if (cancelled) return;
          try {
            const res = await getBillingOrderV1BillingOrdersOrderIdGet(orderId, {
              sync: true,
            });
            if (cancelled) return;
            if (res.status === 200) {
              if (res.data.status === 'completed') {
                const credited = res.data.credits || expectedAdded;
                queryClient.setQueryData(getGetWalletV1BillingWalletGetQueryKey(), {
                  data: res.data.wallet,
                  status: 200,
                  headers: res.headers,
                });
                appendLedgerEntry({
                  kind: 'charge',
                  amount: credited,
                  balance: res.data.wallet.credits,
                  price: res.data.amount_krw || expectedPrice,
                });
                setChargeState((prev) =>
                  prev
                    ? {
                        ...prev,
                        stage: 'done',
                        added: credited,
                        isPaying: false,
                        hasPaymentError: false,
                      }
                    : null,
                );
                return;
              }
              if (res.data.status === 'failed' || res.data.status === 'canceled') {
                setChargeState((prev) =>
                  prev
                    ? {
                        ...prev,
                        stage: 'charge',
                        isPaying: false,
                        hasPaymentError: res.data.status === 'failed',
                      }
                    : null,
                );
                return;
              }
            }
          } catch {
            // Keep polling briefly while webhook/transaction status propagates.
          }
          await new Promise((resolve) => window.setTimeout(resolve, 1500));
        }
        if (!cancelled) {
          void queryClient.invalidateQueries({
            queryKey: getGetWalletV1BillingWalletGetQueryKey(),
          });
          setChargeState((prev) =>
            prev
              ? {
                  ...prev,
                  stage: 'charge',
                  isPaying: false,
                  hasPaymentError: true,
                }
              : null,
          );
        }
      };

      void run();
    },
    [appendLedgerEntry, queryClient],
  );

  const handlePayPackage = useCallback(
    async (pkg: CreditPackage) => {
      if (!auth.user) return;
      const beforeCredits = wallet?.credits ?? 0;
      setChargeState((prev) =>
        prev
          ? { ...prev, isPaying: true, hasPaymentError: false, before: beforeCredits }
          : null,
      );

      try {
        const res = await checkoutMutation.mutateAsync({
          data: { package_id: pkg.id as CreateCheckoutRequestPackageId },
        });
        if (res.status !== 200) {
          setChargeState((prev) =>
            prev ? { ...prev, isPaying: false, hasPaymentError: true } : null,
          );
          return;
        }

        const checkout = res.data;
        await openPaddleCheckout({
          environment:
            (import.meta.env.VITE_PADDLE_ENVIRONMENT as 'sandbox' | 'production' | undefined) ??
            checkout.paddle_environment,
          clientToken:
            (import.meta.env.VITE_PADDLE_CLIENT_TOKEN as string | undefined) ??
            checkout.paddle_client_token,
          transactionId: checkout.paddle_transaction_id,
          customerEmail: checkout.customer_email ?? auth.user.email,
          theme: isDark ? 'dark' : 'light',
          onCompleted: () => {
            setChargeState((prev) =>
              prev
                ? {
                    ...prev,
                    stage: 'confirming',
                    before: beforeCredits,
                    added: pkg.credits,
                    isPaying: false,
                    hasPaymentError: false,
                  }
                : null,
            );
            pollOrderCompletion(checkout.order_id, pkg.credits, pkg.price);
          },
          onClosed: () => {
            setChargeState((prev) =>
              prev ? { ...prev, isPaying: false } : null,
            );
          },
          onError: () => {
            setChargeState((prev) =>
              prev ? { ...prev, isPaying: false, hasPaymentError: true } : null,
            );
          },
        });
      } catch {
        setChargeState((prev) =>
          prev ? { ...prev, isPaying: false, hasPaymentError: true } : null,
        );
      }
    },
    [auth.user, checkoutMutation, isDark, pollOrderCompletion, wallet?.credits],
  );

  const { inProgress, completed } = useMemo(() => {
    const list =
      projectsQuery.data?.status === 200 ? projectsQuery.data.data.projects : [];
    return splitProjects(list);
  }, [projectsQuery.data]);

  const displayName = useMemo(() => {
    if (!auth.user) return '냅다사장';
    const uid = auth.user.user_id;
    return (
      nicknameOverrides[uid] ??
      getStorageFlag(`napda:nickname:${uid}`) ??
      (auth.user.name?.trim() || auth.user.email.split('@')[0] || '냅다사장')
    );
  }, [auth.user, nicknameOverrides]);

  const handleAddComment = useCallback(
    (videoId: string, text: string) => {
      commentSeqRef.current += 1;
      const item: VideoComment = {
        id: `live-comment-${commentSeqRef.current}`,
        authorName: displayName,
        text,
        createdAt: new Date().toISOString(),
        isMine: true,
      };
      setCommentsByVideo((prev) => ({
        ...prev,
        [videoId]: [...(prev[videoId] ?? []), item],
      }));
    },
    [displayName],
  );

  const handleDeleteComment = useCallback((videoId: string, commentId: string) => {
    setCommentsByVideo((prev) => ({
      ...prev,
      [videoId]: (prev[videoId] ?? []).filter((c) => c.id !== commentId),
    }));
  }, []);

  const handleOpenNotification = useCallback(
    (target: AppNotification) => {
      setNotifications((prev) =>
        prev.map((n) => (n.id === target.id ? { ...n, isRead: true } : n)),
      );
      if (target.kind === 'videoReady' || target.kind === 'videoFailed') {
        if (target.targetId && target.targetId.startsWith('prj_')) {
          void openExistingProject(
            target.targetId,
            target.kind === 'videoReady' ? 'download' : 'continue',
          );
          return;
        }
        setOverlayScreen(null);
        setActiveTab('myVideos');
        setMyTab(target.kind === 'videoReady' ? 'completed' : 'inProgress');
        return;
      }
      if (target.kind === 'expiring') {
        setOverlayScreen(null);
        setMyTab('completed');
        setActiveTab('myVideos');
        return;
      }
      if (target.kind === 'creditCharged') {
        setOverlayScreen({ type: 'creditHistory', from: 'notifications' });
        return;
      }
      if (target.kind === 'communityLike') {
        setOverlayScreen({
          type: 'communityViewer',
          from: 'home',
          videoId: target.targetId,
        });
      }
    },
    [openExistingProject],
  );

  const handleNavigate = (tab: NavTab) => {
    setOverlayScreen(null);
    setCreationStep(null);
    if (tab === 'myVideos') {
      setMyTab('inProgress');
    }
    setActiveTab(tab);
  };

  const needsSignup =
    auth.status === 'authenticated' &&
    Boolean(auth.user) &&
    authEntryStep === 'login' &&
    !onboardedUsers[auth.user!.user_id] &&
    !getStorageFlag(`napda:onboarded:${auth.user!.user_id}`);

  const isAdminRoute =
    typeof window !== 'undefined' && window.location.pathname.startsWith('/admin');
  if (isAdminRoute) {
    return (
      <NapdaProvider mode={themeMode}>
        <AdminUsagePage
          themeMode={themeMode}
          onThemeModeChange={setThemeMode}
          userEmail={auth.user?.email}
        />
      </NapdaProvider>
    );
  }

  let screen;
  if (!isSplashMinDone || (auth.status === 'loading' && activeTab !== 'profile')) {
    screen = <SplashScreen />;
  } else if (auth.status === 'loading') {
    // 내 정보 탭에서 다시 확인하는 동안은 스플래시 대신 내 정보 스켈레톤을 보여 준다
    screen = (
      <ProfileScreen
        isLoading
        themeMode={themeMode}
        onThemeModeChange={setThemeMode}
        onNavigate={handleNavigate}
        onOpenDoc={openInfoDocument}
      />
    );
  } else if (auth.status === 'unauthenticated' || !auth.user) {
    screen =
      activeTab === 'profile' ? (
        <ProfileScreen
          user={null}
          themeMode={themeMode}
          onThemeModeChange={setThemeMode}
          onNavigate={handleNavigate}
          onOpenDoc={openInfoDocument}
          signInSlot={<GoogleSignInButton theme={gisTheme} />}
        />
      ) : authEntryStep === 'login' ? (
        <LoginScreen
          showcase={loginShowcase}
          isSigningIn={auth.isSubmitting}
          hasError={Boolean(auth.error)}
          signInSlot={<GoogleSignInButton theme={gisTheme} />}
          onOpenDoc={openInfoDocument}
        />
      ) : (
        <OnboardingScreen onStart={() => setAuthEntryStep('login')} />
      );
  } else if (needsSignup && !termsAgreed) {
    screen = (
      <LoginScreen
        showcase={loginShowcase}
        isTermsOpen
        onOpenDoc={openInfoDocument}
        onAgreeTerms={() => {
          setNicknameStatus('available');
          setTermsAgreed(true);
        }}
        onCloseTerms={() => {
          setTermsAgreed(false);
          setAuthEntryStep('login');
          void auth.logout();
        }}
      />
    );
  } else if (needsSignup && termsAgreed) {
    const initialNick =
      (auth.user.name || auth.user.email.split('@')[0] || '냅다사장')
        .replace(/[^가-힣a-zA-Z0-9_]+/g, '')
        .slice(0, 12) || '냅다사장';
    screen = (
      <NicknameScreen
        initialNickname={initialNick}
        availability={nicknameStatus}
        onNicknameChange={() => {
          if (nicknameTimerRef.current) {
            window.clearTimeout(nicknameTimerRef.current);
          }
          setNicknameStatus('checking');
          nicknameTimerRef.current = window.setTimeout(() => {
            setNicknameStatus('available');
          }, 200);
        }}
        onBack={() => {
          setTermsAgreed(false);
        }}
        onSubmit={(chosenName) => {
          if (auth.user) {
            setStorageFlag(`napda:nickname:${auth.user.user_id}`, chosenName);
            setStorageFlag(`napda:onboarded:${auth.user.user_id}`, '1');
            setNicknameOverrides((prev) => ({
              ...prev,
              [auth.user!.user_id]: chosenName,
            }));
            setOnboardedUsers((prev) => ({
              ...prev,
              [auth.user!.user_id]: true,
            }));
          }
          setTermsAgreed(false);
          setAuthEntryStep('onboarding');
        }}
      />
    );
  } else {
    const profileUser = {
      name: displayName,
      email: auth.user.email,
      imageUrl: auth.user.picture ?? undefined,
    };

    if (chargeState) {
      if (chargeState.stage === 'charge') {
        screen = (
          <CreditChargeScreen
            credits={wallet?.credits ?? 0}
            packages={creditPackages}
            creditsPerVideo={creditsPerVideo}
            shortfall={chargeState.shortfall}
            isPaying={chargeState.isPaying}
            hasPaymentError={chargeState.hasPaymentError}
            onOpenPolicy={openCreditPolicy}
            onBack={() => {
              const target = chargeState.from;
              setChargeState(null);
              if (target === 'upload') {
                setCreationStep('upload');
              } else if (target === 'creditHistory') {
                setOverlayScreen({ type: 'creditHistory', from: 'profile' });
              } else {
                setActiveTab(target);
              }
            }}
            onPay={(pkg) => {
              void handlePayPackage(pkg);
            }}
          />
        );
      } else {
        screen = (
          <ChargeResultScreen
            status={chargeState.stage === 'done' ? 'done' : 'confirming'}
            before={chargeState.before}
            added={chargeState.added}
            isResumingVideo={chargeState.from === 'upload'}
            onDone={() => {
              const target = chargeState.from;
              setChargeState(null);
              if (target === 'upload') {
                setCreationStep('upload');
              } else if (target === 'creditHistory') {
                setOverlayScreen({ type: 'creditHistory', from: 'profile' });
              } else {
                setActiveTab(target);
              }
            }}
          />
        );
      }
    } else if (creationStep === 'product') {
      screen = (
        <ProductInfoScreen
          initialValue={productInfo}
          showPhotoUpload={false}
          onBack={() => setCreationStep(null)}
          onNext={(val) => {
            void handleProductNext(val);
          }}
        />
      );
    } else if (creationStep === 'hook') {
      screen = (
        <HookTypeScreen
          initialSelected={[hookType]}
          creditsPerVideo={creditsPerVideo}
          onBack={() => setCreationStep('product')}
          onNext={(selected) => {
            void handleHookNext(selected);
          }}
          onSkipToVideo={(selected) => {
            setHookType(selected[0] ?? hookType);
            setScenarioId(null);
            setScenarioText(undefined);
            setStoryboardScenes(undefined);
            setStoryboardError(null);
            setGuideScenes(undefined);
            setSkippedDrafts(true);
            setCreationStep('upload');
          }}
        />
      );
    } else if (creationStep === 'scenario') {
      screen = (
        <ScenarioScreen
          hookType={hookType}
          scenario={scenarioText}
          onBack={() => setCreationStep('hook')}
          onShootingGuide={() => {
            void handleGoShootingGuide();
          }}
          onStoryboard={() => {
            void handleGoStoryboard();
          }}
        />
      );
    } else if (creationStep === 'storyboard') {
      screen = (
        <StoryboardScreen
          hookType={hookType}
          scenes={storyboardScenes}
          isLoading={storyboardLoading}
          error={storyboardError}
          onRetry={() => {
            void handleGoStoryboard(true);
          }}
          onBack={() => setCreationStep('scenario')}
          onShootingGuide={() => {
            void handleGoShootingGuide();
          }}
        />
      );
    } else if (creationStep === 'guide') {
      screen = (
        <ShootingGuideScreen
          scenes={guideScenes}
          onBack={() => setCreationStep('scenario')}
          onUpload={() => setCreationStep('upload')}
        />
      );
    } else if (creationStep === 'upload') {
      screen = (
        <UploadVideoScreen
          hookType={hookType}
          initialFiles={uploadFiles}
          cost={creditsPerVideo}
          credits={wallet?.credits}
          isInternalAccount={isInternalAccount}
          onBack={() => setCreationStep(skippedDrafts ? 'hook' : 'guide')}
          onReviewGuide={skippedDrafts ? undefined : () => setCreationStep('guide')}
          onCreate={(files) => {
            void handleUploadAndRender(files);
          }}
          onCharge={(files, shortfall) => {
            setUploadFiles(files);
            openCharge('upload', shortfall);
          }}
        />
      );
    } else if (creationStep === 'generating') {
      screen = (
        <GeneratingScreen
          status={genJob?.status ?? 'running'}
          queuePosition={genJob?.status === 'queued' ? 1 : undefined}
          progress={genJob?.progress}
          stageIndex={genJob?.stageIndex ?? 0}
          remainingSeconds={genJob?.remainingSeconds}
          productName={productInfo.name}
          failure={genJob?.failure}
          refundedCredits={genJob?.refundedCredits}
          credits={wallet?.credits}
          retryCost={creditsPerVideo}
          isInternalAccount={isInternalAccount}
          isCanceling={isCancelingRender}
          onCancel={() => {
            void handleCancelRender();
          }}
          onBack={() => {
            setCreationStep(null);
            setActiveTab('home');
          }}
          onWaitAtHome={() => {
            setCreationStep(null);
            setActiveTab('home');
          }}
          onViewVideo={() => setCreationStep('review')}
          onRetry={() => {
            if (uploadFiles.length === 0) {
              setCreationStep('upload');
              return;
            }
            const currentCredits = wallet?.credits ?? 0;
            if (!isInternalAccount && currentCredits < creditsPerVideo) {
              openCharge('upload', creditsPerVideo - currentCredits);
            } else {
              void handleUploadAndRender(uploadFiles);
            }
          }}
          onReupload={() => setCreationStep('upload')}
          onReviewGuide={skippedDrafts ? undefined : () => setCreationStep('guide')}
          onContact={() => openInfoDocument('help')}
        />
      );
    } else if (creationStep === 'review') {
      screen = (
        <VideoReviewScreen
          videoUrl={videoUrl}
          onBack={() => {
            renderPollCancelRef.current?.();
            setCreationStep('upload');
          }}
          onMakeThumbnail={() => setCreationStep('thumbnail')}
        />
      );
    } else if (creationStep === 'thumbnail') {
      const summaryPublic =
        projectId && projectsQuery.data?.status === 200
          ? Boolean(
              projectsQuery.data.data.projects.find((p) => p.project_id === projectId)?.is_public,
            )
          : false;
      const currentPublic =
        projectId && projectId in publicProjectIds ? publicProjectIds[projectId] : summaryPublic;
      const cleanKeyframeUrl =
        deliverableThumb?.candidateImageUrls[0] || deliverableThumb?.imageUrl;
      screen = (
        <ThumbnailDownloadScreen
          key={`thumb-${projectId ?? 'none'}`}
          useFigmaTemplates
          backgroundImageUrl={cleanKeyframeUrl}
          badge={deliverableThumb?.badge}
          highlightWord={deliverableThumb?.highlightWord}
          initialTemplateId={deliverableThumb?.style ?? 'invert-box'}
          initialCaption={publishedCaption || productInfo.name || ''}
          aiDisclosure={aiDisclosureGuide}
          isDownloadingThumbnail={isDownloadingThumb}
          thumbnailError={thumbError}
          initialIsPublic={currentPublic}
          needsPublishConsent={!currentPublic}
          onPublicChange={(next, caption) => {
            void handleTogglePublish(next, caption);
          }}
          onBack={() => setCreationStep('review')}
          onDownloadVideo={() => {
            if (videoDownloadUrl) {
              triggerFileDownload(videoDownloadUrl, 'napda_master.mp4');
            }
          }}
          onDownloadThumbnail={(tplId, caption) => {
            void handleDownloadThumbnail(tplId, caption);
          }}
        />
      );
    } else if (overlayScreen?.type === 'notifications') {
      screen = (
        <NotificationsScreen
          items={notifications}
          onBack={() => setOverlayScreen(null)}
          onOpen={handleOpenNotification}
          onMarkAllRead={() =>
            setNotifications((prev) => prev.map((n) => ({ ...n, isRead: true })))
          }
        />
      );
    } else if (overlayScreen?.type === 'creditHistory') {
      screen = (
        <CreditHistoryScreen
          credits={wallet?.credits}
          entries={creditLedger}
          onOpenPolicy={openCreditPolicy}
          onBack={() => {
            if (overlayScreen.from === 'notifications') {
              setOverlayScreen({ type: 'notifications' });
            } else {
              setOverlayScreen(null);
            }
          }}
          onCharge={() => openCharge('creditHistory')}
        />
      );
    } else if (overlayScreen?.type === 'communityViewer') {
      const viewerItems =
        overlayScreen.from === 'creator'
          ? buildCreatorProfile(overlayScreen.creatorName || '', homeFeedVideos).videos
          : overlayScreen.from === 'home'
            ? homeFeedVideos
            : communityVideos;
      screen = (
        <CommunityViewerScreen
          items={viewerItems}
          initialId={overlayScreen.videoId}
          share={shareHandlers}
          comments={commentsByVideo}
          myName={displayName}
          onToggleLike={handleToggleVideoLike}
          onAddComment={handleAddComment}
          onDeleteComment={handleDeleteComment}
          onBack={() => {
            if (overlayScreen.from === 'creator' && overlayScreen.creatorName) {
              setOverlayScreen({
                type: 'creator',
                name: overlayScreen.creatorName,
                returnTo: { type: 'home' },
              });
            } else if (overlayScreen.from === 'home') {
              setOverlayScreen(null);
              setActiveTab('home');
            } else {
              setOverlayScreen(null);
              setActiveTab('community');
            }
          }}
          onOpenCreator={(creatorName) => {
            setOverlayScreen({
              type: 'creator',
              name: creatorName,
              returnTo: {
                type: 'communityViewer',
                from: overlayScreen.from === 'home' ? 'home' : 'community',
                videoId: overlayScreen.videoId,
              },
            });
          }}
          onRemix={(video) => startNewCreation(video.hookType)}
        />
      );
    } else if (overlayScreen?.type === 'creator') {
      const { profile, videos } = buildCreatorProfile(overlayScreen.name, homeFeedVideos);
      screen = (
        <CreatorProfileScreen
          creator={profile}
          videos={videos}
          onBack={() => {
            if (overlayScreen.returnTo.type === 'communityViewer') {
              setOverlayScreen(overlayScreen.returnTo);
            } else {
              setOverlayScreen(null);
              setActiveTab('home');
            }
          }}
          onOpenVideo={(videoId) => {
            setOverlayScreen({
              type: 'communityViewer',
              from: 'creator',
              videoId,
              creatorName: overlayScreen.name,
            });
          }}
          onRemix={(ht) => startNewCreation(ht)}
        />
      );
    } else if (activeTab === 'myVideos') {
      screen = (
        <MyVideosScreen
          key={`my-videos-${myTab}`}
          inProgress={inProgress}
          completed={completed}
          retentionDays={7}
          initialTab={myTab}
          onContinue={(id) => {
            void openExistingProject(id, 'continue');
          }}
          onDownloadAgain={(id) => {
            void openExistingProject(id, 'download');
          }}
          onNavigate={handleNavigate}
        />
      );
    } else if (activeTab === 'community') {
      screen = (
        <CommunityScreen
          items={communityVideos}
          status={communityQuery.isLoading ? 'loading' : communityQuery.isError ? 'error' : 'ready'}
          hookType={communityHookType}
          onHookTypeChange={setCommunityHookType}
          onRetry={() => {
            void communityQuery.refetch();
          }}
          onOpenVideo={(videoId) =>
            setOverlayScreen({ type: 'communityViewer', from: 'community', videoId })
          }
          onCreate={() => startNewCreation('A')}
          onNavigate={handleNavigate}
        />
      );
    } else if (activeTab === 'profile') {
      screen = (
        <ProfileScreen
          user={profileUser}
          credits={wallet?.credits}
          retentionDays={7}
          videoCounts={{ inProgress: inProgress.length, completed: completed.length }}
          themeMode={themeMode}
          onThemeModeChange={setThemeMode}
          onNavigate={handleNavigate}
          onOpenDoc={openInfoDocument}
          onChargeClick={() => openCharge('profile')}
          onCreditHistoryClick={() =>
            setOverlayScreen({ type: 'creditHistory', from: 'profile' })
          }
          onOpenMyVideos={(tab) => {
            setMyTab(tab);
            setActiveTab('myVideos');
          }}
          onLogout={() => {
            renderPollCancelRef.current?.();
            setCreationStep(null);
            setOverlayScreen(null);
            setChargeState(null);
            setAuthEntryStep('login');
            void auth.logout();
          }}
          onRequestDeleteSupport={openDeleteAccountSupport}
        />
      );
    } else {
      screen = (
        <HomeScreen
          banners={HOME_BANNERS}
          onBannerSelect={handleBannerSelect}
          inProgress={inProgress}
          completed={completed}
          credits={wallet?.credits}
          unreadCount={notifications.filter((n) => !n.isRead).length}
          onNotificationsClick={() => setOverlayScreen({ type: 'notifications' })}
          onCreditClick={() => openCharge('home')}
          profile={profileUser}
          onCreate={() => startNewCreation('A')}
          onContinue={(id) => {
            void openExistingProject(id, 'continue');
          }}
          onDownloadAgain={(id) => {
            void openExistingProject(id, 'download');
          }}
          onNavigate={handleNavigate}
          onSeeAllMyVideos={() => {
            setMyTab('inProgress');
            setActiveTab('myVideos');
          }}
          feed={homeFeedVideos.slice(0, homeFeedCount)}
          feedHasMore={homeFeedCount < homeFeedVideos.length}
          onLoadMoreFeed={() => setHomeFeedCount((value) => Math.min(homeFeedVideos.length, value + 4))}
          onOpenFeed={(videoId) => setOverlayScreen({ type: 'communityViewer', from: 'home', videoId })}
          onToggleFeedLike={handleToggleVideoLike}
          share={shareHandlers}
          onOpenCreator={(name) => setOverlayScreen({ type: 'creator', name, returnTo: { type: 'home' } })}
          onRemixFeed={(video) => startNewCreation(video.hookType)}
          onSeeAllFeed={() => setActiveTab('community')}
          comments={commentsByVideo}
          onAddComment={handleAddComment}
          onDeleteComment={handleDeleteComment}
        />
      );
    }
  }

  return (
    <div className="napda-app-shell">
      <NapdaProvider mode={themeMode}>
        {screen}
        <InfoSheet
          isOpen={infoSheet !== null}
          title={infoSheet?.title ?? ''}
          description={infoSheet?.description}
          actionLabel={infoSheet?.actionLabel}
          onAction={infoSheet?.onAction}
          onClose={() => setInfoSheet(null)}
        />
      </NapdaProvider>
    </div>
  );
}

export default App;
