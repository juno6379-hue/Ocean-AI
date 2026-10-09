import test from 'node:test';
import assert from 'node:assert/strict';
import {resolve} from 'node:path';
import {Window} from 'happy-dom';
import {compile,frontend,apiFixture,json} from './ai-insights-sample-runtime.mjs';
import {aiFixture as f} from './ai-insights-sample-fixtures.mjs';

const win=new Window({url:'http://localhost/ai-insights?source=SAMPLE'});
for(const name of ['window','document','HTMLElement','SVGElement','Element','Node','MouseEvent','KeyboardEvent','Event','CustomEvent','MutationObserver'])globalThis[name]=name==='window'?win:win[name];
Object.defineProperty(globalThis,'navigator',{value:win.navigator,configurable:true});
globalThis.getComputedStyle=win.getComputedStyle.bind(win);globalThis.IS_REACT_ACT_ENVIRONMENT=true;
win.HTMLElement.prototype.getBoundingClientRect=()=>new win.DOMRect(0,0,450,220);
globalThis.ResizeObserver=class{constructor(callback){this.callback=callback;}observe(target){this.callback([{target,contentRect:target.getBoundingClientRect()}]);}unobserve(){}disconnect(){}};
globalThis.requestAnimationFrame=callback=>setTimeout(()=>callback(performance.now()),0);globalThis.cancelAnimationFrame=clearTimeout;
const React=await import('react'),{act}=React,{createRoot}=await import('react-dom/client');
const {MemoryRouter,Routes,Route,useLocation}=await import('react-router-dom');
const Page=(await import(compile(resolve(frontend,'pages/AIInsights.tsx')))).default;
const Sample=(await import(compile(resolve(frontend,'pages/AIInsightsSample.tsx')))).default;
const Layout=(await import(compile(resolve(frontend,'components/Layout.tsx')))).default;
const data=await import(compile(resolve(frontend,'data/aiInsightsSample.ts'))),format=await import(compile(resolve(frontend,'data/qcWorkspace.ts'))),client=await import(compile(resolve(frontend,'api/client.ts')));
let root,container,requests,route,downloads,blobs;
function Capture(){route=useLocation();return null;}
const label=text=>container.querySelector('[aria-label="'+text+'"]'),button=text=>[...container.querySelectorAll('button')].find(b=>b.textContent.trim()===text);
async function flush(){await act(async()=>{await new Promise(r=>setTimeout(r,20));});}
async function mount(api,initial='/ai-insights?source=SAMPLE',actualPage=true){
 requests=[];downloads=[];blobs=new Map();client.setOperatorToken('isolated-actual-ai-operator-never-sample');
 globalThis.fetch=async(url,init={})=>{requests.push({url:String(url),init});return api.respond(String(url),init);};
 URL.createObjectURL=blob=>{const id='blob:isolated-ai-'+blobs.size;blobs.set(id,blob);return id;};URL.revokeObjectURL=()=>{};
 win.HTMLAnchorElement.prototype.click=function(){downloads.push({filename:this.download,href:this.getAttribute('href')});};
 container=document.createElement('div');document.body.append(container);root=createRoot(container);
 const pages=React.createElement(Routes,null,React.createElement(Route,{element:React.createElement(Layout)},
  React.createElement(Route,{path:'/ai-insights',element:React.createElement(actualPage?Page:Sample)}),
  React.createElement(Route,{path:'/qc',element:React.createElement('div',{'data-testid':'qc-return'},'QC return route')})));
 await act(async()=>{root.render(React.createElement(MemoryRouter,{initialEntries:[initial]},React.createElement(Capture),pages));await new Promise(r=>setTimeout(r,20));});await flush();
}
async function dispose(){if(root)await act(async()=>root.unmount());container?.remove();root=null;client.clearOperatorToken();await win.happyDOM.cancelAsync();await win.happyDOM.waitUntilComplete();}
async function click(node){assert.ok(node,'Expected button must render');await act(async()=>{node.dispatchEvent(new MouseEvent('click',{bubbles:true}));await new Promise(r=>setTimeout(r,20));});await flush();}
async function change(node,value){assert.ok(node,'Expected input must render');await act(async()=>{Object.getOwnPropertyDescriptor(Object.getPrototypeOf(node),'value').set.call(node,value);if(node.tagName!=='SELECT')node.dispatchEvent(new Event('input',{bubbles:true}));node.dispatchEvent(new Event('change',{bubbles:true}));await new Promise(r=>setTimeout(r,20));});await flush();}
async function select(id){await change(label('AI 샘플 시나리오'),id);}
async function comment(value='Independent synthetic evidence review'){await change(label('AI 샘플 검토 의견'),value);}

