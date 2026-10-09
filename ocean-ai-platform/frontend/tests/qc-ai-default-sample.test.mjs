import test from 'node:test';
import assert from 'node:assert/strict';
import {resolve} from 'node:path';
import {Window} from 'happy-dom';
import {compile,frontend,apiFixture as qcFixture,json} from './qc-sample-workspace-runtime.mjs';
import {apiFixture as aiFixture} from './ai-insights-sample-runtime.mjs';
import {sampleFixture as qcPackets} from './qc-sample-fixtures.mjs';
import {aiFixture as aiPackets} from './ai-insights-sample-fixtures.mjs';

// Actual QC, AI, Layout and API-client components run with a closed fixture network.
// The source-mode marker never authorizes an operating workflow or database write.
const win=new Window({url:'http://localhost/qc'});
for(const name of ['window','document','HTMLElement','SVGElement','Element','Node','MouseEvent','KeyboardEvent','Event','CustomEvent','MutationObserver'])globalThis[name]=name==='window'?win:win[name];
Object.defineProperty(globalThis,'navigator',{value:win.navigator,configurable:true});
globalThis.getComputedStyle=win.getComputedStyle.bind(win);globalThis.IS_REACT_ACT_ENVIRONMENT=true;
win.HTMLElement.prototype.getBoundingClientRect=()=>new win.DOMRect(0,0,450,220);
globalThis.ResizeObserver=class{constructor(callback){this.callback=callback;}observe(target){this.callback([{target,contentRect:target.getBoundingClientRect()}]);}unobserve(){}disconnect(){}};
globalThis.requestAnimationFrame=callback=>setTimeout(()=>callback(performance.now()),0);globalThis.cancelAnimationFrame=clearTimeout;
const React=await import('react'),{act}=React,{createRoot}=await import('react-dom/client');
const {MemoryRouter,Routes,Route,useLocation,useNavigate}=await import('react-router-dom');
const QC=(await import(compile(resolve(frontend,'pages/QCCopilot.tsx')))).default;
const AI=(await import(compile(resolve(frontend,'pages/AIInsights.tsx')))).default;
const Layout=(await import(compile(resolve(frontend,'components/Layout.tsx')))).default;
const client=await import(compile(resolve(frontend,'api/client.ts')));
const mode=await import(compile(resolve(frontend,'data/workspaceMode.ts')));
let root,container,route,navigate,requests;
function Capture(){route=useLocation();navigate=useNavigate();return null;}
function isolatedAPI(){
 const qc=qcFixture(),ai=aiFixture();
 return {respond:async(url,init)=>{
  if(url.startsWith('/api/qc-sample/')||url.startsWith('/api/qc/'))return qc.respond(url,init);
  if(url.startsWith('/api/ai-insights-sample/'))return ai.respond(url,init);
  assert.equal(init.method||'GET','GET','Operating namespaces must remain read-only in this fixture');
  assert.equal(new URL(url,'http://localhost').searchParams.has('data_mode'),false);
  return url.startsWith('/api/stations?')?json([]):json({detail:'Isolated operating empty fixture'},404);
 }};
}
async function flush(){await act(async()=>{await new Promise(resolve=>setTimeout(resolve,20));});}
async function mount(initial,api=isolatedAPI()){
 requests=[];client.setOperatorToken('isolated-existing-operator-must-never-reach-sample');
 globalThis.fetch=async(url,init={})=>{requests.push({url:String(url),init});return api.respond(String(url),init);};
 container=document.createElement('div');document.body.append(container);root=createRoot(container);
 const pages=React.createElement(Routes,null,React.createElement(Route,{element:React.createElement(Layout)},
  React.createElement(Route,{path:'/qc',element:React.createElement(QC)}),
  React.createElement(Route,{path:'/copilot',element:React.createElement(QC)}),
  React.createElement(Route,{path:'/ai-insights',element:React.createElement(AI)})));
 await act(async()=>{root.render(React.createElement(MemoryRouter,{initialEntries:[initial]},React.createElement(Capture),pages));await new Promise(resolve=>setTimeout(resolve,20));});await flush();
}
async function dispose(){if(root)await act(async()=>root.unmount());container?.remove();root=null;client.clearOperatorToken();await win.happyDOM.cancelAsync();await win.happyDOM.waitUntilComplete();}
const control=text=>container.querySelector('[aria-label="'+text+'"]');
const nav=path=>[...container.querySelectorAll('aside nav a')].find(a=>new URL(a.getAttribute('href'),'http://localhost').pathname===path);
async function click(node){assert.ok(node,'Expected navigation control must render');await act(async()=>{node.dispatchEvent(new MouseEvent('click',{bubbles:true}));await new Promise(resolve=>setTimeout(resolve,20));});await flush();}
async function change(node,value){assert.ok(node,'Expected source selector must render');await act(async()=>{Object.getOwnPropertyDescriptor(Object.getPrototypeOf(node),'value').set.call(node,value);node.dispatchEvent(new Event('change',{bubbles:true}));await new Promise(resolve=>setTimeout(resolve,20));});await flush();}
function assertNoSampleRequests(){assert.ok(requests.length>0);assert.ok(requests.every(r=>!r.url.includes('-sample/')));assert.equal(container.querySelector('.qs-banner'),null);assert.equal(container.querySelector('.ais-banner'),null);}
function assertSampleOnly(){
 assert.ok(requests.length>0);
 for(const r of requests){
  const qc=r.url.startsWith('/api/qc-sample/'),ai=r.url.startsWith('/api/ai-insights-sample/');assert.ok(qc||ai,'The first render must not start an operating request');
  const headers=new Headers(r.init.headers),packets=qc?qcPackets:aiPackets;
  assert.equal(headers.has('Authorization'),false);assert.equal(headers.has('Cookie'),false);assert.equal(r.init.credentials,'omit');assert.equal(r.init.redirect,'error');
  assert.equal(new URL(r.url,'http://localhost').search,'');
  if(!r.url.endsWith('/context'))assert.equal(headers.get(qc?'X-QC-Sample-Token':'X-AI-Sample-Token'),r.url.endsWith('/sessions')?packets.context.bootstrap_token:packets.session.session_token);
 }
 assert.equal(control('담당자 접근 토큰'),null);assert.equal(container.querySelector('button[aria-label="AI 챗봇 열기"]'),null);
 assert.equal(win.localStorage.length,0);assert.equal(win.sessionStorage.length,0);
}

