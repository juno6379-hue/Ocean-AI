import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import ts from 'typescript';
const {outputText}=ts.transpileModule(readFileSync(new URL('../src/data/observationWorkspace.ts',import.meta.url),'utf8'),{compilerOptions:{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022}});
const {filterObservationStations,summarizeVisibleOperations,collectionPresentation}=await import(`data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`);
const end='2026-07-09 15:41:20',start='2026-07-08 15:41:20',source='GD_OBS_ST_MONTHLY',snapshot='validation-test';
const policy={basis:'OBSERVATION_DIAGNOSTIC',policy_version:'diagnostic-v1',policy_hash:'a'.repeat(64),window_start:start,window_end:end};
function row(id,held=10,expected=10,state='NORMAL',extra={}){
  const channel={...policy,station_code:id,item_code:'WATER_TEMP',source_group:source,
    depth_step:null,depth_from:null,depth_to:null,state,
    observed_grid:{held_slots:held,expected_slots:expected,availability_percent:expected?100*held/expected:null,denominator:'INFERRED_OBSERVATION_GRID'}};
  const operation={...policy,station_code:id,state,channels:[channel],channels_total:1,
    channels_evaluated:state==='UNVERIFIED'?0:1,collection_rate:null,
    observed_grid_availability_percent:expected?100*held/expected:null,
    observed_grid:{held_slots:held??0,expected_slots:expected??0,eligible_channels:expected==null?0:1,
      excluded_channels:expected==null?1:0,denominator:'INFERRED_OBSERVATION_GRID'}};
  return {id,name:'인천 '+id,source,snapshot,operation,time:'2026-07-09 15:41:00',
    refRegistered:true,network_type:'조위관측소',sea_area:'서해',net:'조위관측소',sea:'서해',...extra};
}
function packet(rows){
  const count={normal:0,warning:0,abnormal:0,unclassified:0};
  for(const value of rows)count[({NORMAL:'normal',WARNING:'warning',ABNORMAL:'abnormal'})[value.operation.state]||'unclassified']++;
  return {source,snapshot,totals:{stations:rows.length},stations:rows.map(value=>({station_code:value.id,operation:value.operation})),
    operation_summary:{...policy,...count,stations_total:rows.length,collection_rate:null}};
}
const ids=rows=>rows.map(value=>value.id);

test('classification scopes distinguish absent metadata, unassigned registered fields and literal unknown sea',()=>{
  const rows=[row('A'),row('B',10,10,'NORMAL',{refRegistered:false,network_type:null,sea_area:null,net:'원천망',sea:'해역정보없음'}),
    row('C',10,10,'NORMAL',{network_type:null,sea_area:null}),row('D',10,10,'NORMAL',{sea_area:'미상'}),
    row('E',10,10,'NORMAL',{refRegistered:null,network_type:null,sea_area:null}),
    row('F',10,10,'NORMAL',{network_type:'HF-Radar',net:'해수유동관측소 (HF-Radar)',sea_area:'남해'})];
  assert.deepEqual(ids(filterObservationStations(rows,{},end)),['A','B','C','D','E','F']);
  assert.deepEqual(ids(filterObservationStations(rows,{network:'__UNREGISTERED__'},end)),['B']);
  assert.deepEqual(ids(filterObservationStations(rows,{sea:'__UNASSIGNED__'},end)),['C']);
  assert.deepEqual(ids(filterObservationStations(rows,{network:'__UNREGISTERED__',sea:'__UNASSIGNED__'},end)),['B']);
  assert.deepEqual(ids(filterObservationStations(rows,{network:'__UNREGISTERED__',sea:'서해'},end)),[]);
  assert.deepEqual(ids(filterObservationStations(rows,{sea:'미상'},end)),['D']);
  assert.deepEqual(ids(filterObservationStations(rows,{network:'HF-Radar'},end)),['F']);
  assert.deepEqual(ids(filterObservationStations(rows,{network:'해수유동관측소 (HF-Radar)'},end)),[]);
});

