import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import ts from 'typescript';
import {context,request,overview,detail,emptyPreset} from './qc-daily-fixtures.mjs';
const {outputText}=ts.transpileModule(readFileSync(new URL('../src/data/qcWorkspace.ts',import.meta.url),'utf8'),{compilerOptions:{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022}});
const h=await import(`data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`);
test('actual observation and AI values preserve six decimal places independently of KPI rounding',()=>{
 for(const [value,expected] of [[21.38,'21.38'],[21.123456,'21.123456'],[.256544000000001,'0.256544'],[-21.38,'-21.38'],[0,'0'],[-0,'0'],[null,'—'],[' 21.38','—'],[Infinity,'—'],[NaN,'—']])assert.equal(h.qcValueNumber(value),expected);
 assert.notEqual(h.qcValueNumber(.0000001),'0');assert.equal(h.qcNumber(21.38),'21.4');assert.equal(h.qcPercent(21.38),'21.4%');
});
test('fresh daily QC uses the backend today, carrying no client-computed date or offset',()=>{
 const ctx=context();assert.equal(h.validQCContext(ctx),true);const q=h.qcDailyRequest(new URLSearchParams(),ctx);assert.equal(q.source,'REGISTERED');assert.equal(q.preset,'today');assert.equal(q.dateFrom,undefined);assert.equal(q.dateTo,undefined);assert.equal(new URLSearchParams(h.qcDailyQuery(q)).has('as_of_day'),false);assert.equal(h.qcDailyRequest(new URLSearchParams(),null),null);
 for(const preset of ['yesterday','7d','30d'])assert.equal(h.qcDailyRequest(new URLSearchParams({preset}),ctx).preset,preset);
});
test('legacy July 9 is one native day; explicit custom dates keep their intended window',()=>{
 const q=h.qcDailyRequest(new URLSearchParams('source=GD_OBS_ST_MONTHLY&from=2026-07&to=2026-07&as_of_day=2026-07-09&as_of_time=15%3A41%3A20'),context());assert.equal(q.dateFrom,'2026-07-09 00:00:00');assert.equal(q.dateTo,'2026-07-09 15:41:20');assert.equal(q.preset,'custom');
 const defaultSource=h.qcDailyRequest(new URLSearchParams('as_of_day=2026-07-09&as_of_time=15%3A41%3A20'),context());assert.equal(defaultSource.source,'GD_OBS_ST_MONTHLY');assert.equal(defaultSource.dateFrom,'2026-07-09 00:00:00');assert.equal(defaultSource.dateTo,'2026-07-09 15:41:20');
 const custom=h.qcDailyRequest(new URLSearchParams('source=GD_OBS_ST_MONTHLY&date_from=2026-07-01T00%3A00%3A00&date_to=2026-07-09T15%3A41%3A20'),context());assert.equal(custom.dateFrom,'2026-07-01T00:00:00');
});
test('explicit operating offsets compare instants; archives forbid guessed offsets and invalid calendars',()=>{
 assert.equal(h.qcClockCoordinate('2026-10-09T15:40:00+05:30','REGISTERED'),h.qcClockCoordinate('2026-10-09T10:10:00Z','REGISTERED'));
 for(const time of ['2026-02-31T00:00:00+05:30','2026-10-09T15:40:00','2026-10-09T15:40:00+25:00'])assert.equal(h.qcClockCoordinate(time,'REGISTERED'),null);
 assert.equal(h.qcClockCoordinate('2026-07-09 15:41:20+09:00','GD_OBS_ST_MONTHLY'),null);assert.equal(h.qcClockCoordinate('2026-07-09 15:41:20.000001','GD_OBS_ST_MONTHLY')-h.qcClockCoordinate('2026-07-09 15:41:20','GD_OBS_ST_MONTHLY'),1);
});
test('presets enforce server day anchors, hour/day aggregation, archive custom and a bounded 31-day window',()=>{
 const ctx=context();for(const preset of ['today','yesterday','7d','30d']){const r=h.qcDailyRequest(new URLSearchParams({preset}),ctx),v=emptyPreset(preset);assert.equal(h.validQCDailyOverview(v,r),true,preset);v.window.granularity=v.window.granularity==='hour'?'day':'hour';assert.equal(h.validQCDailyOverview(v,r),false,preset+' wrong aggregation');}
 const r=h.qcDailyRequest(new URLSearchParams(),ctx);for(const day of ['2026-10-08','2026-10-10']){const v=overview(true);for(const key of ['start','end','as_of'])v.window[key]=v.window[key].replace('2026-10-09',day);assert.equal(h.validQCDailyOverview(v,r),false,'wrong server today '+day);}
 const v=overview(true);v.window.start='2026-09-01T00:00:00+05:30';assert.equal(h.validQCDailyWindow(v.window,'REGISTERED'),false);v.window.source='GD_OBS_ST_MONTHLY';v.window.mode='ARCHIVE';assert.equal(h.validQCDailyWindow(v.window,'GD_OBS_ST_MONTHLY'),false);assert.equal(h.qcDailyQuery(r).includes('clockAnchor'),false);
});
test('all daily widgets use one exact source/window/scope and reconcile denominators',()=>{
 assert.equal(h.validQCDailyOverview(overview(),request()),true);assert.equal(h.validQCDailyOverview(overview(true),request()),true);
 for(const mutate of [v=>v.scope.flag='UNKNOWN',v=>v.source='SIMULATION',v=>v.window.source='SIMULATION',v=>v.flag_distribution[0].denominator=3,v=>v.flag_distribution[2].rate=99,v=>v.flag_distribution[2].label='무조건 정상',v=>v.station_variable_matrix[0].rates.bad=99,v=>v.quality_trend[0].end='2026-10-10T00:00:00+05:30',v=>v.review_queue.rows[0].observation_time='2026-10-09T16:00:00.000001+05:30',v=>v.review_queue.rows[0].variable_code='SALINITY']){const v=overview();mutate(v);const r=request();if(v.review_queue.rows[0].variable_code==='SALINITY'){r.item='WATER_TEMP';v.scope.variable_code='WATER_TEMP';}assert.equal(h.validQCDailyOverview(v,r),false);}
});
test('partial authority never displays a full-scope rate or total candidate count',()=>{
 const v=overview();v.states.overall='PARTIAL';for(const row of v.flag_distribution)row.rate=null;for(const row of [...v.quality_trend,...v.station_variable_matrix])for(const k of Object.keys(row.rates))row.rates[k]=null;for(const m of Object.values(v.summary))if(m.stage==='RULE_QC'){m.count=null;m.rate=null;m.state='PARTIAL';}v.review_queue.total=null;v.review_queue.validated_subset_total=1;v.review_queue.state='PARTIAL';assert.equal(h.validQCDailyOverview(v,request()),true);assert.equal(h.qcDailyMetricText(v.summary.bad).value,'—');v.flag_distribution[2].rate=100;assert.equal(h.validQCDailyOverview(v,request()),false);
});
test('detail query copies the complete immutable window rather than re-resolving today',()=>{
 const v=overview(),q=new URLSearchParams(h.qcDetailQuery(v,request()));for(const [key,from] of Object.entries({date_from:'start',date_to:'end',as_of:'as_of',window_id:'window_id',clock_basis:'clock_basis',offset:'offset',granularity:'granularity',mode:'mode'}))assert.equal(q.get(key),v.window[from]);assert.equal(q.has('network'),false);assert.equal(q.has('snapshot'),false);
});
test('stored AI detail accepts genuine result only and rejects stale clocks, invented AI and authority shifts',()=>{
 assert.equal(h.validQCCandidateDetail(detail(), 'qc:TEST-ROW',overview(),request()),true);assert.equal(h.validQCCandidateDetail(detail(true), 'qc:TEST-ROW',overview(),request()),true);
 for(const mutate of [v=>v.window.window_id='b'.repeat(64),v=>v.scope.station='another',v=>v.observation.value=NaN,v=>v.surrounding_timeseries.interpolation=true,v=>v.surrounding_timeseries.rows[0].observation_time='2026-10-09T16:00:00.000001+05:30',v=>v.ai.results[0].stored_only=false,v=>v.ai.results[0].residual=999,v=>v.ai.results[0].available_at='2026-10-09T16:01:00+05:30',v=>v.provenance.final_qc_written=true,v=>v.observation.received_time='2026-10-09T15:39:00+05:30',v=>v.surrounding_timeseries.rows[0].depth.step=1]){const v=detail(true);mutate(v);assert.equal(h.validQCCandidateDetail(v,'qc:TEST-ROW',overview(),request()),false);}
});
test('real plot preserves zero, negative, missing, duplicate and late values without interpolation',()=>{
 const v=detail(true),p=h.qcDetailPlot(v);assert.equal(p.points.length,5);assert.equal(p.gaps.length,1);assert.equal(p.predictions[0].predicted_value,20);assert.equal(p.points.find(x=>x.row.value===0).row.value_raw,'0');assert.equal(p.points.find(x=>x.row.value===-1).row.value_raw,'-1');assert.equal(p.points.filter(x=>x.duplicates===2).length,2);assert.ok(p.segments.every(s=>s.length===1));assert.equal(p.points.find(x=>x.row.is_late).row.value,21);const none=detail();assert.equal(h.qcDetailPlot(none).predictions.length,0);
 for(const row of v.surrounding_timeseries.rows)row.variable_code='WIND_DIRECT';v.observation.variable_code='WIND_DIRECT';const wind=h.qcDetailPlot(v);assert.equal(wind.discrete,true);assert.ok(wind.segments.every(s=>s.length===1));
});
test('existing workflow actions require exact endpoint/hash/revision and current reviewer role',()=>{
 const v=detail(false,true),c=v.capabilities[0];assert.equal(h.qcDetailActionAvailability(v,c,{user_id:'reviewer-test',role:'reviewer'}).enabled,true);assert.equal(h.qcDetailActionAvailability(v,c,null).enabled,false);assert.equal(h.qcDetailActionAvailability(v,c,{user_id:'operator-test',role:'operator'}).enabled,false);
 for(const altered of [{endpoint:'https://example.test/exfiltrate'},{body_template:{...c.body_template,expected_revision:2}},{body_template:{...c.body_template,expected_recommendation_sha256:'b'.repeat(64)}},{body_template:{...c.body_template,raw_value:123}},{definitive_qc:true}])assert.equal(h.qcDetailActionAvailability(v,{...c,...altered},{user_id:'test',role:'reviewer'}).enabled,false);
 const unconfigured=detail();assert.match(h.qcDetailActionAvailability(unconfigured,unconfigured.capabilities[0],null).reason,/운영 단계/);assert.equal(h.qcDailyMetricText(overview(true).summary.normal).value,'데이터 없음');assert.equal(h.qcDailyMetricText({count:0,rate:0,denominator:1,state:'RULE_QC',stage:'RULE_QC'}).value,'0%');
 const resume={...c,action:'RESUME',endpoint:'/api/agents/workflows/TEST-WORKFLOW/resume',role_requirement:'operator',body_template:{request_key:null,comment:'',expected_revision:3,expected_recommendation_sha256:'a'.repeat(64)}};v.workflow.status='APPROVED';v.workflow.human_approval={requested_by:'owner'};assert.equal(h.qcDetailActionAvailability(v,resume,{user_id:'other',role:'operator'}).enabled,false);assert.equal(h.qcDetailActionAvailability(v,resume,{user_id:'owner',role:'operator'}).enabled,true);assert.equal(h.qcDetailActionAvailability(v,resume,{user_id:'reviewer',role:'reviewer'}).enabled,true);v.workflow.status='COMPLETED';assert.equal(h.qcDetailActionAvailability(v,resume,{user_id:'owner',role:'operator'}).enabled,false);
});
