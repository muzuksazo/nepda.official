import { useState } from 'react';
import {
  Badge,
  Button,
  Card,
  FilePicker,
  FlowHeader,
  MobileScreen,
  PendingBadge,
  ScreenTitle,
  Stack,
  TimeEstimate,
  type TimeEstimateStage,
} from '../components';
import type { HookType } from './flowData';

export interface UploadVideoScreenProps {
  hookType: HookType;
  initialFile?: File | null;
  onBack?: () => void;
  onReviewGuide?: () => void;
  onCreate?: (file: File) => void;
  /** 예상 소요 시간(서버가 알려 주는 값). 아직 정해지지 않아 예시 값을 기본으로 둔다 */
  estimate?: { total: string; stages: TimeEstimateStage[] };
}

const SAMPLE_ESTIMATE = {
  total: '약 2~3분',
  stages: [
    { label: '훅 영상 뽑기', time: '1~2분' },
    { label: '본편에 이어 붙이기', time: '30초' },
    { label: '자막·마무리', time: '30초' },
  ],
};

/** 안1-7 영상 올리기 (6/8) – 영상을 고르기 전에는 만들기 버튼이 꺼져 있다. */
export function UploadVideoScreen({
  hookType,
  initialFile = null,
  onBack,
  onReviewGuide,
  onCreate,
  estimate = SAMPLE_ESTIMATE,
}: UploadVideoScreenProps) {
  const [file, setFile] = useState<File | null>(initialFile);

  return (
    <MobileScreen
      header={<FlowHeader title="영상 올리기" step={6} onBack={onBack} />}
      footerSummary={
        <>
          <span>{file ? `${estimate.total}이면 나와요` : '영상부터 골라 주세요'}</span>
          <PendingBadge>크레딧 미정</PendingBadge>
        </>
      }
      footer={
        <Button label="훅 붙여서 만들기" isBlock isDisabled={!file} onClick={() => file && onCreate?.(file)} />
      }
    >
      <ScreenTitle title="찍은 거, 냅다 올려요" />

      {/* 붙일 훅과 올릴 영상을 한 카드에 묶는다(공통 영역) */}
      <Card>
        <Stack gap={16}>
          <div className="n-row" style={{ justifyContent: 'space-between' }}>
            <div className="n-row" style={{ gap: 8 }}>
              <span className="n-small n-muted">붙일 훅</span>
              <Badge tone="brand">{hookType} 유형</Badge>
            </div>
            <Button label="가이드 다시 보기" variant="ghost" size="sm" onClick={onReviewGuide} />
          </div>
          <FilePicker
            label="촬영한 영상"
            isLabelHidden
            accept="video/*"
            value={file}
            onChange={setFile}
            placeholder="찍은 영상을 골라 주세요"
          />
          <div>
            <PendingBadge>길이·용량 제한 미정 · OQ-007</PendingBadge>
          </div>
        </Stack>
      </Card>

      {/* 누르기 전에 기다릴 시간을 알려 준다: 총 시간 하나 + 단계별 시간 */}
      <TimeEstimate total={estimate.total} stages={estimate.stages}>
        <span>만드는 동안 다른 화면 봐도 괜찮아요.</span>
        <PendingBadge>시간·완료 알림 미정</PendingBadge>
      </TimeEstimate>
    </MobileScreen>
  );
}
