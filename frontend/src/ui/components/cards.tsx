import { Check, Package, Play } from 'lucide-react';
import { FLOW_TOTAL_STEPS } from './layout';
import { MediaPlaceholder } from './media';
import { Badge, Button, Card, CheckMark, ProgressBar, SelectCard, Stack } from './primitives';

export interface HookTypeCardProps {
  type: string;
  description: string;
  isSelected: boolean;
  onChange: (isSelected: boolean) => void;
}

/** 훅 유형 선택 카드: 같은 모양이 나란히(유사성), 선택된 카드만 테두리·체크로 떠오른다(전경/배경) */
export function HookTypeCard({ type, description, isSelected, onChange }: HookTypeCardProps) {
  return (
    <SelectCard label={`${type} 유형`} isSelected={isSelected} onChange={onChange}>
      <div className="n-row" style={{ gap: 16 }}>
        <MediaPlaceholder ratio="9 / 16" width={54}>
          <Play size={18} aria-hidden="true" />
        </MediaPlaceholder>
        <Stack gap={4} style={{ flex: 1 }}>
          <span className="n-title">{type} 유형</span>
          <span className="n-small n-muted">{description}</span>
        </Stack>
        <CheckMark />
      </div>
    </SelectCard>
  );
}

export interface ProjectCardProps {
  productName: string;
  status: string;
  /** 끝낸 단계 수. 없으면 완성 카드 */
  completedSteps?: number;
  nextStep?: string;
  actionLabel: string;
  onAction?: () => void;
}

/** 홈 프로젝트 카드: 정보 → 진행 → 행동 순서. 막대 옆에 "5/8"을 붙인다(근접성) */
export function ProjectCard({ productName, status, completedSteps, nextStep, actionLabel, onAction }: ProjectCardProps) {
  const isDone = completedSteps === undefined;
  return (
    <Card>
      <Stack gap={16}>
        <div className="n-row" style={{ gap: 12 }}>
          <MediaPlaceholder ratio="1" width={52}>
            <Package size={22} aria-hidden="true" />
          </MediaPlaceholder>
          <Stack gap={2} style={{ flex: 1, minWidth: 0 }}>
            <span className="n-bold">{productName}</span>
            <span className="n-small n-muted">{status}</span>
          </Stack>
          {isDone ? (
            <Badge icon={<Check size={12} strokeWidth={3} aria-hidden="true" />}>완성</Badge>
          ) : null}
        </div>

        {!isDone ? (
          <div className="n-row" style={{ gap: 12 }}>
            <ProgressBar label={`${productName} 진행`} value={completedSteps} max={FLOW_TOTAL_STEPS} />
            <span className="n-small n-bold n-num">
              {completedSteps}/{FLOW_TOTAL_STEPS}
            </span>
          </div>
        ) : null}

        <div className="n-row" style={{ gap: 12, justifyContent: 'space-between' }}>
          {nextStep ? (
            <Stack gap={0}>
              <span className="n-caption n-muted">다음 단계</span>
              <span className="n-small n-semibold">{nextStep}</span>
            </Stack>
          ) : (
            <span />
          )}
          <Button label={actionLabel} variant="secondary" size="md" onClick={onAction} />
        </div>
      </Stack>
    </Card>
  );
}
