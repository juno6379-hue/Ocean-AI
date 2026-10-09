export type QCScope={source:string;from:string;to:string;day:string;time:string;station:string;item:string;network:string;sea:string;qcField:string;qcLiteral:string|null;qcNull:boolean;qcLiteralSet:boolean};
export type QCLiteral=string|number|boolean|null;
export type QCDistribution={field:string;literal:QCLiteral;count:number;denominator:number;rate:number|null;interpreted:false};
export type QCMonth={month:string;held_rows:number;qc_present_rows:number|null;qc_presence_rate:number|null;missing_rows:number|null;missing_rate:number|null;unassessed_rate:number|null;interpreted:false};
export type QCMatrix={station_code:string;station_name:string;item_code:string;held_rows:number;qc_present_rows:number;qc_presence_rate:number|null;missing_rows:number;missing_rate:number|null;unassessed_rate:number|null;state:'UNKNOWN';typed_grains:{depth_step:unknown;depth_from:unknown;depth_to:unknown}[]};
export type QCCase={case_key:string;station_code:string;item_code:string;depth_step:unknown;depth_from:unknown;depth_to:unknown;observed_time_raw:string;value_raw:unknown;source_qc_raw:QCLiteral;source_mq_raw:QCLiteral;source_n1_qc_raw:QCLiteral;source_sha256:string;parquet_sha256:string;file:string;file_row_number:number;physical_sensor_id:null;unit:null;timezone:null;classification:'UNINTERPRETED';available_at:null};
export type QCMetric={count:number|null;rate?:number|null;denominator?:number|null;status:string};
export type QCWorkspacePacket={schema_version:'qc-workspace-1';source:string;snapshot:string;from_month:string;to_month:string;as_of_day:string;as_of_time:string;cutoff_native:string;result_sha256:string;
  scope:{station:string;item:string;network:string;sea:string;qc_field:string|null;qc_literal:QCLiteral;qc_literal_is_null:boolean};
  filters:{stations:{station_code:string;station_name:string;network_type:string|null;sea_area:string|null;classification_state:string;held_rows:number}[];items:{item_code:string;held_rows:number}[];networks:{value:string;label:string;count:number}[];seas:{value:string;label:string;count:number}[]};
  cards:{held_rows:number;normal:QCMetric;warning:QCMetric;bad:QCMetric;missing:QCMetric;unassessed:QCMetric;pending:QCMetric;completed:QCMetric};raw:unknown;distribution:QCDistribution[];monthly:QCMonth[];matrix:QCMatrix[];
  cases:{rows:QCCase[];total_matching_rows:number;limit:number;ordering:'NATIVE_CLOCK_DESC_FILE_ROW_DESC';population:'RAW_SOURCE_ROWS_NOT_ANOMALY_RESULTS'};
  rules:{catalog_version:string;catalog_count:number;registered_definition_count:number|null;result_count:number|null;items:{kind:string;name_ko:string;status:string;evaluated_count:number|null;anomaly_count:number|null;not_evaluated_count:number|null;reasons:string[]}[]};
  review:{status:string;ai_prediction_count:number|null;ai_label_count:number|null;workflow_count:number|null;approved_count:number|null;source_fact_status:string;reasons:string[]};
  capabilities:{review:boolean;hold:boolean;flag_change:boolean;approve:boolean;reason:string};global_registry:{state:string;counts:Record<string,number|null>;scope:string};provenance:Record<string,unknown>;
};

const count=(v:unknown):v is number=>typeof v==='number'&&Number.isSafeInteger(v)&&v>=0;
const rate=(v:unknown)=>v===null||(typeof v==='number'&&Number.isFinite(v)&&v>=0&&v<=100);
const hash=(v:unknown)=>typeof v==='string'&&/^[a-f0-9]{64}$/.test(v);
const literal=(v:unknown)=>v===null||typeof v==='string'||typeof v==='boolean'||(typeof v==='number'&&Number.isFinite(v));
const strings=(v:unknown)=>Array.isArray(v)&&v.every(x=>typeof x==='string');
const metric=(v:any)=>v&&typeof v.status==='string'&&(v.count===null||count(v.count))&&(v.rate===undefined||rate(v.rate))&&(v.denominator===undefined||v.denominator===null||count(v.denominator));
const clock=(v:unknown)=>{
  const m=typeof v==='string'?/^(\d{4})-(0[1-9]|1[0-2])-([0-2]\d|3[01])[ T]([01]\d|2[0-3]):([0-5]\d):([0-5]\d)(?:\.\d{1,6})?$/.exec(v):null;
  if(!m)return false;const [year,month,day,hour,minute,second]=m.slice(1,7).map(Number),d=new Date(0);d.setUTCFullYear(year,month-1,day);d.setUTCHours(hour,minute,second,0);
  return d.getUTCFullYear()===year&&d.getUTCMonth()===month-1&&d.getUTCDate()===day&&d.getUTCHours()===hour&&d.getUTCMinutes()===minute&&d.getUTCSeconds()===second;
};
const comparable=(s:string)=>s.replace('T',' ').split('.')[0]+'.'+(s.split('.')[1]||'').padEnd(6,'0');
const weighted=(n:number|null,d:number,r:number|null)=>d===0?r===null&&(n===0||n===null):typeof n==='number'&&typeof r==='number'&&Math.abs(r-100*n/d)<.0001;
const heldCount=(n:unknown,d:number)=>d===0?n===0||n===null:count(n)&&n<=d;

