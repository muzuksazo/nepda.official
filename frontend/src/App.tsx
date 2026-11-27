import { useQueryClient } from '@tanstack/react-query';
import { useCallback, useEffect, useMemo, useRef, useState, useSyncExternalStore } from 'react';
import { customFetch } from './api/mutator';
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
  type GenerateScenariosRequest,
  type ProjectSummary,
  type ProjectSummaryStatus,
  type ScenarioItem,
} from './api/generated/model';
import { GoogleSignInButton, useAuth } from './auth';
import { openPaddleCheckout } from './billing';
import { NapdaProvider, type ThemeSetting } from './ui/NapdaProvider';
import type { CreditPackage, NavTab, ShareHandlers, VideoComment } from './ui/components';
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
  StoryboardScreen,
  ThumbnailDownloadScreen,
  UploadVideoScreen,
  VideoReviewScreen,
  type AppNotification,
  type CompletedProject,
  type CreditEntry,
  type HookType,
  type InProgressProject,
  type MyVideosTab,
  type NicknameScreenProps,
  type ProductInfo,
} from './ui/screens';
import type { GuideScene } from './ui/screens/ShootingGuideScreen';
import type { StoryboardScene } from './ui/screens/StoryboardScreen';
import {
  SAMPLE_BANNERS,
  SAMPLE_COMMENTS,
  SAMPLE_COMMUNITY,
  SAMPLE_CREDIT_EXPIRING,
  SAMPLE_CREDIT_HISTORY,
  SAMPLE_CREDIT_PACKAGES,
  SAMPLE_CREDITS_PER_VIDEO,
  SAMPLE_LOGIN_SHOWCASE,
  SAMPLE_NOTIFICATIONS,
  SAMPLE_THUMBNAIL_TEMPLATES,
  filterCommunityByType,
  sampleCreator,
} from './ui/screens/sampleProjects';

const DARK_QUERY = '(prefers-color-scheme: dark)';

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

