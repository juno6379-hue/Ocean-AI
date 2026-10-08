"""시점 경계·센서 혼합·원천 보존·미검사를 정상으로 취급하지 않는 회귀 검증."""
import copy, unittest
from app.services.source_validation import audit_raw, normalize, precise_qc, validate_normalized

def fixture():
    row={'station_id_raw':'78','item_code_raw':'P','observed_at_raw':'2013-01-01 09:00:00','value_raw_numeric':'1018.1','source_qc_fields':{'QC1':'SR'}}
    ev={'status':'VERIFIED','references':['SYNTHETIC_TEST_ONLY']}
    c={'version':'synthetic-1','source_sha256':('0'*64),'source_station_id':'78','station_id':'DT_0001','role':'OBSERVED','source_utc_offset_minutes':540,'evidence':{k:ev for k in ['inventory','station','items','units','timezone','role','qc_policy','sensor_history','datum']},'item_mapping':{'P':{'variable_code':'AIR_PRES','source_unit':'hPa','target_unit':'Pa'}},'bindings':[{'station_id':'DT_0001','variable_code':'AIR_PRES','sensor_id':'s1','equipment_code':'e1','valid_from':'2013-01-01T00:00:00+00:00','valid_to':'2013-01-02T00:00:00+00:00','evidence':ev}]}
    return row,c

class Tests(unittest.TestCase):
    def test_conversion_and_source_preservation(self):
        r,c=fixture();before=copy.deepcopy(r);out,gate=normalize([r],c,('0'*64))
        self.assertEqual(gate['status'],'PASS');self.assertEqual(out[0]['value'],101810);self.assertEqual(out[0]['timestamp_utc'],'2013-01-01T00:00:00+00:00');self.assertEqual(r,before);self.assertEqual(out[0]['source_qc'],{'QC1':'SR'})
    def test_unknown_history_blocks(self):
        r,c=fixture();c['evidence']['sensor_history']={'status':'UNCONFIRMED'};self.assertEqual(normalize([r],c,('0'*64))[0],[])
    def test_hash_mismatch_blocks(self):
        r,c=fixture();self.assertIn('SOURCE_HASH_MISMATCH',normalize([r],c,'changed')[1]['reasons'])
    def test_end_exclusive(self):
        r,c=fixture();r['observed_at_raw']='2013-01-02 09:00:00';self.assertEqual(normalize([r],c,('0'*64))[0],[])
    def test_ambiguous_binding(self):
        r,c=fixture();c['bindings'].append(copy.deepcopy(c['bindings'][0]));self.assertEqual(normalize([r],c,('0'*64))[0],[])
    def test_missing_start_not_infinite(self):
        r,c=fixture();c['bindings'][0]['valid_from']=None;self.assertEqual(normalize([r],c,('0'*64))[0],[])
    def test_duplicate_standard_blocks(self):
        r,c=fixture();self.assertEqual(normalize([r,r],c,('0'*64))[1]['status'],'FAIL')
    def test_unknown_sentinel_blocks(self):
        r,c=fixture();r['value_raw_numeric']='-999';self.assertEqual(normalize([r],c,('0'*64))[0],[])
    def test_raw_conflict_missing(self):
        r,c=fixture();r2={**r,'value_raw_numeric':None};s=audit_raw([r,r2])['series'][0];self.assertEqual(s['checks']['DUPLICATE_CONFLICT'],1);self.assertEqual(s['checks']['MISSING_VALUE'],1)
    def test_qc_no_rule_not_pass(self):
        r,c=fixture();out,_=normalize([r],c,('0'*64));self.assertEqual(precise_qc(out,{})['results'][0]['status'],'NOT_EVALUATED_RULE_UNVERIFIED')
    def test_utc_required(self):
        r,c=fixture();out,_=normalize([r],c,('0'*64));out[0]['timestamp_utc']='2013-01-01T00:00:00';self.assertEqual(validate_normalized(out)['status'],'FAIL')
    def test_qc_gap_and_sensor_boundaries(self):
        r,c=fixture();out,_=normalize([r],c,('0'*64));base=out[0];rows=[base,{**base,'timestamp_utc':'2013-01-01T00:01:00+00:00','value':102000},{**base,'timestamp_utc':'2013-01-01T01:00:00+00:00','value':103000},{**base,'sensor_id':'s2','timestamp_utc':'2013-01-01T00:02:00+00:00'}]
        rule={'evidence':c['evidence']['units'],'version':'test-only','unit':'Pa','valid_from':c['bindings'][0]['valid_from'],'valid_to':c['bindings'][0]['valid_to'],'lower':90000,'upper':110000,'rate_per_second':1,'max_gap_seconds':90,'stuck_seconds':120}
        result=precise_qc(rows,{'DT_0001|s1|AIR_PRES':rule})['results'];self.assertEqual(result[1]['checks']['rate'],'REVIEW');self.assertEqual(result[2]['checks']['rate'],'NOT_EVALUATED');self.assertEqual(result[3]['status'],'NOT_EVALUATED_RULE_UNVERIFIED')
if __name__=='__main__':unittest.main()
