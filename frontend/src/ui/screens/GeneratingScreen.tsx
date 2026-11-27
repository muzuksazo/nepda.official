import type { ReactNode } from 'react';
import { brand } from '../brand';
import { Button, CreditIcon, FlowHeader, Mascot, MobileScreen, Note, PendingBadge, Stack } from '../components';
import { Check, X } from '../icons';

/** 만드는 단계 (영상 올리기 화면의 예상 시간과 같은 이름) */
const GENERATING_STAGES = ['훅 영상 뽑기', '본편에 이어 붙이기', '자막·마무리'] as const;

/**
 * 실패 이유 — 누구 탓이냐에 따라 할 일이 다르다.
 * temporary: 냅다 쪽 문제(서버·AI 오류) → 같은 영상으로 다시 만들기
 * video: 올린 영상 문제(너무 짧거나 길다, 읽을 수 없다 등) → 다른 영상 올리기
 */
export interface GeneratingFailure {
  kind: 'temporary' | 'video';
  /** 영상 문제일 때 무엇이 문제인지 한 줄 (예: "영상이 5초보다 짧아요.") */
  detail?: string;
}

export interface GeneratingScreenProps {
  /** queued: 차례를 기다리는 중 · running: 만드는 중 · done: 다 됨 · failed: 못 만듦 */
  status: 'queued' | 'running' | 'done' | 'failed';
  /** 앞에 기다리는 영상 수 (queued일 때) */
  queuePosition?: number;
  /** 0~100 (running일 때). 서버가 주지 않으면 퍼센트·막대 대신 단계만 보여 준다 */
  progress?: number;
  /** 지금 하는 단계 (GENERATING_STAGES 순서, 0부터). failed면 멈춘 단계 */
  stageIndex?: number;
  /** 남은 시간(초) 어림값 */
  remainingSeconds?: number;
  productName?: string;
  /** failed일 때 이유 */
  failure?: GeneratingFailure;
  /** failed일 때 돌려준 크레딧 */
  refundedCredits?: number;
  /** 돌려받은 뒤 잔액 */
  credits?: number;
  /** "다시 만들기"에 드는 크레딧 (temporary 실패) */
  retryCost?: number;
  /** 위 뒤로 버튼 — 만들기는 멈추지 않고 홈으로 간다 */
  onBack?: () => void;
  /** "홈에서 기다릴게요" · 실패 시 "홈으로" */
  onWaitAtHome?: () => void;
  /** 다 됐을 때 "영상 보러 가기" */
  onViewVideo?: () => void;
  /** temporary 실패: 같은 영상으로 다시 만들기 */
  onRetry?: () => void;
  /** video 실패: 영상 올리기로 돌아가 다른 영상 고르기 */
  onReupload?: () => void;
  /** video 실패: 촬영 가이드 다시 보기 */
  onReviewGuide?: () => void;
  /** "계속 안 되면 문의하기" */
  onContact?: () => void;
}

/** "약 2분 남았어요." · "1분 안에 끝나요." · "거의 다 됐어요." */
function remainingText(seconds: number): string {
  if (seconds <= 15) return '거의 다 됐어요.';
  if (seconds < 60) return '1분 안에 끝나요.';
  return `약 ${Math.round(seconds / 60)}분 남았어요.`;
}

/**
 * 영상 만드는 중 (7/8 앞) — 영상 올리기에서 "훅 붙여서 만들기"를 누르면 온다.
 * 2~3분 걸리므로 붙잡아 두지 않는다: 퍼센트와 단계로 진행을 보여 주고, 다른 화면에 가도 되며 다 되면 알림으로 알려 준다.
 * 실패하면 같은 화면에서 이유 → 돌려받은 크레딧 → 할 일 순서로 보여 준다.
 */