test('Actual AI route sample branch mounts only its isolated workspace and Layout with no operational auth, sources or cookies',async()=>{
 try{await mount(apiFixture());assert.equal(label('AI 자료 경로').value,'SAMPLE');assert.equal(container.querySelectorAll('.ais-kpis article').length,5);assert.equal(container.querySelectorAll('.ais-map-marker').length,4);assert.match(container.querySelector('.ais-banner').textContent,/운영 자료.*0건/);assert.match(container.querySelector('.ais-period').textContent,/2026-07-09T15:41:20\+09:00/);assert.match(container.textContent,/운영 모델 0개/);assert.match(container.textContent,/정량 채점 미산정/);assert.equal(label('담당자 접근 토큰'),null);assert.equal(container.querySelector('.obs-access-panel'),null);assert.doesNotMatch(container.textContent,/해양관측 지식 검색 AI/);assert.equal(requests.length,4);for(const r of requests){assert.ok(r.url.startsWith('/api/ai-insights-sample/'));assert.equal(r.init.credentials,'omit');assert.equal(new Headers(r.init.headers).has('Authorization'),false);assert.equal(new Headers(r.init.headers).has('Cookie'),false);assert.equal(r.url.includes('token'),false);}assert.equal(container.textContent.includes(f.session.session_token),false);assert.equal(win.localStorage.length,0);assert.equal(win.sessionStorage.length,0);
 }finally{await dispose();}
});

test('React all four scenarios preserve global KPI denominators and bind exact dataset values, forecast lines and metrics to the selected case',async()=>{
 try{await mount(apiFixture());const kpis=container.querySelector('.ais-kpis').textContent;
  for(const id of data.aiScenarioIds){await select(id);const d=f.details[id],plot=data.aiSeriesPlot(d.series),selected=d.series.find(p=>p.row_id===d.scenario.selected_row_id);assert.equal(container.querySelector('.ais-kpis').textContent,kpis);assert.match(container.querySelector('.ais-case-detail').textContent,new RegExp(d.scenario.title));assert.ok(container.querySelector('.ais-case-detail').textContent.includes(format.qcValueNumber(selected.value)));assert.ok(container.querySelector('.ais-case-detail').textContent.includes(d.scenario.unit));assert.equal(container.querySelectorAll('.ais-series-point').length,280);for(const field of ['value','prediction','reference_value']){const expected=plot.segments(field).filter(s=>s.length>1).map(s=>s.map(p=>plot.x(p.time)+','+plot.y(p.row[field])).join(' '));assert.deepEqual([...container.querySelectorAll('.ais-line-'+field)].map(n=>n.getAttribute('points')),expected,id+':'+field);}
   const table=container.querySelector('.ais-evaluation-grid table'),rows=[...table.querySelectorAll('tbody tr')];assert.equal(rows.length,2);for(const [i,model] of ['PERSISTENCE','RIDGE'].entries()){const cells=rows[i].querySelectorAll('td');assert.equal(cells[1].textContent,format.qcValueNumber(d.forecast.validation_metrics[model].mae));assert.equal(cells[2].textContent,format.qcValueNumber(d.forecast.test_metrics[model].mae));assert.equal(cells[3].textContent,format.qcValueNumber(d.forecast.test_metrics[model].rmse));}
   assert.match(container.querySelector('.ais-future-prediction').textContent,/2026-07-09T16:00:00\+09:00/);assert.match(container.querySelector('.ais-future-prediction').textContent,/TEST 평가행에 포함하지 않습니다/);assert.match(container.querySelector('.ais-insight').textContent,/확률.*아닙니다/);
  }
 }finally{await dispose();}
});

test('React sample approval stops before report; explicit resume prepares only a bound sample Markdown download with exact UTF8 contents',async()=>{
 try{await mount(apiFixture());await select('spike');assert.equal(button('샘플 보고서 단계 재개').disabled,true);await comment();await click(button('샘플 승인'));assert.match(container.querySelector('.ais-gate').textContent,/샘플 승인.*후속 단계 중지/);assert.equal(container.querySelector('.ais-report-ready'),null);assert.equal(button('샘플 보고서 단계 재개').disabled,false);await comment('Resume synthetic report draft only');await click(button('샘플 보고서 단계 재개'));assert.match(container.querySelector('.ais-gate').textContent,/샘플 보고서 준비 완료/);const reports=[...container.querySelectorAll('.ais-reports tbody tr')],row=reports.find(r=>r.textContent.includes(f.details.spike.scenario.title));await click(row.querySelector('td:last-child button'));assert.match(container.querySelector('.ais-report-ready').textContent,/SAMPLE/);await click(button('샘플 Markdown 다운로드'));assert.equal(downloads.length,1);assert.equal(downloads[0].filename,'ai-sample-spike.md');const content=await blobs.get(downloads[0].href).text();assert.equal(content,f.report.markdown);assert.match(content,/운영 미승인.*실제 발송 없음/);assert.equal(requests.filter(r=>r.url.endsWith('/report')).length,1);assert.ok(requests.filter(r=>r.init.method==='POST').every(r=>r.url.startsWith('/api/ai-insights-sample/')));
 }finally{await dispose();}
});

