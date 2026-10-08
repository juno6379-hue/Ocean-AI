import { useEffect,useState } from 'react';
import { Link,useLocation } from 'react-router-dom';
import { API_BASE_URL,apiFetch } from '../api/client';
import { observationContext, observationPeriod } from '../data/observationPeriod';
const count=(value:unknown)=>typeof value==='number'&&Number.isFinite(value)?value.toLocaleString('ko-KR'):'미조회';

/** A shared source/period contract, with global model totals explicitly labelled. */
export default function WorkflowStatus(){
 const {search}=useLocation(),[data,setData]=useState<any>(null),[error,setError]=useState('');
 const current=new URLSearchParams(search),context=observationContext(current);
 const contextQuery=context.size?`?${context}`:'';
 useEffect(()=>{
  const abort=new AbortController(),s=new URLSearchParams(search);
  const {source,from,to}=observationPeriod(s);
  const q=new URLSearchParams({source,from_month:from,to_month:to,network:s.get('network')||'',sea:s.get('sea')||''});
  let busy=false;setData(null);setError('');
  async function refresh(){if(busy)return;busy=true;try{const r=await apiFetch(`${API_BASE_URL}/data-lake/foundation/workflow?${q}`,{signal:abort.signal});if(!r.ok)throw new Error(`HTTP ${r.status}`);const d=await r.json();if(!abort.signal.aborted){setData(d);setError('');}}catch(e){if(!abort.signal.aborted){setData(null);setError(`연결·진행 상태 조회 실패: ${String(e)}`);}}finally{busy=false;}}
  refresh();const t=setInterval(refresh,60000);return()=>{abort.abort();clearInterval(t);};
 },[search]);
 const labels:Record<string,string>={REVIEW_REQUIRED:'검토 필요',NOT_EXECUTED:'미실행',NOT_ESTABLISHED:'평가 미확정',NOT_DEPLOYED:'미배포',RUNTIME_VALIDATION_REQUIRED:'운영 실증 필요'};
 return <details className="mx-4 mt-3 rounded-xl border border-blue-100 bg-white px-4 py-3 text-xs text-slate-600">
  <summary className="cursor-pointer font-medium text-blue-800">시설·데이터·AI 연결 상태 · {error?'조회 실패':data?`시설 기준일 ${data.as_of} / 운영 수 ${data.operating_facility_count==null?'미확정':count(data.operating_facility_count)}`:'조회 중'} · 2–8단계 보기</summary>
  {error?<p role="alert" className="mt-3 text-red-700">{error}</p>:data?<div className="mt-3 space-y-3">
   <p>선택 자료 {data.scope.source} · {data.scope.from} ~ {data.scope.to} · 관측망 {data.scope.network||'전체'} · 해역 {data.scope.sea||'전체'}</p>
   {data.coverage_supported?<p>자료 보유 코드 {count(data.channels.stations)}개 · 채널/월 {count(data.channels.channels)}행<br/>물리 센서 연결 {count(data.channels.physical_sensor_linked)}행 · 양쪽 경계 확정 {count(data.channels.bounded_intervals)}행 · 관측간격 확정 {count(data.channels.nominal_interval_known)}행<br/>0행은 선택 범위에 등록된 연결 근거가 없는 상태입니다. 관측시설 중단 여부는 별도 확인이 필요합니다.</p>:<p>과거 CSV는 이 시설 연결본의 채널 집계 대상에 아직 포함되지 않았습니다. 과거 자료 자체가 없다는 뜻은 아닙니다.</p>}
   <p>연결본 전체: 문서–시설 연결 후보 {count(data.registry_counts.document_link)}건 · 게시 당시 SQL/Vector ID 대조 문서 {count(data.verified_vector_documents)}건. 선택 관측기간의 승인 건수와는 별도입니다.</p>
   <div className="grid md:grid-cols-2 xl:grid-cols-4 gap-2">{data.stages.map((s:any)=><Link key={s.stage} to={`${s.href}${contextQuery}`} className="rounded-lg border p-3 hover:border-blue-400 focus-visible:ring-2 focus-visible:ring-blue-500"><strong>{s.stage}. {s.name}</strong><p className={`mt-1 ${s.count!=null&&['REVIEW_REQUIRED','RUNTIME_VALIDATION_REQUIRED'].includes(s.state)?'text-amber-700':'text-slate-500'}`}>{s.count==null?'건수 미조회 · 상태 확인 필요':labels[s.state]||s.state}</p><p>{count(s.count)} {s.unit}</p><ul className="mt-2 list-disc pl-4 text-[11px]">{s.blockers.map((b:string)=><li key={b}>{b}</li>)}</ul></Link>)}</div>
   <p className="rounded bg-amber-50 p-2 text-amber-900">품질검사·AI 이상 탐지·예측은 별도 업무입니다. 가이드 전체 항목과 HF-radar 세부 규칙·모델 비교·운영 검증은 아직 완료되지 않았습니다.</p>
   <p className="text-[11px] text-slate-500">{data.note}<br/>검증본 {data.snapshot} · 연결본 {data.run_id} · 조회 확인 {new Date(data.checked_at).toLocaleString('ko-KR')} · 1분마다 갱신. 조회 시각은 원천자료 갱신 시각과 다릅니다.</p>
  </div>:null}
 </details>;
}
