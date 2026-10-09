import test from 'node:test';
import assert from 'node:assert/strict';
import {resolve} from 'node:path';
import {Window} from 'happy-dom';
import {compile,frontend,apiFixture,json} from './qc-sample-workspace-runtime.mjs';
import {sampleFixture} from './qc-sample-fixtures.mjs';
import {context as operatingContext,overview as operatingOverview,request as operatingRequest} from './qc-daily-fixtures.mjs';

const win=new Window({url:'http://localhost/qc'});
for(const name of ['window','document','HTMLElement','SVGElement','Element','Node','MouseEvent','KeyboardEvent','Event','CustomEvent','MutationObserver'])globalThis[name]=name==='window'?win:win[name];
Object.defineProperty(globalThis,'navigator',{value:win.navigator,configurable:true});
win.HTMLElement.prototype.getBoundingClientRect=()=>new win.DOMRect(0,0,450,220);
globalThis.ResizeObserver=class{constructor(callback){this.callback=callback;}observe(target){this.callback([{target,contentRect:target.getBoundingClientRect()}]);}unobserve(){}disconnect(){}};
globalThis.requestAnimationFrame=callback=>setTimeout(()=>callback(performance.now()),0);globalThis.cancelAnimationFrame=clearTimeout;
globalThis.IS_REACT_ACT_ENVIRONMENT=true;
const React=await import('react'),{act}=React,{createRoot}=await import('react-dom/client');
const {MemoryRouter,Routes,Route,useLocation,useNavigate}=await import('react-router-dom');
const Page=(await import(compile(resolve(frontend,'pages/QCCopilot.tsx')))).default;
const Standalone=(await import(compile(resolve(frontend,'pages/QCSample.tsx')))).default;
const Layout=(await import(compile(resolve(frontend,'components/Layout.tsx')))).default;
const apiClient=await import(compile(resolve(frontend,'api/client.ts')));
const daily=await import(compile(resolve(frontend,'data/qcWorkspace.ts')));
let root,container,requests,route,navigate;
function CaptureRoute(){route=useLocation();navigate=useNavigate();return null;}
async function flush(){await act(async()=>{await new Promise(r=>setTimeout(r,15));});}
async function mount(api,initial='/qc?source=SAMPLE',withLayout=false){
 requests=[];apiClient.setOperatorToken('isolated-operational-token-never-a-sample');
 globalThis.fetch=async(input,init={})=>{requests.push({url:String(input),init});return api.respond(String(input),init);};
 container=document.createElement('div');document.body.append(container);root=createRoot(container);
 const pages=[React.createElement(Route,{key:'qc',path:'/qc',element:React.createElement(Page)}),React.createElement(Route,{key:'copilot',path:'/copilot',element:React.createElement(Page)}),React.createElement(Route,{key:'standalone',path:'/qc/sample',element:React.createElement(Standalone)}),React.createElement(Route,{key:'ai',path:'/ai-insights',element:React.createElement('div',{'data-testid':'sample-ai-navigation-target'},'AI route target only')})];
 await act(async()=>{root.render(React.createElement(MemoryRouter,{initialEntries:[initial]},React.createElement(CaptureRoute),
  React.createElement(Routes,null,...(withLayout?[React.createElement(Route,{element:React.createElement(Layout)},...pages)]:pages))));await new Promise(r=>setTimeout(r,15));});
 await flush();
}
async function dispose(){if(root)await act(async()=>root.unmount());container?.remove();root=null;apiClient.clearOperatorToken();await win.happyDOM.waitUntilComplete();}
const label=text=>container.querySelector(`[aria-label="${text}"]`),button=text=>[...container.querySelectorAll('button')].find(b=>b.textContent.trim()===text);
async function click(node){assert.ok(node,'Expected action must be rendered');await act(async()=>{node.dispatchEvent(new MouseEvent('click',{bubbles:true}));await new Promise(r=>setTimeout(r,15));});await flush();}
async function change(node,value){assert.ok(node,'Expected source control must be rendered');await act(async()=>{Object.getOwnPropertyDescriptor(Object.getPrototypeOf(node),'value').set.call(node,value);if(node.tagName!=='SELECT')node.dispatchEvent(new Event('input',{bubbles:true}));node.dispatchEvent(new Event('change',{bubbles:true}));await new Promise(r=>setTimeout(r,15));});await flush();}
async function choose(name){const scenario=sampleFixture.context.scenario_catalog.find(s=>s.scenario_id===name);await click([...container.querySelectorAll('.qs-table tbody button')].find(b=>b.textContent.trim()===scenario.label+' 상세'));}