/** Accept exact native scope only; unknown flags are never promoted to approved QC. */
export function validQCWorkspace(v:any,s:QCScope):v is QCWorkspacePacket {
  if(!v||v.schema_version!=='qc-workspace-1'||v.source!==s.source||v.from_month!==s.from||v.to_month!==s.to
    ||v.as_of_day!==s.day||v.as_of_time!==s.time||v.cutoff_native!==s.day+' '+s.time||!clock(v.cutoff_native)
    ||typeof v.snapshot!=='string'||!v.snapshot||!hash(v.result_sha256))return false;
  const scope=v.scope;if(!scope||scope.station!==s.station||scope.item!==s.item||scope.network!==s.network||scope.sea!==s.sea
    ||(scope.qc_field??'')!==s.qcField||scope.qc_literal_is_null!==s.qcNull
    ||(s.qcNull?scope.qc_literal!==null:s.qcLiteralSet?scope.qc_literal!==s.qcLiteral:scope.qc_literal!==null))return false;
  const c=v.cards;if(!c||!count(c.held_rows)||!['normal','warning','bad','missing','unassessed','pending','completed'].every(k=>metric(c[k])))return false;
  if(['normal','warning','bad'].some(k=>c[k].status!=='NOT_EVALUATED'||c[k].count!==null||c[k].rate!==null||c[k].denominator!==null))return false;
  if(c.missing.denominator!==c.held_rows||!heldCount(c.missing.count,c.held_rows)||!weighted(c.missing.count,c.held_rows,c.missing.rate))return false;
  if(c.unassessed.status==='SOURCE_QC_UNINTERPRETED'&&(c.unassessed.count!==c.held_rows||c.unassessed.denominator!==c.held_rows||!weighted(c.unassessed.count,c.held_rows,c.unassessed.rate)))return false;
  for(const key of ['pending','completed'])if(c[key].status==='GLOBAL_EMPTY'&&c[key].count!==0)return false;
  const f=v.filters;if(!f||!['stations','items','networks','seas'].every(k=>Array.isArray(f[k])))return false;
  if(f.stations.some((r:any)=>typeof r.station_code!=='string'||typeof r.station_name!=='string'||!count(r.held_rows))||new Set(f.stations.map((r:any)=>r.station_code)).size!==f.stations.length)return false;
  if(f.items.some((r:any)=>typeof r.item_code!=='string'||!count(r.held_rows))||new Set(f.items.map((r:any)=>r.item_code)).size!==f.items.length)return false;
  if(['networks','seas'].some(k=>f[k].some((r:any)=>typeof r.value!=='string'||typeof r.label!=='string'||!count(r.count))))return false;
  if(!Array.isArray(v.distribution)||v.distribution.some((r:any)=>typeof r.field!=='string'||!literal(r.literal)||!count(r.count)||!count(r.denominator)||r.count>r.denominator||r.interpreted!==false||!weighted(r.count,r.denominator,r.rate)))return false;
  const distributionKeys=v.distribution.map((r:any)=>JSON.stringify([r.field,r.literal]));if(new Set(distributionKeys).size!==distributionKeys.length)return false;
  for(const field of new Set<string>(v.distribution.map((r:any)=>r.field))){const rows=v.distribution.filter((r:any)=>r.field===field),denominator=rows[0].denominator;if(denominator>c.held_rows||rows.some((r:any)=>r.denominator!==denominator)||rows.reduce((n:number,r:any)=>n+r.count,0)!==denominator)return false;}
  if(!Array.isArray(v.monthly)||v.monthly.some((r:any)=>typeof r.month!=='string'||!/^\d{4}-(0[1-9]|1[0-2])$/.test(r.month)||r.month<s.from||r.month>s.to||r.month>s.day.slice(0,7)||r.interpreted!==false||!count(r.held_rows)||!heldCount(r.qc_present_rows,r.held_rows)||!heldCount(r.missing_rows,r.held_rows)||!weighted(r.qc_present_rows,r.held_rows,r.qc_presence_rate)||!weighted(r.missing_rows,r.held_rows,r.missing_rate)||!rate(r.unassessed_rate)))return false;
  if(new Set(v.monthly.map((r:any)=>r.month)).size!==v.monthly.length||v.monthly.reduce((n:number,r:any)=>n+r.held_rows,0)!==c.held_rows)return false;
  if(!Array.isArray(v.matrix)||v.matrix.some((r:any)=>typeof r.station_code!=='string'||typeof r.station_name!=='string'||typeof r.item_code!=='string'||(s.station&&r.station_code!==s.station)||(s.item&&r.item_code!==s.item)||r.state!=='UNKNOWN'||!count(r.held_rows)||!count(r.qc_present_rows)||!count(r.missing_rows)||r.qc_present_rows>r.held_rows||r.missing_rows>r.held_rows||!weighted(r.qc_present_rows,r.held_rows,r.qc_presence_rate)||!weighted(r.missing_rows,r.held_rows,r.missing_rate)||!rate(r.unassessed_rate)||!Array.isArray(r.typed_grains)))return false;
  if(new Set(v.matrix.map((r:any)=>JSON.stringify([r.station_code,r.item_code]))).size!==v.matrix.length||v.matrix.reduce((n:number,r:any)=>n+r.held_rows,0)!==c.held_rows)return false;
  const cases=v.cases;if(!cases||cases.population!=='RAW_SOURCE_ROWS_NOT_ANOMALY_RESULTS'||cases.ordering!=='NATIVE_CLOCK_DESC_FILE_ROW_DESC'||!count(cases.limit)||cases.limit>100||!count(cases.total_matching_rows)||cases.total_matching_rows>c.held_rows||!Array.isArray(cases.rows)||cases.rows.length>cases.limit||cases.rows.length>cases.total_matching_rows)return false;
  if(cases.rows.some((r:any)=>typeof r.case_key!=='string'||!r.case_key||typeof r.station_code!=='string'||typeof r.item_code!=='string'||(s.station&&r.station_code!==s.station)||(s.item&&r.item_code!==s.item)||!clock(r.observed_time_raw)||comparable(r.observed_time_raw)>comparable(v.cutoff_native)||r.observed_time_raw.slice(0,7)<s.from||r.observed_time_raw.slice(0,7)>s.to||!hash(r.source_sha256)||!hash(r.parquet_sha256)||typeof r.file!=='string'||!count(r.file_row_number)||r.classification!=='UNINTERPRETED'||r.unit!==null||r.timezone!==null||r.physical_sensor_id!==null||r.available_at!==null||!['source_qc_raw','source_mq_raw','source_n1_qc_raw'].every(k=>literal(r[k]))))return false;
  if(new Set(cases.rows.map((r:any)=>r.case_key)).size!==cases.rows.length)return false;
  const aliases:Record<string,string>={qc_raw:'source_qc_raw',mq_raw:'source_mq_raw',n1_aqc_raw:'source_n1_qc_raw',QC_FLAG:'source_qc_raw',MQC_FLAG:'source_mq_raw',N1_AQC_FLAG:'source_n1_qc_raw'};
  if(s.qcField&&(!aliases[s.qcField]||cases.rows.some((r:any)=>s.qcNull?r[aliases[s.qcField]]!==null:s.qcLiteralSet?r[aliases[s.qcField]]!==s.qcLiteral:false)))return false;
  const rules=v.rules;if(!rules||typeof rules.catalog_version!=='string'||!count(rules.catalog_count)||(rules.registered_definition_count!==null&&!count(rules.registered_definition_count))||(rules.result_count!==null&&!count(rules.result_count))||!Array.isArray(rules.items)||rules.items.length!==rules.catalog_count)return false;
  if(rules.items.some((r:any)=>typeof r.kind!=='string'||typeof r.name_ko!=='string'||typeof r.status!=='string'||!strings(r.reasons)||['evaluated_count','anomaly_count','not_evaluated_count'].some(k=>r[k]!==null&&!count(r[k]))||r.status==='NOT_EVALUATED'&&r.anomaly_count!==null&&r.anomaly_count!==0)||new Set(rules.items.map((r:any)=>r.kind)).size!==rules.items.length)return false;
  const review=v.review;if(!review||typeof review.status!=='string'||typeof review.source_fact_status!=='string'||!strings(review.reasons)||['ai_prediction_count','ai_label_count','workflow_count','approved_count'].some(k=>review[k]!==null&&!count(review[k])))return false;
  if(!v.capabilities||typeof v.capabilities.reason!=='string'||['review','hold','flag_change','approve'].some(k=>typeof v.capabilities[k]!=='boolean'))return false;
  if(!v.provenance||v.provenance.approved!==false||v.provenance.source_qc_interpreted!==false||v.provenance.simulated_included!==false||v.provenance.production_writes!==0)return false;
  const registry=v.global_registry;if(!registry||registry.scope!=='GLOBAL_REGISTERED_NOT_SELECTED_RESULTS'||!registry.counts)return false;
  for(const key of ['pending','completed']){const tables=key==='pending'?['qc_flag_history','ai_label','agent_task_approvals','agent_workflow_run']:['approval_history','agent_workflow_run','agent_workflow_transition'];if(c[key].status==='GLOBAL_EMPTY'&&tables.some(table=>registry.counts[table]!==0))return false;if(c[key].status==='UNVERIFIED_SCOPE'&&c[key].count!==null)return false;}
  return true;
}

