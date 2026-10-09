/** One clock anchor for all requests; raw observation clocks stay untouched. */
export const DEFAULT_OBSERVATION_DAY='2026-07-09';
export function systemObservationTime(now=new Date()) {
  return new Intl.DateTimeFormat('en-GB',{timeZone:'Asia/Seoul',hour:'2-digit',minute:'2-digit',second:'2-digit',hour12:false}).format(now);
}
export function matchesObservationCutoff(value:any,day?:string,time?:string) {
  return (!day||value?.as_of_day===day)&&(!time||value?.as_of_time===time);
}

type LakeScope={source:string;from:string;to:string;day?:string;time?:string};
export function matchesLakeSummary(value:any,scope:LakeScope) {
  return Boolean(value && value.source===scope.source && value.from_month===scope.from && value.to_month===scope.to
    && typeof value.snapshot==='string' && value.snapshot.length && Array.isArray(value.stations)
    && matchesObservationCutoff(value,scope.day,scope.time));
}
export function matchesLakeDetail(value:any,scope:LakeScope,station:string,snapshot:string) {
  return Boolean(value && value.source===scope.source && value.station_code===station && value.snapshot===snapshot
    && Array.isArray(value.months) && value.months.every((r:any)=>String(r.month).slice(0,7)>=scope.from&&String(r.month).slice(0,7)<=scope.to)
    && matchesObservationCutoff(value,scope.day,scope.time));
}
export function matchesLakeSeries(value:any,scope:LakeScope & {station:string;item:string;month:string;depth:unknown[];snapshot:string;limit:number;offset:number;tail:boolean}) {
  if (!value || value.source!==scope.source || value.station!==scope.station || value.item!==scope.item || value.month!==scope.month
    || value.snapshot!==scope.snapshot || value.tail!==scope.tail || value.limit!==scope.limit || value.offset!==scope.offset
    || !Array.isArray(value.rows) || value.rows.length>scope.limit || !matchesObservationCutoff(value,scope.day,scope.time))return false;
  const literal=(v:unknown)=>v==null?null:String(v);
  return value.rows.every((r:any)=>{
    if(r.station_code!==scope.station||r.item_code!==scope.item||['depth_step','depth_from','depth_to'].some((key,i)=>literal(r[key])!==literal(scope.depth[i])))return false;
    if(!scope.day)return true;
    const clock=String(r.observed_time_raw??'').replace('T',' ');
    if(!/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}(\.\d{1,6})?$/.test(clock)||clock.slice(0,7)!==scope.month)return false;
    const ceiling=scope.day+' '+(scope.time||'23:59:59.999999');
    const comparable=(s:string)=>(s.includes('.')?s:s+'.').padEnd(26,'0');
    return comparable(clock)<=comparable(ceiling);
  });
}
