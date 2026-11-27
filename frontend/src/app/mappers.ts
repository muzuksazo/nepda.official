import type {
  FilmingGuideShot,
  ProductInputCategory,
  ProjectSummary,
  ProjectSummaryStatus,
  ScenarioItem,
  StoryboardFrame,
} from '../api/generated/model';
import type { CompletedProject, InProgressProject } from '../ui/screens/HomeScreen';
import type { GuideScene } from '../ui/screens/ShootingGuideScreen';
import type { StoryboardScene } from '../ui/screens/StoryboardScreen';

/** 화면의 카테고리 이름(flowData.PRODUCT_CATEGORIES) → API 값 */
const CATEGORY_BY_LABEL: Record<string, ProductInputCategory> = {
  자취: 'living',
  주방: 'kitchen',
  문구: 'stationery',
};

export function toApiCategory(label: string | null): ProductInputCategory | undefined {
  return label ? CATEGORY_BY_LABEL[label] : undefined;
}

/** 만들기 흐름에서 이어서 열 화면 */
export type ResumeStep = 'scenario' | 'storyboard' | 'upload' | 'review' | 'thumbnail';

interface StatusView {
  /** 카드에 보여 줄 한 줄 상태 */
  status: string;
  /** 8단계 중 끝낸 단계 수 */
  completedSteps: number;
  nextStep: string;
  resume: ResumeStep;
}

const STATUS_VIEW: Record<ProjectSummaryStatus, StatusView> = {
  PRODUCT_SAVED: { status: '훅 유형을 골랐어요', completedSteps: 2, nextStep: '시나리오 글 보기', resume: 'scenario' },
  SCENARIOS_READY: { status: '시나리오 글을 확인하고 있어요', completedSteps: 3, nextStep: '촬영 가이드 받기', resume: 'scenario' },
  STORYBOARD_READY: { status: '그림 콘티까지 봤어요', completedSteps: 4, nextStep: '촬영 가이드 받기', resume: 'storyboard' },
  GUIDE_READY: { status: '촬영 가이드까지 받았어요', completedSteps: 5, nextStep: '찍은 영상 올리기', resume: 'upload' },
  HOOK_RENDERING: { status: '훅을 만들고 있어요', completedSteps: 5, nextStep: '찍은 영상 올리기', resume: 'upload' },
  HOOK_READY: { status: '훅을 만들었어요', completedSteps: 5, nextStep: '찍은 영상 올리기', resume: 'upload' },
  UPLOADS_READY: { status: '찍은 영상을 올렸어요', completedSteps: 6, nextStep: '영상 만들기', resume: 'upload' },
  RENDERING: { status: '영상을 만들고 있어요', completedSteps: 6, nextStep: '영상 확인하기', resume: 'review' },
  DELIVERABLE_READY: { status: '영상과 썸네일을 만들었어요', completedSteps: 8, nextStep: '다시 받기', resume: 'thumbnail' },
  FAILED: { status: '만들다가 멈췄어요', completedSteps: 6, nextStep: '다시 만들기', resume: 'upload' },
};

export function resumeStepFor(status: ProjectSummaryStatus, flowMode: ProjectSummary['flow_mode']): ResumeStep {
  // 시안을 건너뛴 프로젝트는 시나리오가 없으니 바로 영상 올리기로 간다
  if (status === 'PRODUCT_SAVED' && flowMode === 'skip_drafts') return 'upload';
  return STATUS_VIEW[status].resume;
}

/** GET /v1/projects 목록 → 홈·내 영상의 '진행 중'과 '완료' */
export function splitProjects(projects: ProjectSummary[]): { inProgress: InProgressProject[]; completed: CompletedProject[] } {
  const inProgress: InProgressProject[] = [];
  const completed: CompletedProject[] = [];
  for (const project of projects) {
    const view = STATUS_VIEW[project.status];
    if (project.status === 'DELIVERABLE_READY') {
      completed.push({ id: project.project_id, productName: project.product_name, status: view.status });
      continue;
    }
    const isSkip = project.status === 'PRODUCT_SAVED' && project.flow_mode === 'skip_drafts';
    inProgress.push({
      id: project.project_id,
      productName: project.product_name,
      status: view.status,
      completedSteps: view.completedSteps,
      nextStep: isSkip ? '찍은 영상 올리기' : view.nextStep,
    });
  }
  return { inProgress, completed };
}

/** 시나리오 한 편을 화면에 보여 줄 글 한 덩어리로 */
export function scenarioText(scenario: ScenarioItem): string {
  const lines = scenario.beats
    .filter((beat) => beat.role !== 'silence_gap')
    .map((beat) => (beat.narration || beat.caption || beat.visual || '').trim())
    .filter(Boolean);
  return [scenario.hook_title, ...lines].join(' ');
}

const isWebUrl = (url: string | null | undefined): url is string => Boolean(url && /^https?:\/\//i.test(url));

/** 브라우저가 열 수 있는 주소만 돌려준다 (로컬 저장소의 file:// 주소는 뺀다) */
export function webUrl(url: string | null | undefined): string | undefined {
  return isWebUrl(url) ? url : undefined;
}

export function toStoryboardScenes(frames: StoryboardFrame[]): StoryboardScene[] {
  return [...frames]
    .sort((a, b) => a.beat_order - b.beat_order)
    .map((frame) => ({ imageUrl: webUrl(frame.image_url), caption: frame.caption || undefined }));
}

const formatSeconds = (sec: number) => `${Number.isInteger(sec) ? sec : sec.toFixed(1)}초`;

export function toGuideScenes(shots: FilmingGuideShot[]): GuideScene[] {
  return [...shots]
    .sort((a, b) => a.shot_no - b.shot_no)
    .map((shot) => ({ instruction: `${shot.title}. ${shot.framing_tip}`, duration: formatSeconds(shot.duration_sec) }));
}

/** 고른 영상 파일의 길이·크기를 브라우저에서 읽는다. 못 읽으면 비워 두고 서버 기본값에 맡긴다 */
export function readVideoMeta(file: File): Promise<{ duration_sec?: number; width?: number; height?: number }> {
  return new Promise((resolve) => {
    const url = URL.createObjectURL(file);
    const video = document.createElement('video');
    const done = (meta: { duration_sec?: number; width?: number; height?: number }) => {
      URL.revokeObjectURL(url);
      resolve(meta);
    };
    video.preload = 'metadata';
    video.onloadedmetadata = () =>
      done({
        duration_sec: Number.isFinite(video.duration) && video.duration > 0 ? video.duration : undefined,
        width: video.videoWidth || undefined,
        height: video.videoHeight || undefined,
      });
    video.onerror = () => done({});
    video.src = url;
  });
}
