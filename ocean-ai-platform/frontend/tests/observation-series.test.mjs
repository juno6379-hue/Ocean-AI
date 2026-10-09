import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import ts from 'typescript';
const {outputText}=ts.transpileModule(readFileSync(new URL('../src/data/observationSeries.ts',import.meta.url),'utf8'),{compilerOptions:{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022}});
const {nativeClockCoordinate,observationSeries,observationPlot,observationSeriesUnit,numericObservationValue}=await import(`data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`);
const row=(time,value,index=0)=>({observed_time_raw:'2026-07-09 '+time,value_raw:value,filename:'source.parquet',file_row_number:index,depth_from:'02',unit:null});

test('native coordinates use actual intervals, including microseconds, without guessing a time zone',()=>{
  assert.equal(nativeClockCoordinate('2026-07-09T15:41:20'),nativeClockCoordinate('2026-07-09 15:41:20.000000'));
  assert.equal(nativeClockCoordinate('2026-07-09 15:41:20.000001')-nativeClockCoordinate('2026-07-09 15:41:20'),1);
  for(const clock of ['2026-07-09 15:41:20+09:00','2026-02-30 00:00:00','2026-07-09 24:00:00','invalid'])assert.equal(nativeClockCoordinate(clock),null);
  const plot=observationPlot([row('12:10:00','3'),row('12:01:00','2'),row('12:00:00','1')],'WATER_TEMP',100,100);
  assert.deepEqual(plot.points.map(point=>point.x),[0,10,100]);
});

test('zero and negative values remain, missing values break lines, and raw file rows remain inspectable',()=>{
  const rows=[row('12:03:00','0',3),row('12:02:00','NaN',2),row('12:01:00','',1),row('12:00:00','-2',0)];
  const plot=observationPlot(rows,'WATER_TEMP');
  assert.equal(plot.numericCount,2);assert.equal(plot.missingCount,2);
  assert.deepEqual(plot.samples.map(point=>point.value),[-2,null,null,0]);
  assert.deepEqual(plot.segments.map(segment=>segment.length),[1,1]);
  assert.equal(plot.samples[0].raw,'-2');assert.equal(plot.samples[0].filename,'source.parquet');
  assert.deepEqual(plot.samples[0].depth,[undefined,'02',undefined]);
});

test('duplicate clocks retain every raw value and do not assert a vertical temporal change or preferred value',()=>{
  const rows=[row('12:02:00','9',4),row('12:01:00','8',3),row('12:01:00','5',2),row('12:00:00','1',1)];
  const plot=observationPlot(rows,'SALINITY');
  assert.equal(plot.samples.length,4);assert.equal(plot.coincident,2);
  assert.equal(plot.points[1].x,plot.points[2].x);assert.notEqual(plot.points[1].y,plot.points[2].y);
  assert.deepEqual(plot.segments.map(segment=>segment.length),[1,1,1,1]);
  assert.equal(new Set(plot.samples.map(sample=>sample.key)).size,4);
});

test('direction data is discrete, so 359 to 0 never draws a false large wind-direction transition',()=>{
  const plot=observationPlot([row('12:01:00','0'),row('12:00:00','359')],'WIND_DIRECT');
  assert.equal(plot.direction,true);assert.deepEqual(plot.segments.map(segment=>segment.length),[1,1]);
  assert.deepEqual(plot.samples.map(sample=>sample.value),[359,0]);
  assert.equal(observationPlot([row('12:00:00','2.1')],'WIND_SPEED').direction,false);
});

test('labels require an explicit consistent source unit and empty series stays empty',()=>{
  assert.equal(observationSeriesUnit([row('12:00:00','21.38')]),'원천값');
  assert.equal(observationSeriesUnit([{unit:'℃'},{unit:'℃'}]),'℃');
  assert.equal(observationSeriesUnit([{unit:'℃'},{unit:null}]),'원천값');
  assert.equal(observationSeriesUnit([{unit:'℃'},{unit:'K'}]),'원천값');
  assert.deepEqual(observationSeries([]),[]);assert.equal(observationPlot([],'WATER_TEMP').numericCount,0);
});

test('graph numbers reject JavaScript coercions and a conflicting backend numeric value',()=>{
  for(const value_raw of ['0x10','0b10','',null,'NaN','Infinity','1e999',true])assert.equal(numericObservationValue({value_raw}),null);
  assert.equal(numericObservationValue({value_raw:' 21.38 ',value_numeric:21.38}),21.38);
  assert.equal(numericObservationValue({value_raw:'-2.1e-2',value_numeric:-.021}),-.021);
  assert.equal(numericObservationValue({value_raw:'0',value_numeric:0}),0);
  assert.equal(numericObservationValue({value_raw:'21.38',value_numeric:20}),null);
  assert.equal(numericObservationValue({value_raw:'21.38',value_numeric:null}),null);
});
