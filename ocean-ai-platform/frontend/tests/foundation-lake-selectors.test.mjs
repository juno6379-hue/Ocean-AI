import test from 'node:test';
import assert from 'node:assert/strict';
import {resolve} from 'node:path';
import {Window} from 'happy-dom';
import {compile,frontend,json} from './qc-sample-workspace-runtime.mjs';

const win=new Window({url:'http://localhost/data-lake'});
for(const name of ['window','document','HTMLElement','Element','Node','MouseEvent','Event','MutationObserver'])globalThis[name]=name==='window'?win:win[name];
Object.defineProperty(globalThis,'navigator',{value:win.navigator,configurable:true});
globalThis.IS_REACT_ACT_ENVIRONMENT=true;
const React=await import('react'),{act}=React,{createRoot}=await import('react-dom/client');
const {MemoryRouter}=await import('react-router-dom');
const Foundation=(await import(compile(resolve(frontend,'components/FoundationLake.tsx')))).default;
const client=await import(compile(resolve(frontend,'api/client.ts')));
const originalGet=client.apiClient.get;
let root,container,requests;
const snapshot='selector-fixture';
const stationRow=(code,name)=>({station_code:code,station_name:name,held_rows:20});
const itemRow=(station,code,extra={})=>({source_group:'GR_OBS_ST',station_code:station,item_code:code,item_labels:'\uFFFD',month:'2026-07-01',held_rows:20,...extra});
function response(url,config={}){
 const p=config.params||{};
 if(url.endsWith('/foundation/summary'))return {verified_monthly_files:99,conversion:{state:'COMPLETE'},validation:{baseline_files:6149,new_monthly_verified_files:99,at:'fixture'},monthly_groups:[]};
 if(url.endsWith('/stations'))return [{station_id:'DT_0001',name:'인천'},{station_id:'DT_0002',name:'평택'},{station_id:'DB_ONLY',name:'보유자료 없음'}];
 if(url.endsWith('/lake/summary'))return {source:p.source,from_month:p.from_month,to_month:p.to_month,snapshot,stations:p.from_month==='2026-07'?[stationRow('DT_0001','\uFFFD'),stationRow('DT_0002','평택'),{...stationRow('EMPTY','빈 관측소'),held_rows:0}]:[]};
 if(url.includes('/lake/stations/')){
  const station=decodeURIComponent(url.split('/').at(-1));
  return {source:p.source,station_code:station,snapshot,months:station==='DT_0001'?
   [itemRow(station,'WATER_TEMP'),itemRow(station,'SALINITY'),itemRow(station,'WATER_TEMP',{depth_from:'5'}),
    ...['GNSS_X','GNSS_Y','GNSS_Z','VOLTAGE','BATT_V','PITCH','BUOY_INNER_TEMP','CUSTOM_UNKNOWN'].map(code=>itemRow(station,code,{item_labels:'수온'})),
    itemRow(station,'OLD',{month:'2026-06-01'}),itemRow(station,'OTHER_SOURCE',{source_group:'GD_OBS_BU'}),
    itemRow('DT_0002','OTHER_STATION'),itemRow(station,'EMPTY',{held_rows:0})]:[itemRow(station,'WIND_SPEED')]};
 }
 if(url.endsWith('/foundation/observations'))return {...p,returned_rows:1,rows:[{OBS_POST_ID:p.station,OBS_ITEM_CODE:p.item,OBS_TIME:'2026-07-01 00:00:00',OBS_VALUE:'23.94'}]};
 if(url.endsWith('/foundation/channels'))return {snapshot,channels:[]};
 throw new Error('Unexpected isolated GET '+url);
}
async function flush(){await act(async()=>{await new Promise(resolve=>setTimeout(resolve,15));});}
async function mount(entry='/data-lake?source=GR_OBS_ST&from=2026-07&to=2026-07&station=DT_0001&item=WATER_TEMP',hook){
 requests=[];globalThis.fetch=async()=>json({detail:'No technical-review fixture'},404);
 client.apiClient.get=async(url,config={})=>{requests.push({url,config});return {data:hook?await hook(url,config):response(url,config)};};
 container=document.createElement('div');document.body.append(container);root=createRoot(container);
 await act(async()=>{root.render(React.createElement(MemoryRouter,{initialEntries:[entry]},React.createElement(Foundation)));});
 await flush();await flush();
}
async function dispose(){await act(async()=>root?.unmount());container?.remove();root=null;client.apiClient.get=originalGet;await win.happyDOM.cancelAsync();}
const station=()=>container.querySelector('select[aria-label="관측소"]');
const item=()=>container.querySelector('select[aria-label="항목"]');
const query=()=>[...container.querySelectorAll('button')].find(button=>button.textContent==='원천·검증 조회');
const codes=node=>[...node.options].map(option=>option.value).filter(Boolean);
async function change(node,value){await act(async()=>{
 const setter=Object.getOwnPropertyDescriptor(node.tagName==='INPUT'?win.HTMLInputElement.prototype:win.HTMLSelectElement.prototype,'value').set;
 setter.call(node,value);node.dispatchEvent(new Event('input',{bubbles:true}));node.dispatchEvent(new Event('change',{bubbles:true}));
});await flush();}

