import {useEffect,useState} from 'react';
import {API_BASE_URL,apiFetch} from '../api/client';
import {validStageReview,type Stage} from '../data/developmentReview';
const labels:Record<string,string>={IMPLEMENTED:'구현됨',PARTIAL:'부분 완료',UNKNOWN:'미확인',VERIFIED:'검증됨',FAILED:'검증 실패',
  READY:'준비됨',BLOCKED:'근거 부족·차단',APPROVED:'승인됨',PENDING:'승인 대기',NOT_APPLICABLE:'해당 없음',
  OPERATING:'운영 확인',ANALYSIS_ONLY:'개발 분석만',NOT_STARTED:'미착수'};
export default function DevelopmentStageReview(){
  const [data,setData]=useState<{checked_at:string;stages:Stage[]}|null>(null),[error,setError]=useState(''),[revision,setRevision]=useState(0);
  useEffect(()=>{const control=new AbortController();setData(null);setError('');
    apiFetch(`${API_BASE_URL}/development-stages/review`,{signal:control.signal}).then(async r=>{if(!r.ok)throw new Error(`HTTP ${r.status}`);return r.json();})
    .then(value=>{if(!validStageReview(value))throw new Error('단계별 검토 응답 형식 미확인');if(!control.signal.aborted)setData(value);})
    .catch(reason=>{if(!control.signal.aborted)setError(`단계 검토 조회 실패: ${reason.message}`);});
    return()=>control.abort();},[revision]);
  return <section className="rounded-xl border border-slate-200 bg-white p-4 mb-5" aria-label="개발 단계별 근거 검토">
    <div className="flex justify-between gap-2"><h2 className="font-bold">개발 단계별 근거 검토</h2><button className="text-sm text-blue-700" onClick={()=>setRevision(v=>v+1)}>다시 확인</button></div>
    <p className="text-xs text-slate-600 mt-2">구현·시험·원천 자료·승인·운영을 각각 확인합니다. 기술 검토가 원천 또는 모델의 운영 승인을 대신하지 않습니다.</p>
    {error?<p role="alert" className="text-sm text-red-700 mt-3">{error}</p>:!data?<p role="status" className="text-sm mt-3">검토 근거 조회 중…</p>:<>
    <p className="text-xs text-slate-500 mt-2">확인 {data.checked_at}</p><div className="overflow-auto mt-3"><table className="min-w-[820px] w-full text-xs text-left"><thead><tr>{['단계','구현','시험','자료 준비','승인','운영'].map(label=><th className="p-2" key={label}>{label}</th>)}</tr></thead><tbody>{data.stages.map(stage=><tr className="border-t align-top" key={stage.stage_id}><td className="p-2"><details><summary className="font-semibold cursor-pointer">{stage.stage_id}. {stage.title}</summary><div className="max-w-lg mt-2 space-y-2">{stage.reasons?.map((reason,i)=><p key={i}>{reason}</p>)}<p className="font-semibold">남은 입력·조치</p>{stage.next_required.map((next,i)=><p key={i}>{next}</p>)}<details><summary className="cursor-pointer">검증 근거 {stage.evidence.length}개</summary>{stage.evidence.map((e,i)=><p className="break-all mt-2 text-slate-500" key={i}>{e.verified?'해시 확인':'확인되지 않음'} · {e.error||e.path}<br/>{e.sha256}</p>)}</details></div></details></td>{[stage.implementation,stage.verification,stage.data_readiness,stage.approval,stage.operational_status].map((state,i)=><td className={`p-2 ${['IMPLEMENTED','VERIFIED','READY','APPROVED','OPERATING'].includes(state)?'text-blue-800':'text-slate-600'}`} key={i}>{labels[state]||state}</td>)}</tr>)}</tbody></table></div></>}
  </section>;
}
