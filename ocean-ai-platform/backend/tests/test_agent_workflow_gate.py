import copy
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import threading
import pytest
from fastapi import FastAPI,Depends
from fastapi.testclient import TestClient
from sqlalchemy import create_engine,event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.core.database import Base,get_db
from app.core.security import Actor,authorize_api
from app.core.config import settings
from app.models.domain import ApprovalHistory,ObservationRaw,ObservationStandard,QCRuleResult,ModelRegistry,RetrainingHistory,ReportRegistry
from app.models.agent_workflow import AgentWorkflowRun,AgentWorkflowTransition
from app.agents import multi_agent_workflow as w
from app.api import routes_agents
from app.services.evidence_fusion import digest
from test_evidence_fusion import SCOPE,item

OP=Actor('operator','operator');REVIEW=Actor('reviewer','reviewer')
def rag(*args):return {'results':[],'evidence_status':'NO_RELEVANT_EVIDENCE','vector_status':'EMPTY'}
@pytest.fixture
def environment(tmp_path,monkeypatch):
    engine=create_engine('sqlite://',poolclass=StaticPool,connect_args={'check_same_thread':False})
    @event.listens_for(engine,'connect')
    def fk(conn,_):conn.execute('PRAGMA foreign_keys=ON')
    Base.metadata.create_all(engine);sessions=sessionmaker(bind=engine,expire_on_commit=False)
    monkeypatch.setattr(settings,'API_IDENTITIES',{'operator':{'token':'op-token','role':'operator'},'reviewer':{'token':'review-token','role':'reviewer'},'viewer':{'token':'view-token','role':'viewer'}})
    monkeypatch.setattr(settings,'DATA_MODE','live')
    yield sessions
    engine.dispose()
def create(sessions,key='start',evidence=None):
    with sessions() as db:
        payload,recommendation=w.analyze_inputs(db,SCOPE,declared_evidence=[item()] if evidence is None else evidence,rag_search=rag)
        result=w.start_workflow(db,payload,recommendation,OP,key);db.commit();return result,payload,recommendation
def approve(sessions,result,key='approve'):
    with sessions() as db:
        approved=w.decide_workflow(db,result['workflow_id'],REVIEW,key,result['recommendation_sha256'],result['revision'],'APPROVED');db.commit();return approved

def test_pending_stops_and_survives_session_restart(environment,monkeypatch):
    monkeypatch.setattr(w,'report_draft_agent',lambda s:pytest.fail('report before approval'))
    monkeypatch.setattr(w,'mlops_agent',lambda s:pytest.fail('MLOps before approval'))
    result,_,_=create(environment)
    assert result['status']=='PENDING' and result['result'] is None and len(result['workflow'])==4
    with environment() as db:
        run=db.get(AgentWorkflowRun,result['workflow_id']);assert run.status=='PENDING' and run.result is None
        assert db.query(ApprovalHistory).one().approval_status=='PENDING'
        with pytest.raises(w.WorkflowError,match='APPROVAL_REQUIRED'):
            w.resume_workflow(db,run.workflow_id,OP,'resume',result['recommendation_sha256'],0)

def test_actual_reviewer_then_resume_once_and_no_definitive_side_effect(environment,monkeypatch):
    result,_,_=create(environment);approved=approve(environment,result)
    calls=[];original=w.report_draft_agent
    monkeypatch.setattr(w,'report_draft_agent',lambda s:(calls.append(1),original(s))[1])
    with environment() as db:
        done=w.resume_workflow(db,result['workflow_id'],OP,'resume',result['recommendation_sha256'],approved['revision']);db.commit()
    with environment() as db:
        replay=w.resume_workflow(db,result['workflow_id'],OP,'resume',result['recommendation_sha256'],approved['revision']);db.commit()
        assert db.query(AgentWorkflowTransition).count()==3 and db.query(ApprovalHistory).count()==2
        assert db.query(ModelRegistry).count()==db.query(RetrainingHistory).count()==db.query(ReportRegistry).count()==0
    assert done==replay and done['status']=='COMPLETED' and calls==[1]
    assert done['result']['report_draft']['status']=='DRAFT' and done['result']['mlops']['training_enqueued'] is False

