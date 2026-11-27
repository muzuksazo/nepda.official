import { Badge, Button, Card, FlowHeader, Mascot, MobileScreen, PendingBadge, ScreenTitle, SkeletonText, Stack } from '../components';
import { brand } from '../brand';
import { HOOK_TYPES, type HookType } from './flowData';

export interface ScenarioScreenProps {
  hookType: HookType;
  /** 생성된 시나리오 글. 없으면 스켈레톤(생성 중) */
  scenario?: string;
  onBack?: () => void;
  onShootingGuide?: () => void;
  onStoryboard?: () => void;
}

/** 안1-4 시나리오 글 (3/8) */
export function ScenarioScreen({ hookType, scenario, onBack, onShootingGuide, onStoryboard }: ScenarioScreenProps) {
  const description = HOOK_TYPES.find((h) => h.type === hookType)?.description;

  return (
    <MobileScreen
      header={<FlowHeader title="시나리오 글" step={3} onBack={onBack} />}
      footerSummary={
        <>
          <span>그림은 크레딧이 더 들어요</span>
          <PendingBadge>크레딧 미정</PendingBadge>
        </>
      }
      footer={
        <>
          <Button label="촬영 가이드 받기" isBlock onClick={onShootingGuide} />
          <Button label="그림으로 보기" variant="secondary" isBlock onClick={onStoryboard} />
        </>
      }
    >
      <ScreenTitle title="이렇게 낚아 볼게요" description={description} />

      <Card padding={20}>
        <Stack gap={16}>
          <div className="n-row" style={{ justifyContent: 'space-between' }}>
            <span className="n-bold">훅 시나리오</span>
            <Badge tone="brand">{hookType} 유형</Badge>
          </div>
          {scenario ? (
            <p>{scenario}</p>
          ) : (
            <Stack gap={16}>
              <div className="n-row" style={{ gap: 12 }} role="status">
                <Mascot src={brand.mascot.lying} size="xs" />
                <span className="n-small n-muted">냅다곰이 머리 굴리는 중…</span>
              </div>
              <SkeletonText widths={[100, 94, 98, 72, 90, 48]} />
            </Stack>
          )}
          <div>
            <PendingBadge>훅 길이 미정 · OQ-002</PendingBadge>
          </div>
        </Stack>
      </Card>
    </MobileScreen>
  );
}
