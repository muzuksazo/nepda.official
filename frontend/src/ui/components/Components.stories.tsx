import { useState } from 'react';
import type { Meta, StoryObj } from '@storybook/react-vite';
import { fn } from 'storybook/test';
import { Bell, Download, FileText, Help, Logout, Play } from '../icons';
import { brand } from '../brand';
import { CreditBalanceCard, HookTypeCard, ProjectCard, StatTile, TimeEstimate, VideoTile } from './cards';
import { AppHeaderActions, Avatar, BottomNav, CreditBadge, FlowHeader, NotificationButton, ProfileButton, StepNumber, type NavTab } from './layout';
import { ListGroup, ListRow } from './list';
import { Mascot, VideoFrame } from './media';
import { ConfirmSheet } from './Sheet';
import { CreditChange, CreditPackagePicker } from './credit';
import { ThumbnailPicker } from './thumbnail';
import { SAMPLE_CREDIT_PACKAGES, SAMPLE_CREDITS_PER_VIDEO, SAMPLE_THUMBNAIL_TEMPLATES } from '../screens/sampleProjects';
import {
  Badge,
  Button,
  ChoiceChips,
  FilePicker,
  IconButton,
  Note,
  PendingBadge,
  SkeletonText,
  Stack,
  Switch,
  TextField,
} from './primitives';

/** /DESIGN.md 토큰으로 직접 만든 냅다 컴포넌트. 라임은 선택 체크·브랜드 배지·강조 단어에만 쓴다. */
const meta = {
  title: 'NAPDA/컴포넌트',
  parameters: { layout: 'padded' },
  decorators: [
    (Story) => (
      <div style={{ width: 360 }}>
        <Stack gap={16}>
          <Story />
        </Stack>
      </div>
    ),
  ],
} satisfies Meta;

export default meta;
type Story = StoryObj<typeof meta>;

export const Buttons: Story = {
  name: '버튼',
  render: () => (
    <>
      <Button label="영상 만들기" isBlock onClick={fn()} />
      <Button label="그림으로 보기" variant="secondary" isBlock />
      <Button label="시안 없이 냅다 만들기" variant="ghost" size="md" isBlock />
      <Button label="훅 붙여서 만들기" isBlock isDisabled />
      <Button label="영상 내려받기" isBlock icon={<Download size={20} aria-hidden="true" />} />
      <div className="n-row" style={{ gap: 8 }}>
        <Button label="이어하기" variant="secondary" size="md" />
        <Button label="가이드 다시 보기" variant="ghost" size="sm" />
      </div>
    </>
  ),
};

export const Inputs: Story = {
  name: '입력',
  render: function Render() {
    const [name, setName] = useState('');
    const [cat, setCat] = useState<string | null>('주방');
    const [file, setFile] = useState<File | null>(null);
    return (
      <>
        <TextField label="제품 이름" placeholder="예: 접이식 실리콘 도마" value={name} onChange={setName} isRequired hasClear />
        <ChoiceChips label="카테고리" options={['자취', '주방', '문구']} value={cat} onChange={setCat} />
        <FilePicker label="제품 사진" isOptional variant="compact" accept="image/*" value={file} onChange={setFile} placeholder="사진 고르기" />
      </>
    );
  },
};

export const Badges: Story = {
  name: '배지 · 안내',
  render: () => (
    <>
      <div className="n-row" style={{ gap: 8, flexWrap: 'wrap' }}>
        <Badge tone="brand">B 유형</Badge>
        <Badge>장면 1</Badge>
        <PendingBadge>크레딧 미정 · OQ-003</PendingBadge>
      </div>
      <Note title="촬영하고 다시 들어오면 여기서 이어져요.">
        <PendingBadge>이어하기 방식 미정 · OQ-008</PendingBadge>
      </Note>
    </>
  ),
};

export const Header: Story = {
  name: '흐름 헤더',
  render: () => <FlowHeader title="제품 정보" step={3} onBack={fn()} />,
};

export const Credit: Story = {
  name: '크레딧 배지',
  render: () => (
    <div className="n-row" style={{ gap: 12 }}>
      <CreditBadge credits={120} onClick={fn()} />
      <CreditBadge credits={2400} onClick={fn()} />
      <CreditBadge />
    </div>
  ),
};

