import StationClassifications, { DatasetSourceSelect } from './StationClassifications';
import OSMBaseLayer from './OSMBaseLayer';
import MetricCompletionPanel, { useMetricCompletion } from './MetricCompletionPanel';
import { percentMetric, qcPresencePercent } from '../data/metricPresentation';
import { observationPeriod } from '../data/observationPeriod';
/** Evidence-led QC / insight views. Never infer fault, confidence or approval from document overlap. */
import { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { Activity, ShieldCheck, AlertTriangle, FileText, BrainCircuit, Database, RefreshCw } from 'lucide-react';
import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid, Legend, PieChart, Pie, Cell } from 'recharts';
import { MapContainer, CircleMarker, Popup } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import { API_BASE_URL, apiFetch } from '../api/client';

const panel = 'bg-white rounded-2xl border border-blue-100 shadow-sm p-5 min-w-0';
const fmt = (v:any) => typeof v==='number'&&Number.isFinite(v) ? v.toLocaleString('ko-KR') : '필요입력 없음';
const pct = (v:any) => typeof v==='number'&&Number.isFinite(v) ? `${fmt(v)}%` : '필요입력 없음';
const colors = ['#2563eb', '#cbd5e1'];
async function read(path:string, signal:AbortSignal) {
  const r=await apiFetch(`${API_BASE_URL}${path}`,{signal});
  if(!r.ok) throw new Error(`조회 실패 (HTTP ${r.status})`);
  return r.json();
}

export function EvidenceCase({event, linkQuery}: {event:any;linkQuery:string}) {
  if(!event)return <p className="text-sm text-slate-500 py-8">선택 범위에 연결된 문서 사건이 없습니다. 이상이 없다는 의미는 아닙니다.</p>;
  return <div className="space-y-3 text-sm">
    <div className="flex justify-between gap-2"><h4 className="font-bold">{event.station_name} · {event.item_codes.join(', ')}</h4><span className="text-amber-700 shrink-0">담당 검토 전</span></div>
    <p className="text-xs text-slate-500">{event.id} · {event.period_start} ~ {event.period_end_inclusive} · 월 단위 근거</p>
    <blockquote className="bg-blue-50 border-l-4 border-blue-500 p-3 rounded-r-lg">{event.claim}</blockquote>
    <dl className="grid grid-cols-[100px_1fr] gap-2 text-xs">
      <dt className="text-slate-500">기간 대응</dt><dd>{event.decision} · 원인 확정/승인과 별개</dd>
      <dt className="text-slate-500">선택 범위 연결</dt><dd>{fmt(event.linked_monthly_records)}개 월별 기록 · {fmt(event.linked_held_rows)}행</dd>
      <dt className="text-slate-500">물리 센서</dt><dd>{event.physical_sensor_id || '미확정'}</dd>
      <dt className="text-slate-500">모델 / 신뢰도</dt><dd>미평가 · 문서 기반 검토 후보</dd>
      <dt className="text-slate-500">문서 위치</dt><dd>{event.locator}</dd>
    </dl>
    <details className="rounded-xl border border-slate-200 p-3 text-xs"><summary className="cursor-pointer font-semibold text-blue-700">원문 경로·해시·원천 플래그 확인</summary><p className="break-all mt-3">{event.document_path}</p><p className="break-all mt-2 text-slate-500">SHA-256: {event.sha256}</p>
      <p className="mt-3">아래 플래그는 보고서 사건 전체 기간의 원천 집계이며, 상단 조회 기간 집계와 다를 수 있습니다. QC / MQ 코드 정의는 별도 확인이 필요합니다.</p>
      <table className="w-full mt-2 text-left"><thead><tr><th>원천 QC</th><th>원천 MQ</th><th>행 수</th></tr></thead><tbody>{(event.source_flags||[]).map((f:any,i:number)=><tr key={i}><td>{f.qc ?? 'NULL'}</td><td>{f.mq ?? 'NULL'}</td><td>{fmt(f.rows)}</td></tr>)}</tbody></table></details>
    <p className="text-xs text-slate-500">{event.limitation}</p>
    <div className="flex flex-wrap gap-2">{event.station_codes.map((s:string)=><Link key={s} className="bg-blue-600 text-white rounded-lg px-3 py-2 text-xs" to={`/profile/${encodeURIComponent(s)}?${linkQuery}`}>{s} 관측값·근거 상세 →</Link>)}</div>
    <p className="text-xs text-amber-700">원인·Label·QC 최종 승인은 담당 검토가 필요합니다. 이 화면은 승인을 수행하지 않습니다.</p>
  </div>;
}

