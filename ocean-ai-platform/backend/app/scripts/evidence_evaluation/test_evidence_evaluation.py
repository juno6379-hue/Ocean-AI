"""실제 사고 위험인 기간 오연결·분할 누수·미검토 점수 승격을 검증한다."""
import unittest
from temporal import date_bounds, calendar_relation, sensor_period_candidates, evaluation_blockers, validate_splits
from benchmark import forecast, classification, retrieval, report_quality, resources, selection_gate
from evaluate import evaluate


class TemporalTests(unittest.TestCase):
    def events(self):
        return [dict(event_id='a',event_type='SENSOR_REPLACEMENT',station_id='DT_0001',
                     equipment_expression='C/T',source_excerpt='s/n:333→737',date_text='2011-06-29'),
                dict(event_id='b',event_type='SENSOR_REMOVAL',station_id='DT_0001',
                     equipment_expression='C/T',source_excerpt='s/n:737',date_text='2013-08-16')]

    def test_installation_before_observation_is_not_no_match(self):
        p=sensor_period_candidates(self.events())[0]
        self.assertEqual(calendar_relation(p,'2013-01-01','2013-01-02'),'INSIDE_CANDIDATE_CALENDAR_WINDOW')
        self.assertEqual(p['status'],'CANDIDATE')
        self.assertIsNone(p['physical_sensor_id'])

    def test_serial_and_station_are_not_interchangeable(self):
        for field,value in [('station_id','DT_0002'),('equipment_expression','OTT'),('source_excerpt','s/n:7370')]:
            events=self.events();events[1][field]=value
            self.assertEqual(sensor_period_candidates(events),[])

    def test_boundary_day_is_uncertain(self):
        p=sensor_period_candidates(self.events())[0]
        self.assertEqual(calendar_relation(p,'2013-08-16','2013-08-16'),'BOUNDARY_OR_PARTIAL_OVERLAP_UNCERTAIN')
        self.assertEqual(calendar_relation(p,'2013-08-17','2013-08-18'),'NO_CALENDAR_OVERLAP')

    def test_month_is_not_exact_date(self):
        lo,hi,precision=date_bounds('2024-02')
        self.assertEqual((hi-lo).days,29); self.assertEqual(precision,'month')
        with self.assertRaises(ValueError):date_bounds('2024-13')

    def test_missing_proof_blocks(self):
        self.assertIn('SENSOR_DEPLOYMENT_UNAPPROVED',evaluation_blockers({}))
        self.assertIn('LABEL_UNAPPROVED',evaluation_blockers({'task':'anomaly_detection'}))

    def test_event_and_horizon_leakage(self):
        r=[dict(id=str(i),split=s,timestamp=f'2020-01-0{i+1}T00:00:00',label_end=f'2020-01-0{i+1}T01:00:00')
           for i,s in enumerate(['TRAIN','VALIDATION','TEST'])]
        self.assertEqual(validate_splits(r),[])
        r[0]['event_id']=r[1]['event_id']='same-event'
        self.assertIn('EVENT_ID_LEAKAGE',validate_splits(r))
        r[0]['label_end']='2020-01-02T00:00:00'
        self.assertIn('TEMPORAL_OR_EMBARGO_LEAKAGE',validate_splits(r))


class MetricTests(unittest.TestCase):
    def test_forecast_baseline(self):
        m=forecast([1,2],[1,3],[0,0])
        self.assertEqual(m['mae'],.5);self.assertAlmostEqual(m['skill_vs_baseline'],2/3)
        self.assertIsNone(forecast([1],[1],[1])['skill_vs_baseline'])
        with self.assertRaises(ValueError):forecast([1],[float('nan')],[0])

    def test_no_positive_is_not_perfect_recall(self):
        self.assertIsNone(classification([0,0],[0,0])['recall'])
        self.assertEqual(classification([1,0],[1,1])['precision'],.5)

    def test_retrieval_and_duplicate_rank(self):
        m=retrieval(['x','a'],['a','b'],2)
        self.assertEqual(m['recall_at_k'],.5);self.assertEqual(m['mrr_at_k'],.5)
        with self.assertRaises(ValueError):retrieval(['a','a'],['a'],2)
        self.assertIsNone(retrieval([],[],5)['recall_at_k'])

    def test_report_requires_human_review(self):
        with self.assertRaises(ValueError):report_quality({'status':'MODEL_SELF_REVIEW'})
        r=dict(status='REVIEWED',reviewer='fixture',claims=4,supported_claims=3,citations=2,
               valid_citations=1,required_facts=3,covered_facts=2)
        self.assertEqual(report_quality(r)['unsupported_claims'],1)

    def test_unmeasured_cost_is_not_free(self):
        self.assertIsNone(resources([1,2,3])['billed_cost'])
        self.assertEqual(resources([1,2,3])['latency_p95_ms'],3)
        with self.assertRaises(ValueError):resources([1],billed_cost=1)

    def test_unapproved_candidate_cannot_be_selected(self):
        c=dict(dataset_hash='d',protocol_hash='p',model_digest='m',hardware='fixture',
               dataset_status='BLOCKED',split_validation='PASS',metrics={'mae':1})
        self.assertEqual(selection_gate(c,{'mae':{'max':2}})['status'],'BLOCKED')
        c['dataset_status']='APPROVED'
        self.assertEqual(selection_gate(c,{})['status'],'BLOCKED')
        self.assertEqual(selection_gate(c,{'mae':{'max':2}})['status'],'ELIGIBLE_FOR_REVIEW')

    def test_comparison_uses_same_test_cases(self):
        packet={'dataset':{'status':'APPROVED','reviewer_reference':'TEST_FIXTURE_ONLY',
                    'membership_hash':'fixture','split_validation':'PASS','test_case_ids':['one']},
                'protocol':{'task':'forecast','unit':'C','horizon_seconds':3600,'requirements':{'mae':{'max':1}}},
                'reference':{'actual':[2],'baseline':[0]},
                'candidates':[{'name':'fixture','model_digest':'fixture','hardware':'fixture',
                    'test_case_ids':['one'],'output':[2],'measurement':{'latency_ms':[1]}}]}
        self.assertEqual(evaluate(packet)['candidates'][0]['metrics']['mae'],0)
        packet['candidates'][0]['test_case_ids']=['another']
        with self.assertRaisesRegex(ValueError,'TEST_MEMBERSHIP_MISMATCH'):evaluate(packet)
        packet['dataset']['status']='BLOCKED'
        with self.assertRaisesRegex(ValueError,'DATASET_APPROVAL_REQUIRED'):evaluate(packet)


if __name__=='__main__':unittest.main()
