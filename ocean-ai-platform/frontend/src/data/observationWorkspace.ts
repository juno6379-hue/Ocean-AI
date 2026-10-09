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

const nativeClock=(value:unknown)=>{
  const literal=String(value??'').replace('T',' ');
  const parts=/^(\d{4})-(\d{2})-(\d{2}) (\d{2}):(\d{2}):(\d{2})(\.\d{1,6})?$/.exec(literal);
  if(!parts)return null;
  const [year,month,day,hour,minute,second]=parts.slice(1,7).map(Number);
  const leap=year%4===0&&(year%100!==0||year%400===0);
  const days=[31,leap?29:28,31,30,31,30,31,31,30,31,30,31];
  if(year<1||month<1||month>12||day<1||day>days[month-1]||hour>23||minute>59||second>59)return null;
  return (literal.includes('.')?literal:literal+'.').padEnd(26,'0');
};
const nonnegativeInteger=(value:unknown)=>typeof value==='number'&&Number.isInteger(value)&&value>=0;
const percent=(value:unknown)=>typeof value==='number'&&Number.isFinite(value)&&value>=0&&value<=100;

/** A dated data diagnostic never grants physical sensor health or approved QC. */
export function validOperationEvidence(value:any,expectedEnd?:string) {
  if(!value||value.basis!=='OBSERVATION_DIAGNOSTIC'||typeof value.policy_version!=='string'||!value.policy_version||
    !/^[a-f0-9]{64}$/.test(value.policy_hash||''))return false;
  const start=nativeClock(value.window_start),end=nativeClock(value.window_end);
  return Boolean(start&&end&&start<end&&(!expectedEnd||end===nativeClock(expectedEnd)));
}

export function operatingState(value:any,expectedEnd?:string) {
  if(validOperationEvidence(value,expectedEnd)&&nonnegativeInteger(value.channels_evaluated)&&value.channels_evaluated>0&&
    nonnegativeInteger(value.channels_total)&&value.channels_evaluated<=value.channels_total){
    if(value.state==='NORMAL'&&value.channels_evaluated===value.channels_total)return {state:'NORMAL',label:'정상',tone:'emerald'};
    if(value.state==='WARNING')return {state:'WARNING',label:'주의',tone:'amber'};
    if(value.state==='ABNORMAL')return {state:'ABNORMAL',label:'이상',tone:'rose'};
  }
  return {state:'UNVERIFIED',label:'확인 필요',tone:'slate'};
}

export function operationSummary(value:any,total:number,expectedEnd:string) {
  if(!validOperationEvidence(value,expectedEnd)||!['normal','warning','abnormal','unclassified'].every(key=>nonnegativeInteger(value[key]))||
    value.normal+value.warning+value.abnormal+value.unclassified!==total)return null;
  return value;
}

export function observedAvailability(value:any,expectedEnd?:string) {
  return validOperationEvidence(value,expectedEnd)&&percent(value.observed_grid_availability_percent)
    ?value.observed_grid_availability_percent.toFixed(1)+'%':'—';
}

const safeCount=(value:unknown):value is number=>typeof value==='number'&&Number.isSafeInteger(value)&&value>=0;
const nonempty=(value:unknown):value is string=>typeof value==='string'&&value.length>0;
const samePolicy=(left:any,right:any)=>left.basis===right.basis&&left.policy_version===right.policy_version&&
  left.policy_hash===right.policy_hash&&nativeClock(left.window_start)===nativeClock(right.window_start)&&
  nativeClock(left.window_end)===nativeClock(right.window_end);
const ratioMatches=(value:unknown,held:number,expected:number)=>expected>0
  ?percent(value)&&Math.abs((value as number)-100*held/expected)<1e-8:value==null;

