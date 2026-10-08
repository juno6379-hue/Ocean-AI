// Three observation screens share the same manifest-backed source and period.
// Unknown units, physical sensors, timezone and QC approval are never invented.
import { useEffect, useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { apiFetch, API_BASE_URL } from '../api/client';
import { observationPeriod, selectObservationSource } from '../data/observationPeriod';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, ScatterChart, Scatter, CartesianGrid } from 'recharts';

const sources: Record<string,string> = {
  GD_OBS_ST_MONTHLY: '월별 정형 기준자료 · 현황 기준월 / 과거 기간 선택',
  GD_OBS_BU: '해양관측부이 원천 · GD_OBS_BU',
  GD_OBS_VBU: '부이 원천 · GD_OBS_VBU',
  GR_OBS_ST: 'GR_OBS_ST 원천',
  HISTORICAL_RECONCILED: '과거 정산 원천 · 등록 범위만',
};
const number = (n: number | null | undefined) => n == null ? '미확정' : n.toLocaleString('ko-KR');
const shown = (s: unknown) => s == null || s === '' ? '미확정' : String(s);
const conditionNames: Record<string,string> = {
  station_dictionary_decision:'관측소 코드', item_dictionary_decision:'항목 코드',
  source_identity_decision:'원천 동일성', unit_application_decision:'적용 단위',
  sensor_decision:'물리 센서', period_decision:'센서 유효기간', timezone_decision:'시간대',
  qc_evidence_decision:'QC 근거', qc_approval_decision:'QC 승인',
};
const field = 'rounded border border-slate-300 bg-white px-3 py-2 text-sm';

