import {useEffect,useMemo,useState,useCallback} from 'react';
import {Link} from 'react-router-dom';
import {MapPin,ArrowRight,Waves,Thermometer,Wind,Droplets,RadioTower,Clock3,BarChart3,Compass} from 'lucide-react';
import {API_BASE_URL,apiFetch} from '../api/client';
import {nativeReceiptPresentation} from '../data/nativeReceiptPresentation';
import {observationItemLabel} from '../data/observationAvailability';
import {operatingState,collectionPresentation} from '../data/observationWorkspace';
import ObservationMonthGrid from './ObservationMonthGrid';
import ObservationTrend from './ObservationTrend';
import ObservationSeriesChart from './ObservationSeriesChart';
import {nativeClockCoordinate,observationSeriesUnit} from '../data/observationSeries';
import StationPhoto from './StationPhoto';
import OperationEvidence from './OperationEvidence';
import {matchesLakeDetail,matchesLakeSeries} from '../data/observationCutoff';

export default function StationQuickView({station,source,from,to,snapshot,metric,revision=0,asOfDay,asOfTime}:{station:any;source:string;from:string;to:string;snapshot?:string;metric?:any;revision?:number;asOfDay?:string;asOfTime?:string}) {
  const [data,setData]=useState<any>(null),[error,setError]=useState(''),[tab,setTab]=useState('관측자료');
  const [channelKey,setChannelKey]=useState(''),[previews,setPreviews]=useState<Record<string,{data?:any;error?:string}>>({});
  const [graphLimit,setGraphLimit]=useState(240),[graph,setGraph]=useState<{key?:string;data?:any;error?:string}>({});
  const stationId=station?.id;
  const cutoff=useMemo(()=>({...((asOfDay)?{as_of_day:asOfDay}:{}),...(asOfTime?{as_of_time:asOfTime}:{})}),[asOfDay,asOfTime]);
  const query=new URLSearchParams({source,from_month:from,to_month:to,...cutoff}).toString();
  const linkQuery=new URLSearchParams({source,from,to,...cutoff}).toString();
  useEffect(()=>{
    setData(null);setError('');setTab('관측자료');setChannelKey('');setPreviews({});
    if(!stationId)return;
    const c=new AbortController();
    apiFetch(API_BASE_URL+'/lake/stations/'+encodeURIComponent(stationId)+'?'+query,{signal:c.signal})
      .then(async r=>{if(!r.ok)throw new Error('HTTP '+r.status);return r.json();})
      .then(d=>{if(c.signal.aborted)return;if(!matchesLakeDetail(d,{source,from,to,day:asOfDay,time:asOfTime},stationId,snapshot||''))throw new Error('관측소·검증본 또는 기준일시 불일치');setData(d);})
      .catch(e=>{if(!c.signal.aborted)setError('상세 조회 실패: '+e.message);});
    return()=>c.abort();
  },[stationId,source,query,from,to,snapshot,revision,asOfDay,asOfTime]);
  const currentData=matchesLakeDetail(data,{source,from,to,day:asOfDay,time:asOfTime},stationId,snapshot||'')?data:null;
  const rows=currentData?.months||[];
  const channels=useMemo(()=>{
    const grouped=new Map<string,any>();
    for(const row of currentData?.months||[]){
      if(!(row.held_rows>0))continue;
      const key=JSON.stringify([row.item_code,row.depth_step,row.depth_from,row.depth_to]);
      if(!grouped.has(key))grouped.set(key,{key,item:row.item_code,depth:[row.depth_step,row.depth_from,row.depth_to],months:[]});
      grouped.get(key).months.push(row);
    }
    return [...grouped.values()].map(c=>({...c,month:c.months.map((r:any)=>String(r.month).slice(0,7)).sort().at(-1)}));
  },[currentData]);
  const channel=channels.find(c=>c.key===channelKey)||channels.find(c=>c.item==='WATER_TEMP')||channels[0];
  const cards=useMemo(()=>{
    const chosen:any[]=[];
    for(const family of [['WATER_TEMP'],['SALINITY'],['WIND_DIRECT','WIND_DIRECTION'],['WIND_SPEED'],['TIDE_LEVEL','TIDE_LEVEL_VEGA','WAVE_HEIGHT']]){
      const match=family.map(code=>channels.find(c=>c.item===code)).find(Boolean);
      if(match&&!chosen.includes(match))chosen.push(match);
    }
    for(const c of channels){if(chosen.length>=5)break;if(!chosen.includes(c))chosen.push(c);}
    return chosen;
  },[channels]);
  const seriesScope=useCallback((item:any,limit:number)=>({source,from,to,day:asOfDay,time:asOfTime,station:stationId,item:item.item,month:item.month,depth:item.depth,snapshot:snapshot||'',limit,offset:0,tail:true}),[source,from,to,asOfDay,asOfTime,stationId,snapshot]);
  const fetchSeries=useCallback(async(item:any,limit:number,signal:AbortSignal)=>{
    const p=new URLSearchParams({source,station:stationId,item:item.item,month:item.month,limit:String(limit),tail:'true',...cutoff});
    ['depth_step','depth_from','depth_to'].forEach((key,i)=>{if(item.depth[i]!=null)p.set(key,String(item.depth[i]));});
    const response=await apiFetch(API_BASE_URL+'/lake/series?'+p,{signal});
    if(!response.ok)throw new Error('HTTP '+response.status);
    const d=await response.json();
    if(!matchesLakeSeries(d,seriesScope(item,limit))||!d.rows.every((row:any)=>nativeClockCoordinate(row.observed_time_raw)!==null))
      throw new Error('관측소·항목·수심·기준시각 확인 실패');
    return d;
  },[source,stationId,cutoff,seriesScope]);
  const graphKey=channel?.key+'|'+graphLimit+'|'+stationId+'|'+query+'|'+snapshot+'|'+revision;
  useEffect(()=>{
    setPreviews({});
    if(!stationId||!snapshot||!cards.length)return;
    const c=new AbortController();
    for(const item of cards){
      fetchSeries(item,24,c.signal)
        .then(d=>{
          if(c.signal.aborted)return;
          setPreviews(previous=>({...previous,[item.key]:{data:d}}));
        }).catch(e=>{if(!c.signal.aborted)setPreviews(previous=>({...previous,[item.key]:{error:'관측값 조회 실패: '+e.message}}));});
    }
    return()=>c.abort();
  },[stationId,cards,snapshot,revision,fetchSeries]);
  useEffect(()=>{
    setGraph({});
    if(!stationId||!snapshot||!channel)return;
    const c=new AbortController();
    const key=graphKey;
    fetchSeries(channel,graphLimit,c.signal).then(d=>{if(!c.signal.aborted)setGraph({key,data:d});})
      .catch(e=>{if(!c.signal.aborted)setGraph({key,error:'시계열 조회 실패: '+e.message});});
    return()=>c.abort();
  },[stationId,channel,snapshot,revision,fetchSeries,graphLimit,graphKey]);
  const preview=graph.key===graphKey&&(!graph.data||channel&&matchesLakeSeries(graph.data,seriesScope(channel,graphLimit)))?graph:{};
  const receipt=nativeReceiptPresentation(metric?.receipt_diagnostics);
  const operationEnd=asOfDay?asOfDay+' '+(asOfTime||'23:59:59.999999'):'';
  const state=operatingState(station?.operation,operationEnd);
  const collection=collectionPresentation(station?.operation?{...station.operation,source}:null,operationEnd);
  const itemCount=new Set(rows.map((r:any)=>r.item_code)).size;
  return <><aside className="obs-panel obs-detail" aria-label="선택 관측소">
    <div className="obs-panel-heading"><h3><RadioTower size={18}/>관측소 상세 정보</h3>{station&&<span className={'obs-status '+state.tone}>{state.label}</span>}</div>
    {!station?<div className="obs-detail-empty"><MapPin size={38}/><h4>어느 관측소를 살펴볼까요?</h4><p>지도나 목록에서 관측소를 선택하면<br/>최근 관측값과 자료 추세를 볼 수 있습니다.</p></div>:<>
      <div className="obs-station-identity"><StationPhoto station={station.id} name={station.name}/><div>
        <h4>{station.name}{station.name.includes(station.net)?'':' '+station.net}</h4><p>{station.id}</p><p><MapPin size={11}/>{station.sea}</p>
        {station.lat!=null&&station.lng!=null&&<p className="obs-coordinates">{station.lat.toFixed(3)}° N · {station.lng.toFixed(3)}° E</p>}
      </div></div>
      <div className="obs-tabs" role="tablist" aria-label="관측소 상세 종류">{['관측자료','센서·QC','기간정보'].map(t=><button role="tab" aria-selected={tab===t} key={t} onClick={()=>setTab(t)}>{t}</button>)}</div>
      {operationEnd&&<OperationEvidence operation={station.operation} expectedEnd={operationEnd}/>}
      {error&&<p role="alert" className="obs-error">{error}</p>}
      {!currentData&&!error&&<p role="status" className="obs-loading">관측항목 조회 중…</p>}
      {tab==='관측자료'&&currentData&&<>
        <div className="obs-detail-metrics"><div><span><Clock3 size={12}/>최근 관측시각</span><strong>{station.time.replace('T',' ')}</strong></div><div title={collection.title}><span><BarChart3 size={12}/>{collection.label}</span><strong>{collection.value}</strong></div></div>
        <p className="obs-caption">{collection.note}</p>
        <div className="obs-value-cards">{cards.map(c=>{
          const candidate=previews[c.key],result=candidate?.data&&!matchesLakeSeries(candidate.data,seriesScope(c,24))?undefined:candidate;
          const samples=result?.data?.rows||[],latest=samples[0];
          const Icon=c.item.includes('TEMP')?Thermometer:c.item.includes('DIRECT')?Compass:c.item.includes('WIND')?Wind:c.item.includes('SALINITY')?Droplets:Waves;
          return <button className={'obs-value-card '+(channel?.key===c.key?'selected':'')} key={c.key} onClick={()=>setChannelKey(c.key)} aria-label={observationItemLabel(c.item)+' 원천값 보기'} aria-pressed={channel?.key===c.key}>
            <span className="obs-value-title"><Icon size={14}/>{observationItemLabel(c.item)}</span>
            <strong>{latest?.value_raw==null||String(latest.value_raw).trim()===''?(result?.error?'조회 실패':latest?'값 없음':result?.data?'자료 없음':'조회 중'):String(latest.value_raw).trim()}<small>{latest?.unit||'원천값'}</small></strong>
            {result?.data&&<ObservationTrend rows={samples} label={observationItemLabel(c.item)} item={c.item}/>}
            {latest&&<time className="obs-sample-clock" title={latest.observed_time_raw}>{String(latest.observed_time_raw).replace('T',' ').slice(5,19)}</time>}
          </button>;
        })}</div>
        <p className="obs-caption">{asOfDay&&<span>공통 기준 {asOfDay} {asOfTime||'일 종료'}<br/></span>}카드를 선택하면 아래에서 실제 시계열을 볼 수 있습니다.</p>
        {!channels.length&&<p className="obs-loading">선택 기간에 보유 관측항목이 없습니다.</p>}
      </>}
      {tab==='센서·QC'&&<div className="obs-sensor-facts">{[['물리 센서','physical_sensor_id'],['센서 대응','sensor_decision'],['단위 적용','unit_application_decision'],['시간대','timezone_decision'],['QC 근거','qc_evidence_decision'],['QC 승인','qc_approval_decision']].map(([label,key])=>{const counts:Record<string,number>={};rows.forEach((r:any)=>{const v=r[key]||'근거 확인 필요';counts[v]=(counts[v]||0)+1;});return <div key={key}><strong>{label}</strong><p>{Object.entries(counts).map(([k,v])=>k+' '+v+'기록').join(' · ')||'기록 없음'}</p></div>;})}</div>}
      {tab==='기간정보'&&<div className="obs-period-facts"><dl>
        <div><dt>첫 관측시각 (원문)</dt><dd>{station.first||'시각 기록 없음'}</dd></div><div><dt>마지막 관측시각 (원문)</dt><dd>{station.time}</dd></div>
        <div><dt>수신·관측 시계차 (원문)</dt><dd title={receipt.title}>{receipt.value}{receipt.note&&<small>{receipt.note}</small>}</dd></div>
      </dl><ObservationMonthGrid rows={channel?.months||rows} from={from} to={to}/><p className="obs-caption">선택 기간 {from} ~ {to} · {itemCount}개 관측항목</p></div>}
      <Link className="obs-detail-link" to={'/profile/'+encodeURIComponent(station.id)+'?'+linkQuery+(channel?'&item='+encodeURIComponent(channel.item):'')}>상세 데이터 보기<ArrowRight size={15}/></Link>
    </>}
  </aside>
    {station&&currentData&&channel&&<section className="obs-panel obs-series-panel" aria-label="실제 관측값 시계열">
      <div className="obs-series-heading"><div><h3><BarChart3 size={20}/>{station.name} · {observationItemLabel(channel.item)} 실제 관측값</h3><p>기준 {asOfDay||to} {asOfTime||''} · 항목별 최근 관측 기록</p></div><div className="obs-series-controls">
        <label>관측항목·수심<select aria-label="관측항목·수심" value={channel.key} onChange={e=>setChannelKey(e.target.value)}>{channels.map(c=><option key={c.key} value={c.key}>{observationItemLabel(c.item)}{c.depth.some((d:any)=>d!=null)?' · 수심 '+c.depth.map((d:any)=>d??'—').join('/') : ''}</option>)}</select></label>
        <div role="group" aria-label="그래프 조회 건수">{[24,240].map(limit=><button key={limit} aria-pressed={graphLimit===limit} onClick={()=>setGraphLimit(limit)}>최근 {limit}건</button>)}</div>
      </div></div>
      {preview.error&&<p role="alert" className="obs-error">{preview.error}</p>}
      {!preview.data&&!preview.error&&<p role="status" className="obs-chart-empty">실제 관측 시계열 조회 중…</p>}
      {preview.data&&<ObservationSeriesChart key={channel.key+'|'+graphLimit+'|'+query+'|'+revision} rows={preview.data.rows} item={channel.item} label={observationItemLabel(channel.item)}/>}
      {preview.data&&<details className="obs-preview-table"><summary>원천 기록 {preview.data.rows.length}건 보기 <span>{channel.month}</span></summary><div className="obs-preview-scroll"><table><thead><tr><th>관측시각 (원문)</th><th>{observationSeriesUnit(preview.data.rows)}</th><th>원문 QC</th><th>수심</th><th>원천 파일 · 행</th></tr></thead><tbody>{preview.data.rows.map((r:any)=><tr key={r.filename+':'+r.file_row_number}><td>{String(r.observed_time_raw).replace('T',' ')}</td><td>{r.value_raw==null?'NULL':String(r.value_raw)}</td><td>{r.source_qc_raw==null?'—':String(r.source_qc_raw)}</td><td>{[r.depth_step,r.depth_from,r.depth_to].map(d=>d??'—').join('/')}</td><td title={r.filename}>{String(r.filename).split(/[\\/]/).at(-1)} · {r.file_row_number}</td></tr>)}</tbody></table></div></details>}
    </section>}
  </>;
}
