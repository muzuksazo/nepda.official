import { useRef, useState, type CSSProperties, type DragEvent, type PointerEvent } from 'react';
import type { Meta, StoryObj } from '@storybook/react-vite';
import { Download, Eye, ImagePlus, RotateCcw, Trash2 } from 'lucide-react';
import { Button, ChoiceChips, Stack, TextField } from '../components';
import { exportThumbnailPng } from './exportThumbnailPng';
import {
  IMAGE_PRESET_OPTIONS,
  PS2_GTA_SHOWCASE_PRESETS,
  VARIANT_PRESETS,
  type ThumbnailTemplateProps,
  type ThumbnailVariant,
} from './presets';
import { ThumbnailTemplate } from './ThumbnailTemplate';

const VARIANT_LABELS: Record<string, ThumbnailVariant> = {
  '스타일 1 · 반전 2줄 박스': 'invert-box',
  '스타일 2 · 화이트 라벨': 'white-label',
  '스타일 3 · 대형 명조 외곽선': 'serif-outline',
  '스타일 4 · 상단 블랙 POV': 'pov-bar',
};

const LABEL_BY_VARIANT: Record<ThumbnailVariant, string> = {
  'invert-box': '스타일 1 · 반전 2줄 박스',
  'white-label': '스타일 2 · 화이트 라벨',
  'serif-outline': '스타일 3 · 대형 명조 외곽선',
  'pov-bar': '스타일 4 · 상단 블랙 POV',
};

/**
 * Figma 릴스 커버 4가지 제목 스타일 템플릿과 1080×1920 PNG 저장 스튜디오.
 * 하단 검은 그라데이션 스크림 토글과 배경 이미지 교체·드래그 팬·줌 편집을 지원한다.
 */
const meta: Meta<ThumbnailTemplateProps> = {
  title: 'NAPDA/썸네일 템플릿',
  component: ThumbnailTemplate,
  parameters: { layout: 'fullscreen' },
  argTypes: {
    variant: {
      control: 'select',
      options: ['invert-box', 'white-label', 'serif-outline', 'pov-bar'],
    },
    imageUrl: { control: 'text' },
    showBottomGradient: { control: 'boolean' },
    imageScale: { control: { type: 'range', min: 0.5, max: 2.5, step: 0.05 } },
    imageOffsetX: { control: { type: 'range', min: -540, max: 540, step: 10 } },
    imageOffsetY: { control: { type: 'range', min: -960, max: 960, step: 10 } },
    scale: { control: { type: 'range', min: 0.2, max: 0.6, step: 0.02 } },
    showSafeZone: { control: 'boolean' },
    showWordmark: { control: 'boolean' },
  },
  args: {
    ...VARIANT_PRESETS['invert-box'],
    showBottomGradient: false,
    imageScale: 1,
    imageOffsetX: 0,
    imageOffsetY: 0,
    showSafeZone: false,
    scale: 0.34,
  },
};

export default meta;
type Story = StoryObj<ThumbnailTemplateProps>;

const studioPanelStyle: CSSProperties = {
  width: 400,
  padding: 24,
  borderRadius: 16,
  border: '1px solid var(--border-weak)',
  backgroundColor: 'var(--bg)',
  flexShrink: 0,
};

