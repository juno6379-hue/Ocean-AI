import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import ts from 'typescript';
const source=readFileSync(new URL('../src/data/developmentReview.ts',import.meta.url),'utf8');
const {outputText}=ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022}});
const {trainingReviewMatches,validStageReview}=await import(`data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`);
test('a ready receipt must bind the selected manifest path/hash and actual origin membership',()=>{
  const manifest={path:'configured/request.json',sha256:'a'.repeat(64)};
  const receipt={status:'READY',training_eligible:true,manifest_path:manifest.path,manifest_sha256:manifest.sha256,origin_membership_sha256:'b'.repeat(64)};
  assert.equal(trainingReviewMatches(receipt,manifest),true);
  for(const changed of [{status:'BLOCKED'},{training_eligible:false},{manifest_path:'other.json'},{manifest_sha256:'c'.repeat(64)},{origin_membership_sha256:null}])
    assert.equal(trainingReviewMatches({...receipt,...changed},manifest),false);
  assert.equal(trainingReviewMatches(receipt,{...manifest,sha256:'d'.repeat(64)}),false);
});
function board(){return {schema_version:'development-stage-review-v1',approved:false,checked_at:'2026-10-08T00:00:00Z',
  stages:Array.from({length:13},(_,i)=>({stage_id:i+1,title:'단계',implementation:'PARTIAL',verification:'UNKNOWN',data_readiness:'BLOCKED',
    approval:'PENDING',operational_status:'ANALYSIS_ONLY',next_required:['근거 필요'],evidence:[{path:null,sha256:null,verified:false,error:'MISSING'}]}))};}
test('partial and missing evidence are valid display states without becoming completion',()=>{
  const value=board();assert.equal(validStageReview(value),true);assert.equal(value.stages[0].approval,'PENDING');
});
test('malformed/duplicate stage rows and unsupported completion claims fail closed',()=>{
  for(const change of [value=>value.stages[0]=null,value=>value.stages[0].stage_id=2,value=>value.stages[0].next_required=null,
    value=>value.stages[0].evidence=[null],value=>value.stages[0].data_readiness='COMPLETE',value=>value.approved=true]){
    const value=board();change(value);assert.equal(validStageReview(value),false);
  }
});
