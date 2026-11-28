import { Badge, Button, Card, FlowHeader, Mascot, MobileScreen, ScreenTitle, SkeletonText, Stack } from '../components';
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
  const isReady = Boolean(scenario);

  return (
    <MobileScreen
      header={<FlowHeader title="시나리오 글" step={3} onBack={onBack} />}
      footerSummary={<span>그림 콘티는 무료로 미리 볼 수 있어요</span>}
      footer={
        <>
          <Button label="촬영 가이드 받기" isBlock isDisabled={!isReady} onClick={onShootingGuide} />
          <Button label="그림으로 보기" variant="secondary" isBlock isDisabled={!isReady} onClick={onStoryboard} />
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
            <>
              <p style={{ whiteSpace: 'pre-line' }}>{scenario}</p>
              <p className="n-small n-muted">
                본편 나레이션(10~15초)은 촬영 영상을 올린 뒤, 이 훅의 마지막 말을 이어받아 만들어져요.
              </p>
            </>
          ) : (
            <Stack gap={16}>
              <div className="n-row" style={{ gap: 12 }} role="status">
                <Mascot src={brand.mascot.lying} size="xs" />
                <span className="n-small n-muted">냅다곰이 머리 굴리는 중…</span>
              </div>
              <SkeletonText widths={[100, 94, 98, 72, 90, 48]} />
            </Stack>
          )}
        </Stack>
      </Card>
    </MobileScreen>
  );
}