@pytest.mark.parametrize('terminal',['REJECTED','CANCELLED'])
def test_rejected_and_cancelled_cannot_resume(environment,terminal):
    result,_,_=create(environment)
    with environment() as db:
        if terminal=='REJECTED':view=w.decide_workflow(db,result['workflow_id'],REVIEW,'reject',result['recommendation_sha256'],0,'REJECTED')
        else:view=w.cancel_workflow(db,result['workflow_id'],OP,'cancel',result['recommendation_sha256'],0)
        db.commit()
    with environment() as db:
        with pytest.raises(w.WorkflowError,match='APPROVAL_REQUIRED'):w.resume_workflow(db,result['workflow_id'],OP,'resume',result['recommendation_sha256'],view['revision'])
        assert db.get(AgentWorkflowRun,result['workflow_id']).result is None

def test_cancel_after_approval_revokes_resume(environment):
    result,_,_=create(environment);approved=approve(environment,result)
    with environment() as db:
        cancelled=w.cancel_workflow(db,result['workflow_id'],OP,'cancel',result['recommendation_sha256'],approved['revision']);db.commit()
    assert cancelled['status']=='CANCELLED'
    with environment() as db:
        assert db.query(ApprovalHistory).order_by(ApprovalHistory.id.desc()).first().approval_status=='CANCELLED'
        with pytest.raises(w.WorkflowError):w.resume_workflow(db,result['workflow_id'],OP,'resume',result['recommendation_sha256'],cancelled['revision'])

@pytest.mark.parametrize('actor',[Actor('viewer','viewer'),Actor('operator','operator')])
def test_non_reviewer_cannot_approve(environment,actor):
    result,_,_=create(environment)
    with environment() as db:
        with pytest.raises(w.WorkflowError,match='REVIEWER_REQUIRED'):w.decide_workflow(db,result['workflow_id'],actor,'bad',result['recommendation_sha256'],0,'APPROVED')
        assert db.query(ApprovalHistory).count()==1

def test_start_idempotency_and_actor_payload_replay_protection(environment):
    result,payload,recommendation=create(environment)
    with environment() as db:
        assert w.start_workflow(db,payload,recommendation,OP,'start')==result
        with pytest.raises(w.WorkflowError,match='REPLAY_MISMATCH'):w.start_workflow(db,payload,recommendation,Actor('other','operator'),'start')
        other=copy.deepcopy(payload);other['query']='changed'
        with pytest.raises(w.WorkflowError,match='REPLAY_MISMATCH'):w.start_workflow(db,other,recommendation,OP,'start')
        assert db.query(AgentWorkflowRun).count()==1

def test_stale_hash_revision_and_changed_decision_replay(environment):
    result,_,_=create(environment)
    with environment() as db:
        with pytest.raises(w.WorkflowError,match='STALE_RECOMMENDATION_HASH'):w.decide_workflow(db,result['workflow_id'],REVIEW,'bad','b'*64,0,'APPROVED')
        with pytest.raises(w.WorkflowError,match='STALE_WORKFLOW_REVISION'):w.decide_workflow(db,result['workflow_id'],REVIEW,'bad',result['recommendation_sha256'],5,'APPROVED')
    approve(environment,result)
    with environment() as db:
        assert w.decide_workflow(db,result['workflow_id'],REVIEW,'approve',result['recommendation_sha256'],0,'APPROVED')['status']=='APPROVED'
        with pytest.raises(w.WorkflowError,match='REPLAY_MISMATCH'):w.decide_workflow(db,result['workflow_id'],REVIEW,'approve',result['recommendation_sha256'],0,'REJECTED')

def test_changed_frozen_evidence_or_recipe_cannot_resume(environment):
    result,_,_=create(environment);approved=approve(environment,result)
    with environment() as db:
        run=db.get(AgentWorkflowRun,result['workflow_id']);payload=copy.deepcopy(run.payload);payload['bundle']['evidence'][0]['support_strength']=0;run.payload=payload;db.commit()
    with environment() as db:
        with pytest.raises(w.WorkflowError,match='SNAPSHOT_CHANGED'):w.resume_workflow(db,result['workflow_id'],OP,'resume',result['recommendation_sha256'],approved['revision'])