test('React hold, comment, reject and reset preserve gates, clear old report authority and keep other scenario history independent',async()=>{
 try{await mount(apiFixture());await select('salinity-drift');await comment();await click(button('검토 보류'));assert.match(container.querySelector('.ais-gate').textContent,/검토 보류/);assert.equal(button('샘플 보고서 단계 재개').disabled,true);await comment('Additional synthetic comment');await click(button('검토 의견 저장'));await comment('Reject synthetic candidate');await click(button('샘플 반려'));assert.match(container.querySelector('.ais-gate').textContent,/샘플 반려/);assert.equal(button('샘플 승인').disabled,true);await select('normal');assert.match(container.querySelector('.ais-gate').textContent,/revision 1/);assert.equal(container.querySelectorAll('.ais-history li').length,1);await click(button('샘플 초기화'));assert.match(container.querySelector('.ais-period').textContent,/generation 2/);assert.match(container.querySelector('.ais-gate').textContent,/샘플 검토 대기.*revision 1/);assert.equal(container.querySelector('.ais-report-ready'),null);assert.equal(container.querySelectorAll('.ais-history li').length,1);assert.equal(button('샘플 보고서 단계 재개').disabled,true);
 }finally{await dispose();}
});

test('React stale review refreshes exact evidence and a double click cannot submit two state transitions',async()=>{
 const api=apiFixture();try{await mount(api);api.setRejectNextReview();await comment();await click(button('샘플 승인'));assert.match(container.textContent,/HTTP 409/);assert.match(container.querySelector('.ais-gate').textContent,/revision 1/);await comment('Fresh exact revision after conflict');const approve=button('샘플 승인');await act(async()=>{approve.dispatchEvent(new MouseEvent('click',{bubbles:true}));approve.dispatchEvent(new MouseEvent('click',{bubbles:true}));await new Promise(r=>setTimeout(r,20));});await flush();assert.equal(requests.filter(r=>r.url.endsWith('/review')).length,2);assert.match(container.querySelector('.ais-gate').textContent,/revision 2/);
 }finally{await dispose();}
});

test('React changing scenario aborts a pending detail and cannot paint its late values into the newly selected dataset',async()=>{
 const api=apiFixture();let release,pending;api.setHook((url,init,base)=>url.endsWith('/scenarios/normal')?new Promise(resolve=>{pending=init;release=()=>resolve(base(url,init));}):base(url,init));
 try{await mount(api);assert.ok(release);await select('salinity-drift');assert.equal(pending.signal.aborted,true);await act(async()=>release());await flush();assert.match(container.querySelector('.ais-case-detail').textContent,/염분 Drift/);assert.match(container.querySelector('.ais-case-detail').textContent,/psu/);assert.equal(label('AI 샘플 시나리오').value,'salinity-drift');
 }finally{if(release)release();await dispose();}
});

test('React leaving the AI sample while a review waits aborts transport and sends no downstream read after unmount',async()=>{
 const api=apiFixture();let release,pending;api.setHook((url,init,base)=>url.endsWith('/review')?new Promise(resolve=>{pending=init;release=()=>resolve(base(url,init));}):base(url,init));
 try{await mount(api);await comment();await click(button('샘플 승인'));assert.ok(release);const link=container.querySelector('a[href="/qc?source=SAMPLE"]');await click(link);assert.equal(pending.signal.aborted,true);assert.equal(route.pathname,'/qc');assert.equal(route.search,'?source=SAMPLE');const count=requests.length,finish=release;release=undefined;await act(async()=>finish());await flush();assert.equal(requests.length,count);assert.equal(container.querySelector('.ais-banner'),null);assert.ok(container.querySelector('[data-testid="qc-return"]'));
 }finally{if(release)release();await dispose();}
});

test('React pending bootstrap cannot create a session after navigating out of sample mode',async()=>{
 const api=apiFixture();let release,pending;api.setHook((url,init,base)=>url.endsWith('/context')?new Promise(resolve=>{pending=init;release=()=>resolve(base(url,init));}):base(url,init));
 try{await mount(api);assert.ok(release);await click(container.querySelector('a[href="/qc?source=SAMPLE"]'));assert.equal(pending.signal.aborted,true);await act(async()=>release());await flush();assert.equal(requests.length,1);assert.equal(container.querySelector('.ais-kpis'),null);
 }finally{if(release)release();await dispose();}
});

