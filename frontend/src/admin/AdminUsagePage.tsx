import { Fragment, useCallback, useEffect, useState } from 'react';
import { customFetch } from '../api/mutator';
import type { ThemeSetting } from '../ui/NapdaProvider';
import { AdminAccountsPanel } from './AdminAccountsPanel';
import { AdminTemplatesPanel } from './AdminTemplatesPanel';
import './AdminUsagePage.css';

interface UsageTotals {
  total_calls: number;
  cache_hits: number;
  error_calls: number;
  project_count: number;
  input_tokens: number;
  output_tokens: number;
  cached_tokens: number;
  thinking_tokens: number;
  estimated_cost_usd: number;
  unpriced_calls: number;
}

interface ProviderModelRow {
  provider: string;
  model: string;
  calls: number;
  cache_hits: number;
  project_count: number;
  input_tokens: number;
  output_tokens: number;
  thinking_tokens: number;
  media_unit: string | null;
  media_qty: number;
  unit_price_label: string;
  estimated_cost_usd: number;
  avg_cost_per_project_usd: number;
  unpriced_calls: number;
  avg_latency_ms: number;
}

interface StageRow {
  stage: string;
  calls: number;
  cache_hits: number;
  input_tokens: number;
  output_tokens: number;
  thinking_tokens: number;
  media_unit: string | null;
  media_qty: number;
  estimated_cost_usd: number;
  unpriced_calls: number;
  avg_latency_ms: number;
}

interface ProjectUsageRow {
  project_id: string;
  product_name: string;
  project_status: string | null;
  user_email: string;
  hook_types: string[];
  providers: string[];
  models: string[];
  calls: number;
  cache_hits: number;
  input_tokens: number;
  output_tokens: number;
  thinking_tokens: number;
  video_sec: number;
  image_count: number;
  tts_chars: number;
  estimated_cost_usd: number;
  unpriced_calls: number;
  total_latency_ms: number;
  last_event_at: string;
}

interface UsageEventRow {
  event_id: string;
  created_at: string;
  hook_type: string | null;
  stage: string;
  step_name: string | null;
  provider: string;
  model: string;
  input_tokens: number;
  output_tokens: number;
  cached_tokens: number;
  thinking_tokens: number;
  media_unit: string | null;
  media_qty: number | null;
  estimated_cost_usd: number | null;
  unit_price_label: string | null;
  latency_ms: number;
  cache_hit: boolean;
  status: string;
  metadata?: Record<string, unknown>;
}

interface PricingRow {
  model: string;
  kind: string;
  input_usd_per_1m: number | null;
  output_usd_per_1m: number | null;
  per_unit_usd: number | null;
  unit: string;
  source: string;
}

interface AdminUsageSummaryResponse {
  days: number;
  totals: UsageTotals;
  by_provider_model: ProviderModelRow[];
  by_stage: StageRow[];
  recent_projects: ProjectUsageRow[];
  pricing_version: string;
  pricing_table: PricingRow[];
  usd_krw_rate: number | null;
  admin_actor: string;
  dev_open_admin: boolean;
}

interface AdminScenarioBeat {
  order?: number;
  role?: string;
  duration_sec?: number;
  narration?: string;
  caption?: string;
  visual?: string;
}

interface AdminScenarioArtifact {
  scenario_id?: string;
  type?: string;
  selected?: boolean;
  hook_title?: string;
  abstract_law?: string;
  genre?: string;
  hook_summary?: string;
  beats?: AdminScenarioBeat[];
  shooting_guide?: Record<string, unknown> | null;
  storyboard_frames?: Array<{
    beat_order?: number;
    image_url?: string | null;
    caption?: string | null;
  }>;
}

interface AdminProjectArtifacts {
  product?: {
    name?: string;
    category?: string;
    verified_facts?: string[];
  } | null;
  final_video?: {
    stream_url?: string | null;
    download_url?: string | null;
    raw_master_url?: string | null;
    clean_url?: string | null;
    srt_url?: string | null;
    duration_sec?: number | null;
    has_cover_intro?: boolean;
    cover_intro_sec?: number;
    voice?: string | null;
    job_id?: string | null;
    job_status?: string | null;
    warnings?: string[];
  } | null;
  thumbnail?: {
    image_url?: string | null;
    download_url?: string | null;
    style?: string | null;
    headline_lines?: string[];
    badge?: string | null;
    highlight_word?: string | null;
    has_video_with_cover?: boolean;
    safe_zone_1_1_ok?: boolean | null;
  } | null;
  scenarios?: AdminScenarioArtifact[];
  hooks?: Array<{
    hook_id: string;
    scenario_id?: string | null;
    status?: string | null;
    video_url?: string | null;
    audio_url?: string | null;
    srt_url?: string | null;
    scenario_json_url?: string | null;
    error?: string | null;
  }>;
  body?: {
    video_url?: string | null;
    srt_url?: string | null;
    audio_url?: string | null;
    duration_sec?: number | null;
    script?: {
      lines?: Array<{
        narration?: string;
        caption?: string;
        start?: number;
        duration?: number;
      }>;
    } | null;
  } | null;
  uploads?: Array<{
    clip_id?: string | null;
    filename?: string | null;
    duration_sec?: number | null;
    width?: number | null;
    height?: number | null;
    video_url?: string | null;
  }>;
}