@pytest.mark.parametrize('tamper',['latest_rejection','actor','transition'])
def test_latest_approval_and_transition_integrity_required(environment,tamper):
    result,_,_=create(environment);approved=approve(environment,result)
    with environment() as db:
        if tamper=='latest_rejection':db.add(ApprovalHistory(approval_type='AGENT_WORKFLOW',target_id=result['workflow_id'],requested_by=OP.user_id,approved_by=REVIEW.user_id,approval_status='REJECTED'))
        elif tamper=='actor':db.get(ApprovalHistory,approved['human_approval']['approval_history_id']).approved_by='intruder'
        else:db.query(AgentWorkflowTransition).filter_by(action='APPROVED').one().actor_id='intruder'
        db.commit()
    with environment() as db:
        with pytest.raises(w.WorkflowError,match='CURRENT_WORKFLOW_APPROVAL_INVALID'):w.resume_workflow(db,result['workflow_id'],OP,'resume',result['recommendation_sha256'],approved['revision'])

def seed_observation(db,value=1000.,oid='O1',sensor='S1',unit='hPa'):
    stamp=datetime(2025,1,1,0,1)
    db.add(ObservationRaw(station_id='ST',sensor_id=sensor,variable_code='AIR_PRES',timestamp_utc=stamp,value_raw=value,value_unit=unit,source_system='ISOLATED_REAL_SHAPED_FIXTURE'))
    db.add(ObservationStandard(observation_id=oid,station_id='ST',sensor_id=sensor,variable_code='AIR_PRES',timestamp_utc=stamp,value_raw=value,value_standard=value,standard_unit=unit,standardization_version='fixture'))

def test_post_approval_live_source_change_and_new_membership_block(environment):
    with environment() as db:seed_observation(db);db.commit()
    result,_,_=create(environment);approved=approve(environment,result)
    with environment() as db:db.get(ObservationStandard,'O1').value_standard=1200.;db.commit()
    with environment() as db:
        with pytest.raises(w.WorkflowError,match='CURRENT_SOURCE_REFERENCE_CHANGED'):w.resume_workflow(db,result['workflow_id'],OP,'resume',result['recommendation_sha256'],approved['revision'])
    with environment() as db:db.get(ObservationStandard,'O1').value_standard=1000.;db.commit()
    with environment() as db:
        db.add(ObservationStandard(observation_id='O2',station_id='ST',sensor_id='S1',variable_code='AIR_PRES',timestamp_utc=datetime(2025,1,1,0,2),value_standard=999.,standard_unit='hPa',standardization_version='fixture'));db.commit()
    with environment() as db:
        with pytest.raises(w.WorkflowError,match='CURRENT_SCOPE_MEMBERSHIP_CHANGED'):w.resume_workflow(db,result['workflow_id'],OP,'resume',result['recommendation_sha256'],approved['revision'])

def test_stored_new_rule_reaches_fusion_but_legacy_and_mixed_scope_do_not(environment):
    with environment() as db:
        seed_observation(db)
        facts={'physical_sensor_id':'physical','sensor_episode_id':'episode','clock_semantics':'UTC_WITH_EXPLICIT_OFFSET'}
        prov={'event_clock_policy':'EXPLICIT_OFFSET_INSTANT','evidence_scope':{k:SCOPE[k] for k in ('station_id','sensor_id','variable_code','unit')},'source_facts':facts,
            'event_at':'2025-01-01T00:01:00Z','available_at':'2025-01-01T00:02:00Z','executed_at_utc':'2025-01-01T00:02:00Z','input_window_sha256':'f'*64}
        db.add(QCRuleResult(qc_result_id='R1',observation_id='O1',station_id='ST',sensor_id='S1',variable_code='AIR_PRES',timestamp_utc=datetime(2025,1,1,0,1),qc_rule_id='R',qc_rule_name='range',qc_stage='RULE',result_flag='4',rule_version='1',evaluation_status='EVALUATED',result_reason='OUTSIDE',provenance_json=prov));db.commit()
        payload,recommendation=w.analyze_inputs(db,SCOPE,rag_search=rag)
        assert recommendation['recommendation_score']==.3 and recommendation['coverage']['RULE']['status']=='PRESENT'
        r=db.get(QCRuleResult,'R1');r.provenance_json=None;db.commit()
        assert w.analyze_inputs(db,SCOPE,rag_search=rag)[1]['recommendation_score'] is None
        r.provenance_json=prov;r.sensor_id='other';db.commit()
        assert not w.analyze_inputs(db,SCOPE,rag_search=rag)[1]['accepted_evidence']

def test_failed_pure_resume_rolls_back_to_approved(environment,monkeypatch):
    result,_,_=create(environment);approved=approve(environment,result)
    def fail(_):raise RuntimeError('draft failure')
    monkeypatch.setattr(w,'report_draft_agent',fail)
    with environment() as db:
        with pytest.raises(RuntimeError):w.resume_workflow(db,result['workflow_id'],OP,'resume',result['recommendation_sha256'],approved['revision'])
        db.rollback()
    with environment() as db:
        run=db.get(AgentWorkflowRun,result['workflow_id']);assert run.status=='APPROVED' and run.result is None and run.revision==approved['revision']

