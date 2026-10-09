import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import ts from 'typescript';
const {outputText}=ts.transpileModule(readFileSync(new URL('../src/data/stationPhotograph.ts',import.meta.url),'utf8'),{compilerOptions:{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022}});
const {stationPhotograph}=await import(`data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`);
const source='https://www.khoa.go.kr/oceandata/oceaninfo/detail.do?obs_post_id=DT_0028';
const photograph={station:'DT_0028',status:'AVAILABLE',image_url:'data:image/gif;base64,R0lGODlh',image_sha256:'a'.repeat(64),source_url:source,credit:'국립해양조사원',captured_at:null,retrieved_at:'2026-10-09T06:54:10Z',historical_photo_asserted:false};

test('station photographs preserve unknown capture date independently of the observation clock',()=>{
  assert.deepEqual(stationPhotograph(photograph,'DT_0028'),photograph);
  assert.throws(()=>stationPhotograph({...photograph,captured_at:'2026-07-09'},'DT_0028'));
  assert.throws(()=>stationPhotograph({...photograph,historical_photo_asserted:true},'DT_0028'));
});

test('stale station responses and changed external links cannot appear under a new station',()=>{
  assert.throws(()=>stationPhotograph(photograph,'DT_0001'));
  assert.throws(()=>stationPhotograph({...photograph,source_url:'https://other.example/photo'},'DT_0028'));
  assert.throws(()=>stationPhotograph({...photograph,source_url:source.replace('DT_0028','DT_0001')},'DT_0028'));
});

test('only verified raster data and image content hashes are accepted',()=>{
  assert.throws(()=>stationPhotograph({...photograph,image_url:'data:image/svg+xml;base64,PHN2Zz4='},'DT_0028'));
  assert.throws(()=>stationPhotograph({...photograph,image_url:'https://other.example/image.jpg'},'DT_0028'));
  assert.throws(()=>stationPhotograph({...photograph,image_sha256:null},'DT_0028'));
});

test('missing official photographs have an explicit identity-bound empty response',()=>{
  const absent={...photograph,status:'NO_PUBLIC_PHOTO',image_url:null,image_sha256:null};
  assert.equal(stationPhotograph(absent,'DT_0028').image_url,null);
  assert.throws(()=>stationPhotograph({...absent,image_url:photograph.image_url},'DT_0028'));
});
