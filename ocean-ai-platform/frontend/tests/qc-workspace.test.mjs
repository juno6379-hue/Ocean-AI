import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import ts from 'typescript';
const {outputText}=ts.transpileModule(readFileSync(new URL('../src/data/qcWorkspace.ts',import.meta.url),'utf8'),{compilerOptions:{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022}});
const {validQCWorkspace,qcLiteralLabel,qcTrendRows,qcCaseRows,qcPage,nextQCHeatmapCell,qcActionAvailability,qcLiteralQuery,qcPeriodQuery,qcPercent}=await import(`data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`);
const hash='a'.repeat(64),scope={source:'GD_OBS_ST_MONTHLY',from:'2026-07',to:'2026-07',day:'2026-07-09',time:'15:41:20',station:'',item:'',network:'',sea:'',qcField:'',qcLiteral:null,qcNull:false,qcLiteralSet:false};
function fixture(){
 const raw=(key,value,qc,clock='2026-07-09 15:40:00')=>({case_key:key,station_code:'DT_0028',item_code:'WATER_TEMP',depth_step:null,depth_from:null,depth_to:null,observed_time_raw:clock,value_raw:value,source_qc_raw:qc,source_mq_raw:' G ',source_n1_qc_raw:'',source_sha256:hash,parquet_sha256:hash,file:'source.parquet',file_row_number:Number(key),physical_sensor_id:null,unit:null,timezone:null,classification:'UNINTERPRETED',available_at:null});
 const unavailable={count:null,rate:null,denominator:null,status:'NOT_EVALUATED'};
 return {schema_version:'qc-workspace-1',source:scope.source,snapshot:'validation-test',from_month:scope.from,to_month:scope.to,as_of_day:scope.day,as_of_time:scope.time,cutoff_native:'2026-07-09 15:41:20',result_sha256:hash,
 scope:{station:'',item:'',network:'',sea:'',qc_field:'',qc_literal:null,qc_literal_is_null:false},
 filters:{stations:[{station_code:'DT_0028',station_name:'진도',held_rows:4,network_type:'조위관측소',sea_area:'서해',classification_state:'RESOLVED'}],items:[{item_code:'WATER_TEMP',held_rows:4}],networks:[{value:'조위관측소',label:'조위관측소',count:1}],seas:[{value:'서해',label:'서해',count:1}]},
 cards:{held_rows:4,normal:{...unavailable},warning:{...unavailable},bad:{...unavailable},missing:{count:1,rate:25,denominator:4,status:'RAW_VALUE_LITERAL'},unassessed:{count:4,rate:100,denominator:4,status:'SOURCE_QC_UNINTERPRETED'},pending:{count:0,status:'GLOBAL_EMPTY'},completed:{count:0,status:'GLOBAL_EMPTY'}},
 distribution:[{field:'qc_raw',literal:'OK',count:2,denominator:4,rate:50,interpreted:false},{field:'qc_raw',literal:' G ',count:1,denominator:4,rate:25,interpreted:false},{field:'qc_raw',literal:null,count:1,denominator:4,rate:25,interpreted:false}],
 monthly:[{month:'2026-07',held_rows:4,qc_present_rows:3,qc_presence_rate:75,missing_rows:1,missing_rate:25,unassessed_rate:100,interpreted:false}],
 matrix:[{station_code:'DT_0028',station_name:'진도',item_code:'WATER_TEMP',held_rows:4,qc_present_rows:3,qc_presence_rate:75,missing_rows:1,missing_rate:25,unassessed_rate:100,state:'UNKNOWN',typed_grains:[{depth_step:null,depth_from:null,depth_to:null}]}],
 cases:{rows:[raw('1','0','OK'),raw('2','-1','OK'),raw('3',null,null),raw('4','2',' G ','2026-07-09 15:39:00')],total_matching_rows:4,limit:15,ordering:'NATIVE_CLOCK_DESC_FILE_ROW_DESC',population:'RAW_SOURCE_ROWS_NOT_ANOMALY_RESULTS'},
 rules:{catalog_version:'rules-1',catalog_count:12,registered_definition_count:2,result_count:0,items:Array.from({length:12},(_,i)=>({kind:'kind-'+i,name_ko:'규칙 '+i,status:'NOT_EVALUATED',evaluated_count:0,anomaly_count:0,not_evaluated_count:null,reasons:['SOURCE_QC_CODEBOOK_EFFECTIVE_PERIOD_UNRESOLVED']}))},
 review:{status:'NOT_EVALUATED',ai_prediction_count:0,ai_label_count:0,workflow_count:0,approved_count:0,source_fact_status:'UNRESOLVED',reasons:[]},
 capabilities:{review:false,hold:false,flag_change:false,approve:false,reason:'QC 판본과 담당 승인 대상 미연결'},global_registry:{state:'AVAILABLE',scope:'GLOBAL_REGISTERED_NOT_SELECTED_RESULTS',counts:{qc_flag_history:0,ai_label:0,agent_task_approvals:0,agent_workflow_run:0,approval_history:0,agent_workflow_transition:0}},
 provenance:{approved:false,source_qc_interpreted:false,simulated_included:false,production_writes:0},raw:{} };
}

