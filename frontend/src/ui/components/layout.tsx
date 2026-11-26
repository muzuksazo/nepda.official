import type { ComponentType, ReactNode } from 'react';
import { ChevronLeft, ChevronRight, Folder, Home, Lightning, User, Users, type IconProps } from '../icons';
import { brand } from '../brand';
import { IconButton, ProgressBar } from './primitives';

export const FLOW_TOTAL_STEPS = 8;

export interface MobileScreenProps {
  header: ReactNode;
  children: ReactNode;
  footer?: ReactNode;
  /** 버튼 바로 위 한 줄 요약. 결정 직전에 확인할 정보를 버튼과 같은 영역에 묶는다. */
  footerSummary?: ReactNode;
  /** 하단 내비게이션 바 (탭 최상위 화면에서만) */
  bottomNav?: ReactNode;
  /** 확인 시트 같은 대화상자가 떠 있는 동안 화면 전체를 조작·읽기 대상에서 뺀다 */
  isInert?: boolean;
}

export function MobileScreen({ header, children, footer, footerSummary, bottomNav, isInert }: MobileScreenProps) {
  const footerEl = footer ? (
    <footer className="n-screen__footer">
      {footerSummary ? <div className="n-screen__summary">{footerSummary}</div> : null}
      {footer}
    </footer>
  ) : null;
  return (
    <div className="n-screen" inert={isInert}>
      <div className="n-screen__header">{header}</div>
      <main className="n-screen__body">{children}</main>
      {bottomNav ? (
        <div className="n-screen__bottom">
          {footerEl}
          {bottomNav}
        </div>
      ) : (
        footerEl
      )}
    </div>
  );
}

export type NavTab = 'home' | 'myVideos' | 'community' | 'profile';

const NAV_ITEMS: { value: NavTab; label: string; Icon: ComponentType<IconProps> }[] = [
  { value: 'home', label: '홈', Icon: Home },
  { value: 'myVideos', label: '내 영상', Icon: Folder },
  { value: 'community', label: '커뮤니티', Icon: Users },
  { value: 'profile', label: '프로필', Icon: User },
];

export interface BottomNavProps {
  active: NavTab;
  onNavigate?: (tab: NavTab) => void;
}

/** 하단 내비게이션 바: 홈 · 내 영상 · 커뮤니티 · 프로필. 아이콘만 보이고(이름은 스크린 리더용), 현재 탭은 아이콘이 검정(다크는 흰색)으로 꽉 채워진다. */
export function BottomNav({ active, onNavigate }: BottomNavProps) {
  return (
    <nav className="n-bottom-nav" aria-label="주요 메뉴">
      {NAV_ITEMS.map((item) => {
        const isActive = item.value === active;
        return (
          <button
            key={item.value}
            type="button"
            className={`n-bottom-nav__item${isActive ? ' is-active' : ''}`}
            aria-label={item.label}
            aria-current={isActive ? 'page' : undefined}
            onClick={() => onNavigate?.(item.value)}
          >
            <span className="n-bottom-nav__icon" aria-hidden="true">
              {/* 현재 탭: 아이콘을 글자색(라이트 검정·다크 흰색)으로 꽉 채운다. 나머지: 회색 선만 */}
              <item.Icon size={24} strokeWidth={2} fill={isActive ? 'currentColor' : 'none'} />
            </span>
          </button>
        );
      })}
    </nav>
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

export interface CreditBadgeProps {
  /** 남은 크레딧. 아직 못 불러왔으면 undefined → "—" */
  credits?: number;
  onClick?: () => void;
}

/** 상단 GNB 오른쪽 크레딧 잔액. 누르면 크레딧 화면(충전·내역)으로 간다. */
export function CreditBadge({ credits, onClick }: CreditBadgeProps) {
  const shown = credits === undefined ? '—' : credits.toLocaleString('ko-KR');
  return (
    <button
      type="button"
      className="n-credit"
      onClick={onClick}
      aria-label={credits === undefined ? '크레딧 불러오는 중' : `남은 크레딧 ${shown}, 크레딧 보기`}
    >
      <span className="n-credit__icon" aria-hidden="true">
        <Lightning size={12} strokeWidth={2.5} fill="currentColor" />
      </span>
      <span className="n-credit__value n-num">{shown}</span>
    </button>
  );
}

export interface AvatarProps {
  /** 닉네임. 사진이 없으면 첫 글자를 보여 준다 */
  name?: string;
  imageUrl?: string;
  /** sm 32px(상단 GNB) · lg 56px(내 정보) */
  size?: 'sm' | 'lg';
}

/** 프로필 원. 사진 → 닉네임 첫 글자 → 사람 아이콘 순으로 대체한다. 장식이라 이름은 옆 글자가 전한다. */
export function Avatar({ name, imageUrl, size = 'sm' }: AvatarProps) {
  const initial = name?.trim().charAt(0);
  return (
    <span className={`n-avatar${size === 'lg' ? ' n-avatar--lg' : ''}`} aria-hidden="true">
      {imageUrl ? <img src={imageUrl} alt="" /> : initial ? initial : <User size={size === 'lg' ? 28 : 18} strokeWidth={2.25} />}
    </span>
  );
}

export interface ProfileButtonProps {
  /** 닉네임. 사진이 없으면 첫 글자를 보여 준다 */
  name?: string;
  imageUrl?: string;
  onClick?: () => void;
}

/** 상단 GNB 프로필 원. 누르면 내 정보로 간다. */
export function ProfileButton({ name, imageUrl, onClick }: ProfileButtonProps) {
  return (
    <button type="button" className="n-avatar-btn" onClick={onClick} aria-label={name ? `${name} 프로필` : '내 프로필'}>
      <Avatar name={name} imageUrl={imageUrl} />
    </button>
  );
}

export interface AppHeaderActionsProps {
  credits?: number;
  onCreditClick?: () => void;
  profile?: { name?: string; imageUrl?: string };
  onProfileClick?: () => void;
}

/** 홈 상단 오른쪽 묶음: 크레딧 · 프로필 */
export function AppHeaderActions({ credits, onCreditClick, profile, onProfileClick }: AppHeaderActionsProps) {
  return (
    <div className="n-header-actions">
      <CreditBadge credits={credits} onClick={onCreditClick} />
      <ProfileButton name={profile?.name} imageUrl={profile?.imageUrl} onClick={onProfileClick} />
    </div>
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
  /** 탭 최상위 화면(하단 내비게이션으로 들어온 화면)은 뒤로 버튼 없이 제목만 */
  isTabRoot?: boolean;
}

/** 일반 페이지 상단: 뒤로 · 제목 · 개수 (진행 막대 없음) */
export function PageHeader({ title, count, onBack, isTabRoot }: PageHeaderProps) {
  return (
    <header className={`n-flow-header${isTabRoot ? ' n-flow-header--root' : ''}`}>
      <div className="n-row" style={{ gap: 4, minHeight: 44 }}>
        {isTabRoot ? null : <IconButton label="이전" icon={<ChevronLeft size={26} />} onClick={onBack} />}
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