test('Fresh QC, copilot and AI entry selects SAMPLE before the first request and canonicalizes the URL without live access',async()=>{
 for(const entry of ['/qc','/copilot','/ai-insights'])try{
  await mount(entry);assert.equal(route.pathname,entry);assert.equal(route.search,'?source=SAMPLE');assert.equal(control(entry==='/ai-insights'?'AI 자료 경로':'QC 자료 경로').value,'SAMPLE');assertSampleOnly();
  assert.equal(container.querySelectorAll(entry==='/ai-insights'?'.ais-kpis article':'.qs-metrics article').length,entry==='/ai-insights'?5:6);
 }finally{await dispose();}
});

test('Actual sidebar moves between both default sample workspaces using distinct tokens without leaking sample mode to other menus',async()=>{
 try{
  await mount('/qc');assertSampleOnly();await click(nav('/ai-insights'));assert.equal(route.search,'?source=SAMPLE');assert.equal(control('AI 자료 경로').value,'SAMPLE');assertSampleOnly();
  assert.ok(requests.some(r=>r.url.startsWith('/api/qc-sample/')));assert.ok(requests.some(r=>r.url.startsWith('/api/ai-insights-sample/')));
  await click(nav('/qc'));assert.equal(control('QC 자료 경로').value,'SAMPLE');assert.equal(route.search,'?source=SAMPLE');assertSampleOnly();
  for(const link of container.querySelectorAll('aside nav a')){const url=new URL(link.getAttribute('href'),'http://localhost');assert.equal(url.search,['/qc','/ai-insights'].includes(url.pathname)?'?source=SAMPLE':'');}
 }finally{await dispose();}
});

