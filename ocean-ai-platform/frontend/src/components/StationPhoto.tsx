import {useEffect,useState} from 'react';
import {API_BASE_URL,apiFetch} from '../api/client';
import {stationPhotograph} from '../data/stationPhotograph';
import type {StationPhotograph} from '../data/stationPhotograph';

export default function StationPhoto({station,name}:{station:string;name:string}) {
  const [result,setResult]=useState<StationPhotograph|null>(null),[failedStation,setFailedStation]=useState<string|null>(null),[attempt,setAttempt]=useState(0);
  useEffect(()=>{
    const control=new AbortController();setResult(null);setFailedStation(null);
    apiFetch(API_BASE_URL+'/stations/'+encodeURIComponent(station)+'/photograph',{signal:control.signal})
      .then(async response=>{if(!response.ok)throw new Error('사진 조회 실패');return response.json();})
      .then(value=>{const verified=stationPhotograph(value,station);if(!control.signal.aborted)setResult(verified);})
      .catch(()=>{if(!control.signal.aborted)setFailedStation(station);});
    return()=>control.abort();
  },[station,attempt]);
  const current=result?.station===station?result:null,failed=failedStation===station;
  const loading=!current&&!failed;
  return <figure className="obs-station-photo" aria-label={name+' 관측소 사진'} aria-busy={loading}>{current?.status==='AVAILABLE'&&!failed?<>
    <a href={current.source_url} target="_blank" rel="noreferrer" title={current.credit+' · 촬영일 미상'}><img key={station} src={current.image_url!} alt={name+' 실제 관측소 사진'} decoding="async" onError={()=>setFailedStation(station)}/></a>
    <figcaption title={current.credit}>공식 · 촬영일 미상</figcaption>
  </>:<div role="status">{failed?<><span>사진 조회 불가</span><button type="button" className="obs-photo-retry" onClick={()=>setAttempt(value=>value+1)} aria-label={name+' 관측소 사진 다시 조회'}>재시도</button></>:current?'공식 사진 없음':'사진 조회 중'}</div>}</figure>;
}
