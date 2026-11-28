import { useCallback, useEffect, useState, type FormEvent } from 'react';
import { customFetch, NapdaApiError } from '../api/mutator';

export interface AdminAccountRow {
  user_id: string | null;
  email: string;
  name: string | null;
  picture: string | null;
  credits: number;
  free_videos_remaining: number;
  project_count: number;
  renders_today: number;
  is_internal: boolean;
  internal_source: 'db' | 'env' | null;
  note: string;
  has_logged_in: boolean;
  created_at: string | null;
  last_login_at: string | null;
}

interface AdminAccountsResponse {
  accounts: AdminAccountRow[];
  internal_count: number;
  total_count: number;
  admin_actor: string;
}

function parseError(err: unknown, fallback: string): string {
  if (err instanceof NapdaApiError) return err.message || fallback;
  if (err instanceof Error && err.message) return err.message;
  return fallback;
}

export function AdminAccountsPanel({
  bearerToken,
  reloadSignal,
}: {
  bearerToken: string;
  reloadSignal: number;
}) {
  const [accounts, setAccounts] = useState<AdminAccountRow[]>([]);
  const [internalCount, setInternalCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [emailInput, setEmailInput] = useState('');
  const [noteInput, setNoteInput] = useState('');
  const [busyKey, setBusyKey] = useState<string | null>(null);

  const authHeaders = useCallback((): HeadersInit | undefined => {
    const trimmed = bearerToken.trim();
    return trimmed ? { Authorization: `Bearer ${trimmed}` } : undefined;
  }, [bearerToken]);

  const loadAccounts = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await customFetch<{ data: AdminAccountsResponse; status: number }>(
        '/v1/admin/accounts',
        { headers: authHeaders() },
      );
      setAccounts(res.data.accounts);
      setInternalCount(res.data.internal_count);
    } catch (err) {
      setError(parseError(err, '계정 목록을 불러오지 못했습니다.'));
    } finally {
      setLoading(false);
    }
  }, [authHeaders]);

  useEffect(() => {
    void loadAccounts();
  }, [loadAccounts, reloadSignal]);

  const applyResponse = (data: AdminAccountsResponse, message: string) => {
    setAccounts(data.accounts);
    setInternalCount(data.internal_count);
    setNotice(message);
    setError(null);
  };

  const handleAddInternal = async (e: FormEvent) => {
    e.preventDefault();
    const email = emailInput.trim().toLowerCase();
    if (!email || !email.includes('@')) {
      setError('올바른 구글 계정 이메일을 입력해 주세요.');
      return;
    }
    setBusyKey('add');
    setError(null);
    setNotice(null);
    try {
      const res = await customFetch<{ data: AdminAccountsResponse; status: number }>(
        '/v1/admin/accounts/internal',
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            ...(authHeaders() ?? {}),
          },
          body: JSON.stringify({
            email,
            is_internal: true,
            note: noteInput.trim() || undefined,
          }),
        },
      );
      setEmailInput('');
      setNoteInput('');
      applyResponse(res.data, `${email} 계정을 내부 테스트 계정으로 등록했습니다. (크레딧·일일 한도 면제)`);
    } catch (err) {
      setError(parseError(err, '내부 계정 등록에 실패했습니다.'));
    } finally {
      setBusyKey(null);
    }
  };

  const handleToggleInternal = async (row: AdminAccountRow) => {
    const targetEmail = row.email.trim().toLowerCase();
    const nextInternal = !row.is_internal;
    setBusyKey(targetEmail);
    setError(null);
    setNotice(null);
    try {
      const url = nextInternal
        ? '/v1/admin/accounts/internal'
        : `/v1/admin/accounts/internal/${encodeURIComponent(targetEmail)}`;
      const res = await customFetch<{ data: AdminAccountsResponse; status: number }>(
        url,
        nextInternal
          ? {
              method: 'POST',
              headers: {
                'Content-Type': 'application/json',
                ...(authHeaders() ?? {}),
              },
              body: JSON.stringify({
                email: targetEmail,
                is_internal: true,
                note: row.note || undefined,
              }),
            }
          : {
              method: 'DELETE',
              headers: authHeaders(),
            },
      );
      applyResponse(
        res.data,
        nextInternal
          ? `${targetEmail} → 내부 테스트 계정 지정됨 (크레딧 차감 없음)`
          : `${targetEmail} → 일반 계정으로 전환됨`,
      );
    } catch (err) {
      setError(parseError(err, '내부 계정 상태 변경에 실패했습니다.'));
    } finally {
      setBusyKey(null);
    }
  };

  return (
    <>
      {error && <div className="napda-admin-error">오류: {error}</div>}
      {notice && (
        <div className="napda-admin-card" style={{ borderColor: 'rgba(16, 185, 129, 0.4)' }}>
          {notice}
        </div>
      )}

      <section className="napda-admin-kpis">
        <div className="napda-admin-kpi">
          <div className="napda-admin-kpi-label">전체 계정 수</div>
          <div className="napda-admin-kpi-val">{accounts.length}명</div>
          <div className="napda-admin-kpi-note">로그인 이력 + 사전 등록 이메일 포함</div>
        </div>
        <div className="napda-admin-kpi">
          <div className="napda-admin-kpi-label">내부 테스트 계정 (크레딧 면제)</div>
          <div className="napda-admin-kpi-val">{internalCount}명</div>
          <div className="napda-admin-kpi-note">결제/잔액·일일 생성 한도 없이 영상 테스트 가능</div>
        </div>
      </section>

      <section className="napda-admin-card">
        <div className="napda-admin-card-head">
          <h2 className="napda-admin-card-title">내부 테스트 계정 추가 / 지정</h2>
          <button
            type="button"
            className="napda-admin-btn"
            onClick={() => void loadAccounts()}
            disabled={loading}
          >
            새로고침
          </button>
        </div>
        <p className="napda-admin-sub" style={{ marginTop: 0, marginBottom: 12 }}>
          등록한 이메일로 로그인하면 보유 크레딧이 0이어도 크레딧 차감 및 일일 한도 제한 없이 바로 영상을 생성·테스트할 수 있습니다. (로그인 전 이메일도 사전 등록 가능)
        </p>
        <form
          onSubmit={(e) => void handleAddInternal(e)}
          style={{ display: 'flex', flexWrap: 'wrap', gap: 8, alignItems: 'center' }}
        >
          <input
            className="napda-admin-input"
            type="email"
            placeholder="예: teammate@gmail.com"
            value={emailInput}
            onChange={(e) => setEmailInput(e.target.value)}
            style={{ flex: '1 1 240px', minWidth: 200 }}
            required
          />
          <input
            className="napda-admin-input"
            type="text"
            placeholder="메모 (선택, 예: A안 담당 / QA)"
            value={noteInput}
            onChange={(e) => setNoteInput(e.target.value)}
            style={{ flex: '1 1 180px', minWidth: 160 }}
          />
          <button
            type="submit"
            className="napda-admin-btn is-active"
            disabled={busyKey === 'add'}
          >
            {busyKey === 'add' ? '저장 중...' : '내부 계정 등록'}
          </button>
        </form>
      </section>

      <section className="napda-admin-card">
        <div className="napda-admin-card-head">
          <h2 className="napda-admin-card-title">계정 목록</h2>
          <span className="napda-admin-sub" style={{ margin: 0 }}>
            R2 스냅샷에 저장되어 서버 재시작 후에도 유지됩니다
          </span>
        </div>
        <div className="napda-admin-table-wrap">
          <table className="napda-admin-table">
            <thead>
              <tr>
                <th>이메일</th>
                <th>이름</th>
                <th>구분</th>
                <th className="num">보유 크레딧</th>
                <th className="num">오늘 생성</th>
                <th className="num">프로젝트</th>
                <th>메모</th>
                <th>최근 로그인</th>
                <th>관리</th>
              </tr>
            </thead>
            <tbody>
              {loading && accounts.length === 0 ? (
                <tr>
                  <td colSpan={9}>불러오는 중...</td>
                </tr>
              ) : accounts.length === 0 ? (
                <tr>
                  <td colSpan={9}>등록되거나 로그인한 계정이 아직 없습니다.</td>
                </tr>
              ) : (
                accounts.map((row) => {
                  const key = row.email.trim().toLowerCase();
                  const isBusy = busyKey === key;
                  const isEnvOnly = row.internal_source === 'env';
                  return (
                    <tr key={key}>
                      <td className="napda-admin-mono">{row.email}</td>
                      <td>{row.name || (row.has_logged_in ? '-' : '미로그인(사전등록)')}</td>
                      <td>
                        {row.is_internal ? (
                          <span className="napda-admin-badge is-inworld">
                            내부 테스트{isEnvOnly ? ' (env)' : ''}
                          </span>
                        ) : (
                          <span className="napda-admin-badge">일반 사용자</span>
                        )}
                      </td>
                      <td className="num">
                        {row.is_internal ? '무제한 (면제)' : row.credits.toLocaleString()}
                      </td>
                      <td className="num">{row.renders_today}회</td>
                      <td className="num">{row.project_count}개</td>
                      <td>{row.note || '-'}</td>
                      <td>
                        {row.last_login_at
                          ? new Date(row.last_login_at).toLocaleString('ko-KR')
                          : '-'}
                      </td>
                      <td>
                        {isEnvOnly ? (
                          <span className="napda-admin-sub" style={{ margin: 0 }}>
                            환경변수 고정
                          </span>
                        ) : (
                          <button
                            type="button"
                            className={`napda-admin-btn${row.is_internal ? '' : ' is-active'}`}
                            disabled={isBusy}
                            onClick={() => void handleToggleInternal(row)}
                          >
                            {isBusy
                              ? '처리 중...'
                              : row.is_internal
                                ? '내부 지정 해제'
                                : '내부 계정 지정'}
                          </button>
                        )}
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </section>
    </>
  );
}
