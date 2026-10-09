import StationClassifications,{DatasetSourceSelect} from '../components/StationClassifications';
import OSMBaseLayer from '../components/OSMBaseLayer';
import StationQuickView from '../components/StationQuickView';
import ObservationMonthGrid from '../components/ObservationMonthGrid';
import MetricCompletionPanel,{useMetricCompletion} from '../components/MetricCompletionPanel';
import {countMetric,gridPercent,qcPresencePercent} from '../data/metricPresentation';
import {observationAvailability} from '../data/observationAvailability';
import {operatingState,stationPage,facilityColor} from '../data/observationWorkspace';
import {DEFAULT_OBSERVATION_DAY,systemObservationTime,matchesObservationCutoff} from '../data/observationCutoff';
import {CURRENT_OBSERVATION_MONTH,observationPeriod,applyObservationPeriod} from '../data/observationPeriod';
import {API_BASE_URL,apiFetch} from '../api/client';
import {useState,useEffect,useMemo} from 'react';
import {Link,useSearchParams} from 'react-router-dom';
import {Building2,RefreshCw,CalendarDays,Activity,Maximize2,ArrowRight,ChevronLeft,ChevronRight,Search,MapPin,Lightbulb,ShieldCheck,Database,Waves,CheckCircle2,RotateCcw,TriangleAlert,CircleAlert,BarChart3 as BarChartIcon} from 'lucide-react';
import {MapContainer,Marker,Popup,Tooltip,useMap,TileLayer} from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import '../styles/observations.css';

function SatelliteBaseLayer() {
  const [failed,setFailed]=useState(false);
  return <><TileLayer url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}" maxZoom={19}
    attribution="Imagery &copy; Esri, Vantor, Earthstar Geographics, GIS User Community"
    eventHandlers={{tileerror:()=>setFailed(true),loading:()=>setFailed(false)}}/>
    {failed&&<div role="status" className="obs-tile-error">위성 배경 일부를 불러오지 못했습니다. 일반지도로 전환할 수 있습니다.</div>}</>;
}

function markerIcon(name:string,selected:boolean,color:string) {
  const safe=name.replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]!));
  return L.divIcon({className:'observation-marker',
    html:'<div style="transform:translate(-50%,-50%);display:flex;flex-direction:column;align-items:center"><span style="display:flex;align-items:center;justify-content:center;width:'+(selected?'24':'16')+'px;height:'+(selected?'24':'16')+'px;background:'+color+';border:2px solid white;border-radius:100%;box-shadow:'+(selected?'0 0 0 5px #1684ff30,':'')+'0 1px 5px #33415580"><i style="width:4px;height:4px;border-radius:50%;background:white"></i></span>'+(selected?'<span style="margin-top:4px;padding:2px 6px;background:white;border-radius:5px;box-shadow:0 1px 5px #33415540;white-space:nowrap;font-size:12px;font-weight:700">'+safe+'</span>':'')+'</div>',
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
    if(selected?.lat!=null&&selected?.lng!=null)map.panInside([selected.lat,selected.lng],{padding:[60,60],animate:true});
  },[map,selected?.id,selected?.lat,selected?.lng]);
  return null;
}