test('QC workspace requires one exact source, native cutoff and immutable snapshot packet',()=>{
 const p=fixture();assert.equal(validQCWorkspace(p,scope),true);
 for(const [key,value] of Object.entries({source:'SIMULATION',snapshot:'',schema_version:'legacy',from_month:'2026-06',as_of_day:'2026-07-10',as_of_time:'15:41:21',cutoff_native:'2026-07-09 15:41:20.000001',result_sha256:'bad'}))assert.equal(validQCWorkspace({...p,[key]:value},scope),false,key);
 const shifted=fixture();shifted.scope.network='해양관측소';assert.equal(validQCWorkspace(shifted,scope),false);
});

test('a raw code such as OK never creates a normal/BAD rate or a simulated approval',()=>{
 for(const category of ['normal','warning','bad']){const p=fixture();p.cards[category]={count:4,rate:100,denominator:4,status:'EVALUATED'};assert.equal(validQCWorkspace(p,scope),false,category);}
 for(const changed of [{approved:true},{source_qc_interpreted:true},{simulated_included:true},{production_writes:1}]){const p=fixture();Object.assign(p.provenance,changed);assert.equal(validQCWorkspace(p,scope),false);}
 assert.equal(qcPercent(null),'—');assert.equal(qcPercent(0),'0%');
});

test('field, month and weighted station-item populations must reconcile independently',()=>{
 const original=fixture();
 for(const mutation of [p=>p.distribution[0].denominator=3,p=>p.distribution[0].count=1,p=>p.distribution[0].rate=51,p=>p.distribution.push({...p.distribution[0]}),p=>p.monthly[0].held_rows=3,p=>p.matrix[0].held_rows=3,p=>p.matrix.push({...p.matrix[0]}),p=>p.monthly[0].month='2026-08']){const p=structuredClone(original);mutation(p);assert.equal(validQCWorkspace(p,scope),false);}
});

test('latest source cases reject future microseconds, false units and duplicate identity while retaining duplicate clocks',()=>{
 assert.equal(validQCWorkspace(fixture(),scope),true);
 for(const mutation of [p=>p.cases.rows[0].observed_time_raw='2026-07-09 15:41:20.000001',p=>p.cases.rows[0].observed_time_raw='2026-07-10 00:00:00',p=>p.cases.rows[0].observed_time_raw='2026-02-31 12:00:00',p=>p.cases.rows[0].unit='℃',p=>p.cases.rows[0].source_sha256='missing',p=>p.cases.rows[1].case_key=p.cases.rows[0].case_key,p=>p.cases.population='ANOMALY_RESULTS']){const p=fixture();mutation(p);assert.equal(validQCWorkspace(p,scope),false);}
 const p=fixture();p.cases.rows[0].observed_time_raw='2026-07-09 15:41:20.000000';assert.equal(validQCWorkspace(p,scope),true);
});