/** Exact station/item/typed-depth channels are the source scope of a station diagnostic. */
function stationOperationScope(operation:any,expectedEnd:string,source?:string) {
  if(!nativeClock(expectedEnd)||!validOperationEvidence(operation,expectedEnd)||!nonempty(operation.station_code)||
    !Array.isArray(operation.channels)||!safeCount(operation.channels_total)||
    operation.channels.length!==operation.channels_total||!safeCount(operation.channels_evaluated))return null;
  const grains=new Set<string>();
  const sources=new Set<string>();
  let evaluated=0;
  for(const channel of operation.channels){
    if(!validOperationEvidence(channel,expectedEnd)||!samePolicy(channel,operation)||
      channel.station_code!==operation.station_code||!nonempty(channel.item_code)||!nonempty(channel.source_group)||
      (source&&channel.source_group!==source)||!['NORMAL','WARNING','ABNORMAL','UNVERIFIED'].includes(channel.state))return null;
    const depth=['depth_step','depth_from','depth_to'].map(key=>{
      const value=channel[key];return value==null?['null']: [typeof value,value];
    });
    if(['depth_step','depth_from','depth_to'].some(key=>channel[key]!=null&&
      typeof channel[key]!=='string'&&typeof channel[key]!=='number'))return null;
    if(['depth_step','depth_from','depth_to'].some(key=>typeof channel[key]==='number'&&!Number.isFinite(channel[key])))return null;
    const grain=JSON.stringify([channel.item_code,...depth]);
    if(grains.has(grain))return null;
    grains.add(grain);sources.add(channel.source_group);
    if(channel.state!=='UNVERIFIED')evaluated++;
  }
  if(sources.size>1||evaluated!==operation.channels_evaluated)return null;
  const states=operation.channels.map((channel:any)=>channel.state);
  const worst=states.includes('ABNORMAL')?'ABNORMAL':states.includes('WARNING')?'WARNING':
    evaluated>0?(evaluated===operation.channels_total?'NORMAL':'WARNING'):'UNVERIFIED';
  if(operation.state!==worst)return null;
  return {source:sources.values().next().value as string|undefined,channels:operation.channels};
}

function stationGrid(operation:any,expectedEnd:string,source?:string) {
  const scope=stationOperationScope(operation,expectedEnd,source||operation?.source);
  const grid=operation?.observed_grid;
  if(!scope||!grid||grid.denominator!=='INFERRED_OBSERVATION_GRID')return null;
  let held=0,expected=0,eligible=0;
  for(const channel of scope.channels){
    const value=channel.observed_grid;
    if(!value||value.denominator!=='INFERRED_OBSERVATION_GRID')return null;
    if(value.expected_slots==null){if(value.held_slots!=null)return null;continue;}
    if(!safeCount(value.expected_slots)||!safeCount(value.held_slots)||value.held_slots>value.expected_slots||
      !ratioMatches(value.availability_percent,value.held_slots,value.expected_slots))return null;
    expected+=value.expected_slots;held+=value.held_slots;eligible++;
  }
  if(!safeCount(held)||!safeCount(expected)||grid.expected_slots!==expected||grid.held_slots!==held||
    grid.eligible_channels!==eligible||grid.excluded_channels!==operation.channels_total-eligible||
    !ratioMatches(operation.observed_grid_availability_percent,held,expected))return null;
  return {held,expected,eligible,total:operation.channels_total,source:scope.source};
}

function rowOperation(row:any,expectedEnd:string) {
  return nonempty(row?.id)&&nonempty(row?.source)&&nonempty(row?.snapshot)&&
    row.operation?.station_code===row.id&&stationOperationScope(row.operation,expectedEnd,row.source)
    ?row.operation:null;
}

export type ObservationFilters={sea?:string;network?:string;state?:string;search?:string};

