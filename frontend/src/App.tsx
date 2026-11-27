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
import type { CreditPackage, NavTab } from './ui/components';
import {
  ChargeResultScreen,
  CommunityScreen,
  CreditChargeScreen,
  HomeScreen,
  HookTypeScreen,
  MyVideosScreen,
  OnboardingScreen,
  ProductInfoScreen,
  ProfileScreen,
  ScenarioScreen,
  ShootingGuideScreen,
  StoryboardScreen,
  ThumbnailDownloadScreen,
  UploadVideoScreen,
  VideoReviewScreen,
  type CompletedProject,
  type HookType,
  type InProgressProject,
  type MyVideosTab,
  type ProductInfo,
} from './ui/screens';
import type { GuideScene } from './ui/screens/ShootingGuideScreen';
import type { StoryboardScene } from './ui/screens/StoryboardScreen';
import {
  SAMPLE_BANNERS,
  SAMPLE_COMMUNITY,
  SAMPLE_CREDIT_PACKAGES,
  SAMPLE_CREDITS_PER_VIDEO,
  SAMPLE_THUMBNAIL_TEMPLATES,
  filterCommunityByType,
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
    const body = (b.caption || b.narration || b.visual || '').replace(/\*\*/g, '').trim();
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

const STAGE_LABEL_KO: Record<string, string> = {
  QUEUED: '작업 대기열에 올렸어요…',
  ANALYZING: '올린 영상의 길이와 구도를 분석하고 있어요…',
  PLANNING: '템플릿 훅과 한국어 내레이션을 맞추고 있어요…',
  LINTING: '광고 품질과 자막 규칙을 점검하고 있어요…',
  GENERATING: '오디오와 영상 소스를 준비하고 있어요…',
  ASSEMBLING: '훅 템플릿과 본편 영상을 깔끔하게 이어 붙이고 있어요…',
};

type ChargeFrom = 'home' | 'profile' | 'upload';
type CreationStep =
  | 'product'
  | 'hook'
  | 'scenario'
  | 'storyboard'
  | 'guide'
  | 'upload'
  | 'review'
  | 'thumbnail';

interface ChargeFlowState {
  stage: 'charge' | 'confirming' | 'done';
  from: ChargeFrom;
  before: number;
  added: number;
  isPaying: boolean;
  hasPaymentError: boolean;
}

export function App() {
  const auth = useAuth();
  const queryClient = useQueryClient();
  const [themeMode, setThemeMode] = useState<ThemeSetting>('system');
  const [activeTab, setActiveTab] = useState<NavTab>('home');
  const [myTab, setMyTab] = useState<MyVideosTab>('inProgress');
  const [communityHookType, setCommunityHookType] = useState<HookType | null>(null);
  const [chargeState, setChargeState] = useState<ChargeFlowState | null>(null);

  // 8-step creation flow state
  const [creationStep, setCreationStep] = useState<CreationStep | null>(null);
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
  const [isRendering, setIsRendering] = useState(false);
  const [renderStatusText, setRenderStatusText] = useState<string | undefined>(undefined);
  const [renderError, setRenderError] = useState<string | undefined>(undefined);

  const pollCancelRef = useRef<(() => void) | null>(null);
  const renderPollCancelRef = useRef<(() => void) | null>(null);

  useEffect(() => {
    return () => {
      pollCancelRef.current?.();
      renderPollCancelRef.current?.();
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

  const startNewCreation = useCallback((initialType: HookType = 'A') => {
    renderPollCancelRef.current?.();
    setChargeState(null);
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
    setIsRendering(false);
    setRenderStatusText(undefined);
    setRenderError(undefined);
    setCreationStep('product');
  }, []);

  const pollRenderCompletion = useCallback(
    (pid: string) => {
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
              const jobObj = proj.latest_job as { status?: string; stage?: string; error?: string } | null | undefined;
              const stageKey = jobObj?.stage || '';
              if (STAGE_LABEL_KO[stageKey]) {
                setRenderStatusText(STAGE_LABEL_KO[stageKey]);
              }
              if (proj.status === 'DELIVERABLE_READY' || jobObj?.status === 'QC_READY') {
                const delivRes = await getDeliverablesV1ProjectsProjectIdDeliverablesGet(pid);
                if (cancelled) return;
                if (delivRes.status === 200 && delivRes.data.video?.stream_url) {
                  setVideoUrl(delivRes.data.video.stream_url);
                  setVideoDownloadUrl(delivRes.data.video.download_url ?? delivRes.data.video.stream_url);
                  setIsRendering(false);
                  setRenderError(undefined);
                  void queryClient.invalidateQueries({ queryKey: getListProjectsV1ProjectsGetQueryKey() });
                  void queryClient.invalidateQueries({ queryKey: getGetWalletV1BillingWalletGetQueryKey() });
                  return;
                }
              }
              if (proj.status === 'FAILED' || jobObj?.status === 'FAILED') {
                setRenderError(jobObj?.error || '영상 합성 중 오류가 발생했어요.');
                setIsRendering(false);
                return;
              }
            }
          } catch (err) {
            setRenderError(err instanceof Error ? err.message : '상태를 불러오지 못했어요.');
          }
          await new Promise((resolve) => window.setTimeout(resolve, 1500));
        }
        if (!cancelled) {
          setRenderError('렌더링 확인 시간이 초과되었어요. 내 영상에서 다시 확인해 주세요.');
          setIsRendering(false);
        }
      };

      void run();
    },
    [queryClient],
  );

  const openExistingProject = useCallback(
    async (pid: string, target: 'continue' | 'download') => {
      try {
        const res = await getProjectV1ProjectsProjectIdGet(pid);
        if (res.status !== 200) return;
        const proj = res.data;
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
            setIsRendering(false);
            setCreationStep(target === 'download' ? 'thumbnail' : 'review');
            return;
          }
        }
        if (proj.status === 'RENDERING') {
          setIsRendering(true);
          setCreationStep('review');
          pollRenderCompletion(pid);
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

  const handleProductNext = useCallback(async (info: ProductInfo) => {
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
  }, [hookType, projectId, queryClient]);

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
      // Keep skeleton or empty scenes cleanly.
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
      setRenderError(undefined);
      setIsRendering(true);
      setRenderStatusText('영상을 안전하게 올리고 있어요…');
      setCreationStep('review');

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
          throw new Error(`영상 파일 전송 실패 (HTTP ${putRes.status})`);
        }

        setRenderStatusText('올린 영상의 길이와 해상도를 확인하고 있어요…');
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
          throw new Error('업로드 검증에 실패했어요.');
        }

        setRenderStatusText('영상 제작 작업을 시작했어요…');
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
        pollRenderCompletion(projectId);
      } catch (err) {
        setRenderError(err instanceof Error ? err.message : '영상 제작 요청 중 오류가 발생했어요.');
        setIsRendering(false);
      }
    },
    [auth.user, hookType, pollRenderCompletion, projectId, scenarioId],
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
    (from: ChargeFrom) => {
      pollCancelRef.current?.();
      setChargeState({
        stage: 'charge',
        from,
        before: wallet?.credits ?? 0,
        added: 0,
        isPaying: false,
        hasPaymentError: false,
      });
    },
    [wallet?.credits],
  );

  const pollOrderCompletion = useCallback(
    (orderId: string, expectedAdded: number) => {
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
                queryClient.setQueryData(getGetWalletV1BillingWalletGetQueryKey(), {
                  data: res.data.wallet,
                  status: 200,
                  headers: res.headers,
                });
                setChargeState((prev) =>
                  prev
                    ? {
                        ...prev,
                        stage: 'done',
                        added: res.data.credits || expectedAdded,
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
    [queryClient],
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
            pollOrderCompletion(checkout.order_id, pkg.credits);
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

  const handleNavigate = (tab: NavTab) => {
    setCreationStep(null);
    if (tab === 'myVideos') {
      setMyTab('inProgress');
    }
    setActiveTab(tab);
  };

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
      ) : (
        <OnboardingScreen footer={<GoogleSignInButton theme={gisTheme} />} />
      );
  } else {
    const profileUser = {
      name: auth.user.name ?? undefined,
      email: auth.user.email,
      imageUrl: auth.user.picture ?? undefined,
    };

    if (chargeState) {
      if (chargeState.stage === 'charge') {
        screen = (
          <CreditChargeScreen
            credits={wallet?.credits ?? 0}
            packages={creditPackages}
            creditsPerVideo={billingConfig?.credits_per_video ?? SAMPLE_CREDITS_PER_VIDEO}
            isPaying={chargeState.isPaying}
            hasPaymentError={chargeState.hasPaymentError}
            onBack={() => {
              const target = chargeState.from;
              setChargeState(null);
              if (target === 'upload') {
                setCreationStep('upload');
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
          cost={billingConfig?.credits_per_video ?? SAMPLE_CREDITS_PER_VIDEO}
          credits={wallet?.credits}
          onBack={() => setCreationStep('guide')}
          onReviewGuide={() => setCreationStep('guide')}
          onCreate={(file) => {
            void handleUploadAndRender(file);
          }}
          onCharge={(file, _shortfall) => {
            setUploadFile(file);
            openCharge('upload');
          }}
        />
      );
    } else if (creationStep === 'review') {
      screen = (
        <VideoReviewScreen
          videoUrl={videoUrl}
          isRendering={isRendering}
          renderStatusText={renderStatusText}
          errorMessage={renderError}
          onBack={() => {
            renderPollCancelRef.current?.();
            setCreationStep('upload');
          }}
          onMakeThumbnail={() => setCreationStep('thumbnail')}
        />
      );
    } else if (creationStep === 'thumbnail') {
      screen = (
        <ThumbnailDownloadScreen
          templates={SAMPLE_THUMBNAIL_TEMPLATES}
          initialCaption={productInfo.name || ''}
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
          onOpenMyVideos={(tab) => {
            setMyTab(tab);
            setActiveTab('myVideos');
          }}
          onLogout={() => {
            renderPollCancelRef.current?.();
            setCreationStep(null);
            setChargeState(null);
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
