import { useState } from 'react';
import {
  Badge,
  Button,
  Card,
  ConfirmSheet,
  CreditIcon,
  FilesPicker,
  FlowHeader,
  MobileScreen,
  ScreenTitle,
  Stack,
  TimeEstimate,
  type TimeEstimateStage,
} from '../components';
import type { HookType } from './flowData';

export interface UploadVideoScreenProps {
  hookType: HookType;
  initialFiles?: File[];
  onBack?: () => void;
  onReviewGuide?: () => void;
  /** 고른 영상들 (촬영 순서). 1개 이상 */
  onCreate?: (files: File[]) => void;
  /** 이 영상에 드는 크레딧(견적 API). 없으면 예상 소요 시간만 보여 준다 */
  cost?: number;
  /** 지금 보유한 크레딧 */
  credits?: number;
  /** 크레딧이 모자라 "충전하고 만들기"를 눌렀을 때. 충전 뒤 이 화면으로 돌아오도록 고른 영상과 모자란 크레딧을 넘긴다 */
  onCharge?: (files: File[], shortfall: number) => void;
  /** 처음부터 크레딧 부족 시트를 열어 둔다 (스토리·테스트용) */
  initialIsShort?: boolean;
  /** 예상 소요 시간(서버가 알려 주는 값). 없으면 기본 안내 값을 쓴다 */
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
  initialFiles = [],
  onBack,
  onReviewGuide,
  onCreate,
  estimate = SAMPLE_ESTIMATE,
  cost,
  credits,
  onCharge,
  initialIsShort = false,
}: UploadVideoScreenProps) {
  const [files, setFiles] = useState<File[]>(initialFiles);
  const file = files.length > 0;
  const [isShortOpen, setIsShortOpen] = useState(initialIsShort);
  // 단가·잔액을 모르면 막지 않고 서버에 맡긴다
  const shortfall = cost !== undefined && credits !== undefined ? Math.max(0, cost - credits) : 0;

  const create = () => {
    if (!file) return;
    if (shortfall > 0) setIsShortOpen(true);
    else onCreate?.(files);
  };

  // 버튼 바로 위 한 줄: 누르면 무엇이 빠지는지 미리 보여 준다
  let summary;
  if (!file) {
    summary = <span>영상부터 골라 주세요</span>;
  } else if (cost === undefined) {
    summary = <span>{estimate.total}이면 나와요</span>;
  } else {
    summary = (
      <span className="n-cost">
        <CreditIcon />
        <b className="n-num">{cost.toLocaleString('ko-KR')}</b> 크레딧 써요
        {credits !== undefined ? <span className="n-cost__have n-num">· 보유 {credits.toLocaleString('ko-KR')}</span> : null}
      </span>
    );
  }

  return (
    <>
      <MobileScreen
        isInert={isShortOpen}
        header={<FlowHeader title="영상 올리기" step={6} onBack={onBack} />}
        footerSummary={summary}
        footer={<Button label="훅 붙여서 만들기" isBlock isDisabled={!file} onClick={create} />}
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
              {onReviewGuide ? (
                <Button label="가이드 다시 보기" variant="ghost" size="sm" onClick={onReviewGuide} />
              ) : null}
            </div>
            <FilesPicker
              label="촬영한 영상"
              isLabelHidden
              accept="video/*"
              value={files}
              onChange={setFiles}
              placeholder="찍은 영상을 골라 주세요 (여러 개 가능)"
            />
            <p className="n-small n-muted">합쳐서 5~90초 · 한 개 100MB 이하 · 세로 9:16 영상</p>
          </Stack>
        </Card>

        {/* 누르기 전에 기다릴 시간을 알려 준다: 총 시간 하나 + 단계별 시간 */}
        <TimeEstimate total={estimate.total} stages={estimate.stages}>
          <span>만드는 동안 다른 화면 봐도 괜찮아요.</span>
        </TimeEstimate>
      </MobileScreen>

      {/* 모자랄 때만: 막는 대신 바로 충전으로 이어 준다 */}
      <ConfirmSheet
        isOpen={isShortOpen}
        title="크레딧이 조금 모자라요"
        description="충전하면 올린 영상 그대로 바로 만들 수 있어요."
        confirmLabel="충전하고 만들기"
        cancelLabel="나중에"
        onConfirm={() => {
          setIsShortOpen(false);
          if (file) onCharge?.(files, shortfall);
        }}
        onClose={() => setIsShortOpen(false)}
      >
        <dl className="n-shortfall">
          <div>
            <dt>필요</dt>
            <dd className="n-num">{cost?.toLocaleString('ko-KR')}</dd>
          </div>
          <div>
            <dt>보유</dt>
            <dd className="n-num">{credits?.toLocaleString('ko-KR')}</dd>
          </div>
          <div className="n-shortfall__need">
            <dt>더 필요</dt>
            <dd>
              <CreditIcon />
              <span className="n-num">{shortfall.toLocaleString('ko-KR')}</span>
            </dd>
          </div>
        </dl>
      </ConfirmSheet>
    </>
  );
}
