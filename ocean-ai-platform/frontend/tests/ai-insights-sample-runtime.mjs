// Isolated HTTP fixtures exercise real application modules; no operational network.
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {aiFixture} from './ai-insights-sample-fixtures.mjs';
export {compile,frontend,json} from './qc-sample-workspace-runtime.mjs';
import {json} from './qc-sample-workspace-runtime.mjs';

export function apiFixture(){
 const f=structuredClone(aiFixture),store=f.details,receipt=f.session;
 let hook,rejectNextReview=false;
 const detail=id=>({...structuredClone(store[id]),session_revision:receipt.session_revision,generation:receipt.generation});
 const overview=()=>{
  const p=structuredClone(f.overview);p.session_revision=receipt.session_revision;p.generation=receipt.generation;p.scenarios=Object.values(store).map(d=>structuredClone(d.scenario));
  p.kpis.pending_review_count=p.scenarios.filter(s=>s.workflow_status==='PENDING').length;p.kpis.review_report_ready_count=p.scenarios.filter(s=>s.report_status==='READY').length;
  return p;
 };
 function apply(id,body){
  const d=store[id],from=d.workflow.status,to={COMMENT:from,APPROVE:'APPROVED',HOLD:'HELD',REJECT:'REJECTED',RESUME:'COMPLETED'}[body.action];
  assert.equal(body.expected_revision,d.revision);assert.equal(body.recommendation_sha256,d.recommendation_sha256);assert.ok(body.request_key);assert.ok(body.comment.trim());
  assert.ok(d.workflow.capabilities[body.action.toLowerCase()],'Blocked sample actions must never be sent');
  d.workflow.history.push({sequence:d.workflow.history.length+1,action:body.action,from_state:from,to_state:to,comment:body.comment,actor:'SAMPLE_REVIEWER_NOT_OPERATIONAL_IDENTITY',sample_clock:d.window.as_of});
  d.revision++;receipt.session_revision++;d.scenario.revision=d.workflow.revision=d.revision;
  d.scenario.workflow_status=d.workflow.status=to;d.scenario.report_status=d.workflow.report_status=to==='COMPLETED'?'READY':'BLOCKED';
  d.workflow.blocked=to!=='COMPLETED';d.workflow.downstream_executed=to==='COMPLETED';
  d.workflow.capabilities={comment:true,approve:['PENDING','HELD'].includes(to),hold:['PENDING','APPROVED'].includes(to),reject:['PENDING','HELD','APPROVED'].includes(to),resume:to==='APPROVED'};
  return {...detail(id),schema_version:'ai-sample-review-1',idempotent_replay:false};
 }
 function report(id){
  const d=detail(id);assert.equal(d.workflow.status,'COMPLETED');
  const r=structuredClone(f.report);Object.assign(r,{session_id:receipt.session_id,session_revision:receipt.session_revision,generation:receipt.generation,scenario_id:id,revision:d.revision,recommendation_sha256:d.recommendation_sha256,filename:'ai-sample-'+id+'.md'});
  Object.assign(r.report,{scenario:d.scenario,workflow:d.workflow});
  r.markdown_sha256=createHash('sha256').update(r.markdown,'utf8').digest('hex');
  return r;
 }
 async function base(url,init={}){
  assert.ok(url.startsWith('/api/ai-insights-sample/'),'Only the isolated AI namespace may be called');
  assert.equal(init.credentials,'omit');assert.equal(new Headers(init.headers).has('Authorization'),false);assert.equal(new Headers(init.headers).has('Cookie'),false);assert.equal(init.redirect,'error');assert.equal(new URL(url,'http://localhost').searchParams.toString(),'');
  const path=url.slice('/api/ai-insights-sample'.length);
  if(path==='/context')return json(f.context);
  if(path==='/sessions')return json(receipt);
  if(path.endsWith('/overview'))return json(overview());
  if(path.endsWith('/reset')){
   const body=JSON.parse(init.body);assert.equal(body.expected_session_revision,receipt.session_revision);
   receipt.session_revision++;receipt.generation++;
   for(const id of Object.keys(store)){
    const d=structuredClone(aiFixture.details[id]);store[id]=d;d.generation=receipt.generation;
    d.recommendation_sha256=d.scenario.recommendation_sha256=d.workflow.recommendation_sha256=({'normal':'a','high-temp-neighbor':'b','spike':'c','salinity-drift':'d'}[id]).repeat(64);
   }
   return json(receipt);
  }
  const match=/\/scenarios\/(normal|high-temp-neighbor|spike|salinity-drift)(?:\/(review|report))?$/.exec(path);
  assert.ok(match,'Only an exact bounded synthetic scenario may be requested');
  if(match[2]==='report')return json(report(match[1]));
  if(match[2]==='review'){
   if(rejectNextReview){rejectNextReview=false;return json({detail:{code:'AI_SAMPLE_STALE_REVISION'}},409);}
   return json(apply(match[1],JSON.parse(init.body)));
  }
  return json(detail(match[1]));
 }
 return {respond:(url,init)=>hook?hook(url,init,base):base(url,init),setHook:fn=>hook=fn,detail,overview,report,apply,receipt,setRejectNextReview:()=>rejectNextReview=true};
}
