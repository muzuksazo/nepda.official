import { useState, type CSSProperties } from 'react';
import type { Meta, StoryObj } from '@storybook/react-vite';
import { Download, Eye, ImagePlus, Trash2 } from 'lucide-react';
import { Button, ChoiceChips, Stack, TextField } from '../components';
import { exportThumbnailPng } from './exportThumbnailPng';
import {
  PS2_GTA_SHOWCASE_PRESETS,
  VARIANT_PRESETS,
  type ThumbnailTemplateProps,
  type ThumbnailVariant,
} from './presets';
import { ThumbnailTemplate } from './ThumbnailTemplate';

const VARIANT_LABELS: Record<string, ThumbnailVariant> = {
  '01 기본 에디토리얼': 'editorial',
  '02 바이럴 훅': 'viral-hook',
  '03 스플릿 VS': 'split-vs',
  '04 제품 커머스': 'commerce',
};

const LABEL_BY_VARIANT: Record<ThumbnailVariant, string> = {
  editorial: '01 기본 에디토리얼',
  'viral-hook': '02 바이럴 훅',
  'split-vs': '03 스플릿 VS',
  commerce: '04 제품 커머스',
};

/**
 * 1080×1920 릴스·쇼츠 썸네일 템플릿 4종과 라이브 편집·PNG 저장 스튜디오.
 * 실제 K-밈 2004 PS2/GTA · 제트엔진 · 피에브 스틸컷이 기본 적용되어 있다.
 */
const meta: Meta<ThumbnailTemplateProps> = {
  title: 'NAPDA/썸네일 템플릿',
  component: ThumbnailTemplate,
  parameters: { layout: 'fullscreen' },
  argTypes: {
    variant: {
      control: 'select',
      options: ['editorial', 'viral-hook', 'split-vs', 'commerce'],
    },
    scale: { control: { type: 'range', min: 0.2, max: 0.6, step: 0.02 } },
    showSafeZone: { control: 'boolean' },
    showWordmark: { control: 'boolean' },
  },
  args: {
    ...VARIANT_PRESETS.editorial,
    showSafeZone: false,
    scale: 0.34,
  },
};

export default meta;
type Story = StoryObj<ThumbnailTemplateProps>;

