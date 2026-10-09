import test from 'node:test';
import assert from 'node:assert/strict';
import {resolve} from 'node:path';
import {compile,frontend,json} from './qc-sample-workspace-runtime.mjs';
import {aiFixture as f} from './ai-insights-sample-fixtures.mjs';
const m=await import(compile(resolve(frontend,'data/aiInsightsSample.ts')));

test('Actual sanitized backend context/session/overview and four full TEST datasets satisfy the AI sample contract',()=>{
 assert.equal(m.validAIContext(f.context),true);assert.equal(m.validAISession(f.session),true);assert.equal(m.validAIOverview(f.overview,f.session,f.context),true);
 for(const id of m.aiScenarioIds)assert.equal(m.validAIDetail(f.details[id],f.overview,id),true,id);
 assert.equal(m.validAIReview(f.reviewApproved,f.overview,'spike',2),true);
 assert.equal(m.validAIOverview(f.overviewReady,f.session,f.context),true);
 assert.equal(m.validAIReport(f.report,f.overviewReady,'spike'),true);
});

test('Forecast predictions bind exact target, origin, three past feature IDs and metric rows rather than shifted series',()=>{
 const base=f.details.spike;
 for(const corrupt of [d=>d.forecast.paired_test_predictions[10].target_id=d.series[20].row_id,d=>d.forecast.paired_test_predictions[10].origin_id=d.series[14].row_id,d=>d.forecast.paired_test_predictions[10].feature_row_ids[0]=d.series[14].row_id,d=>d.forecast.paired_test_predictions[10].target+=1,d=>d.series[13].prediction+=1,d=>d.forecast.test_metrics.RIDGE.count--,d=>d.forecast.test_metrics.RIDGE.mae+=1000,d=>d.forecast.validation_metrics.PERSISTENCE.rmse+=1000]){
  const d=structuredClone(base);corrupt(d);assert.equal(m.validAIDetail(d,f.overview,'spike'),false);
 }
});

test('Sample authority, units, source clock, future rows and exact generation cannot be replaced by operational evidence',()=>{
 for(const corrupt of [d=>d.source='REGISTERED',d=>d.approved=true,d=>d.operational_model_count=1,d=>d.model_registry_writes=1,d=>d.generation++,d=>d.session_id='qc-sample-session-other',d=>d.series.at(-1).timestamp='2026-07-09T16:00:00+09:00',d=>d.series[20].modes[0].available_at='not-a-clock',d=>d.series[20].modes[0].available_at=null,d=>d.series[20].modes[0].available_at='2026-07-09T16:00:00+09:00',d=>d.window.clock_basis='SERVER_LOCAL_OFFSET',d=>d.scenario.confidence_probability=.99,d=>d.scenario.unit='psu']){
  const d=structuredClone(f.details.spike);corrupt(d);assert.equal(m.validAIDetail(d,f.overview,'spike'),false);
 }
 const wrong=structuredClone(f.overview);wrong.scenarios.find(s=>s.scenario_id==='salinity-drift').unit='degree_C';wrong.stations.find(s=>s.scenario_id==='salinity-drift').unit='degree_C';assert.equal(m.validAIOverview(wrong,f.session,f.context),false,'scenario unit must match the context dataset contract');
});

test('Displayed calibration score and confusion rates must be derived from the same mode results and injected truth',()=>{
 for(const corrupt of [d=>d.anomaly_evaluation.precision=.5,d=>d.anomaly_evaluation.recall=.5,d=>d.anomaly_evaluation.false_positive_rate=.5,d=>d.anomaly_evaluation.false_negative_rate=.5,d=>d.series[20].anomaly_score+=1000,d=>d.series[20].assessment=d.series[20].assessment==='ANOMALY'?'NORMAL':'ANOMALY']){
  const d=structuredClone(f.details.spike);corrupt(d);assert.equal(m.validAIDetail(d,f.overview,'spike'),false);
 }
});

