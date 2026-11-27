import { useQueryClient } from '@tanstack/react-query';
import { useCallback, useEffect, useMemo, useRef, useState, useSyncExternalStore } from 'react';
import {
  getBillingOrderV1BillingOrdersOrderIdGet,
  getGetWalletV1BillingWalletGetQueryKey,
  useCreateBillingCheckoutV1BillingCheckoutPost,
  useGetBillingConfigV1BillingConfigGet,
  useGetWalletV1BillingWalletGet,
} from './api/generated/billing/billing';
import { useListProjectsV1ProjectsGet } from './api/generated/projects/projects';
import type {
  CreateCheckoutRequestPackageId,
  ProjectSummary,
  ProjectSummaryStatus,
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
  MyVideosScreen,
  OnboardingScreen,
  ProfileScreen,
  type CompletedProject,
  type HookType,
  type InProgressProject,
  type MyVideosTab,
} from './ui/screens';
import {
  SAMPLE_BANNERS,
  SAMPLE_COMMUNITY,
  SAMPLE_CREDIT_PACKAGES,
  SAMPLE_CREDITS_PER_VIDEO,
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

type ChargeFrom = 'home' | 'profile';

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
  const pollCancelRef = useRef<(() => void) | null>(null);

  useEffect(() => {
    return () => {
      pollCancelRef.current?.();
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
              setChargeState(null);
              setActiveTab(chargeState.from);
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
            onDone={() => {
              const targetTab = chargeState.from;
              setChargeState(null);
              setActiveTab(targetTab);
            }}
          />
        );
      }
    } else if (activeTab === 'myVideos') {
      screen = (
        <MyVideosScreen
          key={`my-videos-${myTab}`}
          inProgress={inProgress}
          completed={completed}
          initialTab={myTab}
          onNavigate={handleNavigate}
        />
      );
    } else if (activeTab === 'community') {
      screen = (
        <CommunityScreen
          items={filterCommunityByType(SAMPLE_COMMUNITY, communityHookType)}
          hookType={communityHookType}
          onHookTypeChange={setCommunityHookType}
          onNavigate={handleNavigate}
        />
      );
    } else if (activeTab === 'profile') {
      screen = (
        <ProfileScreen
          user={profileUser}
          credits={wallet?.credits}
          hasFreeVideo={wallet?.has_free_video}
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
          onNavigate={handleNavigate}
          onSeeAllInProgress={() => {
            setMyTab('inProgress');
            setActiveTab('myVideos');
          }}
          onSeeAllCompleted={() => {
            setMyTab('completed');
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