/** Match the July reference scope exactly, including absent rows versus unassigned fields. */
export function filterObservationStations<T extends Record<string,any>>(rows:T[],filters:ObservationFilters,
  expectedEnd:string,sortNewest=false):T[] {
  const {sea='',network='',state='',search=''}=filters;
  const query=search.trim().toLocaleLowerCase();
  const filtered=rows.filter(row=>{
    if(network==='__UNREGISTERED__'){
      if(row.refRegistered!==false||(sea&&sea!=='__UNASSIGNED__'))return false;
    }else if(network||sea){
      if(row.refRegistered!==true)return false;
      if(network&&row.network_type!==network)return false;
      if(sea==='__UNASSIGNED__'?Boolean(row.sea_area):sea&&row.sea_area!==sea)return false;
    }
    if(state&&operatingState(rowOperation(row,expectedEnd),expectedEnd).state!==state)return false;
    if(query&&!['id','name','net','sea','network_type','sea_area'].some(key=>String(row[key]??'').toLocaleLowerCase().includes(query)))return false;
    return true;
  });
  if(sortNewest)filtered.sort((left,right)=>{
    const cutoff=nativeClock(expectedEnd);
    const a=nativeClock(left.time),b=nativeClock(right.time);
    const validA=a&&cutoff&&a<=cutoff?a:'',validB=b&&cutoff&&b<=cutoff?b:'';
    return validA===validB?0:validA>validB?-1:1;
  });
  return filtered;
}

/** Recompute the visible scope; no full-fleet counts or mean station percentages leak in. */
export function summarizeVisibleOperations(rows:any[],baseSummary:any,expectedEnd:string) {
  const base=baseSummary?.operation_summary;
  if(!nativeClock(expectedEnd)||!nonempty(baseSummary?.source)||!nonempty(baseSummary?.snapshot)||
    !Array.isArray(baseSummary?.stations)||!safeCount(baseSummary?.totals?.stations)||
    baseSummary.stations.length!==baseSummary.totals.stations||
    !operationSummary(base,baseSummary.totals.stations,expectedEnd))return null;
  const baseIds=new Set(baseSummary.stations.map((row:any)=>row.station_code));
  if(baseIds.size!==baseSummary.totals.stations)return null;
  const ids=new Set<string>();
  const counts={normal:0,warning:0,abnormal:0,unclassified:0};
  let held=0,expected=0,eligible=0,totalChannels=0,gridStations=0,excludedStations=0;
  for(const row of rows){
    if(!nonempty(row?.id)||ids.has(row.id)||!baseIds.has(row.id)||row.source!==baseSummary.source||
      row.snapshot!==baseSummary.snapshot)return null;
    ids.add(row.id);
    const candidate=rowOperation(row,expectedEnd);
    const operation=candidate&&samePolicy(candidate,base)?candidate:null;
    const state=operatingState(operation,expectedEnd).state;
    counts[state==='NORMAL'?'normal':state==='WARNING'?'warning':state==='ABNORMAL'?'abnormal':'unclassified']++;
    if(!operation){excludedStations++;continue;}
    totalChannels+=operation.channels_total;
    const grid=stationGrid(operation,expectedEnd,baseSummary.source);
    if(!grid){excludedStations++;continue;}
    held+=grid.held;expected+=grid.expected;eligible+=grid.eligible;gridStations++;
  }
  if(!safeCount(held)||!safeCount(expected))return null;
  return {...base,...counts,source:baseSummary.source,snapshot:baseSummary.snapshot,scope:'VISIBLE_STATIONS',
    scope_station_codes:[...ids],stations_total:rows.length,collection_rate:null,collection_evidence:null,
    channels_total:totalChannels,observed_grid_availability_percent:expected>0?100*held/expected:null,
    observed_grid:{expected_slots:expected,held_slots:held,eligible_channels:eligible,
      excluded_channels:totalChannels-eligible,eligible_stations:gridStations,excluded_stations:excludedStations,
      denominator:'INFERRED_OBSERVATION_GRID',sampling_contract_approved:false}};
}

function presentedGrid(operation:any,expectedEnd:string) {
  if(operation?.scope!=='VISIBLE_STATIONS')return stationGrid(operation,expectedEnd);
  const grid=operation.observed_grid;
  if(!validOperationEvidence(operation,expectedEnd)||!nonempty(operation.source)||!nonempty(operation.snapshot)||
    !Array.isArray(operation.scope_station_codes)||operation.scope_station_codes.some((id:any)=>!nonempty(id))||
    new Set(operation.scope_station_codes).size!==operation.stations_total||
    !operationSummary(operation,operation.stations_total,expectedEnd)||!grid||grid.denominator!=='INFERRED_OBSERVATION_GRID'||
    !['held_slots','expected_slots','eligible_channels','excluded_channels','eligible_stations','excluded_stations'].every(key=>safeCount(grid[key]))||
    grid.held_slots>grid.expected_slots||grid.eligible_channels+grid.excluded_channels!==operation.channels_total||
    grid.eligible_stations+grid.excluded_stations!==operation.stations_total||
    !ratioMatches(operation.observed_grid_availability_percent,grid.held_slots,grid.expected_slots))return null;
  return {held:grid.held_slots,expected:grid.expected_slots,eligible:grid.eligible_channels,total:operation.channels_total,
    source:operation.source,excludedStations:grid.excluded_stations};
}

