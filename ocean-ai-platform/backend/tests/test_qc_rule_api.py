"""Isolated API persistence and non-evaluation regressions."""
from test_safety_workflow import env, OPERATOR, TS
from test_qc_rule_engine import row, rule, CONTEXT
from app.models.domain import QCRuleDefinition, QCRuleResult, ObservationStandard, ApprovalHistory, QCFlagHistory
from app.scripts.seed_qc_rules import seed_qc_rules, guide_rule_templates
from app.models.domain import StationMetadata, SensorMetadata
from app.core.security import Actor
from app.services import source_contract_authority as authority
from app.services.source_contract_snapshot import ingest_approved_source
from test_source_contract_snapshot import source_packet


def test_pure_rule_endpoint_does_not_write_or_require_fake_approval(env):
    client, sessions = env
    response = client.post('/api/qc/rules/evaluate', json={'records':[row(50)],'rules':[rule('GR',min=-50,max=40,boundary='CLOSED')],'context':CONTEXT})
    assert response.status_code == 200, response.text
    assert response.json()['results'][0]['result_flag'] == '4'
    with sessions() as db:
        assert db.query(QCRuleResult).count() == db.query(ApprovalHistory).count() == db.query(QCFlagHistory).count() == 0
    assert len(client.get('/api/qc/rule-catalog').json()['rules']) == 12


def test_unbound_standard_is_not_evaluated_or_finalized(env):
    client, sessions = env
    with sessions() as db:
        db.add(ObservationStandard(observation_id='UNBOUND',station_id='TEST_1',sensor_id='S1',variable_code='AIR_TEMP',timestamp_utc=TS,value_standard=100,standard_unit='degC',standardization_version='TEST'))
        spec=rule('GR',min=-50,max=40,boundary='CLOSED')
        db.add(QCRuleDefinition(qc_rule_id='G',qc_rule_name='Guide',applicable_variable=['AIR_TEMP'],algorithm_description='TEST',threshold_definition=spec,rule_version='TEST1',active=True));db.commit()
    response=client.post('/api/qc/rules/execute',headers=OPERATOR,json={'station_id':'TEST_1'})
    assert response.status_code==200,response.text
    assert response.json()['evaluation_counts']=={'NOT_EVALUATED':1}
    with sessions() as db:
        result=db.query(QCRuleResult).one()
        assert result.result_flag=='NOT_EVALUATED' and result.evaluation_status=='NOT_EVALUATED'
        assert result.provenance_json['approval_created'] is False
    response=client.get('/api/qc/rule-results')
    assert response.json()[0]['evaluation_status']=='NOT_EVALUATED'
    assert client.post('/api/qc/review-candidates',headers=OPERATOR,json={'observation_id':'UNBOUND'}).status_code==409
    analyzed=client.post('/api/qc/copilot/analyze',json={'station_id':'TEST_1'})
    assert analyzed.status_code==200,analyzed.text
    assert analyzed.json()['recommended_flag']=='UNASSESSED'


def test_missing_range_config_is_not_good(env):
    client,sessions=env
    with sessions() as db:
        db.add(ObservationStandard(observation_id='NO-RANGE',station_id='TEST_1',sensor_id='S1',variable_code='TIDE',timestamp_utc=TS,value_standard=10,standardization_version='TEST'))
        db.add(QCRuleDefinition(qc_rule_id='EMPTY',qc_rule_name='Empty',algorithm_description='TEST',threshold_definition={},rule_version='TEST1',active=True));db.commit()
    response=client.post('/api/qc/rules/execute',headers=OPERATOR,json={'station_id':'TEST_1'})
    assert response.status_code==200,response.text
    with sessions() as db:
        assert db.query(QCRuleResult).one().result_flag=='NOT_EVALUATED'


