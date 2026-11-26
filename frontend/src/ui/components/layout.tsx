import type { ReactNode } from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import { brand } from '../brand';
import { IconButton, ProgressBar } from './primitives';

export const FLOW_TOTAL_STEPS = 8;

export interface MobileScreenProps {
  header: ReactNode;
  children: ReactNode;
  footer?: ReactNode;
  /** 버튼 바로 위 한 줄 요약. 결정 직전에 확인할 정보를 버튼과 같은 영역에 묶는다. */
  footerSummary?: ReactNode;
}

export function MobileScreen({ header, children, footer, footerSummary }: MobileScreenProps) {
  return (
    <div className="n-screen">
      <div className="n-screen__header">{header}</div>
      <main className="n-screen__body">{children}</main>
      {footer ? (
        <footer className="n-screen__footer">
          {footerSummary ? <div className="n-screen__summary">{footerSummary}</div> : null}
          {footer}
        </footer>
      ) : null}
    </div>
  );
}

/** 홈·온보딩 상단 로고. 한 화면에 로고는 이것 하나뿐이다. */
export function BrandHeader({ endContent }: { endContent?: ReactNode }) {
  return (
    <header className="n-brand-header">
      <h1>
        <img className="n-wordmark n-wordmark--light" src={brand.wordmarkBlack} alt="NAPDA 냅다" />
        <img className="n-wordmark n-wordmark--dark" src={brand.wordmarkWhite} alt="NAPDA 냅다" />
      </h1>
      {endContent}
    </header>
  );
}

export interface FlowHeaderProps {
  title: string;
  step: number;
  onBack?: () => void;
}

/** 만들기 흐름 상단: [뒤로 · 제목 · 단계] 한 줄 + 바로 아래 진행 막대 */
export function FlowHeader({ title, step, onBack }: FlowHeaderProps) {
  return (
    <header className="n-flow-header">
      <div className="n-row" style={{ gap: 4 }}>
        <IconButton label="이전" icon={<ChevronLeft size={26} />} onClick={onBack} />
        <h1 className="n-title">{title}</h1>
        <span className="n-flow-header__step n-num">
          <b>{step}</b> / {FLOW_TOTAL_STEPS}
        </span>
      </div>
      <div style={{ paddingLeft: 12 }}>
        <ProgressBar label="진행 단계" value={step} max={FLOW_TOTAL_STEPS} />
      </div>
    </header>
  );
}

export interface ScreenTitleProps {
  title: ReactNode;
  description?: string;
  size?: 'md' | 'xl';
  children?: ReactNode;
}

/** 화면 제목(디스플레이 서체, 화면당 한 번) + 설명 */
export function ScreenTitle({ title, description, size = 'md', children }: ScreenTitleProps) {
  return (
    <div className="n-stack" style={{ gap: 8, alignItems: 'flex-start' }}>
      <h2 className={`n-display${size === 'xl' ? ' n-display--xl' : ''}`}>{title}</h2>
      {description ? <p className="n-muted">{description}</p> : null}
      {children}
    </div>
  );
}

export interface SectionTitleProps {
  title: string;
  count?: number;
  children?: ReactNode;
  /** 오른쪽 화살표: 전체 목록 페이지로 이동 */
  onSeeAll?: () => void;
}

export function SectionTitle({ title, count, children, onSeeAll }: SectionTitleProps) {
  return (
    <div className="n-row" style={{ gap: 8 }}>
      <h2 className="n-title">{title}</h2>
      {count !== undefined ? <span className="n-title n-muted">{count}</span> : null}
      {children}
      {onSeeAll ? (
        <span style={{ marginLeft: 'auto', marginRight: -12 }}>
          <IconButton label={`${title} 전체 보기`} icon={<ChevronRight size={24} />} onClick={onSeeAll} />
        </span>
      ) : null}
    </div>
  );
}

export interface PageHeaderProps {
  title: string;
  count?: number;
  onBack?: () => void;
}

/** 일반 페이지 상단: 뒤로 · 제목 · 개수 (진행 막대 없음) */
export function PageHeader({ title, count, onBack }: PageHeaderProps) {
  return (
    <header className="n-flow-header">
      <div className="n-row" style={{ gap: 4 }}>
        <IconButton label="이전" icon={<ChevronLeft size={26} />} onClick={onBack} />
        <h1 className="n-title">{title}</h1>
        {count !== undefined ? <span className="n-title n-muted" style={{ marginLeft: 4 }}>{count}</span> : null}
      </div>
    </header>
  );
}

/** 번호 원 (온보딩·촬영 가이드 공통) */
export function StepNumber({ n }: { n: number }) {
  return (
    <span className="n-step-num" aria-hidden="true">
      {n}
    </span>
  );
}
