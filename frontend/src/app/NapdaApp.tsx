import { useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { NapdaApiError } from '../api/mutator';
import { useAuthLogoutV1AuthLogoutPost, useAuthMeV1AuthMeGet } from '../api/generated/auth/auth';
import { useEstimateCreditsV1ProjectsProjectIdEstimatePost } from '../api/generated/credits/credits';
import { usePresignUploadV1UploadsPresignPost } from '../api/generated/default/default';
import { useGetDeliverablesV1ProjectsProjectIdDeliverablesGet } from '../api/generated/delivery/delivery';
import { useCreateFilmingGuideV1ProjectsProjectIdFilmingGuidePost } from '../api/generated/filming-guide/filming-guide';
import { useCreateRenderV1ProjectsProjectIdRendersPost } from '../api/generated/generation/generation';
import {
  useGenerateScenariosV1ProjectsProjectIdScenariosPost,
  useGenerateStoryboardV1ProjectsProjectIdScenariosScenarioIdStoryboardPost,
  useSelectScenarioV1ProjectsProjectIdScenariosScenarioIdSelectPost,
} from '../api/generated/planning/planning';
import {
  getListProjectsV1ProjectsGetQueryKey,
  getProjectV1ProjectsProjectIdGet,
  useCreateProductInfoV1ProductInfoPost,
  useCreateProjectV1ProjectsPost,
  useListProjectsV1ProjectsGet,
} from '../api/generated/projects/projects';
import { useCompleteUploadsV1ProjectsProjectIdUploadsCompletePost } from '../api/generated/uploads/uploads';
import type { FilmingGuideShot, ScenarioItem, StoryboardFrame } from '../api/generated/model';
import { ConfirmSheet, type NavTab } from '../ui/components';
import type { ThemeSetting } from '../ui/NapdaProvider';
import { CommunityScreen } from '../ui/screens/CommunityScreen';
import type { HookType } from '../ui/screens/flowData';
import { HomeScreen } from '../ui/screens/HomeScreen';
import { HookTypeScreen } from '../ui/screens/HookTypeScreen';
import { MyVideosScreen, type MyVideosTab } from '../ui/screens/MyVideosScreen';
import { OnboardingScreen } from '../ui/screens/OnboardingScreen';
import { ProductInfoScreen, type ProductInfo } from '../ui/screens/ProductInfoScreen';
import { ProfileScreen } from '../ui/screens/ProfileScreen';
import { SAMPLE_THUMBNAIL_TEMPLATES } from '../ui/screens/sampleProjects';
import { ScenarioScreen } from '../ui/screens/ScenarioScreen';
import { ShootingGuideScreen } from '../ui/screens/ShootingGuideScreen';
import { StoryboardScreen } from '../ui/screens/StoryboardScreen';
import { ThumbnailDownloadScreen } from '../ui/screens/ThumbnailDownloadScreen';
import { UploadVideoScreen } from '../ui/screens/UploadVideoScreen';
import { VideoReviewScreen } from '../ui/screens/VideoReviewScreen';
import {
  readVideoMeta,
  resumeStepFor,
  scenarioText,
  splitProjects,
  toApiCategory,
  toGuideScenes,
  toStoryboardScenes,
  webUrl,
} from './mappers';

type Step =
  | 'onboarding'
  | 'home'
  | 'myVideos'
  | 'community'
  | 'profile'
  | 'product'
  | 'hook'
  | 'scenario'
  | 'storyboard'
  | 'guide'
  | 'upload'
  | 'review'
  | 'thumbnail';

/** 지금 만들고 있는 영상 한 편에 대해 서버에서 받아 둔 값 */
interface Draft {
  productInfoId?: string;
  projectId?: string;
  hookTypes: HookType[];
  scenarios: ScenarioItem[];
  scenarioId?: string;
  frames?: StoryboardFrame[];
  shots?: FilmingGuideShot[];
  /** 시안 없이 바로 만들기 (flow_mode: skip_drafts) */
  isSkip: boolean;
  /** 견적 API가 알려 준 크레딧 */
  cost?: number;
}

const EMPTY_DRAFT: Draft = { hookTypes: [], scenarios: [], isSkip: false };

interface Notice {
  title: string;
  description: string;
  /** 있으면 "다시 시도" 버튼을 보여 준다 */
  retry?: () => void;
}

const ONBOARDED_KEY = 'napda.onboarded';
const PROJECTS_PARAMS = { limit: 50 };

/** 생성 클라이언트는 실패하면 던지므로, 성공 응답만 좁혀서 data를 꺼낸다 */
function unwrap<R extends { status: number; data: unknown }, S extends R['status']>(res: R, status: S): Extract<R, { status: S }>['data'] {
  if (res.status !== status) throw new Error(`서버가 예상과 다른 응답(${res.status})을 보냈어요.`);
  return (res as Extract<R, { status: S }>).data;
}

function errorMessage(error: unknown): string {
  if (error instanceof NapdaApiError) return error.message;
  if (error instanceof TypeError) return '서버에 연결하지 못했어요. 백엔드가 켜져 있는지 확인해 주세요.';
  return error instanceof Error ? error.message : '알 수 없는 문제가 생겼어요.';
}

export interface NapdaAppProps {
  themeMode: ThemeSetting;
  onThemeModeChange: (mode: ThemeSetting) => void;
}

/** 디자인 화면(src/ui/screens)을 Orval 생성 훅으로 백엔드에 연결한 앱 본체 */
export function NapdaApp({ themeMode, onThemeModeChange }: NapdaAppProps) {
  const queryClient = useQueryClient();
  const [step, setStep] = useState<Step>(() => (localStorage.getItem(ONBOARDED_KEY) ? 'home' : 'onboarding'));
  const [myTab, setMyTab] = useState<MyVideosTab>('inProgress');
  const [draft, setDraft] = useState<Draft>(EMPTY_DRAFT);
  const [notice, setNotice] = useState<Notice | null>(null);
  const [isAuthNoticeClosed, setIsAuthNoticeClosed] = useState(false);
  const [communityType, setCommunityType] = useState<HookType | null>(null);

  // ----- 조회 -----
  const me = useAuthMeV1AuthMeGet({ query: { retry: false } });
  const projects = useListProjectsV1ProjectsGet(PROJECTS_PARAMS, { query: { enabled: me.isSuccess } });
  const isWatchingRender = Boolean(draft.projectId) && (step === 'review' || step === 'thumbnail');
  const deliverables = useGetDeliverablesV1ProjectsProjectIdDeliverablesGet(draft.projectId ?? '', {
    query: {
      enabled: isWatchingRender,
      retry: false,
      // 영상이 다 만들어지거나 실패할 때까지 5초마다 다시 묻는다
      refetchInterval: (query) => {
        const res = query.state.data;
        const jobStatus = res?.status === 200 ? res.data.status : undefined;
        return query.state.error || jobStatus === 'QC_READY' || jobStatus === 'FAILED' ? false : 5000;
      },
    },
  });

  // ----- 변경 -----
  const createProductInfo = useCreateProductInfoV1ProductInfoPost();
  const createProject = useCreateProjectV1ProjectsPost();
  const generateScenarios = useGenerateScenariosV1ProjectsProjectIdScenariosPost();
  const selectScenario = useSelectScenarioV1ProjectsProjectIdScenariosScenarioIdSelectPost();
  const generateStoryboard = useGenerateStoryboardV1ProjectsProjectIdScenariosScenarioIdStoryboardPost();
  const createFilmingGuide = useCreateFilmingGuideV1ProjectsProjectIdFilmingGuidePost();
  const estimateCredits = useEstimateCreditsV1ProjectsProjectIdEstimatePost();
  const presignUpload = usePresignUploadV1UploadsPresignPost();
  const completeUploads = useCompleteUploadsV1ProjectsProjectIdUploadsCompletePost();
  const createRender = useCreateRenderV1ProjectsProjectIdRendersPost();
  const logout = useAuthLogoutV1AuthLogoutPost();

  const user = me.data?.status === 200 ? me.data.data.user : null;
  const projectList = projects.data?.status === 200 ? projects.data.data.projects : [];
  const { inProgress, completed } = splitProjects(projectList);
  const activeScenario = draft.scenarios.find((s) => s.scenario_id === draft.scenarioId) ?? draft.scenarios[0];
  const hookType: HookType = activeScenario?.type ?? draft.hookTypes[0] ?? 'A';
  const deliverable = deliverables.data?.status === 200 ? deliverables.data.data : undefined;

  const refreshProjects = () => queryClient.invalidateQueries({ queryKey: getListProjectsV1ProjectsGetQueryKey().slice(0, 1) });

  /** 서버 호출을 감싸 실패하면 시트로 알리고, 필요하면 돌아갈 화면으로 보낸다 */
  const attempt = async (title: string, run: () => Promise<void>, onFail?: () => void) => {
    try {
      await run();
    } catch (error) {
      onFail?.();
      setNotice({ title, description: errorMessage(error), retry: () => void attempt(title, run, onFail) });
    }
  };

  const goHome = () => {
    setStep('home');
    void refreshProjects();
  };

  const navigate = (tab: NavTab) => {
    if (tab === 'myVideos') setMyTab('inProgress');
    setStep(tab);
    if (tab === 'home' || tab === 'myVideos') void refreshProjects();
  };

  const startCreate = (initialType?: HookType) => {
    setDraft({ ...EMPTY_DRAFT, hookTypes: initialType ? [initialType] : [] });
    setStep('product');
  };

  // 1단계: 제품 정보 → POST /v1/product-info
  const submitProduct = (value: ProductInfo) => {
    const category = toApiCategory(value.category);
    if (!category) {
      setNotice({ title: '카테고리를 골라 주세요', description: '자취·주방·문구 중 하나를 골라야 시안을 만들 수 있어요.' });
      return;
    }
    void attempt('제품 정보를 저장하지 못했어요', async () => {
      const intro = value.intro.trim();
      const res = await createProductInfo.mutateAsync({
        data: { product: { name: value.name.trim(), category, verified_facts: intro ? [intro] : [] } },
      });
      const info = unwrap(res, 200);
      setDraft((prev) => ({ ...prev, productInfoId: info.product_info_id, projectId: undefined, scenarios: [], scenarioId: undefined }));
      setStep('hook');
    });
  };

  /** 프로젝트가 없으면 만든다 (POST /v1/projects) */
  const ensureProject = async (types: HookType[], isSkip: boolean): Promise<string> => {
    if (draft.projectId) return draft.projectId;
    if (!draft.productInfoId) throw new Error('제품 정보부터 다시 입력해 주세요.');
    const res = await createProject.mutateAsync({
      data: { product_info_id: draft.productInfoId, selected_types: types, flow_mode: isSkip ? 'skip_drafts' : 'guide_first' },
    });
    const projectId = unwrap(res, 201).project_id;
    setDraft((prev) => ({ ...prev, projectId }));
    return projectId;
  };

  /** 3단계: 시나리오 글 → POST /v1/projects/{id}/scenarios. 화면은 먼저 넘기고 글이 오면 채운다 */
  const loadScenarios = async (projectId: string, types: HookType[]) => {
    setDraft((prev) => ({ ...prev, projectId, hookTypes: types, isSkip: false, scenarios: [], scenarioId: undefined, frames: undefined, shots: undefined }));
    setStep('scenario');
    const res = await generateScenarios.mutateAsync({ projectId, data: { types } });
    const scenarios = unwrap(res, 200).scenarios;
    setDraft((prev) => ({ ...prev, scenarios, scenarioId: scenarios[0]?.scenario_id }));
  };

  // 2단계: 유형 선택 → 프로젝트 만들고 시나리오 요청
  const submitHookTypes = (selected: HookType[]) => {
    void attempt(
      '시나리오를 만들지 못했어요',
      async () => loadScenarios(await ensureProject(selected, false), selected),
      () => setStep('hook'),
    );
  };

  /** 견적(POST /v1/projects/{id}/estimate)을 받아 두고 영상 올리기로 간다. 견적을 못 받으면 "크레딧 미정"으로 둔다 */
  const openUpload = (projectId: string, target: { scenarioId?: string; selectedType?: HookType }) => {
    setStep('upload');
    estimateCredits
      .mutateAsync({ projectId, data: { scenario_id: target.scenarioId, selected_type: target.selectedType } })
      .then((res) => setDraft((prev) => ({ ...prev, cost: unwrap(res, 200).total_estimated_credits })))
      .catch(() => setDraft((prev) => ({ ...prev, cost: undefined })));
  };

  // 2단계의 "시안 없이 냅다 만들기": 유형 하나로 프로젝트를 만들고 바로 영상 올리기로
  const skipToVideo = () => {
    const selectedType = draft.hookTypes[0] ?? 'A';
    void attempt('프로젝트를 만들지 못했어요', async () => {
      const projectId = await ensureProject([selectedType], true);
      setDraft((prev) => ({ ...prev, hookTypes: [selectedType], isSkip: true }));
      openUpload(projectId, { selectedType });
    });
  };

  // 4단계: 그림 콘티 → POST …/scenarios/{sid}/storyboard
  const openStoryboard = () => {
    const { projectId } = draft;
    if (!projectId || !activeScenario) return;
    const scenarioId = activeScenario.scenario_id;
    setDraft((prev) => ({ ...prev, frames: undefined }));
    setStep('storyboard');
    void attempt(
      '그림 콘티를 만들지 못했어요',
      async () => {
        const res = await generateStoryboard.mutateAsync({ projectId, scenarioId, data: {} });
        const frames = unwrap(res, 200).frames;
        setDraft((prev) => ({ ...prev, frames }));
      },
      () => setStep('scenario'),
    );
  };

  // 5단계: 촬영 가이드 → 시나리오 선택(POST …/select) 후 POST …/filming-guide
  const openGuide = () => {
    const { projectId } = draft;
    if (!projectId || !activeScenario) return;
    const scenarioId = activeScenario.scenario_id;
    const from = step;
    setDraft((prev) => ({ ...prev, scenarioId, shots: undefined }));
    setStep('guide');
    void attempt(
      '촬영 가이드를 만들지 못했어요',
      async () => {
        await selectScenario.mutateAsync({ projectId, scenarioId });
        const res = await createFilmingGuide.mutateAsync({ projectId, data: { scenario_id: scenarioId } });
        const shots = unwrap(res, 200).shots;
        setDraft((prev) => ({ ...prev, shots }));
      },
      () => setStep(from),
    );
  };

  // 6단계: 영상 올리기 → presign → PUT → uploads/complete → renders
  const createVideo = (file: File) => {
    const { projectId } = draft;
    if (!projectId) return;
    void attempt('영상을 만들지 못했어요', async () => {
      const safeName = file.name.replace(/[^\w.-]+/g, '_');
      const objectKey = `projects/${projectId}/uploads/shot_01_${Date.now()}_${safeName}`;
      const contentType = file.type || 'video/mp4';
      const presigned = unwrap(await presignUpload.mutateAsync({ data: { object_key: objectKey, content_type: contentType } }), 200);
      const uploadUrl = webUrl(presigned.upload_url);
      if (!uploadUrl) {
        throw new Error('이 서버는 로컬 저장소를 쓰고 있어 브라우저에서 영상을 올릴 수 없어요. 백엔드에 S3·R2 저장소(STORAGE_BACKEND=s3)를 설정해 주세요.');
      }
      const put = await fetch(uploadUrl, { method: 'PUT', headers: { 'Content-Type': contentType }, body: file });
      if (!put.ok) throw new Error(`영상을 올리지 못했어요 (HTTP ${put.status}).`);

      const meta = await readVideoMeta(file);
      await completeUploads.mutateAsync({
        projectId,
        data: { clips: [{ shot_no: 1, object_key: objectKey, file_size_bytes: file.size, ...meta }] },
      });
      await createRender.mutateAsync({
        projectId,
        data: draft.isSkip || !activeScenario ? { skip_drafts: true, selected_type: hookType } : { scenario_id: activeScenario.scenario_id },
      });
      setStep('review');
    });
  };

  /** 홈·내 영상의 "이어하기 / 다시 받기": GET /v1/projects/{id} 로 상태를 되살려 알맞은 화면을 연다 */
  const resumeProject = (projectId: string) => {
    void attempt('프로젝트를 불러오지 못했어요', async () => {
      const detail = unwrap(await getProjectV1ProjectsProjectIdGet(projectId), 200);
      const scenarios = detail.scenarios ?? [];
      const scenario = scenarios.find((s) => s.scenario_id === detail.selected_scenario_id) ?? scenarios[0];
      const isSkip = detail.flow_mode === 'skip_drafts';
      const next = resumeStepFor(detail.status, detail.flow_mode);
      if (next === 'scenario' && scenarios.length === 0) {
        await loadScenarios(projectId, detail.selected_types);
        return;
      }
      setDraft({
        projectId,
        hookTypes: detail.selected_types,
        scenarios,
        scenarioId: scenario?.scenario_id,
        frames: scenario?.storyboard_frames,
        shots: detail.filming_guide?.shots,
        isSkip,
      });
      if (next === 'upload') {
        openUpload(projectId, isSkip || !scenario ? { selectedType: detail.selected_types[0] } : { scenarioId: scenario.scenario_id });
      } else {
        setStep(next);
      }
    });
  };

  const signOut = () => {
    void attempt('로그아웃하지 못했어요', async () => {
      await logout.mutateAsync();
      queryClient.clear();
      setStep('home');
    });
  };

  const openDownload = (url: string | null | undefined, what: string) => {
    const target = webUrl(url);
    if (target) window.open(target, '_blank', 'noopener');
    else setNotice({ title: `${what}을 아직 받을 수 없어요`, description: '서버가 내려받을 주소를 주지 않았어요. 영상이 다 만들어졌는지 확인해 주세요.' });
  };

  const isRenderFailed = step === 'review' && deliverable?.status === 'FAILED';
  const isSignedOut = me.isError && !isAuthNoticeClosed;

  const screen = (() => {
    switch (step) {
      case 'onboarding':
        return (
          <OnboardingScreen
            onStart={() => {
              localStorage.setItem(ONBOARDED_KEY, '1');
              setStep('home');
            }}
          />
        );
      case 'home':
        return (
          <HomeScreen
            profile={user ? { name: user.name ?? user.email, imageUrl: user.picture ?? undefined } : undefined}
            onProfileClick={() => setStep('profile')}
            onNavigate={navigate}
            inProgress={inProgress}
            completed={completed}
            onCreate={() => startCreate()}
            onContinue={resumeProject}
            onDownloadAgain={resumeProject}
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
            inProgress={inProgress}
            completed={completed}
            initialTab={myTab}
            onNavigate={navigate}
            onContinue={resumeProject}
            onDownloadAgain={resumeProject}
          />
        );
      case 'community':
        // 커뮤니티 목록 API가 아직 없어 빈 목록으로 둔다
        return (
          <CommunityScreen
            items={[]}
            hookType={communityType}
            onHookTypeChange={setCommunityType}
            onCreate={() => startCreate(communityType ?? undefined)}
            onNavigate={navigate}
          />
        );
      case 'profile':
        return (
          <ProfileScreen
            user={user ? { name: user.name ?? undefined, email: user.email, imageUrl: user.picture ?? undefined } : null}
            isLoading={me.isPending}
            videoCounts={{ inProgress: inProgress.length, completed: completed.length }}
            themeMode={themeMode}
            onThemeModeChange={onThemeModeChange}
            onNavigate={navigate}
            onOpenMyVideos={(tab) => {
              setMyTab(tab);
              setStep('myVideos');
            }}
            onLogout={signOut}
          />
        );
      case 'product':
        return <ProductInfoScreen onBack={goHome} onNext={submitProduct} />;
      case 'hook':
        return (
          <HookTypeScreen
            initialSelected={draft.hookTypes}
            onBack={() => setStep('product')}
            onNext={submitHookTypes}
            onSkipToVideo={skipToVideo}
          />
        );
      case 'scenario':
        return (
          <ScenarioScreen
            hookType={hookType}
            scenario={activeScenario ? scenarioText(activeScenario) : undefined}
            onBack={() => setStep('hook')}
            onShootingGuide={openGuide}
            onStoryboard={openStoryboard}
          />
        );
      case 'storyboard':
        return (
          <StoryboardScreen
            hookType={hookType}
            scenes={draft.frames ? toStoryboardScenes(draft.frames) : undefined}
            onBack={() => setStep('scenario')}
            onShootingGuide={openGuide}
          />
        );
      case 'guide':
        return (
          <ShootingGuideScreen
            scenes={draft.shots ? toGuideScenes(draft.shots) : undefined}
            onBack={() => setStep('scenario')}
            onUpload={() => draft.projectId && openUpload(draft.projectId, { scenarioId: activeScenario?.scenario_id })}
          />
        );
      case 'upload':
        return (
          <UploadVideoScreen
            hookType={hookType}
            cost={draft.cost}
            onBack={() => (draft.shots ? setStep('guide') : goHome())}
            onReviewGuide={() => (draft.shots ? setStep('guide') : undefined)}
            onCreate={createVideo}
          />
        );
      case 'review':
        return (
          <VideoReviewScreen
            videoUrl={webUrl(deliverable?.video?.stream_url)}
            onBack={goHome}
            onMakeThumbnail={() => setStep('thumbnail')}
          />
        );
      case 'thumbnail':
        return (
          <ThumbnailDownloadScreen
            templates={SAMPLE_THUMBNAIL_TEMPLATES}
            initialCaption={activeScenario?.hook_title ?? ''}
            onBack={() => setStep('review')}
            onDownloadVideo={() => openDownload(deliverable?.video?.download_url, '영상')}
            onDownloadThumbnail={() => openDownload(deliverable?.thumbnail?.download_url, '썸네일')}
          />
        );
    }
  })();

  return (
    <>
      {screen}
      <ConfirmSheet
        isOpen={notice !== null}
        title={notice?.title ?? ''}
        description={notice?.description}
        confirmLabel={notice?.retry ? '다시 시도' : '확인'}
        cancelLabel="닫기"
        onConfirm={() => {
          const retry = notice?.retry;
          setNotice(null);
          retry?.();
        }}
        onClose={() => setNotice(null)}
      />
      <ConfirmSheet
        isOpen={notice === null && isRenderFailed}
        title="영상을 만들다가 멈췄어요"
        description="찍은 영상을 다시 올려서 한 번 더 만들어 볼 수 있어요."
        confirmLabel="다시 올리기"
        cancelLabel="홈으로"
        onConfirm={() => setStep('upload')}
        onClose={goHome}
      />
      <ConfirmSheet
        isOpen={notice === null && !isRenderFailed && isSignedOut && step !== 'onboarding'}
        title="로그인이 필요해요"
        description={`내 정보를 불러오지 못했어요 (${errorMessage(me.error)}). 로그인 화면은 아직 연결 전이라, 개발 중에는 VITE_DEV_ACCESS_TOKEN에 개발용 토큰을 넣어 주세요.`}
        confirmLabel="다시 확인"
        cancelLabel="닫기"
        onConfirm={() => void me.refetch()}
        onClose={() => setIsAuthNoticeClosed(true)}
      />
    </>
  );
}
