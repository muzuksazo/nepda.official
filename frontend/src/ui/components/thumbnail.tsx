import { useId, useLayoutEffect, useRef } from 'react';
import { Check, ImageIcon } from '../icons';
import type { ThumbnailTemplate } from './thumbnailTemplates';

export interface ThumbnailPickerProps {
  label: string;
  /** 팀이 만든 템플릿들 (보여 줄 순서대로) */
  templates: readonly ThumbnailTemplate[];
  /** 고른 템플릿 id */
  value: string | null;
  onChange: (id: string) => void;
}

/**
 * 썸네일 시안 고르기 — 가로로 넘기는 캐러셀에서 하나만 고른다 (라디오 그룹).
 * 다음 시안이 오른쪽에 살짝 보여 넘길 수 있다는 걸 알려 준다. 고른 시안은 사진에 붙은 라임 테두리 + 체크.
 */
export function ThumbnailPicker({ label, templates, value, onChange }: ThumbnailPickerProps) {
  const name = useId();
  const trackRef = useRef<HTMLDivElement>(null);

  // 처음에 골라 둔 시안이 뒤쪽에 있으면 그 시안이 보이게 가로로만 옮겨 둔다 (화면 세로 위치는 건드리지 않는다)
  useLayoutEffect(() => {
    const track = trackRef.current;
    const option = track?.querySelector('input:checked')?.closest<HTMLElement>('.n-thumb-option');
    if (!track || !option) return;
    const start = parseFloat(getComputedStyle(track).paddingLeft) || 0;
    track.style.scrollBehavior = 'auto';
    track.scrollLeft = option.offsetLeft - start;
    track.style.scrollBehavior = '';
  }, []);

  return (
    <fieldset className="n-field n-thumb-picker" style={{ border: 0, padding: 0, margin: 0 }}>
      <legend className="n-field__label" style={{ marginBottom: 4, padding: 0 }}>
        {label}
      </legend>
      <div ref={trackRef} className="n-thumb-picker__track">
        {templates.map((template) => {
          const descId = template.description ? `${name}-${template.id}-desc` : undefined;
          return (
            <label key={template.id} className="n-thumb-option">
              <input
                type="radio"
                name={name}
                value={template.id}
                checked={value === template.id}
                aria-label={template.name}
                aria-describedby={descId}
                onChange={(e) => {
                  onChange(template.id);
                  // 반쯤 걸친 시안을 고르면 다 보이게 끌어온다
                  e.currentTarget.closest('.n-thumb-option')?.scrollIntoView({ block: 'nearest', inline: 'nearest' });
                }}
              />
              <span className={`n-thumb-option__frame${template.previewUrl ? '' : ' is-empty'}`}>
                {template.previewUrl ? (
                  <img src={template.previewUrl} alt="" loading="lazy" decoding="async" />
                ) : (
                  <ImageIcon size={28} aria-hidden="true" />
                )}
                <span className="n-thumb-option__check" aria-hidden="true">
                  <Check size={18} strokeWidth={3} />
                </span>
              </span>
              <span className="n-thumb-option__name">{template.name}</span>
              {descId ? (
                <span id={descId} className="napda-visually-hidden">
                  {template.description}
                </span>
              ) : null}
            </label>
          );
        })}
      </div>
    </fieldset>
  );
}