export const qcLiteralLabel=(value:unknown)=>value===null?'NULL':value===''?'빈 문자열':JSON.stringify(value);
export const qcNumber=(value:unknown)=>typeof value==='number'&&Number.isFinite(value)?new Intl.NumberFormat('ko-KR',{maximumFractionDigits:1}).format(value):'—';
/** Observation and AI comparison values keep precision independently of rounded KPI rates. */
export const qcValueNumber=(value:unknown)=>typeof value==='number'&&Number.isFinite(value)?new Intl.NumberFormat('ko-KR',value!==0&&Math.abs(value)<.000001?{notation:'scientific',maximumSignificantDigits:6}:{maximumFractionDigits:6}).format(Object.is(value,-0)?0:value):'—';
export const qcPercent=(value:unknown)=>typeof value==='number'&&Number.isFinite(value)?qcNumber(value)+'%':'—';
export const qcReasonText=(value:string)=>({SOURCE_SEMANTIC_UNIT_AND_SENSOR_EPISODE_UNRESOLVED:'원천 의미·단위와 물리 센서의 유효기간 확인 필요',SOURCE_QC_CODEBOOK_EFFECTIVE_PERIOD_UNRESOLVED:'원문 QC 코드북·판본·시행기간 확인 필요',NATIVE_CLOCK_TIMEZONE_AND_AVAILABILITY_UNRESOLVED:'원문 시각의 시간대와 자료 가용시각 확인 필요',APPROVED_QC_LEDGER_NOT_BOUND_TO_SELECTED_RAW_ROWS:'선택 원천 행에 승인된 QC 원장이 연결되지 않음'} as Record<string,string>)[value]||value;
export const qcStateLabel=(value:unknown)=>({SERVER_LOCAL_OFFSET:'서버 기준시각',UNAPPROVED_NATIVE_SOURCE_CLOCK:'원문 기준시각 · 시간대 미확정',RULE_QC:'1차 QC',REVIEW_WORKFLOW:'검토 이력',RECOMMENDATION_WORKFLOW:'권고 검토 작업 · Final QC와 별도',RAW_VALUE_LITERAL:'원문 빈값',SOURCE_QC_UNINTERPRETED:'원문 QC 의미 미해석',UNKNOWN:'미확인',UNVERIFIED:'판정 근거 확인 필요',UNVERIFIED_SCOPE:'선택 범위 연결 근거 미확정',NOT_EVALUATED:'미평가',NOT_EXECUTED:'분석 미실행',NOT_RUN:'분석 미실행',NO_MODEL:'사용 가능한 모델 없음',NO_EVIDENCE:'근거 없음',NO_CASES:'검토 후보 없음',GLOBAL_EMPTY:'해당 기록 없음',PARTIAL:'일부 근거만 확인',NO_DATA:'데이터 없음',EVALUATED:'평가됨',READY:'조회 완료',RECEIPT_VERIFIED_ONLY:'승인 원천 계약 확인',UNRESOLVED:'원천 사실 확인 필요',UNREVIEWED:'미검토',NO_LINKED_WORKFLOW:'연결된 검토 작업 없음',AMBIGUOUS:'여러 검토 작업 연결 확인 필요',PENDING:'담당자 검토 대기',APPROVED:'검토 결정 승인',REJECTED:'검토 반려',CANCELLED:'작업 취소',RESUMING:'승인 작업 재개 중',COMPLETED:'권고 검토 작업 완료'} as Record<string,string>)[String(value)]||String(value??'확인 전');

/** Literal filters affect the sampled case table and preserve every raw character. */
export function qcLiteralQuery(search:URLSearchParams,row:QCDistribution|null){
  const next=new URLSearchParams(search);for(const key of ['qc_field','qc_literal','qc_literal_is_null','case_q'])next.delete(key);
  if(row){next.set('qc_field',row.field);if(row.literal===null)next.set('qc_literal_is_null','true');else next.set('qc_literal',String(row.literal));}return next;
}

/** Applying edited dates preserves the explicitly chosen native clock. */
export function qcPeriodQuery(search:URLSearchParams,draft:{from:string;to:string;day:string;time:string}){
  const month=/^20\d{2}-(0[1-9]|1[0-2])$/;
  if(!month.test(draft.from)||!month.test(draft.to)||draft.from>draft.to||draft.to>draft.day.slice(0,7)||!clock(draft.day+' '+draft.time))return null;
  const span=(Number(draft.to.slice(0,4))-Number(draft.from.slice(0,4)))*12+Number(draft.to.slice(5))-Number(draft.from.slice(5))+1;if(span>48)return null;
  const next=new URLSearchParams(search);next.set('from',draft.from);next.set('to',draft.to);next.set('as_of_day',draft.day);next.set('as_of_time',draft.time);return next;
}

/** Month holes remain null and do not become false good/zero-failure months. */
export function qcTrendRows(rows:QCMonth[],from:string,to:string){
  if(!/^\d{4}-(0[1-9]|1[0-2])$/.test(from)||!/^\d{4}-(0[1-9]|1[0-2])$/.test(to)||from>to)return [];
  const found=new Map(rows.map(r=>[r.month,r])),result:any[]=[];
  let [year,month]=from.split('-').map(Number);while(`${String(year).padStart(4,'0')}-${String(month).padStart(2,'0')}`<=to&&result.length<1200){
    const key=`${String(year).padStart(4,'0')}-${String(month).padStart(2,'0')}`,row=found.get(key);
    result.push(row?{...row,value_present_rate:row.missing_rate===null?null:100-row.missing_rate}:{month:key,held_rows:null,qc_presence_rate:null,missing_rate:null,unassessed_rate:null,value_present_rate:null});
    if(++month===13){month=1;year++;}
  }return result;
}

