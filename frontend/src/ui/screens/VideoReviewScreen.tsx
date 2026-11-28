import { Play } from '../icons';
import { Button, FlowHeader, IconButton, MobileScreen, ScreenTitle, Stack, VideoFrame } from '../components';

/** 15칸 중 훅이 차지하는 칸 */
const HOOK_SEGMENTS = 6;

export interface VideoReviewScreenProps {
  videoUrl?: string;
  isRendering?: boolean;
  renderStatusText?: string;
  errorMessage?: string;
  onBack?: () => void;
  onPlay?: () => void;
  onMakeThumbnail?: () => void;
}

/** 안1-8 영상 확인 (7/8) */
export function VideoReviewScreen({
  videoUrl,
  isRendering = false,
  renderStatusText,
  errorMessage,
  onBack,
  onPlay,
  onMakeThumbnail,
}: VideoReviewScreenProps) {
  return (
    <MobileScreen
      header={<FlowHeader title="영상 확인" step={7} onBack={onBack} />}
      footer={
        <Button
          label={isRendering ? '영상 만드는 중…' : '썸네일 만들기'}
          isBlock
          isDisabled={isRendering || Boolean(errorMessage)}
          onClick={onMakeThumbnail}
        />
      }
    >
      {/* 영상이 주인공인 화면이라 냅다곰은 두지 않는다 */}
      <ScreenTitle
        title={isRendering ? '잠시만요, 영상 굽는 중…' : errorMessage ? '영상 만들기에 실패했어요' : '짜잔, 영상 나왔어요'}
        description={
          isRendering
            ? renderStatusText ?? '템플릿 훅이랑 본편 영상을 이어 붙이고 있어요.'
            : errorMessage ?? '훅에서 본편까지 매끄러운지 봐 주세요.'
        }
      />

      <div className="n-row" style={{ justifyContent: 'center' }}>
        {videoUrl ? (
          <video src={videoUrl} controls playsInline className="n-video" style={{ width: 228 }} />
        ) : (
          <VideoFrame width={228} caption={isRendering ? '조금만 기다려 주세요…' : '훅 + 본편 미리보기'}>
            {isRendering ? null : (
              <IconButton label="재생" variant="solid" icon={<Play size={26} fill="currentColor" />} onClick={onPlay} />
            )}
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
        </div>
      </Stack>
    </MobileScreen>
  );
}