interface ProjectUsageDetailResponse {
  project_id: string;
  events: UsageEventRow[];
  totals: UsageTotals & { total_latency_ms: number };
  artifacts?: AdminProjectArtifacts | null;
}

const BEARER_STORAGE_KEY = 'napda_admin_bearer';
type AdminTab = 'usage' | 'templates' | 'accounts';

function readAdminTabFromUrl(): AdminTab {
  try {
    const tab = new URLSearchParams(window.location.search).get('tab');
    if (tab === 'templates') return 'templates';
    if (tab === 'accounts') return 'accounts';
    return 'usage';
  } catch {
    return 'usage';
  }
}

function fmtUsd(val: number | null | undefined, rate?: number | null): string {
  if (val === null || val === undefined) return '단가 미등록';
  const usdStr = `$${val.toFixed(4)}`;
  if (rate && rate > 0) {
    return `${usdStr} (약 ${Math.round(val * rate).toLocaleString()}원)`;
  }
  return usdStr;
}

function fmtNum(val: number | null | undefined): string {
  return (val ?? 0).toLocaleString();
}

function fmtMedia(unit: string | null, qty: number | null): string {
  if (!unit || !qty) return '-';
  if (unit === 'sec') return `${qty.toFixed(1)}초`;
  if (unit === 'image') return `${Math.round(qty)}장`;
  if (unit === 'char') return `${Math.round(qty)}자`;
  return `${qty} ${unit}`;
}