test('Deep link is retained in real select controls; only positive held stations/items in the exact source/month are offered',async()=>{
 try{
  await mount();assert.equal(station().tagName,'SELECT');assert.equal(item().tagName,'SELECT');
  assert.deepEqual(codes(station()).sort(),['DT_0001','DT_0002']);assert.equal(station().value,'DT_0001');
  assert.match(station().selectedOptions[0].textContent,/인천.*DT_0001/);
  assert.deepEqual(codes(item()).sort(),['SALINITY','WATER_TEMP']);assert.equal(item().value,'WATER_TEMP');
  assert.match(item().selectedOptions[0].textContent,/수온.*WATER_TEMP/);assert.equal(query().disabled,false);
  await act(async()=>query().click());await flush();
  const raw=requests.find(row=>row.url.endsWith('/foundation/observations'));
  assert.deepEqual(raw.config.params,{source:'GR_OBS_ST',month:'202607',station:'DT_0001',item:'WATER_TEMP',limit:100});
  assert.match(container.textContent,/23.94/);
 }finally{await dispose();}
});

test('Changing station clears the old item/result and loads only the new station items',async()=>{
 try{
  await mount();await act(async()=>query().click());await flush();
  await change(station(),'DT_0002');assert.equal(item().value,'');assert.deepEqual(codes(item()),['WIND_SPEED']);
  assert.equal(query().disabled,true);assert.doesNotMatch(container.textContent,/23.94/);
  await change(item(),'WIND_SPEED');assert.equal(query().disabled,false);
 }finally{await dispose();}
});

test('Changing month/source resets dependent selections; empty held month and absent source disable querying',async()=>{
 try{
  await mount();await change(container.querySelector('input[type="month"]'),'2026-06');
  assert.deepEqual(codes(station()),[]);assert.deepEqual(codes(item()),[]);assert.equal(query().disabled,true);
  assert.match(station().textContent,/보유 관측소 없음/);
  await change(container.querySelector('select:not([aria-label])'),'');assert.equal(station().disabled,true);
  assert.match(station().textContent,/원천을 먼저 선택/);
 }finally{await dispose();}
});

test('A late response for a former station cannot replace the current item choices',async()=>{
 let release;
 try{
  await mount(undefined,async(url,config)=>{
   if(url.endsWith('/lake/stations/DT_0001'))return new Promise(resolve=>{release=()=>resolve(response(url,config));});
   return response(url,config);
  });
  assert.equal(item().disabled,true);await change(station(),'DT_0002');assert.deepEqual(codes(item()),['WIND_SPEED']);
  await act(async()=>release());await flush();assert.deepEqual(codes(item()),['WIND_SPEED']);assert.equal(station().value,'DT_0002');
 }finally{await dispose();}
});

test('Wrong snapshot or failed station request never enables a query using old or invented choices',async()=>{
 try{
  await mount(undefined,(url,config)=>{const value=response(url,config);return url.includes('/lake/stations/')?{...value,snapshot:'different'}:value;});
  assert.equal(item().disabled,true);assert.equal(query().disabled,true);assert.match(container.textContent,/항목 목록 조회 실패/);
 }finally{await dispose();}
 try{
  await mount(undefined,(url,config)=>{if(url.endsWith('/lake/summary'))throw new Error('offline');return response(url,config);});
  assert.equal(station().disabled,true);assert.equal(query().disabled,true);assert.match(container.textContent,/관측소 목록 조회 실패/);
 }finally{await dispose();}
});

test('Excluded GNSS deep links cannot select a hidden item or initiate raw queries',async()=>{
 for(const code of ['GNSS_X','GNSS_Y','GNSS_Z'])try{
  await mount('/data-lake?source=GR_OBS_ST&from=2026-07&to=2026-07&station=DT_0001&item='+code);
  assert.equal(station().value,'DT_0001');assert.equal(item().value,'');assert.equal(query().disabled,true);
  assert.deepEqual(codes(item()).sort(),['SALINITY','WATER_TEMP']);
  assert.equal(requests.some(row=>row.url.endsWith('/foundation/observations')),false);
 }finally{await dispose();}
});

test('A station with only position/equipment codes has no selectable marine item',async()=>{
 try{
  await mount(undefined,(url,config)=>{
   const value=response(url,config);
   return url.includes('/lake/stations/')?{...value,months:['GNSS_X','GNSS_Y','GNSS_Z','VOLTAGE'].map(code=>itemRow('DT_0001',code))}:value;
  });
  assert.deepEqual(codes(item()),[]);assert.equal(item().disabled,true);assert.equal(query().disabled,true);
  assert.match(item().textContent,/해양 관측항목 없음/);
 }finally{await dispose();}
});

test('Display scope keeps marine/weather codes and instrument variants but never admits unknown or equipment codes',async()=>{
 const {isMarineObservationItem}=await import(compile(resolve(frontend,'data/marineObservationItems.ts')));
 for(const code of ['WATER_TEMP','SALINITY','TIDE_LEVEL_MIROS','TIDE_LEVEL_VEGA_2','WIND_SPEED','AIR_PRES2','CURRENT_SPEED2','TURBIDITY','SIGNIFI_WAVE_HEIGHT','MOSE_HF_WAVE_DIRECT','SBD_WATER_TEMP_05'])assert.equal(isMarineObservationItem(code),true,code);
 for(const code of ['GNSS_X','GNSS_Y','GNSS_Z','VOLTAGE','WATER_VOLTAGE','HEADING','PITCH','ROLL','BUOY_INNER_TEMP','TEMP_BAT_RM','WATER_TEMP_STATUS','UNCLASSIFIED',''])assert.equal(isMarineObservationItem(code),false,code);
});
