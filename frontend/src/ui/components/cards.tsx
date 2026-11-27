import { useId, type ReactNode } from 'react';
import { formatCount } from '../format';
import { ArrowRight, ChevronRight, Clock, Download, Heart, Lightning, Package, Play } from '../icons';
import { FLOW_TOTAL_STEPS } from './layout';
import { MediaPlaceholder } from './media';
import { Button, Card, CheckMark, ProgressBar, SelectCard, Stack } from './primitives';

export interface HookTypeCardProps {
  type: string;
  description: string;
  isSelected: boolean;
  onChange: (isSelected: boolean) => void;
}

/** 훅 유형 선택 카드: 같은 모양이 나란히(유사성), 선택된 카드만 테두리·체크로 떠오른다(전경/배경) */
export function HookTypeCard({ type, description, isSelected, onChange }: HookTypeCardProps) {
  return (
    <SelectCard label={`${type} 유형`} isSelected={isSelected} onChange={onChange}>
      <div className="n-row" style={{ gap: 16 }}>
        <MediaPlaceholder ratio="9 / 16" width={54}>
          <Play size={18} aria-hidden="true" />
        </MediaPlaceholder>
        <Stack gap={4} style={{ flex: 1 }}>
          <span className="n-title">{type} 유형</span>
          <span className="n-small n-muted">{description}</span>
        </Stack>
        <CheckMark />
      </div>
    </SelectCard>
  );
}

export interface ProjectCardProps {
  productName: string;
  status: string;
  /** 끝낸 단계 수. 없으면 완료 카드 */
  completedSteps?: number;
  nextStep?: string;
  actionLabel: string;
  onAction?: () => void;
}

/** 홈 프로젝트 카드: 정보 → 진행 → 행동 순서. 막대 옆에 "5/8"을 붙인다(근접성) */
export function ProjectCard({ productName, status, completedSteps, nextStep, actionLabel, onAction }: ProjectCardProps) {
  const isDone = completedSteps === undefined;
  return (
    <Card>
      <Stack gap={16}>
        <div className="n-row" style={{ gap: 12 }}>
          <MediaPlaceholder ratio="1" width={52}>
            <Package size={22} aria-hidden="true" />
          </MediaPlaceholder>
          <Stack gap={2} style={{ flex: 1, minWidth: 0 }}>
            <span className="n-bold">{productName}</span>
            <span className="n-small n-muted">{status}</span>
          </Stack>
        </div>

        {/* 진행 중은 "5/8", 완료는 꽉 찬 막대 + "완료" — 한 줄에 섞여 있어도 상태를 바로 알아보고 카드 높이도 같다 */}
        <div className="n-row" style={{ gap: 12 }}>
          <ProgressBar
            label={isDone ? `${productName} 완료` : `${productName} 진행`}
            value={isDone ? FLOW_TOTAL_STEPS : completedSteps}
            max={FLOW_TOTAL_STEPS}
          />
          <span className="n-small n-bold n-num">{isDone ? '완료' : `${completedSteps}/${FLOW_TOTAL_STEPS}`}</span>
        </div>

        {/* 다음 할 일(왼쪽)과 원형 아이콘 버튼(오른쪽)을 한 타일로 묶는다 */}
        <div className="n-card-action">
          <span className="n-card-action__info">
            {isDone ? (
              <span className="n-small n-semibold">영상 + 썸네일</span>
            ) : (
              <>
                <span className="n-caption n-muted">다음 단계</span>
                <span className="n-small n-semibold">{nextStep}</span>
              </>
            )}
          </span>
          <button type="button" className="n-round-btn" aria-label={`${productName} ${actionLabel}`} onClick={onAction}>
            {isDone ? <Download size={18} aria-hidden="true" /> : <ArrowRight size={18} aria-hidden="true" />}
          </button>
        </div>
      </Stack>
    </Card>
  );
}

export interface TimeEstimateStage {
  label: string;
  /** 사람이 읽는 시간, 예: "1~2분", "30초" */
  time: string;
}

export interface TimeEstimateProps {
  /** 전체 예상 시간, 예: "약 2~3분" */
  total: string;
  stages: TimeEstimateStage[];
  /** 아래 한 줄 안내 + 미정 배지 같은 보조 내용 */
  children?: ReactNode;
}