export const Studio: Story = {
  name: '썸네일 스튜디오 · 편집 & PNG 저장',
  parameters: { controls: { disable: true } },
  render: function StudioRender() {
    const initialPreset = VARIANT_PRESETS['invert-box'];
    const [variant, setVariant] = useState<ThumbnailVariant>('invert-box');
    const [badge, setBadge] = useState(initialPreset.badge ?? '');
    const [headline, setHeadline] = useState(initialPreset.headline ?? '');
    const [highlightWord, setHighlightWord] = useState(initialPreset.highlightWord ?? '');
    const [subtitle, setSubtitle] = useState(initialPreset.subtitle ?? '');
    const [showWordmark, setShowWordmark] = useState(Boolean(initialPreset.showWordmark));
    const [showBottomGradient, setShowBottomGradient] = useState(false);
    const [imageUrl, setImageUrl] = useState<string | undefined>(initialPreset.imageUrl);
    const [imageScale, setImageScale] = useState(1);
    const [imageOffsetX, setImageOffsetX] = useState(0);
    const [imageOffsetY, setImageOffsetY] = useState(0);
    const [isFileDragOver, setIsFileDragOver] = useState(false);
    const [showSafeZone, setShowSafeZone] = useState(true);
    const [scale, setScale] = useState(0.36);

    const dragOriginRef = useRef<{
      pointerX: number;
      pointerY: number;
      startX: number;
      startY: number;
    } | null>(null);

    const resetImageTransform = () => {
      setImageScale(1);
      setImageOffsetX(0);
      setImageOffsetY(0);
    };

    const handleVariantChange = (label: string | null) => {
      if (!label) return;
      const next = VARIANT_LABELS[label];
      const preset = VARIANT_PRESETS[next];
      setVariant(next);
      setBadge(preset.badge ?? '');
      setHeadline(preset.headline ?? '');
      setHighlightWord(preset.highlightWord ?? '');
      setSubtitle(preset.subtitle ?? '');
      setShowWordmark(Boolean(preset.showWordmark));
      setImageUrl(preset.imageUrl);
      resetImageTransform();
    };

    const handleClearAllText = () => {
      setBadge('');
      setHeadline('');
      setHighlightWord('');
      setSubtitle('');
      setShowWordmark(false);
    };

    const handleFilePick = (file: File | undefined) => {
      if (!file || !file.type.startsWith('image/')) return;
      setImageUrl(URL.createObjectURL(file));
      resetImageTransform();
    };

    const handlePreviewPointerDown = (e: PointerEvent<HTMLDivElement>) => {
      if (!imageUrl || e.button !== 0) return;
      e.currentTarget.setPointerCapture(e.pointerId);
      dragOriginRef.current = {
        pointerX: e.clientX,
        pointerY: e.clientY,
        startX: imageOffsetX,
        startY: imageOffsetY,
      };
    };

    const handlePreviewPointerMove = (e: PointerEvent<HTMLDivElement>) => {
      const origin = dragOriginRef.current;
      if (!origin) return;
      const dx = Math.round((e.clientX - origin.pointerX) / scale);
      const dy = Math.round((e.clientY - origin.pointerY) / scale);
      setImageOffsetX(Math.max(-540, Math.min(540, origin.startX + dx)));
      setImageOffsetY(Math.max(-960, Math.min(960, origin.startY + dy)));
    };

    const handlePreviewPointerEnd = (e: PointerEvent<HTMLDivElement>) => {
      if (!dragOriginRef.current) return;
      dragOriginRef.current = null;
      if (e.currentTarget.hasPointerCapture(e.pointerId)) {
        e.currentTarget.releasePointerCapture(e.pointerId);
      }
    };

    const handlePreviewDragOver = (e: DragEvent<HTMLDivElement>) => {
      if (e.dataTransfer.types.includes('Files')) {
        e.preventDefault();
        setIsFileDragOver(true);
      }
    };

    const handlePreviewDragLeave = () => {
      setIsFileDragOver(false);
    };

    const handlePreviewDrop = (e: DragEvent<HTMLDivElement>) => {
      e.preventDefault();
      setIsFileDragOver(false);
      handleFilePick(e.dataTransfer.files?.[0]);
    };

    return (
      <div
        style={{
          minHeight: '100vh',
          padding: 32,
          backgroundColor: 'var(--bg-weak)',
          display: 'flex',
          flexWrap: 'wrap',
          gap: 32,
          alignItems: 'flex-start',
          justifyContent: 'center',
        }}
      >
        <div style={studioPanelStyle}>
          <Stack gap={16}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 12 }}>
              <div>
                <h2 style={{ margin: 0, fontSize: 20, fontWeight: 800, color: 'var(--text)' }}>
                  NAPDA 썸네일 스튜디오
                </h2>
                <p style={{ margin: '6px 0 0', fontSize: 13, color: 'var(--text-3)' }}>
                  Figma 4종 제목 · 그라데이션 토글 · 이미지 위치/배율 편집
                </p>
              </div>
              <button
                type="button"
                onClick={handleClearAllText}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 4,
                  padding: '6px 10px',
                  borderRadius: 8,
                  border: '1px solid var(--border)',
                  backgroundColor: 'var(--bg-weak)',
                  color: 'var(--text-2)',
                  fontSize: 12,
                  fontWeight: 600,
                  cursor: 'pointer',
                  flexShrink: 0,
                }}
              >
                <Trash2 size={13} aria-hidden="true" />
                글자 모두 지우기
              </button>
            </div>

            <ChoiceChips
              label="제목 스타일 유형"
              options={Object.keys(VARIANT_LABELS)}
              value={LABEL_BY_VARIANT[variant]}
              onChange={handleVariantChange}
            />

            <TextField
              label={variant === 'serif-outline' ? '상단 이탤릭 소제목 (비우면 숨김)' : '상단 배지 (비우면 숨김)'}
              value={badge}
              onChange={setBadge}
              hasClear
            />

            <div className="n-field">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <label className="n-label" htmlFor="thumb-headline">
                  메인 제목 (줄바꿈으로 2~3줄)
                </label>
                {headline && (
                  <button
                    type="button"
                    onClick={() => setHeadline('')}
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: 4,
                      border: 'none',
                      background: 'transparent',
                      color: 'var(--text-weak)',
                      fontSize: 12,
                      cursor: 'pointer',
                    }}
                  >
                    <Trash2 size={12} aria-hidden="true" />
                    지우기
                  </button>
                )}
              </div>
              <textarea
                id="thumb-headline"
                className="n-input"
                rows={3}
                value={headline}
                onChange={(e) => setHeadline(e.target.value)}
                style={{ height: 'auto', padding: '10px 12px', resize: 'vertical', lineHeight: 1.45 }}
              />
            </div>

            <TextField
              label="라임 강조 단어 (선택)"
              value={highlightWord}
              onChange={setHighlightWord}
              placeholder="예: 얼죽아"
              hasClear
            />

            <TextField
              label="하단 캡션 (비우면 숨김)"
              value={subtitle}
              onChange={setSubtitle}
              hasClear
            />

            {/* 이미지 선택 및 위치/배율 편집 */}
            <div
              style={{
                display: 'flex',
                flexDirection: 'column',
                gap: 10,
                padding: 12,
                borderRadius: 12,
                border: '1px solid var(--border-weak)',
                backgroundColor: 'var(--bg-weak)',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <label className="n-label" style={{ margin: 0 }}>
                  배경 / 스틸컷 이미지 편집
                </label>
                <div style={{ display: 'flex', gap: 8 }}>
                  {(imageScale !== 1 || imageOffsetX !== 0 || imageOffsetY !== 0) && (
                    <button
                      type="button"
                      onClick={resetImageTransform}
                      style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: 4,
                        border: 'none',
                        background: 'transparent',
                        color: 'var(--text-2)',
                        fontSize: 12,
                        fontWeight: 600,
                        cursor: 'pointer',
                      }}
                    >
                      <RotateCcw size={12} aria-hidden="true" />
                      위치 초기화
                    </button>
                  )}
                  {imageUrl && (
                    <button
                      type="button"
                      onClick={() => setImageUrl(undefined)}
                      style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: 4,
                        border: 'none',
                        background: 'transparent',
                        color: 'var(--text-weak)',
                        fontSize: 12,
                        cursor: 'pointer',
                      }}
                    >
                      <Trash2 size={12} aria-hidden="true" />
                      비우기
                    </button>
                  )}
                </div>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gap: 6 }}>
                {IMAGE_PRESET_OPTIONS.map((opt) => {
                  const selected = imageUrl === opt.url;
                  return (
                    <button
                      key={opt.id}
                      type="button"
                      onClick={() => {
                        setImageUrl(opt.url);
                        resetImageTransform();
                      }}
                      style={{
                        padding: 4,
                        borderRadius: 8,
                        border: selected ? '2px solid #d6ff3f' : '1px solid var(--border)',
                        backgroundColor: selected ? '#111317' : 'var(--bg)',
                        color: selected ? '#d6ff3f' : 'var(--text-2)',
                        fontSize: 11,
                        fontWeight: 700,
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        gap: 6,
                      }}
                    >
                      <img
                        src={opt.url}
                        alt={opt.label}
                        style={{ width: 22, height: 32, objectFit: 'cover', borderRadius: 4, flexShrink: 0 }}
                      />
                      <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {opt.label}
                      </span>
                    </button>
                  );
                })}
              </div>

              <label
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: 8,
                  padding: '9px 12px',
                  borderRadius: 10,
                  border: '1.5px dashed var(--border)',
                  backgroundColor: 'var(--bg)',
                  cursor: 'pointer',
                  fontSize: 13,
                  fontWeight: 600,
                  color: 'var(--text-2)',
                }}
              >
                <ImagePlus size={16} aria-hidden="true" />
                파일 고르기 (또는 오른쪽 미리보기에 드래그&드롭)
                <input
                  type="file"
                  accept="image/*"
                  hidden
                  onChange={(e) => handleFilePick(e.target.files?.[0])}
                />
              </label>

              <TextField
                label="이미지 URL 직접 입력"
                value={imageUrl ?? ''}
                onChange={(val) => setImageUrl(val.trim() ? val : undefined)}
                placeholder="https://... 또는 data:image/..."
                hasClear
              />

              <div style={{ display: 'flex', flexDirection: 'column', gap: 6, fontSize: 12, color: 'var(--text-2)' }}>
                <label style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
                  <span>이미지 확대 ({Math.round(imageScale * 100)}%)</span>
                  <input
                    type="range"
                    min={0.5}
                    max={2.5}
                    step={0.05}
                    value={imageScale}
                    onChange={(e) => setImageScale(Number(e.target.value))}
                    style={{ width: 170 }}
                  />
                </label>
                <label style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
                  <span>가로 위치 ({imageOffsetX}px)</span>
                  <input
                    type="range"
                    min={-540}
                    max={540}
                    step={10}
                    value={imageOffsetX}
                    onChange={(e) => setImageOffsetX(Number(e.target.value))}
                    style={{ width: 170 }}
                  />
                </label>
                <label style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
                  <span>세로 위치 ({imageOffsetY}px)</span>
                  <input
                    type="range"
                    min={-960}
                    max={960}
                    step={10}
                    value={imageOffsetY}
                    onChange={(e) => setImageOffsetY(Number(e.target.value))}
                    style={{ width: 170 }}
                  />
                </label>
              </div>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                <label style={{ display: 'inline-flex', alignItems: 'center', gap: 8, fontSize: 13, fontWeight: 600 }}>
                  <input
                    type="checkbox"
                    checked={showBottomGradient}
                    onChange={(e) => setShowBottomGradient(e.target.checked)}
                  />
                  하단 검은 그라데이션
                </label>
                <label style={{ display: 'inline-flex', alignItems: 'center', gap: 8, fontSize: 13, fontWeight: 600 }}>
                  <input
                    type="checkbox"
                    checked={showSafeZone}
                    onChange={(e) => setShowSafeZone(e.target.checked)}
                  />
                  <Eye size={15} aria-hidden="true" />
                  금지 영역 표시 (빨간색)
                </label>
                <label style={{ display: 'inline-flex', alignItems: 'center', gap: 8, fontSize: 13, fontWeight: 600 }}>
                  <input
                    type="checkbox"
                    checked={showWordmark}
                    onChange={(e) => setShowWordmark(e.target.checked)}
                  />
                  NAPDA 로고 표시
                </label>
              </div>
              <label style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 12, color: 'var(--text-3)' }}>
                미리보기
                <input
                  type="range"
                  min={0.24}
                  max={0.48}
                  step={0.02}
                  value={scale}
                  onChange={(e) => setScale(Number(e.target.value))}
                  style={{ width: 84 }}
                />
              </label>
            </div>

            <Button
              label="1080×1920 PNG 내려받기"
              isBlock
              icon={<Download size={20} aria-hidden="true" />}
              onClick={() => {
                void exportThumbnailPng({
                  variant,
                  badge,
                  headline,
                  highlightWord,
                  subtitle,
                  showWordmark,
                  showBottomGradient,
                  imageUrl,
                  imageScale,
                  imageOffsetX,
                  imageOffsetY,
                });
              }}
            />
          </Stack>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12 }}>
          <div
            onPointerDown={handlePreviewPointerDown}
            onPointerMove={handlePreviewPointerMove}
            onPointerUp={handlePreviewPointerEnd}
            onPointerCancel={handlePreviewPointerEnd}
            onDragOver={handlePreviewDragOver}
            onDragLeave={handlePreviewDragLeave}
            onDrop={handlePreviewDrop}
            title="드래그해서 이미지 위치 이동 · 이미지 파일 드롭으로 교체"
            style={{
              position: 'relative',
              borderRadius: 18,
              outline: isFileDragOver ? '3px dashed #d6ff3f' : 'none',
              outlineOffset: 4,
              cursor: imageUrl ? 'grab' : 'default',
              touchAction: 'none',
            }}
          >
            <ThumbnailTemplate
              variant={variant}
              badge={badge}
              headline={headline}
              highlightWord={highlightWord}
              subtitle={subtitle}
              showWordmark={showWordmark}
              showBottomGradient={showBottomGradient}
              imageUrl={imageUrl}
              imageScale={imageScale}
              imageOffsetX={imageOffsetX}
              imageOffsetY={imageOffsetY}
              showSafeZone={showSafeZone}
              scale={scale}
            />
          </div>
          <span style={{ fontSize: 12, color: 'var(--text-weak)' }}>
            논리 해상도 1080 × 1920 px · 미리보기 드래그로 이미지 위치 이동 · 파일 드롭 교체 가능
          </span>
        </div>
      </div>
    );
  },
};