test('state and search filtering uses the same source, exact cutoff, station and channel policy',()=>{
  const normal=row('DT_0001'),warning=row('DT_0002',9,10,'WARNING'),bad=row('DT_0003',1,10,'ABNORMAL');
  const wrongCutoff=structuredClone(normal);wrongCutoff.id='D';wrongCutoff.operation.window_end='2026-07-09 15:41:20.000001';
  const wrongHash=structuredClone(normal);wrongHash.operation.policy_hash='b'.repeat(64);
  const wrongSource={...normal,source:'LEGACY'};
  assert.deepEqual(ids(filterObservationStations([normal,warning,bad],{sea:'서해',state:'WARNING',search:'  dt_0002  '},end)),['DT_0002']);
  for(const invalid of [wrongCutoff,wrongHash,wrongSource]){
    assert.equal(filterObservationStations([invalid],{state:'NORMAL'},end).length,0);
    assert.equal(filterObservationStations([invalid],{state:'UNVERIFIED'},end).length,1);
  }
  assert.equal(filterObservationStations([normal],{state:'NORMAL'},'2026-07-09 15:41:20.000001').length,0);
});

test('newest sorting preserves native microseconds, stable ties and the input collection',()=>{
  const rows=[row('A',10,10,'NORMAL',{time:'2026-07-09 15:41:00.000001'}),row('B',10,10,'NORMAL',{time:'2026-07-09T15:41:00.000002'}),
    row('C',10,10,'NORMAL',{time:'2026-07-09 15:41:00.000002'}),row('D',10,10,'NORMAL',{time:'2026-07-09 15:42:00'}),
    row('E',10,10,'NORMAL',{time:'2026-02-30 15:41:00'})];
  assert.deepEqual(ids(filterObservationStations(rows,{},end,true)),['B','C','A','D','E']);
  assert.deepEqual(ids(rows),['A','B','C','D','E']);
});

test('visible fleet counts and availability sum raw grid counts instead of averaging station rates',()=>{
  const rows=[row('A',10,10),row('B',1,10,'ABNORMAL'),row('C',90,90)];
  const summary=summarizeVisibleOperations(rows,packet(rows),end);
  assert.deepEqual([summary.normal,summary.warning,summary.abnormal,summary.unclassified],[2,0,1,0]);
  assert.deepEqual(summary.scope_station_codes,['A','B','C']);
  assert.equal(summary.observed_grid.held_slots,101);
  assert.equal(summary.observed_grid.expected_slots,110);
  assert.equal(summary.observed_grid_availability_percent,100*101/110);
  assert.equal(collectionPresentation(summary,end).value,'91.8%');
  const onlyBad=filterObservationStations(rows,{state:'ABNORMAL'},end);
  const narrowed=summarizeVisibleOperations(onlyBad,packet(rows),end);
  assert.equal(narrowed.stations_total,1);assert.equal(narrowed.normal,0);assert.equal(narrowed.abnormal,1);
  assert.equal(collectionPresentation(narrowed,end).value,'10.0%');
  assert.equal(narrowed.collection_rate,null);
});

test('empty filtered scopes stay empty without leaking selected or full-fleet rates',()=>{
  const rows=[row('A'),row('B',1,10,'ABNORMAL')];
  const visible=filterObservationStations(rows,{search:'존재하지않는 관측소'},end);
  const summary=summarizeVisibleOperations(visible,packet(rows),end);
  assert.equal(visible.find(value=>value.id==='A'),undefined);
  assert.deepEqual([summary.normal,summary.warning,summary.abnormal,summary.unclassified],[0,0,0,0]);
  assert.equal(summary.stations_total,0);assert.equal(summary.observed_grid.expected_slots,0);
  assert.equal(summary.observed_grid_availability_percent,null);assert.equal(collectionPresentation(summary,end).value,'—');
});

