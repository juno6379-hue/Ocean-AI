export type ObservationSample = {
  key:string;time:string;clock:number|null;raw:unknown;value:number|null;unit:string|null;
  filename:string;rowNumber:unknown;depth:unknown[];
};

/** A numeric coordinate of the native calendar clock, without assigning a time zone. */
export function nativeClockCoordinate(raw:unknown):number|null {
  const m=/^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2}):(\d{2})(?:\.(\d{1,6}))?$/.exec(String(raw??''));
  if(!m)return null;
  const [year,month,day,hour,minute,second]=m.slice(1,7).map(Number);
  const date=new Date(0);date.setUTCFullYear(year,month-1,day);date.setUTCHours(hour,minute,second,0);
  if(date.getUTCFullYear()!==year||date.getUTCMonth()!==month-1||date.getUTCDate()!==day||
    date.getUTCHours()!==hour||date.getUTCMinutes()!==minute||date.getUTCSeconds()!==second)return null;
  const coordinate=date.getTime()*1000+Number((m[7]||'').padEnd(6,'0'));
  return Number.isSafeInteger(coordinate)?coordinate:null;
}

/** Decimal source syntax only: JavaScript's hex/binary/empty coercions are not observations. */
export function numericObservationValue(row:any):number|null {
  const raw=row.value_raw,literal=raw==null?'':String(raw).trim();
  if(!/^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$/.test(literal))return null;
  const value=Number(literal);
  if(!Number.isFinite(value))return null;
  if(Object.hasOwn(row,'value_numeric')&&(!Number.isFinite(row.value_numeric)||row.value_numeric!==value))return null;
  return value;
}

/** Keep every file row, including coincident observations and invalid values. */
export function observationSeries(rows:any[]):ObservationSample[] {
  return [...rows].reverse().map((row,index)=>{
    const raw=row.value_raw,value=numericObservationValue(row);
    return {key:String(row.filename??'')+':'+String(row.file_row_number??index)+':'+index,
      time:String(row.observed_time_raw??''),clock:nativeClockCoordinate(row.observed_time_raw),
      raw,value,unit:row.unit||null,
      filename:String(row.filename??''),rowNumber:row.file_row_number,
      depth:[row.depth_step,row.depth_from,row.depth_to]};
  });
}

/** Direction samples are discrete: their unit and circular period are not yet confirmed. */
export function isDirectionItem(item:string) {
  return ['WIND_DIRECT','CURRENT_DIRECT','WAVE_DIRECT','WIND_DIRECTION','CURRENT_DIRECTION','WAVE_DIRECTION'].includes(item);
}

export function observationPlot(rows:any[],item:string,width=912,height=148) {
  const samples=observationSeries(rows),clocked=samples.filter(s=>s.clock!==null);
  const finite=clocked.filter(s=>s.value!==null);
  const first=clocked.length?Math.min(...clocked.map(s=>s.clock!)):0;
  const last=clocked.length?Math.max(...clocked.map(s=>s.clock!)):0;
  const min=finite.length?Math.min(...finite.map(s=>s.value!)):0;
  const max=finite.length?Math.max(...finite.map(s=>s.value!)):0;
  const yPad=max===min?Math.max(Math.abs(min)*.05,1):(max-min)*.1;
  const low=min-yPad,high=max+yPad;
  const points=samples.map(s=>({...s,x:s.clock===null?null:first===last?width/2:(s.clock-first)*width/(last-first),
    y:s.value===null?null:height-(s.value-low)*height/(high-low)}));
  const counts=new Map<number,number>();clocked.forEach(s=>counts.set(s.clock!,1+(counts.get(s.clock!)||0)));
  const coincident=[...counts.values()].filter(count=>count>1).reduce((total,count)=>total+count,0);
  const direction=isDirectionItem(item);
  const segments:typeof points[]=[];let current:typeof points=[];
  const flush=()=>{if(current.length)segments.push(current);current=[];};
  for(const point of points){
    if(point.x===null||point.y===null){flush();continue;}
    if(direction||(counts.get(point.clock!)||0)>1){flush();segments.push([point]);continue;}
    // Two file rows at the same native time are parallel evidence, not a temporal change.
    current.push(point);
  }
  flush();
  return {samples,points,segments,first,last,low,high,min,max,direction,coincident,
    numericCount:finite.length,missingCount:samples.filter(s=>s.value===null).length,
    invalidClockCount:samples.filter(s=>s.clock===null).length};
}

/** A shared unit can be shown only if every returned record explicitly carries it. */
export function observationSeriesUnit(rows:any[]) {
  const units=new Set(rows.map(row=>typeof row.unit==='string'?row.unit.trim():''));
  return rows.length&&units.size===1&&!units.has('')?[...units][0]:'원천값';
}
