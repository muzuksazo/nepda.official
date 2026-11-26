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
} from '../components';
import type { HookType } from './flowData';

export interface UploadVideoScreenProps {
  hookType: HookType;
  initialFile?: File | null;
  onBack?: () => void;
  onReviewGuide?: () => void;
  onCreate?: (file: File) => void;
}

/** 안1-7 영상 올리기 (6/8) – 영상을 고르기 전에는 만들기 버튼이 꺼져 있다. */
export function UploadVideoScreen({ hookType, initialFile = null, onBack, onReviewGuide, onCreate }: UploadVideoScreenProps) {
  const [file, setFile] = useState<File | null>(initialFile);

  return (
    <MobileScreen
      header={<FlowHeader title="영상 올리기" step={6} onBack={onBack} />}
      footerSummary={
        <>
          <span>{file ? '이제 훅만 붙이면 돼요' : '영상부터 골라 주세요'}</span>
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
    </MobileScreen>
  );
}