test('Plot coordinates preserve exact per-case units, forecast warmup nulls and independent reference without pooling salinity with temperature',()=>{
 for(const id of m.aiScenarioIds){const d=f.details[id],plot=m.aiSeriesPlot(d.series);assert.equal(plot.points.length,280);assert.equal(plot.segments('prediction').flat().length,277);assert.equal(plot.segments('value').flat().length,280);assert.equal(plot.segments('reference_value').flat().length,280);assert.equal(plot.points[0].row.value,d.series[0].value);assert.equal(plot.points.at(-1).row.value,d.series.at(-1).value);assert.ok(plot.points.every(p=>Number.isFinite(plot.x(p.time))&&Number.isFinite(plot.y(p.row.value))));assert.equal(plot.x(plot.points[0].time),55);assert.equal(plot.x(plot.points.at(-1).time),705);const daily=m.aiDailyTrend(d.series);assert.equal(daily.reduce((n,b)=>n+b.total,0),280);assert.equal(daily.reduce((n,b)=>n+b.evaluated,0),d.anomaly_evaluation.evaluated_count);assert.equal(daily.reduce((n,b)=>n+b.anomaly,0),d.series.filter(r=>r.assessment==='ANOMALY').length);}
});

test('Sample reports are bound to ready case, session generation, revision, hash and explicit non-operational delivery',()=>{
 assert.equal(m.validAIReport(f.report,f.overview,'spike'),false);
 for(const corrupt of [r=>r.generation++,r=>r.session_revision++,r=>r.revision--,r=>r.markdown_hash_kind='CANONICAL_JSON',r=>r.recommendation_sha256='0'.repeat(64),r=>r.scenario_id='salinity-drift',r=>r.filename='actual-ocean-report.md',r=>r.delivered=true,r=>r.report.recipients=['real-recipient'],r=>r.report.scenario.revision--,r=>r.report.approved=true]){const r=structuredClone(f.report);corrupt(r);assert.equal(m.validAIReport(r,f.overviewReady,'spike'),false);}
});

test('Report Markdown verification hashes exact UTF8 bytes, including Korean text, and rejects content or digest policy changes',async()=>{
 assert.equal(await m.verifyAIReportMarkdown(f.report),true);const changed=structuredClone(f.report);changed.markdown+='\n변조';assert.equal(await m.verifyAIReportMarkdown(changed),false);assert.equal(await m.verifyAIReportMarkdown({...f.report,markdown_hash_kind:'CANONICAL_JSON'}),false);assert.equal(await m.verifyAIReportMarkdown({...f.report,markdown_sha256:'0'.repeat(64)}),false);
});

test('AI transport only accepts its namespace token, omits Cookie credentials and never forwards actual operator Authorization',async()=>{
 const calls=[],old=globalThis.fetch;globalThis.fetch=async(url,init)=>{calls.push({url,init});return json({});};
 try{await m.aiSampleRequest('/context');await m.aiSampleRequest('/sessions',f.context.bootstrap_token,{request_key:'isolated-create'});await m.aiSampleRequest(m.aiSamplePath(f.session.session_id),f.session.session_token);await m.aiSampleRequest(m.aiSamplePath(f.session.session_id,'spike','review'),f.session.session_token,{action:'COMMENT'});
  assert.equal(calls.length,4);for(const c of calls){assert.ok(c.url.startsWith('/api/ai-insights-sample/'));assert.equal(c.init.credentials,'omit');assert.equal(c.init.redirect,'error');assert.equal(c.init.cache,'no-store');assert.equal(new Headers(c.init.headers).has('Authorization'),false);}
  for(const [path,token,body] of [['/api/agents/workflows/real/decision',f.session.session_token,{}],['/sessions/'+f.session.session_id+'/overview?source=REGISTERED',f.session.session_token],['/context',f.session.session_token],['/sessions',f.session.session_token,{}],[m.aiSamplePath(f.session.session_id),'qc-sample-token-foreign'],[m.aiSamplePath(f.session.session_id),'actual-operator-token'],[m.aiSamplePath(f.session.session_id),f.context.bootstrap_token],[m.aiSamplePath(f.session.session_id,'spike','review'),f.session.session_token]])await assert.rejects(m.aiSampleRequest(path,token,body));
  assert.equal(calls.length,4);
 }finally{globalThis.fetch=old;}
});
