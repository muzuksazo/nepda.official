import type { ComponentType, ReactNode } from 'react';
import { Bell, ChevronLeft, ChevronRight, Folder, Home, Lightning, Search, User, type IconProps } from '../icons';
import { brand } from '../brand';
import { IconButton, ProgressBar } from './primitives';

export const FLOW_TOTAL_STEPS = 8;

export interface MobileScreenProps {
  /** 위 고정 영역. 없으면 노치·상태 표시줄 높이만 비워 둔다 (온보딩·로그인처럼 로고 없이 시작하는 화면) */
  header?: ReactNode;
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
      <main className="n-screen__body" tabIndex={0}>{children}</main>
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

/**
 * activeLook — 현재 탭 표시. fill: 아이콘 면을 꽉 채운다 · bold: 선만 굵게 (돋보기는 채우면 렌즈가 까만 원이 돼 알아보기 어렵다)
 */
const NAV_ITEMS: { value: NavTab; label: string; Icon: ComponentType<IconProps>; activeLook: 'fill' | 'bold' }[] = [
  { value: 'home', label: '홈', Icon: Home, activeLook: 'fill' },
  { value: 'myVideos', label: '내 영상', Icon: Folder, activeLook: 'fill' },
  // 탐색 = 다른 사람 영상을 둘러보는 탭이라 돋보기 (코드 이름은 community 그대로)
  { value: 'community', label: '탐색', Icon: Search, activeLook: 'bold' },
  { value: 'profile', label: '프로필', Icon: User, activeLook: 'fill' },
];

export interface BottomNavProps {
  active: NavTab;
  onNavigate?: (tab: NavTab) => void;
}

/** 하단 내비게이션 바: 홈 · 내 영상 · 탐색 · 프로필. 아이콘만 보이고(이름은 스크린 리더용), 현재 탭은 아이콘이 검정(다크는 흰색)으로 꽉 채워진다. */
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
              {/* 현재 탭: 아이콘을 글자색(라이트 검정·다크 흰색)으로 꽉 채운다(돋보기는 선만 굵게). 나머지: 회색 선만 */}
              <item.Icon
                size={24}
                strokeWidth={isActive && item.activeLook === 'bold' ? 2.75 : 2}
                fill={isActive && item.activeLook === 'fill' ? 'currentColor' : 'none'}
              />
            </span>
          </button>
        );
      })}
    </nav>
  );
}

/** 홈 상단 로고. 한 화면에 로고는 이것 하나뿐이다. (온보딩·로그인은 스플래시에서 로고를 보여 줬으니 두지 않는다) */
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

export interface NotificationButtonProps {
  /** 안 읽은 알림 수. 0이면 표시 없음, 1개 이상이면 빨간 점 (개수는 스크린 리더 이름으로만 알린다) */
  unreadCount?: number;
  onClick?: () => void;
}

/** 상단 GNB 알림 종: 안 읽은 알림이 있으면 오른쪽 위에 숫자 점이 붙는다 */
export function NotificationButton({ unreadCount = 0, onClick }: NotificationButtonProps) {
  return (
    <button
      type="button"
      className="n-bell"
      onClick={onClick}
      aria-label={unreadCount > 0 ? `알림, 안 읽은 알림 ${unreadCount}개` : '알림'}
    >
      <Bell size={24} aria-hidden="true" />
      {/* 안 읽은 알림이 있다는 표시만 한다. 개수는 스크린 리더 이름으로 알린다 */}
      {unreadCount > 0 ? <span className="n-bell__dot" aria-hidden="true" /> : null}
    </button>
  );
}

export interface AppHeaderActionsProps {
  credits?: number;
  onCreditClick?: () => void;
  /** 안 읽은 알림 수 */
  unreadCount?: number;
  onNotificationsClick?: () => void;
}

/** 홈 상단 오른쪽 묶음: 크레딧 · 알림 (프로필은 하단 내비게이션 탭으로 간다) */
export function AppHeaderActions({
  credits,
  onCreditClick,
  unreadCount,
  onNotificationsClick,
}: AppHeaderActionsProps) {
  return (
    <div className="n-header-actions">
      <CreditBadge credits={credits} onClick={onCreditClick} />
      <NotificationButton unreadCount={unreadCount} onClick={onNotificationsClick} />
    </div>
  );
}

export interface FlowHeaderProps {
  title: string;
  step: number;
  onBack?: () => void;
  /** 뒤로 버튼의 스크린 리더 이름 (기본 "이전") */
  backLabel?: string;
}

/** 만들기 흐름 상단: [뒤로 · 제목 · 단계] 한 줄 + 바로 아래 진행 막대 */
export function FlowHeader({ title, step, onBack, backLabel = '이전' }: FlowHeaderProps) {
  return (
    <header className="n-flow-header">
      <div className="n-row" style={{ gap: 4 }}>
        <IconButton label={backLabel} icon={<ChevronLeft size={26} />} onClick={onBack} />
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
  /** 오른쪽 끝 행동 (예: "모두 읽음") */
  endContent?: ReactNode;
  /** 탭 최상위 화면(하단 내비게이션으로 들어온 화면)은 뒤로 버튼 없이 제목만 */
  isTabRoot?: boolean;
}

/** 일반 페이지 상단: 뒤로 · 제목 · 개수 (진행 막대 없음) */
export function PageHeader({ title, count, onBack, isTabRoot, endContent }: PageHeaderProps) {
  return (
    <header className={`n-flow-header${isTabRoot ? ' n-flow-header--root' : ''}`}>
      <div className="n-row" style={{ gap: 4, minHeight: 44 }}>
        {isTabRoot ? null : <IconButton label="이전" icon={<ChevronLeft size={26} />} onClick={onBack} />}
        <h1 className="n-title">{title}</h1>
        {count !== undefined ? <span className="n-title n-muted" style={{ marginLeft: 4 }}>{count}</span> : null}
        {endContent ? <div style={{ marginLeft: 'auto' }}>{endContent}</div> : null}
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