export default function Observations() {
  const [search,setSearch]=useSearchParams();
  const {source,from,to}=observationPeriod(search);
  const [initialClock]=useState(()=>systemObservationTime());
  const asOfDay=search.get('as_of_day')||DEFAULT_OBSERVATION_DAY;
  const asOfTime=search.get('as_of_time')||initialClock;
  const [dayDraft,setDayDraft]=useState(asOfDay);
  useEffect(()=>{setDayDraft(asOfDay);},[asOfDay]);
  useEffect(()=>{if(!search.has('as_of_day')||!search.has('as_of_time'))setSearch(p=>{const n=new URLSearchParams(p);if(!n.has('as_of_day'))n.set('as_of_day',asOfDay);if(!n.has('as_of_time'))n.set('as_of_time',asOfTime);return n;},{replace:true});},[asOfDay,asOfTime,search,setSearch]);
  const [periodDraft,setPeriodDraft]=useState({from,to}),[periodError,setPeriodError]=useState('');
  useEffect(()=>{setPeriodDraft({from,to});setPeriodError('');},[from,to]);
  const selectedStation=search.get('station')||'';
  const [lake,setLake]=useState<any>(null),[tableData,setTableData]=useState<any[]>([]),[mapMarkers,setMapMarkers]=useState<any[]>([]);
  const [loading,setLoading]=useState(false),[error,setError]=useState(''),[metadataError,setMetadataError]=useState('');
  const [revision,setRevision]=useState(0),[lastUpdated,setLastUpdated]=useState<Date|null>(null),[refreshSeconds,setRefreshSeconds]=useState(0);
  const [stationSearch,setStationSearch]=useState(''),[mapReset,setMapReset]=useState(0),[page,setPage]=useState(1),[stateFilter,setStateFilter]=useState(''),[sortNewest,setSortNewest]=useState(false),[mapLayer,setMapLayer]=useState('street');
  const july=from===CURRENT_OBSERVATION_MONTH&&to===CURRENT_OBSERVATION_MONTH;
  const metadataQuery=new URLSearchParams({limit:'10000',...(july?{as_of_month:CURRENT_OBSERVATION_MONTH}:{})}).toString();
  const query=new URLSearchParams({network:search.get('network')||'',sea:search.get('sea')||'',source,from_month:from,to_month:to,as_of_day:asOfDay,as_of_time:asOfTime}).toString();
  const linkQuery=new URLSearchParams({network:search.get('network')||'',sea:search.get('sea')||'',source,from,to,as_of_day:asOfDay,as_of_time:asOfTime}).toString();
  const update=(changes:Record<string,string>)=>setSearch({...Object.fromEntries(search),...changes});
  const chooseStation=(id:string)=>{const index=filtered.findIndex(row=>row.id===id);setPage(index>=0?Math.floor(index/10)+1:1);update({station:id,item:''});};
  const completion=useMetricCompletion(query,revision,lake?.snapshot);
  const stationMetrics=new Map(completion.data?.raw?.stations.map(row=>[row.station_code,row])||[]);
  const selected=tableData.find(row=>row.id===selectedStation);
  const filtered=useMemo(()=>tableData.filter(row=>(row.name+' '+row.id+' '+row.sea+' '+row.net).toLowerCase().includes(stationSearch.toLowerCase())&&(!stateFilter||row.operation?.state===stateFilter))
    .sort((a,b)=>sortNewest?b.time.localeCompare(a.time)||a.id.localeCompare(b.id):a.id.localeCompare(b.id)),[tableData,stationSearch,stateFilter,sortNewest]);
  const paged=stationPage(filtered,page);
  useEffect(()=>setPage(1),[stationSearch,stateFilter,query]);
  useEffect(()=>{const index=filtered.findIndex(row=>row.id===selectedStation);if(index>=0)setPage(Math.floor(index/10)+1);},[selectedStation,filtered]);
  const pageNumbers=Array.from({length:Math.min(5,paged.pages)},(_,i)=>Math.max(1,Math.min(paged.page-2,paged.pages-4))+i);
  const seaCounts=[...new Set(tableData.map(row=>row.sea))].map(sea=>({sea,count:tableData.filter(row=>row.sea===sea).length}));
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
    if(from>to||to>asOfDay.slice(0,7)){setError('조회 기간은 기준일이 속한 월까지 선택하세요.');setLoading(false);return()=>c.abort();}
    const read=async(path:string)=>{
      const response=await apiFetch(API_BASE_URL+path,{signal:c.signal});
      if(!response.ok)throw new Error('HTTP '+response.status);
      return response.json();
    };
    Promise.all([read('/lake/summary?'+query),read('/stations?'+metadataQuery).catch(()=>{if(!c.signal.aborted)setMetadataError('위치 기준정보 조회 실패');return [];})])
      .then(([data,metadata])=>{
        if(c.signal.aborted)return;
        if(!matchesObservationCutoff(data,asOfDay,asOfTime))throw new Error('관측 기준일시 응답 불일치');
        const refs=new Map<string,any[]>();
        for(const m of metadata)refs.set(m.station_id,[...(refs.get(m.station_id)||[]),m]);
        const rows=data.stations.map((r:any)=>{
          const matches=refs.get(r.station_code)||[],ref=matches.length===1?matches[0]:null;
          const valid=Number.isFinite(ref?.latitude)&&Number.isFinite(ref?.longitude)&&Math.abs(ref.latitude)<=90&&Math.abs(ref.longitude)<=180;
          return {id:r.station_code,name:r.station_name||r.reference_name||ref?.reference_name||ref?.station_name||r.station_code,
            net:ref?.network_type||'분류 정보 없음',sea:ref?.sea_area||'해역 정보 없음',lat:valid?ref.latitude:null,lng:valid?ref.longitude:null,
            stat:r.held_rows>0?'자료 보유':'자료 없음',time:r.last_clock||'시각 기록 없음',first:r.first_clock,
            held_rows:r.held_rows,items:r.items,months:r.held_months,
            operation:r.operation,
            note:r.items+'개 항목 · '+r.held_months+'개월 자료'};
        });
        setLake(data);setTableData(rows);setMapMarkers(rows.filter((r:any)=>r.lat!=null&&r.lng!=null));setLastUpdated(new Date());
      }).catch(e=>{if(!c.signal.aborted)setError('관측자료 조회 실패: '+e.message);})
      .finally(()=>{if(!c.signal.aborted)setLoading(false);});
    return()=>c.abort();
  },[query,metadataQuery,revision,asOfDay,asOfTime,from,to]);


  return <div className="observation-workspace">
    <div className="obs-masthead">
      <label className="obs-global-search"><Search size={17}/><input aria-label="관측소 검색" placeholder="관측소명, 지역, 해역을 검색하세요…" value={stationSearch} onChange={e=>setStationSearch(e.target.value)}/><span>관측소 검색</span></label>
      <svg className="obs-masthead-waves" viewBox="0 0 600 80" preserveAspectRatio="none" aria-hidden="true"><path d="M0 65 Q80 5 160 50 T340 45 T600 20 V80 H0Z" fill="#a9dcf9"/><path d="M0 78 Q100 30 230 64 T600 43 V80 H0Z" fill="#72c5ee"/><path d="M0 80 Q180 45 340 75 T600 55 V80Z" fill="#218aca"/></svg>
      <div className="obs-masthead-message">데이터로 만드는<br/><strong>안전한 바다, 지속 가능한 미래</strong></div><span className="obs-view-mode"><Database size={14}/>저장자료 조회</span>
    </div>
    <div className="obs-page-body">
      <div className="obs-breadcrumb"><Link to={'/'+(search.size?'?'+search:'')}>홈</Link><ChevronRight size={12}/><span>관측 현황</span><time>{lastUpdated?'조회 '+lastUpdated.toLocaleString('ko-KR',{timeZone:'Asia/Seoul',hour12:false})+' KST':'조회 대기'}</time></div>
      <header className="obs-page-heading">
        <div className="obs-title"><div><h2>관측 현황</h2><span>{asOfDay}</span></div><p>관측 기준 {asOfDay} {asOfTime} · 모든 관측소에 동일한 기준시각 적용</p></div>
        <Link to={'/qc?'+linkQuery+(selectedStation?'&station='+encodeURIComponent(selectedStation):'')} className="obs-ai-entry"><span className="obs-ai-symbol">AI</span><span><strong>AI 품질 분석</strong><small>관측자료의 품질 근거와 분석 결과를 함께 확인하세요.</small></span><ChevronRight size={21}/></Link>
        <form className="obs-period-form" aria-label="조회 기간" onSubmit={e=>{e.preventDefault();const f=new FormData(e.currentTarget);const day=String(f.get('day')||'');const next=applyObservationPeriod(search,String(f.get('from')||''),String(f.get('to')||''));if(next&&day&&next.get('to')!<=day.slice(0,7)){next.set('as_of_day',day);next.set('as_of_time',systemObservationTime());setSearch(next);setPeriodError('');}else setPeriodError('조회 기간은 관측 기준일이 속한 월까지 선택하세요.');}}>
          <span className="obs-form-title">조회 기간</span><div className="obs-period-inputs"><CalendarDays size={15}/><input name="from" required aria-label="시작월" type="month" value={periodDraft.from} onInput={e=>{const value=e.currentTarget.value;setPeriodDraft(p=>({...p,from:value}));}} onChange={e=>{const value=e.currentTarget.value;setPeriodDraft(p=>({...p,from:value}));}}/><span>~</span><input name="to" required aria-label="종료월" type="month" value={periodDraft.to} onInput={e=>{const value=e.currentTarget.value;setPeriodDraft(p=>({...p,to:value}));}} onChange={e=>{const value=e.currentTarget.value;setPeriodDraft(p=>({...p,to:value}));}}/></div>
          <button className="obs-primary-button" type="submit">조회하기</button><div className="obs-period-shortcuts"><label>기준일 <input type="date" name="day" aria-label="관측 기준일" required value={dayDraft} onChange={e=>setDayDraft(e.target.value)}/></label><button type="button" className={july?'active':''} onClick={()=>update({from:CURRENT_OBSERVATION_MONTH,to:CURRENT_OBSERVATION_MONTH})}>7월</button><button type="button" onClick={()=>update({from:'2026-05',to:CURRENT_OBSERVATION_MONTH})}>3개월</button></div>
          {periodError&&<p role="alert" className="obs-error">{periodError}</p>}{(periodDraft.from!==from||periodDraft.to!==to)&&<p role="status" className="obs-caption">현재 결과: {from} ~ {to} · 조회하기로 적용</p>}
        </form>
      </header>
      {error&&<p role="alert" className="obs-error obs-error-banner">{error}</p>}
      <div className="obs-summary-cards">{[
        ['전체 관측소',lake?countMetric(lake.totals.stations):'조회 중','개소','선택 원천에 자료가 있는 관측소',Building2,'blue'],
        ['정상 운영',lake?(lake.operation_summary?.normal??'—'):'조회 중','개소','기준일 운영 기록 확인 필요',ShieldCheck,'emerald'],
        ['주의 필요',lake?(lake.operation_summary?.warning??'—'):'조회 중','개소','기준일 운영 기록 확인 필요',CircleAlert,'amber'],
        ['이상 발생',lake?(lake.operation_summary?.abnormal??'—'):'조회 중','개소','기준일 장애 기록 확인 필요',TriangleAlert,'rose'],
        ['최근 수집률',lake?(lake.operation_summary?.collection_rate==null?'—':lake.operation_summary.collection_rate+'%'):'조회 중','','예정 관측건수 확인 필요',BarChartIcon,'violet'],
      ].map(([title,value,unit,note,Icon,tone]:any)=><article className={'obs-summary-card '+tone} key={title}><div className="obs-summary-main"><span className="obs-summary-icon"><Icon size={23}/></span><div><h3>{title}</h3><p>{value}<small>{unit}</small></p></div></div><p className="obs-summary-note"><span className="obs-dot"/>{note}</p></article>)}</div>
      <div className="obs-workbench">
        <section aria-label="관측소 지도" className="obs-panel obs-map-panel">
          <div className="obs-panel-heading"><h3><MapPin size={20}/>전국 관측소 현황 지도</h3><span className="obs-count-badge">{mapMarkers.length}개소</span></div><p className="obs-panel-subtitle">지도를 클릭해 관측소의 상세 자료를 확인하세요.</p>
          <div className="obs-map-stage"><MapContainer center={[36.3,127.5]} zoom={6} style={{height:'100%',width:'100%'}} zoomControl={true} scrollWheelZoom={true}>
            {mapLayer==='street'?<OSMBaseLayer/>:<SatelliteBaseLayer/>}<MapFocus markers={mapMarkers} selected={selected} scope={query} resetKey={mapReset}/>
            {mapMarkers.map(marker=><Marker key={marker.id} position={[marker.lat,marker.lng]} icon={markerIcon(marker.name,marker.id===selectedStation,facilityColor(marker.net))} title={marker.name+' '+marker.id} alt={marker.name} eventHandlers={{click:()=>chooseStation(marker.id)}}>
              <Tooltip direction="top" offset={[0,-12]}>{marker.name+' · '+marker.net}</Tooltip><Popup><strong>{marker.name}</strong><p>{marker.id+' · '+marker.sea}</p><p>{marker.items+'개 항목 · '+marker.time.replace('T',' ')}</p><Link to={'/profile/'+encodeURIComponent(marker.id)+'?'+linkQuery}>관측값 자세히</Link></Popup>
            </Marker>)}
          </MapContainer>
          <div className="obs-map-legend">{['조위관측소','해양관측부이','해수유동관측소','해양과학기지',...(tableData.some(r=>r.net==='해양관측소')?['해양관측소']:[])].map(net=><span key={net}><i style={{background:facilityColor(net)}}/>{net}</span>)}</div>
          <div className="obs-map-regions">{seaCounts.filter(s=>['서해','동해','남해','제주해역'].includes(s.sea)).map(s=><button key={s.sea} aria-pressed={search.get('sea')===s.sea} onClick={()=>update({sea:search.get('sea')===s.sea?'':s.sea,station:'',item:''})}><span>{s.sea}</span><strong>{s.count}<small>개소</small></strong></button>)}</div>
          <div className="obs-map-tools"><button aria-label="지도 전체 위치" onClick={()=>setMapReset(v=>v+1)}><Maximize2 size={14}/>전체 위치</button><div><button aria-pressed={mapLayer==='street'} onClick={()=>setMapLayer('street')}>일반지도</button><button aria-pressed={mapLayer==='satellite'} onClick={()=>setMapLayer('satellite')}>위성지도</button></div></div>
          </div><p className="obs-map-caption">{metadataError||'마우스 휠로 확대·축소할 수 있습니다.'}{!loading&&mapMarkers.length<tableData.length?' · 좌표 없는 '+(tableData.length-mapMarkers.length)+'개소는 목록에서 선택':''}</p>
        </section>
        <section id="observation-table" aria-label="관측소 목록" className="obs-panel obs-list-panel">
          <div className="obs-list-filters"><StationClassifications compact/><label>운영상태<select aria-label="운영상태" value={stateFilter} onChange={e=>setStateFilter(e.target.value)}><option value="">전체</option><option value="NORMAL">정상</option><option value="WARNING">주의</option><option value="ABNORMAL">이상</option><option value="UNVERIFIED">확인 필요</option></select></label><button aria-label="선택 초기화" title="필터 초기화" onClick={()=>{update({sea:'',network:'',station:'',item:''});setStateFilter('');setStationSearch('');}}><RotateCcw size={14}/></button></div>
          <div className="obs-panel-heading"><h3><span className="obs-triangle">▶</span>관측소 목록 <small>(총 {filtered.length}개소)</small></h3><button className="obs-refresh" aria-label="새로고침" disabled={loading} onClick={()=>setRevision(r=>r+1)}><RefreshCw size={14} className={loading?'animate-spin':''}/></button></div>
          <label className="obs-list-search"><Search size={15}/><input aria-label="목록 검색" placeholder="관측소명, 지역, 해역을 검색하세요…" value={stationSearch} onChange={e=>setStationSearch(e.target.value)}/></label>
          <select className="obs-station-picker" aria-label="관측소 선택" value={selected?.id||''} disabled={loading} onChange={e=>chooseStation(e.target.value)}><option value="">관측소 바로 선택</option>{tableData.map(row=><option key={row.id} value={row.id}>{row.name+' · '+row.id}</option>)}</select>
          <div className="obs-list-scroll"><table className="obs-station-table"><thead><tr><th>관측소</th><th>유형·해역</th><th>운영상태</th><th>수집률</th><th><button onClick={()=>setSortNewest(v=>!v)} aria-label="마지막 관측시각 정렬">최근 관측 {sortNewest?'↓':'↕'}</button></th></tr></thead><tbody>{paged.rows.map(row=>{
            const state=operatingState(row.operation);
            return <tr key={row.id} className={row.id===selectedStation?'selected':''}><td><button aria-label={row.name+' '+row.id} title={row.id} aria-pressed={row.id===selectedStation} onClick={()=>chooseStation(row.id)}>{row.name}</button></td><td title={row.net+' · '+row.sea}><span>{({'조위관측소':'조위','해양관측부이':'부이','해수유동관측소':'유동','해양과학기지':'기지','해양관측소':'해양'} as Record<string,string>)[row.net]||row.net} · {row.sea}</span></td><td><span className={'obs-status '+state.tone} title={row.operation?.reason}>{state.label}</span></td><td title={row.operation?.reason}>{row.operation?.collection_rate==null?'—':row.operation.collection_rate+'%'}</td><td title={row.time}><span>{row.time.length>=16?row.time.slice(5,10)+' '+row.time.slice(11,16):row.time}</span></td></tr>;
          })}{!filtered.length&&<tr><td colSpan={5} className="obs-empty-row">{loading?'관측소 조회 중…':error?'자료 조회 실패':'선택 조건에 자료가 없습니다.'}</td></tr>}</tbody></table></div>
          <div className="obs-pagination"><span>{paged.first} - {paged.last} / {filtered.length}개소</span><nav aria-label="관측소 목록 페이지"><button aria-label="이전 페이지" disabled={paged.page<=1} onClick={()=>setPage(paged.page-1)}><ChevronLeft size={14}/></button>{pageNumbers.map(number=><button key={number} aria-label={number+'페이지'} aria-current={paged.page===number?'page':undefined} onClick={()=>setPage(number)}>{number}</button>)}<button aria-label="다음 페이지" disabled={paged.page>=paged.pages} onClick={()=>setPage(paged.page+1)}><ChevronRight size={14}/></button></nav></div>
        </section>
        <StationQuickView key={selectedStation+'|'+query+'|'+lake?.snapshot} station={selected} source={source} from={from} to={to} snapshot={lake?.snapshot} metric={stationMetrics.get(selectedStation)} revision={revision} asOfDay={asOfDay} asOfTime={asOfTime}/>
      </div>
      <section aria-label="관측자료 인사이트" className="obs-panel obs-insights"><div className="obs-panel-heading"><h3><Lightbulb size={19}/>해양 관측 인사이트</h3><span>선택한 보유 자료의 산정 근거</span><Link to={'/ai-insights?'+linkQuery}>AI 분석 보기<ArrowRight size={13}/></Link></div><div className="obs-insight-cards">
        <Link to={'/qc?'+linkQuery} className="rose"><span className="obs-insight-icon"><ShieldCheck size={23}/></span><div><strong>QC 근거 확인</strong><p>원문 QC 표기 {completion.data?.raw?qcPresencePercent(completion.data.raw):metricWaiting}</p></div><ChevronRight size={15}/></Link>
        <a href="#observation-months" className="amber"><span className="obs-insight-icon"><CalendarDays size={22}/></span><div><strong>기간별 자료 공백</strong><p>{lake?'자료 없는 월 '+(months.length-months.filter(m=>m.held).length)+'개월':'자료 조회 중'}</p></div><ChevronRight size={15}/></a>
        <a href="#observation-evidence" className="blue"><span className="obs-insight-icon"><Activity size={23}/></span><div><strong>참고 자료 채움</strong><p>{completion.data?.raw?gridPercent(completion.data.raw.grid):metricWaiting} · 산정 범위 확인</p></div><ChevronRight size={15}/></a>
        <Link to={'/profile/'+encodeURIComponent(selectedStation||tableData[0]?.id||'')+'?'+linkQuery} className="violet"><span className="obs-insight-icon"><Waves size={23}/></span><div><strong>관측소별 자료 탐색</strong><p>{selected?selected.name+' · '+selected.items+'개 관측항목':'지도에서 관측소를 선택하세요.'}</p></div><ChevronRight size={15}/></Link>
      </div></section>
      <section id="observation-months" className="obs-panel obs-months">{lake?<ObservationMonthGrid rows={lake.monthly} from={from} to={to} onMonth={month=>update({from:month,to:month})}/>:<p className="obs-caption">기간별 자료 조회 중…</p>}</section>
      <details id="observation-evidence" className="obs-panel obs-evidence"><summary>자료 출처·산정 근거 <span>{source} · {from} ~ {to}</span></summary><div className="obs-evidence-body"><DatasetSourceSelect source={source}/><p>보유 원천 {lake?countMetric(lake.totals.held_rows):'조회 중'}행</p><MetricCompletionPanel {...completion}/></div></details>
      <details className="obs-panel obs-evidence"><summary>7월 월간해양정보 대조</summary><div className="obs-evidence-body"><Link to="/reports?from=2026-07&to=2026-07">7월 전체 월 보고서 보기</Link><p>월간 보고서의 전체 월 수치는 기준일시 집계에 포함하지 않습니다.</p></div></details>
      <div className="obs-view-footer"><span><CheckCircle2 size={12}/>{error?'자료 조회 실패':lake?'실제 보유 자료 연결':'자료 조회 중'}</span><span>조회 갱신</span><select aria-label="자동 갱신" value={refreshSeconds} onChange={e=>setRefreshSeconds(Number(e.target.value))}><option value={0}>수동</option><option value={60}>1분마다</option><option value={300}>5분마다</option></select></div>
    </div>
  </div>;
}
