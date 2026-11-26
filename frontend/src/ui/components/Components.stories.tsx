import { useState } from 'react';
import type { Meta, StoryObj } from '@storybook/react-vite';
import { fn } from 'storybook/test';
import { Download, Play } from '../icons';
import { brand } from '../brand';
import { HookTypeCard, ProjectCard } from './cards';
import { AppHeaderActions, BottomNav, CreditBadge, FlowHeader, ProfileButton, StepNumber, type NavTab } from './layout';
import { Mascot, VideoFrame } from './media';
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
  name: '상단 GNB 묶음 · 프로필',
  render: () => (
    <>
      <div className="n-row" style={{ justifyContent: 'flex-end', paddingRight: 6 }}>
        <AppHeaderActions credits={120} profile={{ name: '냅다사장' }} onCreditClick={fn()} onProfileClick={fn()} />
      </div>
      <div className="n-row" style={{ gap: 8 }}>
        <ProfileButton name="냅다사장" />
        <ProfileButton name="Jin" />
        <ProfileButton />
      </div>
    </>
  ),
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