const studioPanelStyle: CSSProperties = {
  width: 380,
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
    const initialPreset = VARIANT_PRESETS['viral-hook'];
    const [variant, setVariant] = useState<ThumbnailVariant>('viral-hook');
    const [badge, setBadge] = useState(initialPreset.badge ?? '');
    const [realityBadge, setRealityBadge] = useState(
      VARIANT_PRESETS['split-vs'].realityBadge ?? '현실 · REALITY',
    );
    const [headline, setHeadline] = useState(initialPreset.headline ?? '');
    const [highlightWord, setHighlightWord] = useState(initialPreset.highlightWord ?? '');
    const [subtitle, setSubtitle] = useState(initialPreset.subtitle ?? '');
    const [showWordmark, setShowWordmark] = useState(Boolean(initialPreset.showWordmark));
    const [imageUrl, setImageUrl] = useState<string | undefined>(initialPreset.imageUrl);
    const [bottomImageUrl, setBottomImageUrl] = useState<string | undefined>(
      initialPreset.bottomImageUrl,
    );
    const [showSafeZone, setShowSafeZone] = useState(true);
    const [scale, setScale] = useState(0.36);

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
      setBottomImageUrl(preset.bottomImageUrl);
      if (preset.realityBadge) setRealityBadge(preset.realityBadge);
    };

    const handleClearAllText = () => {
      setBadge('');
      setRealityBadge('');
      setHeadline('');
      setHighlightWord('');
      setSubtitle('');
      setShowWordmark(false);
    };

    const handleFilePick = (file: File | undefined, isBottom = false) => {
      if (!file) return;
      const url = URL.createObjectURL(file);
      if (isBottom) setBottomImageUrl(url);
      else setImageUrl(url);
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
                  원치 않는 글·배지·로고는 비우면 바로 사라집니다.
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
              label="템플릿 유형"
              options={Object.keys(VARIANT_LABELS)}
              value={LABEL_BY_VARIANT[variant]}
              onChange={handleVariantChange}
            />

            <TextField label="상단 배지 (비우면 숨김)" value={badge} onChange={setBadge} hasClear />

            {variant === 'split-vs' && (
              <TextField
                label="하단 배지 (현실 · 비우면 숨김)"
                value={realityBadge}
                onChange={setRealityBadge}
                hasClear
              />
            )}

            <div className="n-field">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <label className="n-label" htmlFor="thumb-headline">
                  메인 헤드라인 (비우면 숨김)
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
              label="라임 강조 단어 (1단어)"
              value={highlightWord}
              onChange={setHighlightWord}
              placeholder="예: 제트엔진"
              hasClear
            />

            <TextField
              label="하단 서브 카피 / 제품명 (비우면 숨김)"
              value={subtitle}
              onChange={setSubtitle}
              hasClear
            />

            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <label className="n-label">배경 / 제품 이미지 교체</label>
                {(imageUrl || bottomImageUrl) && (
                  <button
                    type="button"
                    onClick={() => {
                      setImageUrl(undefined);
                      setBottomImageUrl(undefined);
                    }}
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
                    <Trash2 size={13} aria-hidden="true" />
                    비우기
                  </button>
                )}
              </div>

              <label
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: 8,
                  padding: '10px 14px',
                  borderRadius: 10,
                  border: '1.5px dashed var(--border)',
                  cursor: 'pointer',
                  fontSize: 14,
                  fontWeight: 600,
                  color: 'var(--text-2)',
                }}
              >
                <ImagePlus size={18} aria-hidden="true" />
                {variant === 'split-vs' ? '상단 이미지 교체하기' : '이미지 파일 고르기'}
                <input
                  type="file"
                  accept="image/*"
                  hidden
                  onChange={(e) => handleFilePick(e.target.files?.[0], false)}
                />
              </label>

              {variant === 'split-vs' && (
                <label
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: 8,
                    padding: '10px 14px',
                    borderRadius: 10,
                    border: '1.5px dashed var(--border)',
                    cursor: 'pointer',
                    fontSize: 14,
                    fontWeight: 600,
                    color: 'var(--text-2)',
                  }}
                >
                  <ImagePlus size={18} aria-hidden="true" />
                  하단 이미지 교체하기
                  <input
                    type="file"
                    accept="image/*"
                    hidden
                    onChange={(e) => handleFilePick(e.target.files?.[0], true)}
                  />
                </label>
              )}
            </div>

            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                <label style={{ display: 'inline-flex', alignItems: 'center', gap: 8, fontSize: 13, fontWeight: 600 }}>
                  <input
                    type="checkbox"
                    checked={showSafeZone}
                    onChange={(e) => setShowSafeZone(e.target.checked)}
                  />
                  <Eye size={15} aria-hidden="true" />
                  릴스 안전 영역 보기
                </label>
                {variant !== 'split-vs' && (
                  <label style={{ display: 'inline-flex', alignItems: 'center', gap: 8, fontSize: 13, fontWeight: 600 }}>
                    <input
                      type="checkbox"
                      checked={showWordmark}
                      onChange={(e) => setShowWordmark(e.target.checked)}
                    />
                    NAPDA 로고 표시
                  </label>
                )}
              </div>
              <label style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 12, color: 'var(--text-3)' }}>
                배율
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
                  realityBadge,
                  headline,
                  highlightWord,
                  subtitle,
                  showWordmark,
                  imageUrl,
                  bottomImageUrl,
                });
              }}
            />
          </Stack>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12 }}>
          <ThumbnailTemplate
            variant={variant}
            badge={badge}
            realityBadge={realityBadge}
            headline={headline}
            highlightWord={highlightWord}
            subtitle={subtitle}
            showWordmark={showWordmark}
            imageUrl={imageUrl}
            bottomImageUrl={bottomImageUrl}
            showSafeZone={showSafeZone}
            scale={scale}
          />
          <span style={{ fontSize: 12, color: 'var(--text-weak)' }}>
            논리 해상도 1080 × 1920 px (9:16 Reels/Shorts) · 미리보기 {Math.round(scale * 100)}%
          </span>
        </div>
      </div>
    );
  },
};

export const Ps2GtaMemeShowcase: Story = {
  name: '실전 예시 · K-밈 2004 PS2/GTA 3종',
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
          K-밈 2004 PS2/GTA 실제 스틸컷 적용 예시
        </h2>
        <p style={{ margin: '8px 0 0', color: '#a6a6a6', fontSize: 14 }}>
          EP.2 영하 15도 얼죽아 & EP.1 서울 2호선 출근길 실제 레퍼런스 컷 적용 · 바로 1080×1920 PNG 저장 가능
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
      {(['editorial', 'viral-hook', 'split-vs', 'commerce'] as const).map((key) => (
        <div key={key} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 10 }}>
          <span style={{ color: '#e5e5e5', fontSize: 13, fontWeight: 700 }}>{LABEL_BY_VARIANT[key]}</span>
          <ThumbnailTemplate {...VARIANT_PRESETS[key]} scale={0.28} />
        </div>
      ))}
    </div>
  ),
};

export const Editorial: Story = {
  name: '01 · 기본 에디토리얼 (PS2 얼죽아)',
  parameters: { layout: 'centered' },
  args: { ...VARIANT_PRESETS.editorial, scale: 0.34 },
};

export const ViralHook: Story = {
  name: '02 · 바이럴 훅 (제트엔진)',
  parameters: { layout: 'centered' },
  args: { ...VARIANT_PRESETS['viral-hook'], scale: 0.34 },
};

export const SplitVs: Story = {
  name: '03 · 스플릿 VS (PS2 2호선)',
  parameters: { layout: 'centered' },
  args: { ...VARIANT_PRESETS['split-vs'], scale: 0.34 },
};

export const Commerce: Story = {
  name: '04 · 제품 커머스 (피에브)',
  parameters: { layout: 'centered' },
  args: { ...VARIANT_PRESETS.commerce, scale: 0.34 },
};
