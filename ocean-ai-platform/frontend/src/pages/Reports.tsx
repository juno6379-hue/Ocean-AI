import { API_BASE_URL, apiClient } from '../api/client';
import { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { FileText, CheckCircle, Clock, Sparkles, Search, Download, Eye, ArrowRight, RefreshCw } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

const TYPES: Record<string, string> = {weekly:'주간 요약', monthly:'월간 품질', anomaly:'이상 분석', special:'특별 분석', daily:'일일 점검', quality:'품질 검증', technical:'기술문서', publication:'간행물'};
const STATES: Record<string, string> = {DRAFT:'초안', REVIEW:'검토 대기', APPROVED:'승인 완료', PUBLISHED:'게시 완료', REJECTED:'반려'};
const typeLabel = (value: string | null) => value ? TYPES[value.toLowerCase()] || value : '유형 미등록';
const stateLabel = (value: string | null) => value ? STATES[value] || value : '상태 미확정';
const dateLabel = (value: string | null) => value ? value.replace('T',' ').slice(0,16) : '미등록';
const stateColor = (value: string) => ['APPROVED','PUBLISHED'].includes(value) ? 'text-emerald-700 bg-emerald-50 border-emerald-200' : value === 'REJECTED' ? 'text-red-700 bg-red-50 border-red-200' : value === 'REVIEW' ? 'text-amber-800 bg-amber-50 border-amber-200' : 'text-slate-600 bg-slate-50 border-slate-200';
type Report = {report_id:string; report_title:string|null; report_type:string|null; status:string; summary:string|null; created_at:string|null; updated_at:string|null; period_start:string|null; period_end:string|null; created_by:string|null; reviewed_by:string|null; approved_by:string|null};

export default function Reports() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [reports,setReports] = useState<Report[]>([]);
  const [loading,setLoading] = useState(true);
  const [error,setError] = useState('');
  const [revision,setRevision] = useState(0);
  const [filterType,setFilterType] = useState('');
  const [filterState,setFilterState] = useState('');
  const [filterMonth,setFilterMonth] = useState('');
  const [query,setQuery] = useState('');
  const [comment,setComment] = useState('');
  const [actionMessage,setActionMessage] = useState('');
  const [acting,setActing] = useState(false);
  const selectedId = searchParams.get('report');
  const selected = reports.find(r => r.report_id === selectedId);
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true); setError(''); setReports([]);
    apiClient.get(`${API_BASE_URL}/reports`, {signal:controller.signal}).then(res => {
      if(!controller.signal.aborted) setReports(res.data.reports);
    }).catch(() => {if(!controller.signal.aborted) setError('보고서 등록부 조회 실패 · 0건으로 판정하지 않습니다.');})
      .finally(() => {if(!controller.signal.aborted) setLoading(false);});
    return () => controller.abort();
  },[revision]);
  const filtered = reports.filter(r => (!filterType || r.report_type === filterType) && (!filterState || r.status === filterState) && (!filterMonth || r.created_at?.startsWith(filterMonth)) && `${r.report_title || ''} ${r.created_by || ''} ${r.report_id}`.toLowerCase().includes(query.toLowerCase()));
  const select = (id:string) => {setSearchParams({...Object.fromEntries(searchParams),report:id});setComment('');setActionMessage('');};
  const count = (predicate:(r:Report)=>boolean) => loading || error ? '—' : reports.filter(predicate).length;
  const drafts = reports.filter(r => r.status === 'DRAFT');
  const reviews = reports.filter(r => r.status === 'REVIEW');
  const types = [...new Set(reports.map(r => r.report_type).filter((r):r is string => !!r))].sort();
  const reset = () => {setFilterType('');setFilterState('');setFilterMonth('');setQuery('');};
  const exportList = () => {
    const url = URL.createObjectURL(new Blob([JSON.stringify(filtered,null,2)],{type:'application/json;charset=utf-8'}));
    const link = document.createElement('a');link.href=url;link.download='report-registry.json';link.click();URL.revokeObjectURL(url);
  };
  const transition = async (action:'review'|'approve'|'reject') => {
    if(!selected || acting) return;
    if(action !== 'review' && !window.confirm(`${selected.report_title || selected.report_id}: ${action === 'approve' ? '승인' : '반려'} 기록을 남기시겠습니까?`)) return;
    setActing(true);setActionMessage('');
    try {
      await apiClient.post(`${API_BASE_URL}/reports/${encodeURIComponent(selected.report_id)}/${action}`, action === 'review' ? undefined : {user_id:'',comment});
      setActionMessage('처리 완료 · 등록부를 다시 조회합니다.');setRevision(r=>r+1);
    } catch {setActionMessage('처리 실패 · 로그인한 검토 권한과 보고서 상태를 확인하세요.');}
    finally {setActing(false);}
  };
  const card = 'bg-white border border-slate-200 rounded-xl shadow-sm';
  const input = 'border border-slate-200 rounded-lg px-3 py-2 text-xs bg-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500';
  return <div className="p-4 md:p-6 space-y-5 bg-slate-50 min-h-full">
    <div className="flex flex-wrap justify-between items-end gap-3 border-b border-slate-200 pb-4">
      <div><h2 className="text-2xl font-bold text-slate-900">보고서 & 문서</h2><p className="text-sm text-slate-500 mt-1">등록된 보고서를 확인하고 초안 → 검토 → 승인 상태를 구분합니다.</p></div>
      <button onClick={()=>setRevision(r=>r+1)} className={`${input} flex items-center gap-2`}><RefreshCw size={14}/>새로고침</button>
    </div>
    <p className="text-xs text-slate-500">전체 보고서 등록부 · 공통 원천·관측기간 필터와 별도 · 원문 색인 문서 수와 다릅니다. 생성일과 보고 대상 기간을 구분합니다.</p>
    {error && <p role="alert" className="rounded-lg bg-red-50 border border-red-200 p-3 text-sm text-red-700">{error}</p>}
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
      {[{name:'등록 보고서',value:count(()=>true),icon:FileText,color:'text-blue-600 bg-blue-50'}, {name:'작성 초안',value:count(r=>r.status==='DRAFT'),icon:Sparkles,color:'text-slate-600 bg-slate-100'}, {name:'검토 대기',value:count(r=>r.status==='REVIEW'),icon:Clock,color:'text-amber-700 bg-amber-50'}, {name:'승인·게시',value:count(r=>['APPROVED','PUBLISHED'].includes(r.status)),icon:CheckCircle,color:'text-emerald-700 bg-emerald-50'}].map(c=><div key={c.name} className={`${card} p-4`}><div className="flex items-center gap-2 text-xs font-semibold text-slate-600"><span className={`p-2 rounded-lg ${c.color}`}><c.icon size={17}/></span>{c.name}</div><p className="text-2xl font-bold text-slate-900 mt-3">{c.value}<span className="text-xs font-normal text-slate-500 ml-2">건</span></p></div>)}
    </div>
    <div className={`${card} p-3 flex flex-wrap items-end gap-3`}>
      <label className="text-[11px] text-slate-500">제목·작성자·문서 ID<div className="relative mt-1"><Search size={14} className="absolute left-3 top-3 text-slate-400"/><input aria-label="보고서 검색" value={query} onChange={e=>setQuery(e.target.value)} placeholder="등록된 보고서 검색" className={`${input} pl-9`}/></div></label>
      <label className="text-[11px] text-slate-500">생성월<input aria-label="생성월" type="month" value={filterMonth} onChange={e=>setFilterMonth(e.target.value)} className={`${input} block mt-1`}/></label>
      <label className="text-[11px] text-slate-500">유형<select value={filterType} onChange={e=>setFilterType(e.target.value)} className={`${input} block mt-1`}><option value="">전체 유형</option>{types.map(t=><option key={t} value={t}>{typeLabel(t)}</option>)}</select></label>
      <label className="text-[11px] text-slate-500">검토 상태<select value={filterState} onChange={e=>setFilterState(e.target.value)} className={`${input} block mt-1`}><option value="">전체 상태</option>{Object.entries(STATES).map(([v,l])=><option key={v} value={v}>{l}</option>)}</select></label>
      <button className={`${input} text-blue-700`} onClick={reset}>필터 해제</button><button disabled={loading || !!error || !filtered.length} onClick={exportList} className={`${input} ml-auto flex items-center gap-2 text-blue-700 disabled:opacity-40`}><Download size={14}/>조회 목록 JSON</button>
    </div>
    <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
      <section className={`${card} xl:col-span-2 p-4 flex flex-col h-[490px]`} aria-label="보고서 목록">
        <div className="flex items-center justify-between mb-3"><h3 className="text-sm font-bold text-slate-800">문서 목록</h3><span aria-live="polite" className="text-xs text-slate-500">{loading ? '조회 중' : error ? '조회 실패' : `${filtered.length} / ${reports.length}건`}</span></div>
        <div className="overflow-auto flex-1"><table className="w-full min-w-[650px] text-xs text-left"><thead className="sticky top-0 bg-slate-50 text-slate-500"><tr>{['문서명 / ID','유형','보고 대상 기간','상태','생성일'].map(h=><th key={h} className="p-2.5 font-medium">{h}</th>)}</tr></thead><tbody className="divide-y divide-slate-100">{filtered.map(r=><tr key={r.report_id} className={selectedId===r.report_id?'bg-blue-50':'hover:bg-slate-50'}><td className="p-2.5"><button onClick={()=>select(r.report_id)} className="text-left text-blue-700 font-medium focus-visible:ring-2 focus-visible:ring-blue-500 rounded">{r.report_title || '제목 미등록'}<span className="block text-[10px] text-slate-500 mt-1">{r.report_id}</span></button></td><td className="p-2.5 whitespace-nowrap">{typeLabel(r.report_type)}</td><td className="p-2.5 text-slate-500">{r.period_start?.slice(0,10) || '미등록'} ~ {r.period_end?.slice(0,10) || '미등록'}</td><td className="p-2.5"><span className={`text-[10px] whitespace-nowrap rounded border px-2 py-0.5 ${stateColor(r.status)}`}>{stateLabel(r.status)}</span></td><td className="p-2.5 text-slate-500 whitespace-nowrap">{dateLabel(r.created_at)}</td></tr>)}{!filtered.length && <tr><td colSpan={5} className="text-center p-12 text-slate-500">{loading?'보고서를 조회하고 있습니다…':error?'조회 실패 · 새로고침해 주세요.':reports.length?'선택 조건에 해당하는 보고서가 없습니다.':'등록된 AI 보고서가 없습니다. 승인된 근거를 연결한 보고서 생성은 아직 미구현입니다.'}</td></tr>}</tbody></table></div>
        <p className="text-[10px] text-slate-500 border-t border-slate-100 pt-3 mt-2">날짜는 API 원문 기준 · 시간대 미확정. 관측소 연결·문서 버전 정보는 현재 등록부에 없습니다.</p>
      </section>
      <section className={`${card} p-4 flex flex-col h-[490px]`} aria-label="보고서 미리보기">
        <div className="flex items-center gap-2 mb-3"><Eye size={16} className="text-blue-600"/><h3 className="text-sm font-bold text-slate-800">문서 미리보기</h3><span className="ml-auto text-[10px] text-slate-500">등록 요약</span></div>
        <div className="overflow-auto flex-1 bg-slate-50 border border-slate-200 rounded-lg p-4 text-sm text-slate-700">
          {selected ? <><h4 className="font-bold mb-3">{selected.report_title || selected.report_id}</h4>{selected.summary ? <ReactMarkdown remarkPlugins={[remarkGfm]}>{selected.summary}</ReactMarkdown> : <p className="text-xs text-slate-500">등록된 요약이 없습니다. 원문 파일 미리보기는 미연결입니다.</p>}</> : <p className="text-xs text-slate-500 text-center py-12">{selectedId && !loading && !error ? '해당 문서 ID가 등록부에 없습니다.' : '목록에서 보고서를 선택하세요.'}</p>}
        </div>
        {selected && <><dl className="grid grid-cols-2 gap-1 text-[10px] text-slate-500 my-3"><dt>문서 ID</dt><dd className="text-right break-all">{selected.report_id}</dd><dt>작성자 / 승인자</dt><dd className="text-right">{selected.created_by || '미등록'} / {selected.approved_by || '미등록'}</dd><dt>수정일</dt><dd className="text-right">{dateLabel(selected.updated_at)}</dd><dt>게시 상태</dt><dd className="text-right">{selected.status==='PUBLISHED'?'게시 완료':'게시 확인 없음'}</dd></dl>
        {['DRAFT','REVIEW'].includes(selected.status) && <div className="border-t border-slate-100 pt-2 space-y-2">{selected.status==='REVIEW' && <input aria-label="검토 의견" placeholder="검토 의견" value={comment} onChange={e=>setComment(e.target.value)} className={`${input} w-full`}/>}<div className="flex gap-2">{selected.status==='DRAFT'?<button disabled={acting} onClick={()=>transition('review')} className={`${input} text-blue-700`}>검토 단계로 전환</button>:<><button disabled={acting} onClick={()=>transition('approve')} className={`${input} text-emerald-700`}>검토 후 승인</button><button disabled={acting} onClick={()=>transition('reject')} className={`${input} text-red-700`}>반려</button></>}</div><p className="text-[10px] text-slate-500">승인·반려는 로그인한 검토 권한 필요 · 승인은 게시와 별도</p></div>}</>}
        {actionMessage && <p role="status" className="text-xs text-slate-600 mt-2">{actionMessage}</p>}
      </section>
    </div>
    <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
      {[{title:'보고서 초안 목록',rows:drafts,state:'DRAFT'}, {title:'검토 대기함',rows:reviews,state:'REVIEW'}].map(group=><section key={group.title} className={`${card} p-4 h-56 flex flex-col`}><div className="flex justify-between mb-3"><h3 className="text-sm font-bold text-slate-800">{group.title}</h3><button onClick={()=>{reset();setFilterState(group.state);}} className="text-xs text-blue-700">목록에서 보기</button></div><div className="space-y-2 overflow-auto flex-1">{group.rows.map(r=><button key={r.report_id} onClick={()=>select(r.report_id)} className="block text-left w-full text-xs p-2 rounded-lg hover:bg-blue-50 text-slate-700">{r.report_title || r.report_id}<span className="block text-[10px] text-slate-500 mt-1">생성 {dateLabel(r.created_at)}</span></button>)}{!group.rows.length && <p className="text-xs text-slate-500">{loading?'조회 중…':error?'조회 실패':'해당 상태의 보고서 없음'}</p>}</div></section>)}
      <section className={`${card} p-4 h-56`}><h3 className="text-sm font-bold text-slate-800 mb-3">문서 유형별 분포</h3><div className="space-y-2 overflow-auto max-h-40">{types.map(t=><div key={t} className="flex justify-between text-xs text-slate-600"><span>{typeLabel(t)}</span><span className="tabular-nums">{reports.filter(r=>r.report_type===t).length}건</span></div>)}{!types.length && <p className="text-xs text-slate-500">{loading?'조회 중…':error?'조회 실패':'등록 유형 없음'}</p>}</div></section>
      <section className={`${card} p-4 h-56`}><h3 className="text-sm font-bold text-slate-800 mb-3">보고서 작성 준비</h3><p className="text-xs leading-relaxed text-slate-500">일일·주간·월간·이상·특별 보고서의 근거 연결, 양식 및 AI 생성 흐름은 구현 전입니다. 원천자료와 문서 후보를 검토한 뒤 작성으로 연결할 예정입니다.</p><Link to={`/ai-insights?${new URLSearchParams(Object.fromEntries([...searchParams].filter(([k])=>k!=='report')))}`} className="inline-flex items-center gap-1 text-xs text-blue-700 mt-3">분석 근거 검토 <ArrowRight size={13}/></Link></section>
    </div>
  </div>;
}
