/** Presentation of stored observations; these states never assert equipment health. */
export function storedDataState(metric: any) {
  if (!metric || !(metric.held_rows > 0)) return {key:'checking',label:'근거 확인',tone:'slate'};
  if (typeof metric.missing_value_rows === 'number' && metric.missing_value_rows > 0)
    return {key:'missing',label:'값 누락',tone:'amber'};
  if (metric.source_qc_presence_rate === 0) return {key:'qc_absent',label:'QC 표기 없음',tone:'amber'};
  return {key:'available',label:'자료 보유',tone:'emerald'};
}

export function stationPage<T>(rows:T[],requested:number,size=10) {
  const pages=Math.max(1,Math.ceil(rows.length/size));
  const page=Math.max(1,Math.min(pages,Number.isFinite(requested)?Math.trunc(requested):1));
  return {page,pages,rows:rows.slice((page-1)*size,page*size),
    first:rows.length?(page-1)*size+1:0,last:Math.min(page*size,rows.length)};
}

/** Keep bad and absent raw values as gaps, never as zero-valued observations. */
export function observationTrend(rows:any[]) {
  return [...rows].reverse().map(row=>{
    const raw=row.value_raw;
    const value=raw==null || String(raw).trim()==='' ? NaN : Number(raw);
    return {time:String(row.observed_time_raw||''),value:Number.isFinite(value)?value:null};
  });
}

export function facilityColor(network:string) {
  if(network.includes('조위'))return '#0085ff';
  if(network.includes('부이'))return '#00b894';
  if(network.includes('유동')||network.includes('HF-Radar'))return '#ffb000';
  if(network.includes('과학'))return '#984bff';
  if(network.includes('해양관측소'))return '#0e7490';
  return '#64748b';
}

export function operatingState(value:any) {
  if(value?.state==='NORMAL')return {label:'정상',tone:'emerald'};
  if(value?.state==='WARNING')return {label:'주의',tone:'amber'};
  if(value?.state==='ABNORMAL')return {label:'이상',tone:'rose'};
  return {label:'확인 필요',tone:'slate'};
}
