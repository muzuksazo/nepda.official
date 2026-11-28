import { useState, type ReactNode } from 'react';
import { brand } from '../brand';
import {
  Avatar,
  Badge,
  BottomNav,
  Button,
  ChoiceChips,
  ConfirmSheet,
  CreditBalanceCard,
  ListGroup,
  ListRow,
  Mascot,
  MobileScreen,
  PageHeader,
  SkeletonText,
  Stack,
  StatTile,
  type NavTab,
} from '../components';
import { Bell, FileText, Help, Logout, ShieldCheck, Stars } from '../icons';
import type { ThemeSetting } from '../NapdaProvider';
import type { MyVideosTab } from './MyVideosScreen';

/** GET /v1/auth/me 의 user — 구글 계정에서 온 값이라 여기서 고치지 않는다 */
export interface ProfileUser {
  name?: string;
  email: string;
  imageUrl?: string;
}

export type ProfileDoc = 'help' | 'terms' | 'privacy' | 'aiLabel';
export type ProfileConfirm = 'logout' | 'delete';

export interface ProfileScreenProps {
  /** 로그인한 사용자. 없으면(null) 로그인 안내를 보여 준다 */
  user?: ProfileUser | null;
  /** 내 정보를 불러오는 중: 계정·크레딧 자리에 스켈레톤을 보여 준다 */
  isLoading?: boolean;
  /** 크레딧 잔액 */
  credits?: number;
  videoCounts?: { inProgress: number; completed: number };
  /** 영상 보관 기간(일). 기본 7일 */
  retentionDays?: number;
  themeMode?: ThemeSetting;
  onThemeModeChange?: (mode: ThemeSetting) => void;
  onNavigate?: (tab: NavTab) => void;
  /** 크레딧 카드의 "충전하기" */
  onChargeClick?: () => void;
  /** 크레딧 카드의 "내역" → 크레딧 내역 */
  onCreditHistoryClick?: () => void;
  /** 숫자 타일 → 내 영상의 해당 탭 */
  onOpenMyVideos?: (tab: MyVideosTab) => void;
  onOpenDoc?: (doc: ProfileDoc) => void;
  onLogout?: () => void;
  /** 실제 회원 탈퇴 API가 연동된 경우 확인 시트 뒤 호출 */
  onDeleteAccount?: () => void;
  /** 자동 탈퇴 대신 고객지원 안내를 열 때 호출 (거짓 삭제 안내 방지) */
  onRequestDeleteSupport?: () => void;
  onSignIn?: () => void;
  /** 로그인 전 상태의 버튼 자리. 실제 앱은 여기에 Google 공식 로그인 버튼(GIS)을 넣는다 */
  signInSlot?: ReactNode;
  /** 처음부터 열어 둘 확인 시트 (스토리·테스트용) */
  initialConfirm?: ProfileConfirm;
}

const THEME_ORDER: ThemeSetting[] = ['system', 'light', 'dark'];
const THEME_LABELS: Record<ThemeSetting, string> = { system: '기기 설정', light: '라이트', dark: '다크' };

