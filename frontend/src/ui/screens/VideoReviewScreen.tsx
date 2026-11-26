import { Play } from '../icons';
import { Button, FlowHeader, IconButton, Mascot, MobileScreen, PendingBadge, ScreenTitle, Stack, VideoFrame } from '../components';
import { brand } from '../brand';

/** 15칸 중 훅이 차지하는 칸 (길이 비율 미정 · OQ-002, 임시값) */
const HOOK_SEGMENTS = 6;

export interface VideoReviewScreenProps {
  videoUrl?: string;
  onBack?: () => void;
  onPlay?: () => void;
  onMakeThumbnail?: () => void;
}

/** 안1-8 영상 확인 (7/8) */
export function VideoReviewScreen({ videoUrl, onBack, onPlay, onMakeThumbnail }: VideoReviewScreenProps) {
  return (
    <MobileScreen
      header={<FlowHeader title="영상 확인" step={7} onBack={onBack} />}
      footer={<Button label="썸네일 만들기" isBlock onClick={onMakeThumbnail} />}
    >
      <div className="n-row" style={{ gap: 12, justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <ScreenTitle title="짜잔, 영상 나왔어요" description="훅에서 본편까지 매끄러운지 봐 주세요." />
        <Mascot src={brand.mascot.surprised} width={76} />
      </div>

      <div className="n-row" style={{ justifyContent: 'center' }}>
        {videoUrl ? (
          <video src={videoUrl} controls className="n-video" style={{ width: 228 }} />
        ) : (
          <VideoFrame width={228} caption="훅 + 본편 미리보기">
            <IconButton label="재생" variant="solid" icon={<Play size={26} fill="currentColor" />} onClick={onPlay} />
          </VideoFrame>
        )}
      </div>

      {/* 막대와 이름을 같은 열에 맞춰 이어 읽게 한다(연속성) */}
      <Stack gap={8}>
        <div className="n-timeline" aria-hidden="true">
          {Array.from({ length: 15 }, (_, i) => (
            <span key={i} className={`n-timeline__seg${i < HOOK_SEGMENTS ? ' n-timeline__seg--hook' : ''}`} />
          ))}
        </div>
        <div className="n-timeline n-small n-bold">
          <span className="n-timeline__label--hook">훅</span>
          <span className="n-timeline__label--main">본편</span>
        </div>
        <div className="n-row n-small n-muted" style={{ gap: 8, paddingTop: 4 }}>
          전체 30초 안팎
          <PendingBadge>길이 비율 미정 · OQ-002</PendingBadge>
        </div>
      </Stack>
    </MobileScreen>
  );
}
