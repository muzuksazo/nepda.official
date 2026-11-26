import { Plus } from '../icons';
import {
  AppHeaderActions,
  BottomNav,
  BrandHeader,
  Button,
  Carousel,
  EventBanner,
  Mascot,
  MobileScreen,
  PendingBadge,
  ProjectCard,
  SectionTitle,
  Stack,
  type NavTab,
  type BannerItem,
} from '../components';
import { brand } from '../brand';

export interface InProgressProject {
  id: string;
  productName: string;
  status: string;
  completedSteps: number;
  nextStep: string;
}

export interface CompletedProject {
  id: string;
  productName: string;
  status: string;
}

export interface HomeScreenProps {
  inProgress: InProgressProject[];
  completed: CompletedProject[];
  onCreate?: () => void;
  onContinue?: (id: string) => void;
  onDownloadAgain?: (id: string) => void;
  /** 상단 이벤트 배너 (없으면 영역을 숨긴다) */
  banners?: BannerItem[];
  onBannerSelect?: (id: string) => void;
  /** 진행 중 화살표 → 내 영상(진행 중 탭) */
  onSeeAllInProgress?: () => void;
  /** 완성 화살표 → 내 영상(완성 탭) */
  onSeeAllCompleted?: () => void;
  /** 상단 크레딧 잔액 (못 불러왔으면 생략) */
  credits?: number;
  onCreditClick?: () => void;
  /** 상단 프로필 (사진이 없으면 닉네임 첫 글자) */
  profile?: { name?: string; imageUrl?: string };
  onProfileClick?: () => void;
  /** 하단 내비게이션 이동 */
  onNavigate?: (tab: NavTab) => void;
}

/** 안3-1 홈 */
export function HomeScreen({
  inProgress,
  completed,
  onCreate,
  onContinue,
  onDownloadAgain,
  onSeeAllInProgress,
  onSeeAllCompleted,
  banners = [],
  onBannerSelect,
  credits,
  onCreditClick,
  profile,
  onProfileClick,
  onNavigate,
}: HomeScreenProps) {
  const isEmpty = inProgress.length === 0 && completed.length === 0;
  const header = (
    <BrandHeader
      endContent={
        <AppHeaderActions
          credits={credits}
          onCreditClick={onCreditClick}
          profile={profile}
          onProfileClick={onProfileClick}
        />
      }
    />
  );
  const bottomNav = <BottomNav active="home" onNavigate={onNavigate} />;
  const createButton = <Button label="영상 만들기" isBlock icon={<Plus size={20} aria-hidden="true" />} onClick={onCreate} />;

  if (isEmpty) {
    return (
      <MobileScreen header={header} footer={createButton} bottomNav={bottomNav}>
        <Stack gap={16} align="center" justify="center" style={{ flex: 1, textAlign: 'center', paddingBottom: 24 }}>
          <Mascot src={brand.mascot.clapboard} width={140} />
          <Stack gap={8} align="center">
            <h2 className="n-display">
              첫 광고, <span className="n-mark">냅다</span> 만들어 볼까요?
            </h2>
            <p className="n-muted">제품만 알려 주면 훅은 저희가 붙여요.</p>
          </Stack>
        </Stack>
      </MobileScreen>
    );
  }

  return (
    <MobileScreen header={header} bottomNav={bottomNav}>
      {banners.length > 0 ? (
        <div style={{ marginBottom: -8 }}>
          <EventBanner items={banners} onSelect={onBannerSelect} />
        </div>
      ) : null}
      {createButton}

      {inProgress.length > 0 ? (
        <Stack gap={12} as="section">
          <SectionTitle title="진행 중" count={inProgress.length} onSeeAll={onSeeAllInProgress} />
          <Carousel label="진행 중인 영상">
            {inProgress.map((p) => (
              <ProjectCard
                key={p.id}
                productName={p.productName}
                status={p.status}
                completedSteps={p.completedSteps}
                nextStep={p.nextStep}
                actionLabel="이어하기"
                onAction={() => onContinue?.(p.id)}
              />
            ))}
          </Carousel>
        </Stack>
      ) : null}

      {completed.length > 0 ? (
        <Stack gap={12} as="section">
          <SectionTitle title="완성" count={completed.length} onSeeAll={onSeeAllCompleted}>
            <PendingBadge>보관 기간 미정 · OQ-012</PendingBadge>
          </SectionTitle>
          <Carousel label="완성한 영상">
            {completed.map((p) => (
              <ProjectCard
                key={p.id}
                productName={p.productName}
                status={p.status}
                actionLabel="다시 받기"
                onAction={() => onDownloadAgain?.(p.id)}
              />
            ))}
          </Carousel>
        </Stack>
      ) : null}
    </MobileScreen>
  );
}
