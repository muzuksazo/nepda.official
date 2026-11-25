import {
  Button,
  FlowHeader,
  MobileScreen,
  Note,
  PendingBadge,
  ScreenTitle,
  SkeletonText,
  Stack,
  StepNumber,
} from '../components';

export interface GuideScene {
  instruction?: string;
  duration?: string;
}

export interface ShootingGuideScreenProps {
  scenes?: GuideScene[];
  onBack?: () => void;
  onUpload?: () => void;
}

/** 안1-6 촬영 가이드 (5/8) */
export function ShootingGuideScreen({ scenes = [{}, {}, {}, {}], onBack, onUpload }: ShootingGuideScreenProps) {
  return (
    <MobileScreen
      header={<FlowHeader title="촬영 가이드" step={5} onBack={onBack} />}
      footer={<Button label="찍은 영상 올리기" isBlock onClick={onUpload} />}
    >
      <ScreenTitle title="이대로만 찍어요" description="훅까지 합쳐 30초 안팎이에요.">
        <PendingBadge>본편 길이 미정 · OQ-002</PendingBadge>
      </ScreenTitle>

      {/* 온보딩과 같은 번호 원 + 연결선: 순서대로 찍는다는 흐름(유사성·연속성) */}
      <ol aria-label="촬영 순서">
        {scenes.map((scene, i) => (
          <li key={i} className="n-steps__item">
            <StepNumber n={i + 1} />
            <Stack gap={8} style={{ paddingTop: 4 }}>
              <span className="n-bold">장면 {i + 1}</span>
              {scene.instruction ? (
                <span className="n-small n-muted">{scene.instruction}</span>
              ) : (
                <SkeletonText widths={[100, 62]} />
              )}
            </Stack>
            <div style={{ paddingTop: 4 }}>
              {scene.duration ? <span className="n-small n-bold">{scene.duration}</span> : <PendingBadge>길이</PendingBadge>}
            </div>
          </li>
        ))}
      </ol>

      <Note title="찍고 오면 여기서 이어져요.">
        <PendingBadge>이어하기 방식 미정 · OQ-008</PendingBadge>
      </Note>
    </MobileScreen>
  );
}