test('literal legend preserves NULL, empty and padding and changes only the case filter URL',()=>{
 const initial=new URLSearchParams('source=GD_OBS_ST_MONTHLY&from=2026-07&to=2026-07&station=DT_0028&item=WATER_TEMP&as_of_day=2026-07-09&as_of_time=15%3A41%3A20&case_q=old');
 for(const value of [null,'',' G ']){
   const next=qcLiteralQuery(initial,{field:'qc_raw',literal:value});assert.equal(next.get('qc_field'),'qc_raw');
   assert.equal(next.has('qc_literal'),value!==null);assert.equal(next.get('qc_literal'),value);assert.equal(next.get('qc_literal_is_null'),value===null?'true':null);assert.equal(next.get('case_q'),null);
   for(const key of ['source','from','to','station','item','as_of_day','as_of_time'])assert.equal(next.get(key),initial.get(key));
 }
 assert.deepEqual([null,'',' G '].map(qcLiteralLabel),['NULL','빈 문자열','" G "']);
 assert.equal(qcLiteralQuery(initial,null).get('station'),'DT_0028');
});

test('QC literal filtering validates case aliases and cannot substitute a trimmed or null flag',()=>{
 const p=fixture();p.scope={...p.scope,qc_field:'qc_raw',qc_literal:' G '};p.cases.rows=p.cases.rows.filter(row=>row.source_qc_raw===' G ');p.cases.total_matching_rows=1;
 const s={...scope,qcField:'qc_raw',qcLiteral:' G ',qcLiteralSet:true};assert.equal(validQCWorkspace(p,s),true);assert.equal(p.cards.held_rows,4);
 p.cases.rows[0].source_qc_raw='G';assert.equal(validQCWorkspace(p,s),false);
 const n=fixture();n.scope={...n.scope,qc_field:'qc_raw',qc_literal_is_null:true};n.cases.rows=n.cases.rows.filter(row=>row.source_qc_raw===null);n.cases.total_matching_rows=1;assert.equal(validQCWorkspace(n,{...scope,qcField:'qc_raw',qcNull:true}),true);
});

test('empty scopes keep undefined raw rates and do not display false zero missing/good rates',()=>{
 const p=fixture();p.cards.held_rows=0;p.cards.missing={count:null,rate:null,denominator:0,status:'RAW_VALUE_LITERAL'};p.cards.unassessed={count:0,rate:null,denominator:0,status:'SOURCE_QC_UNINTERPRETED'};p.distribution=[];p.matrix=[];p.cases.rows=[];p.cases.total_matching_rows=0;p.monthly=[{month:'2026-07',held_rows:0,qc_present_rows:null,qc_presence_rate:null,missing_rows:null,missing_rate:null,unassessed_rate:null,interpreted:false}];assert.equal(validQCWorkspace(p,scope),true);
 p.cards.missing.rate=0;assert.equal(validQCWorkspace(p,scope),false);
});

test('global empty pending/completed counts need actual empty ledgers, never invented scoped zeros',()=>{
 const p=fixture();p.global_registry.counts.approval_history=1;assert.equal(validQCWorkspace(p,scope),false);
 const n=fixture();n.cards.completed={count:null,status:'UNVERIFIED_SCOPE'};n.global_registry.counts.approval_history=1;assert.equal(validQCWorkspace(n,scope),true);
 n.cards.completed.count=0;assert.equal(validQCWorkspace(n,scope),false);
});

test('monthly gaps remain null while raw value composition remains a truthful 100 percent denominator',()=>{
 const data=qcTrendRows(fixture().monthly,'2026-05','2026-07');assert.equal(data.length,3);assert.equal(data[0].missing_rate,null);assert.equal(data[0].value_present_rate,null);assert.equal(data[2].missing_rate+data[2].value_present_rate,100);assert.equal(data[2].unassessed_rate,100);
});

