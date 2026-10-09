import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import ts from 'typescript';
const {outputText}=ts.transpileModule(readFileSync(new URL('../src/data/observationCutoff.ts',import.meta.url),'utf8'),{compilerOptions:{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022}});
const {systemObservationTime,matchesObservationCutoff,matchesLakeSummary,matchesLakeDetail,matchesLakeSeries}=await import(`data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`);
test('system time uses one Seoul anchor, including midnight, without changing raw clocks',()=>{
  assert.equal(systemObservationTime(new Date('2026-10-09T06:33:17Z')),'15:33:17');
  assert.equal(systemObservationTime(new Date('2026-10-08T15:00:00Z')),'00:00:00');
});
test('profile rejects a different station, snapshot, source, month or typed depth under the same clock',()=>{
  const scope={source:'GD_OBS_ST_MONTHLY',from:'2026-07',to:'2026-07',day:'2026-07-09',time:'15:33:17'};
  const summary={source:scope.source,from_month:scope.from,to_month:scope.to,snapshot:'validated',stations:[],as_of_day:scope.day,as_of_time:scope.time};
  assert.equal(matchesLakeSummary(summary,scope),true);
  assert.equal(matchesLakeSummary({...summary,source:'GR_OBS_ST'},scope),false);
  const detail={source:scope.source,station_code:'DT_0028',snapshot:'validated',months:[{month:'2026-07'}],as_of_day:scope.day,as_of_time:scope.time};
  assert.equal(matchesLakeDetail(detail,scope,'DT_0028','validated'),true);
  assert.equal(matchesLakeDetail({...detail,station_code:'DT_0001'},scope,'DT_0028','validated'),false);
  assert.equal(matchesLakeDetail({...detail,snapshot:'other'},scope,'DT_0028','validated'),false);
  const request={...scope,station:'DT_0028',item:'WATER_TEMP',month:'2026-07',depth:[null,'2',null],snapshot:'validated',limit:500,offset:0,tail:false};
  const row={station_code:request.station,item_code:request.item,depth_step:null,depth_from:'2',depth_to:null,observed_time_raw:'2026-07-09T15:33:17.000000'};
  const response={...request,as_of_day:scope.day,as_of_time:scope.time,rows:[row]};
  assert.equal(matchesLakeSeries(response,request),true);
  for(const change of [{station:'DT_0001'},{month:'2026-06'},{snapshot:'other'},{tail:true},{offset:500}])assert.equal(matchesLakeSeries({...response,...change},request),false);
  for(const change of [{depth_from:'02'},{item_code:'SALINITY'},{observed_time_raw:'2026-07-09 15:33:17.000001'},{observed_time_raw:'2026-07-30 00:00:00'},{observed_time_raw:'2026-07-09 15:33:00+09:00'}])assert.equal(matchesLakeSeries({...response,rows:[{...row,...change}]},request),false);
  assert.equal(matchesLakeSeries({...response,rows:[]},request),true);
});
test('a full-month or differently timed response cannot display under the day cutoff label',()=>{
  const scope={as_of_day:'2026-07-09',as_of_time:'15:33:17'};
  assert.equal(matchesObservationCutoff(scope,'2026-07-09','15:33:17'),true);
  assert.equal(matchesObservationCutoff({},'2026-07-09','15:33:17'),false);
  assert.equal(matchesObservationCutoff({...scope,as_of_time:'23:59:59'},'2026-07-09','15:33:17'),false);
  assert.equal(matchesObservationCutoff({...scope,as_of_day:'2026-07-30'},'2026-07-09','15:33:17'),false);
});