export function qcCaseRows(rows:QCCase[],search:string,sort='clock_desc',names:Record<string,string>={}){
  const query=search.trim().toLocaleLowerCase('ko-KR');
  const result=rows.filter(row=>!query||[row.station_code,names[row.station_code],row.item_code,row.observed_time_raw,row.value_raw,qcLiteralLabel(row.source_qc_raw),qcLiteralLabel(row.source_mq_raw),qcLiteralLabel(row.source_n1_qc_raw),row.file].some(v=>String(v??'').toLocaleLowerCase('ko-KR').includes(query)));
  return result.sort((a,b)=>sort==='station'?a.station_code.localeCompare(b.station_code)||a.item_code.localeCompare(b.item_code)||comparable(b.observed_time_raw).localeCompare(comparable(a.observed_time_raw))||a.case_key.localeCompare(b.case_key):sort==='clock_asc'?comparable(a.observed_time_raw).localeCompare(comparable(b.observed_time_raw))||a.case_key.localeCompare(b.case_key):comparable(b.observed_time_raw).localeCompare(comparable(a.observed_time_raw))||a.case_key.localeCompare(b.case_key));
}
export function qcPage<T>(rows:T[],requested:number,size=5){
  const pages=Math.max(1,Math.ceil(rows.length/size)),page=Math.min(pages,Math.max(1,Number.isFinite(requested)?Math.floor(requested):1));
  return {page,pages,rows:rows.slice((page-1)*size,page*size),first:rows.length?(page-1)*size+1:0,last:Math.min(page*size,rows.length)};
}
export function nextQCHeatmapCell(index:number,key:string,rows:number,columns:number,enabled?:boolean[]){
  if(rows<1||columns<1)return 0;const last=rows*columns-1,step=key==='ArrowDown'?columns:key==='ArrowUp'?-columns:key==='ArrowLeft'||key==='End'?-1:1;
  let candidate=Math.max(0,Math.min(last,key==='ArrowRight'?index+1:key==='ArrowLeft'?index-1:key==='ArrowDown'?index+columns:key==='ArrowUp'?index-columns:key==='Home'?Math.floor(index/columns)*columns:key==='End'?Math.floor(index/columns)*columns+columns-1:index));
  if(!enabled)return candidate;
  const lower=key==='Home'||key==='End'?Math.floor(index/columns)*columns:0,upper=key==='Home'||key==='End'?lower+columns-1:last;
  while(candidate>=lower&&candidate<=upper){if(enabled[candidate])return candidate;candidate+=step;}return index;
}

/** Write buttons require an exact workflow target, capabilities and authenticated role. */
export function qcActionAvailability(packet:QCWorkspacePacket|null,actor:{user_id:string;role:string}|null,action:'hold'|'flag_change'|'approve'){
  const reason=!packet?'선택 범위의 검증된 QC 자료가 없습니다.':!packet.capabilities[action]?packet.capabilities.reason:!actor?'승인 계정은 실제 운영 단계에서 설정합니다.':!['reviewer','admin'].includes(actor.role)?'담당 검토 권한이 필요합니다.':'선택 원천 행을 승인할 workflow 대상·판본·hash 연결이 없습니다.';
  // This packet contains raw rows only. Existing authenticated workflow tools handle actual writes.
  return {enabled:false,reason};
}

export type QCFlag={code:string;label:string;color:string;semantic:string;stage:string;definition_source:string;color_policy:string};
export type QCDailyWindow={source:string;mode:'OPERATIONAL'|'ARCHIVE';preset:string;start:string;end:string;as_of:string;clock_basis:string;offset:string|null;granularity:'hour'|'day';window_id:string};
export type QCContext={schema_version:'qc-context-1';server_now:string;today:string;current_time:string;clock_basis:string;offset:string;sources:{value:string;label:string;mode:string;available:boolean;clock_basis?:string}[];default_source:'REGISTERED';default_preset:'today';presets:string[];flag_catalog:QCFlag[]};
export type QCDailyMetric={count:number|null;rate:number|null;denominator:number|null;state:string;stage:string};
export type QCDailyCounts={normal:number;suspect:number;bad:number;missing:number;unknown:number};
export type QCDailyCandidate={id:string;kind:string;station_id:string;station_name?:string;variable_code:string;observation_time:string;value:number|null;flag:string;rule_name?:string;severity?:string;priority?:number;review_status:string;anomaly_score?:number|null;[key:string]:unknown};
export type QCDailyOverview={schema_version:'qc-overview-1';source:string;snapshot:string|null;window:QCDailyWindow;scope:{station_id:string;variable_code:string;network:string;sea:string;flag:string};total_observations:number;
 summary:Record<'normal'|'suspect'|'bad'|'missing'|'pending'|'completed',QCDailyMetric>;flag_catalog:QCFlag[];
 flag_distribution:{code:string;label:string;color:string;semantic:string;count:number;rate:number|null;denominator:number;stage:string}[];
 quality_trend:{bucket:string;start:string;end:string;total:number;counts:QCDailyCounts;rates:Record<keyof QCDailyCounts,number|null>;state:string}[];
 rule_qc_counts:{catalog_version:string;registered_definition_count:number|null;registered_definitions?:{rule_id:string;rule_name:string;rule_version:string;active:boolean;rule_type:string}[];definitions_truncated?:boolean;items:{rule_id:string;rule_name:string;rule_type:string;rule_version:string;evaluated_count:number|null;anomaly_count:number|null;share:number|null;state:string}[]};
 station_variable_matrix:{station_id:string;station_name:string;variable_code:string;total:number;counts:QCDailyCounts;rates:Record<keyof QCDailyCounts,number|null>;state:string;top_rule:string|null;recent_issue_time:string|null}[];
 review_queue:{rows:QCDailyCandidate[];total:number|null;validated_subset_total?:number;limit:number;offset:number;state:string};archive_samples:{rows:any[];total_matching_rows:number;limit:number;state:string}|null;
 filters?:{stations:{station_id:string;station_name:string}[];variables:{variable_code:string;label?:string}[];networks:{value:string;label:string}[];seas:{value:string;label:string}[]};states:Record<string,unknown>;provenance:Record<string,unknown>;result_sha256:string;
};
export type QCDailyRequest={source:string;preset:string;dateFrom?:string;dateTo?:string;station:string;item:string;network:string;sea:string;flag:string;limit:number;offset:number;clockAnchor?:{day:string;offset:string;serverNow:string}};