test('case search, ordering and pagination retain zero, negative, NULL and coincident raw rows',()=>{
 const rows=fixture().cases.rows;assert.equal(qcCaseRows(rows,'진도','clock_desc',{DT_0028:'진도'}).length,4);assert.equal(qcCaseRows(rows,'NULL').length,1);assert.equal(qcCaseRows(rows,'-1')[0].value_raw,'-1');assert.equal(qcCaseRows(rows,'0').length,4);assert.equal(qcCaseRows(rows,'','clock_asc')[0].case_key,'4');
 const micro=[...rows,{...rows[0],case_key:'5',observed_time_raw:'2026-07-09T15:40:00.000001'}];assert.equal(qcCaseRows(micro,'')[0].case_key,'5');assert.equal(qcCaseRows(micro,'').length,5);
 const page=qcPage(rows,100,2);assert.equal(page.page,2);assert.equal(page.rows.length,2);assert.deepEqual(qcPage([],9,6),{page:1,pages:1,rows:[],first:0,last:0});
});

test('heatmap focus navigation stays within visible station-item cells and supports arrows and row boundaries',()=>{
 assert.equal(nextQCHeatmapCell(0,'ArrowLeft',8,6),0);assert.equal(nextQCHeatmapCell(2,'ArrowDown',8,6),8);assert.equal(nextQCHeatmapCell(8,'ArrowUp',8,6),2);assert.equal(nextQCHeatmapCell(47,'ArrowRight',8,6),47);assert.equal(nextQCHeatmapCell(8,'Home',8,6),6);assert.equal(nextQCHeatmapCell(8,'End',8,6),11);assert.equal(nextQCHeatmapCell(2,'ArrowDown',0,0),0);
});

test('heatmap arrow focus skips absent station-item cells without moving onto a disabled cell',()=>{
 const enabled=[true,false,true,false,true,false];assert.equal(nextQCHeatmapCell(0,'ArrowRight',2,3,enabled),2);assert.equal(nextQCHeatmapCell(0,'ArrowDown',2,3,enabled),0);assert.equal(nextQCHeatmapCell(4,'Home',2,3,enabled),4);assert.equal(nextQCHeatmapCell(4,'End',2,3,enabled),4);assert.equal(nextQCHeatmapCell(2,'ArrowDown',2,3,enabled),2);
});

test('draft period applies the chosen native clock unchanged and rejects future, invalid or oversized ranges',()=>{
 const before=new URLSearchParams('source=GD_OBS_ST_MONTHLY&station=DT_0028&item=WATER_TEMP');const draft={from:'2023-01',to:'2026-07',day:'2026-07-09',time:'15:41:20'};const after=qcPeriodQuery(before,draft);assert.equal(after.get('as_of_time'),'15:41:20');assert.equal(after.get('station'),'DT_0028');assert.equal(after.get('from'),'2023-01');
 for(const change of [{from:'2022-01'},{from:'2026-08'},{to:'2026-08'},{day:'2026-02-31'},{time:'25:00:00'},{day:'2026-00-01'}])assert.equal(qcPeriodQuery(before,{...draft,...change}),null);
});

test('raw sample actions stay disabled for absent auth, wrong roles and even a forged enabled capability',()=>{
 const p=fixture();for(const action of ['hold','flag_change','approve']){assert.deepEqual(qcActionAvailability(p,null,action),{enabled:false,reason:p.capabilities.reason});p.capabilities[action]=true;assert.equal(qcActionAvailability(p,null,action).enabled,false);assert.match(qcActionAvailability(p,null,action).reason,/계정/);assert.match(qcActionAvailability(p,{user_id:'op',role:'operator'},action).reason,/권한/);assert.match(qcActionAvailability(p,{user_id:'review',role:'reviewer'},action).reason,/workflow/);}
});
