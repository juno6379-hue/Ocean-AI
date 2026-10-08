import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import ts from 'typescript';
const source=readFileSync(new URL('../src/data/experimentalDeployment.ts',import.meta.url),'utf8');
const {outputText}=ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022}});
const {experimentalReleaseValid,experimentalPredictionMatches,nativeValues}=await import(`data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`);
const model=()=>({model_id:'AIR_PRES',variable_code:'AIR_PRES',selected_model:'PERSISTENCE',artifact_sha256:'a'.repeat(64),source_membership_sha256:'b'.repeat(64),input_lags:3,
  split_counts:{TRAIN:30,VALIDATION:10,TEST:10},validation_metrics:{PERSISTENCE:{mae:1,rmse:2,pair_count:7}},test_metrics:{PERSISTENCE:{mae:1.5,rmse:2,pair_count:7}},last_values:[1,2,3],last_native_times:['a','b','c']});
const release=()=>({status:'READY',release_id:'test-release',experimental:true,nonoperational:true,approved:false,production_eligible:false,unit:null,timezone:null,horizon_seconds:null,
  source_period:'2026-07',source_table:'GR_OBS_ST',station_code:'DT_0001',models:['AIR_PRES','WATER_TEMP','SALINITY'].map(id=>({...model(),model_id:id,variable_code:id}))});

test('experimental evidence refuses operational claims, missing denominators and malformed models',()=>{
  const valid=release();
  assert.equal(experimentalReleaseValid(valid),true);
  for(const change of [value=>value.approved=true,value=>value.production_eligible=true,value=>value.nonoperational=false,value=>value.unit='hPa',
    value=>value.models[0].test_metrics.PERSISTENCE.pair_count=0,value=>value.models[0].test_metrics.PERSISTENCE.mae=NaN,
    value=>value.models[0].source_membership_sha256='missing',value=>value.models.push(model()),value=>value.models[0].last_values=[1,true,3],
    value=>value.models[0].selected_model='unreported-candidate',value=>value.source_period='2026-06',value=>value.source_table='GD_OBS_ST_MONTHLY']) {
    const value=structuredClone(valid);change(value);assert.equal(experimentalReleaseValid(value),false);
  }
});
test('prediction must match the release, artifact and exact input before being displayed',()=>{
  const value=release(), m=value.models[0];
  const prediction={release_id:value.release_id,model_id:m.model_id,artifact_sha256:m.artifact_sha256,prediction:3.2,input_values:[1,2,3],
    approved:false,production_eligible:false,unit:null,timezone:null,horizon_seconds:null,prediction_target:'NEXT_OBSERVED_NATIVE_ROW'};
  assert.equal(experimentalPredictionMatches(prediction,value,m,[1,2,3]),true);
  for(const changed of [{release_id:'superseded'},{artifact_sha256:'c'.repeat(64)},{input_values:[3,2,1]},{prediction:Infinity},{approved:true},{horizon_seconds:60}])
    assert.equal(experimentalPredictionMatches({...prediction,...changed},value,m,[1,2,3]),false);
});
test('native input requires exactly three explicit finite decimal numbers',()=>{
  assert.deepEqual(nativeValues('1, -2.5, 3e2'),[1,-2.5,300]);
  for(const text of ['1,,3','1,  ,3','1,2','1,2,3,4','1,2,Infinity','1,2,NaN','1,2,true','1,2,0x10','1,2,1e999'])
    assert.equal(nativeValues(text),null);
});
