// 파일 역할: 작업자 인증 세션과 권한 상태를 표시합니다.
import { useEffect, useState } from 'react';
import { API_BASE_URL, apiFetch, setOperatorToken, clearOperatorToken } from '../api/client';

export default function OperatorSession() {
  const [token, setToken] = useState('');
  const [user, setUser] = useState('');
  const [error, setError] = useState('');
  const [mode, setMode] = useState('연결 확인 중');
  useEffect(() => {
    apiFetch(`${API_BASE_URL}/runtime`).then(r => { if (!r.ok) throw new Error(); return r.json(); })
      .then(data => setMode(data.is_demo ? '데모 모드 · 예시 포함' : `저장자료 조회 · MDC 자동수집 ${data.mdc_sync_enabled ? '켜짐' : '꺼짐'} · 파일 레이크는 별도 검증`))
      .catch(() => setMode('서버 연결 확인 필요'));
  }, []);
  const connect = async () => {
    setOperatorToken(token);
    try {
      const response = await apiFetch(`${API_BASE_URL}/session`);
      if (!response.ok) throw new Error(response.status === 503 ? '서버에 담당자 인증 설정이 필요합니다.' : '토큰을 확인하세요.');
      const data = await response.json();
      setUser(`${data.user_id} (${data.role})`); setToken(''); setError('');
    } catch (e) {
      clearOperatorToken(); setUser(''); setError(e instanceof Error ? e.message : '연결 실패');
    }
  };
  return <div className="border-b bg-amber-50 px-4 py-2 text-xs text-slate-700">
    <div>검증용 플랫폼 · {mode} · 일부 화면의 정적 예시는 운영 판단에 사용하지 마세요.</div>
    <div className="mt-1 flex flex-wrap items-center gap-2">
      {user ? <><span>{user}</span><button onClick={() => { clearOperatorToken(); setUser(''); }}>연결 해제</button></> : <>
        <input aria-label="담당자 접근 토큰" type="password" autoComplete="off" value={token} onChange={e => setToken(e.target.value)} placeholder="담당자 접근 토큰" className="rounded border px-2 py-1" />
        <button disabled={!token.trim()} onClick={connect} className="rounded bg-slate-700 px-2 py-1 text-white disabled:opacity-50">담당자 연결</button>
        <span>조회는 가능하며 변경·승인에는 담당자 연결이 필요합니다.</span>
      </>}
      {error && <span role="alert" className="text-red-700">{error}</span>}
    </div>
  </div>;
}
