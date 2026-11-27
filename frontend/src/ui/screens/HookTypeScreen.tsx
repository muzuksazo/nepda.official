import { useState } from 'react';
import { Button, FlowHeader, HookTypeCard, MobileScreen, ScreenTitle, Stack } from '../components';
import { HOOK_TYPES, type HookType } from './flowData';

export interface HookTypeScreenProps {
  initialSelected?: HookType[];
  /** 영상 한 편당 크레딧(있으면 안내 문구에 표시) */
  creditsPerVideo?: number;
  onBack?: () => void;
  onNext?: (selected: HookType[]) => void;
  onSkipToVideo?: (selected: HookType[]) => void;
}

/** 안1-3 유형 선택 (2/8) — 훅 유형 하나를 고른다 */
export function HookTypeScreen({
  initialSelected = [],
  creditsPerVideo,
  onBack,
  onNext,
  onSkipToVideo,
}: HookTypeScreenProps) {
  const [selected, setSelected] = useState<HookType[]>(initialSelected.length > 0 ? [initialSelected[0]] : []);

  const choose = (type: HookType) => setSelected([type]);

  return (
    <MobileScreen
      header={<FlowHeader title="유형 선택" step={2} onBack={onBack} />}
      footerSummary={
        <>
          <span className="n-semibold" style={{ color: 'var(--text)' }} aria-live="polite">
            {selected.length > 0 ? `${selected[0]} 유형을 골랐어요` : '하나를 골라 주세요'}
          </span>
          <span className="n-small n-muted">
            {creditsPerVideo !== undefined
              ? `영상 완성 시 ${creditsPerVideo.toLocaleString('ko-KR')} 크레딧`
              : '시안은 무료예요'}
          </span>
        </>
      }
      footer={
        <>
          <Button label="시나리오 글 보기" isBlock isDisabled={selected.length === 0} onClick={() => onNext?.(selected)} />
          <Button
            label="시안 없이 냅다 만들기"
            variant="ghost"
            size="md"
            isBlock
            isDisabled={selected.length === 0}
            onClick={() => onSkipToVideo?.(selected)}
          />
        </>
      }
    >
      <ScreenTitle title="첫 3초, 어떻게 낚을까요?" description="제품에 가장 어울리는 훅 유형 하나를 골라 주세요." />

      <Stack gap={12} as="section">
        {HOOK_TYPES.map(({ type, description }) => (
          <HookTypeCard
            key={type}
            type={type}
            description={description}
            isSelected={selected[0] === type}
            onChange={() => choose(type)}
          />
        ))}
      </Stack>
    </MobileScreen>
  );
}