test('React rejected foreign dataset or inflated confidence never renders its detailed values or review capabilities',async()=>{
 const api=apiFixture();api.setHook((url,init,base)=>{if(url.endsWith('/scenarios/normal')){const d=api.detail('normal');d.scenario.confidence_probability=.999;d.series[0].value=999;return json(d);}return base(url,init);});
 try{await mount(api);assert.match(container.textContent,/응답 확인 실패/);assert.equal(label('AI 샘플 검토 의견'),null);assert.equal(container.querySelector('.ais-line-value'),null);assert.equal(button('샘플 승인'),undefined);
 }finally{await dispose();}
});

test('React selecting a ready report for a different case opens that exact case and report in one click',async()=>{
 const api=apiFixture();let d=api.detail('spike');api.apply('spike',{action:'APPROVE',comment:'Synthetic pre-reviewed case',expected_revision:d.revision,recommendation_sha256:d.recommendation_sha256,request_key:'isolated-pre-approve'});d=api.detail('spike');api.apply('spike',{action:'RESUME',comment:'Synthetic report draft only',expected_revision:d.revision,recommendation_sha256:d.recommendation_sha256,request_key:'isolated-pre-resume'});
 try{await mount(api);assert.equal(label('AI 샘플 시나리오').value,'normal');const row=[...container.querySelectorAll('.ais-reports tbody tr')].find(r=>r.textContent.includes(f.details.spike.scenario.title));await click(row.querySelector('td:last-child button'));await flush();assert.equal(label('AI 샘플 시나리오').value,'spike');assert.equal(requests.filter(r=>r.url.endsWith('/report')).length,1);assert.match(container.querySelector('.ais-report-ready').textContent,/합성 샘플 보고서/);assert.match(container.querySelector('.ais-case-detail').textContent,/센서 Spike/);
 }finally{await dispose();}
});

test('React cannot preview or download modified Markdown whose UTF8 bytes do not match its supplied SHA',async()=>{
 const api=apiFixture();let d=api.detail('spike');api.apply('spike',{action:'APPROVE',comment:'Synthetic approval',expected_revision:d.revision,recommendation_sha256:d.recommendation_sha256,request_key:'isolated-checksum-approve'});d=api.detail('spike');api.apply('spike',{action:'RESUME',comment:'Synthetic resume',expected_revision:d.revision,recommendation_sha256:d.recommendation_sha256,request_key:'isolated-checksum-resume'});
 api.setHook((url,init,base)=>{if(url.endsWith('/report')){const report=api.report('spike');report.markdown+='\nTampered payload';return json(report);}return base(url,init);});
 try{await mount(api);await select('spike');const row=[...container.querySelectorAll('.ais-reports tbody tr')].find(r=>r.textContent.includes(f.details.spike.scenario.title));await click(row.querySelector('td:last-child button'));assert.equal(container.querySelector('.ais-report-ready'),null);assert.equal(button('샘플 Markdown 다운로드'),undefined);assert.match(container.querySelector('.ais-reports [role="alert"]').textContent,/SHA|해시|바이트/);assert.equal(downloads.length,0);
 }finally{await dispose();}
});

test('React switching sample source to actual AI aborts its pending response and returns without sample metrics or source context',async()=>{
 const api=apiFixture();let release,pending;api.setHook((url,init,base)=>{
  if(!url.startsWith('/api/ai-insights-sample/')){assert.equal(init.method||'GET','GET');return url.startsWith('/api/stations?')?json([]):json({detail:'Isolated operational empty fixture'},404);}
  return url.endsWith('/overview')?new Promise(resolve=>{pending=init;release=()=>resolve(base(url,init));}):base(url,init);
 });
 try{await mount(api);assert.ok(release);await change(label('AI 자료 경로'),'REGISTERED');assert.equal(route.pathname,'/ai-insights');assert.equal(route.search,'?data_mode=LIVE');assert.equal(pending.signal.aborted,true);await act(async()=>release());await flush();assert.equal(container.querySelector('.ais-banner'),null);assert.equal(container.querySelector('.ais-kpis'),null);assert.match(container.textContent,/AI 분석 인사이트/);assert.match(container.textContent,/평가대상 없음/);assert.ok(requests.filter(r=>!r.url.startsWith('/api/ai-insights-sample/')).every(r=>!r.url.includes('SAMPLE')));assert.ok(requests.filter(r=>r.init.method==='POST').every(r=>r.url.startsWith('/api/ai-insights-sample/')));
 }finally{if(release)release();await dispose();}
});