test('React operational QC sample source mounts only the isolated engine workspace and never sends stored operator auth',async()=>{
 try{await mount(apiFixture());assert.equal(route.pathname,'/qc');assert.equal(label('QC 자료 경로').value,'SAMPLE');assert.match(container.textContent,/품질 현황/);assert.match(container.textContent,/샘플/);assert.equal(container.querySelectorAll('.qs-shortcuts button').length,4);assert.equal(container.querySelectorAll('.qs-metrics article').length,6);assert.match(container.querySelector('.qs-time').textContent,/2026-07-09T15:41:20\+09:00/);
  assert.equal(requests.length,3);for(const r of requests){assert.ok(r.url.startsWith('/api/qc-sample/'));assert.equal(new Headers(r.init.headers).has('Authorization'),false);assert.equal(r.init.credentials,'omit');assert.equal(r.url.includes('token'),false);}assert.equal(container.querySelector('.qc-workflow-tools'),null);assert.equal(container.textContent.includes(sampleFixture.session.session_token),false);assert.equal(win.localStorage.length,0);assert.equal(win.sessionStorage.length,0);
 }finally{await dispose();}
});

test('React source switching clears operational filters, preserves history and returns to actual empty QC without sample counts',async()=>{
 const initial='/qc?source=GD_OBS_ST_MONTHLY&station=DT_0028&item=WATER_TEMP&as_of_day=2026-07-09&as_of_time=15%3A41%3A20&sea=서해';
 try{await mount(apiFixture(),initial);assert.match(container.textContent,/선택 시간창 데이터 없음/);assert.ok(requests.some(r=>r.url.startsWith('/api/qc/overview?')));await change(label('QC 자료 경로'),'SAMPLE');assert.equal(route.search,'?source=SAMPLE');assert.equal(container.querySelectorAll('.qs-shortcuts button').length,4);await act(async()=>navigate(-1));await flush();assert.equal(new URLSearchParams(route.search).get('station'),'DT_0028');assert.equal(new URLSearchParams(route.search).get('item'),'WATER_TEMP');assert.equal(label('QC 자료 경로').value,'GD_OBS_ST_MONTHLY');assert.equal(container.querySelector('.qs-banner'),null);
  await act(async()=>navigate(1));await flush();assert.equal(route.search,'?source=SAMPLE');await change(label('QC 자료 경로'),'REGISTERED');assert.equal(route.pathname,'/qc');assert.equal(route.search,'');assert.equal(label('QC 자료 경로').value,'REGISTERED');assert.equal(container.querySelector('.qs-shortcuts'),null);assert.equal(container.querySelectorAll('.qc-summary-card').length,6);assert.match(container.textContent,/선택 시간창 데이터 없음/);assert.doesNotMatch(container.querySelector('.qc-summary-cards').textContent,/대표 사례 4건 기준/);
 }finally{await dispose();}
});

test('React four sample scenarios keep one fixed aggregate scope; detail approval stops until an explicit sample draft resume',async()=>{
 try{await mount(apiFixture());const before=[...container.querySelectorAll('.qs-metrics article')].slice(0,4).map(n=>n.textContent);assert.ok(before.every(text=>text.includes('1건')&&text.includes('25%')));
  await choose('missing');assert.equal(container.querySelectorAll('.qs-missing-slot').length,3);assert.deepEqual([...container.querySelectorAll('.qs-metrics article')].slice(0,4).map(n=>n.textContent),before);await click(label('샘플 상세 닫기'));await choose('spike');assert.match(container.querySelector('.qs-detail-facts').textContent,/45 degree_C/);assert.equal(button('샘플 후속 단계 재개').disabled,true);await change(label('샘플 검토 의견'),'운영 화면에서 격리된 샘플 근거 확인');await click(button('샘플 승인'));assert.match(container.querySelector('.qs-gate-state').textContent,/샘플 승인.*후속 단계 중지/);assert.equal(button('샘플 후속 단계 재개').disabled,false);await change(label('샘플 검토 의견'),'가상 초안 단계만 재개');await click(button('샘플 후속 단계 재개'));assert.match(container.querySelector('.qs-history').textContent,/COMPLETE_SAMPLE_DRAFT/);assert.match(container.querySelector('.qs-gate-state').textContent,/샘플 처리 완료/);assert.match(container.querySelector('.qs-metrics article:last-child').textContent,/1건/);const writes=requests.filter(r=>r.init.method==='POST');assert.ok(writes.every(r=>r.url.startsWith('/api/qc-sample/')));assert.equal(writes.filter(r=>r.url.endsWith('/review')).length,2);
 }finally{await dispose();}
});

test('React switching an unfinished operational request to sample aborts its transport and discards a late operational packet',async()=>{
 const api=apiFixture();let release,pending;
 api.setHook((url,init,base)=>url.startsWith('/api/qc/overview?')?new Promise(resolve=>{pending=init;release=()=>resolve(json(operatingOverview(true)));}):base(url,init));
 try{await mount(api,'/qc');assert.ok(release);await change(label('QC 자료 경로'),'SAMPLE');assert.equal(pending.signal.aborted,true);await act(async()=>release());await flush();assert.equal(label('QC 자료 경로').value,'SAMPLE');assert.equal(container.querySelectorAll('.qs-shortcuts button').length,4);assert.equal(container.querySelector('.qc-summary-cards'),null);
 }finally{if(release)release();await dispose();}
});

