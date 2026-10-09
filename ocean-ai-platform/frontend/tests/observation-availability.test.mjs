import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import ts from 'typescript';
const source=readFileSync(new URL('../src/data/observationAvailability.ts',import.meta.url),'utf8');
const {outputText}=ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022}});
const {observationAvailability,observationItemLabel}=await import(`data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`);
test('monthly availability uses held evidence and preserves unregistered months across years',()=>{
  assert.deepEqual(observationAvailability([{month:'2025-12-01',held_rows:3},{month:'2025-12',held_rows:2},{month:'2026-02',held_rows:1}],'2025-12','2026-02'),
    [{month:'2025-12',held:true},{month:'2026-01',held:false},{month:'2026-02',held:true}]);
});
test('absence and unknown counts cannot appear as confirmed held data',()=>{
  for(const held_rows of [0,null,undefined,'3',NaN,Infinity,-1])assert.equal(observationAvailability([{month:'2026-07',held_rows}],'2026-07','2026-07')[0].held,false);
  assert.deepEqual(observationAvailability([],'2026-07','2026-06'),[]);
  assert.deepEqual(observationAvailability([],'2026-13','2026-13'),[]);
});
test('unknown sensor/item variants retain their original code',()=>{
  assert.equal(observationItemLabel('WATER_TEMP'),'수온');
  assert.equal(observationItemLabel('TIDE_LEVEL_SENSOR_UNREGISTERED'),'TIDE_LEVEL_SENSOR_UNREGISTERED');
});
