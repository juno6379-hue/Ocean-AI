import unittest
import pandas as pd
from app.scripts.qc_preflight import audit

class PreflightTests(unittest.TestCase):
    def test_preserves_reversal_duplicate_missing(self):
        d=pd.DataFrame({'source_record_number':[1,2,3,4], 'source_clock_naive':pd.to_datetime(['2000-01-01 00:00','2000-01-01 00:01','2000-01-01 00:01','1999-12-31 23:59']), 'value_numeric':[0.,None,2.,3.], 'value_status':['NUMERIC_UNREVIEWED','MISSING_MARKER','NUMERIC_UNREVIEWED','NUMERIC_UNREVIEWED'],'sensor_id':[None]*4,'observed_at_raw':['a','b','c','d']})
        r=audit(d)
        self.assertEqual(r['duplicate_clock_rows'],2)
        self.assertEqual(r['clock_reversals'],1)
        self.assertEqual(r['numeric'],3)
        self.assertEqual(r['recorded_missing'],1)
        self.assertIsNone(r['qc_valid_count'])
        self.assertIsNone(r['nominal_missing_count'])
    def test_gap_has_source_identity(self):
        d=pd.DataFrame({'source_record_number':[1,2,3,4], 'source_clock_naive':pd.to_datetime(['2000-01-01 00:00','2000-01-01 00:01','2000-01-01 00:02','2000-01-01 01:00']), 'value_numeric':[1.]*4,'value_status':['NUMERIC_UNREVIEWED']*4,'sensor_id':[None]*4,'observed_at_raw':['a','b','c','d']})
        r=audit(d)
        self.assertEqual(len(r['gap_candidates']),1)
        self.assertEqual(r['gap_candidates'][0]['elapsed_seconds'],3480)
        self.assertEqual(r['gap_candidates'][0]['previous_raw_clock'],'c')

if __name__=='__main__':unittest.main()