test('React leaving sample during an unfinished overview aborts it and prevents late sample data from replacing operational empty state',async()=>{
 const api=apiFixture();let release,pending;
 api.setHook((url,init,base)=>url.startsWith('/api/qc-sample/')&&url.endsWith('/overview')?new Promise(resolve=>{pending=init;release=()=>resolve(base(url,init));}):base(url,init));
 try{await mount(api);assert.ok(release);await change(label('QC 자료 경로'),'REGISTERED');assert.equal(pending.signal.aborted,true);await act(async()=>release());await flush();assert.equal(route.search,'');assert.match(container.textContent,/선택 시간창 데이터 없음/);assert.equal(container.querySelector('.qs-shortcuts'),null);assert.equal(container.querySelector('.qs-banner'),null);
 }finally{if(release)release();await dispose();}
});

test('React leaving sample during a pending review aborts it and performs no downstream read or operational write',async()=>{
 const api=apiFixture();let release,pending;
 api.setHook((url,init,base)=>url.startsWith('/api/qc-sample/')&&url.endsWith('/review')?new Promise(resolve=>{pending=init;release=()=>resolve(base(url,init));}):base(url,init));
 try{await mount(api);await choose('normal');await change(label('샘플 검토 의견'),'화면 전환 중 요청 격리');await click(button('샘플 승인'));assert.ok(release);await change(label('QC 자료 경로'),'REGISTERED');assert.equal(pending.signal.aborted,true);const calls=requests.length,finish=release;release=undefined;await act(async()=>finish());await flush();assert.equal(requests.length,calls);assert.equal(container.querySelector('[role="dialog"]'),null);assert.match(container.textContent,/선택 시간창 데이터 없음/);assert.ok(requests.filter(r=>r.init.method==='POST').every(r=>r.url.startsWith('/api/qc-sample/')));
 }finally{if(release)release();await dispose();}
});

test('Registered source guards reject SAMPLE packets and forged source metadata even when the sample route is supported',()=>{
 assert.equal(daily.validQCContext({...operatingContext(),default_source:'SAMPLE'}),false);assert.equal(daily.validQCDailyOverview(sampleFixture.overview,operatingRequest()),false);const forged=operatingOverview(true);forged.source='SAMPLE';forged.window.source='SAMPLE';assert.equal(daily.validQCDailyOverview(forged,operatingRequest()),false);
});

test('Standalone sample route still mounts its isolated page without operational source selectors or operational requests',async()=>{
 try{await mount(apiFixture(),'/qc/sample');assert.equal(label('QC 자료 경로'),null);assert.match(container.textContent,/QC 샘플 검증/);assert.equal(container.querySelectorAll('.qs-shortcuts button').length,4);assert.ok(requests.every(r=>r.url.startsWith('/api/qc-sample/')));
 }finally{await dispose();}
});

test('Actual Layout retains sample only between QC and AI menus and never mounts operational auth, workflow or RAG in sample mode',async()=>{
 for(const entry of ['/qc?source=SAMPLE','/copilot?source=SAMPLE','/qc/sample','/ai-insights?source=SAMPLE']){
  try{await mount(apiFixture(),entry,true);const links=[...container.querySelectorAll('nav a')];assert.equal(links.length,12);
   for(const link of links){const url=new URL(link.getAttribute('href'),'http://localhost');assert.equal(url.search,['/qc','/ai-insights'].includes(url.pathname)?'?source=SAMPLE':'');}
   assert.equal(label('담당자 접근 토큰'),null);assert.equal(container.querySelector('.obs-access-panel'),null);assert.equal(container.querySelector('button[aria-label="AI 챗봇 열기"]'),null);assert.doesNotMatch(container.textContent,/해양관측 지식 검색 AI/);assert.ok(requests.every(r=>r.url.startsWith('/api/qc-sample/')));
   if(entry==='/qc?source=SAMPLE'){
    await click(links.find(a=>a.textContent.includes('AI 분석 인사이트')));assert.equal(route.pathname,'/ai-insights');assert.equal(route.search,'?source=SAMPLE');assert.equal(container.querySelector('[data-testid="sample-ai-navigation-target"]')?.textContent,'AI route target only');
    await click([...container.querySelectorAll('nav a')].find(a=>a.textContent.includes('품질 현황')));assert.equal(route.pathname,'/qc');assert.equal(route.search,'?source=SAMPLE');assert.equal(container.querySelectorAll('.qs-shortcuts button').length,4);assert.ok(requests.every(r=>r.url.startsWith('/api/qc-sample/')));
   }
  }finally{await dispose();}
 }
});
