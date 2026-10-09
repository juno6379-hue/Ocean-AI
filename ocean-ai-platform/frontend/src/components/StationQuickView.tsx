import {useEffect,useMemo,useState} from 'react';
import {Link} from 'react-router-dom';
import {MapPin,ArrowUpRight} from 'lucide-react';
import {API_BASE_URL,apiFetch} from '../api/client';
import {nativeReceiptPresentation} from '../data/nativeReceiptPresentation';
import {observationItemLabel} from '../data/observationAvailability';
import ObservationMonthGrid from './ObservationMonthGrid';

export default function StationQuickView({station,source,from,to,snapshot,receiptDiagnostics,revision=0}:{station:any;source:string;from:string;to:string;snapshot?:string;receiptDiagnostics?:unknown;revision?:number}) {
  const [data,setData]=useState<any>(null),[error,setError]=useState(''),[tab,setTab]=useState('자료');
  const [channelKey,setChannelKey]=useState('');
  const [preview,setPreview]=useState<any>(null),[previewError,setPreviewError]=useState('');
  const query=new URLSearchParams({source,from_month:from,to_month:to}).toString();
  const linkQuery=new URLSearchParams({source,from,to}).toString();
  useEffect(()=>{
    setData(null);setError('');setTab('자료');setChannelKey('');
    if(!station)return;
    const c=new AbortController();
    apiFetch(API_BASE_URL+'/lake/stations/'+encodeURIComponent(station.id)+'?'+query,{signal:c.signal})
      .then(async r=>{if(!r.ok)throw new Error('HTTP '+r.status);return r.json();})
      .then(d=>{if(c.signal.aborted)return;if(snapshot&&d.snapshot!==snapshot)throw new Error('검증본 전환 중');setData(d);})
      .catch(e=>{if(!c.signal.aborted)setError('상세 조회 실패: '+e.message);});
    return()=>c.abort();
  },[station?.id,query,snapshot,revision]);
  const rows=data?.months||[];
  const channels=useMemo(()=>{
    const map=new Map<string,any>();
    for(const row of data?.months||[]){
      if(!(row.held_rows>0))continue;
      const key=JSON.stringify([row.item_code,row.depth_step,row.depth_from,row.depth_to]);
      if(!map.has(key))map.set(key,{key,item:row.item_code,depth:[row.depth_step,row.depth_from,row.depth_to],months:[]});
      map.get(key).months.push(row);
    }
    return [...map.values()];
  },[data]);
  const channel=channels.find(c=>c.key===channelKey)||channels.find(c=>c.item==='TIDE_LEVEL')||channels.find(c=>c.item==='TIDE_LEVEL_VEGA')||channels[0];
  const latestMonth=channel ? [...channel.months].map((r:any)=>String(r.month).slice(0,7)).sort().at(-1) : '';
  useEffect(()=>{
    setPreview(null);setPreviewError('');
    if(!station||!channel||!latestMonth)return;
    const c=new AbortController();
    const p=new URLSearchParams({source,station:station.id,item:channel.item,month:latestMonth,limit:'24',tail:'true'});
    ['depth_step','depth_from','depth_to'].forEach((key,i)=>{if(channel.depth[i]!=null)p.set(key,String(channel.depth[i]));});
    apiFetch(API_BASE_URL+'/lake/series?'+p,{signal:c.signal})
      .then(async r=>{if(!r.ok)throw new Error('HTTP '+r.status);return r.json();})
      .then(d=>{
        if(c.signal.aborted)return;
        if(d.snapshot!==snapshot||d.source!==source||d.station!==station.id||d.item!==channel.item||d.month!==latestMonth||d.tail!==true)
          throw new Error('조회 범위 확인 실패');
        setPreview(d);
      }).catch(e=>{if(!c.signal.aborted)setPreviewError('관측값 조회 실패: '+e.message);});
    return()=>c.abort();
  },[station?.id,source,channel,latestMonth,snapshot,revision]);
  const receipt=nativeReceiptPresentation(receiptDiagnostics);
  const itemCount=new Set(rows.filter((r:any)=>r.held_rows>0).map((r:any)=>r.item_code)).size;
  return <aside className="bg-white border border-slate-200 rounded-2xl p-4 min-w-0 self-start shadow-sm" aria-label="선택 관측소">
    <h3 className="text-sm font-bold text-slate-800 flex gap-2 items-center"><MapPin className="w-4 h-4 text-blue-600"/>선택 관측소</h3>
    {!station?<p className="text-sm text-slate-500 py-12">지도나 관측소 선택 메뉴에서 관측소를 고르세요.</p>:<>
      <div className="mt-3 border-b border-slate-100 pb-4">
        <h4 className="text-xl font-bold text-slate-900">{station.name}</h4>
        <p className="text-xs text-slate-500 mt-1">{station.id} · {station.sea} · {station.net}</p>
        <p className="text-xs text-blue-700 mt-3">{from} ~ {to} · {itemCount}개 관측항목</p>
        <p className="text-xs text-slate-500 mt-1">마지막 자료 {station.time.replace('T',' ')}</p>
      </div>
      <div className="flex border-b border-slate-200 my-3" role="tablist" aria-label="관측소 상세 종류">{['자료','센서·QC','기간'].map(t=><button role="tab" aria-selected={tab===t} key={t} onClick={()=>setTab(t)} className={'flex-1 text-xs p-2 '+(tab===t?'border-b-2 border-blue-600 text-blue-700 font-bold':'text-slate-500')}>{t}</button>)}</div>
      {error&&<p role="alert" className="text-xs text-red-700">{error}</p>}
      {!data&&!error&&<p role="status" className="text-xs py-8">관측항목 조회 중…</p>}
      {tab==='자료'&&data&&<>
        <label className="text-xs font-semibold block">관측항목·수심
          <select aria-label="관측항목·수심" value={channel?.key||''} onChange={e=>setChannelKey(e.target.value)} className="block w-full rounded-lg border border-slate-200 p-2 mt-2 text-xs bg-white">
            {channels.map(c=><option key={c.key} value={c.key}>{observationItemLabel(c.item)}{c.depth.some((d:any)=>d!=null)?' · 수심 코드 '+c.depth.map((d:any)=>d??'—').join('/') : ''}</option>)}
          </select>
        </label>
        {channel&&<div className="mt-4">
          <p className="text-xs font-bold">최근 자료 미리보기</p>
          <p className="text-[11px] text-slate-500 mt-1">{channel.item} · {latestMonth} · 원문 관측시각 순</p>
          {previewError&&<p role="alert" className="text-xs text-red-700 py-3">{previewError}</p>}
          {!preview&&!previewError&&<p role="status" className="text-xs text-slate-500 py-8">실측값 조회 중…</p>}
          {preview&&<div className="mt-2 max-h-44 overflow-auto rounded-lg border border-slate-100"><table className="w-full text-[11px] text-left">
            <thead className="bg-slate-50 sticky top-0"><tr><th className="p-2 font-medium">관측시각</th><th className="p-2 font-medium text-right">원천값</th><th className="p-2 font-medium">원문 QC</th></tr></thead>
            <tbody>{preview.rows.map((r:any)=><tr key={r.filename+':'+r.file_row_number} className="border-t border-slate-100"><td className="p-2 whitespace-nowrap">{String(r.observed_time_raw).replace('T',' ')}</td><td className="p-2 text-right">{r.value_raw==null?'NULL':String(r.value_raw)}</td><td className="p-2">{r.source_qc_raw==null?'—':String(r.source_qc_raw)}</td></tr>)}</tbody>
          </table>{!preview.rows.length&&<p className="p-3 text-xs text-slate-500">선택 채널에 해석 가능한 관측시각의 값이 없습니다.</p>}</div>}
          <p className="text-[10px] text-slate-500 mt-1">최대 24건 · 단위 적용 전 원천값</p>
          <div className="border-t border-slate-100 mt-4 pt-3"><ObservationMonthGrid rows={channel.months} from={from} to={to}/></div>
        </div>}
        {!channels.length&&<p className="text-xs text-slate-500 py-4">선택 기간에 보유 관측항목이 없습니다.</p>}
      </>}
      {tab==='센서·QC'&&<div className="space-y-3 text-xs">{[['물리 센서','physical_sensor_id'],['센서 대응','sensor_decision'],['단위 적용','unit_application_decision'],['시간대','timezone_decision'],['QC 근거','qc_evidence_decision'],['QC 승인','qc_approval_decision']].map(([label,key])=>{const counts:Record<string,number>={};rows.forEach((r:any)=>{const v=r[key]||'미확정';counts[v]=(counts[v]||0)+1;});return <div key={key} className="border-b pb-2 border-slate-100"><p className="font-bold">{label}</p><p className="text-slate-500 mt-1">{Object.entries(counts).map(([k,v])=>k+' '+v+'기록').join(' · ')||'기록 없음'}</p></div>;})}</div>}
      {tab==='기간'&&<dl className="text-xs space-y-4">
        <div><dt className="text-slate-500">첫 관측시각 (원문)</dt><dd className="mt-1 font-semibold break-words">{station.first||'시각 기록 없음'}</dd></div>
        <div><dt className="text-slate-500">마지막 관측시각 (원문)</dt><dd className="mt-1 font-semibold break-words">{station.time}</dd></div>
        <div><dt className="text-slate-500">수신·관측 시계차 (원문)</dt><dd className="mt-1 font-semibold" title={receipt.title}>{receipt.value}{receipt.note&&<span className="block text-slate-500 mt-1">{receipt.note}</span>}</dd></div>
        <details className="text-slate-500"><summary className="cursor-pointer">운영기간·시간대 확인 조건</summary><p className="mt-2">관측소 운영·센서 설치 기간과 원천 시간대는 별도 이력에서 확인합니다.</p></details>
      </dl>}
      <Link className="flex items-center justify-center gap-1 text-xs font-bold text-blue-700 bg-blue-50 border border-blue-100 rounded-lg p-3 mt-4" to={'/profile/'+encodeURIComponent(station.id)+'?'+linkQuery+(channel?'&item='+encodeURIComponent(channel.item):'')}>관측값·QC·월별 자료 자세히<ArrowUpRight className="w-4 h-4"/></Link>
    </>}
  </aside>;
}