/** Only explicit offsets are compared as instants; naive archives remain native calendars. */
export function qcClockCoordinate(value:unknown,source:string):number|null {
 if(typeof value!=='string')return null;
 const m=/^(\d{4}-\d{2}-\d{2})[ T](\d{2}:\d{2}:\d{2})(?:\.(\d{1,6}))?(Z|[+-]\d{2}:\d{2})?$/.exec(value);if(!m)return null;
 if(source==='REGISTERED'?!m[4]:!!m[4])return null;
 const raw=m[1]+' '+m[2]+(m[3]?'.'+m[3]:'');if(!clock(raw))return null;
 const [year,month,day]=m[1].split('-').map(Number),[hour,minute,second]=m[2].split(':').map(Number),d=new Date(0);d.setUTCFullYear(year,month-1,day);d.setUTCHours(hour,minute,second,0);
 let offset=0;if(m[4]&&m[4]!=='Z'){const h=Number(m[4].slice(1,3)),min=Number(m[4].slice(4));if(h>23||min>59)return null;offset=(m[4][0]==='-'?-1:1)*(h*60+min)*60*1e6;}
 const coordinate=d.getTime()*1000+Number((m[3]||'').padEnd(6,'0'))-offset;return Number.isSafeInteger(coordinate)?coordinate:null;
}
const validFlag=(v:any)=>v&&typeof v.code==='string'&&typeof v.label==='string'&&/^#[0-9a-f]{6}$/i.test(v.color)&&typeof v.semantic==='string'&&typeof v.stage==='string'&&typeof v.definition_source==='string'&&typeof v.color_policy==='string';
export function validQCContext(v:any):v is QCContext {
 return Boolean(v&&v.schema_version==='qc-context-1'&&qcClockCoordinate(v.server_now,'REGISTERED')!==null&&v.today===v.server_now.slice(0,10)&&typeof v.current_time==='string'&&v.clock_basis==='SERVER_LOCAL_OFFSET'&&/^[+-]\d{2}:\d{2}$/.test(v.offset)&&v.server_now.endsWith(v.offset)&&v.default_source==='REGISTERED'&&v.default_preset==='today'&&Array.isArray(v.presets)&&['today','yesterday','7d','30d','custom'].every(p=>v.presets.includes(p))&&Array.isArray(v.sources)&&v.sources.some((s:any)=>s.value==='REGISTERED'&&s.mode==='OPERATIONAL'&&s.available===true)&&Array.isArray(v.flag_catalog)&&v.flag_catalog.every(validFlag));
}
export function validQCDailyWindow(v:any,source:string){
 const start=qcClockCoordinate(v?.start,source),end=qcClockCoordinate(v?.end,source),asof=qcClockCoordinate(v?.as_of,source);
 const explicitOffset=(s:unknown)=>typeof s==='string'?/(Z|[+-]\d{2}:\d{2})$/.exec(s)?.[1]?.replace('Z','+00:00'):undefined;
 const expectedGranularity=v?.preset==='today'||v?.preset==='yesterday'?'hour':v?.preset==='7d'||v?.preset==='30d'?'day':start!==null&&end!==null&&end-start<2*86400*1e6?'hour':'day';
 return Boolean(v&&v.source===source&&v.mode===(source==='REGISTERED'?'OPERATIONAL':'ARCHIVE')&&['today','yesterday','7d','30d','custom'].includes(v.preset)&&(source==='REGISTERED'||v.preset==='custom')&&v.clock_basis===(source==='REGISTERED'?'SERVER_LOCAL_OFFSET':'UNAPPROVED_NATIVE_SOURCE_CLOCK')&&hash(v.window_id)&&v.granularity===expectedGranularity&&start!==null&&end!==null&&asof!==null&&start<=end&&end-start<31*86400*1e6&&end===asof&&(source==='REGISTERED'?typeof v.offset==='string'&&explicitOffset(v.start)===v.offset&&explicitOffset(v.end)===v.offset&&explicitOffset(v.as_of)===v.offset:v.offset===null));
}
function shiftedQCDay(day:string,delta:number){const [year,month,date]=day.split('-').map(Number),d=new Date(0);d.setUTCFullYear(year,month-1,date+delta);d.setUTCHours(0,0,0,0);return d.toISOString().slice(0,10);}
function matchesQCClockAnchor(w:QCDailyWindow,r:QCDailyRequest){
 if(!r.clockAnchor||r.source!=='REGISTERED')return true;const a=r.clockAnchor;if(w.offset!==a.offset)return false;if(r.preset==='custom')return true;
 const days=r.preset==='yesterday'?-1:r.preset==='7d'?-6:r.preset==='30d'?-29:0,midnight=qcClockCoordinate(a.day+'T00:00:00'+a.offset,'REGISTERED'),start=qcClockCoordinate(shiftedQCDay(a.day,days)+'T00:00:00'+a.offset,'REGISTERED'),end=qcClockCoordinate(w.end,'REGISTERED');
 return midnight!==null&&start!==null&&end!==null&&qcClockCoordinate(w.start,'REGISTERED')===start&&(r.preset==='yesterday'?end===midnight-1:w.end.slice(0,10)===a.day&&end>=qcClockCoordinate(a.serverNow,'REGISTERED')!);
}
const dailyCounts=(v:any,total:number)=>v&&['normal','suspect','bad','missing','unknown'].every(k=>count(v[k]))&&['normal','suspect','bad','missing','unknown'].reduce((sum,k)=>sum+v[k],0)===total;
const dailyRates=(v:any,c:QCDailyCounts,total:number,partial=false)=>v&&['normal','suspect','bad','missing','unknown'].every(k=>partial?v[k]===null:weighted(c[k as keyof QCDailyCounts],total,v[k]));
export function validQCDailyOverview(v:any,r:QCDailyRequest):v is QCDailyOverview {
 if(!v||v.schema_version!=='qc-overview-1'||v.source!==r.source||!validQCDailyWindow(v.window,r.source)||v.window.preset!==r.preset||!hash(v.result_sha256)||!count(v.total_observations))return false;
 if(!matchesQCClockAnchor(v.window,r))return false;
 if(r.dateFrom&&qcClockCoordinate(v.window.start,r.source)!==qcClockCoordinate(r.dateFrom,r.source)||r.dateTo&&qcClockCoordinate(v.window.end,r.source)!==qcClockCoordinate(r.dateTo,r.source))return false;
 if(!v.scope||v.scope.station_id!==r.station||v.scope.variable_code!==r.item||v.scope.network!==r.network||v.scope.sea!==r.sea||v.scope.flag!==r.flag)return false;
 if(!v.summary||['normal','suspect','bad','missing','pending','completed'].some(k=>!v.summary[k]||!metric({...v.summary[k],status:v.summary[k].state})||typeof v.summary[k].stage!=='string'))return false;
 for(const key of ['normal','suspect','bad','missing']){const m=v.summary[key];if(m.denominator!==v.total_observations||m.count!==null&&(m.count>v.total_observations||!weighted(m.count,m.denominator,m.rate))||v.source!=='REGISTERED'&&key!=='missing'&&(m.count!==null||m.rate!==null)||v.states?.overall==='PARTIAL'&&(m.count!==null||m.rate!==null))return false;}
 if(!Array.isArray(v.flag_catalog)||v.flag_catalog.some((f:any)=>!validFlag(f))||new Set(v.flag_catalog.map((f:any)=>f.code)).size!==v.flag_catalog.length)return false;
 const flags=new Map<string,QCFlag>(v.flag_catalog.map((f:any)=>[f.code,f])),partial=v.states?.overall==='PARTIAL';
 if(!Array.isArray(v.flag_distribution)||v.flag_distribution.some((f:any)=>!flags.has(f.code)||flags.get(f.code)!.label!==f.label||flags.get(f.code)!.color!==f.color||flags.get(f.code)!.semantic!==f.semantic||flags.get(f.code)!.stage!==f.stage||!count(f.count)||f.denominator!==v.total_observations||(partial?f.rate!==null:!weighted(f.count,f.denominator,f.rate)))||new Set(v.flag_distribution.map((f:any)=>f.code)).size!==v.flag_distribution.length)return false;
 if(v.flag_distribution.reduce((sum:number,f:any)=>sum+f.count,0)!==v.total_observations)return false;
 const inside=(time:string)=>{const c=qcClockCoordinate(time,r.source);return c!==null&&c>=qcClockCoordinate(v.window.start,r.source)!&&c<=qcClockCoordinate(v.window.end,r.source)!;};
 if(!Array.isArray(v.quality_trend)||v.quality_trend.some((t:any)=>typeof t.bucket!=='string'||!count(t.total)||!dailyCounts(t.counts,t.total)||!dailyRates(t.rates,t.counts,t.total,partial)||!inside(t.start)||!inside(t.end)||qcClockCoordinate(t.start,r.source)!>qcClockCoordinate(t.end,r.source)!)||new Set(v.quality_trend.map((t:any)=>t.bucket)).size!==v.quality_trend.length)return false;
 if(v.quality_trend.reduce((sum:number,t:any)=>sum+t.total,0)!==v.total_observations)return false;
 if(!Array.isArray(v.station_variable_matrix)||v.station_variable_matrix.some((m:any)=>typeof m.station_id!=='string'||typeof m.station_name!=='string'||typeof m.variable_code!=='string'||(r.station&&m.station_id!==r.station)||(r.item&&m.variable_code!==r.item)||!count(m.total)||!dailyCounts(m.counts,m.total)||!dailyRates(m.rates,m.counts,m.total,partial)||typeof m.state!=='string'||(m.recent_issue_time!==null&&!inside(m.recent_issue_time)))||new Set(v.station_variable_matrix.map((m:any)=>JSON.stringify([m.station_id,m.variable_code]))).size!==v.station_variable_matrix.length)return false;
 if(v.station_variable_matrix.reduce((sum:number,m:any)=>sum+m.total,0)!==v.total_observations)return false;
 if(!v.rule_qc_counts||!Array.isArray(v.rule_qc_counts.items)||v.rule_qc_counts.items.some((t:any)=>typeof t.rule_id!=='string'||typeof t.rule_name!=='string'||typeof t.rule_type!=='string'||typeof t.rule_version!=='string'||['evaluated_count','anomaly_count'].some(k=>t[k]!==null&&!count(t[k]))||!rate(t.share)||typeof t.state!=='string'))return false;
 const q=v.review_queue;if(!q||q.limit!==r.limit||q.offset!==r.offset||(partial?q.total!==null||!count(q.validated_subset_total):!count(q.total))||!Array.isArray(q.rows)||q.rows.length>q.limit||q.rows.some((c:any)=>typeof c.id!=='string'||!c.id.startsWith('qc:')||typeof c.kind!=='string'||typeof c.station_id!=='string'||typeof c.variable_code!=='string'||(r.station&&c.station_id!==r.station)||(r.item&&c.variable_code!==r.item)||!inside(c.observation_time)||!flags.has(c.flag)||typeof c.review_status!=='string')||new Set(q.rows.map((c:any)=>c.id)).size!==q.rows.length)return false;
 if(v.source!=='REGISTERED'&&(q.rows.length||q.total!==0))return false;
 const samples=v.archive_samples;if(v.source==='REGISTERED'?samples!==null:!samples||!Array.isArray(samples.rows)||samples.limit!==15||!count(samples.total_matching_rows)||samples.total_matching_rows>v.total_observations||samples.rows.length>samples.limit||samples.rows.length>samples.total_matching_rows||samples.rows.some((c:any)=>c.kind!=='ARCHIVE_RAW_SAMPLE'||c.id!==`archive:${c.parquet_sha256}:${c.file_row_number}`||!hash(c.parquet_sha256)||!count(c.file_row_number)||!inside(c.observed_time_raw||c.observation_time)||(r.station&&(c.station_code||c.station_id)!==r.station)||(r.item&&(c.item_code||c.variable_code)!==r.item))||new Set(samples.rows.map((c:any)=>c.id)).size!==samples.rows.length)return false;
 if(!v.states||!v.provenance||v.provenance.production_writes!==0)return false;
 return true;
}