export const HeaderActions: Story = {
  name: '상단 GNB 묶음 · 알림 · 프로필',
  render: () => (
    <>
      <div className="n-row" style={{ justifyContent: 'flex-end', paddingRight: 6 }}>
        <AppHeaderActions
          credits={120}
          unreadCount={3}
          profile={{ name: '냅다사장' }}
          onCreditClick={fn()}
          onNotificationsClick={fn()}
          onProfileClick={fn()}
        />
      </div>
      {/* 안 읽은 알림: 없음 · 1개 · 12개("9+") */}
      <div className="n-row" style={{ gap: 8 }}>
        <NotificationButton />
        <NotificationButton unreadCount={1} />
        <NotificationButton unreadCount={12} />
      </div>
      <div className="n-row" style={{ gap: 8 }}>
        <ProfileButton name="냅다사장" />
        <ProfileButton name="Jin" />
        <ProfileButton />
      </div>
      <div className="n-row" style={{ gap: 12 }}>
        <Avatar name="냅다사장" size="lg" />
        <Avatar size="lg" />
      </div>
    </>
  ),
};

export const Wallet: Story = {
  name: '크레딧 카드 · 숫자 타일 · 예상 시간',
  render: () => (
    <>
      <CreditBalanceCard credits={2400} onChargeClick={fn()} />
      <CreditBalanceCard credits={0} hasFreeVideo onChargeClick={fn()} />
      <CreditBalanceCard credits={0} onChargeClick={fn()} />
      <div className="n-stat-grid">
        <StatTile label="진행 중" value={3} onClick={fn()} />
        <StatTile label="완료" onClick={fn()} />
      </div>
      <TimeEstimate
        total="약 2~3분"
        stages={[
          { label: '훅 영상 뽑기', time: '1~2분' },
          { label: '본편에 이어 붙이기', time: '30초' },
        ]}
      />
    </>
  ),
};

export const Toggles: Story = {
  name: '스위치 · 영상 타일',
  render: function Render() {
    const [isOn, setIsOn] = useState(true);
    return (
      <>
        <Switch label="커뮤니티에도 올리기" description="다른 사람들도 이 영상을 볼 수 있어요." isChecked={isOn} onChange={setIsOn} />
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 2 }}>
          <VideoTile caption="이 도마, 미쳤다" label="실리콘 접이식 도마, 도마왕" likeCount={1284} onClick={fn()} />
          <VideoTile caption="설거지 3분 컷" label="실리콘 수세미, 설거지장인" likeCount={12300} onClick={fn()} />
          <span className="n-video-tile n-video-tile--skeleton n-shimmer" />
        </div>
      </>
    );
  },
};

export const Lists: Story = {
  name: '목록 줄',
  render: () => (
    <div style={{ paddingInline: 20 }}>
      <ListGroup title="도움말·약관" note="줄을 누르면 해당 화면으로 가요.">
        <ListRow icon={<Help size={20} />} label="도움말·문의" onClick={fn()} />
        <ListRow icon={<FileText size={20} />} label="이용약관" description="2026년 11월 개정" onClick={fn()} />
        <ListRow icon={<Bell size={20} />} label="영상 완성 알림" endContent={<PendingBadge>방식 미정</PendingBadge>} />
        <ListRow icon={<Logout size={20} />} label="로그아웃" hasChevron={false} onClick={fn()} />
      </ListGroup>
    </div>
  ),
};

export const Sheets: Story = {
  name: '확인 시트',
  render: function Render() {
    const [open, setOpen] = useState<'logout' | 'delete' | null>(null);
    return (
      <>
        <Button label="로그아웃 확인 열기" variant="secondary" isBlock onClick={() => setOpen('logout')} />
        <Button label="탈퇴 확인 열기 (되돌릴 수 없는 행동)" variant="secondary" isBlock onClick={() => setOpen('delete')} />
        <ConfirmSheet
          isOpen={open === 'logout'}
          title="로그아웃할까요?"
          description="다시 로그인하면 그대로 이어져요."
          confirmLabel="로그아웃"
          onConfirm={() => setOpen(null)}
          onClose={() => setOpen(null)}
        />
        <ConfirmSheet
          isOpen={open === 'delete'}
          isDestructive
          title="정말 탈퇴할까요?"
          description="영상과 프로젝트가 전부 지워져요. 되돌릴 수 없어요."
          confirmLabel="탈퇴하기"
          cancelLabel="계속 쓸게요"
          onConfirm={() => setOpen(null)}
          onClose={() => setOpen(null)}
        />
      </>
    );
  },
};