def test_seed_templates_inactive_idempotent_in_isolated_database(env):
    _,sessions=env
    with sessions() as db:
        assert seed_qc_rules(db)==14
        assert seed_qc_rules(db)==0
        templates=db.query(QCRuleDefinition).filter(QCRuleDefinition.qc_rule_id.like('GUIDE2023_%')).all()
        assert len(templates)==12 and all(r.active is False for r in templates)
        assert db.query(ApprovalHistory).count()==0
        assert all(t['threshold_definition']['provenance']['configuration_reference'] is None for t in guide_rule_templates())


def test_nested_bad_types_422_or_non_evaluation_never_500(env):
    client,_=env
    assert client.post('/api/qc/rules/evaluate',json={'records':[[]],'rules':[],'context':CONTEXT}).status_code==422
    spec=rule('GR',min=-50,max=40,boundary='CLOSED');spec['parameters']=[]
    response=client.post('/api/qc/rules/evaluate',json={'records':[row()],'rules':[spec],'context':CONTEXT})
    assert response.status_code==200,response.text
    assert response.json()['results'][0]['result_flag']=='NOT_EVALUATED'


def test_current_approved_source_ingest_executes_and_preserves_evidence_then_detects_tamper(env,tmp_path,monkeypatch):
    client,sessions=env;monkeypatch.setattr(authority,'SOURCE_ROOT',tmp_path)
    packet=source_packet(tmp_path,'ISOLATED_EVENT',with_receive=True)
    with sessions() as db:
        db.add(StationMetadata(station_id='ST1',station_name='Synthetic test only'))
        db.add(SensorMetadata(station_id='ST1',sensor_id='S1',variable_code='TIDE'));db.commit()
        request=authority.request_contract(db,packet,Actor('isolated-operator','operator'))
        approved=authority.decide_contract(db,packet['contract_id'],request['packet_sha256'],'APPROVED',Actor('isolated-reviewer','reviewer'))
        ingest_approved_source(db,approved['receipt'],approved['receipt_sha256'],Actor('isolated-operator','operator'));db.commit()
        spec=rule('GR','TIDE','cm',min=-300,max=1300,boundary='CLOSED',missing_sentinels=[-9999])
        db.add(QCRuleDefinition(qc_rule_id='GUIDE-TIDE',qc_rule_name='Guide TIDE',applicable_variable=['TIDE'],algorithm_description='Synthetic test only',threshold_definition=spec,rule_version='TEST1',active=True));db.commit()
    response=client.post('/api/qc/rules/execute',headers=OPERATOR,json={'station_id':'ST1'})
    assert response.status_code==200,response.text
    assert response.json()['evaluation_counts']=={'EVALUATED':3}
    with sessions() as db:
        results=db.query(QCRuleResult).order_by(QCRuleResult.timestamp_utc).all()
        assert [r.result_flag for r in results]==['1','1','4']
        evidence=results[-1].provenance_json
        assert evidence['evidence_scope']=={'station_id':'ST1','sensor_id':'S1','variable_code':'TIDE','unit':'cm'}
        assert evidence['available_at']==evidence['executed_at_utc'] and evidence['available_at'].endswith('+00:00')
        assert evidence['source_facts']['reference_datum']=='ISOLATED_FIXTURE_DATUM'
        assert evidence['source_facts']['sensor_episode_id']=='isolated-episode-001'
        assert db.query(QCFlagHistory).count()==0
        # A newer immutable rule sees corrupted standardized data as unbound;
        # an existing persisted earlier analysis is not rewritten silently.
        db.get(ObservationStandard,'O2').value_standard=10000
        db.add(QCRuleDefinition(qc_rule_id='GUIDE-TIDE',qc_rule_name='Guide TIDE',applicable_variable=['TIDE'],algorithm_description='Synthetic test only',threshold_definition=spec,rule_version='TEST2',active=True));db.commit()
    response=client.post('/api/qc/rules/execute',headers=OPERATOR,json={'station_id':'ST1'})
    assert response.status_code==200,response.text
    with sessions() as db:
        latest=db.query(QCRuleResult).filter_by(observation_id='O2',rule_version='TEST2').one()
        assert latest.result_flag=='NOT_EVALUATED'