export function AdminUsagePage({
  themeMode,
  onThemeModeChange,
  userEmail,
}: {
  themeMode: ThemeSetting;
  onThemeModeChange: (next: ThemeSetting) => void;
  userEmail?: string;
}) {
  const [activeTab, setActiveTab] = useState<AdminTab>(() => readAdminTabFromUrl());
  const [days, setDays] = useState<number>(30);
  const [bearerInput, setBearerInput] = useState<string>(() => {
    try {
      return window.sessionStorage.getItem(BEARER_STORAGE_KEY) ?? '';
    } catch {
      return '';
    }
  });
  const [appliedBearer, setAppliedBearer] = useState<string>(() => {
    try {
      return window.sessionStorage.getItem(BEARER_STORAGE_KEY) ?? '';
    } catch {
      return '';
    }
  });
  const [bearerRevision, setBearerRevision] = useState<number>(0);
  const [summary, setSummary] = useState<AdminUsageSummaryResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [detailByProject, setDetailByProject] = useState<Record<string, ProjectUsageDetailResponse>>({});
  const [loadingDetailId, setLoadingDetailId] = useState<string | null>(null);
  const [showPricing, setShowPricing] = useState<boolean>(false);

  const authHeaders = useCallback((): HeadersInit | undefined => {
    const trimmed = appliedBearer.trim();
    return trimmed ? { Authorization: `Bearer ${trimmed}` } : undefined;
  }, [appliedBearer]);

  const loadSummary = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await customFetch<{ data: AdminUsageSummaryResponse; status: number }>(
        `/v1/admin/usage/summary?days=${days}&limit=50`,
        { headers: authHeaders() },
      );
      setSummary(res.data);
    } catch (err) {
      setError(err instanceof Error ? err.message : '사용량 데이터를 불러오지 못했습니다.');
    } finally {
      setLoading(false);
    }
  }, [authHeaders, days]);

  useEffect(() => {
    const onPopState = () => {
      setActiveTab(readAdminTabFromUrl());
    };
    window.addEventListener('popstate', onPopState);
    return () => window.removeEventListener('popstate', onPopState);
  }, []);

  useEffect(() => {
    let active = true;
    const run = async () => {
      setLoading(true);
      setError(null);
      try {
        const res = await customFetch<{ data: AdminUsageSummaryResponse; status: number }>(
          `/v1/admin/usage/summary?days=${days}&limit=50`,
          { headers: authHeaders() },
        );
        if (!active) return;
        setSummary(res.data);
      } catch (err) {
        if (!active) return;
        setError(err instanceof Error ? err.message : '사용량 데이터를 불러오지 못했습니다.');
      } finally {
        if (active) setLoading(false);
      }
    };
    void run();
    return () => {
      active = false;
    };
  }, [authHeaders, days, bearerRevision]);

  const handleSelectTab = (next: AdminTab) => {
    setActiveTab(next);
    try {
      const url = new URL(window.location.href);
      url.searchParams.set('tab', next);
      window.history.replaceState(null, '', url.toString());
    } catch {
      // ignore history errors
    }
  };

  const handleSaveBearer = () => {
    const trimmed = bearerInput.trim();
    try {
      if (trimmed) window.sessionStorage.setItem(BEARER_STORAGE_KEY, trimmed);
      else window.sessionStorage.removeItem(BEARER_STORAGE_KEY);
    } catch {
      // ignore storage errors
    }
    setAppliedBearer(trimmed);
    setBearerRevision((n) => n + 1);
  };

  const handleToggleProject = async (projectId: string) => {
    if (expandedId === projectId) {
      setExpandedId(null);
      return;
    }
    setExpandedId(projectId);
    if (detailByProject[projectId]) return;
    setLoadingDetailId(projectId);
    try {
      const res = await customFetch<{ data: ProjectUsageDetailResponse; status: number }>(
        `/v1/admin/usage/projects/${encodeURIComponent(projectId)}`,
        { headers: authHeaders() },
      );
      setDetailByProject((prev) => ({ ...prev, [projectId]: res.data }));
    } catch (err) {
      setError(err instanceof Error ? err.message : '상세 내역을 불러오지 못했습니다.');
    } finally {
      setLoadingDetailId(null);
    }
  };

  const totals = summary?.totals;
  const rate = summary?.usd_krw_rate ?? null;

  return (
    <div className="napda-admin">
      <div className="napda-admin-inner">
        <header className="napda-admin-header">
          <div>
            <h1 className="napda-admin-title">
              {activeTab === 'templates'
                ? 'NAPDA A안 템플릿 관리'
                : activeTab === 'accounts'
                  ? 'NAPDA 계정 · 내부 테스트 관리'
                  : 'NAPDA 사용량 · 단가 · A/B 텔레메트리'}
            </h1>
            <p className="napda-admin-sub">
              {summary
                ? `접속: ${summary.admin_actor}${summary.dev_open_admin ? ' (로컬 오픈 모드 — 운영 시 ADMIN_EMAILS 설정 필요)' : ''} · 단가 기준 ${summary.pricing_version}`
                : userEmail
                  ? `로그인 계정: ${userEmail}`
                  : '관리자 계정 또는 API Bearer Token 필요'}
            </p>
          </div>
          <div className="napda-admin-controls">
            {activeTab === 'usage' ? (
              <>
                {[7, 30, 90].map((d) => (
                  <button
                    key={d}
                    type="button"
                    className={`napda-admin-btn${days === d ? ' is-active' : ''}`}
                    onClick={() => setDays(d)}
                  >
                    {d}일
                  </button>
                ))}
                <button type="button" className="napda-admin-btn" onClick={() => void loadSummary()}>
                  새로고침
                </button>
              </>
            ) : null}
            <button
              type="button"
              className="napda-admin-btn"
              onClick={() => onThemeModeChange(themeMode === 'dark' ? 'light' : 'dark')}
            >
              {themeMode === 'dark' ? '라이트' : '다크'}
            </button>
            <a className="napda-admin-link" href="/?provider=anthropic">
              Claude 테스트 열기
            </a>
            <a className="napda-admin-link" href="/?provider=google">
              Gemini 테스트 열기
            </a>
            <a className="napda-admin-link" href="/">
              스튜디오로 돌아가기
            </a>
          </div>
        </header>

        <nav className="napda-admin-tabs" role="tablist" aria-label="관리자 메뉴">
          <button
            type="button"
            role="tab"
            aria-selected={activeTab === 'usage'}
            className={`napda-admin-tab${activeTab === 'usage' ? ' is-active' : ''}`}
            onClick={() => handleSelectTab('usage')}
          >
            사용량 · 비용
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={activeTab === 'templates'}
            className={`napda-admin-tab${activeTab === 'templates' ? ' is-active' : ''}`}
            onClick={() => handleSelectTab('templates')}
          >
            A안 템플릿 관리
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={activeTab === 'accounts'}
            className={`napda-admin-tab${activeTab === 'accounts' ? ' is-active' : ''}`}
            onClick={() => handleSelectTab('accounts')}
          >
            계정 관리
          </button>
        </nav>

        <div className="napda-admin-bearer">
          <span className="napda-admin-sub" style={{ margin: 0 }}>
            Admin Bearer Token (선택 · `ADMIN_EMAILS` 로그인 대신 사용 시):
          </span>
          <input
            className="napda-admin-input"
            type="password"
            value={bearerInput}
            onChange={(e) => setBearerInput(e.target.value)}
            placeholder="API_BEARER_TOKEN 입력 후 적용"
          />
          <button type="button" className="napda-admin-btn" onClick={handleSaveBearer}>
            토큰 적용
          </button>
        </div>

        {activeTab === 'templates' ? (
          <AdminTemplatesPanel
            bearerToken={appliedBearer}
            reloadSignal={bearerRevision}
          />
        ) : activeTab === 'accounts' ? (
          <AdminAccountsPanel
            bearerToken={appliedBearer}
            reloadSignal={bearerRevision}
          />
        ) : (
          <>
        {error && (
          <div className="napda-admin-error">
            오류: {error} (백엔드 `ADMIN_EMAILS`에 이메일 등록 또는 위 `API_BEARER_TOKEN`을 입력해 주세요.)
          </div>
        )}

        {loading && !summary ? (
          <div className="napda-admin-card">불러오는 중...</div>
        ) : null}

        {totals && (
          <section className="napda-admin-kpis">
            <div className="napda-admin-kpi">
              <div className="napda-admin-kpi-label">총 추정 비용 ({summary?.days}일)</div>
              <div className="napda-admin-kpi-val">{fmtUsd(totals.estimated_cost_usd, rate)}</div>
              <div className="napda-admin-kpi-note">
                단가 미등록 호출 {fmtNum(totals.unpriced_calls)}건 제외 합계
              </div>
            </div>
            <div className="napda-admin-kpi">
              <div className="napda-admin-kpi-label">총 API 호출 수</div>
              <div className="napda-admin-kpi-val">{fmtNum(totals.total_calls)}회</div>
              <div className="napda-admin-kpi-note">
                캐시 히트 {fmtNum(totals.cache_hits)}회 · 오류 {fmtNum(totals.error_calls)}회
              </div>
            </div>
            <div className="napda-admin-kpi">
              <div className="napda-admin-kpi-label">총 토큰 (입력 / 출력)</div>
              <div className="napda-admin-kpi-val">
                {fmtNum(totals.input_tokens)} / {fmtNum(totals.output_tokens)}
              </div>
              <div className="napda-admin-kpi-note">
                생각 토큰 {fmtNum(totals.thinking_tokens)} · 캐시 토큰 {fmtNum(totals.cached_tokens)}
              </div>
            </div>
            <div className="napda-admin-kpi">
              <div className="napda-admin-kpi-label">집계 프로젝트 수</div>
              <div className="napda-admin-kpi-val">{fmtNum(totals.project_count)}건</div>
              <div className="napda-admin-kpi-note">
                건당 평균{' '}
                {totals.project_count > 0
                  ? fmtUsd(totals.estimated_cost_usd / totals.project_count, rate)
                  : '$0.0000'}
              </div>
            </div>
          </section>
        )}

        {summary && (
          <section className="napda-admin-card">
            <div className="napda-admin-card-head">
              <h2 className="napda-admin-card-title">모델별 사용량 · A/B 단가 비교</h2>
            </div>
            <div className="napda-admin-table-wrap">
              <table className="napda-admin-table">
                <thead>
                  <tr>
                    <th>공급자</th>
                    <th>모델</th>
                    <th className="num">호출(캐시)</th>
                    <th className="num">프로젝트</th>
                    <th className="num">입력 토큰</th>
                    <th className="num">출력(+생각) 토큰</th>
                    <th>미디어</th>
                    <th>적용 단가</th>
                    <th className="num">건당 평균</th>
                    <th className="num">합계(USD)</th>
                    <th className="num">평균 지연</th>
                  </tr>
                </thead>
                <tbody>
                  {summary.by_provider_model.length === 0 ? (
                    <tr>
                      <td colSpan={11}>아직 기록된 사용량이 없습니다.</td>
                    </tr>
                  ) : (
                    summary.by_provider_model.map((row) => (
                      <tr key={`${row.provider}:${row.model}`}>
                        <td>
                          <span className={`napda-admin-badge is-${row.provider}`}>{row.provider}</span>
                        </td>
                        <td className="napda-admin-mono">{row.model}</td>
                        <td className="num">
                          {fmtNum(row.calls)} ({fmtNum(row.cache_hits)})
                        </td>
                        <td className="num">{fmtNum(row.project_count)}</td>
                        <td className="num">{fmtNum(row.input_tokens)}</td>
                        <td className="num">
                          {fmtNum(row.output_tokens + row.thinking_tokens)}
                        </td>
                        <td>{fmtMedia(row.media_unit, row.media_qty)}</td>
                        <td className="napda-admin-mono">{row.unit_price_label}</td>
                        <td className="num">{fmtUsd(row.avg_cost_per_project_usd, rate)}</td>
                        <td className="num">{fmtUsd(row.estimated_cost_usd, rate)}</td>
                        <td className="num">{fmtNum(row.avg_latency_ms)} ms</td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </section>
        )}

        {summary && (
          <section className="napda-admin-card">
            <div className="napda-admin-card-head">
              <h2 className="napda-admin-card-title">단계별 사용량 (Stage Breakdown)</h2>
            </div>
            <div className="napda-admin-table-wrap">
              <table className="napda-admin-table">
                <thead>
                  <tr>
                    <th>단계</th>
                    <th className="num">호출(캐시)</th>
                    <th className="num">입력 토큰</th>
                    <th className="num">출력(+생각) 토큰</th>
                    <th>미디어</th>
                    <th className="num">추정 비용</th>
                    <th className="num">평균 지연</th>
                  </tr>
                </thead>
                <tbody>
                  {summary.by_stage.length === 0 ? (
                    <tr>
                      <td colSpan={7}>데이터 없음</td>
                    </tr>
                  ) : (
                    summary.by_stage.map((row) => (
                      <tr key={row.stage}>
                        <td className="napda-admin-mono">{row.stage}</td>
                        <td className="num">
                          {fmtNum(row.calls)} ({fmtNum(row.cache_hits)})
                        </td>
                        <td className="num">{fmtNum(row.input_tokens)}</td>
                        <td className="num">{fmtNum(row.output_tokens + row.thinking_tokens)}</td>
                        <td>{fmtMedia(row.media_unit, row.media_qty)}</td>
                        <td className="num">{fmtUsd(row.estimated_cost_usd, rate)}</td>
                        <td className="num">{fmtNum(row.avg_latency_ms)} ms</td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </section>
        )}

        {summary && (
          <section className="napda-admin-card">
            <div className="napda-admin-card-head">
              <h2 className="napda-admin-card-title">프로젝트(건당) 사용 내역 — 행 클릭 시 단계별 상세</h2>
            </div>
            <div className="napda-admin-table-wrap">
              <table className="napda-admin-table">
                <thead>
                  <tr>
                    <th>프로젝트</th>
                    <th>사용자</th>
                    <th>유형</th>
                    <th>사용 모델</th>
                    <th className="num">호출</th>
                    <th className="num">입력/출력 토큰</th>
                    <th>영상 · 이미지 · TTS</th>
                    <th className="num">추정 비용</th>
                    <th className="num">누적 지연</th>
                  </tr>
                </thead>
                <tbody>
                  {summary.recent_projects.length === 0 ? (
                    <tr>
                      <td colSpan={9}>최근 프로젝트 사용 기록이 없습니다.</td>
                    </tr>
                  ) : (
                    summary.recent_projects.map((p) => {
                      const isExpanded = expandedId === p.project_id;
                      const detail = detailByProject[p.project_id];
                      return (
                        <Fragment key={p.project_id}>
                          <tr
                            className="napda-admin-row-btn"
                            onClick={() => void handleToggleProject(p.project_id)}
                          >
                            <td>
                              <strong>{p.product_name}</strong>
                              <div className="napda-admin-mono">{p.project_id}</div>
                            </td>
                            <td>{p.user_email || '-'}</td>
                            <td>{p.hook_types.join(', ') || '-'}</td>
                            <td className="napda-admin-mono">{p.models.join(', ')}</td>
                            <td className="num">
                              {fmtNum(p.calls)} ({fmtNum(p.cache_hits)})
                            </td>
                            <td className="num">
                              {fmtNum(p.input_tokens)} / {fmtNum(p.output_tokens + p.thinking_tokens)}
                            </td>
                            <td>
                              {p.video_sec > 0 ? `${p.video_sec.toFixed(1)}s ` : ''}
                              {p.image_count > 0 ? `${p.image_count}장 ` : ''}
                              {p.tts_chars > 0 ? `${p.tts_chars}자` : ''}
                              {p.video_sec === 0 && p.image_count === 0 && p.tts_chars === 0 ? '-' : ''}
                            </td>
                            <td className="num">{fmtUsd(p.estimated_cost_usd, rate)}</td>
                            <td className="num">{(p.total_latency_ms / 1000).toFixed(1)}s</td>
                          </tr>
                          {isExpanded && (
                            <tr>
                              <td colSpan={9} className="napda-admin-detail">
                                {loadingDetailId === p.project_id && !detail ? (
                                  <div>상세 이벤트 불러오는 중...</div>
                                ) : detail ? (
                                  <div className="napda-admin-artifacts">
                                    {detail.artifacts && (
                                      <>
                                        {(detail.artifacts.final_video || detail.artifacts.thumbnail) && (
                                          <div className="napda-admin-artifact-section">
                                            <h3 className="napda-admin-artifact-title">최종 결과물 · 썸네일</h3>
                                            <div className="napda-admin-artifact-grid">
                                              {detail.artifacts.final_video?.stream_url && (
                                                <div className="napda-admin-media-card">
                                                  <div className="napda-admin-media-head">
                                                    <strong>최종 영상</strong>
                                                    {detail.artifacts.final_video.has_cover_intro ? (
                                                      <span className="napda-admin-badge is-google">
                                                        썸네일 인트로 포함 (+
                                                        {detail.artifacts.final_video.cover_intro_sec ?? 0.4}s)
                                                      </span>
                                                    ) : (
                                                      <span className="napda-admin-badge">원본 마스터</span>
                                                    )}
                                                  </div>
                                                  <video
                                                    className="napda-admin-video"
                                                    controls
                                                    playsInline
                                                    preload="metadata"
                                                    src={detail.artifacts.final_video.stream_url}
                                                    poster={detail.artifacts.thumbnail?.image_url ?? undefined}
                                                  />
                                                  <div className="napda-admin-media-meta">
                                                    {detail.artifacts.final_video.duration_sec !== null &&
                                                    detail.artifacts.final_video.duration_sec !== undefined
                                                      ? `${detail.artifacts.final_video.duration_sec.toFixed(1)}s`
                                                      : '-'}
                                                    {detail.artifacts.final_video.voice
                                                      ? ` · 음성: ${detail.artifacts.final_video.voice}`
                                                      : ''}
                                                  </div>
                                                  <div className="napda-admin-media-links">
                                                    {detail.artifacts.final_video.download_url && (
                                                      <a
                                                        className="napda-admin-link"
                                                        href={detail.artifacts.final_video.download_url}
                                                        target="_blank"
                                                        rel="noreferrer"
                                                      >
                                                        최종 MP4
                                                      </a>
                                                    )}
                                                    {detail.artifacts.final_video.raw_master_url &&
                                                      detail.artifacts.final_video.has_cover_intro && (
                                                        <a
                                                          className="napda-admin-link"
                                                          href={detail.artifacts.final_video.raw_master_url}
                                                          target="_blank"
                                                          rel="noreferrer"
                                                        >
                                                          커버 전 마스터
                                                        </a>
                                                      )}
                                                    {detail.artifacts.final_video.clean_url && (
                                                      <a
                                                        className="napda-admin-link"
                                                        href={detail.artifacts.final_video.clean_url}
                                                        target="_blank"
                                                        rel="noreferrer"
                                                      >
                                                        클린본
                                                      </a>
                                                    )}
                                                    {detail.artifacts.final_video.srt_url && (
                                                      <a
                                                        className="napda-admin-link"
                                                        href={detail.artifacts.final_video.srt_url}
                                                        target="_blank"
                                                        rel="noreferrer"
                                                      >
                                                        자막 SRT
                                                      </a>
                                                    )}
                                                  </div>
                                                </div>
                                              )}

                                              {detail.artifacts.thumbnail?.image_url && (
                                                <div className="napda-admin-media-card">
                                                  <div className="napda-admin-media-head">
                                                    <strong>커버 썸네일</strong>
                                                    {detail.artifacts.thumbnail.style && (
                                                      <span className="napda-admin-badge">
                                                        {detail.artifacts.thumbnail.style}
                                                      </span>
                                                    )}
                                                  </div>
                                                  <img
                                                    className="napda-admin-thumb-img"
                                                    src={detail.artifacts.thumbnail.image_url}
                                                    alt="프로젝트 썸네일"
                                                  />
                                                  {detail.artifacts.thumbnail.headline_lines &&
                                                    detail.artifacts.thumbnail.headline_lines.length > 0 && (
                                                      <div className="napda-admin-media-meta">
                                                        문구:{' '}
                                                        {detail.artifacts.thumbnail.headline_lines.join(' / ')}
                                                      </div>
                                                    )}
                                                  <div className="napda-admin-media-links">
                                                    {detail.artifacts.thumbnail.download_url && (
                                                      <a
                                                        className="napda-admin-link"
                                                        href={detail.artifacts.thumbnail.download_url}
                                                        target="_blank"
                                                        rel="noreferrer"
                                                      >
                                                        썸네일 PNG
                                                      </a>
                                                    )}
                                                  </div>
                                                </div>
                                              )}
                                            </div>
                                          </div>
                                        )}

                                        {(detail.artifacts.product ||
                                          (detail.artifacts.scenarios && detail.artifacts.scenarios.length > 0)) && (
                                          <div className="napda-admin-artifact-section">
                                            <h3 className="napda-admin-artifact-title">기획 글 · 시나리오 · 콘티</h3>
                                            {detail.artifacts.product && (
                                              <div className="napda-admin-product-box">
                                                <strong>{detail.artifacts.product.name || p.product_name}</strong>
                                                {detail.artifacts.product.category && (
                                                  <span className="napda-admin-badge">
                                                    {detail.artifacts.product.category}
                                                  </span>
                                                )}
                                                {detail.artifacts.product.verified_facts &&
                                                  detail.artifacts.product.verified_facts.length > 0 && (
                                                    <ul className="napda-admin-facts">
                                                      {detail.artifacts.product.verified_facts.map((fact, idx) => (
                                                        <li key={idx}>{fact}</li>
                                                      ))}
                                                    </ul>
                                                  )}
                                              </div>
                                            )}

                                            {detail.artifacts.scenarios?.map((scn, sIdx) => (
                                              <div
                                                key={scn.scenario_id || sIdx}
                                                className="napda-admin-scenario-card"
                                              >
                                                <div className="napda-admin-media-head">
                                                  <div>
                                                    <span className="napda-admin-badge">{scn.type || '?'}안</span>{' '}
                                                    {scn.selected && (
                                                      <span className="napda-admin-badge is-inworld">선택됨</span>
                                                    )}{' '}
                                                    <strong>{scn.hook_title || scn.scenario_id}</strong>
                                                  </div>
                                                  <span className="napda-admin-mono">{scn.scenario_id}</span>
                                                </div>
                                                {(scn.abstract_law || scn.genre || scn.hook_summary) && (
                                                  <p className="napda-admin-scenario-summary">
                                                    {[scn.genre, scn.abstract_law, scn.hook_summary]
                                                      .filter(Boolean)
                                                      .join(' · ')}
                                                  </p>
                                                )}
                                                {scn.beats && scn.beats.length > 0 && (
                                                  <div className="napda-admin-table-wrap">
                                                    <table className="napda-admin-table napda-admin-subtable">
                                                      <thead>
                                                        <tr>
                                                          <th>컷</th>
                                                          <th>시간</th>
                                                          <th>나레이션</th>
                                                          <th>자막</th>
                                                          <th>화면 연출(Visual)</th>
                                                        </tr>
                                                      </thead>
                                                      <tbody>
                                                        {scn.beats.map((b, bIdx) => (
                                                          <tr key={bIdx}>
                                                            <td>{b.order ?? bIdx + 1}</td>
                                                            <td>
                                                              {b.duration_sec !== undefined
                                                                ? `${b.duration_sec}s`
                                                                : '-'}
                                                            </td>
                                                            <td className="wrap">{b.narration || '-'}</td>
                                                            <td className="wrap">{b.caption || '-'}</td>
                                                            <td className="wrap">{b.visual || '-'}</td>
                                                          </tr>
                                                        ))}
                                                      </tbody>
                                                    </table>
                                                  </div>
                                                )}
                                                {scn.storyboard_frames && scn.storyboard_frames.length > 0 && (
                                                  <div className="napda-admin-storyboard-grid">
                                                    {scn.storyboard_frames.map((fr, fIdx) => (
                                                      <div key={fIdx} className="napda-admin-storyboard-item">
                                                        {fr.image_url && (
                                                          <img src={fr.image_url} alt={`콘티 ${fIdx + 1}`} />
                                                        )}
                                                        <div className="napda-admin-media-meta">
                                                          #{fr.beat_order ?? fIdx + 1} {fr.caption || ''}
                                                        </div>
                                                      </div>
                                                    ))}
                                                  </div>
                                                )}
                                              </div>
                                            ))}
                                          </div>
                                        )}

                                        {((detail.artifacts.hooks && detail.artifacts.hooks.length > 0) ||
                                          detail.artifacts.body ||
                                          (detail.artifacts.uploads && detail.artifacts.uploads.length > 0)) && (
                                          <div className="napda-admin-artifact-section">
                                            <h3 className="napda-admin-artifact-title">중간 산물 (훅 · 본편 · 업로드)</h3>
                                            <div className="napda-admin-artifact-grid">
                                              {detail.artifacts.hooks?.map((hk) => (
                                                <div key={hk.hook_id} className="napda-admin-media-card">
                                                  <div className="napda-admin-media-head">
                                                    <strong>훅 ({hk.hook_id})</strong>
                                                    <span className="napda-admin-badge">{hk.status || '-'}</span>
                                                  </div>
                                                  {hk.video_url && (
                                                    <video
                                                      className="napda-admin-video"
                                                      controls
                                                      playsInline
                                                      preload="metadata"
                                                      src={hk.video_url}
                                                    />
                                                  )}
                                                  <div className="napda-admin-media-links">
                                                    {hk.audio_url && (
                                                      <a
                                                        className="napda-admin-link"
                                                        href={hk.audio_url}
                                                        target="_blank"
                                                        rel="noreferrer"
                                                      >
                                                        TTS 오디오
                                                      </a>
                                                    )}
                                                    {hk.srt_url && (
                                                      <a
                                                        className="napda-admin-link"
                                                        href={hk.srt_url}
                                                        target="_blank"
                                                        rel="noreferrer"
                                                      >
                                                        훅 자막
                                                      </a>
                                                    )}
                                                    {hk.scenario_json_url && (
                                                      <a
                                                        className="napda-admin-link"
                                                        href={hk.scenario_json_url}
                                                        target="_blank"
                                                        rel="noreferrer"
                                                      >
                                                        시나리오 JSON
                                                      </a>
                                                    )}
                                                  </div>
                                                </div>
                                              ))}

                                              {detail.artifacts.body && (
                                                <div className="napda-admin-media-card">
                                                  <div className="napda-admin-media-head">
                                                    <strong>본편 편집본</strong>
                                                    {detail.artifacts.body.duration_sec && (
                                                      <span className="napda-admin-badge">
                                                        {detail.artifacts.body.duration_sec.toFixed(1)}s
                                                      </span>
                                                    )}
                                                  </div>
                                                  {detail.artifacts.body.video_url && (
                                                    <video
                                                      className="napda-admin-video"
                                                      controls
                                                      playsInline
                                                      preload="metadata"
                                                      src={detail.artifacts.body.video_url}
                                                    />
                                                  )}
                                                  {detail.artifacts.body.script?.lines && (
                                                    <ul className="napda-admin-facts">
                                                      {detail.artifacts.body.script.lines.map((ln, lIdx) => (
                                                        <li key={lIdx}>{ln.narration || ln.caption}</li>
                                                      ))}
                                                    </ul>
                                                  )}
                                                  <div className="napda-admin-media-links">
                                                    {detail.artifacts.body.srt_url && (
                                                      <a
                                                        className="napda-admin-link"
                                                        href={detail.artifacts.body.srt_url}
                                                        target="_blank"
                                                        rel="noreferrer"
                                                      >
                                                        본편 SRT
                                                      </a>
                                                    )}
                                                  </div>
                                                </div>
                                              )}

                                              {detail.artifacts.uploads && detail.artifacts.uploads.length > 0 && (
                                                <div className="napda-admin-media-card">
                                                  <div className="napda-admin-media-head">
                                                    <strong>업로드 원본 ({detail.artifacts.uploads.length}개)</strong>
                                                  </div>
                                                  <ul className="napda-admin-facts">
                                                    {detail.artifacts.uploads.map((up, uIdx) => (
                                                      <li key={up.clip_id || uIdx}>
                                                        {up.filename || up.clip_id} (
                                                        {up.duration_sec ? `${up.duration_sec.toFixed(1)}s` : '-'})
                                                        {up.video_url && (
                                                          <>
                                                            {' '}
                                                            <a
                                                              href={up.video_url}
                                                              target="_blank"
                                                              rel="noreferrer"
                                                            >
                                                              열기
                                                            </a>
                                                          </>
                                                        )}
                                                      </li>
                                                    ))}
                                                  </ul>
                                                </div>
                                              )}
                                            </div>
                                          </div>
                                        )}
                                      </>
                                    )}

                                    <h3 className="napda-admin-artifact-title">단계별 AI 호출 · 비용 기록</h3>
                                    <table className="napda-admin-table">
                                      <thead>
                                        <tr>
                                          <th>단계 / 스텝</th>
                                          <th>공급자 · 모델</th>
                                          <th className="num">입력</th>
                                          <th className="num">출력(+생각)</th>
                                          <th>미디어</th>
                                          <th>적용 단가</th>
                                          <th className="num">비용</th>
                                          <th className="num">지연</th>
                                          <th>상태</th>
                                          <th>프롬프트 / 산물</th>
                                        </tr>
                                      </thead>
                                      <tbody>
                                        {detail.events.map((ev) => (
                                          <tr key={ev.event_id}>
                                            <td className="napda-admin-mono">
                                              {ev.stage}
                                              {ev.step_name ? ` · ${ev.step_name}` : ''}
                                              {ev.hook_type ? ` [${ev.hook_type}]` : ''}
                                            </td>
                                            <td>
                                              <span className={`napda-admin-badge is-${ev.provider}`}>
                                                {ev.provider}
                                              </span>{' '}
                                              <span className="napda-admin-mono">{ev.model}</span>
                                            </td>
                                            <td className="num">{fmtNum(ev.input_tokens)}</td>
                                            <td className="num">
                                              {fmtNum(ev.output_tokens + ev.thinking_tokens)}
                                            </td>
                                            <td>{fmtMedia(ev.media_unit, ev.media_qty)}</td>
                                            <td className="napda-admin-mono">
                                              {ev.unit_price_label || '-'}
                                            </td>
                                            <td className="num">{fmtUsd(ev.estimated_cost_usd, rate)}</td>
                                            <td className="num">{fmtNum(ev.latency_ms)} ms</td>
                                            <td>
                                              {ev.cache_hit ? (
                                                <span className="napda-admin-badge">CACHE</span>
                                              ) : ev.status !== 'ok' ? (
                                                <span className="napda-admin-badge is-error">
                                                  {ev.status}
                                                </span>
                                              ) : (
                                                'OK'
                                              )}
                                            </td>
                                            <td className="wrap">
                                              {ev.metadata && Object.keys(ev.metadata).length > 0 ? (
                                                <details>
                                                  <summary className="napda-admin-meta-summary">보기</summary>
                                                  <pre className="napda-admin-meta-pre">
                                                    {JSON.stringify(ev.metadata, null, 2)}
                                                  </pre>
                                                </details>
                                              ) : (
                                                '-'
                                              )}
                                            </td>
                                          </tr>
                                        ))}
                                      </tbody>
                                    </table>
                                  </div>
                                ) : null}
                              </td>
                            </tr>
                          )}
                        </Fragment>
                      );
                    })
                  )}
                </tbody>
              </table>
            </div>
          </section>
        )}

        {summary && (
          <section className="napda-admin-card">
            <div className="napda-admin-card-head">
              <h2 className="napda-admin-card-title">
                적용 단가표 ({summary.pricing_version})
              </h2>
              <button
                type="button"
                className="napda-admin-btn"
                onClick={() => setShowPricing((v) => !v)}
              >
                {showPricing ? '접기' : '단가표 보기'}
              </button>
            </div>
            {showPricing && (
              <div className="napda-admin-table-wrap">
                <table className="napda-admin-table">
                  <thead>
                    <tr>
                      <th>모델</th>
                      <th>구분</th>
                      <th className="num">입력 단가</th>
                      <th className="num">출력 단가</th>
                      <th className="num">단위 단가</th>
                      <th>출처</th>
                    </tr>
                  </thead>
                  <tbody>
                    {summary.pricing_table.map((row) => (
                      <tr key={row.model}>
                        <td className="napda-admin-mono">{row.model}</td>
                        <td>{row.unit}</td>
                        <td className="num">
                          {row.input_usd_per_1m !== null ? `$${row.input_usd_per_1m}` : '-'}
                        </td>
                        <td className="num">
                          {row.output_usd_per_1m !== null ? `$${row.output_usd_per_1m}` : '-'}
                        </td>
                        <td className="num">
                          {row.per_unit_usd !== null ? `$${row.per_unit_usd}` : '-'}
                        </td>
                        <td>{row.source}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        )}
          </>
        )}
      </div>
    </div>
  );
}
