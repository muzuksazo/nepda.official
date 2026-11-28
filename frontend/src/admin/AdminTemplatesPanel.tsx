import { useCallback, useEffect, useMemo, useState, type FormEvent } from 'react';
import { customFetch, getApiBaseUrl, NapdaApiError } from '../api/mutator';

export interface TrackATemplateItem {
  id: string;
  filename: string;
  title: string;
  duration_sec: number;
  width: number;
  height: number;
  size_bytes: number;
  a_genre_archetype: string;
  tags: string[];
  visual_summary: string;
  default_hook_captions: string[];
  enabled: boolean;
  video_url: string;
}

interface ListTemplatesResponse {
  templates: TrackATemplateItem[];
}

type StatusFilter = 'all' | 'enabled' | 'disabled';

const GENRE_OPTIONS: readonly { value: string; label: string }[] = [
  { value: 'mock_documentary', label: 'mock_documentary (다큐/실험형)' },
  { value: 'absurd_physics', label: 'absurd_physics (황당 물리형)' },
  { value: 'meme_parody', label: 'meme_parody (밈·패러디형)' },
  { value: 'drama_parody', label: 'drama_parody (드라마·상황극형)' },
];

const MAX_UPLOAD_BYTES = 50 * 1024 * 1024;

function formatMb(bytes: number): string {
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

function parseErrorMessage(err: unknown, fallback: string): string {
  if (err instanceof NapdaApiError) return err.message || fallback;
  if (err instanceof Error && err.message) return err.message;
  return fallback;
}

function TemplateVideoPreview({
  videoUrl,
  cacheKey,
  bearerToken,
  title,
}: {
  videoUrl: string;
  cacheKey: string;
  bearerToken: string;
  title: string;
}) {
  const apiBase = getApiBaseUrl();
  const fullUrl = `${apiBase}${videoUrl}?v=${encodeURIComponent(cacheKey)}`;
  const trimmedToken = bearerToken.trim();
  const [blobSrc, setBlobSrc] = useState<string | null>(null);
  const [blobFailed, setBlobFailed] = useState(false);

  useEffect(() => {
    if (!trimmedToken) return;
    let active = true;
    let createdUrl: string | null = null;

    const loadBlob = async () => {
      try {
        const response = await fetch(fullUrl, {
          headers: { Authorization: `Bearer ${trimmedToken}` },
          credentials: 'include',
        });
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }
        const blob = await response.blob();
        if (!active) return;
        createdUrl = URL.createObjectURL(blob);
        setBlobSrc(createdUrl);
        setBlobFailed(false);
      } catch {
        if (active) {
          setBlobSrc(null);
          setBlobFailed(true);
        }
      }
    };

    void loadBlob();
    return () => {
      active = false;
      if (createdUrl) {
        URL.revokeObjectURL(createdUrl);
      }
    };
  }, [fullUrl, trimmedToken]);

  const effectiveSrc = trimmedToken ? blobSrc : fullUrl;

  return (
    <div className="napda-tpl-video-box">
      {effectiveSrc ? (
        <video
          key={effectiveSrc}
          src={effectiveSrc}
          controls
          playsInline
          preload="metadata"
          aria-label={`${title} 미리보기`}
          className="napda-tpl-video"
        />
      ) : (
        <div className="napda-tpl-video-fallback">
          {blobFailed ? '영상을 불러오지 못했어요' : '영상 불러오는 중…'}
        </div>
      )}
    </div>
  );
}

interface TemplateFormModalProps {
  mode: 'create' | 'edit';
  initial: TrackATemplateItem | null;
  bearerToken: string;
  onClose: () => void;
  onSaved: () => void;
}