export const BottomNavigation: Story = {
  name: '하단 내비게이션',
  render: function Render() {
    const [tab, setTab] = useState<NavTab>('home');
    return (
      <div style={{ marginInline: -16 }}>
        <BottomNav active={tab} onNavigate={setTab} />
      </div>
    );
  },
};

export const HookCards: Story = {
  name: '훅 유형 카드',
  render: function Render() {
    const [a, setA] = useState(false);
    const [b, setB] = useState(true);
    return (
      <>
        <HookTypeCard type="A" description="제품과 상관없는 장면으로 시작해요." isSelected={a} onChange={setA} />
        <HookTypeCard type="B" description="제품을 살짝 짐작할 수 있는 장면으로 시작해요." isSelected={b} onChange={setB} />
      </>
    );
  },
};

export const ProjectCards: Story = {
  name: '프로젝트 카드',
  render: () => (
    <>
      <ProjectCard
        productName="실리콘 접이식 도마"
        status="촬영 가이드까지 받았어요"
        completedSteps={5}
        nextStep="찍은 영상 올리기"
        actionLabel="이어하기"
      />
      <ProjectCard productName="원목 데스크 정리함" status="영상과 썸네일을 만들었어요" actionLabel="다시 받기" />
    </>
  ),
};

export const ChargePackages: Story = {
  name: '충전 묶음 · 잔액 변화',
  render: function Render() {
    const [picked, setPicked] = useState<string | null>('c100');
    return (
      <>
        <CreditPackagePicker
          label="충전할 크레딧"
          packages={SAMPLE_CREDIT_PACKAGES}
          value={picked}
          onChange={setPicked}
          creditsPerVideo={SAMPLE_CREDITS_PER_VIDEO}
        />
        <CreditChange from={5} to={105} />
      </>
    );
  },
};

export const Thumbnails: Story = {
  name: '썸네일 시안 고르기',
  render: function Render() {
    const [picked, setPicked] = useState<string | null>(SAMPLE_THUMBNAIL_TEMPLATES[0].id);
    const [pickedEmpty, setPickedEmpty] = useState<string | null>(null);
    return (
      <>
        <ThumbnailPicker label="시안 고르기" templates={SAMPLE_THUMBNAIL_TEMPLATES} value={picked} onChange={setPicked} />
        {/* 미리보기 이미지를 아직 안 넣은 템플릿 */}
        <ThumbnailPicker
          label="이미지 넣기 전"
          templates={SAMPLE_THUMBNAIL_TEMPLATES.map((template) => ({ ...template, previewUrl: undefined }))}
          value={pickedEmpty}
          onChange={setPickedEmpty}
        />
      </>
    );
  },
};

export const BrandBits: Story = {
  name: '번호 · 영상 프레임 · 냅다곰',
  render: () => (
    <>
      <div className="n-row" style={{ gap: 8 }}>
        <StepNumber n={1} />
        <StepNumber n={2} />
        <StepNumber n={3} />
      </div>
      <div className="n-row" style={{ gap: 16, alignItems: 'flex-end' }}>
        <VideoFrame width={120} caption="미리보기">
          <IconButton label="재생" variant="solid" icon={<Play size={24} fill="currentColor" />} />
        </VideoFrame>
      </div>
      <div className="n-row" style={{ gap: 12, alignItems: 'flex-end' }}>
        <Mascot src={brand.mascot.clapboard} width={80} />
        <Mascot src={brand.mascot.lying} width={90} />
        <Mascot src={brand.mascot.surprised} width={64} />
        <Mascot src={brand.mascot.happy} width={70} />
      </div>
      <SkeletonText widths={[100, 80, 56]} />
    </>
  ),
};
