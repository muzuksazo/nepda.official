import { useState } from 'react';
import { Button, FlowHeader, HookTypeCard, MobileScreen, PendingBadge, ScreenTitle, Stack } from '../components';
import { HOOK_TYPES, type HookType } from './flowData';

export interface HookTypeScreenProps {
  initialSelected?: HookType[];
  onBack?: () => void;
  onNext?: (selected: HookType[]) => void;
  onSkipToVideo?: () => void;
}

/** 안1-3 유형 선택 (2/8) */
export function HookTypeScreen({ initialSelected = [], onBack, onNext, onSkipToVideo }: HookTypeScreenProps) {
  const [selected, setSelected] = useState<HookType[]>(initialSelected);

  const toggle = (type: HookType, isOn: boolean) =>
    setSelected((prev) => (isOn ? [...prev, type].sort() : prev.filter((t) => t !== type)));

  return (
    <MobileScreen
      header={<FlowHeader title="유형 선택" step={2} onBack={onBack} />}
      footerSummary={
        <>
          <span className="n-semibold" style={{ color: 'var(--text)' }} aria-live="polite">
            {selected.length > 0 ? `${selected.join('·')} 유형 ${selected.length}개 골랐어요` : '하나는 골라 주세요'}
          </span>
          <PendingBadge>크레딧 미정 · OQ-003</PendingBadge>
        </>
      }
      footer={
        <>
          <Button label="시나리오 글 보기" isBlock isDisabled={selected.length === 0} onClick={() => onNext?.(selected)} />
          <Button label="시안 없이 냅다 만들기" variant="ghost" size="md" isBlock onClick={onSkipToVideo} />
        </>
      }
    >
      <ScreenTitle title="첫 3초, 어떻게 낚을까요?" description="여러 개 골라도 돼요. 대신 크레딧도 늘어요." />

      <Stack gap={12} as="section">
        {HOOK_TYPES.map(({ type, description }) => (
          <HookTypeCard
            key={type}
            type={type}
            description={description}
            isSelected={selected.includes(type)}
            onChange={(isOn) => toggle(type, isOn)}
          />
        ))}
      </Stack>
    </MobileScreen>
  );
}