/** 안3-3 내 정보 — 하단 내비게이션 '프로필' 탭. 계정 · 크레딧 · 내 영상 요약 · 설정 · 약관 · 로그아웃 */
export function ProfileScreen({
  user,
  isLoading,
  credits,
  videoCounts,
  retentionDays = 7,
  themeMode = 'system',
  onThemeModeChange,
  onNavigate,
  onChargeClick,
  onCreditHistoryClick,
  onOpenMyVideos,
  onOpenDoc,
  onLogout,
  onDeleteAccount,
  onRequestDeleteSupport,
  onSignIn,
  signInSlot,
  initialConfirm,
}: ProfileScreenProps) {
  const [confirm, setConfirm] = useState<ProfileConfirm | null>(initialConfirm ?? null);
  const isSignedOut = !isLoading && !user;
  const openDoc = (doc: ProfileDoc) => (onOpenDoc ? () => onOpenDoc(doc) : undefined);

  const helpGroup = (
    <ListGroup title="도움말·약관">
      <ListRow icon={<Help size={20} />} label="도움말·문의" onClick={openDoc('help')} />
      <ListRow icon={<FileText size={20} />} label="이용약관" onClick={openDoc('terms')} />
      <ListRow icon={<ShieldCheck size={20} />} label="개인정보 처리방침" onClick={openDoc('privacy')} />
      <ListRow icon={<Stars size={20} />} label="AI 라벨 안내" onClick={openDoc('aiLabel')} />
    </ListGroup>
  );

  const settingsGroup = (
    <ListGroup
      title="설정"
      lead={
        <ChoiceChips
          label="화면 모드"
          options={THEME_ORDER.map((mode) => THEME_LABELS[mode])}
          value={THEME_LABELS[themeMode]}
          onChange={(label) => {
            const mode = THEME_ORDER.find((m) => THEME_LABELS[m] === label);
            if (mode) onThemeModeChange?.(mode);
          }}
        />
      }
    >
      <ListRow
        icon={<Bell size={20} />}
        label="영상 완성 알림"
        endContent={<span className="n-small n-muted">앱 내 알림</span>}
      />
    </ListGroup>
  );

  const videosGroup = (
    <ListGroup
      title="내 영상"
      lead={
        <div className="n-stat-grid">
          <StatTile label="진행 중" value={videoCounts?.inProgress} onClick={() => onOpenMyVideos?.('inProgress')} />
          <StatTile label="완료" value={videoCounts?.completed} onClick={() => onOpenMyVideos?.('completed')} />
        </div>
      }
      note={`만든 날부터 ${retentionDays}일 동안 보관돼요.`}
    />
  );

  let body: ReactNode;
  if (isSignedOut) {
    // 로그인이 풀렸을 때: 냅다곰 + 한 줄 안내, 로그인 버튼은 하단 고정
    body = (
      <>
        <Stack gap={16} align="center" justify="center" style={{ flex: 1, textAlign: 'center', padding: '24px 0' }}>
          <Mascot src={brand.mascot.lying} />
          <Stack gap={8} align="center">
            <h2 className="n-display">로그인이 풀렸어요</h2>
            <p className="n-muted">다시 로그인하면 만들던 영상이 그대로 있어요.</p>
          </Stack>
        </Stack>
        {helpGroup}
      </>
    );
  } else {
    const displayName = user ? user.name?.trim() || user.email.split('@')[0] : '';
    body = (
      <>
        {user ? (
          <section className="n-profile" aria-label="내 계정">
            <Avatar name={displayName} imageUrl={user.imageUrl} size="lg" />
            <div className="n-profile__text">
              <h2 className="n-profile__name">{displayName}</h2>
              <p className="n-profile__email">{user.email}</p>
            </div>
            <Badge>구글 계정</Badge>
          </section>
        ) : (
          <div className="n-profile" aria-hidden="true">
            <span className="n-avatar n-avatar--lg n-shimmer" />
            <div className="n-profile__text">
              <SkeletonText widths={[36, 62]} />
            </div>
          </div>
        )}

        {isLoading ? (
          <div className="n-card n-wallet n-wallet--loading" aria-hidden="true">
            <SkeletonText widths={[28, 44]} />
          </div>
        ) : (
          <CreditBalanceCard credits={credits} onChargeClick={onChargeClick} onHistoryClick={onCreditHistoryClick} />
        )}

        {isLoading ? (
          <p className="napda-visually-hidden" role="status">
            내 정보를 불러오고 있어요
          </p>
        ) : null}

        {videosGroup}
        {settingsGroup}
        {helpGroup}

        {user ? (
          <>
            <ListGroup title="계정">
              <ListRow icon={<Logout size={20} />} label="로그아웃" hasChevron={false} onClick={() => setConfirm('logout')} />
            </ListGroup>
            <div className="n-profile__leave">
              <button
                type="button"
                className="n-link-btn"
                onClick={() => {
                  if (onRequestDeleteSupport && !onDeleteAccount) {
                    onRequestDeleteSupport();
                  } else {
                    setConfirm('delete');
                  }
                }}
              >
                탈퇴하기
              </button>
            </div>
          </>
        ) : null}
      </>
    );
  }

  return (
    <>
      <MobileScreen
        header={<PageHeader title="내 정보" isTabRoot />}
        footer={isSignedOut ? (signInSlot ?? <Button label="구글 계정으로 로그인" isBlock onClick={onSignIn} />) : undefined}
        bottomNav={<BottomNav active="profile" onNavigate={onNavigate} />}
        isInert={confirm !== null}
      >
        {body}
      </MobileScreen>

      <ConfirmSheet
        isOpen={confirm === 'logout'}
        title="로그아웃할까요?"
        description="다시 로그인하면 그대로 이어져요."
        confirmLabel="로그아웃"
        onConfirm={() => {
          setConfirm(null);
          onLogout?.();
        }}
        onClose={() => setConfirm(null)}
      />
      <ConfirmSheet
        isOpen={confirm === 'delete'}
        isDestructive
        title="정말 탈퇴할까요?"
        description="영상과 프로젝트가 전부 지워져요. 되돌릴 수 없어요."
        confirmLabel="탈퇴하기"
        cancelLabel="계속 쓸게요"
        onConfirm={() => {
          setConfirm(null);
          onDeleteAccount?.();
        }}
        onClose={() => setConfirm(null)}
      />
    </>
  );
}