test('Explicit QC operating selection survives remount and sidebar round trip instead of returning to default samples',async()=>{
 let reloadURL;
 try{
  await mount('/qc');await change(control('QC 자료 경로'),'REGISTERED');assert.deepEqual(Object.fromEntries(new URLSearchParams(route.search)),{source:'REGISTERED',data_mode:'LIVE'});reloadURL=route.pathname+route.search;
 }finally{await dispose();}
 try{
  await mount(reloadURL);assert.equal(control('QC 자료 경로').value,'REGISTERED');assertNoSampleRequests();
  await click(nav('/ai-insights'));assert.equal(new URLSearchParams(route.search).get('data_mode'),'LIVE');assert.match(container.textContent,/AI 분석 인사이트/);assertNoSampleRequests();
  await click(nav('/qc'));assert.equal(control('QC 자료 경로').value,'REGISTERED');assert.equal(new URLSearchParams(route.search).get('data_mode'),'LIVE');assertNoSampleRequests();
  assert.ok(requests.every(r=>!new URL(r.url,'http://localhost').searchParams.has('data_mode')));
 }finally{await dispose();}
});

test('Explicit AI operating selection survives remount and preserves LIVE on the QC and AI sidebar links',async()=>{
 let reloadURL;
 try{await mount('/ai-insights');await change(control('AI 자료 경로'),'REGISTERED');assert.equal(route.search,'?data_mode=LIVE');reloadURL=route.pathname+route.search;}finally{await dispose();}
 try{
  await mount(reloadURL);assert.match(container.textContent,/AI 분석 인사이트/);assertNoSampleRequests();
  await click(nav('/qc'));assert.equal(new URLSearchParams(route.search).get('data_mode'),'LIVE');assert.equal(control('QC 자료 경로').value,'REGISTERED');assertNoSampleRequests();
  await click(nav('/ai-insights'));assert.equal(new URLSearchParams(route.search).get('data_mode'),'LIVE');assertNoSampleRequests();
  for(const link of container.querySelectorAll('aside nav a')){const url=new URL(link.getAttribute('href'),'http://localhost');assert.equal(url.searchParams.has('data_mode'),['/qc','/ai-insights'].includes(url.pathname));assert.notEqual(url.searchParams.get('source'),'SAMPLE');}
 }finally{await dispose();}
});

test('Existing native source, period, cutoff, station and item URL context remains operating context with exact original values',async()=>{
 const cases=[
  '/qc?source=GD_OBS_ST_MONTHLY&station=DT_0028&item=WATER_TEMP&from=2026-06&to=2026-07&as_of_day=2026-07-09&as_of_time=15%3A41%3A20&sea=%EC%84%9C%ED%95%B4',
  '/qc?date_from=2026-07-09+00%3A00%3A00&date_to=2026-07-09+15%3A41%3A20&flag=9&preset=custom',
  '/copilot?station=DT_0028&item=WATER_TEMP',
  '/ai-insights?source=GD_OBS_ST_MONTHLY&from=2026-06&to=2026-07&station=DT_0028&item=WATER_TEMP&network=%EC%A1%B0%EC%9C%84%EA%B4%80%EC%B8%A1%EC%86%8C&sea=%EC%84%9C%ED%95%B4',
 ];
 for(const entry of cases)try{
  const expected=new URL(entry,'http://localhost').searchParams;await mount(entry);const actual=new URLSearchParams(route.search);for(const [key,value] of expected)assert.equal(actual.get(key),value,key+' must not be replaced by sample defaults');assert.equal(actual.get('data_mode'),'LIVE');assertNoSampleRequests();
  if(entry.startsWith('/ai-insights')){const url=new URL(requests.find(r=>r.url.startsWith('/api/lake/monitoring?')).url,'http://localhost');assert.equal(url.searchParams.get('source'),'GD_OBS_ST_MONTHLY');assert.equal(url.searchParams.get('from_month'),'2026-06');assert.equal(url.searchParams.get('to_month'),'2026-07');assert.equal(url.searchParams.get('station'),'DT_0028');assert.equal(url.searchParams.get('item'),'WATER_TEMP');}
 }finally{await dispose();}
});