export const Ps2GtaMemeShowcase: Story = {
  name: '실전 예시 · 4종 타이틀 적용',
  parameters: { controls: { disable: true } },
  render: () => (
    <div
      style={{
        minHeight: '100vh',
        padding: 32,
        backgroundColor: '#111215',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: 24,
      }}
    >
      <div style={{ textAlign: 'center' }}>
        <h2 style={{ margin: 0, color: '#ffffff', fontSize: 22, fontWeight: 800 }}>
          Figma 4가지 릴스커버 제목 스타일 · 실전 적용 예시
        </h2>
        <p style={{ margin: '8px 0 0', color: '#a6a6a6', fontSize: 14 }}>
          검은 그라데이션 스크림 없이 원본 이미지 위에 4가지 제목 스타일을 그대로 얹어 1080×1920 PNG로 저장합니다
        </p>
      </div>
      <div
        style={{
          display: 'flex',
          flexWrap: 'wrap',
          gap: 28,
          justifyContent: 'center',
          alignItems: 'flex-start',
        }}
      >
        {PS2_GTA_SHOWCASE_PRESETS.map((item) => (
          <div
            key={item.id}
            style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12 }}
          >
            <span style={{ color: '#d6ff3f', fontSize: 13, fontWeight: 700 }}>{item.label}</span>
            <ThumbnailTemplate {...item.props} scale={0.31} />
            <Button
              label="PNG 저장"
              variant="secondary"
              size="sm"
              icon={<Download size={16} aria-hidden="true" />}
              onClick={() => void exportThumbnailPng(item.props)}
            />
          </div>
        ))}
      </div>
    </div>
  ),
};