/** Fresh QC enters today; an explicit preserved source replays only its chosen native window. */
export function qcDailyRequest(search:URLSearchParams,context:QCContext|null):QCDailyRequest|null {
 const source=search.get('source')||(search.has('as_of_day')?'GD_OBS_ST_MONTHLY':'REGISTERED'),isArchive=source!=='REGISTERED';
 if(!context&&!isArchive)return null;
 let preset=search.get('preset')||'today',dateFrom=search.get('date_from')||undefined,dateTo=search.get('date_to')||undefined;
 if(isArchive&&!dateFrom&&!dateTo){dateFrom=(search.get('as_of_day')||'2026-07-09')+' 00:00:00';dateTo=(search.get('as_of_day')||'2026-07-09')+' '+(search.get('as_of_time')||'15:41:20');preset='custom';}
 if(isArchive&&(dateFrom||dateTo))preset='custom';
 return {source,preset,dateFrom,dateTo,station:search.get('station')||search.get('station_id')||'',item:search.get('item')||search.get('variable_code')||'',network:search.get('network')||'',sea:search.get('sea')||'',flag:search.get('flag')||'',limit:15,offset:Math.max(0,Math.min(1000,Math.floor(Number(search.get('queue_offset')||0)||0))),...(source==='REGISTERED'&&context?{clockAnchor:{day:context.today,offset:context.offset,serverNow:context.server_now}}:{})};
}
export function qcDailyQuery(r:QCDailyRequest){
 const params=new URLSearchParams({source:r.source,preset:r.preset,station_id:r.station,variable_code:r.item,network:r.network,sea:r.sea,flag:r.flag,queue_limit:String(r.limit),queue_offset:String(r.offset)});if(r.dateFrom)params.set('date_from',r.dateFrom);if(r.dateTo)params.set('date_to',r.dateTo);return params.toString();
}
export function qcDailyMetricText(value:QCDailyMetric|undefined,percentage=true){
 if(!value)return {value:'조회 중',count:'분모 조회 중'};
 if(value.state==='NO_DATA')return {value:'데이터 없음',count:'선택 시간창에 자료 없음'};
 if(value.state==='PARTIAL')return {value:'—',count:'일부 근거만 확인 · 전체 비율 미확정'};
 if(value.state==='UNVERIFIED'||value.state==='NOT_EVALUATED'||value.count===null)return {value:'—',count:value.state==='NOT_EVALUATED'?'QC 분석 미실행':value.state==='SOURCE_QC_UNINTERPRETED'?'원문 QC 의미 미해석':'판정 근거 확인 필요'};
 return {value:percentage?qcPercent(value.rate):qcNumber(value.count),count:percentage?qcNumber(value.count)+' / '+qcNumber(value.denominator)+'건':value.count===0?'해당 기록 없음':qcNumber(value.count)+'건'};
}