/** 만들기 전에 보는 예상 소요 시간: 큰 숫자 하나 + 단계별 시간 */
export function TimeEstimate({ total, stages, children }: TimeEstimateProps) {
  return (
    <section className="n-card n-estimate" aria-labelledby="n-estimate-title">
      <div className="n-estimate__head">
        <span className="n-estimate__icon" aria-hidden="true">
          <Clock size={22} />
        </span>
        <div>
          <h2 id="n-estimate-title" className="n-small n-muted">
            얼마나 걸려요?
          </h2>
          <p className="n-estimate__total n-num">{total}</p>
        </div>
      </div>
      <ol className="n-estimate__stages" aria-label="단계별 예상 시간">
        {stages.map((s, i) => (
          <li key={s.label}>
            <span className="n-estimate__dot" aria-hidden="true">
              {i + 1}
            </span>
            <span>{s.label}</span>
            <span className="n-estimate__time n-num">{s.time}</span>
          </li>
        ))}
      </ol>
      {children ? <div className="n-estimate__foot">{children}</div> : null}
    </section>
  );
}

export interface CreditBalanceCardProps {
  /** 크레딧 잔액. 아직 못 불러왔으면 undefined → "—" */
  credits?: number;
  onChargeClick?: () => void;
  /** 있으면 오른쪽 위에 "내역" 링크를 보여 준다 → 크레딧 내역 */
  onHistoryClick?: () => void;
  /** 잔액 줄 아래 한 줄 (예: 곧 사라지는 크레딧) */
  note?: ReactNode;
}

/** 크레딧 잔액 카드: 잔액(큰 숫자) + 충전하기. 영상은 횟수 제한 없이, 충전한 크레딧으로 만든다. */
export function CreditBalanceCard({ credits, onChargeClick, onHistoryClick, note }: CreditBalanceCardProps) {
  const titleId = useId();
  const shownCredits = credits === undefined ? '—' : credits.toLocaleString('ko-KR');
  return (
    <section className="n-card n-wallet" aria-labelledby={titleId}>
      <div className="n-wallet__head">
        <h2 id={titleId} className="n-wallet__label">
          내 크레딧
        </h2>
        {onHistoryClick ? (
          <button type="button" className="n-wallet__link" onClick={onHistoryClick} aria-label="크레딧 내역 보기">
            내역
            <ChevronRight size={16} aria-hidden="true" />
          </button>
        ) : null}
      </div>
      <div className="n-wallet__row">
        <p className="n-wallet__balance">
          <span className="n-credit__icon n-wallet__icon" aria-hidden="true">
            <Lightning size={14} strokeWidth={2.5} fill="currentColor" />
          </span>
          <span className="n-num">{shownCredits}</span>
        </p>
        <Button label="충전하기" size="md" onClick={onChargeClick} />
      </div>
      {note ? <div className="n-wallet__note">{note}</div> : null}
    </section>
  );
}

export interface StatTileProps {
  label: string;
  /** 아직 못 불러왔으면 undefined → "–" */
  value?: number;
  onClick?: () => void;
}

/** 숫자 타일: 작은 이름 + 큰 숫자. 누르면 해당 목록으로 간다. */
export function StatTile({ label, value, onClick }: StatTileProps) {
  return (
    <button
      type="button"
      className="n-stat"
      onClick={onClick}
      aria-label={value === undefined ? `${label} 불러오는 중` : `${label} ${value}개 보기`}
    >
      <span className="n-stat__label">{label}</span>
      <span className="n-stat__value n-num">{value ?? '–'}</span>
      <ChevronRight className="n-stat__chevron" size={20} />
    </button>
  );
}

export interface VideoTileProps {
  /** 9:16 썸네일. 없으면 검정 바탕에 caption 글자를 보여 준다 */
  thumbnailUrl?: string;
  /** 썸네일 글자(썸네일 이미지가 없을 때 대신 보인다) */
  caption?: string;
  /** 스크린 리더용 이름 (예: "실리콘 접이식 도마, 도마왕") */
  label: string;
  likeCount: number;
  onClick?: () => void;
}

/** 탐색 그리드의 영상 한 칸: 9:16 썸네일 + 왼쪽 아래 좋아요 수 */
export function VideoTile({ thumbnailUrl, caption, label, likeCount, onClick }: VideoTileProps) {
  return (
    <button type="button" className="n-video-tile" onClick={onClick} aria-label={`${label}, 좋아요 ${formatCount(likeCount)}개. 영상 보기`}>
      {thumbnailUrl ? (
        <img src={thumbnailUrl} alt="" loading="lazy" decoding="async" />
      ) : (
        <span className="n-video-tile__fallback">{caption}</span>
      )}
      <span className="n-video-tile__meta" aria-hidden="true">
        <Heart size={14} strokeWidth={2.5} fill="currentColor" />
        <span className="n-num">{formatCount(likeCount)}</span>
      </span>
    </button>
  );
}
