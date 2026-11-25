import { useState } from 'react';
import { Download } from 'lucide-react';
import {
  Button,
  FlowHeader,
  Mascot,
  MobileScreen,
  Note,
  PendingBadge,
  ScreenTitle,
  TextField,
  VideoFrame,
} from '../components';
import { brand } from '../brand';

export interface ThumbnailDownloadScreenProps {
  thumbnailUrl?: string;
  initialCaption?: string;
  onBack?: () => void;
  onDownloadVideo?: () => void;
  onDownloadThumbnail?: (caption: string) => void;
}

/** 안1-9 썸네일·내려받기 (8/8) */
export function ThumbnailDownloadScreen({
  thumbnailUrl,
  initialCaption = '',
  onBack,
  onDownloadVideo,
  onDownloadThumbnail,
}: ThumbnailDownloadScreenProps) {
  const [caption, setCaption] = useState(initialCaption);

  return (
    <MobileScreen
      header={<FlowHeader title="썸네일·내려받기" step={8} onBack={onBack} />}
      footer={
        <>
          <Button label="영상 내려받기" isBlock icon={<Download size={20} aria-hidden="true" />} onClick={onDownloadVideo} />
          <Button
            label="썸네일 내려받기"
            variant="secondary"
            isBlock
            icon={<Download size={20} aria-hidden="true" />}
            onClick={() => onDownloadThumbnail?.(caption)}
          />
        </>
      }
    >
      <div className="n-row" style={{ gap: 12, justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <ScreenTitle title="끝! 썸네일만 챙겨요" />
        <Mascot src={brand.mascot.cheer} width={64} />
      </div>

      {/* 입력한 글자가 바로 위 썸네일에 겹쳐 보인다: 입력과 결과를 한 덩어리로 */}
      <div className="n-row" style={{ justifyContent: 'center' }}>
        {thumbnailUrl ? (
          <img src={thumbnailUrl} alt="썸네일 미리보기" className="n-video" style={{ width: 180, objectFit: 'cover' }} />
        ) : (
          <VideoFrame
            width={180}
            topContent={<span className="n-thumb-caption">{caption || '썸네일 글자'}</span>}
            caption="썸네일 미리보기"
          />
        )}
      </div>

      <TextField
        label="썸네일 글자"
        placeholder="예: 이 도마, 미쳤다"
        value={caption}
        onChange={setCaption}
        hasClear
      />

      <Note title="올리기 전에 AI 라벨 안내를 꼭 봐요.">
        <PendingBadge>안내 문구 미정 · FR-014</PendingBadge>
      </Note>
    </MobileScreen>
  );
}