export default function LakeExplorer({ mode, station }: {mode:'dashboard'|'observations'|'detail';station?:string}) {
  const [search,setSearch] = useSearchParams();
  const { source, from, to } = observationPeriod(search);
  const network = search.get('network') || '';
  const sea = search.get('sea') || '';
  const requestedItem = search.get('item') || '';
  const [summary,setSummary] = useState<any>(null);
  const [detail,setDetail] = useState<any>(null);
  const [error,setError] = useState('');
  const [loading,setLoading] = useState(false);
  const [filter,setFilter] = useState('');
  const [channelKey,setChannelKey] = useState('');
  const [month,setMonth] = useState('');
  const [series,setSeries] = useState<any>(null);
  const [seriesError,setSeriesError] = useState('');
  const [seriesLoading,setSeriesLoading] = useState(false);
  const [offset,setOffset] = useState(0);
  const [revision,setRevision] = useState(0);
  const query = new URLSearchParams({source,from_month:from,to_month:to,network,sea}).toString();
  const linkQuery = new URLSearchParams({source,from,to,network,sea,...(requestedItem?{item:requestedItem}:{})}).toString();
  const update = (changes:Record<string,string>) => setSearch({...Object.fromEntries(search),...changes});

  useEffect(()=>{
    const control=new AbortController();
    setLoading(true);setError('');setSummary(null);setDetail(null);setSeries(null);setChannelKey('');setMonth('');setOffset(0);
    const read=async(path:string)=>{
      const r=await apiFetch(`${API_BASE_URL}${path}`,{signal:control.signal});
      if(!r.ok) throw new Error(`자료 조회 실패 (HTTP ${r.status})`);
      return r.json();
    };
    Promise.all([read(`/lake/summary?${query}`),station?read(`/lake/stations/${encodeURIComponent(station)}?${query}`):Promise.resolve(null)])
      .then(([s,d])=>{if(!control.signal.aborted){setSummary(s);setDetail(station && !s.stations.some((r:any)=>r.station_code===station) ? null : d);}})
      .catch(e=>{if(!control.signal.aborted)setError(e.message);})
      .finally(()=>{if(!control.signal.aborted)setLoading(false);});
    return()=>control.abort();
  },[query,station,revision]);

  const channels = useMemo(()=>{
    const map=new Map<string,any>();
    for(const r of detail?.months||[]){
      const key=JSON.stringify([r.item_code,r.depth_step,r.depth_from,r.depth_to]);
      if(!map.has(key)) map.set(key,{key,item:r.item_code,depth:[r.depth_step,r.depth_from,r.depth_to],months:[]});
      map.get(key).months.push(r);
    }
    return Array.from(map.values());
  },[detail]);
  const channel=channels.find(c=>c.key===channelKey && (!requestedItem || c.item===requestedItem))
    || (requestedItem ? channels.find(c=>c.item===requestedItem) : channels[0]);
  const selectedMonth=month || String(channel?.months[0]?.month||'').slice(0,7);
  const evidence=channel?.months.find((m:any)=>String(m.month).startsWith(selectedMonth));

  useEffect(()=>{setMonth('');setOffset(0);},[requestedItem]);

  useEffect(()=>{
    setSeries(null);setSeriesError('');setSeriesLoading(false);
    if(!station || !channel || !selectedMonth)return;
    const control=new AbortController();setSeriesLoading(true);
    const p=new URLSearchParams({source,station,item:channel.item,month:selectedMonth,limit:'500',offset:String(offset)});
    ['depth_step','depth_from','depth_to'].forEach((key,i)=>{if(channel.depth[i]!=null)p.set(key,String(channel.depth[i]));});
    apiFetch(`${API_BASE_URL}/lake/series?${p}`,{signal:control.signal})
      .then(async r=>{if(!r.ok)throw new Error(`실측값 조회 실패 (HTTP ${r.status})`);return r.json();})
      .then(s=>{if(!control.signal.aborted)setSeries(s);})
      .catch(e=>{if(!control.signal.aborted)setSeriesError(e.message);})
      .finally(()=>{if(!control.signal.aborted)setSeriesLoading(false);});
    return()=>control.abort();
  },[source,station,channel,selectedMonth,offset,revision]);

  const title=mode==='dashboard'?'실측자료 통합 대시보드':mode==='observations'?'관측자료 보유 현황':`${station} 관측 상세`;
  const stations=(summary?.stations||[]).filter((s:any)=>`${s.station_code} ${s.station_name||''}`.toLowerCase().includes(filter.toLowerCase()));
  const stationTotals=station ? summary?.stations.find((s:any)=>s.station_code===station) : null;
  const totals=mode==='detail' ? (stationTotals ? {...stationTotals,stations:1} : {stations:0,items:0,held_rows:0,held_months:0}) : summary?.totals;
  return <div className="p-6 space-y-5 bg-slate-50 min-h-full text-slate-800">
    <div className="flex justify-between items-start"><div><h1 className="text-2xl font-bold">{title}</h1><p className="mt-1 text-sm text-slate-600">Parquet 실측 원천 → 공통 조회 API → 대시보드·현황·상세</p></div>
      <button className={field} onClick={()=>setRevision(r=>r+1)}>새로고침</button></div>
    <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm space-y-1">
      <p><strong>실측 원천 조회 · QC 승인 전</strong> — SIMULATED 자료는 이 화면에 포함하지 않습니다.</p>
      <p>보유 시계열은 확인할 수 있지만, 물리 센서·단위·시간대·QC의 미확정 조건은 남아 있습니다. 자료가 없는 월을 관측 중단으로 단정하지 않습니다.</p>
      <p>관측값은 D: Parquet에서 읽습니다. PostgreSQL 전체 관측값 적재가 완료되었다는 의미는 아닙니다.</p>
    </div>
    <div className="flex flex-wrap gap-3 items-end rounded-xl bg-white border p-4">
      <label className="text-sm">원천<select aria-label="원천" className={`${field} block mt-1`} value={source} onChange={e=>setSearch(selectObservationSource(search,e.target.value))}>{Object.entries(sources).map(([k,v])=><option key={k} value={k}>{v}</option>)}</select></label>
      <label className="text-sm">시작월<input aria-label="시작월" type="month" className={`${field} block mt-1`} value={from} onChange={e=>e.target.value&&update({from:e.target.value})}/></label>
      <label className="text-sm">종료월<input aria-label="종료월" type="month" className={`${field} block mt-1`} value={to} onChange={e=>e.target.value&&update({to:e.target.value})}/></label>
      <Link className="text-blue-700 underline p-2" to={`/observations?${linkQuery}`}>관측소 목록</Link>
      <Link className="text-blue-700 underline p-2" to={`/data-lake?${linkQuery}`}>원천 검증 현황</Link>
    </div>
    {loading&&<p role="status">정산된 원천 목록을 불러오는 중…</p>}
    {error&&<p role="alert" className="text-red-700">{error} 이전 값이나 모의값으로 대체하지 않습니다.</p>}
    {mode==='detail'&&summary&&!loading&&!error&&!stationTotals&&<p className="bg-white border p-4 rounded">이 관측소는 선택 원천·기간·관측망·해역의 보유자료 범위에 없습니다.</p>}
    {mode==='detail'&&detail&&requestedItem&&!channel&&<p role="alert" className="text-amber-800">요청 항목 {requestedItem}의 채널이 선택 범위에 없습니다. 다른 항목의 값으로 대체하지 않습니다.</p>}
    {summary&&<>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">{[
        ['보유 관측소',number(totals?.stations)],['원천 항목 코드',number(totals?.items)],
        ['보유 원천 행 수',number(totals?.held_rows)],['자료가 있는 월',number(totals?.held_months)],
      ].map(([label,value])=><div key={label} className="rounded-xl border bg-white p-5"><p className="text-sm text-slate-600">{label}</p><p className="text-2xl font-bold mt-2">{value}</p></div>)}</div>
      <p className="text-sm">선택 기간의 자료 보유 수 · 현재 운영 시설 수 아님<br/>최초·최종 원천 시각: {shown(totals?.first_clock)} ~ {shown(totals?.last_clock)} · 시간대 미확정<br/>{summary.note}</p>
      {source==='HISTORICAL_RECONCILED'&&<p className="border border-amber-300 rounded p-3 text-sm">{summary.legacy_status}. 현재 선택 결과가 과거 전체 보유량을 뜻하지 않습니다.</p>}
      {mode!=='detail'&&<div className="bg-white border rounded-xl p-5"><h2 className="font-bold mb-3">월별 보유 관측 행 수</h2><div className="h-56"><ResponsiveContainer width="100%" height="100%"><BarChart data={summary.monthly}><XAxis dataKey="month" tickFormatter={v=>String(v).slice(0,7)}/><YAxis tickFormatter={v=>Number(v).toLocaleString()}/><Tooltip/><Bar dataKey="held_rows" name="원천 보유 행" fill="#2563eb"/></BarChart></ResponsiveContainer></div></div>}
      {mode!=='detail'&&<div className="bg-white border rounded-xl p-5"><div className="flex justify-between mb-3"><h2 className="font-bold">관측소별 기간과 항목</h2><input aria-label="관측소 검색" className={field} placeholder="코드·관측소명 검색" value={filter} onChange={e=>setFilter(e.target.value)}/></div><div className="overflow-auto max-h-[550px]"><table className="w-full text-sm text-left"><thead><tr>{['관측소','항목 수','보유 행 수','최초 시각','최종 시각','상세'].map(s=><th className="p-2 border-b" key={s}>{s}</th>)}</tr></thead><tbody>{stations.map((s:any)=><tr key={s.station_code} className="border-b"><td className="p-2">{s.station_name||'이름 미확정'}<br/><span className="text-slate-500">{s.station_code}</span></td><td>{s.items}</td><td>{number(s.held_rows)}</td><td>{shown(s.first_clock)}</td><td>{shown(s.last_clock)}</td><td><Link className="text-blue-700 underline" to={`/profile/${encodeURIComponent(s.station_code)}?${linkQuery}`}>실측·QC 근거 보기</Link></td></tr>)}</tbody></table></div>{!stations.length&&<p className="p-3">선택 범위에 등록된 보유 자료가 없습니다. 관측 중단 여부는 미확정입니다.</p>}</div>}
      <p className="text-xs text-slate-500">검증 스냅샷: {summary.snapshot} · 원천별 조회 · QC 승인 상태: {summary.approval_status}</p>
    </>}
    {mode==='detail'&&detail&&<div className="space-y-4">
      {!channels.length?<p className="bg-white border p-4 rounded">이 관측소의 선택 원천·기간에 등록된 자료가 없습니다. 다른 원천 또는 기간을 선택하세요.</p>:<>
        <div className="bg-white border rounded-xl p-4 flex flex-wrap gap-4"><label>항목·수심 채널<select aria-label="항목·수심 채널" className={`${field} block mt-1`} value={channel?.key||''} onChange={e=>{setChannelKey(e.target.value);setMonth('');setOffset(0);const selected=channels.find(c=>c.key===e.target.value);if(selected)update({item:selected.item});}}>{!channel&&<option value="" disabled>요청 항목 채널 없음</option>}{channels.map(c=><option key={c.key} value={c.key}>{c.item} · 수심 {c.depth.map(shown).join(' / ')}</option>)}</select></label>
          <label>관측월<select aria-label="관측월" className={`${field} block mt-1`} value={selectedMonth} onChange={e=>{setMonth(e.target.value);setOffset(0);}}>{channel?.months.map((m:any)=><option key={m.month} value={String(m.month).slice(0,7)}>{String(m.month).slice(0,7)} · {number(m.held_rows)}행</option>)}</select></label></div>
        {evidence&&<div className="bg-white border rounded-xl p-4"><h2 className="font-bold">관측소–항목–선택월 검증 상세</h2><p className="my-2 text-sm">물리 센서: {shown(evidence.physical_sensor_id)} · 단위: {shown(evidence.standard_unit)} · 시간대: {shown(evidence.timezone_name)} · 센서 유효기간: {shown(evidence.valid_from)} ~ {shown(evidence.valid_to)}</p>
          <div className="grid md:grid-cols-3 gap-2 text-sm">{Object.entries(conditionNames).map(([k,v])=><p key={k} className="rounded bg-slate-50 p-2">{v}: <strong>{shown(evidence[k])}</strong></p>)}</div>
          <p className="text-sm mt-3">관측 시각 {shown(evidence.first_clock)} ~ {shown(evidence.last_clock)} · 결측값 행 {number(evidence.missing_value_rows)} · 원천 QC 표기 행 {number(evidence.source_qc_present_rows)} · 승인 QC 유효 행 {number(evidence.approved_qc_valid_rows)}</p>
          <p className="text-sm mt-1">시각 해석 불가 행: {number(evidence.invalid_time_rows)} · 시각을 해석할 수 없는 행은 아래 시간순 조회에 포함하지 않습니다. 원천은 보존됩니다.</p>
          <details className="mt-3 text-sm"><summary className="cursor-pointer text-blue-700">문서 근거·충돌·미해결 사유 보기</summary><pre className="whitespace-pre-wrap break-all bg-slate-50 p-3">{JSON.stringify({reason:evidence.reason,dictionary:evidence.dictionary_evidence,history:evidence.history_evidence,events:evidence.event_ids,conflicts:evidence.conflict_evidence,candidate_sensors:evidence.physical_sensor_candidate_ids},null,2)}</pre></details>
        </div>}
        <div className="bg-white border rounded-xl p-5"><h2 className="font-bold">실측 원천값 · 시간순 페이지 (최대 500행)</h2><p className="text-sm text-slate-600 my-2">아래 그래프는 현재 페이지의 값입니다. 전체 월 통계가 아니며 결측 보간·단위 변환을 하지 않습니다. 원천 시각에 시간대를 임의 적용하지 않습니다.</p>
          {seriesLoading&&<p role="status">Parquet 조회 및 반환 파일 해시 확인 중…</p>}{seriesError&&<p role="alert" className="text-red-700">{seriesError}</p>}
          {series&&<><div className="h-64"><ResponsiveContainer width="100%" height="100%"><ScatterChart><CartesianGrid strokeDasharray="3 3"/><XAxis dataKey="observed_time_raw" type="category" name="원천 시각" allowDuplicatedCategory={false}/><YAxis dataKey="value_numeric" type="number" name="원천값" domain={['auto','auto']}/><Tooltip/><Scatter data={series.rows.filter((r:any)=>r.value_numeric!=null)} fill="#2563eb"/></ScatterChart></ResponsiveContainer></div>
            <div className="flex gap-4 my-3 items-center"><button className={field} disabled={offset===0||seriesLoading} onClick={()=>setOffset(Math.max(0,offset-500))}>이전</button><span>{offset+1}행부터 · 반환 {series.rows.length}행</span><button className={field} disabled={!series.has_more||seriesLoading} onClick={()=>setOffset(offset+500)}>다음</button></div>
            <div className="overflow-auto max-h-80"><table className="w-full text-sm text-left"><thead><tr>{['원천 관측시각','원천값','원천 QC','원천 MQ','수집·수신 시각','계보'].map(x=><th className="p-2 border-b" key={x}>{x}</th>)}</tr></thead><tbody>{series.rows.map((r:any)=><tr className="border-b" key={`${r.filename}:${r.file_row_number}`}><td className="p-2">{shown(r.observed_time_raw)}</td><td>{r.value_raw===null?'NULL':String(r.value_raw)}</td><td>{shown(r.source_qc_raw)}</td><td>{shown(r.source_mq_raw)}</td><td>{shown(r.received_time_raw)}</td><td><details><summary className="cursor-pointer">해시·파일·행</summary><pre className="text-xs whitespace-pre-wrap break-all max-w-md">{JSON.stringify({file:r.filename,row:r.file_row_number,source_sha256:r.source_sha256,parquet_sha256:r.parquet_sha256},null,2)}</pre></details></td></tr>)}</tbody></table></div>
            {!series.rows.length&&<p>선택 채널·월에 반환할 원천 관측값이 없습니다.</p>}</>}
        </div>
      </>}
    </div>}
  </div>;
}