/** Unknown receipt rates can use a separately labelled, source-clock grid estimate. */
export function collectionPresentation(operation:any,expectedEnd:string) {
  const grid=nativeClock(expectedEnd)?presentedGrid(operation,expectedEnd):null;
  const receipt=operation?.collection_evidence;
  const receiptScope=operation?.scope==='VISIBLE_STATIONS'?operation.scope_station_codes:[operation?.station_code];
  const receiptIds=Array.isArray(receipt?.scope_station_codes)?receipt.scope_station_codes:receipt?.station_code?[receipt.station_code]:[];
  if(grid&&receipt?.basis==='RECEIPT_LOG'&&receipt.source===grid.source&&
    nativeClock(receipt.window_start)===nativeClock(operation.window_start)&&nativeClock(receipt.window_end)===nativeClock(expectedEnd)&&
    receiptIds.length===receiptScope.length&&new Set(receiptIds).size===receiptIds.length&&receiptIds.every((id:any)=>receiptScope.includes(id))&&
    /^[a-f0-9]{64}$/.test(receipt.plan_hash||'')&&/^[a-f0-9]{64}$/.test(receipt.log_hash||'')&&
    safeCount(receipt.received_slots)&&safeCount(receipt.expected_slots)&&receipt.received_slots<=receipt.expected_slots&&
    receipt.expected_slots>0&&ratioMatches(operation.collection_rate,receipt.received_slots,receipt.expected_slots)){
    const note=`수신 이력 ${receipt.received_slots.toLocaleString('ko-KR')} / 예정 ${receipt.expected_slots.toLocaleString('ko-KR')}건 · 동일 기준시각·선택 범위`;
    return {label:'수집률',value:operation.collection_rate.toFixed(1)+'%',title:note,note,kind:'RECEIPT',estimated:false,
      numerator:receipt.received_slots,denominator:receipt.expected_slots};
  }
  if(grid&&grid.expected>0){
    const excludedStations='excludedStations' in grid?grid.excludedStations:0;
    const note=`원천 관측시각 격자 ${grid.held.toLocaleString('ko-KR')} / 추정 예정 ${grid.expected.toLocaleString('ko-KR')}건 · ${grid.eligible}/${grid.total}개 항목·수심${excludedStations?' · '+excludedStations+'개 관측소 제외':''} · 실제 수신율은 근거 없음`;
    return {label:'수집률 (추정)',value:(100*grid.held/grid.expected).toFixed(1)+'%',title:note,note,kind:'INFERRED_GRID',estimated:true,
      numerator:grid.held,denominator:grid.expected};
  }
  const note='동일 기준시각의 수신 이력·예정 분모 또는 추정 관측격자 근거가 없습니다.';
  return {label:'수집률',value:'—',title:note,note,kind:'UNAVAILABLE',estimated:false,numerator:null,denominator:null};
}

