import { useState } from 'react';
import { API_BASE_URL, apiFetch } from '../api/client';

type Fusion = {
  scope: { station_id: string; sensor_id: string; variable_code: string; unit: string; period_start: string; period_end: string };
  recommendation_score?: number | null;
  anomaly_support: number;
  normal_support: number;
  coverage_weight: number;
  recommendation: string;
  missing_categories: string[];
  conflicts: unknown[];
};
type Workflow = {
  workflow_id: string;
  status: string;
  revision: number;
  recommendation_sha256: string;
  recommendation: Fusion;
  result: { report_draft?: { status: string; text: string }; mlops?: { status?: string } } | null;
};
type Actor = { user_id: string; role: string };
const percentage = (value: number | null | undefined) => value == null ? '미평가' : `${(value * 100).toFixed(1)} / 100`;

async function request<T>(path: string, body?: unknown): Promise<T> {
  const response = await apiFetch(`${API_BASE_URL}/agents${path}`, body === undefined ? undefined : {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  });
  const data = await response.json();
  if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : `요청 실패 (${response.status}): ${JSON.stringify(data.detail)}`);
  return data;
}

export default function WorkflowReviewPanel() {
  const [station, setStation] = useState('');
  const [sensor, setSensor] = useState('');
  const [variable, setVariable] = useState('');
  const [unit, setUnit] = useState('');
  const [start, setStart] = useState('');
  const [end, setEnd] = useState('');
  const [query, setQuery] = useState('');
  const [workflowId, setWorkflowId] = useState('');
  const [workflow, setWorkflow] = useState<Workflow | null>(null);
  const [fusion, setFusion] = useState<Fusion | null>(null);
  const [actor, setActor] = useState<Actor | null>(null);
  const [comment, setComment] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const perform = async (action: () => Promise<void>) => {
    setBusy(true); setError('');
    try { await action(); } catch (e) { setError(e instanceof Error ? e.message : '요청 실패'); }
    finally { setBusy(false); }
  };
  const payload = () => {
    if (![station, sensor, variable, unit, start, end].every(x => x.trim())) throw new Error('관측소·센서·항목·단위와 시작·종료 시각을 입력하세요.');
    return { scope: { station_id: station.trim(), sensor_id: sensor.trim(), variable_code: variable.trim(), unit: unit.trim(),
      period_start: new Date(start).toISOString(), period_end: new Date(end).toISOString(), as_of: new Date().toISOString() }, query };
  };
  const setRun = (run: Workflow) => { setWorkflow(run); setWorkflowId(run.workflow_id); setFusion(run.recommendation); };
  const transition = async (action: 'decision' | 'resume' | 'cancel', decision?: string) => {
    if (!workflow) throw new Error('검토할 작업을 먼저 조회하세요.');
    const run = await request<Workflow>(`/workflows/${encodeURIComponent(workflow.workflow_id)}/${action}`, {
      request_key: crypto.randomUUID(), expected_recommendation_sha256: workflow.recommendation_sha256,
      expected_revision: workflow.revision, comment, ...(decision ? { decision } : {}),
    });
    setRun(run);
  };
  const canWrite = !!actor && ['operator', 'reviewer', 'admin'].includes(actor.role);
  const canReview = !!actor && ['reviewer', 'admin'].includes(actor.role);
  const inputClass = 'rounded border p-2 text-sm';

  return <section className="rounded-xl border bg-white p-5 shadow-sm" aria-label="근거 통합 및 승인 대기">
    <h2 className="text-lg font-semibold">근거 통합 · 승인 대기</h2>
    <p className="mt-2 text-sm text-slate-600">Rule·AI·장비·운영·문서 근거를 같은 센서와 기간에서 비교합니다. 점수는 근거의 지원 정도이며 오류 확률이 아닙니다. 승인 대기 중에는 보고서와 MLOps 단계가 실행되지 않습니다.</p>
    <div className="mt-4 grid gap-2 md:grid-cols-4">
      <input className={inputClass} aria-label="분석 관측소" placeholder="관측소 ID" value={station} onChange={e => setStation(e.target.value)} />
      <input className={inputClass} aria-label="분석 센서" placeholder="센서 ID" value={sensor} onChange={e => setSensor(e.target.value)} />
      <input className={inputClass} aria-label="분석 관측항목" placeholder="관측항목 코드" value={variable} onChange={e => setVariable(e.target.value)} />
      <input className={inputClass} aria-label="분석 단위" placeholder="확인된 단위" value={unit} onChange={e => setUnit(e.target.value)} />
      <label className="text-xs">시작 (현지 시각)<input className={`${inputClass} block w-full`} type="datetime-local" value={start} onChange={e => setStart(e.target.value)} /></label>
      <label className="text-xs">종료 (현지 시각)<input className={`${inputClass} block w-full`} type="datetime-local" value={end} onChange={e => setEnd(e.target.value)} /></label>
      <input className={`${inputClass} md:col-span-2`} aria-label="관련 문서 검색" placeholder="관련 문서 검색어 (선택)" value={query} onChange={e => setQuery(e.target.value)} />
    </div>
    <div className="mt-3 flex flex-wrap gap-2">
      <button disabled={busy} className="rounded bg-blue-700 px-3 py-2 text-sm text-white disabled:opacity-50" onClick={() => perform(async () => { setFusion(null); setWorkflow(null); setFusion(await request<Fusion>('/evidence/analyze', payload())); })}>근거 분석</button>
      <button disabled={busy || !canWrite} className="rounded border px-3 py-2 text-sm disabled:opacity-50" onClick={() => perform(async () => setRun(await request<Workflow>('/workflows', { ...payload(), request_key: crypto.randomUUID() })))}>승인 대기 작업 생성</button>
      <button disabled={busy} className="rounded border px-3 py-2 text-sm" onClick={() => perform(async () => {
        const response = await apiFetch(`${API_BASE_URL}/session`);
        if (!response.ok) { setActor(null); throw new Error(response.status === 503 ? '승인 계정은 이후 운영 단계에서 설정합니다. 근거 분석·조회는 계속 사용할 수 있습니다.' : '상단 담당자 연결을 확인하세요.'); }
        setActor(await response.json());
      })}>담당자 연결 확인</button>
      {actor && <span className="self-center text-sm">{actor.user_id} ({actor.role})</span>}
    </div>
    <div className="mt-3 flex flex-wrap gap-2">
      <input className={`${inputClass} min-w-64 flex-1`} aria-label="기존 검토 작업 ID" placeholder="기존 검토 작업 ID" value={workflowId} onChange={e => setWorkflowId(e.target.value)} />
      <button disabled={busy || !workflowId.trim()} className="rounded border px-3 py-2 text-sm disabled:opacity-50" onClick={() => perform(async () => setRun(await request<Workflow>(`/workflows/${encodeURIComponent(workflowId.trim())}`)))}>작업 조회</button>
    </div>
    {fusion && <div className="mt-4 rounded bg-slate-50 p-3 text-sm">
      <div>분석 대상: {fusion.scope.station_id} · {fusion.scope.sensor_id} · {fusion.scope.variable_code} ({fusion.scope.unit})</div>
      <div className="mb-2 text-xs text-slate-600">{fusion.scope.period_start} ~ {fusion.scope.period_end}</div>
      <div>추천 점수: <strong>{percentage(fusion.recommendation_score)}</strong> · 평가된 근거 비중: {percentage(fusion.coverage_weight)}</div>
      <div>분석 결과: {fusion.recommendation} · 정상 지원: {percentage(fusion.normal_support)}</div>
      <div>누락 근거: {fusion.missing_categories.join(', ') || '없음'} · 충돌: {fusion.conflicts.length}건</div>
    </div>}
    {workflow && <div className="mt-4 rounded border p-3 text-sm">
      <div>승인 대상: {workflow.recommendation.scope.station_id} · {workflow.recommendation.scope.sensor_id} · {workflow.recommendation.scope.variable_code} ({workflow.recommendation.scope.unit})</div>
      <div className="text-xs text-slate-600">{workflow.recommendation.scope.period_start} ~ {workflow.recommendation.scope.period_end}</div>
      <div>작업 상태: <strong>{workflow.status}</strong> · {workflow.result ? '승인 후 초안 단계' : '후속 단계 미실행'}</div>
      <textarea aria-label="검토 의견" className={`${inputClass} mt-2 w-full`} placeholder="검토 의견" value={comment} onChange={e => setComment(e.target.value)} />
      <div className="mt-2 flex flex-wrap gap-2">
        <button disabled={busy || !canReview || workflow.status !== 'PENDING'} className="rounded border px-3 py-2 disabled:opacity-50" onClick={() => perform(() => transition('decision', 'APPROVED'))}>추천 승인</button>
        <button disabled={busy || !canReview || workflow.status !== 'PENDING'} className="rounded border px-3 py-2 disabled:opacity-50" onClick={() => perform(() => transition('decision', 'REJECTED'))}>반려</button>
        <button disabled={busy || !canWrite || workflow.status !== 'APPROVED'} className="rounded bg-green-700 px-3 py-2 text-white disabled:opacity-50" onClick={() => perform(() => transition('resume'))}>승인 후 재개</button>
        <button disabled={busy || !canWrite || !['PENDING', 'APPROVED'].includes(workflow.status)} className="rounded border px-3 py-2 disabled:opacity-50" onClick={() => perform(() => transition('cancel'))}>취소</button>
      </div>
      {workflow.result?.report_draft && <pre className="mt-3 whitespace-pre-wrap">{workflow.result.report_draft.text}</pre>}
      <p className="mt-2 text-xs text-slate-600">추천 승인은 원천·최종 QC·학습·배포 승인과 별개입니다. 재개 결과는 보고서 초안과 MLOps 추천이며 실제 학습·배포를 실행하지 않습니다.</p>
    </div>}
    {error && <p role="alert" className="mt-3 text-sm text-red-700">{error}</p>}
  </section>;
}
