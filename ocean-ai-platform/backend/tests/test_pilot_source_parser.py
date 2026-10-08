# 파일 역할: 시험 원본 파서의 형식·시간대·오류 처리를 검증합니다.
import io,unittest
from app.services.pilot_source_parser import parse_wide,parse_dt_row,SourceFormatError,require_release
HEADER='ID,Time,OTT,OTT_QC1,OTT_QC2,APR,APR_QC1,APR_QC2,ASP,ASP_QC1,ASP_QC2\n'
ROW='DT_0001,2000-01-01 00:00:00,628,OK,G,1025,SR,G,2,ZZ,B\n'
class ParserTests(unittest.TestCase):
    def dtrow(self):return {'dt_ts_id':78,'dt_time':'2013-01-01 00:00:56','dt_tide':999,'dt_tide1':100,'dt_apress':1000,'dt_wspeed':2,'is_simulated':None}
    def test_dt_uses_ott_column_not_generic_tide(self):
        r=parse_dt_row(self.dtrow(),78,'DT_0001');self.assertEqual(r[0]['value_raw_numeric'],'100');self.assertEqual(r[0]['item_code_raw'],'TIDE_LEVEL_OTT')
    def test_dt_absent_qc_and_unknown_role_preserved(self):
        r=parse_dt_row(self.dtrow(),78,'DT_0001')[0];self.assertEqual(r['source_qc_availability'],'NOT_PROVIDED');self.assertEqual(r['source_qc_fields'],{});self.assertIsNone(r['is_simulated_raw']);self.assertIsNone(r['utc_time'])
    def test_dt_requires_source_mapping(self):
        with self.assertRaises(SourceFormatError):parse_dt_row(self.dtrow(),7,'DT_0002')
    def test_dt_missing_channel_cannot_fall_back(self):
        r=self.dtrow();del r['dt_tide1']
        with self.assertRaises(SourceFormatError):parse_dt_row(r,78,'DT_0001')
    def parse(self,s):return list(parse_wide(io.StringIO(s),'DT_0001'))
    def test_preserves_time_and_unknown_qc(self):
        r=self.parse(HEADER+ROW)[0];self.assertIsNone(r[3]);self.assertEqual(r[2][2]['source_qc_fields'],{'QC1':'ZZ','QC2':'B'});self.assertIsNone(r[2][0]['utc_time'])
    def test_station_mismatch_never_joins(self):self.assertEqual(self.parse(HEADER+ROW.replace('DT_0001','DT_0002'))[0][3],'STATION_MISMATCH')
    def test_invalid_date(self):self.assertEqual(self.parse(HEADER+ROW.replace('2000-01-01','2000-02-30'))[0][3],'INVALID_TIME')
    def test_width(self):self.assertEqual(self.parse(HEADER+ROW.rstrip()+',extra\n')[0][3],'ROW_WIDTH_MISMATCH')
    def test_nonfinite(self):self.assertEqual(self.parse(HEADER+ROW.replace(',628,',',Infinity,'))[0][3],'INVALID_VALUE')
    def test_missing_and_sentinel_preserved(self):
        r=self.parse(HEADER+ROW.replace(',628,',',NaN,').replace(',1025,',',-999,'))[0][2];self.assertIsNone(r[0]['value_raw_numeric']);self.assertEqual(r[1]['value_raw_numeric'],'-999')
    def test_duplicate_header(self):
        with self.assertRaises(SourceFormatError):self.parse(HEADER.replace('ASP_QC2','ASP_QC1')+ROW)
    def test_valid_json_without_evidence_is_blocked(self):
        with self.assertRaises(SourceFormatError):require_release({'source_sha256':'a','multivariate_same_station_and_time':True},'a')
    def test_hash_change_is_blocked(self):
        c={'source_sha256':'a','multivariate_same_station_and_time':True,'evidence':{k:{'status':'VERIFIED','references':['fixture']} for k in ['station_identity','item_mapping','units','timezone','qc_codebook','sensor_history','datum','role','inventory']}}
        with self.assertRaises(SourceFormatError):require_release(c,'b')
if __name__=='__main__':unittest.main()
