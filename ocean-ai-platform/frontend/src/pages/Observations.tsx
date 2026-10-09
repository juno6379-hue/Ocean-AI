import StationClassifications,{DatasetSourceSelect} from '../components/StationClassifications';
import OSMBaseLayer from '../components/OSMBaseLayer';
import StationQuickView from '../components/StationQuickView';
import ObservationMonthGrid from '../components/ObservationMonthGrid';
import MonthlyReportComparison from '../components/MonthlyReportComparison';
import MetricCompletionPanel,{useMetricCompletion} from '../components/MetricCompletionPanel';
import {countMetric,gridCoverageLabel,gridPercent} from '../data/metricPresentation';
import {observationAvailability} from '../data/observationAvailability';
import {CURRENT_OBSERVATION_MONTH,observationPeriod,applyObservationPeriod} from '../data/observationPeriod';
import {API_BASE_URL,apiFetch} from '../api/client';
import {useState,useEffect} from 'react';
import {Link,useSearchParams} from 'react-router-dom';
import {Building2,RefreshCw,Layers,CalendarDays,Activity,Maximize2,ArrowUpRight} from 'lucide-react';
import {MapContainer,Marker,Popup,Tooltip,useMap} from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

function markerIcon(name:string,selected:boolean) {
  const safe=name.replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]!));
  return L.divIcon({className:'observation-marker',
    html:'<div style="transform:translate(-50%,-50%);display:flex;flex-direction:column;align-items:center"><span style="display:block;width:'+(selected?'22':'13')+'px;height:'+(selected?'22':'13')+'px;background:'+(selected?'#f97316':'#2563eb')+';border:2px solid white;border-radius:100%;box-shadow:0 1px 5px #33415580"></span>'+(selected?'<span style="margin-top:4px;padding:2px 6px;background:white;border-radius:5px;box-shadow:0 1px 5px #33415540;white-space:nowrap;font-size:12px;font-weight:700">'+safe+'</span>':'')+'</div>',
    iconSize:[0,0],iconAnchor:[0,0]});
}

function MapFocus({markers,selected,scope,resetKey}:{markers:any[];selected:any;scope:string;resetKey:number}) {
  const map=useMap();
  useEffect(()=>{
    map.invalidateSize();
    if(markers.length)map.fitBounds(L.latLngBounds(markers.map(m=>[m.lat,m.lng] as [number,number])),{padding:[32,32],maxZoom:7});
    else map.setView([36.3,127.5],6);
  },[map,markers,scope,resetKey]);
  useEffect(()=>{
    if(selected?.lat!=null&&selected?.lng!=null)map.flyTo([selected.lat,selected.lng],9,{duration:.5});
  },[map,selected?.id,selected?.lat,selected?.lng]);
  return null;
}

