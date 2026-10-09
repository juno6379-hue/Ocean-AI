export const observationItemLabel = (code:string) => ({
  TIDE_LEVEL:'조위', TIDE_LEVEL_VEGA:'조위 · VEGA', TIDE_LEVEL_LASER_1:'조위 · LASER_1',
  AIR_PRES:'기압', AIR_TEMP:'기온', WATER_TEMP:'수온', SALINITY:'염분',
  WIND_SPEED:'풍속', WIND_DIRECT:'풍향', WIND_GUST:'돌풍', HUMIDITY:'습도',
  CURRENT_SPEED:'유속', CURRENT_DIRECT:'유향', WAVE_HEIGHT:'파고', WAVE_PERIOD:'파주기',
  WAVE_DIRECT:'파향', ELECT_CONDUCT:'전기전도도',
} as Record<string,string>)[code] || code;

/** A month with any held row is present. Its absence is not an outage decision. */
export function observationAvailability(rows:{month:unknown;held_rows?:unknown}[],from:string,to:string) {
  const pattern=/^[0-9]{4}-(0[1-9]|1[0-2])$/;
  if(!pattern.test(from)||!pattern.test(to)||from>to)return [];
  const held=new Set(rows.filter(row=>typeof row.held_rows==='number'&&Number.isFinite(row.held_rows)&&row.held_rows>0)
    .map(row=>String(row.month).slice(0,7)));
  const result:{month:string;held:boolean}[]=[];
  const [year,month]=from.split('-').map(Number);
  const cursor=new Date(0);cursor.setUTCFullYear(year,month-1,1);
  while(cursor.toISOString().slice(0,7)<=to&&result.length<1200){
    const key=cursor.toISOString().slice(0,7);
    result.push({month:key,held:held.has(key)});cursor.setUTCMonth(cursor.getUTCMonth()+1);
  }
  return result;
}