function splitProjects(projects: ProjectSummary[]): {
  inProgress: InProgressProject[];
  completed: CompletedProject[];
} {
  const inProgress: InProgressProject[] = [];
  const completed: CompletedProject[] = [];

  for (const project of projects) {
    if (COMPLETED_STATUSES.has(project.status)) {
      completed.push({
        id: project.project_id,
        productName: project.product_name,
        status: '영상과 썸네일을 만들었어요',
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

interface GeneratingJobState {
  status: 'queued' | 'running' | 'done' | 'failed';
  progress: number;
  stageIndex: number;
  remainingSeconds?: number;
  failure?: { kind: 'temporary' | 'video'; detail?: string };
  refundedCredits?: number;
}

export function App() {
  const auth = useAuth();
  const queryClient = useQueryClient();
  const [themeMode, setThemeMode] = useState<ThemeSetting>('system');
  const [activeTab, setActiveTab] = useState<NavTab>('home');
  const [myTab, setMyTab] = useState<MyVideosTab>('inProgress');
  const [communityHookType, setCommunityHookType] = useState<HookType | null>(null);
  const [chargeState, setChargeState] = useState<ChargeFlowState | null>(null);
  const [overlayScreen, setOverlayScreen] = useState<OverlayScreen | null>(null);

  // Onboarding / Login / Signup flow
  const [authEntryStep, setAuthEntryStep] = useState<'onboarding' | 'login'>('onboarding');
  const [termsAgreed, setTermsAgreed] = useState(false);
  const [nicknameStatus, setNicknameStatus] =
    useState<NicknameScreenProps['availability']>('available');
  const [nicknameOverrides, setNicknameOverrides] = useState<Record<string, string>>({});
  const [onboardedUsers, setOnboardedUsers] = useState<Record<string, boolean>>({});
  const nicknameTimerRef = useRef<number | undefined>(undefined);

  // Feed / Comments / Notifications / Credit ledger (local interactive state until backend social APIs land)
  const [feedCount, setFeedCount] = useState(4);
  const [commentsByVideo, setCommentsByVideo] = useState<Record<string, VideoComment[]>>(SAMPLE_COMMENTS);
  const [notifications, setNotifications] = useState<AppNotification[]>(SAMPLE_NOTIFICATIONS);
  const [creditLedger, setCreditLedger] = useState<CreditEntry[]>(SAMPLE_CREDIT_HISTORY);
  const [publicProjectIds, setPublicProjectIds] = useState<Record<string, boolean>>({});

  // 8-step creation flow state
  const [creationStep, setCreationStep] = useState<CreationStep | null>(null);
  const creationStepRef = useRef<CreationStep | null>(null);
  const [projectId, setProjectId] = useState<string | null>(null);
  const [productInfo, setProductInfo] = useState<Partial<ProductInfo>>({});
  const [hookType, setHookType] = useState<HookType>('A');
  const [scenarioId, setScenarioId] = useState<string | null>(null);
  const [scenarioText, setScenarioText] = useState<string | undefined>(undefined);
  const [storyboardScenes, setStoryboardScenes] = useState<StoryboardScene[] | undefined>(undefined);
  const [guideScenes, setGuideScenes] = useState<GuideScene[] | undefined>(undefined);
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [videoUrl, setVideoUrl] = useState<string | undefined>(undefined);
  const [videoDownloadUrl, setVideoDownloadUrl] = useState<string | undefined>(undefined);
  const [genJob, setGenJob] = useState<GeneratingJobState | null>(null);

  const pollCancelRef = useRef<(() => void) | null>(null);
  const renderPollCancelRef = useRef<(() => void) | null>(null);
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
  const creditsPerVideo = billingConfig?.credits_per_video ?? SAMPLE_CREDITS_PER_VIDEO;

  const creditPackages = useMemo<CreditPackage[]>(() => {
    if (!billingConfig?.packages?.length) {
      return SAMPLE_CREDIT_PACKAGES;
    }
    return billingConfig.packages.map((p) => ({
      id: p.id,
      credits: p.credits,
      price: p.price,
      isPopular: Boolean(p.is_popular),
    }));
  }, [billingConfig]);

  const shareHandlers = useMemo<ShareHandlers>(() => buildShareHandlers(), []);

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

  const startNewCreation = useCallback((initialType: HookType = 'A') => {
    renderPollCancelRef.current?.();
    setChargeState(null);
    setOverlayScreen(null);
    setProjectId(null);
    setProductInfo({});
    setHookType(initialType);
    setScenarioId(null);
    setScenarioText(undefined);
    setStoryboardScenes(undefined);
    setGuideScenes(undefined);
    setUploadFile(null);
    setVideoUrl(undefined);
    setVideoDownloadUrl(undefined);
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
        for (let attempt = 0; attempt < 180; attempt += 1) {
          if (cancelled) return;
          try {
            const projRes = await getProjectV1ProjectsProjectIdGet(pid);
            if (cancelled) return;
            if (projRes.status === 200) {
              const proj = projRes.data;
              const jobObj = proj.latest_job as
                | { status?: string; stage?: string; error?: string }
                | null
                | undefined;
              const stageKey = jobObj?.stage || '';

              if (proj.status === 'DELIVERABLE_READY' || jobObj?.status === 'QC_READY') {
                const delivRes = await getDeliverablesV1ProjectsProjectIdDeliverablesGet(pid);
                if (cancelled) return;
                if (delivRes.status === 200 && delivRes.data.video?.stream_url) {
                  setVideoUrl(delivRes.data.video.stream_url);
                  setVideoDownloadUrl(
                    delivRes.data.video.download_url ?? delivRes.data.video.stream_url,
                  );
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
                setGenJob({
                  status: 'failed',
                  progress: 42,
                  stageIndex: 0,
                  failure: {
                    kind: 'temporary',
                    detail: jobObj?.error || '영상 합성 중 오류가 발생했어요.',
                  },
                  refundedCredits: creditsPerVideo,
                });
                appendLedgerEntry({
                  kind: 'refund',
                  amount: creditsPerVideo,
                  balance: walletCredits + creditsPerVideo,
                  productName: nameForNotice || proj.product.name,
                });
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
                    body: `${nameForNotice || proj.product.name} · 쓴 크레딧 ${creditsPerVideo}는 돌려드렸어요. 다시 해 볼까요?`,
                    targetId: pid,
                  });
                }
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
          await new Promise((resolve) => window.setTimeout(resolve, 1500));
        }
        if (!cancelled) {
          setGenJob({
            status: 'failed',
            progress: 78,
            stageIndex: 1,
            failure: {
              kind: 'temporary',
              detail: '렌더링 확인 시간이 초과되었어요. 잠시 후 다시 확인해 주세요.',
            },
          });
        }
      };

      void run();
    },
    [appendLedgerEntry, appendNotification, creditsPerVideo, queryClient, walletCredits],
  );

  const openExistingProject = useCallback(
    async (pid: string, target: 'continue' | 'download') => {
      try {
        const res = await getProjectV1ProjectsProjectIdGet(pid);
        if (res.status !== 200) return;
        const proj = res.data;
        setOverlayScreen(null);
        setProjectId(pid);
        setProductInfo({
          name: proj.product.name,
          intro: (proj.product.verified_facts || []).join(', '),
        });
        const firstType = (proj.selected_types?.[0] as HookType | undefined) ?? 'A';
        setHookType(firstType);
        const selScn =
          proj.scenarios?.find((s) => s.scenario_id === proj.selected_scenario_id) ?? proj.scenarios?.[0];
        if (selScn) {
          setScenarioId(selScn.scenario_id);
          setScenarioText(formatScenarioText(selScn));
        }
        if (proj.filming_guide?.shots?.length) {
          setGuideScenes(
            proj.filming_guide.shots.map((sh) => ({
              instruction: `${sh.title} — ${sh.framing_tip}`,
              duration: `${sh.duration_sec}초`,
            })),
          );
        }
        if (proj.status === 'DELIVERABLE_READY') {
          const deliv = await getDeliverablesV1ProjectsProjectIdDeliverablesGet(pid);
          if (deliv.status === 200 && deliv.data.video?.stream_url) {
            setVideoUrl(deliv.data.video.stream_url);
            setVideoDownloadUrl(deliv.data.video.download_url ?? deliv.data.video.stream_url);
            setGenJob({ status: 'done', progress: 100, stageIndex: 2, remainingSeconds: 0 });
            setCreationStep(target === 'download' ? 'thumbnail' : 'review');
            return;
          }
        }
        if (proj.status === 'RENDERING') {
          setGenJob({ status: 'running', progress: 42, stageIndex: 0, remainingSeconds: 60 });
          setCreationStep('generating');
          pollRenderCompletion(pid, proj.product.name);
          return;
        }
        if (proj.filming_guide?.shots?.length) {
          setCreationStep('upload');
        } else if (selScn) {
          setCreationStep('scenario');
        } else {
          setCreationStep('hook');
        }
      } catch {
        // Stay on current tab if load fails.
      }
    },
    [pollRenderCompletion],
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
      setScenarioText(undefined);
      setScenarioId(null);
      setStoryboardScenes(undefined);
      setCreationStep('scenario');
      if (!projectId) return;
      try {
        const res = await generateScenariosV1ProjectsProjectIdScenariosPost(projectId, {
          types: selected as GenerateScenariosRequest['types'],
          provider: 'google',
          count: 1,
        });
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

  const handleGoStoryboard = useCallback(async () => {
    setCreationStep('storyboard');
    if (!projectId || !scenarioId) return;
    try {
      const res = await generateStoryboardV1ProjectsProjectIdScenariosScenarioIdStoryboardPost(
        projectId,
        scenarioId,
        {
          visual_style: hookType === 'B' ? 'blender_3d_cutaway' : 'blender_clay_diorama',
        },
      );
      if (res.status === 200) {
        setStoryboardScenes(
          res.data.frames.map((f) => ({
            imageUrl: f.image_url ?? undefined,
            caption: f.caption,
          })),
        );
      }
    } catch {
      // Keep skeleton cleanly.
    }
  }, [hookType, projectId, scenarioId]);

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
    async (file: File) => {
      if (!projectId || !auth.user) return;
      setUploadFile(file);
      setVideoUrl(undefined);
      setVideoDownloadUrl(undefined);
      setGenJob({ status: 'queued', progress: 8, stageIndex: 0, remainingSeconds: 110 });
      setCreationStep('generating');

      let failedAsVideoProblem = true;
      try {
        const cleanName = (file.name || 'clip.mp4').replace(/[^a-zA-Z0-9._-]+/g, '_');
        const objKey = `uploads/${auth.user.user_id}/${projectId}/shot_01_${Date.now()}_${cleanName}`;
        const presignRes = await presignUploadV1UploadsPresignPost({
          object_key: objKey,
          content_type: file.type || 'video/mp4',
        });
        if (presignRes.status !== 200) {
          throw new Error('업로드 주소를 발급받지 못했어요.');
        }

        const putRes = await fetch(presignRes.data.upload_url, {
          method: 'PUT',
          headers: { 'Content-Type': file.type || 'video/mp4' },
          body: file,
          credentials: 'include',
        });
        if (!putRes.ok) {
          throw new Error(`올린 영상을 전송하지 못했어요 (HTTP ${putRes.status})`);
        }

        const completeRes = await completeUploadsV1ProjectsProjectIdUploadsCompletePost(projectId, {
          clips: [
            {
              shot_no: 1,
              object_key: presignRes.data.object_key,
              file_size_bytes: file.size,
            },
          ],
        });
        if (completeRes.status !== 200) {
          throw new Error('올린 영상의 길이와 해상도를 확인할 수 없어요.');
        }

        failedAsVideoProblem = false;
        setGenJob({ status: 'running', progress: 20, stageIndex: 0, remainingSeconds: 90 });

        const renderRes = await createRenderV1ProjectsProjectIdRendersPost(projectId, {
          scenario_id: scenarioId,
          selected_type: hookType as CreateRenderRequestSelectedType,
          skip_drafts: !scenarioId,
          resolution: '720p',
          dry_run: false,
        });
        if (renderRes.status !== 202) {
          throw new Error('영상 제작 요청에 실패했어요.');
        }

        const remaining = Math.max(0, walletCredits - creditsPerVideo);
        appendLedgerEntry({
          kind: 'use',
          amount: -creditsPerVideo,
          balance: remaining,
          productName: productInfo.name || '내 영상',
        });
        void queryClient.invalidateQueries({ queryKey: getGetWalletV1BillingWalletGetQueryKey() });
        pollRenderCompletion(projectId, productInfo.name);
      } catch (err) {
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
      pollRenderCompletion,
      productInfo.name,
      projectId,
      queryClient,
      scenarioId,
      walletCredits,
    ],
  );

  const handleDownloadThumbnail = useCallback(
    async (_templateId: string | null, caption: string) => {
      if (!projectId) return;
      const lines = caption
        .split('\n')
        .map((s) => s.trim())
        .filter(Boolean)
        .slice(0, 2);
      const res = await customFetch<{
        status: number;
        data: { download_url?: string | null; image_url?: string | null };
      }>(`/v1/projects/${projectId}/thumbnail`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          headline_lines: lines.length > 0 ? lines : [productInfo.name || '지금 확인'],
          style: 'stroke_bold',
        }),
      });
      const url = res.data?.download_url || res.data?.image_url;
      if (url) {
        triggerFileDownload(url, 'cover.png');
      }
    },
    [productInfo.name, projectId],
  );

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

  let screen;
  if (auth.status === 'loading') {
    screen =
      activeTab === 'profile' ? (
        <ProfileScreen
          isLoading
          themeMode={themeMode}
          onThemeModeChange={setThemeMode}
          onNavigate={handleNavigate}
        />
      ) : (
        <OnboardingScreen
          footer={
            <p className="n-small n-muted" role="status" style={{ textAlign: 'center', margin: 0 }}>
              로그인 상태를 확인하고 있어요...
            </p>
          }
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
          signInSlot={<GoogleSignInButton theme={gisTheme} />}
        />
      ) : authEntryStep === 'login' ? (
        <LoginScreen
          showcase={SAMPLE_LOGIN_SHOWCASE}
          isSigningIn={auth.isSubmitting}
          hasError={Boolean(auth.error)}
          signInSlot={<GoogleSignInButton theme={gisTheme} />}
        />
      ) : (
        <OnboardingScreen onStart={() => setAuthEntryStep('login')} />
      );
  } else if (needsSignup && !termsAgreed) {
    screen = (
      <LoginScreen
        showcase={SAMPLE_LOGIN_SHOWCASE}
        isTermsOpen
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
        onNicknameChange={(name) => {
          if (nicknameTimerRef.current) {
            window.clearTimeout(nicknameTimerRef.current);
          }
          setNicknameStatus('checking');
          nicknameTimerRef.current = window.setTimeout(() => {
            setNicknameStatus(name.trim() === '도마왕' ? 'taken' : 'available');
          }, 300);
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
          onBack={() => setCreationStep('product')}
          onNext={(selected) => {
            void handleHookNext(selected);
          }}
          onSkipToVideo={() => {
            setCreationStep('guide');
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
          initialFile={uploadFile}
          cost={creditsPerVideo}
          credits={wallet?.credits}
          onBack={() => setCreationStep('guide')}
          onReviewGuide={() => setCreationStep('guide')}
          onCreate={(file) => {
            void handleUploadAndRender(file);
          }}
          onCharge={(file, shortfall) => {
            setUploadFile(file);
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
            if (!uploadFile) {
              setCreationStep('upload');
              return;
            }
            const currentCredits = wallet?.credits ?? 0;
            if (currentCredits < creditsPerVideo) {
              openCharge('upload', creditsPerVideo - currentCredits);
            } else {
              void handleUploadAndRender(uploadFile);
            }
          }}
          onReupload={() => setCreationStep('upload')}
          onReviewGuide={() => setCreationStep('guide')}
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
      const currentPublic = Boolean(projectId && publicProjectIds[projectId]);
      screen = (
        <ThumbnailDownloadScreen
          templates={SAMPLE_THUMBNAIL_TEMPLATES}
          initialCaption={productInfo.name || ''}
          initialIsPublic={currentPublic}
          needsPublishConsent={!currentPublic}
          onPublicChange={(next) => {
            if (!projectId) return;
            setPublicProjectIds((prev) => ({ ...prev, [projectId]: next }));
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
          expiring={SAMPLE_CREDIT_EXPIRING}
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
          ? sampleCreator(overlayScreen.creatorName || '도마왕').videos
          : filterCommunityByType(SAMPLE_COMMUNITY, communityHookType);
      screen = (
        <CommunityViewerScreen
          items={viewerItems}
          initialId={overlayScreen.videoId}
          share={shareHandlers}
          comments={commentsByVideo}
          myName={displayName}
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
      const { profile, videos } = sampleCreator(overlayScreen.name);
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
          items={filterCommunityByType(SAMPLE_COMMUNITY, communityHookType)}
          hookType={communityHookType}
          onHookTypeChange={setCommunityHookType}
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
          onDeleteAccount={() => {
            renderPollCancelRef.current?.();
            setCreationStep(null);
            setOverlayScreen(null);
            setChargeState(null);
            setAuthEntryStep('onboarding');
            void auth.logout();
          }}
        />
      );
    } else {
      screen = (
        <HomeScreen
          inProgress={inProgress}
          completed={completed}
          banners={SAMPLE_BANNERS}
          credits={wallet?.credits}
          unreadCount={notifications.filter((n) => !n.isRead).length}
          onNotificationsClick={() => setOverlayScreen({ type: 'notifications' })}
          onCreditClick={() => openCharge('home')}
          profile={profileUser}
          onProfileClick={() => setActiveTab('profile')}
          onCreate={() => startNewCreation('A')}
          onContinue={(id) => {
            void openExistingProject(id, 'continue');
          }}
          onDownloadAgain={(id) => {
            void openExistingProject(id, 'download');
          }}
          feed={SAMPLE_COMMUNITY.slice(0, feedCount)}
          feedHasMore={feedCount < SAMPLE_COMMUNITY.length}
          onLoadMoreFeed={() =>
            setFeedCount((count) => Math.min(SAMPLE_COMMUNITY.length, count + 4))
          }
          onOpenFeed={(videoId) =>
            setOverlayScreen({ type: 'communityViewer', from: 'home', videoId })
          }
          onOpenCreator={(creatorName) =>
            setOverlayScreen({
              type: 'creator',
              name: creatorName,
              returnTo: { type: 'home' },
            })
          }
          onRemixFeed={(video) => startNewCreation(video.hookType)}
          onSeeAllFeed={() => setActiveTab('community')}
          share={shareHandlers}
          comments={commentsByVideo}
          onAddComment={handleAddComment}
          onDeleteComment={handleDeleteComment}
          onNavigate={handleNavigate}
          onSeeAllMyVideos={() => {
            setMyTab('inProgress');
            setActiveTab('myVideos');
          }}
        />
      );
    }
  }

  return (
    <div className="napda-app-shell">
      <NapdaProvider mode={themeMode}>{screen}</NapdaProvider>
    </div>
  );
}

export default App;