export function operationReasonText(value:any):string {
  if(typeof value==='string'){
    if(value.includes(' · '))return value.split(' · ').map(operationReasonText).join(' · ');
    const translations:Record<string,string>={
      RECENT_OBSERVATION_FLOW_WITHIN_DEVELOPMENT_THRESHOLDS:'최근 자료 흐름이 개발 진단 기준 안에 있습니다',
      CADENCE_CHANGED_FROM_PREVIOUS_HISTORY:'이전 이력과 추정 관측간격이 달라졌습니다',
      CLOCK_PHASE_CHANGED_FROM_PREVIOUS_HISTORY:'이전 이력과 관측시각의 격자 위상이 달라졌습니다',
      MULTIPLE_OR_MISSING_CLOCK_PHASES:'관측시각의 격자 위상이 일정하지 않습니다',
      RECENT_INFERRED_GRID_AVAILABILITY_BELOW_ABNORMAL_THRESHOLD:'최근 자료 채움이 이상 기준 미만입니다',
      RECENT_INFERRED_GRID_AVAILABILITY_BELOW_NORMAL_THRESHOLD:'최근 자료 채움이 정상 기준 미만입니다',
      LAST_OBSERVATION_AGE_EXCEEDS_ABNORMAL_THRESHOLD:'최근 관측 지연이 이상 기준을 넘었습니다',
      LAST_OBSERVATION_AGE_EXCEEDS_WARNING_THRESHOLD:'최근 관측 지연이 주의 기준을 넘었습니다',
      RECENT_FINITE_VALUE_FRACTION_BELOW_ABNORMAL_THRESHOLD:'수치가 있는 관측시각 비율이 이상 기준 미만입니다',
      RECENT_FINITE_VALUE_FRACTION_BELOW_NORMAL_THRESHOLD:'수치가 있는 관측시각 비율이 정상 기준 미만입니다',
      NO_CURRENT_OR_PRIOR_OBSERVATION_EVIDENCE:'현재와 이전 기간의 관측 근거가 없습니다',
      NO_OBSERVATIONS_IN_RECENT_WINDOW:'최근 24시간에 관측자료가 없습니다',
      CONFLICTING_VALUES_AT_DUPLICATE_CLOCKS:'같은 관측시각에 서로 다른 원천값이 있습니다',
      RECENT_INTERPRETED_BAD_QC_AT_ABNORMAL_THRESHOLD:'판본을 확인한 불량 QC 비율이 이상 기준입니다',
      RECENT_INTERPRETED_BAD_OR_SUSPECT_QC_PRESENT:'판본을 확인한 불량·의심 QC가 있습니다',
      CHANNELS_NOT_EVALUATED:'일부 관측항목은 판정 근거가 부족합니다',
      INSUFFICIENT_CLOCKS:'관측간격을 추정할 시각 수가 부족합니다',
      AMBIGUOUS_INTERVAL_MODE:'최빈 관측간격을 하나로 정할 수 없습니다',
      INTERVAL_MODE_NOT_DOMINANT:'일정한 관측간격의 비율이 충분하지 않습니다',
      RECEIPT_COLLECTION_RATE_NOT_EVALUATED:'실제 수신 수집률',
      SOURCE_TIMEZONE_UNAPPROVED:'원천 시간대 확정',
      SOURCE_UNIT_AND_SENSOR_EFFECTIVE_PERIOD_UNCONFIRMED:'단위·센서 유효기간 확정',
      EQUIPMENT_HEALTH_NOT_EVALUATED:'장비 건강 확정',
      SOURCE_QC_CODEBOOK_EFFECTIVE_PERIOD_MISSING:'QC 판본·시행기간 해석',
      DATED_INSPECTION_EVIDENCE_MISSING_OR_UNUSABLE:'기준일 이전 점검 이력',
    };
    const dated=/^DATED_(INSPECTION|OPERATIONS|QUALITY_REPORTS|QC_HISTORY|EVENT_REGISTRY)_EVIDENCE_(NORMAL|WARNING|ABNORMAL)$/.exec(value);
    if(dated)return '기준일 이전 '+({INSPECTION:'점검',OPERATIONS:'운영',QUALITY_REPORTS:'품질 보고',QC_HISTORY:'QC 이력',EVENT_REGISTRY:'사건'} as Record<string,string>)[dated[1]]+' 근거: '+({NORMAL:'정상',WARNING:'주의',ABNORMAL:'이상'} as Record<string,string>)[dated[2]];
    return translations[value]||value;
  }
  if(value&&typeof value==='object')return String(value.message||value.detail||value.code||'근거 확인 필요');
  return '근거 확인 필요';
}