export const Gallery: Story = {
  name: '전체 4종 모아보기',
  parameters: { controls: { disable: true } },
  render: () => (
    <div
      style={{
        minHeight: '100vh',
        padding: 32,
        backgroundColor: '#111215',
        display: 'flex',
        flexWrap: 'wrap',
        gap: 24,
        alignItems: 'flex-start',
        justifyContent: 'center',
      }}
    >
      {(['invert-box', 'white-label', 'serif-outline', 'pov-bar'] as const).map((key) => (
        <div key={key} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 10 }}>
          <span style={{ color: '#e5e5e5', fontSize: 13, fontWeight: 700 }}>{LABEL_BY_VARIANT[key]}</span>
          <ThumbnailTemplate {...VARIANT_PRESETS[key]} scale={0.28} />
        </div>
      ))}
    </div>
  ),
};

export const InvertBox: Story = {
  name: '01 · 스타일 1 반전 2줄 박스 (PS2 얼죽아)',
  parameters: { layout: 'centered' },
  args: { ...VARIANT_PRESETS['invert-box'], scale: 0.34 },
};

export const WhiteLabel: Story = {
  name: '02 · 스타일 2 화이트 라벨 (제트엔진)',
  parameters: { layout: 'centered' },
  args: { ...VARIANT_PRESETS['white-label'], scale: 0.34 },
};

export const SerifOutline: Story = {
  name: '03 · 스타일 3 대형 명조 외곽선 (피에브)',
  parameters: { layout: 'centered' },
  args: { ...VARIANT_PRESETS['serif-outline'], scale: 0.34 },
};

export const PovBar: Story = {
  name: '04 · 스타일 4 상단 블랙 POV (PS2 2호선)',
  parameters: { layout: 'centered' },
  args: { ...VARIANT_PRESETS['pov-bar'], scale: 0.34 },
};
