"""계층 혼합·손상 파일·누락 승인·중복을 차단하는 manifest 계약 검증."""
import unittest,json,uuid
from pathlib import Path
from app.services.lake_manifest import select_files,load_observations,checksum,LakeManifestError
import pyarrow as pa,pyarrow.parquet as pq
from datetime import datetime,timezone
class Tests(unittest.TestCase):
 def setUp(self):
  self.root=Path(__file__).resolve().parent/'.work'/('lake-test-'+uuid.uuid4().hex);(self.root/'metadata/standardized').mkdir(parents=True);(self.root/'standardized').mkdir()
  self.p=self.root/'standardized/a.parquet'
  pq.write_table(pa.table({'station_id':['s'],'sensor_id':['i'],'variable_code':['TIDE'],'timestamp_utc':[datetime(2020,1,1,tzinfo=timezone.utc)],'value_raw':[1.]}),self.p)
  self.m={'schema_version':1,'layer':'standardized','status':'APPROVED','approval_reference':'SYNTHETIC_ONLY','files':[{'path':'standardized/a.parquet','sha256':checksum(self.p),'rows':1}]};self.save()
 def save(self):(self.root/'metadata/standardized/manifest.json').write_text(json.dumps(self.m),encoding='utf8')
 def test_only_listed_files(self):
  (self.root/'unlisted.parquet').write_bytes(b'bad');self.assertEqual(len(load_observations(self.root,'standardized')),1)
 def test_no_manifest_no_scan(self):
  (self.root/'metadata/standardized/manifest.json').unlink()
  with self.assertRaisesRegex(LakeManifestError,'MANIFEST_REQUIRED'):select_files(self.root,'standardized')
 def test_unapproved(self):
  self.m['status']='HOLD';self.save()
  with self.assertRaisesRegex(LakeManifestError,'NOT_APPROVED'):load_observations(self.root,'standardized')
 def test_traversal(self):
  self.m['files'][0]['path']='../a.parquet';self.save()
  with self.assertRaisesRegex(LakeManifestError,'UNSAFE_PATH'):select_files(self.root,'standardized')
 def test_cross_layer(self):
  self.m['files'][0]['path']='raw/a.parquet';self.save()
  with self.assertRaisesRegex(LakeManifestError,'CROSS_LAYER'):select_files(self.root,'standardized')
 def test_file_corruption(self):
  self.p.write_bytes(b'corrupt')
  with self.assertRaisesRegex(LakeManifestError,'HASH_MISMATCH'):select_files(self.root,'standardized')
 def test_duplicate_file(self):
  self.m['files']*=2;self.save()
  with self.assertRaisesRegex(LakeManifestError,'DUPLICATE_FILE'):select_files(self.root,'standardized')
 def test_row_count(self):
  self.m['files'][0]['rows']=2;self.save()
  with self.assertRaisesRegex(LakeManifestError,'ROW_COUNT'):load_observations(self.root,'standardized')
 def test_raw_forbidden_for_training(self):
  p=self.root/'metadata/raw';p.mkdir();(p/'manifest.json').write_text(json.dumps({'schema_version':1,'layer':'raw','status':'APPROVED','files':[]}),encoding='utf8')
  with self.assertRaisesRegex(LakeManifestError,'NOT_APPROVED'):load_observations(self.root,'raw')
 def test_consumer_timestamp_units_and_missing_mask(self):
  from datetime import timedelta
  from app.scripts.analyze_long_term import analyze
  from app.scripts.forecast_tide_baseline import forecast
  from app.scripts.build_imputation_dataset import build
  pq.write_table(pa.table({'station_id':['s']*3,'sensor_id':['i']*3,'variable_code':['TIDE']*3,'timestamp_utc':[datetime(2020,1,1,tzinfo=timezone.utc)+timedelta(hours=i) for i in range(3)],'value_raw':[1.,None,3.]}),self.p)
  self.m['files'][0].update(sha256=checksum(self.p),rows=3);self.save()
  self.assertAlmostEqual(analyze(self.root,layer='standardized')['results'][0]['annual_slope'],8766.,places=5)
  self.assertEqual(forecast(self.root,'s',2,layer='standardized')['predictions'][0]['predicted_value'],3.)
  output=self.root/'result.parquet'
  self.assertEqual(build(self.root,output,'s','TIDE',3,1,layer='standardized')['sample_count'],1)
  row=pq.ParquetFile(output).read().to_pylist()[0]
  self.assertEqual(row['missing_count'],1);self.assertEqual(json.loads(row['values_json']),[1.,None,3.])
if __name__=='__main__':unittest.main()
