import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync,existsSync} from 'node:fs';
import {dirname,resolve} from 'node:path';
import {fileURLToPath} from 'node:url';
import ts from 'typescript';
import {Window} from 'happy-dom';
import {context,request,overview,detail,emptyPreset} from './qc-daily-fixtures.mjs';

// Real React DOM components, with isolated API fixtures only. No fixture reaches a live server.
const win=new Window({url:'http://localhost/qc'});
for(const key of ['window','document','HTMLElement','SVGElement','Element','Node','MouseEvent','KeyboardEvent','Event','CustomEvent','MutationObserver','ResizeObserver'])globalThis[key]=key==='window'?win:win[key];
Object.defineProperty(globalThis,'navigator',{value:win.navigator,configurable:true});
// Happy DOM has no layout engine. Give charts a measured test viewport without changing application code.
win.HTMLElement.prototype.getBoundingClientRect=()=>new win.DOMRect(0,0,450,220);
globalThis.ResizeObserver=class {constructor(callback){this.callback=callback;}observe(target){this.callback([{target,contentRect:target.getBoundingClientRect()}]);}unobserve(){}disconnect(){}};
globalThis.requestAnimationFrame=callback=>setTimeout(()=>callback(performance.now()),0);
globalThis.cancelAnimationFrame=handle=>clearTimeout(handle);
globalThis.IS_REACT_ACT_ENVIRONMENT=true;
const React=await import('react'),{act}=React,{createRoot}=await import('react-dom/client'),{MemoryRouter,useLocation,useNavigate}=await import('react-router-dom');
const dataURL=code=>'data:text/javascript;base64,'+Buffer.from(code).toString('base64');
const cache=new Map();
function compile(path){
 if(cache.has(path))return cache.get(path);
 if(path.endsWith('client.ts')){const url=dataURL("export const API_BASE_URL='/api';export const apiFetch=(...args)=>globalThis.fetch(...args);");cache.set(path,url);return url;}
 // The existing workflow launcher is unrelated to the detail authority fixture; its writes are not exercised here.
 if(path.endsWith('WorkflowReviewPanel.tsx')||path.endsWith('ObservationSeriesChart.tsx')){const url=dataURL('export default function ExistingTool(){return null;}');cache.set(path,url);return url;}
 const source=readFileSync(path,'utf8'),result=ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX}}).outputText;
 const parsed=ts.createSourceFile(path,result,ts.ScriptTarget.ES2022,true,ts.ScriptKind.JS);let output=result;
 for(const statement of [...parsed.statements].reverse())if(ts.isImportDeclaration(statement)){const specifier=statement.moduleSpecifier.text;if(specifier.endsWith('.css')){output=output.slice(0,statement.getStart(parsed))+output.slice(statement.end);continue;}let url;
  if(specifier.startsWith('.')){const base=resolve(dirname(path),specifier),found=[base,base+'.ts',base+'.tsx',base+'.mjs'].find(existsSync);if(!found)throw new Error('Unresolved fixture module '+base);url=compile(found);}else url=import.meta.resolve(specifier);
  output=output.slice(0,statement.moduleSpecifier.getStart(parsed))+JSON.stringify(url)+output.slice(statement.moduleSpecifier.end);
 }
 const url=dataURL(output);cache.set(path,url);return url;
}
const base=fileURLToPath(new URL('../src/components/',import.meta.url));
const Drawer=(await import(compile(resolve(base,'QCCandidateDrawer.tsx')))).default;
const Page=(await import(compile(resolve(base,'QCWorkspace.tsx')))).default;
const {QCDailyQueue}=await import(compile(resolve(base,'QCCaseReview.tsx')));
const {QCDailyDistribution,QCDailyTrend,QCDailyMatrix}=await import(compile(resolve(base,'QCWorkspaceCharts.tsx')));
let root,container,requests,route,navigateRoute;
function CaptureRoute(){route=useLocation();navigateRoute=useNavigate();return null;}
async function mount(element,respond,initial='/qc'){
 requests=[];globalThis.fetch=async(input,init={})=>{requests.push({url:String(input),init});return respond(String(input),init);};
 container=document.createElement('div');document.body.append(container);root=createRoot(container);
 await act(async()=>{root.render(React.createElement(MemoryRouter,{initialEntries:[initial]},React.createElement(CaptureRoute),element));await new Promise(r=>setTimeout(r,10));});
 await act(async()=>{await new Promise(r=>setTimeout(r,10));});
}
async function dispose(){if(root)await act(async()=>root.unmount());container?.remove();root=null;await win.happyDOM.waitUntilComplete();}
const json=(value,status=200)=>new Response(JSON.stringify(value),{status,headers:{'Content-Type':'application/json'}});
const button=text=>[...container.querySelectorAll('button')].find(b=>b.textContent.trim()===text);
const byLabel=label=>container.querySelector(`[aria-label="${label}"]`);
async function click(node){assert.ok(node,'button must exist');await act(async()=>{node.dispatchEvent(new MouseEvent('click',{bubbles:true}));await new Promise(r=>setTimeout(r,10));});}
async function input(node,value){assert.ok(node);await act(async()=>{const setter=Object.getOwnPropertyDescriptor(Object.getPrototypeOf(node),'value')?.set;setter?.call(node,value);node.dispatchEvent(new Event(node.tagName==='SELECT'?'change':'input',{bubbles:true}));node.dispatchEvent(new Event('change',{bubbles:true}));await new Promise(r=>setTimeout(r,5));});}
function changeImmediately(node,value){assert.ok(node);Object.getOwnPropertyDescriptor(Object.getPrototypeOf(node),'value').set.call(node,value);node.dispatchEvent(new Event('change',{bubbles:true}));}
async function sameTick(run){await act(async()=>{run();await new Promise(r=>setTimeout(r,10));});await act(async()=>{await new Promise(r=>setTimeout(r,10));});}
// Empty, isolated read-only scope fixtures exercise routing; no synthetic records enter a live API.
function scopeResponse(url){
 if(url.includes('/context'))return json(context());const q=new URL(url,'http://localhost').searchParams,source=q.get('source')||'REGISTERED',preset=q.get('preset')||'today',p=source==='REGISTERED'?emptyPreset(preset==='custom'?'today':preset):overview(true);
 p.source=source;p.window.source=source;p.scope={station_id:q.get('station_id')||'',variable_code:q.get('variable_code')||'',network:q.get('network')||'',sea:q.get('sea')||'',flag:q.get('flag')||''};p.review_queue.limit=Number(q.get('queue_limit')||15);p.review_queue.offset=Number(q.get('queue_offset')||0);p.filters.stations=[{station_id:'DT_0028',station_name:'격리 진도 관측소'}];p.filters.variables=[{variable_code:'WATER_TEMP',label:'수온'},{variable_code:'SALINITY',label:'염분'}];
 if(source!=='REGISTERED'){p.window={...p.window,mode:'ARCHIVE',preset:'custom',start:q.get('date_from')||'2026-07-09 00:00:00',end:q.get('date_to')||'2026-07-09 15:41:20',clock_basis:'UNAPPROVED_NATIVE_SOURCE_CLOCK',offset:null};p.snapshot='isolated-archive';p.archive_samples={rows:[],total_matching_rows:0,limit:15,state:'NO_DATA'};}
 else if(preset==='custom'){p.window.preset='custom';p.window.start=q.get('date_from');p.window.end=q.get('date_to');}
 p.window.as_of=p.window.end;p.window.granularity=Date.parse(p.window.end.replace(' ','T'))-Date.parse(p.window.start.replace(' ','T'))<2*86400000?'hour':'day';const t=p.quality_trend[0];t.bucket=t.start=p.window.start;t.end=p.window.end;return json(p);
}

