import { Plus } from 'lucide-react';
import {
  BrandHeader,
  Button,
  Mascot,
  MobileScreen,
  PendingBadge,
  ProjectCard,
  SectionTitle,
  Stack,
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
}

/** 안3-1 홈 */
export function HomeScreen({ inProgress, completed, onCreate, onContinue, onDownloadAgain }: HomeScreenProps) {
  const isEmpty = inProgress.length === 0 && completed.length === 0;
  const createButton = <Button label="새 영상 만들기" isBlock icon={<Plus size={20} aria-hidden="true" />} onClick={onCreate} />;

  if (isEmpty) {
    return (
      <MobileScreen header={<BrandHeader />} footer={createButton}>
        <Stack gap={16} align="center" style={{ paddingTop: 48, textAlign: 'center' }}>
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
    <MobileScreen header={<BrandHeader />}>
      {createButton}

      {inProgress.length > 0 ? (
        <Stack gap={12} as="section">
          <SectionTitle title="진행 중" count={inProgress.length} />
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
        </Stack>
      ) : null}

      {completed.length > 0 ? (
        <Stack gap={12} as="section">
          <SectionTitle title="완성" count={completed.length}>
            <PendingBadge>보관 기간 미정 · OQ-012</PendingBadge>
          </SectionTitle>
          {completed.map((p) => (
            <ProjectCard
              key={p.id}
              productName={p.productName}
              status={p.status}
              actionLabel="다시 받기"
              onAction={() => onDownloadAgain?.(p.id)}
            />
          ))}
        </Stack>
      ) : null}
    </MobileScreen>
  );
}