export default function Observations() {
  const [search,setSearch]=useSearchParams();
  const {source,from,to}=observationPeriod(search);
  const [periodDraft,setPeriodDraft]=useState({from,to}),[periodError,setPeriodError]=useState('');
  useEffect(()=>{setPeriodDraft({from,to});setPeriodError('');},[from,to]);
  const selectedStation=search.get('station')||'';
  const [lake,setLake]=useState<any>(null),[tableData,setTableData]=useState<any[]>([]),[mapMarkers,setMapMarkers]=useState<any[]>([]);
  const [loading,setLoading]=useState(false),[error,setError]=useState(''),[metadataError,setMetadataError]=useState('');
  const [revision,setRevision]=useState(0),[lastUpdated,setLastUpdated]=useState<Date|null>(null),[refreshSeconds,setRefreshSeconds]=useState(0);
  const [stationSearch,setStationSearch]=useState(''),[mapReset,setMapReset]=useState(0);
  const july=from===CURRENT_OBSERVATION_MONTH&&to===CURRENT_OBSERVATION_MONTH;
  const metadataQuery=new URLSearchParams({limit:'10000',...(july?{as_of_month:CURRENT_OBSERVATION_MONTH}:{})}).toString();
  const query=new URLSearchParams({network:search.get('network')||'',sea:search.get('sea')||'',source,from_month:from,to_month:to}).toString();
  const linkQuery=new URLSearchParams({network:search.get('network')||'',sea:search.get('sea')||'',source,from,to}).toString();
  const update=(changes:Record<string,string>)=>setSearch({...Object.fromEntries(search),...changes});
  const chooseStation=(id:string)=>update({station:id,item:''});
  const completion=useMetricCompletion(query,revision,lake?.snapshot);
  const stationMetrics=new Map(completion.data?.raw?.stations.map(row=>[row.station_code,row])||[]);
  const selected=tableData.find(row=>row.id===selectedStation);
  const filtered=tableData.filter(row=>(row.name+' '+row.id).toLowerCase().includes(stationSearch.toLowerCase()));
  const months=observationAvailability(lake?.monthly||[],from,to);
  const metricWaiting=completion.loading?'조회 중':completion.error?'조회 실패':'산정 근거 확인';

  useEffect(()=>{
    if(!refreshSeconds)return;
    const timer=setInterval(()=>setRevision(r=>r+1),refreshSeconds*1000);
    return()=>clearInterval(timer);
  },[refreshSeconds]);
  useEffect(()=>{
    const c=new AbortController();
    setLake(null);setTableData([]);setMapMarkers([]);setError('');setMetadataError('');setLastUpdated(null);setLoading(true);setStationSearch('');
    if(from>to){setError('시작월은 종료월보다 늦을 수 없습니다.');setLoading(false);return()=>c.abort();}
    const read=async(path:string)=>{
      const response=await apiFetch(API_BASE_URL+path,{signal:c.signal});
      if(!response.ok)throw new Error('HTTP '+response.status);
      return response.json();
    };
    Promise.all([read('/lake/summary?'+query),read('/stations?'+metadataQuery).catch(()=>{if(!c.signal.aborted)setMetadataError('위치 기준정보 조회 실패');return [];})])
      .then(([data,metadata])=>{
        if(c.signal.aborted)return;
        const refs=new Map<string,any[]>();
        for(const m of metadata)refs.set(m.station_id,[...(refs.get(m.station_id)||[]),m]);
        const rows=data.stations.map((r:any)=>{
          const matches=refs.get(r.station_code)||[],ref=matches.length===1?matches[0]:null;
          const valid=Number.isFinite(ref?.latitude)&&Number.isFinite(ref?.longitude)&&Math.abs(ref.latitude)<=90&&Math.abs(ref.longitude)<=180;
          return {id:r.station_code,name:r.station_name||r.reference_name||ref?.reference_name||ref?.station_name||r.station_code,
            net:ref?.network_type||'분류 정보 없음',sea:ref?.sea_area||'해역 정보 없음',lat:valid?ref.latitude:null,lng:valid?ref.longitude:null,
            stat:r.held_rows>0?'자료 보유':'자료 없음',time:r.last_clock||'시각 기록 없음',first:r.first_clock,
            held_rows:r.held_rows,items:r.items,months:r.held_months,
            note:r.items+'개 항목 · '+r.held_months+'개월 자료'};
        });
        setLake(data);setTableData(rows);setMapMarkers(rows.filter((r:any)=>r.lat!=null&&r.lng!=null));setLastUpdated(new Date());
      }).catch(e=>{if(!c.signal.aborted)setError('관측자료 조회 실패: '+e.message);})
      .finally(()=>{if(!c.signal.aborted)setLoading(false);});
    return()=>c.abort();
  },[query,metadataQuery,revision]);

  return <div className="p-4 lg:p-5 space-y-4 bg-slate-50 min-h-full text-slate-800">
    <header className="flex flex-wrap justify-between items-center gap-3">
      <div><div className="flex gap-3 items-center"><h2 className="text-2xl font-bold text-slate-900">관측 현황</h2><span className="text-[11px] text-blue-700 rounded-full bg-blue-50 border border-blue-100 px-2 py-1">{july?'2026년 7월 현황':'기간별 자료 조회'}</span></div>
      <p className="text-xs text-slate-500 mt-1.5">관측소를 선택해 관측항목, 최근 자료와 기간별 공백을 확인하세요.</p></div>
      <div className="flex items-center gap-2 text-[11px] text-slate-500">
        <span>{lastUpdated?'조회 '+lastUpdated.toLocaleTimeString('ko-KR',{timeZone:'Asia/Seoul'}):'조회 대기'}</span>
        <button aria-label="새로고침" disabled={loading} onClick={()=>setRevision(r=>r+1)} className="border rounded-lg bg-white p-2 hover:bg-slate-50"><RefreshCw className={'w-4 h-4 '+(loading?'animate-spin':'')}/></button>
        <select aria-label="자동 갱신" value={refreshSeconds} onChange={e=>setRefreshSeconds(Number(e.target.value))} className="border rounded-lg p-2 bg-white"><option value={0}>수동 갱신</option><option value={60}>1분마다</option><option value={300}>5분마다</option></select>
      </div>
    </header>
    <form aria-label="관측소와 기간 선택" onSubmit={e=>{e.preventDefault();const fields=new FormData(e.currentTarget);const next=applyObservationPeriod(search,String(fields.get('from')||''),String(fields.get('to')||''));if(next){setSearch(next);setPeriodError('');}else setPeriodError('시작월과 종료월을 올바르게 선택하세요.');}} className="flex flex-wrap gap-3 items-end rounded-xl border border-slate-200 bg-white p-3">
      <StationClassifications compact/>
      <label className="text-xs font-semibold flex-1 min-w-44 max-w-72">관측소 선택
        <select aria-label="관측소 선택" value={selected?.id||''} disabled={loading} onChange={e=>chooseStation(e.target.value)} className="block mt-1 border border-slate-200 rounded-lg p-2 w-full bg-white font-normal">
          <option value="">지도로 전체 보기</option>{tableData.map(row=><option key={row.id} value={row.id}>{row.name+' · '+row.id}</option>)}
        </select>
      </label>
      <label className="text-xs">시작월<input name="from" required aria-label="시작월" type="month" value={periodDraft.from} onInput={e=>{const value=e.currentTarget.value;setPeriodDraft(p=>({...p,from:value}));}} onChange={e=>{const value=e.target.value;setPeriodDraft(p=>({...p,from:value}));}} className="block border border-slate-200 rounded-lg p-2 mt-1 bg-white"/></label>
      <label className="text-xs">종료월<input name="to" required aria-label="종료월" type="month" value={periodDraft.to} onInput={e=>{const value=e.currentTarget.value;setPeriodDraft(p=>({...p,to:value}));}} onChange={e=>{const value=e.target.value;setPeriodDraft(p=>({...p,to:value}));}} className="block border border-slate-200 rounded-lg p-2 mt-1 bg-white"/></label>
      <button type="submit" className="text-xs font-semibold text-white bg-blue-600 rounded-lg px-3 py-2 hover:bg-blue-700">기간 적용</button>
      {!july&&<button type="button" className="text-xs text-blue-700 p-2" onClick={()=>update({from:CURRENT_OBSERVATION_MONTH,to:CURRENT_OBSERVATION_MONTH})}>7월 기준으로</button>}
      <button type="button" className="text-xs text-slate-500 p-2" onClick={()=>update({sea:'',network:'',station:'',item:''})}>선택 초기화</button>
      {periodError&&<p role="alert" className="basis-full text-xs text-red-700">{periodError}</p>}
      {(periodDraft.from!==from||periodDraft.to!==to)&&<p role="status" className="basis-full text-[11px] text-slate-500">기간 적용을 누르면 선택한 기간으로 조회합니다. 현재 결과: {from} ~ {to}</p>}
    </form>
    {error&&<p role="alert" className="text-sm text-red-700 bg-red-50 border border-red-100 rounded-lg p-3">{error}</p>}
    <div className="grid grid-cols-2 xl:grid-cols-4 gap-3">{[
      ['자료 있는 관측소',lake?countMetric(lake.totals.stations):'조회 중','선택 해역·관측망',Building2],
      ['관측항목',lake?countMetric(lake.totals.items)+'종':'조회 중','선택 원천의 항목 코드',Layers],
      ['자료 있는 월',lake?months.filter(m=>m.held).length+'/'+months.length+'개월':'조회 중',from+' ~ '+to,CalendarDays],
      ['자료 채움 (참고)',completion.data?.raw?gridPercent(completion.data.raw.grid):metricWaiting,gridCoverageLabel(completion.data)||'원문 시각의 참고 격자',Activity],
    ].map(([title,value,note,Icon]:any)=><article key={title} className="flex items-center gap-3 rounded-xl border border-slate-200 bg-white px-4 py-3"><Icon className="w-5 h-5 shrink-0 text-blue-600"/><div className="min-w-0"><h3 className="text-[11px] text-slate-500">{title}</h3><p className="text-lg font-bold text-slate-900">{value}</p><p className="text-[10px] text-slate-500 truncate" title={note}>{note}</p></div></article>)}</div>
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 items-start">
      <section aria-label="관측소 지도" className="lg:col-span-2 rounded-2xl border border-slate-200 bg-white shadow-sm overflow-hidden">
        <div className="flex flex-wrap justify-between items-center gap-2 px-4 py-3"><div><h3 className="text-sm font-bold">관측소 지도</h3><p className="text-[11px] text-slate-500 mt-1">{loading?'위치 조회 중':(search.get('sea')||'전체 해역')+' · 지도에 표시 '+mapMarkers.length+'개소'}{selected?' · 선택 '+selected.name:''}</p></div>
          <button onClick={()=>setMapReset(v=>v+1)} className="flex items-center gap-1.5 border border-slate-200 rounded-lg p-2 text-xs hover:bg-slate-50"><Maximize2 className="w-3.5 h-3.5"/>전체 위치</button></div>
        <div className="h-[460px] lg:h-[560px] relative">
          <MapContainer center={[36.3,127.5]} zoom={6} style={{height:'100%',width:'100%'}} zoomControl={true} scrollWheelZoom={true}>
            <OSMBaseLayer/><MapFocus markers={mapMarkers} selected={selected} scope={query} resetKey={mapReset}/>
            {mapMarkers.map(marker=><Marker key={marker.id} position={[marker.lat,marker.lng]} icon={markerIcon(marker.name,marker.id===selectedStation)} title={marker.name+' '+marker.id} alt={marker.name} eventHandlers={{click:()=>chooseStation(marker.id)}}>
              <Tooltip direction="top" offset={[0,-12]}>{marker.name+' · '+marker.net}</Tooltip>
              <Popup><p className="font-bold">{marker.name}</p><p>{marker.id+' · '+marker.sea}</p><p>{marker.items+'개 항목 · 마지막 자료 '+marker.time.replace('T',' ')}</p><Link className="text-blue-700 underline" to={'/profile/'+encodeURIComponent(marker.id)+'?'+linkQuery}>관측값 자세히</Link></Popup>
            </Marker>)}
          </MapContainer>
          <div className="absolute bottom-3 left-3 z-[400] rounded-lg border border-slate-200 bg-white/95 px-3 py-2 text-[11px] shadow-sm flex gap-3"><span><span className="text-blue-600">●</span> 자료 보유</span><span><span className="text-orange-500">●</span> 선택 관측소</span></div>
        </div>
        <div className="px-4 py-2 text-[11px] text-slate-500">{metadataError||'지도의 점을 누르거나 상단에서 관측소를 선택하세요.'}
          {!loading&&mapMarkers.length<tableData.length&&<span> · 좌표 없는 {tableData.length-mapMarkers.length}개소는 목록에서 선택</span>}
          {selected?.lat==null&&selected&&<span> · {selected.name}의 위치 좌표가 없습니다.</span>}
        </div>
      </section>
      <StationQuickView station={selected} source={source} from={from} to={to} snapshot={lake?.snapshot} receiptDiagnostics={stationMetrics.get(selectedStation)?.receipt_diagnostics} revision={revision}/>
    </div>
    <section id="observation-table" aria-label="관측소 목록" className="rounded-2xl border border-slate-200 bg-white p-4">
      <div className="flex flex-wrap justify-between items-center gap-3 mb-3"><div><h3 className="text-sm font-bold">관측소 목록</h3><p className="text-[11px] text-slate-500 mt-1">조회 범위 {filtered.length}개소 · 관측소를 선택하면 지도로 이동합니다.</p></div>
        <input aria-label="관측소 검색" placeholder="관측소 이름·코드로 찾기" value={stationSearch} onChange={e=>setStationSearch(e.target.value)} className="border border-slate-200 rounded-lg px-3 py-2 text-xs w-56"/></div>
      <div className="overflow-auto max-h-[420px]"><table className="w-full min-w-[700px] text-xs text-left"><thead className="sticky top-0 bg-slate-50 text-slate-500"><tr>
        {['관측소','해역 · 관측망','관측항목','자료 있는 월','마지막 관측자료 (원문)','자료 채움 (참고)','상세'].map(title=><th key={title} className="px-3 py-3 font-medium">{title}</th>)}
      </tr></thead><tbody>{filtered.map(row=><tr key={row.id} className={'border-t border-slate-100 '+(row.id===selectedStation?'bg-blue-50':'hover:bg-slate-50')}>
        <td className="px-3 py-3"><button aria-pressed={row.id===selectedStation} className="text-blue-700 text-left font-semibold hover:underline" onClick={()=>chooseStation(row.id)}>{row.name}<span className="block text-[10px] text-slate-500 font-normal mt-1">{row.id}</span></button></td>
        <td className="px-3 py-3">{row.sea}<span className="block text-[10px] text-slate-500 mt-1">{row.net}</span></td>
        <td className="px-3 py-3">{row.items}개</td><td className="px-3 py-3">{row.months}개월</td>
        <td className="px-3 py-3 whitespace-nowrap">{row.time.replace('T',' ')}</td>
        <td className="px-3 py-3" title={stationMetrics.get(row.id)?.grid.reason}>{completion.data?.raw?gridPercent(stationMetrics.get(row.id)?.grid):metricWaiting}</td>
        <td className="px-3 py-3"><Link aria-label={row.name+' 관측값 상세'} className="inline-flex gap-1 items-center text-blue-700" to={'/profile/'+encodeURIComponent(row.id)+'?'+linkQuery}>보기<ArrowUpRight className="w-3 h-3"/></Link></td>
      </tr>)}
      {!filtered.length&&<tr><td colSpan={7} className="text-center py-10 text-slate-500">{loading?'관측소 조회 중…':error?'자료 조회 실패':'선택 해역·기간·검색 조건에 자료가 없습니다.'}</td></tr>}
      </tbody></table></div>
      {lake&&<div className="border-t border-slate-100 pt-4 mt-4"><ObservationMonthGrid rows={lake.monthly} from={from} to={to} onMonth={month=>update({from:month,to:month})}/></div>}
    </section>
    <details className="rounded-xl border border-slate-200 bg-white p-3 text-xs">
      <summary className="cursor-pointer text-slate-600 font-semibold">자료 출처·산정 근거</summary>
      <div className="mt-4 space-y-3"><DatasetSourceSelect source={source}/><p className="text-slate-500">보유 원천 {lake?countMetric(lake.totals.held_rows):'조회 중'}행 · 수집률·QC 정상률은 승인된 기준으로 별도 판단합니다.</p><MetricCompletionPanel {...completion}/></div>
    </details>
    <details className="rounded-xl border border-slate-200 bg-white p-3 text-xs">
      <summary className="cursor-pointer text-slate-600 font-semibold">7월 월간해양정보 대조</summary><div className="mt-3"><MonthlyReportComparison source={source} from={from} to={to}/></div>
    </details>
  </div>;
}