test('Explicit SAMPLE wins over LIVE and dirty native query context without initiating an operating source request',async()=>{
 for(const path of ['/qc','/ai-insights'])try{
  await mount(path+'?source=SAMPLE&data_mode=LIVE&station=DT_0028&item=WATER_TEMP&as_of_day=2026-07-09&from=2023-01&sea=서해');assert.equal(route.search,'?source=SAMPLE');assertSampleOnly();
 }finally{await dispose();}
});

test('Default sample replace and explicit live selection preserve browser history and reload boundaries',async()=>{
 try{
  await mount('/qc');assert.equal(route.search,'?source=SAMPLE');await change(control('QC 자료 경로'),'REGISTERED');assert.equal(new URLSearchParams(route.search).get('data_mode'),'LIVE');
  await act(async()=>navigate(-1));await flush();assert.equal(route.search,'?source=SAMPLE');assert.equal(control('QC 자료 경로').value,'SAMPLE');
  await act(async()=>navigate(1));await flush();assert.equal(new URLSearchParams(route.search).get('data_mode'),'LIVE');assert.equal(control('QC 자료 경로').value,'REGISTERED');assert.equal(container.querySelector('.qs-banner'),null);
 }finally{await dispose();}
});

test('Mode resolution preserves empty raw-QC literals and unknown source queries; canonicalization never discards explicit live context',()=>{
 assert.equal(mode.workspaceDataMode(new URLSearchParams()),'SAMPLE');
 for(const key of mode.workspaceContextKeys){const query=new URLSearchParams({[key]:''});assert.equal(mode.workspaceDataMode(query),'LIVE',key);const canonical=mode.canonicalWorkspaceSearch(query);assert.equal(canonical.has(key),true);assert.equal(canonical.get(key),'');assert.equal(canonical.get('data_mode'),'LIVE');}
 const unknown=new URLSearchParams('source=INVALID_NATIVE_SOURCE&qc_literal=&qc_literal_is_null=false&station=DT_0028');const copy=unknown.toString();assert.equal(mode.workspaceDataMode(unknown),'LIVE');assert.equal(mode.canonicalWorkspaceSearch(unknown).get('source'),'INVALID_NATIVE_SOURCE');assert.equal(unknown.toString(),copy,'Canonicalization must not mutate the caller query');
 const conflict=new URLSearchParams('source=SAMPLE&data_mode=LIVE&qc_literal=&from=2023-01');assert.equal(mode.workspaceDataMode(conflict),'SAMPLE');assert.equal(mode.canonicalWorkspaceSearch(conflict).toString(),'source=SAMPLE');
 for(const path of ['/qc','/ai-insights']){const url=new URL(mode.liveWorkspaceHref(path),'http://localhost');assert.equal(url.pathname,path);assert.equal(url.searchParams.get('data_mode'),'LIVE');assert.equal(mode.workspaceDataMode(url.searchParams),'LIVE');}
});

test('Actual operating AI next-task QC link preserves LIVE and native period instead of opening default sample',async()=>{
 for(const initial of ['/ai-insights?data_mode=LIVE','/ai-insights?source=GD_OBS_ST_MONTHLY&from=2026-06&to=2026-07&data_mode=LIVE'])try{
  await mount(initial);assertNoSampleRequests();const links=[...container.querySelectorAll('nav[aria-label="다음 업무"] a')],qc=links.find(link=>new URL(link.getAttribute('href'),'http://localhost').pathname==='/qc');assert.ok(qc,'The actual AI next-task QC link must render');const target=new URL(qc.getAttribute('href'),'http://localhost');assert.equal(target.searchParams.get('data_mode'),'LIVE');
  if(initial.includes('source=')){assert.equal(target.searchParams.get('source'),'GD_OBS_ST_MONTHLY');assert.equal(target.searchParams.get('from'),'2026-06');assert.equal(target.searchParams.get('to'),'2026-07');}
  for(const link of links){const url=new URL(link.getAttribute('href'),'http://localhost');assert.equal(url.searchParams.has('data_mode'),['/qc','/ai-insights'].includes(url.pathname));}
  await click(qc);assert.equal(route.pathname,'/qc');assert.equal(new URLSearchParams(route.search).get('data_mode'),'LIVE');assertNoSampleRequests();
 }finally{await dispose();}
});
