import { useEffect, useRef, useState } from 'react';
import { Download } from '../icons';
import {
  Button,
  Card,
  ConfirmSheet,
  FIGMA_THUMBNAIL_TEMPLATES,
  FlowHeader,
  formatThumbnailHeadline,
  MobileScreen,
  Note,
  ScreenTitle,
  Switch,
  TextField,
  THUMBNAIL_CAPTION_MAX,
  ThumbnailPicker,
  type ThumbnailTemplate as ThumbnailOption,
} from '../components';
import { THUMBNAIL_WIDTH, type ThumbnailVariant } from '../thumbnails/presets';
import { ThumbnailTemplate } from '../thumbnails/ThumbnailTemplate';

function ScaledFigmaThumbnail({
  variant,
  headline,
  badge,
  highlightWord,
  imageUrl,
  showSafeZone,
}: {
  variant: ThumbnailVariant;
  headline: string;
  badge?: string;
  highlightWord?: string;
  imageUrl?: string;
  showSafeZone?: boolean;
}) {
  const boxRef = useRef<HTMLDivElement>(null);
  const [scale, setScale] = useState(140 / THUMBNAIL_WIDTH);

  useEffect(() => {
    const el = boxRef.current;
    if (!el) return;
    const update = () => {
      const w = el.clientWidth;
      if (w > 0) setScale(w / THUMBNAIL_WIDTH);
    };
    update();
    if (typeof ResizeObserver === 'undefined') return;
    const ro = new ResizeObserver(update);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  return (
    <div
      ref={boxRef}
      style={{
        position: 'absolute',
        inset: 0,
        width: '100%',
        height: '100%',
        overflow: 'hidden',
        pointerEvents: 'none',
      }}
    >
      <ThumbnailTemplate
        variant={variant}
        badge={badge}
        headline={headline}
        highlightWord={highlightWord}
        imageUrl={imageUrl}
        showSafeZone={showSafeZone}
        scale={scale}
      />
    </div>
  );
}

export interface ThumbnailDownloadScreenProps {
  /** 정적 미리보기 템플릿들 (스토리북/레거시용). useFigmaTemplates가 true면 4종 Figma 템플릿을 라이브 렌더링한다 */
  templates?: readonly ThumbnailOption[];
  /** Storybook 4종 Figma 템플릿 라이브 렌더링 모드 */
  useFigmaTemplates?: boolean;
  /** 클린 영상 키프레임 URL (useFigmaTemplates 모드에서 4종 템플릿 배경으로 사용) */
  backgroundImageUrl?: string;
  /** 선택적 상단 배지/소제목 */
  badge?: string;
  /** 선택적 라임 강조 단어 */
  highlightWord?: string;
  /** 처음 골라 둘 템플릿 id. 없으면 첫 템플릿 */
  initialTemplateId?: string;
  onTemplateChange?: (templateId: string) => void;
  initialCaption?: string;
  onBack?: () => void;
  onDownloadVideo?: () => void;
  /** 고른 템플릿과 지금 글자로 썸네일을 내려받는다 */
  onDownloadThumbnail?: (templateId: string | null, caption: string) => void;
  /** 썸네일 생성·내려받기 진행 중 */
  isDownloadingThumbnail?: boolean;
  /** 썸네일 생성·내려받기 오류 문구 */
  thumbnailError?: string | null;
  /** AI 생성물 표기 안내 문구 (deliverables.ai_disclosure.instagram_guide) */
  aiDisclosure?: string;
  /** 이 영상이 이미 커뮤니티에 올라가 있는지 */
  initialIsPublic?: boolean;
  /** 커뮤니티에 올리거나(true) 내릴 때(false) */
  onPublicChange?: (isPublic: boolean, caption?: string) => void;
  /** 올리기 전에 동의를 한 번 받는다. 이미 동의한 사용자는 false로 넘겨 바로 올린다 */
  needsPublishConsent?: boolean;
  /** 처음부터 올리기 동의 시트를 열어 둔다 (스토리·테스트용) */
  initialIsConfirmingPublish?: boolean;
  /** 제작 흐름을 마치고 내 영상 목록 등으로 빠져나간다. changed: 썸네일 글자·시안을 고친 뒤 아직 서버에 반영하지 않았다 */
  onComplete?: (templateId: string | null, caption: string, changed: boolean) => void;
}

const DEFAULT_AI_DISCLOSURE = "인스타그램 게시 시 'AI 정보' 라벨 활성화를 권장합니다.";

/** 안1-9 썸네일·내려받기 (8/8) — 시안 중 하나를 캐러셀에서 고르고, 글자를 넣어 내려받는다 */
export function ThumbnailDownloadScreen({
  templates = [],
  useFigmaTemplates = false,
  backgroundImageUrl,
  badge,
  highlightWord,
  initialTemplateId,
  onTemplateChange,
  initialCaption = '',
  onBack,
  onDownloadVideo,
  onDownloadThumbnail,
  isDownloadingThumbnail = false,
  thumbnailError = null,
  aiDisclosure,
  initialIsPublic = false,
  onPublicChange,
  needsPublishConsent = true,
  initialIsConfirmingPublish = false,
  onComplete,
}: ThumbnailDownloadScreenProps) {
  const effectiveTemplates = useFigmaTemplates ? FIGMA_THUMBNAIL_TEMPLATES : templates;
  const [caption, setCaption] = useState(initialCaption);
  const [templateId, setTemplateId] = useState<string | null>(
    initialTemplateId ?? effectiveTemplates[0]?.id ?? null,
  );
  const [showSafeZone, setShowSafeZone] = useState(false);
  const [isPublic, setIsPublic] = useState(initialIsPublic);
  const [syncedInitialPublic, setSyncedInitialPublic] = useState(initialIsPublic);
  if (syncedInitialPublic !== initialIsPublic) {
    setSyncedInitialPublic(initialIsPublic);
    setIsPublic(initialIsPublic);
  }
  const [isConfirmingPublish, setIsConfirmingPublish] = useState(initialIsConfirmingPublish);

  const effectiveTemplateId =
    templateId && effectiveTemplates.some((t) => t.id === templateId)
      ? templateId
      : (initialTemplateId && effectiveTemplates.some((t) => t.id === initialTemplateId)
          ? initialTemplateId
          : (effectiveTemplates[0]?.id ?? null));

  const liveHeadline = formatThumbnailHeadline(caption || initialCaption);
  // 서버 썸네일에 마지막으로 반영된 글자·시안 (내려받기를 누르면 반영된다)
  const [applied, setApplied] = useState({ caption: initialCaption, templateId: initialTemplateId ?? null });
  const isChanged =
    (caption || initialCaption) !== applied.caption || effectiveTemplateId !== (applied.templateId ?? effectiveTemplateId);

  const chooseTemplate = (next: string) => {
    setTemplateId(next);
    onTemplateChange?.(next);
  };
  const applyPublic = (next: boolean) => {
    setIsPublic(next);
    onPublicChange?.(next, caption);
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
              label={isDownloadingThumbnail ? '썸네일 만드는 중…' : '썸네일 내려받기'}
              variant="secondary"
              isBlock
              isDisabled={isDownloadingThumbnail}
              icon={<Download size={20} aria-hidden="true" />}
              onClick={() => {
                setApplied({ caption: caption || initialCaption, templateId: effectiveTemplateId });
                onDownloadThumbnail?.(effectiveTemplateId, caption);
              }}
            />
            {onComplete ? (
              <Button
                label="완료 · 내 영상 보기"
                variant="ghost"
                size="md"
                isBlock
                isDisabled={isDownloadingThumbnail}
                onClick={() => onComplete(effectiveTemplateId, caption || initialCaption, isChanged)}
              />
            ) : null}
          </>
        }
      >
        {/* 썸네일 시안이 주인공인 화면이라 냅다곰은 두지 않는다 */}
        <ScreenTitle title="끝! 썸네일만 골라요" description="시안 하나 콕, 글자 한 줄이면 끝." />

        {effectiveTemplates.length > 0 ? (
          <ThumbnailPicker
            label="시안 고르기"
            templates={effectiveTemplates}
            value={effectiveTemplateId}
            onChange={chooseTemplate}
            headerEnd={
              useFigmaTemplates ? (
                <button
                  type="button"
                  role="switch"
                  aria-checked={showSafeZone}
                  onClick={() => setShowSafeZone((prev) => !prev)}
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 6,
                    padding: '5px 10px',
                    borderRadius: 999,
                    border: showSafeZone ? '1px solid var(--text)' : '1px solid var(--border)',
                    background: showSafeZone ? 'var(--text)' : 'var(--surface-weak)',
                    color: showSafeZone ? 'var(--bg)' : 'var(--text-2)',
                    fontSize: 12,
                    fontWeight: 600,
                    cursor: 'pointer',
                    lineHeight: 1.2,
                  }}
                >
                  안전 영역 보기
                </button>
              ) : undefined
            }
            renderPreview={
              useFigmaTemplates
                ? (tpl) => (
                    <ScaledFigmaThumbnail
                      variant={tpl.id as ThumbnailVariant}
                      badge={badge}
                      headline={liveHeadline}
                      highlightWord={highlightWord}
                      imageUrl={backgroundImageUrl}
                      showSafeZone={showSafeZone}
                    />
                  )
                : undefined
            }
          />
        ) : null}

        <TextField
          label="썸네일 글자"
          placeholder="예: 3초 만에 물기 순삭"
          value={caption}
          onChange={setCaption}
          maxLength={THUMBNAIL_CAPTION_MAX}
          hasClear
        />

        {thumbnailError ? (
          <div role="alert">
            <Note title="썸네일을 만들지 못했어요">
              <span className="n-small n-muted">{thumbnailError}</span>
            </Note>
          </div>
        ) : null}

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
          <span className="n-small n-muted">{aiDisclosure || DEFAULT_AI_DISCLOSURE}</span>
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