def test_sql_cas_stale_session_cannot_claim_resume_twice(environment):
    result,_,_=create(environment);approved=approve(environment,result)
    first=environment();second=environment()
    try:
        a=first.get(AgentWorkflowRun,result['workflow_id']);b=second.get(AgentWorkflowRun,result['workflow_id'])
        w._cas(first,a,'APPROVED','RESUMING');first.commit()
        with pytest.raises(w.WorkflowError,match='CONCURRENT_CHANGE'):w._cas(second,b,'APPROVED','RESUMING')
        second.rollback()
    finally:first.close();second.close()

def test_api_authenticated_gate_and_readonly_analysis(environment,monkeypatch):
    original=w.collect_evidence
    monkeypatch.setattr(w,'collect_evidence',lambda db,scope,query='',rag_search=None:original(db,scope,query,rag))
    app=FastAPI(dependencies=[Depends(authorize_api)]);app.include_router(routes_agents.router)
    def session():
        with environment() as db:yield db
    app.dependency_overrides[get_db]=session
    body={'scope':SCOPE,'declared_evidence':[item()]}
    with TestClient(app) as client:
        analysis=client.post('/api/agents/evidence/analyze',json=body);assert analysis.status_code==200,analysis.text
        assert analysis.json()['recommendation_score']==.3
        assert client.post('/api/agents/workflows',json=dict(body,request_key='api')).status_code==401
        started=client.post('/api/agents/workflows',headers={'Authorization':'Bearer op-token'},json=dict(body,request_key='api')).json()
        assert started['status']=='PENDING' and started['result'] is None
        url='/api/agents/workflows/'+started['workflow_id'];req={'request_key':'decision','expected_recommendation_sha256':started['recommendation_sha256'],'expected_revision':0,'decision':'APPROVED'}
        assert client.post(url+'/decision',headers={'Authorization':'Bearer op-token'},json=req).status_code==403
        assert client.post(url+'/decision',headers={'Authorization':'Bearer review-token'},json=dict(req,user_id='admin')).status_code==422
        approved=client.post(url+'/decision',headers={'Authorization':'Bearer review-token'},json=req).json();assert approved['status']=='APPROVED'
        resume={'request_key':'resume','expected_recommendation_sha256':started['recommendation_sha256'],'expected_revision':approved['revision']}
        done=client.post(url+'/resume',headers={'Authorization':'Bearer op-token'},json=resume);assert done.status_code==200,done.text
        assert done.json()['status']=='COMPLETED' and done.json()['training_started'] is False
        assert client.get('/api/agents/workflows?unit=Pa').json()==[]
        assert client.get('/api/agents/workflows?unit=hPa').json()[0]['workflow_id']==started['workflow_id']
        assert client.post('/api/agents/workflow',json={}).status_code==409


def test_stale_external_source_can_be_cancelled_but_snapshot_tamper_cannot(environment):
    with environment() as db:seed_observation(db);db.commit()
    result,_,_=create(environment);approved=approve(environment,result)
    with environment() as db:db.get(ObservationStandard,'O1').value_standard=1500.;db.commit()
    with environment() as db:
        cancelled=w.cancel_workflow(db,result['workflow_id'],OP,'cancel',result['recommendation_sha256'],approved['revision']);db.commit()
    assert cancelled['status']=='CANCELLED' and cancelled['result'] is None
    other,_,_=create(environment,key='other')
    with environment() as db:
        run=db.get(AgentWorkflowRun,other['workflow_id']);payload=copy.deepcopy(run.payload);payload['query']='tampered';run.payload=payload;db.commit()
    with environment() as db:
        with pytest.raises(w.WorkflowError,match='SNAPSHOT_CHANGED'):w.cancel_workflow(db,other['workflow_id'],OP,'cancel',other['recommendation_sha256'],0)


