import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { MapPin, Database } from 'lucide-react';
import { API_BASE_URL, apiFetch } from '../api/client';

/** Same source / period as the map and table; original nulls remain unknown. */
export default function StationQuickView({station,source,from,to,snapshot}:{station:any;source:string;from:string;to:string;snapshot?:string}) {
  const [data,setData]=useState<any>(null),[error,setError]=useState(''),[tab,setTab]=useState('자료');
  const query=new URLSearchParams({source,from_month:from,to_month:to}).toString();
  const linkQuery=new URLSearchParams({source,from,to}).toString();
  useEffect(()=>{setData(null);setError('');setTab('자료');if(!station)return;const c=new AbortController();apiFetch(`${API_BASE_URL}/lake/stations/${encodeURIComponent(station.id)}?${query}`,{signal:c.signal}).then(async r=>{if(!r.ok)throw new Error(`HTTP ${r.status}`);return r.json();}).then(d=>{if(c.signal.aborted)return;if(snapshot&&d.snapshot!==snapshot)throw new Error('검증본 전환 중 · 화면 새로고침 필요');setData(d);}).catch(e=>{if(!c.signal.aborted)setError(`상세 조회 실패: ${e.message}`);});return()=>c.abort();},[station?.id,query,snapshot]);
  const rows=data?.months||[];
  const items=[...new Set<string>(rows.map((r:any)=>r.item_code))];
  return <aside className="bg-white border border-blue-100 rounded-2xl shadow-sm p-4 min-w-0 xl:col-span-1">
    <h3 className="text-sm font-bold text-blue-900 mb-4 flex gap-2"><MapPin className="w-5 h-5"/>관측소 상세 정보</h3>
    {!station?<p className="text-sm text-slate-500 py-10">지도나 목록에서 관측소를 선택하세요.</p>:<>
      <div className="bg-blue-50 rounded-xl p-4"><h4 className="font-bold">{station.name}</h4><p className="text-xs text-slate-500 mt-1">{station.id} · {station.net} · {station.sea}</p><p className="text-xs text-slate-500 mt-2">운영 상태 미확정 · 원천 QC 승인 전</p></div>
      <div className="flex border-b border-slate-200 my-4" role="tablist" aria-label="관측소 상세 종류">{['자료','센서·QC','기간'].map(t=><button role="tab" aria-selected={tab===t} key={t} onClick={()=>setTab(t)} className={`flex-1 text-xs p-2 ${tab===t?'border-b-2 border-blue-600 text-blue-700 font-bold':'text-slate-500'}`}>{t}</button>)}</div>
      {error&&<p role="alert" className="text-xs text-red-700">{error}</p>}{!data&&!error&&<p role="status" className="text-xs">상세 조회 중…</p>}
      {tab==='자료'&&<><p className="text-xs text-slate-500 mb-3">{from} ~ {to} · {station.note}</p><div className="max-h-[440px] overflow-auto space-y-2">{items.map(i=>{const rr=rows.filter((r:any)=>r.item_code===i);const months=[...new Set<string>(rr.map((r:any)=>String(r.month).slice(0,7)))].sort();return <div key={i} className="border border-blue-100 rounded-xl p-3"><div className="flex gap-2 text-xs font-bold text-blue-800"><Database className="w-4 h-4 shrink-0"/><span className="break-all">{i}</span></div><p className="text-sm font-bold mt-2">{rr.reduce((n:number,r:any)=>n+(r.held_rows||0),0).toLocaleString('ko-KR')}행</p><p className="text-[10px] text-slate-500 mt-1">{months[0]} ~ {months[months.length-1]} · {months.length}개월 보유</p></div>;})}</div><p className="text-[10px] text-slate-500 mt-2">실제 관측값·원천 QC·파일 계보는 아래 상세에서 항목·월·수심별로 조회합니다.</p></>}
      {tab==='센서·QC'&&<div className="space-y-3 text-xs">{[['물리 센서','physical_sensor_id'],['센서 대응','sensor_decision'],['단위 적용','unit_application_decision'],['시간대','timezone_decision'],['QC 근거','qc_evidence_decision'],['QC 승인','qc_approval_decision']].map(([label,key])=>{const counts:Record<string,number>={};rows.forEach((r:any)=>{const v=r[key]||'미확정';counts[v]=(counts[v]||0)+1;});return <div key={key} className="border-b pb-2 border-slate-100"><p className="font-bold">{label}</p><p className="text-slate-500 mt-1">{Object.entries(counts).map(([k,v])=>`${k} ${v}기록`).join(' · ')||'기록 없음'}</p></div>;})}<p className="text-amber-700">코드·기간 대응 해소만으로 센서와 QC가 승인된 것은 아닙니다.</p></div>}
      {tab==='기간'&&<dl className="text-xs space-y-4"><div><dt className="text-slate-500">보유 최초 원천 시각</dt><dd className="mt-1 font-bold">{station.first||'미확정'}</dd></div><div><dt className="text-slate-500">보유 최종 원천 시각</dt><dd className="mt-1 font-bold">{station.time}</dd></div><div><dt className="text-slate-500">관측소 운영 / 센서 설치 기간</dt><dd className="mt-1">별도 근거 검토 필요</dd></div><div><dt className="text-slate-500">수집·적재 시각 / 시간대</dt><dd className="mt-1">이 화면에서 미확정</dd></div><p className="text-amber-700">보유 기간은 연속 관측·운영기간을 보증하지 않습니다.</p></dl>}
      <Link className="block text-center text-xs font-bold text-blue-700 bg-blue-50 border border-blue-100 rounded-lg p-3 mt-5" to={`/profile/${encodeURIComponent(station.id)}?${linkQuery}`}>실측값·월별 근거 상세 보기 →</Link>
    </>}
  </aside>;
}
