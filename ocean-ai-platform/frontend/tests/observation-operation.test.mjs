import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import ts from 'typescript';
const {outputText}=ts.transpileModule(readFileSync(new URL('../src/data/observationWorkspace.ts',import.meta.url),'utf8'),{compilerOptions:{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022}});
const {validOperationEvidence,operatingState,operationSummary,observedAvailability}=await import(`data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`);
const end='2026-07-09 15:41:20';
const evidence={basis:'OBSERVATION_DIAGNOSTIC',policy_version:'diagnostic-v1',policy_hash:'a'.repeat(64),window_start:'2026-07-08 15:41:20',window_end:end,state:'NORMAL',channels_evaluated:5,channels_total:5,observed_grid_availability_percent:98.7,collection_rate:null,inspection_missing:true,qc_interpretation_missing:true};

test('a historical operation badge requires the same native cutoff and a versioned diagnostic policy',()=>{
  assert.equal(operatingState(evidence,end).state,'NORMAL');
  for(const change of [{state:'ERROR',basis:undefined},{basis:'SIMULATION'},{window_end:'2026-10-06 15:41:20'},{window_end:'2026-07-09 15:41:20.000001'},{policy_hash:undefined},{policy_version:''},{window_start:'2026-07-10 15:41:20'}])
    assert.equal(operatingState({...evidence,...change},end).state,'UNVERIFIED');
  assert.equal(validOperationEvidence({...evidence,window_end:'2026-07-09T15:41:20.000000'},end),true);
});

test('states need real evaluated channel evidence and a complete nonnegative fleet count',()=>{
  assert.equal(operatingState({...evidence,state:'WARNING'},end).label,'주의');
  assert.equal(operatingState({...evidence,state:'ABNORMAL'},end).label,'이상');
  for(const channels_evaluated of [0,8,-1,'5',null])assert.equal(operatingState({...evidence,channels_evaluated},end).state,'UNVERIFIED');
  const fleet={...evidence,normal:40,warning:15,abnormal:3,unclassified:3};
  assert.equal(operationSummary(fleet,61,end),fleet);
  for(const change of [{normal:41},{abnormal:-1},{unclassified:undefined},{warning:'15'},{basis:'SIMULATION'}])assert.equal(operationSummary({...fleet,...change},61,end),null);
});

test('inferred-grid availability remains separate from unknown receipt collection rate, including measured zero',()=>{
  assert.equal(observedAvailability(evidence,end),'98.7%');
  assert.equal(evidence.collection_rate,null);
  assert.equal(observedAvailability({...evidence,observed_grid_availability_percent:0},end),'0.0%');
  for(const value of [null,undefined,'98.7',-1,101,Infinity,NaN])assert.equal(observedAvailability({...evidence,observed_grid_availability_percent:value},end),'—');
  assert.equal(observedAvailability({...evidence,window_end:'2026-07-30 00:00:00'},end),'—');
});

test('an incomplete station cannot display a normal badge even if its payload claims NORMAL',()=>{
  assert.equal(operatingState({...evidence,channels_total:7},end).state,'UNVERIFIED');
  assert.equal(operatingState({...evidence,channels_total:7,state:'WARNING'},end).state,'WARNING');
});
