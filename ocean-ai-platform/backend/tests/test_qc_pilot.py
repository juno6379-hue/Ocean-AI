import unittest
import pandas as pd
from app.scripts.qc_pilot import screen, RULES

def frame(values, seconds, sensors=None):
    n=len(values)
    return pd.DataFrame(dict(source_id=['s']*n,station_id_raw=['a']*n,item_code_raw=['WTP']*n,source_clock_naive=pd.Timestamp('2000-01-01')+pd.to_timedelta(seconds,unit='s'),value_numeric=values,value_status=['MISSING_MARKER' if v is None else 'NUMERIC_UNREVIEWED' for v in values],sensor_id=sensors or [None]*n))

class ScreeningTests(unittest.TestCase):
    def test_range_versions_and_missing(self):
        d,_=screen(frame([36,None,-2.5],[0,600,1200]),RULES['WTP'])
        self.assertEqual(d.range_old.tolist(),['CANDIDATE','NOT_EVALUATED','NO_TRIGGER'])
        self.assertEqual(d.range_proposal.tolist(),['NO_TRIGGER','NOT_EVALUATED','CANDIDATE'])
        self.assertTrue(d.qc_decision.str.startswith('NOT_EVALUATED').all())
    def test_spike_exact_interval_no_gap_or_missing_bridge(self):
        d,_=screen(frame([0,3,None,10,20,30],[0,600,1200,1800,4000,4601]),RULES['WTP'])
        self.assertEqual(d.spike_proposal.tolist(),['NOT_EVALUATED','CANDIDATE','NOT_EVALUATED','NOT_EVALUATED','NOT_EVALUATED','NOT_EVALUATED'])
    def test_flat_resets_sensor_and_gap(self):
        rule=dict(RULES['WTP'],flat_seconds=60)
        d,_=screen(frame([1]*7,[0,60,120,180,240,1000,1060],['a','a','a','b','b','b','b']),rule)
        self.assertEqual(d.flat_candidate.tolist(),[False,False,True,False,False,False,False])
    def test_duplicate_and_reversal_not_spikes(self):
        d,_=screen(frame([0,8,20,30],[0,60,60,0]),RULES['WTP'])
        self.assertTrue(d.spike_proposal.eq('NOT_EVALUATED').all())
    def test_no_station_mixing(self):
        d=frame([1,2],[0,60]);d.loc[1,'station_id_raw']='b'
        with self.assertRaisesRegex(ValueError,'MIXED'):screen(d,RULES['WTP'])

if __name__=='__main__':unittest.main()