function TemplateFormModal({
  mode,
  initial,
  bearerToken,
  onClose,
  onSaved,
}: TemplateFormModalProps) {
  const [slug, setSlug] = useState(initial?.id ?? '');
  const [title, setTitle] = useState(initial?.title ?? '');
  const [genre, setGenre] = useState(initial?.a_genre_archetype ?? 'mock_documentary');
  const [tagsText, setTagsText] = useState((initial?.tags ?? []).join(', '));
  const [visualSummary, setVisualSummary] = useState(initial?.visual_summary ?? '');
  const [captionsText, setCaptionsText] = useState(
    (initial?.default_hook_captions ?? []).join('\n'),
  );
  const [enabled, setEnabled] = useState<boolean>(initial?.enabled ?? true);
  const [file, setFile] = useState<File | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && !submitting) {
        onClose();
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [onClose, submitting]);

  const genreChoices = useMemo(() => {
    const hasCurrent = GENRE_OPTIONS.some((opt) => opt.value === genre);
    return hasCurrent
      ? GENRE_OPTIONS
      : [...GENRE_OPTIONS, { value: genre, label: genre }];
  }, [genre]);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setFormError(null);

    const trimmedTitle = title.trim();
    const trimmedVisual = visualSummary.trim();
    if (!trimmedTitle) {
      setFormError('제목을 입력해 주세요.');
      return;
    }
    if (!trimmedVisual) {
      setFormError('장면 설명(Visual Summary)을 입력해 주세요.');
      return;
    }
    if (mode === 'create' && !file) {
      setFormError('업로드할 .mp4 파일을 선택해 주세요.');
      return;
    }
    if (file && file.size > MAX_UPLOAD_BYTES) {
      setFormError('파일 크기가 50MB를 초과합니다. 50MB 이하 .mp4 파일을 올려 주세요.');
      return;
    }

    const parsedTags = tagsText
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean);
    const parsedCaptions = captionsText
      .split('\n')
      .map((s) => s.trim())
      .filter(Boolean);

    const trimmedToken = bearerToken.trim();
    const authHeader: Record<string, string> = trimmedToken
      ? { Authorization: `Bearer ${trimmedToken}` }
      : {};

    setSubmitting(true);
    try {
      if (mode === 'create') {
        const fd = new FormData();
        if (file) fd.append('file', file);
        if (slug.trim()) fd.append('id', slug.trim());
        fd.append('title', trimmedTitle);
        fd.append('a_genre_archetype', genre);
        fd.append('tags', JSON.stringify(parsedTags));
        fd.append('visual_summary', trimmedVisual);
        fd.append('default_hook_captions', JSON.stringify(parsedCaptions));
        fd.append('enabled', enabled ? 'true' : 'false');

        await customFetch<{ data: TrackATemplateItem; status: number }>(
          '/v1/admin/templates/track-a',
          {
            method: 'POST',
            headers: authHeader,
            body: fd,
          },
        );
      } else if (initial) {
        const targetUrl = `/v1/admin/templates/track-a/${encodeURIComponent(initial.id)}`;
        if (file) {
          const fd = new FormData();
          fd.append('file', file);
          fd.append('title', trimmedTitle);
          fd.append('a_genre_archetype', genre);
          fd.append('tags', JSON.stringify(parsedTags));
          fd.append('visual_summary', trimmedVisual);
          fd.append('default_hook_captions', JSON.stringify(parsedCaptions));
          fd.append('enabled', enabled ? 'true' : 'false');

          await customFetch<{ data: TrackATemplateItem; status: number }>(targetUrl, {
            method: 'PATCH',
            headers: authHeader,
            body: fd,
          });
        } else {
          await customFetch<{ data: TrackATemplateItem; status: number }>(targetUrl, {
            method: 'PATCH',
            headers: {
              ...authHeader,
              'Content-Type': 'application/json',
            },
            body: JSON.stringify({
              title: trimmedTitle,
              a_genre_archetype: genre,
              tags: parsedTags,
              visual_summary: trimmedVisual,
              default_hook_captions: parsedCaptions,
              enabled,
            }),
          });
        }
      }
      onSaved();
      onClose();
    } catch (err) {
      setFormError(
        parseErrorMessage(
          err,
          mode === 'create'
            ? '템플릿 업로드에 실패했습니다.'
            : '템플릿 수정에 실패했습니다.',
        ),
      );
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div
      className="napda-admin-modal-backdrop"
      role="presentation"
      onClick={() => {
        if (!submitting) onClose();
      }}
    >
      <div
        className="napda-admin-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="tpl-modal-title"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="napda-admin-modal-head">
          <h2 id="tpl-modal-title" className="napda-admin-card-title">
            {mode === 'create' ? '새 A안 템플릿 업로드' : 'A안 템플릿 수정'}
          </h2>
          <button
            type="button"
            className="napda-admin-btn"
            disabled={submitting}
            onClick={onClose}
          >
            닫기
          </button>
        </div>

        <form className="napda-admin-form" onSubmit={(e) => void handleSubmit(e)}>
          {mode === 'create' ? (
            <label className="napda-admin-field">
              <span className="napda-admin-field-label">템플릿 ID (선택)</span>
              <input
                type="text"
                className="napda-admin-input"
                value={slug}
                onChange={(e) => setSlug(e.target.value)}
                placeholder="비워두면 자동 생성 (예: a_water_drop_3d)"
                pattern="[a-z0-9][a-z0-9_-]{1,63}"
                title="소문자 영문, 숫자, -, _ 만 사용 가능 (2~64자)"
              />
            </label>
          ) : (
            <div className="napda-admin-field">
              <span className="napda-admin-field-label">템플릿 ID</span>
              <code className="napda-admin-mono">{initial?.id}</code>
            </div>
          )}

          <label className="napda-admin-field">
            <span className="napda-admin-field-label">제목 *</span>
            <input
              type="text"
              className="napda-admin-input"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="예: 3D 거대 도미노 다큐멘터리"
              required
            />
          </label>

          <label className="napda-admin-field">
            <span className="napda-admin-field-label">장르 (a_genre_archetype)</span>
            <select
              className="napda-admin-input"
              value={genre}
              onChange={(e) => setGenre(e.target.value)}
            >
              {genreChoices.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </label>

          <label className="napda-admin-field">
            <span className="napda-admin-field-label">태그 (쉼표로 구분)</span>
            <input
              type="text"
              className="napda-admin-input"
              value={tagsText}
              onChange={(e) => setTagsText(e.target.value)}
              placeholder="예: 도미노, 물리, 3D, 충격, 청소"
            />
          </label>

          <label className="napda-admin-field">
            <span className="napda-admin-field-label">장면 설명 (Visual Summary) *</span>
            <textarea
              className="napda-admin-input napda-admin-textarea"
              rows={3}
              value={visualSummary}
              onChange={(e) => setVisualSummary(e.target.value)}
              placeholder="AI 기획자가 참고할 훅 영상의 시각적 장면 흐름을 적어 주세요."
              required
            />
          </label>

          <label className="napda-admin-field">
            <span className="napda-admin-field-label">기본 훅 자막 (한 줄당 1컷)</span>
            <textarea
              className="napda-admin-input napda-admin-textarea"
              rows={3}
              value={captionsText}
              onChange={(e) => setCaptionsText(e.target.value)}
              placeholder={'1cm 도미노를 2배씩 키워 스무 개만 세우면\n마지막 조각은 아파트 50층 높이가 됩니다\n지면에 닿는 순간 반경 1km 지반이 흔들립니다'}
            />
          </label>

          <label className="napda-admin-field">
            <span className="napda-admin-field-label">
              {mode === 'create'
                ? '.mp4 영상 파일 * (세로 9:16 · 2~30초 · 50MB 이하)'
                : '.mp4 영상 교체 (선택 · 비워두면 기존 영상 유지)'}
            </span>
            <input
              type="file"
              accept="video/mp4,.mp4"
              className="napda-admin-input"
              required={mode === 'create'}
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            />
            {file ? (
              <span className="napda-admin-sub">
                선택된 파일: {file.name} ({formatMb(file.size)})
              </span>
            ) : mode === 'edit' && initial ? (
              <span className="napda-admin-sub">
                현재 파일: {initial.filename} ({initial.duration_sec.toFixed(1)}초 ·{' '}
                {initial.width}×{initial.height} · {formatMb(initial.size_bytes)})
              </span>
            ) : null}
          </label>

          <label className="napda-admin-checkbox">
            <input
              type="checkbox"
              checked={enabled}
              onChange={(e) => setEnabled(e.target.checked)}
            />
            <span>활성화 (새 시나리오 추천 대상에 포함)</span>
          </label>

          {formError ? (
            <div className="napda-admin-error" role="alert">
              {formError}
            </div>
          ) : null}

          <div className="napda-admin-modal-actions">
            <button
              type="button"
              className="napda-admin-btn"
              disabled={submitting}
              onClick={onClose}
            >
              취소
            </button>
            <button
              type="submit"
              className="napda-admin-btn is-active"
              disabled={submitting}
            >
              {submitting
                ? mode === 'create'
                  ? '업로드 중…'
                  : '저장 중…'
                : mode === 'create'
                  ? '템플릿 업로드'
                  : '변경 저장'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export function AdminTemplatesPanel({
  bearerToken,
  reloadSignal = 0,
}: {
  bearerToken: string;
  reloadSignal?: number;
}) {
  const [templates, setTemplates] = useState<TrackATemplateItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [togglingIds, setTogglingIds] = useState<Record<string, boolean>>({});
  const [modalState, setModalState] = useState<
    { mode: 'create'; item: null } | { mode: 'edit'; item: TrackATemplateItem } | null
  >(null);
  const [deleteTarget, setDeleteTarget] = useState<TrackATemplateItem | null>(null);
  const [deleting, setDeleting] = useState(false);

  const authHeaders = useCallback((): HeadersInit | undefined => {
    const trimmed = bearerToken.trim();
    return trimmed ? { Authorization: `Bearer ${trimmed}` } : undefined;
  }, [bearerToken]);

  const fetchTemplates = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await customFetch<{ data: ListTemplatesResponse; status: number }>(
        '/v1/admin/templates/track-a',
        { headers: authHeaders() },
      );
      setTemplates(Array.isArray(res.data?.templates) ? res.data.templates : []);
    } catch (err) {
      setError(parseErrorMessage(err, 'A안 템플릿 목록을 불러오지 못했습니다.'));
    } finally {
      setLoading(false);
    }
  }, [authHeaders]);

  useEffect(() => {
    let active = true;
    const run = async () => {
      setLoading(true);
      setError(null);
      try {
        const res = await customFetch<{ data: ListTemplatesResponse; status: number }>(
          '/v1/admin/templates/track-a',
          { headers: authHeaders() },
        );
        if (!active) return;
        setTemplates(Array.isArray(res.data?.templates) ? res.data.templates : []);
      } catch (err) {
        if (!active) return;
        setError(parseErrorMessage(err, 'A안 템플릿 목록을 불러오지 못했습니다.'));
      } finally {
        if (active) setLoading(false);
      }
    };
    void run();
    return () => {
      active = false;
    };
  }, [authHeaders, reloadSignal]);

  const enabledCount = useMemo(
    () => templates.filter((t) => t.enabled).length,
    [templates],
  );

  const filteredTemplates = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    return templates.filter((t) => {
      if (statusFilter === 'enabled' && !t.enabled) return false;
      if (statusFilter === 'disabled' && t.enabled) return false;
      if (!q) return true;
      const haystack = [
        t.id,
        t.title,
        t.a_genre_archetype,
        t.visual_summary,
        ...t.tags,
      ]
        .join(' ')
        .toLowerCase();
      return haystack.includes(q);
    });
  }, [searchQuery, statusFilter, templates]);

  const handleToggleEnabled = async (item: TrackATemplateItem) => {
    setTogglingIds((prev) => ({ ...prev, [item.id]: true }));
    setError(null);
    try {
      const res = await customFetch<{ data: TrackATemplateItem; status: number }>(
        `/v1/admin/templates/track-a/${encodeURIComponent(item.id)}`,
        {
          method: 'PATCH',
          headers: {
            ...(authHeaders() as Record<string, string> | undefined),
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ enabled: !item.enabled }),
        },
      );
      setTemplates((prev) =>
        prev.map((row) => (row.id === item.id ? res.data : row)),
      );
    } catch (err) {
      setError(parseErrorMessage(err, `${item.title} 활성 상태를 바꾸지 못했습니다.`));
    } finally {
      setTogglingIds((prev) => {
        const next = { ...prev };
        delete next[item.id];
        return next;
      });
    }
  };

  const handleConfirmDelete = async () => {
    if (!deleteTarget) return;
    setDeleting(true);
    setError(null);
    try {
      await customFetch<{ data: { deleted: boolean; id: string }; status: number }>(
        `/v1/admin/templates/track-a/${encodeURIComponent(deleteTarget.id)}`,
        {
          method: 'DELETE',
          headers: authHeaders(),
        },
      );
      setTemplates((prev) => prev.filter((row) => row.id !== deleteTarget.id));
      setDeleteTarget(null);
    } catch (err) {
      setError(parseErrorMessage(err, '템플릿을 삭제하지 못했습니다.'));
    } finally {
      setDeleting(false);
    }
  };

  return (
    <section className="napda-tpl-section">
      <div className="napda-admin-card napda-tpl-toolbar">
        <div className="napda-tpl-toolbar-left">
          <div className="napda-tpl-summary">
            <strong>전체 {templates.length}개</strong> · 활성 {enabledCount}개 · 비활성{' '}
            {templates.length - enabledCount}개
          </div>
          <div className="napda-admin-controls" role="group" aria-label="템플릿 상태 필터">
            {(
              [
                ['all', '전체'],
                ['enabled', '활성'],
                ['disabled', '비활성'],
              ] as const
            ).map(([val, label]) => (
              <button
                key={val}
                type="button"
                className={`napda-admin-btn${statusFilter === val ? ' is-active' : ''}`}
                onClick={() => setStatusFilter(val)}
              >
                {label}
              </button>
            ))}
          </div>
        </div>

        <div className="napda-tpl-toolbar-right">
          <input
            type="search"
            className="napda-admin-input napda-tpl-search"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="제목 · 태그 · ID 검색"
            aria-label="템플릿 검색"
          />
          <button
            type="button"
            className="napda-admin-btn"
            onClick={() => void fetchTemplates()}
            disabled={loading}
          >
            새로고침
          </button>
          <button
            type="button"
            className="napda-admin-btn is-active"
            onClick={() => setModalState({ mode: 'create', item: null })}
          >
            + 새 템플릿 업로드
          </button>
        </div>
      </div>

      {error ? (
        <div className="napda-admin-error" role="alert">
          오류: {error}
        </div>
      ) : null}

      {loading && templates.length === 0 ? (
        <div className="napda-admin-card">A안 템플릿을 불러오는 중...</div>
      ) : filteredTemplates.length === 0 ? (
        <div className="napda-admin-card">
          {templates.length === 0
            ? '등록된 A안 템플릿이 없습니다. "+ 새 템플릿 업로드" 버튼으로 추가해 주세요.'
            : '검색·필터 조건에 맞는 템플릿이 없습니다.'}
        </div>
      ) : (
        <div className="napda-tpl-grid">
          {filteredTemplates.map((t) => {
            const isToggling = Boolean(togglingIds[t.id]);
            return (
              <article
                key={t.id}
                className={`napda-admin-card napda-tpl-card${t.enabled ? '' : ' is-disabled'}`}
              >
                <TemplateVideoPreview
                  videoUrl={t.video_url}
                  cacheKey={`${t.size_bytes}_${t.duration_sec}`}
                  bearerToken={bearerToken}
                  title={t.title}
                />

                <div className="napda-tpl-body">
                  <div className="napda-tpl-head">
                    <div>
                      <h3 className="napda-tpl-title">{t.title}</h3>
                      <code className="napda-admin-mono napda-tpl-id">{t.id}</code>
                    </div>
                    <span
                      className={`napda-admin-badge${t.enabled ? ' is-inworld' : ' is-error'}`}
                    >
                      {t.enabled ? '활성' : '비활성'}
                    </span>
                  </div>

                  <div className="napda-tpl-meta">
                    <span className="napda-admin-badge">{t.a_genre_archetype}</span>
                    <span className="napda-admin-sub" style={{ margin: 0 }}>
                      {t.duration_sec.toFixed(1)}초 · {t.width}×{t.height} ·{' '}
                      {formatMb(t.size_bytes)}
                    </span>
                  </div>

                  {t.tags.length > 0 ? (
                    <div className="napda-tpl-tags">
                      {t.tags.map((tag) => (
                        <span key={tag} className="napda-tpl-tag">
                          #{tag}
                        </span>
                      ))}
                    </div>
                  ) : null}

                  <p className="napda-tpl-summary-text" title={t.visual_summary}>
                    {t.visual_summary}
                  </p>

                  {t.default_hook_captions.length > 0 ? (
                    <ol className="napda-tpl-captions">
                      {t.default_hook_captions.map((cap, idx) => (
                        <li key={idx}>{cap}</li>
                      ))}
                    </ol>
                  ) : null}

                  <div className="napda-tpl-actions">
                    <button
                      type="button"
                      className={`napda-admin-btn${t.enabled ? '' : ' is-active'}`}
                      disabled={isToggling}
                      onClick={() => void handleToggleEnabled(t)}
                    >
                      {isToggling
                        ? '변경 중…'
                        : t.enabled
                          ? '비활성화'
                          : '활성화'}
                    </button>
                    <button
                      type="button"
                      className="napda-admin-btn"
                      onClick={() => setModalState({ mode: 'edit', item: t })}
                    >
                      수정
                    </button>
                    <button
                      type="button"
                      className="napda-admin-btn napda-tpl-btn-danger"
                      onClick={() => setDeleteTarget(t)}
                    >
                      삭제
                    </button>
                  </div>
                </div>
              </article>
            );
          })}
        </div>
      )}

      {modalState ? (
        <TemplateFormModal
          mode={modalState.mode}
          initial={modalState.item}
          bearerToken={bearerToken}
          onClose={() => setModalState(null)}
          onSaved={() => {
            void fetchTemplates();
          }}
        />
      ) : null}

      {deleteTarget ? (
        <div
          className="napda-admin-modal-backdrop"
          role="presentation"
          onClick={() => {
            if (!deleting) setDeleteTarget(null);
          }}
        >
          <div
            className="napda-admin-modal napda-admin-modal--sm"
            role="alertdialog"
            aria-modal="true"
            aria-labelledby="tpl-delete-title"
            onClick={(e) => e.stopPropagation()}
          >
            <h2 id="tpl-delete-title" className="napda-admin-card-title">
              템플릿을 삭제할까요?
            </h2>
            <p className="napda-admin-sub" style={{ marginTop: 8, lineHeight: 1.5 }}>
              <strong>{deleteTarget.title}</strong> (<code>{deleteTarget.id}</code>) 메타데이터와
              저장된 MP4 파일이 삭제됩니다. 되돌릴 수 없어요.
            </p>
            <div className="napda-admin-modal-actions" style={{ marginTop: 18 }}>
              <button
                type="button"
                className="napda-admin-btn"
                disabled={deleting}
                onClick={() => setDeleteTarget(null)}
              >
                취소
              </button>
              <button
                type="button"
                className="napda-admin-btn napda-tpl-btn-danger-solid"
                disabled={deleting}
                onClick={() => void handleConfirmDelete()}
              >
                {deleting ? '삭제 중…' : '삭제하기'}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </section>
  );
}
