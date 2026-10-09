import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import ts from 'typescript';
const {outputText}=ts.transpileModule(readFileSync(new URL('../src/data/operationSimulation.ts',import.meta.url),'utf8'),{compilerOptions:{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022}});
const {validSimulationScenarios,validSimulationResult,simulationChartRows}=await import(`data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`);
const flags={source:'SIMULATION',is_simulation:true,approved:false};
const scenario={scenario_id:'normal',label:'정상 자료',description:'가상 시험',expected_operation_state:'NORMAL'};
const fixture=()=>({...flags,production_completed:false,scenario_id:'normal',label:'정상 자료',as_of_day:'2026-07-09',as_of_time:'15:41:20',cutoff_native:'2026-07-09 15:41:20',rows:[{observed_time_raw:'2026-07-09 15:40:00',value_raw:'0'}],operation:{state:'NORMAL'},quality_pipeline:{rule:{status:'EVALUATED',evaluated_count:1,anomaly_count:0,not_evaluated_count:0},ai:{status:'EVALUATED',evaluated_count:1,anomaly_count:0,modes:{SPIKE:{evaluated_count:1,anomaly_count:0}}},fusion:{status:'ANALYSIS_ONLY',recommendation:'REVIEW',recommendation_score:0,missing_categories:['RAG']},workflow:{status:'COMPLETED',pending_stopped:true,unapproved_resume_blocked:true,reviewer_required:true,rejected_resume_blocked:true,resumed_once:true,production_writes:0,transitions:['PENDING','APPROVED','COMPLETED']}},assertions:[{name:'pending stops',passed:true,detail:'후속 실행 차단'}],result_sha256:'a'.repeat(64)});

test('scenario lists require a distinct simulation source and explicit unapproved sample flag',()=>{
  const list={...flags,scenarios:[scenario]};
  assert.equal(validSimulationScenarios(list),true);
  for(const change of [{source:'GD_OBS_ST_MONTHLY'},{is_simulation:false},{approved:true},{scenarios:[scenario,scenario]}])assert.equal(validSimulationScenarios({...list,...change}),false);
});

test('test results cannot borrow another cutoff or scenario, operational claims, or a production write',()=>{
  const result=fixture();assert.equal(validSimulationResult(result,'normal','2026-07-09','15:41:20'),true);
  for(const change of [{source:'GD_OBS_ST_MONTHLY'},{approved:true},{production_completed:true},{scenario_id:'spike'},{as_of_time:'15:42:20'},{cutoff_native:'2026-07-09 15:41:20.000001'},{result_sha256:'bad'}])
    assert.equal(validSimulationResult({...result,...change},'normal','2026-07-09','15:41:20'),false);
  const changed=fixture();changed.quality_pipeline.workflow.production_writes=1;
  assert.equal(validSimulationResult(changed,'normal','2026-07-09','15:41:20'),false);
});

test('failed gate checks remain visible and a measured zero is not converted into missing evaluation',()=>{
  const result=fixture();result.assertions[0].passed=false;result.quality_pipeline.workflow.pending_stopped=false;
  assert.equal(validSimulationResult(result,'normal','2026-07-09','15:41:20'),true);
  result.quality_pipeline.rule.status='NOT_EVALUATED';result.quality_pipeline.rule.evaluated_count=0;result.quality_pipeline.rule.anomaly_count=0;
  assert.equal(validSimulationResult(result,'normal','2026-07-09','15:41:20'),true);
  result.quality_pipeline.fusion.recommendation_score=Infinity;
  assert.equal(validSimulationResult(result,'normal','2026-07-09','15:41:20'),false);
});

test('a future trap cannot enter the synthetic graph and coincident raw rows are preserved',()=>{
  const result=fixture();result.rows.push({observed_time_raw:'2026-07-09 15:41:20.000001',value_raw:'999'},
    {observed_time_raw:'2026-07-09 15:40:00',value_raw:'-1'},{observed_time_raw:'2026-07-09 15:41:20.000000',value_raw:null});
  const rows=simulationChartRows(result);
  assert.equal(rows.length,3);assert.equal(rows[0].value_raw,null);
  assert.deepEqual(rows.slice(1).map(row=>row.value_raw),['-1','0']);
  assert.ok(rows.every(row=>row.filename==='SIMULATION/normal'));
});