export default function AnalysisWorkspace({insights=false}:{insights?:boolean}) {
  const [search,setSearch]=useSearchParams();
  const { source, from, to } = observationPeriod(search);
  const station=search.get('station')||'', item=search.get('item')||'';
  const baseQuery=new URLSearchParams({network:search.get('network')||'',sea:search.get('sea')||'',source,from_month:from,to_month:to}).toString();
  const query=new URLSearchParams({network:search.get('network')||'',sea:search.get('sea')||'',source,from_month:from,to_month:to,station,item}).toString();
  const linkQuery=new URLSearchParams({network:search.get('network')||'',sea:search.get('sea')||'',source,from,to}).toString();
  const update=(v:Record<string,string>)=>setSearch({...Object.fromEntries(search),...v});
  const [data,setData]=useState<any>(null),[overview,setOverview]=useState<any>(null);
  const [metadata,setMetadata]=useState<any[]>([]),[referenceError,setReferenceError]=useState('');
  const [error,setError]=useState(''),[loading,setLoading]=useState(false),[revision,setRevision]=useState(0);
  const [selected,setSelected]=useState('');
  const completion=useMetricCompletion(query,revision,data?.snapshot);
  const metricWaiting=completion.loading?'조회 중':completion.error?'조회 실패':completion.data?.state==='UNAVAILABLE_PERIOD'?'해당 기간 진단 미등록':'필요입력 없음';
  useEffect(()=>{
    const control=new AbortController();setLoading(true);setError('');setData(null);setOverview(null);setSelected('');
    if(from>to){setError('시작월은 종료월보다 늦을 수 없습니다.');setLoading(false);return()=>control.abort();}
    Promise.all([read(`/lake/monitoring?${query}`,control.signal),read(`/lake/summary?${baseQuery}`,control.signal)])
      .then(([m,o])=>{if(control.signal.aborted)return;if(m.snapshot!==o.snapshot)throw new Error('검증본 전환 중입니다. 새로고침해 주세요.');setData(m);setOverview(o);setSelected(m.events[0]?.id||'');})
      .catch(e=>{if(!control.signal.aborted)setError(e.message);}).finally(()=>{if(!control.signal.aborted)setLoading(false);});
    return()=>control.abort();
  },[query,baseQuery,revision]);
  useEffect(()=>{if(!insights)return;const c=new AbortController();setMetadata([]);setReferenceError('');read('/stations?limit=10000',c.signal).then(d=>{if(!c.signal.aborted)setMetadata(d);}).catch(()=>{if(!c.signal.aborted)setReferenceError('지도 기준 좌표 조회 실패');});return()=>c.abort();},[insights,revision]);
  const obs=data?.observations, channels=data?.channels||[], events=data?.events||[];
  const current=events.find((e:any)=>e.id===selected);
  const items=[...new Set<string>(channels.map((c:any)=>c.item_code))];if(item&&!items.includes(item))items.push(item);
  const stationCodes=[...new Set<string>(channels.map((c:any)=>c.station_code))];
  const matrixItems=items.slice(0,7),matrixStations=stationCodes.slice(0,10);
  const distribution=obs?.source_qc_present_rows!=null&&obs.held_rows>0?[{name:'원천 QC 표기 있음',value:obs.source_qc_present_rows},{name:'원천 QC 표기 없음',value:obs.held_rows-obs.source_qc_present_rows}]:[];
  // Fill absent months with null; do not connect observations across an unknown gap.
  const monthly:any[]=[];
  if(data&&from<=to){const date=new Date(`${from}-01T00:00:00Z`);const byMonth=new Map(data.monthly.map((m:any)=>[m.month,m]));while(date.toISOString().slice(0,7)<=to&&monthly.length<1200){const month=date.toISOString().slice(0,7);monthly.push(byMonth.get(month)||{month,source_qc_presence_rate:null,missing_value_rate:null,held_rows:null});date.setUTCMonth(date.getUTCMonth()+1);}}
  const ranked=stationCodes.map(code=>({code,name:channels.find((c:any)=>c.station_code===code)?.station_name||code,events:events.filter((e:any)=>e.station_codes.includes(code)).length})).filter(r=>r.events>0).sort((a,b)=>b.events-a.events||a.code.localeCompare(b.code));
  const markers=ranked.flatMap(r=>{const refs=metadata.filter(m=>m.station_id===r.code);const m=refs.length===1?refs[0]:null;return Number.isFinite(m?.latitude)&&Number.isFinite(m?.longitude)&&Math.abs(m.latitude)<=90&&Math.abs(m.longitude)<=180?[{...r,lat:m.latitude,lng:m.longitude}]:[];});
  const cards=insights ? [
    ['문서 검토 후보',data?fmt(events.length):'—','선택 범위와 기간 대응',FileText],
    ['연결 관측소',data?fmt(ranked.length):'—','위험도 순위 아님',Activity],
    ['AI 예측 결과','평가대상 없음','동일 기간·항목의 평가된 모델 결과 필요',BrainCircuit],
    ['설명가능성 점수','필요입력 없음','근거 충실도 평가셋·채점 규칙 필요',ShieldCheck],
    ['재학습 후보','평가대상 없음','운영 모델·고정 reference와 드리프트 평가 필요',RefreshCw],
  ]:[
    ['승인 QC 정상률','필요입력 없음','승인 최종 QC와 동일 평가 범위·분모 원장 필요',ShieldCheck],['승인 BAD 비율','필요입력 없음','원천 코드와 최종 QC 승인 집계는 별도',AlertTriangle],
    ['원천 QC 표기율',completion.data?.raw?qcPresencePercent(completion.data.raw):metricWaiting,'기본 QC 코드 표기 행 / 보유 행 · 승인 정상률 아님',Activity],['원시 결측표현율',completion.data?.raw?percentMetric(completion.data.raw.missing_value_rate,completion.data.raw.held_rows):metricWaiting,'원시 결측 표현 / 보유 행 · 미수집 결측률 아님',Database],
    ['문서 검토 후보',data?fmt(events.length):'—','승인 대기 건수와 별개',FileText],['보유 행 수',fmt(obs?.held_rows),'중복 제거 전 원천 행',Database],
  ];
  return <div className="p-4 md:p-6 space-y-5 min-h-full bg-gradient-to-br from-blue-50/60 via-white to-indigo-50/40">
    <header className="flex flex-wrap justify-between gap-4 items-end"><div><p className="text-xs tracking-[.18em] text-blue-600 font-bold">{insights?'EVIDENCE & INSIGHTS':'QUALITY CONTROL'}</p><h1 className="text-3xl font-extrabold text-slate-900 mt-2">{insights?'AI 분석 인사이트':'품질 현황 (QC)'}</h1><p className="text-sm text-slate-500 mt-2">{insights?'관측 자료에서 문서 근거, 검토와 평가까지 연결합니다.':'원천 품질 현황과 검토 근거를 함께 확인합니다.'}</p></div><div className="rounded-xl border border-blue-100 bg-blue-50 p-4 text-xs text-blue-800 max-w-sm"><BrainCircuit className="w-5 h-5 mb-2"/>문서 기반 근거 연결 완료 범위부터 조회합니다. 승인된 AI 예측·원인 판정은 아직 제공하지 않습니다.</div></header>
    <StationClassifications/>
    <div className={`${panel} flex flex-wrap gap-3 text-xs items-end`}>
      <label>자료 출처<DatasetSourceSelect source={source}/></label>
      <label>시작월<input aria-label="시작월" type="month" value={from} onChange={e=>e.target.value&&update({from:e.target.value})} className="block border rounded-lg p-2 mt-1"/></label><label>종료월<input aria-label="종료월" type="month" value={to} onChange={e=>e.target.value&&update({to:e.target.value})} className="block border rounded-lg p-2 mt-1"/></label>
      <label>관측소<select aria-label="관측소" value={station} onChange={e=>update({station:e.target.value,item:''})} className="block border rounded-lg p-2 mt-1 max-w-48"><option value="">전체</option>{(overview?.stations||[]).map((s:any)=><option key={s.station_code} value={s.station_code}>{s.station_name||s.station_code} ({s.station_code})</option>)}</select></label>
      <label>항목<select aria-label="항목" value={item} onChange={e=>update({item:e.target.value})} className="block border rounded-lg p-2 mt-1 max-w-48"><option value="">전체</option>{items.map(i=><option key={i}>{i}</option>)}</select></label><button onClick={()=>setRevision(v=>v+1)} className="bg-blue-600 text-white rounded-lg px-5 py-2">새로고침</button><button onClick={()=>update({station:'',item:''})} className="text-blue-700 p-2">필터 초기화</button>
    </div>
    {loading&&<p role="status" className="text-sm text-blue-600">완료된 검증본을 조회하고 있습니다…</p>}{error&&<p role="alert" className="text-red-700">{error}</p>}
    <p className="text-xs text-slate-500">{data?`검증본 ${data.snapshot} · ${source} · ${from} ~ ${to}`:'조회 대기'} · 원천 시각의 시간대 미확정 · {data?.limitations}</p>
    {data&&!data.observation_metrics_available&&<p className="bg-amber-50 p-3 rounded-xl text-sm">과거 정산 자료의 품질 집계·문서 연결은 아직 이 화면에 등록되지 않았습니다. 아래 0건은 등록된 검토 기록 기준입니다.</p>}
    <div className={`grid grid-cols-2 md:grid-cols-3 ${insights?'2xl:grid-cols-5':'2xl:grid-cols-6'} gap-3`}>{cards.map(([label,value,note,Icon]:any)=><article key={label} className={panel}><Icon className="w-6 h-6 text-blue-600 mb-3"/><h2 className="text-xs font-bold">{label}</h2><p className="text-2xl font-extrabold text-slate-900 my-2 break-words">{value}</p><p className="text-[11px] text-slate-500">{note}</p></article>)}</div>
    <MetricCompletionPanel {...completion}/>
    <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
      <section className={panel}><h2 className="font-bold mb-3">{insights?'관측자료 보유 추이':'원천 QC 표기 분포'}</h2>{insights?<div className="h-56"><ResponsiveContainer width="100%" height="100%"><LineChart data={monthly}><CartesianGrid strokeDasharray="3 3"/><XAxis dataKey="month" tick={{fontSize:10}}/><YAxis width={50} tickFormatter={v=>Intl.NumberFormat('ko-KR',{notation:'compact'}).format(v)} tick={{fontSize:10}}/><Tooltip/><Line dataKey="held_rows" name="보유 원천 행" stroke="#6366f1" dot={false} connectNulls={false}/></LineChart></ResponsiveContainer></div>:<><div className="h-48">{distribution.length?<ResponsiveContainer width="100%" height="100%"><PieChart><Pie data={distribution} dataKey="value" innerRadius={55} outerRadius={85}>{distribution.map((_:any,i:number)=><Cell key={i} fill={colors[i]}/>)}</Pie><Tooltip/></PieChart></ResponsiveContainer>:<p className="py-12 text-center text-slate-400">집계 없음</p>}</div>{distribution.map((d:any,i:number)=><div key={d.name} className="text-xs flex justify-between py-1"><span style={{color:colors[i]}}>{d.name}</span><span>{fmt(d.value)}행</span></div>)}</>}<p className="text-xs text-slate-500 mt-3">{insights?'미등록 월은 공백입니다. 보유량의 변화는 이상 탐지 결과가 아닙니다.':'QC 표기가 있어도 정상·BAD 판정 또는 승인 완료를 뜻하지 않습니다.'}</p></section>
      <section className={panel}><h2 className="font-bold mb-3">{insights?'예측값과 관측값 비교':'월별 원천 QC·결측 추이'}</h2>{insights?<div className="h-56 flex flex-col justify-center items-center text-center gap-3 bg-indigo-50 rounded-xl"><BrainCircuit className="w-10 h-10 text-indigo-400"/><p className="font-bold">동일 기간의 평가된 예측 결과 미등록</p><p className="text-xs text-slate-500 px-5">데이터셋·모델 버전·항목·단위·시간대 계약을 갖춘 비교 결과가 필요합니다.</p><Link to={`/forecasting?${linkQuery}`} className="text-blue-700 text-sm underline">예측 기준선 실험 보기 →</Link></div>:<div className="h-56"><ResponsiveContainer width="100%" height="100%"><LineChart data={monthly}><CartesianGrid strokeDasharray="3 3"/><XAxis dataKey="month" tick={{fontSize:10}}/><YAxis domain={[0,100]} unit="%" width={40} tick={{fontSize:10}}/><Tooltip/><Legend wrapperStyle={{fontSize:10}}/><Line dataKey="source_qc_presence_rate" name="QC 표기율" stroke="#2563eb" dot={false} connectNulls={false}/><Line dataKey="missing_value_rate" name="원천 값 결측률" stroke="#a855f7" dot={false} connectNulls={false}/></LineChart></ResponsiveContainer></div>}<p className="text-xs text-slate-500 mt-3">{insights?'예측선·신뢰도·인접 관측소 이상을 임의 생성하지 않습니다.':'분모: 해당 월 보유 행 수. 미수집 기간의 결측률과 다릅니다.'}</p></section>
      <section className={panel}><h2 className="font-bold mb-4">{insights?'근거에서 확인한 검토 사항':'품질 판정에 필요한 연결 조건'}</h2>{insights?<><p className="bg-indigo-50 text-indigo-950 rounded-xl p-4 leading-relaxed">{current?.claim||'선택 범위에 대응하는 문서 사건이 없습니다.'}</p><p className="text-xs text-slate-500 mt-4">보고서의 서술을 인용한 검토 후보입니다. AI 생성 설명이나 확인된 이상 원인이 아닙니다.</p><p className="text-xs text-blue-700 mt-4">{current?.station_name} · {current?.locator}</p></>:(obs?.conditions||[]).map((c:any)=><div key={c.key} className="flex justify-between gap-2 border-b border-slate-100 py-2 text-xs"><span className="font-semibold">{c.name}</span><span className="text-right text-slate-500">{Object.entries(c.counts).map(([k,v])=>`${k} ${fmt(v)}`).join(' · ')}</span></div>)}{!insights&&<p className="text-xs text-slate-500 mt-3">단위: 관측소–항목–수심–월 기록. 관측 행 수나 승인 요청 건수가 아닙니다.</p>}</section>
    </div>
    <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
      <section className={panel}><h2 className="font-bold mb-3">{insights?'문서 사건 연결 관측소 지도':'관측소 × 항목 원천 QC 표기율'}</h2>{insights?<><div className="h-72 rounded-xl overflow-hidden"><MapContainer center={[36,127.5]} zoom={6} style={{height:'100%',width:'100%'}}><OSMBaseLayer/>{markers.map(m=><CircleMarker key={m.code} center={[m.lat,m.lng]} radius={7} pathOptions={{color:'#6366f1'}} eventHandlers={{click:()=>setSelected(events.find((e:any)=>e.station_codes.includes(m.code))?.id||'')}}><Popup>{m.name} · 문서 검토 후보 {m.events}건</Popup></CircleMarker>)}</MapContainer></div><p className="text-xs text-slate-500 mt-2">{referenceError||`기존 PostgreSQL 기준 좌표 참조 · 위치 확인 ${markers.length}/${ranked.length}개소`} · 위험 지도 아님</p></>:<><div className="overflow-auto"><table className="w-full text-[10px] text-center"><thead><tr><th>관측소</th>{matrixItems.map(i=><th key={i} className="p-1 max-w-16 break-all">{i}</th>)}</tr></thead><tbody>{matrixStations.map(s=><tr key={s}><th className="py-2 pr-2 text-left"><Link to={`/profile/${encodeURIComponent(s)}?${linkQuery}`} className="text-blue-700">{channels.find((c:any)=>c.station_code===s)?.station_name||s}</Link></th>{matrixItems.map(i=>{const c=channels.find((c:any)=>c.station_code===s&&c.item_code===i);return <td key={i} className="p-0.5"><span className="block rounded p-2" style={{background:c?.source_qc_presence_rate==null?'#f1f5f9':`rgba(59,130,246,${0.08+c.source_qc_presence_rate/100*0.35})`}}>{c?pct(c.source_qc_presence_rate):'—'}</span></td>;})}</tr>)}</tbody></table></div><p className="text-xs text-slate-500 mt-3">코드순 {matrixStations.length}/{stationCodes.length}개소 · {matrixItems.length}/{items.length}항목. 전체 범위는 필터로 선택하세요. ‘—’는 등록된 채널 없음이며 고장·정상 판정이 아닙니다.</p></>}</section>
      <section className={panel}><h2 className="font-bold mb-3">{insights?'문서 근거 기반 검토 목록':'문서와 연결된 주요 검토 사례'} <span className="text-blue-600 text-sm">{data?events.length:'—'}건</span></h2><div className="max-h-96 overflow-auto space-y-2">{events.map((e:any)=><button key={e.id} aria-pressed={selected===e.id} onClick={()=>setSelected(e.id)} className={`text-left w-full p-3 rounded-xl border ${selected===e.id?'bg-blue-50 border-blue-400':'border-slate-100 hover:bg-slate-50'}`}><span className="font-bold text-sm">{e.station_name} · {e.item_codes.join(', ')}</span><span className="block text-xs text-slate-500 mt-1">{e.period_start} ~ {e.period_end_inclusive}</span><span className="block text-xs mt-2">{e.claim}</span><span className="block text-[10px] text-amber-700 mt-2">기간 대응 {e.decision} / 원인 미승인</span></button>)}{data&&!events.length&&<p className="text-sm text-slate-500">연결 사례 없음 · 안전 또는 정상 판정 아님</p>}</div></section>
      <section className={panel}><h2 className="font-bold mb-4">{insights?'사례 상세 분석 · 판단 근거':'품질 검토 지원 · 판단 근거'}</h2><EvidenceCase event={current} linkQuery={linkQuery}/></section>
    </div>
    {insights&&<section className={panel}><h2 className="font-bold mb-4">AI 분석 업무 흐름</h2><div className="grid grid-cols-2 xl:grid-cols-4 gap-4">{[['1 · 근거 연결','선택 기간·관측소·항목에 문서 사건 연결'],['2 · 평가','Label·평가 데이터셋 확정 후 모델 비교'],['3 · 검토','담당자의 원인·품질 판정과 승인 기록'],['4 · 보고','승인 범위와 문서 인용을 포함해 보고']].map(([t,d])=><div key={t} className="bg-blue-50 rounded-xl p-4"><h3 className="font-bold text-blue-800">{t}</h3><p className="text-xs mt-2 text-slate-600">{d}</p></div>)}</div><div className="flex gap-4 text-sm text-blue-700 mt-4"><Link to={`/reports?${linkQuery}`}>실제 보고서 등록부 →</Link><Link to="/mlops">모델 등록·평가 상태 →</Link></div></section>}
  </div>;
}