def test_real_anomaly_report_to_fusion_and_old_hash_tamper_rejected(environment):
    from test_anomaly_analysis import fitted
    from app.services.anomaly_analysis import analyze_series
    _,test,_,artifact=fitted(modes=['SPIKE'])
    test['rows'][40]['value']+=4
    report=analyze_series(test,artifact)
    scope=dict(test['scope'],period_start=test['rows'][0]['timestamp'],period_end='2020-01-01T09:00:00+00:00',as_of=test['as_of'])
    with environment() as db:
        payload,result=w.analyze_inputs(db,scope,ai_report=report,rag_search=rag)
        assert result['coverage']['AI']['status']=='PRESENT' and result['recommendation_score']>0
        assert any(r['provenance']['calibration_rank'] is not None for r in result['accepted_evidence'])
        tampered=copy.deepcopy(report);tampered['results'][40]['support_strength']=0
        with pytest.raises(w.WorkflowError,match='AI_REPORT_CHECKSUM_MISMATCH'):w.analyze_inputs(db,scope,ai_report=tampered,rag_search=rag)
        tampered=copy.deepcopy(report);tampered['scope']['unit']='fake'
        with pytest.raises(w.WorkflowError,match='AI_REPORT_CHECKSUM_MISMATCH'):w.analyze_inputs(db,scope,ai_report=tampered,rag_search=rag)

def test_real_guide_engine_to_fusion_never_creates_approval(environment):
    from test_qc_rule_engine import row,rule,CONTEXT
    from app.services.qc_rule_engine import execute_rules,to_fusion_evidence
    report=execute_rules([row(50)], [rule('GR',min=-50,max=40,boundary='CLOSED')],CONTEXT)
    scope={'station_id':'ST1','sensor_id':'S1','variable_code':'AIR_TEMP','unit':'degC','period_start':'2026-01-01T00:00:00Z','period_end':'2026-01-01T00:01:00Z','as_of':CONTEXT['as_of']}
    with environment() as db:
        payload,result=w.analyze_inputs(db,scope,rule_report=report,rag_search=rag)
        assert result['recommendation_score']==.30 and result['coverage']['RULE']['status']=='PRESENT'
        from app.services.evidence_fusion import fuse_evidence
        direct=fuse_evidence(scope,[to_fusion_evidence(report['results'][0])])
        assert direct['recommendation_score']==.30
        assert db.query(ApprovalHistory).count()==0 and db.query(QCRuleResult).count()==0


def test_actual_approved_source_ingest_then_stored_rule_then_fusion(environment,tmp_path,monkeypatch):
    from datetime import timedelta,timezone
    from app.services import source_contract_authority as authority
    from app.services.source_contract_snapshot import ingest_approved_source
    from app.models.domain import StationMetadata,SensorMetadata,QCRuleDefinition,QCFlagHistory
    from app.api import routes_qc
    from test_source_contract_snapshot import source_packet
    from test_qc_rule_engine import rule
    monkeypatch.setattr(authority,'SOURCE_ROOT',tmp_path)
    packet=source_packet(tmp_path,'ISOLATED_WORKFLOW_EVENT',with_receive=True)
    with environment() as db:
        db.add(StationMetadata(station_id='ST1',station_name='isolated fixture only'));db.flush()
        db.add(SensorMetadata(station_id='ST1',sensor_id='S1',variable_code='TIDE'));db.flush()
        requested=authority.request_contract(db,packet,OP)
        approved=authority.decide_contract(db,packet['contract_id'],requested['packet_sha256'],'APPROVED',REVIEW)
        ingest_approved_source(db,approved['receipt'],approved['receipt_sha256'],OP)
        spec=rule('GR','TIDE','cm',min=-300,max=1300,boundary='CLOSED',missing_sentinels=[-9999])
        db.add(QCRuleDefinition(qc_rule_id='GUIDE-TIDE',qc_rule_name='guide synthetic fixture',applicable_variable=['TIDE'],algorithm_description='fixture',threshold_definition=spec,rule_version='TEST',active=True));db.commit()
    app=FastAPI(dependencies=[Depends(authorize_api)]);app.include_router(routes_qc.router)
    def session():
        with environment() as db:yield db
    app.dependency_overrides[get_db]=session
    with TestClient(app) as client:
        response=client.post('/api/qc/rules/execute',headers={'Authorization':'Bearer op-token'},json={'station_id':'ST1','sensor_id':'S1','variable_code':'TIDE'})
        assert response.status_code==200,response.text
        assert response.json()['evaluation_counts']=={'EVALUATED':3}
    with environment() as db:
        observed=db.query(ObservationStandard).order_by(ObservationStandard.timestamp_utc).all()
        scope={'station_id':'ST1','sensor_id':'S1','variable_code':'TIDE','unit':'cm',
            'period_start':observed[0].timestamp_utc.replace(tzinfo=timezone.utc).isoformat(),
            'period_end':(observed[-1].timestamp_utc.replace(tzinfo=timezone.utc)+timedelta(seconds=1)).isoformat(),'as_of':datetime.now(timezone.utc).isoformat()}
        payload,result=w.analyze_inputs(db,scope,rag_search=rag)
        assert result['recommendation_score']==.30 and result['coverage']['RULE']['eligible_unique_evidence']==3
        assert not result['conflicts']
        assert any(r['provenance']['source_facts']['clock_semantics']=='OBSERVED_AT' for r in result['accepted_evidence'])
        before=db.query(ApprovalHistory).count();run=w.start_workflow(db,payload,result,OP,'approved-source-workflow');db.commit()
        assert run['status']=='PENDING' and run['result'] is None and db.query(QCFlagHistory).count()==0
        assert db.query(ApprovalHistory).count()==before+1
        dependency=payload['file_dependencies'][0]
        Path=__import__('pathlib').Path
        original=Path(dependency['path']).read_bytes();Path(dependency['path']).write_bytes(original+b'changed')
        with pytest.raises(w.WorkflowError,match='INPUT_FILE_CHANGED_OR_UNAVAILABLE'):
            w.decide_workflow(db,run['workflow_id'],REVIEW,'review',run['recommendation_sha256'],0,'APPROVED')
        assert w.cancel_workflow(db,run['workflow_id'],OP,'cancel',run['recommendation_sha256'],0)['status']=='CANCELLED'
        db.commit()