export function GeneratingScreen({
  status,
  queuePosition,
  progress,
  stageIndex = 0,
  remainingSeconds,
  productName,
  failure = { kind: 'temporary' },
  refundedCredits,
  credits,
  retryCost,
  onBack,
  onWaitAtHome,
  onViewVideo,
  onRetry,
  onReupload,
  onReviewGuide,
  onContact,
}: GeneratingScreenProps) {
  const isDone = status === 'done';
  const isQueued = status === 'queued';
  const isFailed = status === 'failed';
  const isVideoProblem = isFailed && failure.kind === 'video';
  const percent = isDone ? 100 : Math.max(0, Math.min(100, Math.round(progress ?? 0)));
  const currentStage = isDone ? GENERATING_STAGES.length : isQueued ? -1 : stageIndex;

  let title: string;
  let description: string;
  if (isFailed) {
    title = isVideoProblem ? '이 영상으론 못 굽겠어요' : '앗, 영상이 안 구워졌어요';
    description = isVideoProblem
      ? (failure.detail ?? '올린 영상을 읽지 못했어요.')
      : '냅다 쪽 문제예요. 다시 누르면 처음부터 만들어요.';
  } else if (isDone) {
    title = '다 됐어요!';
    description = productName ? `${productName} 영상이 나왔어요.` : '영상이 나왔어요.';
  } else if (isQueued) {
    title = '곧 시작해요';
    description = queuePosition ? `앞에 ${queuePosition}개가 먼저 만들어지는 중이에요.` : '차례를 기다리고 있어요.';
  } else {
    title = '냅다곰이 영상 굽는 중';
    description = remainingSeconds !== undefined ? remainingText(remainingSeconds) : '2~3분이면 나와요.';
  }

  let footer: ReactNode;
  let footerSummary: ReactNode;
  if (isFailed && isVideoProblem) {
    footer = (
      <>
        <Button label="다른 영상 올리기" isBlock onClick={onReupload} />
        <Button label="촬영 가이드 다시 보기" variant="secondary" isBlock onClick={onReviewGuide} />
      </>
    );
  } else if (isFailed) {
    footer = (
      <>
        <Button label="다시 만들기" isBlock onClick={onRetry} />
        <Button label="홈으로" variant="secondary" isBlock onClick={onWaitAtHome} />
      </>
    );
    // 다시 누르면 무엇이 빠지는지 미리 (영상 올리기와 같은 한 줄)
    footerSummary =
      retryCost !== undefined ? (
        <span className="n-cost">
          <CreditIcon />
          <b className="n-num">{retryCost.toLocaleString('ko-KR')}</b> 크레딧 써요
          {credits !== undefined ? <span className="n-cost__have n-num">· 보유 {credits.toLocaleString('ko-KR')}</span> : null}
        </span>
      ) : undefined;
  } else if (isDone) {
    footer = <Button label="영상 보러 가기" isBlock onClick={onViewVideo} />;
  } else {
    footer = <Button label="홈에서 기다릴게요" variant="secondary" isBlock onClick={onWaitAtHome} />;
  }

  let mascot = brand.mascot.lying;
  if (isDone) mascot = brand.mascot.happy;
  if (isFailed) mascot = brand.mascot.surprised;

  return (
    <MobileScreen
      header={
        <FlowHeader
          title={isFailed ? '영상 만들기' : isDone ? '영상 완성' : '영상 만드는 중'}
          step={7}
          onBack={onBack}
          backLabel="홈으로"
        />
      }
      footerSummary={footerSummary}
      footer={footer}
    >
      <Stack gap={20} align="center" style={{ textAlign: 'center', paddingTop: 8 }}>
        <div className={`n-gen__mascot${isDone || isFailed ? '' : ' is-working'}`}>
          <Mascot src={mascot} />
        </div>
        <Stack gap={6} align="center">
          <h2 className="n-display">{title}</h2>
          <p className="n-muted">{description}</p>
        </Stack>
      </Stack>

      {/* 돈 얘기는 먼저: 실패하면 쓴 크레딧을 돌려줬다는 것부터 */}
      {isFailed && refundedCredits ? (
        <div className="n-gen__refund">
          <CreditIcon size="lg" />
          <p className="n-gen__refund-text">
            <b>쓴 크레딧 돌려드렸어요</b>
            {credits !== undefined ? <span className="n-num">지금 {credits.toLocaleString('ko-KR')}</span> : null}
          </p>
          <span className="n-gen__refund-amount n-num" aria-label={`${refundedCredits.toLocaleString('ko-KR')} 크레딧 돌려받음`}>
            +{refundedCredits.toLocaleString('ko-KR')}
          </span>
        </div>
      ) : null}

      {/* 퍼센트 + 막대: 서버가 진행률을 줄 때만 (실패하면 숨긴다) */}
      {!isQueued && !isFailed && (progress !== undefined || isDone) ? (
        <div className="n-gen__meter">
          <div className="n-gen__meter-head">
            <span className="n-small n-muted">{isDone ? '완료' : (GENERATING_STAGES[currentStage] ?? '')}</span>
            <b className="n-gen__percent n-num">{percent}%</b>
          </div>
          <div
            className="n-gen__bar"
            role="progressbar"
            aria-label="영상 만드는 진행률"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={percent}
          >
            <span className={`n-gen__fill${isDone ? '' : ' is-moving'}`} style={{ width: `${percent}%` }} />
          </div>
        </div>
      ) : null}

      {/* 단계: 끝난 단계는 라임 체크, 지금 단계는 도는 원, 멈춘 단계는 X, 남은 단계는 빈 원 */}
      <ol className="n-gen__steps" aria-label="만드는 단계">
        {GENERATING_STAGES.map((label, i) => {
          let state: 'done' | 'running' | 'stopped' | 'waiting' = 'waiting';
          if (i < currentStage) state = 'done';
          else if (i === currentStage) state = isFailed ? 'stopped' : 'running';
          const readout = { done: ' 끝남', running: ' 하는 중', stopped: ' 여기서 멈춤', waiting: ' 기다리는 중' }[state];
          return (
            <li key={label} className={`n-gen__step is-${state}`}>
              <span className="n-gen__dot" aria-hidden="true">
                {state === 'done' ? <Check size={16} strokeWidth={3} /> : null}
                {state === 'stopped' ? <X size={14} strokeWidth={3} /> : null}
              </span>
              <span className="n-gen__label">{label}</span>
              {state === 'stopped' ? (
                <span className="n-gen__stopped" aria-hidden="true">
                  여기서 멈췄어요
                </span>
              ) : null}
              <span className="napda-visually-hidden">{readout}</span>
            </li>
          );
        })}
      </ol>

      {/* 단계가 바뀌거나 끝나면 스크린 리더가 한 번 읽는다 (퍼센트는 읽지 않는다) */}
      <p className="napda-visually-hidden" role="status">
        {isFailed
          ? `영상을 못 만들었어요. ${refundedCredits ? '쓴 크레딧은 돌려드렸어요.' : ''}`
          : isDone
            ? '영상이 다 만들어졌어요'
            : isQueued
              ? '차례를 기다리고 있어요'
              : `${GENERATING_STAGES[currentStage] ?? ''} 하는 중`}
      </p>

      {isFailed ? (
        isVideoProblem ? (
          <Note title="이런 영상이면 잘 만들어져요">
            <span className="n-small n-muted">5~90초, 100MB 이하, 세로(9:16)로 찍은 영상이요.</span>
          </Note>
        ) : null
      ) : isDone ? null : (
        <Note title="다른 화면 봐도 괜찮아요">
          <Stack gap={6} style={{ alignItems: 'flex-start' }}>
            <span className="n-small n-muted">다 되면 알림으로 알려 드려요. 홈의 내 영상에서도 볼 수 있어요.</span>
            <PendingBadge>푸시 알림 방식 미정</PendingBadge>
          </Stack>
        </Note>
      )}

      {isFailed ? (
        <div className="n-gen__help">
          <button type="button" className="n-link-btn" onClick={onContact}>
            계속 안 되면 문의하기
          </button>
        </div>
      ) : null}
    </MobileScreen>
  );
}
