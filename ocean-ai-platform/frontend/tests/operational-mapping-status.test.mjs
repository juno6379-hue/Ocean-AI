import test from 'node:test';
import assert from 'node:assert/strict';
import {resolve} from 'node:path';
import {Window} from 'happy-dom';
import {compile,frontend} from './qc-sample-workspace-runtime.mjs';

const win=new Window({url:'http://localhost/data-lake'});
for(const name of ['window','document','HTMLElement','Element','Node','Event','MutationObserver'])globalThis[name]=name==='window'?win:win[name];
Object.defineProperty(globalThis,'navigator',{value:win.navigator,configurable:true});
globalThis.IS_REACT_ACT_ENVIRONMENT=true;
const React=await import('react'),{act}=React,{createRoot}=await import('react-dom/client');
const Status=(await import(compile(resolve(frontend,'components/OperationalMappingStatus.tsx')))).default;
const client=await import(compile(resolve(frontend,'api/client.ts')));
const originalGet=client.apiClient.get;

async function scenario(result,check){
 const node=document.createElement('div');document.body.append(node);const root=createRoot(node);
 client.apiClient.get=async()=>{if(result instanceof Error)throw result;return {data:result};};
 try{await act(async()=>{root.render(React.createElement(Status));await new Promise(resolve=>setTimeout(resolve,20));});
  await act(async()=>{await new Promise(resolve=>setTimeout(resolve,10));});check(node);
 }finally{await act(async()=>root.unmount());node.remove();client.apiClient.get=originalGet;await win.happyDOM.cancelAsync();}
}

const empty={enabled:false,mapping_version:'OPS-MDC-MAP-2.0',auto_approved_contracts:0,registered_bindings:0,
 first_timestamp_utc:null,last_timestamp_utc:null,variables:[]};
test('Shows exact operational contract/binding counts, scope and variable populations',async()=>{
 await scenario({...empty,enabled:true,auto_approved_contracts:3,registered_bindings:745445,
  first_timestamp_utc:'2026-07-08T06:42:00Z',last_timestamp_utc:'2026-07-09T06:41:00Z',variables:[{variable_code:'WIND_SPEED',rows:78159}]},node=>{
  assert.match(node.textContent,/3건/);assert.match(node.textContent,/745,445행/);assert.match(node.textContent,/WIND_SPEED.*78,159행/);
  assert.match(node.textContent,/2026-07-09T06:41:00Z/);assert.match(node.textContent,/학습·모델 승인 상태는 별도/);
 });
});
test('Empty registration is explicit and does not claim historical completion',async()=>{
 await scenario(empty,node=>{assert.match(node.textContent,/0건/);assert.match(node.textContent,/적재 없음/);assert.match(node.textContent,/전체 과거 자료 적재 완료를 뜻하지 않습니다/);});
});
test('An API failure is an error, not a false zero count',async()=>{
 await scenario(new Error('isolated failure'),node=>{assert.match(node.querySelector('[role="alert"]').textContent,/불러오지 못했습니다/);assert.doesNotMatch(node.textContent,/0건/);});
});
