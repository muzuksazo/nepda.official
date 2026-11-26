import { brand } from '../brand';
import { Button, CreditChange, Mascot, MobileScreen, PageHeader, Stack } from '../components';

export interface ChargeResultScreenProps {
  /** confirming: 결제는 끝났고 서버가 확인하는 중 · done: 잔액에 들어감 */
  status: 'confirming' | 'done';
  /** 충전 전 잔액 */
  before: number;
  /** 충전한 크레딧 */
  added: number;
  /** 영상 만들기 중 모자라서 충전했으면 true: "영상 만들러 가기"로 하던 단계에 돌아간다 */
  isResumingVideo?: boolean;
  /** 완료 버튼: 들어온 곳으로 돌아간다 */
  onDone?: () => void;
}

/** 크레딧 충전 결과 — 확인 중이면 기다리게 하고, 들어가면 늘어난 잔액을 보여 준 뒤 들어온 곳으로 돌려보낸다 */
export function ChargeResultScreen({ status, before, added, isResumingVideo = false, onDone }: ChargeResultScreenProps) {
  const isDone = status === 'done';
  return (
    <MobileScreen
      header={<PageHeader title="크레딧 충전" isTabRoot />}
      footer={isDone ? <Button label={isResumingVideo ? '영상 만들러 가기' : '확인'} isBlock onClick={onDone} /> : undefined}
    >
      {/* 확인 중 → 완료로 바뀌는 걸 스크린 리더가 읽는다 */}
      <div role="status" style={{ display: 'contents' }}>
        {isDone ? (
          <Stack gap={20} align="center" justify="center" style={{ flex: 1, textAlign: 'center', paddingBottom: 24 }}>
            <Mascot src={brand.mascot.happy} width={150} />
            <Stack gap={8} align="center">
              <h2 className="n-display">충전 완료!</h2>
              <p className="n-muted">{isResumingVideo ? '이제 냅다 만들어요.' : '든든하게 채웠어요.'}</p>
            </Stack>
            <CreditChange from={before} to={before + added} />
          </Stack>
        ) : (
          <Stack gap={20} align="center" justify="center" style={{ flex: 1, textAlign: 'center', paddingBottom: 24 }}>
            <span className="n-spinner" aria-hidden="true" />
            <Stack gap={8} align="center">
              <h2 className="n-display">결제 확인 중이에요</h2>
              <p className="n-muted">
                잠깐이면 돼요.
                <br />
                창을 닫아도 충전은 그대로 돼요.
              </p>
            </Stack>
          </Stack>
        )}
      </div>
    </MobileScreen>
  );
}
