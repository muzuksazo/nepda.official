import { ImageIcon } from '../icons';
import { Badge, Button, FlowHeader, MediaPlaceholder, MobileScreen, ScreenTitle, SkeletonText, Stack } from '../components';
import type { HookType } from './flowData';

export interface StoryboardScene {
  imageUrl?: string;
  caption?: string;
}

export interface StoryboardScreenProps {
  hookType: HookType;
  scenes?: StoryboardScene[];
  onBack?: () => void;
  onShootingGuide?: () => void;
}

/** 안1-5 그림 콘티 (4/8) */
export function StoryboardScreen({ hookType, scenes = [{}, {}, {}, {}], onBack, onShootingGuide }: StoryboardScreenProps) {
  return (
    <MobileScreen
      header={<FlowHeader title="그림 콘티" step={4} onBack={onBack} />}
      footer={<Button label="촬영 가이드 받기" isBlock onClick={onShootingGuide} />}
    >
      <ScreenTitle title="그림으로 보면 이 느낌" description={`${hookType} 유형, 네 컷이면 끝나요.`} />

      {/* 장면 번호를 그림 위에 얹어 그림·번호·설명을 한 칸으로 묶는다(공통 영역) */}
      <ol style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '24px 12px' }}>
        {scenes.map((scene, i) => (
          <li key={i}>
            <Stack gap={8}>
              <div style={{ position: 'relative' }}>
                {scene.imageUrl ? (
                  <img
                    src={scene.imageUrl}
                    alt={`장면 ${i + 1}`}
                    style={{ width: '100%', aspectRatio: '4 / 5', objectFit: 'cover', borderRadius: 'var(--radius-md)' }}
                  />
                ) : (
                  <MediaPlaceholder ratio="4 / 5" variant="sketch">
                    <ImageIcon size={26} aria-hidden="true" />
                  </MediaPlaceholder>
                )}
                <span style={{ position: 'absolute', top: 8, left: 8 }}>
                  <Badge>장면 {i + 1}</Badge>
                </span>
              </div>
              {scene.caption ? <p className="n-small">{scene.caption}</p> : <SkeletonText widths={[92, 64]} />}
            </Stack>
          </li>
        ))}
      </ol>
    </MobileScreen>
  );
}