test('React same-tick station and item changes accumulate; history back and subsequent changes use the restored URL',async()=>{
 try{await mount(React.createElement(Page),scopeResponse,'/qc?source=GD_OBS_ST_MONTHLY&as_of_day=2026-07-09&as_of_time=15%3A41%3A20');const station=byLabel('QC 관측소'),item=byLabel('QC 관측항목');await sameTick(()=>{changeImmediately(station,'DT_0028');changeImmediately(item,'WATER_TEMP');});let q=new URLSearchParams(route.search);assert.equal(q.get('station'),'DT_0028');assert.equal(q.get('item'),'WATER_TEMP');let api=new URL(requests.at(-1).url,'http://localhost').searchParams;assert.equal(api.get('station_id'),'DT_0028');assert.equal(api.get('variable_code'),'WATER_TEMP');assert.equal(api.get('date_from'),'2026-07-09 00:00:00');assert.equal(api.get('date_to'),'2026-07-09 15:41:20');assert.equal(byLabel('QC 관측소').value,'DT_0028');assert.equal(byLabel('QC 관측항목').value,'WATER_TEMP');assert.doesNotMatch(container.textContent,/조회 실패|일치하지 않습니다/);
 await sameTick(()=>navigateRoute(-1));q=new URLSearchParams(route.search);assert.equal(q.get('station'),'DT_0028');assert.equal(q.has('item'),false);await sameTick(()=>changeImmediately(byLabel('QC 관측항목'),'SALINITY'));q=new URLSearchParams(route.search);assert.equal(q.get('station'),'DT_0028');assert.equal(q.get('item'),'SALINITY');await sameTick(()=>navigateRoute(-1));assert.equal(new URLSearchParams(route.search).has('item'),false);await sameTick(()=>navigateRoute(-1));assert.equal(new URLSearchParams(route.search).has('station'),false);await sameTick(()=>changeImmediately(byLabel('QC 관측항목'),'WATER_TEMP'));q=new URLSearchParams(route.search);assert.equal(q.has('station'),false);assert.equal(q.get('item'),'WATER_TEMP');assert.equal(q.get('as_of_time'),'15:41:20');assert.doesNotMatch(container.textContent,/조회 실패|일치하지 않습니다/);
 }finally{await dispose();}
});
test('React same-tick source, preset and reset transitions preserve the intended scope and native cutoff',async()=>{
 try{await mount(React.createElement(Page),scopeResponse);await sameTick(()=>{changeImmediately(byLabel('QC 자료 경로'),'GD_OBS_ST_MONTHLY');button('최근 7일').dispatchEvent(new MouseEvent('click',{bubbles:true}));});let q=new URLSearchParams(route.search);assert.equal(q.get('source'),'GD_OBS_ST_MONTHLY');assert.equal(q.get('date_from'),'2026-07-03 00:00:00');assert.equal(q.get('date_to'),'2026-07-09 15:41:20');assert.equal(q.get('range'),'7d');assert.doesNotMatch(container.textContent,/조회 실패|일치하지 않습니다/);
 await sameTick(()=>{changeImmediately(byLabel('QC 해역'),'서해');changeImmediately(byLabel('QC 관측망'),'조위관측소');});q=new URLSearchParams(route.search);assert.equal(q.get('sea'),'서해');assert.equal(q.get('network'),'조위관측소');await sameTick(()=>{button('필터 초기화').dispatchEvent(new MouseEvent('click',{bubbles:true}));changeImmediately(byLabel('QC 관측소'),'DT_0028');changeImmediately(byLabel('QC 관측항목'),'WATER_TEMP');});q=new URLSearchParams(route.search);assert.equal(q.has('sea'),false);assert.equal(q.has('network'),false);assert.equal(q.get('station'),'DT_0028');assert.equal(q.get('item'),'WATER_TEMP');assert.equal(q.get('date_to'),'2026-07-09 15:41:20');await sameTick(()=>{changeImmediately(byLabel('QC 자료 경로'),'REGISTERED');button('기준일 전날').dispatchEvent(new MouseEvent('click',{bubbles:true}));});q=new URLSearchParams(route.search);assert.equal(q.get('source'),'REGISTERED');assert.equal(q.get('data_mode'),'LIVE');assert.equal(q.get('preset'),'yesterday');assert.equal(q.has('date_from'),false);assert.equal(q.has('date_to'),false);assert.equal(q.has('station'),false);assert.equal(q.has('item'),false);assert.match(container.querySelector('.qc-daily-date-summary').textContent,/2026-10-08T00:00:00/);assert.doesNotMatch(container.textContent,/조회 실패|일치하지 않습니다/);
 }finally{await dispose();}
});
test('React filter reset clears legacy scope aliases; back restores them without contaminating later canonical changes',async()=>{
 try{await mount(React.createElement(Page),scopeResponse,'/qc?source=GD_OBS_ST_MONTHLY&as_of_day=2026-07-09&as_of_time=15%3A41%3A20&station_id=DT_0028&variable_code=WATER_TEMP');assert.equal(byLabel('QC 관측소').value,'DT_0028');assert.equal(byLabel('QC 관측항목').value,'WATER_TEMP');await click(button('필터 초기화'));let q=new URLSearchParams(route.search);for(const key of ['station','station_id','item','variable_code'])assert.equal(q.has(key),false);assert.equal(q.get('as_of_time'),'15:41:20');await sameTick(()=>navigateRoute(-1));assert.equal(byLabel('QC 관측소').value,'DT_0028');assert.equal(byLabel('QC 관측항목').value,'WATER_TEMP');await sameTick(()=>{changeImmediately(byLabel('QC 관측소'),'DT_0028');changeImmediately(byLabel('QC 관측항목'),'SALINITY');});q=new URLSearchParams(route.search);assert.equal(q.get('station'),'DT_0028');assert.equal(q.get('item'),'SALINITY');assert.equal(q.has('station_id'),false);assert.equal(q.has('variable_code'),false);assert.doesNotMatch(container.textContent,/조회 실패|일치하지 않습니다/);
 }finally{await dispose();}
});

