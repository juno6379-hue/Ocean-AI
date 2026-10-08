import {useEffect, useRef, useState} from 'react';
import {experimentalReleaseValid, experimentalPredictionMatches, nativeValues, type ExperimentalRelease} from '../data/experimentalDeployment';

const BASE = '/experimental-api';
async function request(path: string, init?: RequestInit) {
  // This separate loopback service never receives the production operator token.
  const response = await fetch(`${BASE}${path}`, {...init, credentials: 'omit'});
  let body;
  try {body = await response.json();} catch {throw new Error('시험 서버에 연결되지 않았습니다. 서버 실행 상태를 확인하세요.');}
  if (!response.ok) {
    const code = body.detail?.code;
    if (code === 'SELECTED_RELEASE_OR_ARTIFACT_CHANGED') throw new Error('시험 배포가 변경됐습니다. 시험 서버를 다시 확인하세요.');
    if (code === 'NO_VALIDATED_DEVELOPMENT_RELEASE') throw new Error('현재 학습 모델을 검증하지 못해 시험 예측을 중단했습니다.');
    throw new Error(`시험 서버 요청을 처리하지 못했습니다 (${response.status}).`);
  }
  return body;
}
const metric = (value: number) => value.toLocaleString('ko-KR', {maximumSignificantDigits: 6});
export default function ExperimentalDeploymentPanel() {
  const [release, setRelease] = useState<ExperimentalRelease|null>(null);
  const [selected, setSelected] = useState(''), [valuesText, setValuesText] = useState('');
  const [result, setResult] = useState<number|null>(null), [error, setError] = useState('');
  const [loading, setLoading] = useState(true), [busy, setBusy] = useState(false), [revision, setRevision] = useState(0);
  const version = useRef(0);
  useEffect(() => {
    const control = new AbortController(); const current = ++version.current;
    setLoading(true); setRelease(null); setResult(null); setError('');
    Promise.all([request('/readiness', {signal: control.signal}), request('/release', {signal: control.signal})]).then(([ready, data]) => {
      if (control.signal.aborted || current !== version.current) return;
      if (ready.status !== 'READY' || ready.release_id !== data.release_id || ready.model_count !== data.models?.length || !experimentalReleaseValid(data))
        throw new Error('시험 배포의 실행·모델 근거가 아직 검증되지 않았습니다.');
      setRelease(data); setSelected(data.models[0].model_id); setValuesText(data.models[0].last_values.join(', '));
    }).catch(reason => {if (!control.signal.aborted && current === version.current) setError(reason instanceof Error ? reason.message : '시험 서버 조회 실패');})
      .finally(() => {if (!control.signal.aborted && current === version.current) setLoading(false);});
    return () => {control.abort(); version.current++;};
  }, [revision]);
  const model = release?.models.find(row => row.model_id === selected);
  const values = nativeValues(valuesText);
  const changeModel = (id: string) => {version.current++; setSelected(id); setValuesText(release?.models.find(row => row.model_id === id)?.last_values.join(', ') || ''); setResult(null); setError('');};
  const predict = async () => {
    if (!release || !model || !values) return;
    const current = version.current; setBusy(true); setResult(null); setError('');
    try {
      const body = await request('/predict', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({model_id:model.model_id, values,
        expected_release_id:release.release_id, expected_artifact_sha256:model.artifact_sha256})});
      if (current !== version.current) return;
      if (!experimentalPredictionMatches(body, release, model, values)) throw new Error('예측 응답과 선택한 모델·입력 근거가 일치하지 않습니다.');
      setResult(body.prediction);
    } catch (reason) {if (current === version.current) setError(reason instanceof Error ? reason.message : '시험 예측 실패');}
    finally {setBusy(false);}
  };
  return <section aria-label="개발용 학습·시험 배포" className="rounded-xl border border-teal-200 bg-white p-4 space-y-3 text-sm">
    <div className="flex justify-between gap-3"><h3 className="font-bold">개발용 학습 · 로컬 시험 배포</h3><button disabled={busy || loading} className="text-teal-700 disabled:text-slate-400" onClick={()=>setRevision(v=>v+1)}>시험 서버 다시 확인</button></div>
    <p className="text-xs text-slate-600">실제 2026년 7월 인천 GR_OBS_ST 원시 숫자로 학습한 다음 행 예측입니다. 단위·시간대·물리 센서·QC는 미확정이며, 아래 모델은 운영 등록부와 별도입니다.</p>
    <p className="text-xs">{loading?'시험 배포 조회 중…':release?`시험 예측 서버 연결됨 · ${release.models.length}개 모델 · 원천 ${release.source_table} / ${release.source_period}`:'시험 배포 연결 미확인'}</p>
    {error && <p role="alert" className="text-red-700">{error}</p>}
    {release && <><div className="overflow-x-auto"><table className="w-full min-w-[680px] text-xs"><thead><tr>{['원문 항목','선정 후보','TRAIN / VALIDATION / TEST 행','VALIDATION MAE','TEST MAE / RMSE'].map(label=><th key={label} className="p-2 text-left">{label}</th>)}</tr></thead><tbody>{release.models.map(row=><tr key={row.model_id} className="border-t"><td className="p-2">{row.variable_code}</td><td className="p-2">{row.selected_model}</td><td className="p-2">{['TRAIN','VALIDATION','TEST'].map(split=>row.split_counts[split].toLocaleString()).join(' / ')}</td><td className="p-2">{metric(row.validation_metrics[row.selected_model].mae)}</td><td className="p-2">{metric(row.test_metrics[row.selected_model].mae)} / {metric(row.test_metrics[row.selected_model].rmse)}</td></tr>)}</tbody></table></div>
      <p className="text-xs text-slate-500">TRAIN 적합 · VALIDATION 선정 · TEST 평가. MAE/RMSE는 원시 숫자 오차이며 물리 단위·장비 고장 정확도·업무 수용률이 아닙니다.</p>
      <div className="flex flex-wrap items-end gap-2"><label className="text-xs">시험 예측 항목<select aria-label="시험 예측 항목" className="block rounded border p-2 mt-1" disabled={busy} value={selected} onChange={e=>changeModel(e.target.value)}>{release.models.map(row=><option key={row.model_id} value={row.model_id}>{row.variable_code}</option>)}</select></label>
        <label className="text-xs flex-1 min-w-64">최근 3개 원시 값 · 오래된 값부터<input aria-label="시험 예측 원시 값" disabled={busy} className="block w-full rounded border p-2 mt-1" value={valuesText} onChange={e=>{version.current++;setValuesText(e.target.value);setResult(null);}}/></label>
        <button disabled={busy || !values || !model || loading} onClick={predict} className="rounded bg-teal-700 px-3 py-2 text-white disabled:bg-slate-200 disabled:text-slate-500">{busy?'예측 중…':'시험 서버에서 예측'}</button></div>
      {result !== null && <p role="status" className="rounded bg-teal-50 p-3 font-medium">다음 원시 행 예측값: {metric(result)} · 예측 시각·물리 단위 미확정</p>}
      {model && <details className="text-xs"><summary className="cursor-pointer">학습·배포 근거와 후보 비교</summary><p className="mt-2 break-all">Release {release.release_id}<br/>모델 SHA {model.artifact_sha256}<br/>원천 참여 SHA {model.source_membership_sha256}</p><p className="mt-2">기본 입력의 원문 시각: {model.last_native_times.join(' → ')}</p><table className="mt-2 w-full"><thead><tr><th className="text-left">후보</th><th className="text-left">VALIDATION MAE</th><th className="text-left">TEST MAE</th><th className="text-left">TEST 쌍 수</th></tr></thead><tbody>{Object.entries(model.test_metrics).map(([name,row])=><tr key={name}><td>{name}</td><td>{model.validation_metrics[name]?metric(model.validation_metrics[name].mae):'미확인'}</td><td>{metric(row.mae)}</td><td>{row.pair_count.toLocaleString()}</td></tr>)}</tbody></table></details>}
    </>}
  </section>;
}
