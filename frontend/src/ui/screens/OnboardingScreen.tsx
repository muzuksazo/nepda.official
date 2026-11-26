import { Play, Plus } from '../icons';
import { BrandHeader, Button, MobileScreen, Stack, StepNumber, VideoFrame } from '../components';

const STEPS = [
  { title: '제품 정보를 넣어요', description: '이름이랑 한 줄이면 돼요' },
  { title: 'A·B·C 훅 중에 골라요', description: '글로 보고, 그림으로 또 봐요' },
  { title: '찍어서 올리면 끝', description: '영상이랑 썸네일까지 나와요' },
];

export interface OnboardingScreenProps {
  onStart?: () => void;
}

/** 안1-1 온보딩 — 로고는 상단 헤더 하나뿐. 본문 그림은 "훅 + 본편" 개념을 보여 준다. */
export function OnboardingScreen({ onStart }: OnboardingScreenProps) {
  return (
    <MobileScreen header={<BrandHeader />} footer={<Button label="냅다 시작하기" isBlock onClick={onStart} />}>
      <figure
        className="n-row"
        style={{ gap: 12, justifyContent: 'center', padding: '20px 0', background: 'var(--bg-weak)', borderRadius: 20 }}
        aria-label="훅 영상 뒤에 제품 영상이 이어지는 예시"
      >
        <VideoFrame width={104} caption="훅 3초">
          <Play size={22} aria-hidden="true" />
        </VideoFrame>
        <Plus size={20} aria-hidden="true" style={{ color: 'var(--text-3)' }} />
        <VideoFrame width={104} caption="내 제품 영상">
          <Play size={22} aria-hidden="true" />
        </VideoFrame>
      </figure>

      <Stack gap={8}>
        <h2 className="n-display n-display--xl">
          영상에 훅 하나 붙이면<br />
          <span className="n-mark">릴스 광고</span> 끝
        </h2>
        <p className="n-muted">아이디어만 있다면, 이제는 냅다.</p>
      </Stack>

      <ol aria-label="만드는 순서">
        {STEPS.map((s, i) => (
          <li key={s.title} className="n-steps__item">
            <StepNumber n={i + 1} />
            <Stack gap={2} style={{ paddingTop: 4 }}>
              <span className="n-bold">{s.title}</span>
              <span className="n-small n-muted">{s.description}</span>
            </Stack>
          </li>
        ))}
      </ol>
    </MobileScreen>
  );
}