test('React daily page bootstraps backend today; presets query every widget with one scope',async()=>{
 try{await mount(React.createElement(Page),url=>url.includes('/context')?json(context()):json(overview(true)));assert.match(container.textContent,/데이터 없음/);assert.equal(requests.find(r=>r.url.includes('/overview')).url.includes('preset=today'),true);assert.equal(requests.find(r=>r.url.includes('/overview')).url.includes('date_from='),false);assert.equal(button('오늘').getAttribute('aria-pressed'),'true');assert.equal(container.querySelectorAll('.qc-summary-card').length,6);assert.equal(container.querySelectorAll('.qc-dashboard-grid > .qc-panel').length,6);assert.equal(container.querySelector('.qc-provenance').open,false);assert.equal(container.querySelector('.qc-workflow-tools').open,false);
 for(const [label,preset] of [['어제','yesterday'],['최근 7일','7d'],['최근 30일','30d']]){globalThis.fetch=async(url,init={})=>{requests.push({url:String(url),init});return json(String(url).includes('/context')?context():emptyPreset(preset));};await click(button(label));assert.ok(requests.at(-1).url.includes('preset='+preset));assert.equal(button(label).getAttribute('aria-pressed'),'true');assert.match(route.search,new RegExp('preset='+preset));assert.doesNotMatch(container.textContent,/조회 실패/);}
 }finally{await dispose();}
});
test('React priority queue calls the selected candidate only and uses backend BAD catalog; raw samples stay out',async()=>{
 let selected='',page=-1;try{await mount(React.createElement(QCDailyQueue,{packet:overview(),selectedId:'',onSelect:id=>selected=id,onPage:v=>page=v}),()=>json({}));assert.equal(container.querySelector('tbody tr').textContent.includes('BAD'),true);await click(byLabel('격리 시험 관측소 수온 QC 상세검토'));assert.equal(selected,'qc:TEST-ROW');assert.equal(byLabel('다음 검토 Queue').disabled,true);assert.equal(page,-1);assert.equal(container.querySelectorAll('tbody tr').length,1);
 }finally{await dispose();}
});
test('React detail renders actual late arrivals, inferred gap and null/duplicate points; zoom leaves raw values intact',async()=>{
 try{await mount(React.createElement(Drawer,{id:'qc:TEST-ROW',overview:overview(),request:request(),onClose(){},onChanged(){}}),()=>json(detail()));assert.equal(container.querySelector('[role="dialog"]').getAttribute('aria-modal'),'true');assert.equal(container.querySelectorAll('svg rect.gap').length,1);assert.equal(container.querySelectorAll('svg path.late').length,1);assert.equal(container.querySelectorAll('svg polyline.actual').length,0);assert.match(container.textContent,/수신 지연 이력/);assert.match(container.textContent,/사용 가능한 모델 없음/);assert.equal(container.querySelectorAll('svg line.prediction').length,0);assert.equal(container.querySelectorAll('.qc-drawer-chart svg circle').length,4);await click(button('확대 +'));assert.equal(byLabel('QC 상세 시계열 확대').value,'60');assert.match(container.textContent,/21/);assert.equal(requests.length,1);assert.equal(button('검토 결정 승인').disabled,true);assert.match(container.textContent,/실제 담당 계정은 운영 단계/);assert.equal(container.querySelectorAll('svg .gap').length,1);
 }finally{await dispose();}
});
test('React stored AI detail overlays an actual saved expectation and residual only when AVAILABLE',async()=>{
 try{await mount(React.createElement(Drawer,{id:'qc:TEST-ROW',overview:overview(),request:request(),onClose(){},onChanged(){}}),()=>json(detail(true)));assert.equal(container.querySelectorAll('svg line.prediction').length,1);assert.match(container.textContent,/Residual/);assert.match(container.textContent,/test-v1/);assert.match(container.textContent,/저장된 AI 기대값/);const check=container.querySelector('input[type="checkbox"]');await click(check);assert.equal(container.querySelectorAll('svg line.prediction').length,0);assert.equal(requests.length,1);
 }finally{await dispose();}
});
test('React missing and unknown colors follow the same backend semantic catalog across charts, heatmap and Drawer',async()=>{
 const css=(value,property='background')=>{const node=document.createElement('i');node.style[property]=value;return node.style[property];};
 // Test both the current catalog and a changed isolated catalog to catch hardcoded frontend colors.
 for(const palette of [['#a855f7','#9ca3af'],['#5b21b6','#737373']]){
  const p=overview(),d=detail(),counts={normal:0,suspect:0,bad:0,missing:1,unknown:1};
  for(const flag of p.flag_catalog){if(flag.semantic==='MISSING')flag.color=palette[0];if(flag.semantic==='UNKNOWN')flag.color=palette[1];}d.display_catalog=structuredClone(p.flag_catalog);d.observation.flag='9';d.rule_results.rows[0].flag='9';d.surrounding_timeseries.rows[0].flag='UNKNOWN';
  p.total_observations=2;p.flag_distribution=p.flag_catalog.map(f=>({...f,count:['MISSING','UNKNOWN'].includes(f.semantic)?1:0,rate:['MISSING','UNKNOWN'].includes(f.semantic)?50:0,denominator:2}));p.quality_trend=['missing','unknown'].map((key,i)=>({...p.quality_trend[0],bucket:i?p.window.end:p.quality_trend[0].bucket,start:i?p.window.end:p.quality_trend[0].start,end:i?p.window.end:p.quality_trend[0].end,total:1,counts:Object.fromEntries(Object.keys(counts).map(k=>[k,k===key?1:0])),rates:Object.fromEntries(Object.keys(counts).map(k=>[k,k===key?100:0]))}));p.station_variable_matrix=['missing','unknown'].map((key,i)=>({station_id:'TEST-'+i,station_name:key,variable_code:'WATER_TEMP',total:1,counts:Object.fromEntries(Object.keys(counts).map(k=>[k,k===key?1:0])),rates:Object.fromEntries(Object.keys(counts).map(k=>[k,k===key?100:0])),state:key.toUpperCase(),top_rule:null,recent_issue_time:null}));
  try{await mount(React.createElement(React.Fragment,null,React.createElement(QCDailyDistribution,{packet:p,onFlag(){}}),React.createElement(QCDailyTrend,{packet:p}),React.createElement(QCDailyMatrix,{packet:p,onSelect(){}}),React.createElement(Drawer,{id:d.id,overview:p,request:request(),onClose(){},onChanged(){}})),()=>json(d));
   for(const [code,semantic,color] of [['9','MISSING',palette[0]],['UNKNOWN','UNKNOWN',palette[1]]]){const flag=p.flag_catalog.find(f=>f.code===code);assert.equal(flag.semantic,semantic);const legend=[...container.querySelectorAll('.qc-distribution-list button')].find(b=>b.textContent.includes(flag.label));assert.equal(legend.querySelector('i').style.background,css(color));assert.ok([...container.querySelectorAll('.qc-donut .recharts-sector')].some(path=>path.getAttribute('fill')===color));const trend=[...container.querySelectorAll('.qc-trend .qc-chart-legend button')].find(b=>b.textContent===flag.label);assert.equal(trend.querySelector('i').style.background,css(color));assert.ok([...container.querySelectorAll('.qc-trend .recharts-area-area')].some(path=>path.getAttribute('fill')===color));const cell=[...container.querySelectorAll('button[data-qc-cell]')].find(b=>b.textContent===flag.label);assert.equal(cell.style.background,css(color+'40'));const detailLegend=[...container.querySelectorAll('.qc-candidate-drawer .qc-chart-legend span')].find(s=>s.textContent===flag.label+' ('+code+')');assert.equal(detailLegend.querySelector('i').style.background,css(color));assert.ok([...container.querySelectorAll('.qc-drawer-chart svg circle')].some(c=>c.getAttribute('fill')===color));}
   assert.equal(container.querySelector('.qc-drawer-observation div:nth-child(3) dd').style.color,css(palette[0],'color'));assert.equal(container.querySelector('.qc-drawer-rule-table tbody tr td:nth-child(5)').style.color,css(palette[0],'color'));assert.equal(button('결측 판정로 플래그 수정').style.color,css(palette[0],'color'));
  }finally{await dispose();}
 }
});
test('React actual values, selected series and stored AI comparisons retain source precision',async()=>{
 const d=detail(true);d.observation.value=21.38;d.observation.value_raw=' 21.38';d.rule_results.rows[0].input_value=21.38;d.ai.results[0].predicted_value=21.123456;d.ai.results[0].residual=d.observation.value-d.ai.results[0].predicted_value;
 try{await mount(React.createElement(Drawer,{id:d.id,overview:overview(),request:request(),onClose(){},onChanged(){}}),()=>json(d));const actual=container.querySelector('.qc-drawer-observation div:nth-child(2) dd');assert.match(actual.textContent,/^21\.38 /);assert.doesNotMatch(actual.textContent,/21\.4/);assert.match(container.querySelector('.qc-drawer-record').textContent,/수치 21\.38 degC/);assert.match(container.querySelector('.qc-drawer-record').textContent,/" 21\.38"/);assert.equal(container.querySelector('.qc-drawer-rule-table tbody tr td:nth-child(3)').textContent,'21.38');const comparisons=[...container.querySelectorAll('#qc-detail-ai dt')];assert.equal(comparisons.find(n=>n.textContent==='정상 기대값').nextElementSibling.textContent,'21.123456');assert.equal(comparisons.find(n=>n.textContent==='Residual').nextElementSibling.textContent,'0.256544');
 }finally{await dispose();}
 const p=overview();p.review_queue.rows[0].value=21.38;try{await mount(React.createElement(QCDailyQueue,{packet:p,selectedId:'',onSelect(){},onPage(){}}),()=>json({}));assert.equal(container.querySelector('tbody tr td:nth-child(4)').textContent,'21.38');}finally{await dispose();}
});
test('React failed/stale details show an error and retry, never a graph from a different cutoff',async()=>{
 let calls=0;try{await mount(React.createElement(Drawer,{id:'qc:TEST-ROW',overview:overview(),request:request(),onClose(){},onChanged(){}}),()=>{calls++;const v=detail();v.window.as_of='2026-10-09T16:00:01+05:30';return json(v);});assert.match(container.textContent,/일치하지 않습니다/);assert.equal(container.querySelectorAll('svg polyline').length,0);globalThis.fetch=async()=>{calls++;return json(detail());};await click(button('상세 다시 조회'));assert.equal(calls,2);assert.match(container.textContent,/실제 관측 시계열/);
 }finally{await dispose();}
});
test('React existing workflow approval checks actor, sends exact revision/hash/comment and blocks a stale 409',async()=>{
 let posts=0;try{await mount(React.createElement(Drawer,{id:'qc:TEST-ROW',overview:overview(),request:request(),onClose(){},onChanged(){}}),(url,init)=>{if(url.endsWith('/session'))return json({user_id:'fixture-reviewer',role:'reviewer'});if(init.method==='POST'){posts++;return json({detail:{code:'WORKFLOW_CONCURRENT_CHANGE'}},409);}return json(detail(false,true));});assert.equal(button('검토 결정 승인').disabled,true);await click(button('담당자·권한 확인'));assert.equal(button('검토 결정 승인').disabled,false);await input(byLabel('QC 상세 검토 의견'),'격리 UI 검토 의견');await click(button('검토 결정 승인'));assert.equal(posts,1);const submitted=requests.find(r=>r.init.method==='POST');assert.equal(submitted.url,'/api/agents/workflows/TEST-WORKFLOW/decision');const body=JSON.parse(submitted.init.body);assert.equal(body.expected_revision,3);assert.equal(body.expected_recommendation_sha256,'a'.repeat(64));assert.equal(body.comment,'격리 UI 검토 의견');assert.equal(body.decision,'APPROVED');assert.ok(body.request_key);assert.match(container.textContent,/WORKFLOW_CONCURRENT_CHANGE/);assert.equal(requests.filter(r=>r.init.method==='POST').length,1);
 }finally{await dispose();}
});
test('React completed workflow is shown independently of absent AI/evidence and cannot re-approve',async()=>{
 const done=detail();done.workflow.status='COMPLETED';done.capabilities[0].reason='AUTHENTICATED_ROLE_OWNER_AND_WORKFLOW_STATE_REQUIRED';done.review_history=[{revision:4,action:'RESUME',actor_id:'fixture-reviewer',from_status:'APPROVED',to_status:'COMPLETED',created_at:'2026-10-09T15:55:00+05:30'}];try{await mount(React.createElement(Drawer,{id:'qc:TEST-ROW',overview:overview(),request:request(),onClose(){},onChanged(){}}),()=>json(done));assert.match(container.textContent,/검토 처리 완료/);assert.match(container.textContent,/fixture-reviewer/);assert.match(container.textContent,/관련 Evidence 없음/);assert.match(container.textContent,/사용 가능한 모델 없음/);assert.equal(button('검토 결정 승인').disabled,true);
 }finally{await dispose();}
});
test('React legend and heatmap selections apply one common filter to all widgets, with source clock unchanged',async()=>{
 try{await mount(React.createElement(Page),url=>url.includes('/context')?json(context()):json(overview()));await click([...container.querySelectorAll('.qc-distribution-list button')].find(b=>b.textContent.includes('BAD')));assert.ok(requests.at(-1).url.includes('flag=4'));assert.match(route.search,/flag=4/);globalThis.fetch=async(url,init={})=>{requests.push({url:String(url),init});if(String(url).includes('/context'))return json(context());const v=overview(),q=new URL(String(url),'http://localhost').searchParams;v.scope.flag=q.get('flag')||'';v.scope.station_id=q.get('station_id')||'';v.scope.variable_code=q.get('variable_code')||'';return json(v);};await click(button('다시 조회'));assert.match(container.textContent,/상태 BAD/);await click(container.querySelector('button[data-qc-cell]'));assert.ok(requests.at(-1).url.includes('station_id=TEST-STATION'));assert.ok(requests.at(-1).url.includes('variable_code=WATER_TEMP'));assert.ok(requests.at(-1).url.includes('flag=4'));assert.equal(new URL(requests.at(-1).url,'http://localhost').searchParams.get('date_from'),null);assert.match(route.search,/station=TEST-STATION/);
 }finally{await dispose();}
});
test('React review authorization failure drops the actor and disables further writes',async()=>{
 let posts=0,unauthorized=false;try{await mount(React.createElement(Drawer,{id:'qc:TEST-ROW',overview:overview(),request:request(),onClose(){},onChanged(){}}),(url,init)=>{if(url.endsWith('/session'))return json({user_id:'fixture-reviewer',role:'reviewer'});if(init.method==='POST'){posts++;unauthorized=true;return json({detail:{code:'ROLE_NOT_ALLOWED'}},403);}return json(detail(false,!unauthorized));});await click(button('담당자·권한 확인'));await input(byLabel('QC 상세 검토 의견'),'격리 권한 오류 시험');await click(button('검토 결정 승인'));assert.equal(posts,1);assert.equal(button('검토 결정 승인').disabled,true);assert.match(container.textContent,/ROLE_NOT_ALLOWED/);assert.equal(requests.filter(r=>r.init.method==='POST').length,1);
 }finally{await dispose();}
});
test('React refresh rechecks the backend clock across midnight and replaces the whole daily window',async()=>{
 let nextDay=false;try{await mount(React.createElement(Page),url=>{if(url.includes('/context')){const c=context();if(nextDay){c.today='2026-10-10';c.current_time='00:05:00';c.server_now='2026-10-10T00:05:00+05:30';}return json(c);}const v=overview(true);if(nextDay){v.window.start='2026-10-10T00:00:00+05:30';v.window.end='2026-10-10T00:05:00+05:30';v.window.as_of=v.window.end;v.quality_trend[0].bucket=v.window.start;v.quality_trend[0].start=v.window.start;v.quality_trend[0].end=v.window.end;}return json(v);});nextDay=true;await click(byLabel('운영 QC 새로고침'));assert.equal(requests.filter(r=>r.url.includes('/context')).length,2);assert.match(container.querySelector('.qc-daily-date-summary').textContent,/2026-10-10T00:00:00/);assert.doesNotMatch(container.querySelector('.qc-daily-date-summary').textContent,/2026-10-09/);assert.doesNotMatch(container.textContent,/조회 실패/);
 }finally{await dispose();}
});
test('React linked equipment events and inspection evidence show their actual dates without claiming equipment-history approval',async()=>{
 const d=detail();d.equipment_epoch={status:'EXPLICIT_LINKED_EQUIPMENT_EVENTS',physical_sensor_id:'TEST-PHYSICAL',sensor_id:'TEST-SENSOR',sensor_episode_id:'TEST-EPISODE',effective_start:'2026-01-01T00:00:00+05:30',effective_end:'2027-01-01T00:00:00+05:30',install_date:'2026-01-01T00:00:00+05:30',replacement_date:null,calibration_date:'2026-06-01T00:00:00+05:30',events:[{event_type:'CALIBRATION',event_at:'2026-06-01T00:00:00+05:30'}],approved_equipment_history:false};d.evidence.inspection={status:'AVAILABLE',rows:[{id:'TEST-REPORT',title:'격리 점검 보고서',available_at:'2026-10-09T15:50:00+05:30',text:'실제 연결 근거 표시 시험'}]};try{await mount(React.createElement(Drawer,{id:d.id,overview:overview(),request:request(),onClose(){},onChanged(){}}),()=>json(d));assert.match(container.querySelector('#qc-detail-equipment').textContent,/2026-06-01/);assert.match(container.querySelector('#qc-detail-equipment').textContent,/담당 승인과 별도/);assert.match(container.querySelector('#qc-detail-evidence').textContent,/격리 점검 보고서/);assert.equal(button('검토 결정 승인').disabled,true);
 }finally{await dispose();}
});