@pytest.mark.parametrize('changed_field',['result_flag','scope'])
def test_real_rule_report_old_checksum_cannot_bind_changed_evidence(environment,changed_field):
    from test_qc_rule_engine import row,rule,CONTEXT
    from app.services.qc_rule_engine import execute_rules
    report=execute_rules([row(50)],[rule('GR',min=-50,max=40,boundary='CLOSED')],CONTEXT)
    scope={'station_id':'ST1','sensor_id':'S1','variable_code':'AIR_TEMP','unit':'degC','period_start':'2026-01-01T00:00:00Z','period_end':'2026-01-01T00:01:00Z','as_of':CONTEXT['as_of']}
    original_sha=report['result_sha256']
    tampered=copy.deepcopy(report)
    if changed_field=='result_flag':tampered['results'][0]['result_flag']='1'
    else:tampered['results'][0]['scope']['unit']='different-unit'
    assert tampered['result_sha256']==original_sha
    with environment() as db:
        with pytest.raises(w.WorkflowError,match='RULE_REPORT_CHECKSUM_MISMATCH'):
            w.analyze_inputs(db,scope,rule_report=tampered,rag_search=rag)
        assert db.query(ApprovalHistory).count()==db.query(AgentWorkflowRun).count()==0


def test_real_parallel_resume_has_one_pure_stage_execution(tmp_path,monkeypatch):
    engine=create_engine('sqlite:///'+str(tmp_path/'parallel.db'),connect_args={'check_same_thread':False,'timeout':10})
    Base.metadata.create_all(engine);sessions=sessionmaker(bind=engine,expire_on_commit=False)
    result,_,_=create(sessions);approved=approve(sessions,result)
    barrier=threading.Barrier(2);original_load=w._load;original_report=w.report_draft_agent;calls=[]
    def simultaneous_load(db,workflow_id,lock=True):
        run=original_load(db,workflow_id,lock);barrier.wait(timeout=10);return run
    def count_stage(state):calls.append(1);return original_report(state)
    monkeypatch.setattr(w,'_load',simultaneous_load);monkeypatch.setattr(w,'report_draft_agent',count_stage)
    def contender(key):
        with sessions() as db:
            try:
                done=w.resume_workflow(db,result['workflow_id'],OP,key,result['recommendation_sha256'],approved['revision']);db.commit();return done['status']
            except w.WorkflowError as exc:db.rollback();return exc.code
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:outcomes=list(pool.map(contender,['resume-a','resume-b']))
        assert outcomes.count('COMPLETED')==1 and outcomes.count('WORKFLOW_CONCURRENT_CHANGE')==1
        assert calls==[1]
        with sessions() as db:
            assert db.get(AgentWorkflowRun,result['workflow_id']).status=='COMPLETED'
            assert db.query(AgentWorkflowTransition).filter_by(action='RESUME').count()==1
    finally:engine.dispose()
