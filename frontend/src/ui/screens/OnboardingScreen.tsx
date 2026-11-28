import type { ReactNode } from 'react';
import { Play, Plus } from '../icons';
import { Button, MobileScreen, Stack, StepNumber, VideoFrame } from '../components';

const STEPS = [
  { title: '제품 정보를 넣어요', description: '이름이랑 한 줄이면 돼요' },
  { title: 'A·B·C 훅 중에 골라요', description: '글로 보고, 그림으로 또 봐요' },
  { title: '찍어서 올리면 끝', description: '영상이랑 썸네일까지 나와요' },
];

export interface OnboardingScreenProps {
  onStart?: () => void;
  footer?: ReactNode;
}

/**
 * 안1-1 온보딩 — 로고 없이 시작한다(스플래시에서 이미 보여 줬다).
 * 제목 → "훅 + 본편" 그림 → 만드는 순서를 위에서부터 붙여 쌓는다(제목과 그림이 한 덩어리로 읽히게).
 * 남는 공간은 아래 버튼 위로 보낸다 — 네이버플러스 스토어·KB스타뱅킹 온보딩과 같은 짜임.
 */
export function OnboardingScreen({ onStart, footer }: OnboardingScreenProps) {
  return (
    <MobileScreen footer={footer ?? <Button label="냅다 시작하기" isBlock onClick={onStart} />}>
      {/* 위 여백 48px — 닉네임 화면(제목이 위에서 93px)보다 조금 위. 헤더가 없는 화면이라 같은 높이면 위가 비어 보인다 */}
      <Stack gap={32} style={{ paddingTop: 48 }}>
        <Stack gap={8}>
          <h1 className="n-display n-display--xl">
            훅 하나 붙이면<br />
            <span className="n-mark">릴스 광고</span> 끝
          </h1>
          <p className="n-muted">아이디어만 있다면, 이제는 냅다.</p>
        </Stack>

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
      </Stack>
    </MobileScreen>
  );
}
