import { useState } from 'react';
import { Download } from '../icons';
import {
  Button,
  Card,
  ConfirmSheet,
  FlowHeader,
  Mascot,
  MobileScreen,
  Note,
  PendingBadge,
  ScreenTitle,
  Switch,
  TextField,
  THUMBNAIL_CAPTION_MAX,
  ThumbnailPicker,
  type ThumbnailTemplate,
} from '../components';
import { brand } from '../brand';

export interface ThumbnailDownloadScreenProps {
  /** 팀이 만든 썸네일 템플릿들 (캐러셀에 보여 줄 순서대로) */
  templates: readonly ThumbnailTemplate[];
  /** 처음 골라 둘 템플릿 id. 없으면 첫 템플릿 */
  initialTemplateId?: string;
  onTemplateChange?: (templateId: string) => void;
  initialCaption?: string;
  onBack?: () => void;
  onDownloadVideo?: () => void;
  /** 고른 템플릿과 지금 글자로 썸네일을 내려받는다 */
  onDownloadThumbnail?: (templateId: string | null, caption: string) => void;
  /** 이 영상이 이미 커뮤니티에 올라가 있는지 */
  initialIsPublic?: boolean;
  /** 커뮤니티에 올리거나(true) 내릴 때(false) */
  onPublicChange?: (isPublic: boolean) => void;
  /** 올리기 전에 동의를 한 번 받는다. 이미 동의한 사용자는 false로 넘겨 바로 올린다 */
  needsPublishConsent?: boolean;
  /** 처음부터 올리기 동의 시트를 열어 둔다 (스토리·테스트용) */
  initialIsConfirmingPublish?: boolean;
}

/** 안1-9 썸네일·내려받기 (8/8) — 팀이 만든 템플릿 중 하나를 캐러셀에서 고르고, 글자를 넣어 내려받는다 */
export function ThumbnailDownloadScreen({
  templates,
  initialTemplateId,
  onTemplateChange,
  initialCaption = '',
  onBack,
  onDownloadVideo,
  onDownloadThumbnail,
  initialIsPublic = false,
  onPublicChange,
  needsPublishConsent = true,
  initialIsConfirmingPublish = false,
}: ThumbnailDownloadScreenProps) {
  const [caption, setCaption] = useState(initialCaption);
  const [templateId, setTemplateId] = useState<string | null>(initialTemplateId ?? templates[0]?.id ?? null);
  const [isPublic, setIsPublic] = useState(initialIsPublic);
  const [isConfirmingPublish, setIsConfirmingPublish] = useState(initialIsConfirmingPublish);

  const chooseTemplate = (next: string) => {
    setTemplateId(next);
    onTemplateChange?.(next);
  };
  const applyPublic = (next: boolean) => {
    setIsPublic(next);
    onPublicChange?.(next);
  };
  // 올릴 때만 한 번 물어본다. 내릴 때는 바로 내린다(되돌리기 쉬운 쪽은 막지 않는다)
  const requestPublic = (next: boolean) => {
    if (next && needsPublishConsent) setIsConfirmingPublish(true);
    else applyPublic(next);
  };

  return (
    <>
      <MobileScreen
        isInert={isConfirmingPublish}
        header={<FlowHeader title="썸네일·내려받기" step={8} onBack={onBack} />}
        footer={
          <>
            <Button label="영상 내려받기" isBlock icon={<Download size={20} aria-hidden="true" />} onClick={onDownloadVideo} />
            <Button
              label="썸네일 내려받기"
              variant="secondary"
              isBlock
              icon={<Download size={20} aria-hidden="true" />}
              onClick={() => onDownloadThumbnail?.(templateId, caption)}
            />
          </>
        }
      >
        <div className="n-row" style={{ gap: 12, justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <ScreenTitle title="끝! 썸네일만 골라요" description="시안 하나 콕, 글자 한 줄이면 끝." />
          <Mascot src={brand.mascot.happy} width={76} />
        </div>

        {/* 시안 → 글자 순서: 템플릿 미리보기는 팀이 만든 이미지라 입력한 글자가 반영되지 않는다 */}
        {templates.length > 0 ? (
          <ThumbnailPicker label="시안 고르기" templates={templates} value={templateId} onChange={chooseTemplate} />
        ) : null}

        <TextField
          label="썸네일 글자"
          placeholder="예: 이 도마, 미쳤다"
          value={caption}
          onChange={setCaption}
          maxLength={THUMBNAIL_CAPTION_MAX}
          hasClear
        />

        {/* 기본은 비공개. 켜면 탐색 탭에서 누구나 볼 수 있다 */}
        <Card>
          <Switch
            label="탐색에도 올리기"
            description={isPublic ? '지금 누구나 볼 수 있어요. 끄면 바로 내려가요.' : '다른 사람들도 탐색에서 이 영상을 볼 수 있어요.'}
            isChecked={isPublic}
            onChange={requestPublic}
          />
        </Card>

        <Note title="올리기 전에 AI 라벨 안내를 꼭 봐요.">
          <PendingBadge>안내 문구 미정 · FR-014</PendingBadge>
        </Note>
      </MobileScreen>

      <ConfirmSheet
        isOpen={isConfirmingPublish}
        title="탐색에 올릴까요?"
        description="올리면 누구나 이 영상을 볼 수 있어요. 여기서 스위치를 끄면 언제든 내릴 수 있어요."
        confirmLabel="올리기"
        onConfirm={() => {
          setIsConfirmingPublish(false);
          applyPublic(true);
        }}
        onClose={() => setIsConfirmingPublish(false)}
      />
    </>
  );
}
