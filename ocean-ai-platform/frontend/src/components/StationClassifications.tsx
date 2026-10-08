import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { API_BASE_URL, apiFetch } from '../api/client';
import { CURRENT_OBSERVATION_MONTH, observationPeriod, selectObservationSource } from '../data/observationPeriod';

export default function StationClassifications(){
 const [search,setSearch]=useSearchParams(),[data,setData]=useState<any>(null),[error,setError]=useState('');
 const {from,to}=observationPeriod(search);
 const julyReference=from===CURRENT_OBSERVATION_MONTH&&to===CURRENT_OBSERVATION_MONTH;
 const referenceQuery=julyReference?`?as_of_month=${CURRENT_OBSERVATION_MONTH}`:'';
 const update=(key:string,value:string)=>setSearch({...Object.fromEntries(search),[key]:value,station:'',item:''});
 useEffect(()=>{const c=new AbortController();setData(null);setError('');apiFetch(`${API_BASE_URL}/stations/catalog/classifications${referenceQuery}`,{signal:c.signal}).then(async r=>{if(!r.ok)throw new Error(`HTTP ${r.status}`);return r.json();}).then(d=>{if(!c.signal.aborted)setData(d);}).catch(()=>{if(!c.signal.aborted)setError('ocean_ai_db 관측망·해역 분류 조회 실패');});return()=>c.abort();},[referenceQuery]);
 return <section className="flex flex-wrap items-end gap-3 border border-blue-100 bg-white rounded-xl p-3 text-xs" aria-label="DB 관측소 분류">
  <label>관측망·시설 유형<select aria-label="관측망·시설 유형" value={search.get('network')||''} onChange={e=>update('network',e.target.value)} className="block border border-blue-200 rounded-lg p-2 mt-1 min-w-44"><option value="">전체 관측망</option>{(data?.networks||[]).map((n:any)=><option key={n.value} value={n.value}>{n.label}</option>)}<option value="__UNREGISTERED__">DB 기준정보 미등록</option></select></label>
  <label>해역<select aria-label="해역" value={search.get('sea')||''} onChange={e=>update('sea',e.target.value)} className="block border border-blue-200 rounded-lg p-2 mt-1 min-w-32"><option value="">전체 해역</option>{(data?.seas||[]).map((s:any)=><option key={s.value} value={s.value}>{s.label}</option>)}</select></label>
  <p className="text-slate-500 pb-1">{error||`ocean_ai_db 등록 코드 ${data?.total_registered??'조회 중'}개 · 과거 자료 포함`}<br/>현재 운영 관측소 수가 아닙니다. 사업·시설 분류와 운영·폐지 기간 대조 중입니다.<br/>{julyReference?'7월 보고서 대조 참조 및 기존 DB 기준정보':'기존 DB 기준정보 참조'} · 운영 상태 미확정. 카드·지도·표는 선택 기간의 자료 보유 수를 표시합니다.</p>
  <button className="text-blue-700 p-2" onClick={()=>setSearch({...Object.fromEntries(search),network:'',sea:'',station:'',item:''})}>분류 초기화</button>
 </section>;
}

/** Storage lineage is a separate choice from the business classification above. */
export function DatasetSourceSelect({source}:{source:string}){
 const [search,setSearch]=useSearchParams();
 const titles:Record<string,string>={GD_OBS_ST_MONTHLY:'월별 수집본 · 현황 기준월',GD_OBS_BU:'추가 수집본 · GD_OBS_BU',GD_OBS_VBU:'추가 수집본 · GD_OBS_VBU',GR_OBS_ST:'추가 수집본 · GR_OBS_ST',HISTORICAL_RECONCILED:'과거 CSV 정산 등록분 · 명시적 역사 조회'};
 return <details className="inline-block align-top"><summary className="cursor-pointer rounded-lg border border-slate-200 bg-white p-2 text-xs text-slate-600">자료 출처: {titles[source]||source}</summary><div className="p-3 bg-slate-50 rounded-lg mt-1"><select aria-label="원천 데이터셋" className="border rounded-lg p-2 bg-white max-w-full" value={source} onChange={e=>setSearch(selectObservationSource(search,e.target.value))}>{Object.entries(titles).map(([k,v])=><option key={k} value={k}>{v}</option>)}</select><p className="text-[11px] text-slate-500 mt-2">원천 구분이며 시설 유형이 아닙니다. 다른 수집본을 자동 병합하지 않습니다. 지정한 조회 기간은 유지되며, 과거 자료는 시작월·종료월을 선택하세요.</p></div></details>;
}
