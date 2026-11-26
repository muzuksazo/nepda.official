import { useState } from 'react';
import {
  Button,
  Card,
  CreditIcon,
  CreditPackagePicker,
  MobileScreen,
  Note,
  PageHeader,
  PendingBadge,
  ScreenTitle,
  Stack,
  type CreditPackage,
} from '../components';
import { formatWon } from '../format';

export interface CreditChargeScreenProps {
  /** 지금 보유한 크레딧 */
  credits: number;
  /** 충전 묶음 (작은 것부터) */
  packages: readonly CreditPackage[];
  /** 영상 한 편에 드는 크레딧. 있으면 묶음마다 "영상 약 N편"을 보여 준다 */
  creditsPerVideo?: number;
  /** 영상 만들기 중 모자라서 들어왔을 때 더 필요한 크레딧. 이만큼을 채우는 가장 작은 묶음을 골라 둔다 */
  shortfall?: number;
  /** 처음 골라 둘 묶음 (shortfall보다 우선) */
  initialPackageId?: string;
  /** 결제창을 여는 중: 버튼을 잠가 두 번 결제되지 않게 한다 */
  isPaying?: boolean;
  /** 결제가 실패하고 돌아왔을 때 (취소는 실패가 아니다 — 아무 표시 없이 돌아온다) */
  hasPaymentError?: boolean;
  onBack?: () => void;
  /** 고른 묶음으로 PG 결제창을 연다 */
  onPay?: (pkg: CreditPackage) => void;
  /** 환불·유효기간 안내 */
  onOpenPolicy?: () => void;
}

/** 처음 골라 둘 묶음: 모자란 만큼을 채우는 가장 작은 묶음 → "많이 골라요" → 첫 묶음 */
function pickInitial(packages: readonly CreditPackage[], shortfall?: number): string | null {
  if (shortfall) {
    const enough = [...packages].sort((a, b) => a.credits - b.credits).find((pkg) => pkg.credits >= shortfall);
    if (enough) return enough.id;
  }
  return (packages.find((pkg) => pkg.isPopular) ?? packages[0])?.id ?? null;
}

/** 크레딧 충전 — 묶음 하나를 골라 결제한다. 상단 크레딧 배지·내 정보·영상 만들기(모자랄 때)에서 들어온다 */
export function CreditChargeScreen({
  credits,
  packages,
  creditsPerVideo,
  shortfall,
  initialPackageId,
  isPaying = false,
  hasPaymentError = false,
  onBack,
  onPay,
  onOpenPolicy,
}: CreditChargeScreenProps) {
  const [packageId, setPackageId] = useState<string | null>(() => initialPackageId ?? pickInitial(packages, shortfall));
  const picked = packages.find((pkg) => pkg.id === packageId);
  const isStillShort = shortfall !== undefined && picked !== undefined && picked.credits < shortfall;

  return (
    <MobileScreen
      header={<PageHeader title="크레딧 충전" onBack={onBack} />}
      footerSummary={
        picked ? (
          <span className="n-cost">
            충전 후
            <CreditIcon />
            <b className="n-num">{(credits + picked.credits).toLocaleString('ko-KR')}</b>
            {isStillShort ? <span className="n-cost__warn">· 아직 모자라요</span> : null}
          </span>
        ) : (
          <span>충전할 만큼 골라 주세요</span>
        )
      }
      footer={
        <Button
          label={isPaying ? '결제창 여는 중…' : picked ? `${formatWon(picked.price)} 결제하기` : '결제하기'}
          isBlock
          isDisabled={!picked || isPaying}
          onClick={() => picked && onPay?.(picked)}
        />
      }
    >
      <ScreenTitle title="크레딧 채우고, 냅다 만들어요" />

      {/* 지금 잔액 + (모자라서 왔다면) 얼마나 더 필요한지 */}
      <Card>
        <Stack gap={4}>
          <span className="n-wallet__label">지금 크레딧</span>
          <p className="n-wallet__balance">
            <CreditIcon size="lg" />
            <span className="n-num">{credits.toLocaleString('ko-KR')}</span>
          </p>
          {shortfall ? (
            <p className="n-wallet__hint" style={{ marginTop: 4 }}>
              영상 만들려면 <b className="n-cost__strong n-num">{shortfall.toLocaleString('ko-KR')}</b> 더 필요해요.
            </p>
          ) : null}
        </Stack>
      </Card>

      {hasPaymentError ? (
        <div role="alert">
          <Note title="결제가 안 됐어요. 다른 수단으로 해 볼까요?">
            <span className="n-small n-muted">돈은 빠져나가지 않았어요.</span>
          </Note>
        </div>
      ) : null}

      <Stack gap={8}>
        <CreditPackagePicker
          label="충전할 크레딧"
          packages={packages}
          value={packageId}
          onChange={setPackageId}
          creditsPerVideo={creditsPerVideo}
        />
        <div>
          <PendingBadge>가격·묶음 예시 값 · OQ-003</PendingBadge>
        </div>
      </Stack>

      {/* 결제 전에 알아야 할 것: 짧게 한 덩어리로 */}
      <Stack gap={8}>
        <ul className="n-policy">
          <li>크레딧은 영상을 만들 때만 써요. 글·콘티·가이드는 무료예요.</li>
          <li>영상 만들기에 실패하면 쓴 크레딧은 돌려드려요.</li>
        </ul>
        <div className="n-row" style={{ gap: 8, flexWrap: 'wrap' }}>
          <Button label="환불·유효기간 안내" variant="ghost" size="sm" onClick={onOpenPolicy} />
          <PendingBadge>환불·유효기간 미정</PendingBadge>
        </div>
      </Stack>
    </MobileScreen>
  );
}
