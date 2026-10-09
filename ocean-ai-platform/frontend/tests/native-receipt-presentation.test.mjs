import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import ts from 'typescript';
const source=readFileSync(new URL('../src/data/nativeReceiptPresentation.ts',import.meta.url),'utf8');
const {outputText}=ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022}});
const {nativeReceiptPresentation:show}=await import(`data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`);
const base={state:'CALCULATED_NATIVE_CLOCK_DIFFERENCE',diagnostic_kind:'SOURCE_CLOCK_DIFFERENCE_NOT_OPERATIONAL_DELAY',
  approved:false,operational_delay:false,receipt_field_state:'PRESENT',raw_rows:100,comparable_pair_rows:90,
  difference_seconds:{min:-10,max:20,mean:0,p50:0,p95:10}};
test('measured zero and negative native differences stay numeric and do not become reception states',()=>{
  assert.equal(show(base).value,'평균 0초');
  assert.equal(show({...base,difference_seconds:{min:-10,max:-1,mean:-5,p50:-5,p95:-2}}).value,'평균 -5초');
  assert.match(show(base).title,/운영 지연 판정과 별도/);
});
test('absent receipt fields and uncomparable clocks do not fabricate zero latency',()=>{
  assert.equal(show({...base,state:'FIELD_ABSENT',receipt_field_state:'FIELD_ABSENT',difference_seconds:null}).value,'수신시각 필드 없음');
  assert.equal(show({...base,state:'NO_COMPARABLE_PAIRS',difference_seconds:null}).value,'비교 가능한 시각 없음');
  assert.equal(show({...base,state:'MIXED_CLOCK_REPRESENTATIONS',difference_seconds:null}).value,'시계 표현 혼재');
});
test('operational claims and impossible or nonfinite summaries cannot be displayed as measured values',()=>{
  for(const change of [{approved:true},{operational_delay:true},{comparable_pair_rows:0},{comparable_pair_rows:101},
    {difference_seconds:{...base.difference_seconds,mean:Infinity}},
    {difference_seconds:{...base.difference_seconds,p50:15,p95:10}},
    {difference_seconds:{...base.difference_seconds,mean:'0'}}]) {
    assert.equal(show({...base,...change}).value,'수신시각 집계 전');
  }
});
