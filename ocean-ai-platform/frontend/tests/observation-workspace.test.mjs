import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import ts from 'typescript';
const {outputText}=ts.transpileModule(readFileSync(new URL('../src/data/observationWorkspace.ts',import.meta.url),'utf8'),{compilerOptions:{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022}});
const {storedDataState,stationPage,observationTrend}=await import(`data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`);
test('stored data flags use actual missing/QC counts and never imply operational normality',()=>{
  assert.equal(storedDataState(null).key,'checking');
  assert.equal(storedDataState({held_rows:2,missing_value_rows:1}).key,'missing');
  assert.equal(storedDataState({held_rows:2,missing_value_rows:0,source_qc_presence_rate:0}).key,'qc_absent');
  assert.equal(storedDataState({held_rows:2,missing_value_rows:0,source_qc_presence_rate:null}).label,'자료 보유');
});
test('pagination clamps a stale page after sea or search narrows the result, including empty data',()=>{
  assert.deepEqual(stationPage([1,2,3],8,2),{page:2,pages:2,rows:[3],first:3,last:3});
  assert.deepEqual(stationPage([],8),{page:1,pages:1,rows:[],first:0,last:0});
});
test('raw trend keeps zero and negative values, preserves gaps and shows oldest to newest',()=>{
  const result=observationTrend([{value_raw:'0',observed_time_raw:'03'},{value_raw:'',observed_time_raw:'02'},{value_raw:'-2',observed_time_raw:'01'}]);
  assert.deepEqual(result,[{time:'01',value:-2},{time:'02',value:null},{time:'03',value:0}]);
  for(const value_raw of [null,'NaN','Infinity','bad'])assert.equal(observationTrend([{value_raw}])[0].value,null);
});
