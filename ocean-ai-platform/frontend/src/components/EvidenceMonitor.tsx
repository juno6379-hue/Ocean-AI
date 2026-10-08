import { useEffect, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { CalendarDays, FileCheck2, ClipboardList, Wrench, BookOpen, AlertCircle, ChevronRight } from 'lucide-react';
import { API_BASE_URL, apiFetch } from '../api/client';

const shown = (v: number | null | undefined) => v == null ? '미확정' : v.toLocaleString('ko-KR');
const kinds: Record<string,string> = {DAILY_SITUATION_REPORT:'일일 상황보고', DAILY_INSPECTION_REPORT:'일일 점검보고'};
const card = 'bg-white border border-blue-100 rounded-2xl p-5 shadow-sm';

/** Published documents are counted by document ID, not chunk count or expected submissions. */
export default function EvidenceMonitor({monitor, from, to}: {monitor:any; from:string; to:string}) {
  const {search}=useLocation();
  const context=new URLSearchParams();
  const current=new URLSearchParams(search);
  for(const key of ['source','from','to','network','sea']){const value=current.get(key);if(value)context.set(key,value);}
  const contextQuery=context.size?`?${context}`:'';
  const [day, setDay] = useState('');
  const [data, setData] = useState<any>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  useEffect(()=>{setDay('');},[from,to]);
  useEffect(()=>{
    const control = new AbortController();
    setData(null);setError('');setLoading(true);
    const query = new URLSearchParams({from_month:from,to_month:to});
    if(day)query.set('day',day);
    if(from>to){setLoading(false);return;}
    apiFetch(`${API_BASE_URL}/lake/daily-reports?${query}`,{signal:control.signal})
      .then(async r=>{if(!r.ok)throw new Error(`일일 보고 조회 실패 (HTTP ${r.status})`);return r.json();})
      .then(d=>{if(!control.signal.aborted)setData(d);})
      .catch(e=>{if(!control.signal.aborted)setError(e.message);})
      .finally(()=>{if(!control.signal.aborted)setLoading(false);});
    return()=>control.abort();
  },[from,to,day]);
  const docs=monitor?.documents;
  const extraction=docs?.extraction;
  return <div className="space-y-5">
    <section className={card} aria-label="일일 보고현황">
      <div className="flex flex-wrap justify-between items-center gap-3 mb-4">
        <div><h3 className="font-bold text-slate-900 flex items-center gap-2"><CalendarDays className="text-blue-600 w-5 h-5"/>일일 보고현황</h3><p className="text-xs text-slate-500 mt-1">일일 상황·점검 보고서 · 전체 게시 색인 기준 · 선택 원천과 별도</p></div>
        <div className="flex items-center gap-2 text-xs"><label>보고 기준일 <input aria-label="보고 기준일" type="date" value={day || data?.selected_day || ''} min={`${from}-01`} max={`${to}-${new Date(Number(to.slice(0,4)),Number(to.slice(5,7)),0).getDate()}`} onChange={e=>setDay(e.target.value)} className="ml-2 border border-blue-100 p-2 rounded-lg"/></label><button onClick={()=>setDay('')} className="border border-blue-100 p-2 rounded-lg text-blue-700">최근 보유일</button></div>
      </div>
      {loading && <p role="status" className="text-sm text-blue-600">보고서 등록 현황 조회 중…</p>}
      {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
      {data && <>
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-4">{[
          ['기준일 보유 보고서',`${shown(data.selected_day_documents)}건`],
          ['일일 상황보고',`${shown(data.by_type.DAILY_SITUATION_REPORT || 0)}건`],
          ['일일 점검보고',`${shown(data.by_type.DAILY_INSPECTION_REPORT || 0)}건`],
          ['제출률 · 미제출','대상·기한 미확정'],
        ].map(([label,value])=><div key={label} className="rounded-xl bg-blue-50/60 p-3"><p className="text-xs text-slate-500">{label}</p><p className="mt-1 font-bold text-slate-900">{value}</p></div>)}</div>
        <p className="text-xs text-slate-500 mb-3">{data.selected_day || '날짜 미확정'} 기준 · 선택 기간 내 {shown(data.period_documents)}개 문서 · 날짜 미확정 {shown(data.unresolved_date_documents_all_periods)}개는 전체 색인 별도 집계. 최신 보유일은 오늘의 제출 완료를 뜻하지 않습니다.</p>
        <div className="overflow-x-auto max-h-96"><table className="w-full text-xs text-left min-w-[620px]"><thead className="bg-slate-50 text-slate-500"><tr>{['보고서','구분','관련 관측소','확인 상태','근거'].map(h=><th className="p-3" key={h}>{h}</th>)}</tr></thead><tbody>{data.documents.map((r:any)=><tr className="border-b border-slate-100 align-top" key={r.document_id}><td className="p-3 font-medium max-w-xs">{r.title}</td><td className="p-3 whitespace-nowrap">{kinds[r.document_type] || r.document_type}</td><td className="p-3 max-w-48 break-words">{r.stations.slice(0,5).join(', ') || '미연결'}{r.stations.length>5 && ` 외 ${r.stations.length-5}개`}</td><td className="p-3 whitespace-nowrap text-amber-700">원문 추출 · 미승인</td><td className="p-3"><details><summary className="text-blue-700 cursor-pointer">발췌 보기</summary><div className="mt-2 max-w-md whitespace-pre-wrap text-slate-600"><p>{r.citation?.page ? `${r.citation.page}쪽` : r.citation?.locator || '쪽/위치 미확정'} · {r.citation?.section}</p><p className="my-2">{r.citation?.excerpt || '발췌 미확인'}</p><p className="text-[10px]">문서 날짜 근거: {r.citation?.date_source}<br/>이 발췌는 대표 청크이며 보고서 전체나 승인된 이상·조치 요약이 아닙니다.</p></div></details></td></tr>)}</tbody></table></div>
        {!data.documents.length && <p className="p-4 text-sm text-slate-500">기준일에 게시된 보고서가 없습니다. 미제출 여부는 판정하지 않았습니다.</p>}
        <p className="mt-3 text-xs text-slate-500">{data.note} · 최대 {data.returned_limit}개 표시</p>
      </>}
    </section>
    <section className={card} aria-label="비정형 운영자료 모니터링">
      <div className="flex flex-wrap items-center justify-between gap-3 mb-4"><div><h3 className="font-bold flex items-center gap-2"><ClipboardList className="w-5 h-5 text-blue-600"/>비정형 운영자료 모니터링</h3><p className="text-xs text-slate-500 mt-1">이력집 · 점검기록 · 설치/교체 이력 · 용역보고서 · QC 근거</p></div><Link className="text-xs text-blue-700 flex items-center" to={`/data-lake${contextQuery}`}>자료 검증 현황<ChevronRight className="w-4 h-4"/></Link></div>
      {!docs ? <p className="text-sm text-slate-500">운영자료 상태 조회 미완료</p> : <>
        <div className="grid grid-cols-2 lg:grid-cols-6 gap-3">{[
          ['이력집',docs.history_documents,BookOpen],['점검 행 후보',docs.inspection_candidates,ClipboardList],
          ['설치 이력 후보',docs.installation_candidates,Wrench],['정비 사건 후보',docs.maintenance_candidates,Wrench],
          ['관리기록 충돌',docs.management_conflicts,AlertCircle],['텍스트 추출 완료',extraction?.counts?.TEXT_EXTRACTED_UNREVIEWED,FileCheck2],
        ].map(([label,value,Icon]:any)=><div key={label} className="rounded-xl border border-slate-100 p-3"><Icon className="w-5 h-5 text-blue-500 mb-2"/><p className="text-xs text-slate-500">{label}</p><p className="font-bold text-lg mt-1">{shown(value)}</p></div>)}</div>
        <div className="flex flex-wrap gap-3 mt-4 text-xs text-slate-600"><span>추출 처리 {shown(extraction?.completed)}/{shown(extraction?.total)}</span><span>추출 실패 {shown(extraction?.counts?.EXTRACTION_FAILED)}</span><span>OCR 필요 {shown(extraction?.counts?.NO_TEXT_OCR_NEEDED)}</span><span>Office 잠금파일 제외 {shown(extraction?.counts?.OFFICE_LOCK_FILE_NOT_EVIDENCE)}</span></div>
        <p className="mt-3 text-[11px] text-slate-500">{docs.scope}. 후보 건수는 고유 장애·확정 센서 수가 아닙니다. 문서 추출 완료와 근거 검토·Embedding 완료는 별도입니다.</p>
      </>}
    </section>
  </div>;
}