export type QCDetailPoint={observation_time:string;value:number|null;value_raw:unknown;unit:string|null;received_time:string|null;delay_minutes:number|null;delay_flag:string;is_late:boolean|null;is_gap:false;actual_value:true;flag:string|null;late_history:any[];station_id?:string;station_code?:string;variable_code?:string;item_code?:string;observation_id?:string;source_row_locator?:string;source_sha256:string;parquet_sha256:string;available_at:string|null;[key:string]:any};
export type QCCapability={action:string;enabled:boolean;endpoint:string;method:string;body_template:Record<string,any>;role_requirement:string;reason:string|null;definitive_qc:boolean;source_approval_granted:boolean};
export type QCCandidateDetail={schema_version:'qc-candidate-review-1';kind:'REGISTERED_QC_CANDIDATE'|'ARCHIVE_RAW_SAMPLE';id:string;source:string;snapshot:string|null;window:QCDailyWindow;scope:{station:string;item:string;candidate_scope:Record<string,any>};observation:QCDetailPoint;
 surrounding_timeseries:{rows:QCDetailPoint[];gaps:{observation_time:string;value:null;is_gap:true;actual_value:false;reason:string}[];window_start:string;window_end:string;truncated:boolean;cadence_status:string;cadence_seconds:number|null;interpolation:false;received_time_replaced:false;gap_markers_truncated?:boolean};
 rule_results:{rows:any[];status?:string;reason?:string;excluded_counts?:Record<string,number>};ai:{status:'AVAILABLE'|'NOT_EXECUTED'|'NO_MODEL'|'UNVERIFIED';results:any[];inference_executed:false;reason?:string};equipment_epoch:Record<string,any>;evidence:Record<string,any>;review_history:any[];workflow:Record<string,any>;capabilities:QCCapability[];flag_catalog:{flags:{code:string;meaning:string;label:string}[];source_qc:{interpreted:false};[key:string]:any};display_catalog?:QCFlag[];provenance:Record<string,any>;result_sha256:string;
};
const finiteOrNull=(v:unknown)=>v===null||typeof v==='number'&&Number.isFinite(v);
const pointStation=(p:QCDetailPoint)=>p.station_id??p.station_code;
const pointItem=(p:QCDetailPoint)=>p.variable_code??p.item_code;
const depthIdentity=(p:QCDetailPoint)=>JSON.stringify(p.depth??[p.depth_step??null,p.depth_from??null,p.depth_to??null]);
export function qcDetailQuery(overview:QCDailyOverview,request:QCDailyRequest){
 const w=overview.window,params=new URLSearchParams({source:w.source,preset:w.preset,date_from:w.start,date_to:w.end,as_of:w.as_of,clock_basis:w.clock_basis,granularity:w.granularity,mode:w.mode,window_id:w.window_id,station:request.station,item:request.item,half_window_minutes:'120'});
 if(w.offset!==null)params.set('offset',w.offset);if(w.mode==='ARCHIVE'&&overview.snapshot)params.set('snapshot',overview.snapshot);return params.toString();
}
/** A detail is tied to the exact overview clock and source; its surrounding context may begin earlier. */
export function validQCCandidateDetail(v:any,id:string,overview:QCDailyOverview,request:QCDailyRequest):v is QCCandidateDetail {
 if(!v||v.schema_version!=='qc-candidate-review-1'||v.id!==id||v.source!==overview.source||!hash(v.result_sha256)||!validQCDailyWindow(v.window,v.source)||(Object.keys(overview.window) as (keyof QCDailyWindow)[]).some(k=>v.window[k]!==overview.window[k])||v.snapshot!==(v.source==='REGISTERED'?null:overview.snapshot)||v.kind!==(id.startsWith('archive:')?'ARCHIVE_RAW_SAMPLE':'REGISTERED_QC_CANDIDATE'))return false;
 if(!v.scope||v.scope.station!==request.station||v.scope.item!==request.item||!v.scope.candidate_scope)return false;
 const flags=v.flag_catalog;if(!flags||!Array.isArray(flags.flags)||flags.source_qc?.interpreted!==false||flags.flags.some((f:any)=>typeof f.code!=='string'||typeof f.meaning!=='string'||!overview.flag_catalog.some(c=>c.code===f.code&&(c.semantic===f.meaning||c.semantic==='NOT_EVALUATED'&&f.meaning==='UNKNOWN'))))return false;
 const display=v.display_catalog||v.flag_catalog.display_catalog;if(display&&(!Array.isArray(display)||display.length!==overview.flag_catalog.length||display.some((f:any)=>!overview.flag_catalog.some(c=>c.code===f.code&&c.label===f.label&&c.color===f.color&&c.semantic===f.semantic&&c.stage===f.stage))))return false;
 const obs=v.observation,source=v.source,cutoff=qcClockCoordinate(v.window.as_of,source),start=qcClockCoordinate(v.window.start,source),end=qcClockCoordinate(v.window.end,source);
 const t=qcClockCoordinate(obs?.observation_time,source);if(t===null||cutoff===null||start===null||end===null||t<start||t>end)return false;
 const validPoint=(p:QCDetailPoint)=>{const c=qcClockCoordinate(p?.observation_time,source),received=p?.received_time===null?null:qcClockCoordinate(p?.received_time,'REGISTERED');return Boolean(p&&c!==null&&c<=cutoff&&p.actual_value===true&&p.is_gap===false&&finiteOrNull(p.value)&&pointStation(p)===pointStation(obs)&&pointItem(p)===pointItem(obs)&&['sensor_id','physical_sensor_id','sensor_episode_id','source_group','unit'].every(k=>p[k]===obs[k])&&depthIdentity(p)===depthIdentity(obs)&&hash(p.source_sha256)&&hash(p.parquet_sha256)&&(p.flag===null||overview.flag_catalog.some(f=>f.code===p.flag))&&Array.isArray(p.late_history)&&p.late_history.every(h=>received!==null&&h.received_time===p.received_time&&typeof h.delay_minutes==='number'&&h.delay_minutes===p.delay_minutes)&&(p.is_late===null||typeof p.is_late==='boolean')&&finiteOrNull(p.delay_minutes)&&(p.received_time===null?p.delay_minutes===null:source==='REGISTERED'&&received!==null&&received>=c&&received<=cutoff&&p.delay_minutes!==null&&Math.abs(p.delay_minutes-(received-c)/6e7)<.000001));};
 if(!validPoint(obs)||(request.station&&pointStation(obs)!==request.station)||(request.item&&pointItem(obs)!==request.item))return false;
 const s=v.surrounding_timeseries,a=qcClockCoordinate(s?.window_start,source),b=qcClockCoordinate(s?.window_end,source);
 if(!s||a===null||b===null||a!==t-120*6e7||b!==Math.min(t+120*6e7,cutoff)||s.interpolation!==false||s.received_time_replaced!==false||typeof s.truncated!=='boolean'||typeof s.cadence_status!=='string'||!Array.isArray(s.rows)||s.rows.length>3000||s.rows.some((p:QCDetailPoint)=>!validPoint(p)||qcClockCoordinate(p.observation_time,source)!<a||qcClockCoordinate(p.observation_time,source)!>b)||!Array.isArray(s.gaps)||s.gaps.length>3000||s.gaps.some((g:any)=>g.value!==null||g.is_gap!==true||g.actual_value!==false||typeof g.reason!=='string'||qcClockCoordinate(g.observation_time,source)===null||qcClockCoordinate(g.observation_time,source)!<a||qcClockCoordinate(g.observation_time,source)!>b))return false;
 if(!v.rule_results||!Array.isArray(v.rule_results.rows)||v.rule_results.rows.some((r:any)=>!overview.flag_catalog.some(f=>f.code===r.flag)||typeof r.rule_id!=='string'||typeof r.rule_version!=='string'||qcClockCoordinate(r.observation_time,source)!==t))return false;
 const ai=v.ai;if(!ai||!['AVAILABLE','NOT_EXECUTED','NO_MODEL','UNVERIFIED'].includes(ai.status)||ai.inference_executed!==false||!Array.isArray(ai.results)||(ai.status==='AVAILABLE'?ai.results.length===0:ai.results.length!==0)||ai.results.some((r:any)=>r.stored_only!==true||r.source_qc_finalized!==false||typeof r.model!=='string'||typeof r.model_version!=='string'||!hash(r.model_sha256)||qcClockCoordinate(r.observation_time,source)!==t||['predicted_value','residual','anomaly_score','confidence','drift_score','level_shift'].some(k=>!finiteOrNull(r[k]))||qcClockCoordinate(r.available_at,'REGISTERED')===null||qcClockCoordinate(r.version_available_at,'REGISTERED')===null||qcClockCoordinate(r.version_available_at,'REGISTERED')!<qcClockCoordinate(r.available_at,'REGISTERED')!||qcClockCoordinate(r.version_available_at,'REGISTERED')!>cutoff||qcClockCoordinate(r.available_at,'REGISTERED')!>cutoff||r.predicted_value!==null&&r.residual!==null&&(obs.value===null||Math.abs(r.residual-(obs.value-r.predicted_value))>1e-8)))return false;
 if(!v.equipment_epoch||!v.evidence||!['operations','inspection','rag'].every(k=>typeof v.evidence[k]?.status==='string'&&Array.isArray(v.evidence[k].rows))||!v.workflow||typeof v.workflow.status!=='string'||!Array.isArray(v.review_history)||!Array.isArray(v.capabilities)||v.capabilities.some((c:any)=>typeof c.action!=='string'||typeof c.enabled!=='boolean'||c.enabled&&(!workflowCapabilityBound(v,c)||v.kind==='ARCHIVE_RAW_SAMPLE')))return false;
 if(!v.provenance||!Array.isArray(v.provenance.mutations)||v.provenance.mutations.length||v.provenance.inference_executed!==false||v.provenance.final_qc_written!==false)return false;
 return true;
}
function workflowCapabilityBound(packet:QCCandidateDetail,c:QCCapability){
 const w=packet.workflow,b=c.body_template,suffix=c.action==='APPROVED'||c.action==='REJECTED'?'decision':c.action==='RESUME'?'resume':c.action==='CANCEL'?'cancel':null;
 const stateAllowed=suffix==='decision'?w.status==='PENDING':c.action==='RESUME'?w.status==='APPROVED':c.action==='CANCEL'&&['PENDING','APPROVED'].includes(w.status);
 return Boolean(suffix&&stateAllowed&&c.role_requirement===(suffix==='decision'?'reviewer':'operator')&&typeof w.workflow_id==='string'&&/^[a-zA-Z0-9_-]{1,128}$/.test(w.workflow_id)&&c.method==='POST'&&c.endpoint==='/api/agents/workflows/'+w.workflow_id+'/'+suffix&&c.definitive_qc===false&&c.source_approval_granted===false&&b&&Object.keys(b).every(k=>['request_key','expected_recommendation_sha256','expected_revision','comment','decision'].includes(k))&&hash(w.recommendation_sha256)&&b.expected_recommendation_sha256===w.recommendation_sha256&&count(w.revision)&&b.expected_revision===w.revision&&(suffix!=='decision'||b.decision===c.action));
}
/** Backend authority, current role and a revision/hash-bound existing workflow are all required. */
export function qcDetailActionAvailability(packet:QCCandidateDetail|null,c:QCCapability,actor:{user_id:string;role:string}|null){
 if(!packet||packet.kind==='ARCHIVE_RAW_SAMPLE')return {enabled:false,reason:'보존 원문은 승인 Workflow 대상이 아닙니다.'};
 if(!c.enabled)return {enabled:false,reason:c.reason==='OPERATOR_AUTHENTICATION_NOT_CONFIGURED'?'실제 담당 계정은 운영 단계에서 설정합니다.':c.reason||'연결된 Workflow·담당 권한·현재 상태 확인이 필요합니다.'};
 if(!workflowCapabilityBound(packet,c))return {enabled:false,reason:'Workflow 대상·revision·추천 hash가 일치하지 않습니다.'};
 if(!actor||!actor.user_id)return {enabled:false,reason:'담당 계정과 권한을 확인하세요.'};
 const allowed=c.role_requirement==='reviewer'?['reviewer','admin']:['operator','reviewer','admin'];
 if(actor.role==='operator'&&actor.user_id!==(packet.workflow.human_approval?.requested_by||packet.workflow.requested_by))return {enabled:false,reason:'작업을 요청한 담당자만 재개·취소할 수 있습니다.'};
 return allowed.includes(actor.role)?{enabled:true,reason:''}:{enabled:false,reason:'이 처리에 필요한 담당 권한이 없습니다.'};
}
/** Null values, explicit inferred gaps and duplicate clocks break segments; no values are imputed. */
export function qcDetailPlot(detail:QCCandidateDetail,spanMinutes=120){
 const source=detail.source,center=qcClockCoordinate(detail.observation.observation_time,source)!;
 const start=Math.max(qcClockCoordinate(detail.surrounding_timeseries.window_start,source)!,center-spanMinutes*6e7),end=Math.min(qcClockCoordinate(detail.surrounding_timeseries.window_end,source)!,center+spanMinutes*6e7);
 const rows=detail.surrounding_timeseries.rows.map((row,index)=>({row,index,time:qcClockCoordinate(row.observation_time,source)!})).filter(p=>p.time>=start&&p.time<=end).sort((a,b)=>a.time-b.time||a.index-b.index);
 const gaps=detail.surrounding_timeseries.gaps.map(g=>({...g,time:qcClockCoordinate(g.observation_time,source)!})).filter(g=>g.time>=start&&g.time<=end);
 const predictions=detail.ai.status==='AVAILABLE'?detail.ai.results.filter(r=>typeof r.predicted_value==='number'&&Number.isFinite(r.predicted_value)):[];
 const values=[...rows.flatMap(p=>typeof p.row.value==='number'?[p.row.value]:[]),...predictions.map(r=>r.predicted_value)],lo=Math.min(...values),hi=Math.max(...values),pad=values.length?Math.max((hi-lo)*.12,Math.abs(hi)*.015,.001):1,min=values.length?lo-pad:0,max=values.length?hi+pad:1;
 const x=(time:number)=>52+((time-start)/Math.max(1,end-start))*824,y=(value:number)=>238-(value-min)/Math.max(1e-12,max-min)*212;
 const duplicates=new Map<number,number>();for(const point of rows)duplicates.set(point.time,(duplicates.get(point.time)||0)+1);
 const seen=new Map<number,number>(),points=rows.map(p=>{const order=seen.get(p.time)||0;seen.set(p.time,order+1);return {...p,x:x(p.time),markerX:x(p.time)+(order-((duplicates.get(p.time)||1)-1)/2)*3,y:typeof p.row.value==='number'?y(p.row.value):null,duplicates:duplicates.get(p.time)||1};});
 const discrete=/WIND.*DIRECT|DIRECTION/i.test(pointItem(detail.observation)||''),segments:typeof points[]=[];let segment:typeof points=[];
 for(const p of points){const previous=segment[segment.length-1],breakLine=p.y===null||discrete||p.duplicates>1||previous?.duplicates>1||previous&&gaps.some(g=>g.time>previous.time&&g.time<p.time);if(breakLine&&segment.length){segments.push(segment);segment=[];}if(p.y!==null){segment.push(p);if(discrete||p.duplicates>1){segments.push(segment);segment=[];}}}
 if(segment.length)segments.push(segment);
 return {start,end,center,points,segments,gaps:gaps.map(g=>({...g,x:x(g.time)})),predictions:predictions.map(r=>({...r,x:x(center),y:y(r.predicted_value)})),issueX:x(center),min,max,x,y,discrete};
}