test('scope projection rejects unknown IDs, duplicate rows, foreign source or snapshot and invalid base cutoff',()=>{
  const a=row('A'),base=packet([a]);
  for(const rows of [[{...a,id:'B'}],[a,a],[{...a,source:'LEGACY'}],[{...a,snapshot:'other'}]])
    assert.equal(summarizeVisibleOperations(rows,base,end),null);
  for(const change of [{policy_hash:undefined},{window_end:'2026-07-30 00:00:00'},{window_end:'2026-02-30 15:41:20'},{normal:2}])
    assert.equal(summarizeVisibleOperations([a],{...base,operation_summary:{...base.operation_summary,...change}},end),null);
  const changed=structuredClone(a);changed.operation.policy_hash='b'.repeat(64);
  const summary=summarizeVisibleOperations([changed],base,end);
  assert.equal(summary.unclassified,1);assert.equal(summary.normal,0);
  assert.equal(summary.observed_grid.excluded_stations,1);assert.equal(collectionPresentation(summary,end).value,'—');
});

test('grid evidence requires exact channel sums, unique typed depths, policy and native cutoff',()=>{
  const a=row('A');
  const variants=[{observed_grid_availability_percent:99},{observed_grid:{...a.operation.observed_grid,held_slots:9}},
    {channels:[...a.operation.channels,...a.operation.channels],channels_total:2,channels_evaluated:2},
    {window_end:'2026-07-09 15:41:20.000001'},
    {channels:[{...a.operation.channels[0],source_group:'OTHER'}],source},
    {channels:[{...a.operation.channels[0],window_start:'2026-07-07 15:41:20'}]}];
  for(const value of variants)assert.equal(collectionPresentation({...a.operation,...value},end).value,'—');
  const sourceWrong={...a.operation,source:'OTHER'};
  assert.equal(collectionPresentation(sourceWrong,end).value,'—');
});

test('zero numerator is a measured grid estimate and excluded channels remain disclosed',()=>{
  const zero=row('ZERO',0,10,'ABNORMAL');
  assert.deepEqual(collectionPresentation(zero.operation,end),{label:'수집률 (추정)',value:'0.0%',
    title:'원천 관측시각 격자 0 / 추정 예정 10건 · 1/1개 항목·수심 · 실제 수신율은 근거 없음',
    note:'원천 관측시각 격자 0 / 추정 예정 10건 · 1/1개 항목·수심 · 실제 수신율은 근거 없음',
    kind:'INFERRED_GRID',estimated:true,numerator:0,denominator:10});
  const partial=row('PARTIAL',10,10,'WARNING');partial.operation.channels[0].state='NORMAL';
  const excluded={...partial.operation.channels[0],item_code:'SALINITY',state:'UNVERIFIED',
    observed_grid:{held_slots:null,expected_slots:null,availability_percent:null,denominator:'INFERRED_OBSERVATION_GRID'}};
  partial.operation.channels.push(excluded);partial.operation.channels_total=2;partial.operation.observed_grid.excluded_channels=1;
  const shown=collectionPresentation(partial.operation,end);
  assert.equal(shown.value,'100.0%');assert.match(shown.note,/1\/2개 항목·수심/);
  const missing=row('MISSING',null,null,'UNVERIFIED');
  assert.equal(collectionPresentation(missing.operation,end).value,'—');
});

test('an unsubstantiated receipt number cannot masquerade as the inferred grid rate',()=>{
  const operation=row('A').operation;
  const shown=collectionPresentation({...operation,collection_rate:98.7},end);
  assert.equal(shown.label,'수집률 (추정)');assert.equal(shown.value,'100.0%');
  const receipt={basis:'RECEIPT_LOG',source,station_code:'A',window_start:start,window_end:end,
    received_slots:0,expected_slots:20,plan_hash:'b'.repeat(64),log_hash:'c'.repeat(64)};
  const verified={...operation,collection_rate:0,collection_evidence:receipt};
  assert.equal(collectionPresentation(verified,end).kind,'RECEIPT');
  assert.equal(collectionPresentation(verified,end).value,'0.0%');
  for(const change of [{source:'OTHER'},{station_code:'B'},{window_end:'2026-07-09 15:41:20.000001'},{expected_slots:0},{plan_hash:null}])
    assert.equal(collectionPresentation({...verified,collection_evidence:{...receipt,...change}},end).kind,'INFERRED_GRID');
});
