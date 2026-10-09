import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import ts from 'typescript';
const source=readFileSync(new URL('../src/data/metricPresentation.ts',import.meta.url),'utf8');
const {outputText}=ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022}});
const {percentMetric,countMetric,literalMetric,gridPercent,qcPresencePercent,validMetricCompletion}=await import(`data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`);

test('an observed zero rate is numeric only when a real evaluation denominator exists',()=>{
  assert.equal(percentMetric(0,100),'0.0%');
  assert.equal(percentMetric(null,100),'필요입력 없음');
  assert.equal(percentMetric(0,0),'평가대상 없음');
  assert.equal(percentMetric(null,0),'평가대상 없음');
  assert.equal(percentMetric(0,null),'필요입력 없음');
});
test('nonfinite, string, negative and out-of-range rates cannot appear as diagnostic numbers',()=>{
  for(const value of [NaN,Infinity,'0',-1,101]) assert.equal(percentMetric(value,100),'필요입력 없음');
  assert.equal(percentMetric(50,-1),'필요입력 없음');
  assert.equal(countMetric(null),'필요입력 없음');
  assert.equal(countMetric(0),'0');
});
test('QC literal presentation preserves NULL, empty, padding and textual NULL separately',()=>{
  assert.equal(literalMetric(null),'NULL');
  assert.equal(literalMetric(''),'빈 문자열');
  assert.equal(literalMetric(' '),'" "');
  assert.equal(literalMetric('G '),'"G "');
  assert.equal(literalMetric('NULL'),'"NULL"');
});
test('an unavailable grid does not fabricate zero holding fraction',()=>{
  assert.equal(gridPercent(undefined),'필요입력 없음');
  assert.equal(gridPercent({holding_fraction_percent:null,expected_slots:null}),'필요입력 없음');
  assert.equal(gridPercent({holding_fraction_percent:50,expected_slots:200}),'50.0%');
});
test('absent QC fields remain distinct from an empty population and observed zero presence',()=>{
  assert.equal(qcPresencePercent({held_rows:10,source_qc_presence_rate:null,source_qc_primary_fields:[]}),'QC 필드 없음');
  assert.equal(qcPresencePercent({held_rows:0,source_qc_presence_rate:null,source_qc_primary_fields:[]}),'평가대상 없음');
  assert.equal(qcPresencePercent({held_rows:10,source_qc_presence_rate:0,source_qc_primary_fields:['qc_raw']}),'0.0%');
});
const query=new URLSearchParams('source=GD_OBS_BU&from_month=2026-07&to_month=2026-07&station=S&item=I');
const response={state:'AVAILABLE',snapshot:'SNAPSHOT',source:'GD_OBS_BU',from_month:'2026-07',to_month:'2026-07',
  scope:{station:'S',item:'I'},raw:{held_rows:10,grid:{},stations:[],qc_codes:[],source_qc_primary_fields:['QC_FLAG']},report_reference:{normal_rates:[]}};
test('nullable unavailable, stale and outside-period responses remain normal explanatory states',()=>{
  for(const state of ['UNAVAILABLE','STALE','UNAVAILABLE_PERIOD']) {
    assert.equal(validMetricCompletion({...response,state,raw:null,report_reference:null,reason:'NEEDED_INPUT'},query),true);
  }
});
test('numeric metrics require the exact request scope and complete numeric/reference structure',()=>{
  assert.equal(validMetricCompletion(response,query),true);
  for(const change of [{source:'GR_OBS_ST'},{from_month:'2026-06'},{snapshot:null},{raw:null},
    {scope:{station:'OTHER',item:'I'}},{scope:{station:'S',item:'OTHER'}},{state:'UNKNOWN'}]) {
    assert.equal(validMetricCompletion({...response,...change},query),false);
  }
});
test('partially recalculated periods expose measured counts only for the exact scope and snapshot',()=>{
  const partial={...response,state:'PARTIAL_CATALOG_COUNTS',raw:{...response.raw,grid:{holding_fraction_percent:null,expected_slots:null}}};
  assert.equal(validMetricCompletion(partial,query),true);
  assert.equal(gridPercent(partial.raw.grid),'필요입력 없음');
  for(const change of [{source:'GR_OBS_ST'},{from_month:'2023-01'},{snapshot:null},{raw:null},{scope:{station:'OTHER',item:'I'}}]) {
    assert.equal(validMetricCompletion({...partial,...change},query),false);
  }
});
