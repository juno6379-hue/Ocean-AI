// The real API client and React components run against isolated HTTP fixtures only.
import assert from 'node:assert/strict';
import {readFileSync,existsSync} from 'node:fs';
import {dirname,resolve} from 'node:path';
import ts from 'typescript';
import {dataURL,frontend} from './qc-sample-runtime.mjs';
import {sampleFixture} from './qc-sample-fixtures.mjs';
import {context as operatingContext,overview as operatingOverview} from './qc-daily-fixtures.mjs';
export {frontend};

const cache=new Map();
export function compile(path){
 if(cache.has(path))return cache.get(path);
 let source=readFileSync(path,'utf8');
 // Vite's build-time environment is the only substituted application expression.
 // apiFetch/setOperatorToken/clearOperatorToken remain the actual implementation.
 if(path.endsWith('client.ts'))source=source.replace('import.meta.env.VITE_API_BASE_URL','undefined');
 let output=ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2023,jsx:ts.JsxEmit.ReactJSX}}).outputText;
 const parsed=ts.createSourceFile(path,output,ts.ScriptTarget.ES2023,true,ts.ScriptKind.JS);
 for(const statement of [...parsed.statements].reverse())if(ts.isImportDeclaration(statement)){
  const specifier=statement.moduleSpecifier.text;
  if(specifier.endsWith('.css')){output=output.slice(0,statement.getStart(parsed))+output.slice(statement.end);continue;}
  let url;
  if(specifier.startsWith('.')){
   const base=resolve(dirname(path),specifier),found=[base,base+'.ts',base+'.tsx',base+'.mjs'].find(existsSync);
   if(!found)throw new Error('Unresolved workspace fixture import '+base);
   url=compile(found);
  }else url=import.meta.resolve(specifier);
  output=output.slice(0,statement.moduleSpecifier.getStart(parsed))+JSON.stringify(url)+output.slice(statement.moduleSpecifier.end);
 }
 const url=dataURL(output);cache.set(path,url);return url;
}

export const json=(value,status=200)=>new Response(JSON.stringify(value),{status,headers:{'Content-Type':'application/json'}});
export function apiFixture(){
 const f=structuredClone(sampleFixture),store=f.details,receipt=f.session;
 let hook;
 const detail=scenario=>{const value=structuredClone(store[scenario]);value.session_revision=receipt.session_revision;return value;};
 const sampleOverview=()=>{
  const value=structuredClone(f.overview);value.session_revision=receipt.session_revision;value.generation=receipt.generation;
  value.cases=Object.values(store).map(d=>structuredClone(d.case));value.review_queue={rows:structuredClone(value.cases),total:4};
  for(const [metric,state] of [['pending','PENDING'],['completed','COMPLETED']]){const count=value.cases.filter(c=>c.review_status===state).length;value.summary[metric].count=count;value.summary[metric].rate=count*25;}
  return value;
 };
 const apply=(scenario,action,comment)=>{
  const d=store[scenario],from=d.workflow.status,to={COMMENT:from,HOLD:'HELD',REJECT:'REJECTED',APPROVE:'APPROVED',RESUME:'COMPLETED'}[action];
  assert.ok(to,'Only sample review transitions are available');
  const add=(action,from_state,to_state,actor,comment)=>d.workflow.history.push({sequence:d.workflow.history.length+1,action,from_state,to_state,actor,comment,sample_clock:d.window.as_of});
  if(action==='RESUME'){add('RESUME',from,'RESUMING','SAMPLE_REVIEWER',comment);add('COMPLETE_SAMPLE_DRAFT','RESUMING','COMPLETED','SAMPLE_ENGINE','샘플 초안만 실행');}
  else add(action,from,to,'SAMPLE_REVIEWER',comment);
  d.case.review_status=d.workflow.status=to;d.workflow.blocked=to!=='COMPLETED';d.workflow.downstream_executed=to==='COMPLETED';
  d.case.revision=d.workflow.revision=++d.revision;receipt.session_revision++;
  d.workflow.capabilities={comment:true,approve:['PENDING','HELD'].includes(to),hold:['PENDING','APPROVED'].includes(to),reject:['PENDING','HELD','APPROVED'].includes(to),resume:to==='APPROVED'};
  return detail(scenario);
 };
 function operational(url){
  const parsed=new URL(url,'http://localhost');
  if(parsed.pathname==='/api/qc/context')return json(operatingContext());
  assert.equal(parsed.pathname,'/api/qc/overview','No operational writes or workflow requests are expected');
  const q=parsed.searchParams,source=q.get('source')||'REGISTERED',preset=q.get('preset')||'today',p=operatingOverview(true);
  p.source=source;p.window.source=source;p.scope={station_id:q.get('station_id')||'',variable_code:q.get('variable_code')||'',network:q.get('network')||'',sea:q.get('sea')||'',flag:q.get('flag')||''};
  p.review_queue.limit=Number(q.get('queue_limit')||15);p.review_queue.offset=Number(q.get('queue_offset')||0);
  if(source!=='REGISTERED'){
   p.window={...p.window,mode:'ARCHIVE',preset:'custom',start:q.get('date_from')||'2026-07-09 00:00:00',end:q.get('date_to')||'2026-07-09 15:41:20',clock_basis:'UNAPPROVED_NATIVE_SOURCE_CLOCK',offset:null};
   p.snapshot='isolated-archive';p.archive_samples={rows:[],total_matching_rows:0,limit:15,state:'NO_DATA'};
  }else if(preset==='yesterday'){
   p.window.preset='yesterday';p.window.start='2026-10-08T00:00:00+05:30';p.window.end='2026-10-08T23:59:59.999999+05:30';
  }
  p.window.as_of=p.window.end;
  const t=p.quality_trend[0];t.bucket=t.start=p.window.start;t.end=p.window.end;
  return json(p);
 }
 async function base(url,init={}){
  if(!url.startsWith('/api/qc-sample/')){
   assert.equal(init.method||'GET','GET','Sample integration must never submit operational writes');
   return operational(url);
  }
  assert.equal(init.credentials,'omit');assert.equal(new Headers(init.headers).has('Authorization'),false);
  assert.equal(init.redirect,'error');assert.equal(new URL(url,'http://localhost').searchParams.toString(),'');
  const path=url.slice('/api/qc-sample'.length);
  if(path==='/context')return json(f.context);
  if(path==='/sessions')return json(receipt);
  if(path.endsWith('/overview'))return json(sampleOverview());
  if(path.endsWith('/reset')){
   const body=JSON.parse(init.body);assert.equal(body.expected_session_revision,receipt.session_revision);
   receipt.session_revision++;receipt.generation++;
   for(const scenario of Object.keys(store)){
    const original=structuredClone(sampleFixture.details[scenario]);store[scenario]=original;original.generation=receipt.generation;
    original.case.case_id='sample-'+scenario+'-g'+receipt.generation;
    original.recommendation_sha256=original.case.recommendation_sha256=original.workflow.recommendation_sha256={normal:'b',late:'c',missing:'d',spike:'e'}[scenario].repeat(64);
   }
   return json(receipt);
  }
  const match=/\/cases\/sample-(normal|late|missing|spike)-g\d+(\/review)?$/.exec(path);
  assert.ok(match,'Only bounded sample case endpoints are allowed');
  if(match[2]){
   const body=JSON.parse(init.body),d=store[match[1]];
   assert.equal(body.expected_revision,d.revision);assert.equal(body.recommendation_sha256,d.recommendation_sha256);
   assert.ok(body.request_key);assert.ok(body.comment.trim());return json(apply(match[1],body.action,body.comment));
  }
  return json(detail(match[1]));
 }
 return {respond:(url,init)=>hook?hook(url,init,base):base(url,init),setHook:fn=>hook=fn,detail,sampleOverview,apply,receipt};
}
