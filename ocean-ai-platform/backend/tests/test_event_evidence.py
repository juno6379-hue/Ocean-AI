# 파일 역할: 사건·문서·관측·승인 라벨·Feature·Dataset의 양방향 연결과 누수 차단을 검증합니다.
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
import pytest
from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event as sql_event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.core.database import Base, get_db
from app.core.config import settings
from app.core.security import authorize_api
from app.api import routes_events, routes_approvals, routes_datasets, routes_qc
from app.models.domain import (StationMetadata, SensorMetadata, ObservationRaw, ObservationStandard,
    DocumentIndex, QCRuleDefinition, AILabel, DatasetRegistry, FeatureValue, QCFlagHistory, ApprovalHistory)
from app.models.evidence import EventEvidence, FeatureProvenance, LabelReviewSnapshot

OP={'Authorization':'Bearer test-operator'}
REVIEW={'Authorization':'Bearer test-reviewer'}
START=datetime(2025,2,1)
QUOTE='2025-02-01 09:00~09:02(KST) 시험관측소 주 조위계 통신 지연 확인'


@pytest.fixture
def env(tmp_path,monkeypatch):
    engine=create_engine('sqlite://',poolclass=StaticPool,connect_args={'check_same_thread':False})
    @sql_event.listens_for(engine,'connect')
    def enforce_fk(connection,_): connection.execute('PRAGMA foreign_keys=ON')
    Base.metadata.create_all(engine)
    sessions=sessionmaker(bind=engine,expire_on_commit=False)
    app=FastAPI(dependencies=[Depends(authorize_api)])
    for router in [routes_events.router,routes_approvals.router,routes_datasets.router,routes_qc.router]: app.include_router(router)
    def get_session():
        with sessions() as db: yield db
    app.dependency_overrides[get_db]=get_session
    monkeypatch.setattr(settings,'API_IDENTITIES',{'operator':{'token':'test-operator','role':'operator'},
                                                 'reviewer':{'token':'test-reviewer','role':'reviewer'}})
    monkeypatch.setattr(settings,'DATASET_SNAPSHOT_DIR',str(tmp_path/'snapshots'))
    with sessions() as db:
        db.add(StationMetadata(station_id='ST1',station_name='시험관측소'));db.flush()
        db.add(SensorMetadata(sensor_id='S1',station_id='ST1',variable_code='TIDE'))
        for i,value in enumerate([50.,150.,9999.]):
            ts=START+timedelta(minutes=i)
            db.add(ObservationRaw(station_id='ST1',sensor_id='S1',variable_code='TIDE',timestamp_utc=ts,
                timestamp_kst=ts+timedelta(hours=9),value_raw=value,value_unit='cm',source_system='ISOLATED_TEST'))
            db.add(ObservationStandard(observation_id=f'O{i}',station_id='ST1',sensor_id='S1',variable_code='TIDE',
                timestamp_utc=ts,value_raw=value,value_standard=value,standard_unit='cm',standardization_version='1'))
        db.add(DocumentIndex(document_id='D1',chunk_id='C1',document_title='격리 검증용 점검보고서',
            document_type='DAILY_INSPECTION_REPORT',document_date=START+timedelta(days=2),chunk_text=QUOTE,
            related_station_id='ST1',related_variable_code='TIDE',page_no=2,section_name='장비 점검',
            metadata_json={'is_demo':True,'source_checksum':'fixture'}))
        db.add(QCRuleDefinition(qc_rule_id='RANGE',qc_rule_name='범위검사',algorithm_description='min/max',
            rule_version='1',active=True,applicable_variable=['TIDE'],threshold_definition={'min':0,'max':100}))
        db.commit()
    with TestClient(app) as client: yield client,sessions
    engine.dispose()


def checked(response):
    assert response.status_code in {200,201},response.text
    return response.json()


def create_chain(client):
    checked(client.post('/api/events/sensor-aliases',headers=REVIEW,json={'station_id':'ST1','sensor_id':'S1',
        'variable_code':'TIDE','alias_text':'주 조위계','mapping_version':'1','valid_start':'2024-01-01T00:00:00Z'}))
    result=checked(client.post('/api/events/from-document',headers=OP,json={'station_id':'ST1','variable_code':'TIDE',
        'expression':'주 조위계','event_start':'2025-02-01T09:00:00+09:00','event_end':'2025-02-01T09:02:00+09:00',
        'event_type':'COMMUNICATION_DELAY','chunk_id':'C1','period_quote':QUOTE,'operation_quote':'통신 지연 확인',
        'operation_time':'2025-02-01T09:01:00+09:00'}))
    eid=result['event_id']
    checked(client.post('/api/qc/rules/execute',headers=OP,json={'station_id':'ST1','sensor_id':'S1','variable_code':'TIDE'}))
    linked=checked(client.post(f'/api/events/{eid}/link-observations',headers=OP))
    assert linked['observations']==2 # 종료 시각의 O2는 연결하지 않는다.
    candidate=checked(client.post(f'/api/events/{eid}/label-candidates',headers=OP,json={'label_version':'1'}))
    assert candidate['review_status']=='PENDING'
    return eid,candidate['label_id']


def register_dataset(client,did='DS1',**overrides):
    body={'dataset_id':did,'dataset_name':'evaluation-1','dataset_version':did,'dataset_split':'TRAIN',
        'station_scope':['ST1'],'sensor_scope':['S1'],'variable_scope':['TIDE'],
        'period_start':'2025-02-01T00:00:00Z','period_end':'2025-02-01T00:02:00Z',
        'feature_version':'event-causal-1','label_version':'1','preprocessing_version':'1','qc_rule_version':'1'}
    body.update(overrides)
    return client.post('/api/datasets',headers=OP,json=body)


def complete_chain(client):
    eid,lid=create_chain(client)
    checked(client.post('/api/approvals/approve',headers=REVIEW,json={'target_type':'AI_LABEL','target_id':lid,'comment':'격리 검증 담당자 승인'}))
    checked(client.post(f'/api/events/{eid}/features',headers=OP))
    checked(register_dataset(client))
    built=checked(client.post('/api/datasets/DS1/build',headers=OP))
    assert built['validation_errors']==[]
    return eid,lid,built


def test_legacy_chain_lineage_cannot_bypass_source_contract_freeze(env):
    client,sessions=env
    eid,lid,built=complete_chain(client)
    assert built['sample_count']==2 and built['unreviewed_count']==0
    valid=checked(client.post('/api/datasets/DS1/validate',headers=OP));assert valid['status']=='INVALID'
    assert 'LEGACY_DATASET_SOURCE_CONTRACT_FREEZE_REQUIRED' in valid['errors']
    assert client.post('/api/datasets/DS1/approve',headers=REVIEW).status_code==409
    snapshot=checked(client.get('/api/datasets/DS1/lineage'))['snapshot']
    assert snapshot['records'][0]['label']['label_id']==lid
    assert len(snapshot['records'][0]['features'])==3
    assert snapshot['events'][eid]['event']['event_start']=='2025-02-01 00:00:00'
    document=next(r for r in snapshot['events'][eid]['evidence'] if r['kind']=='DOCUMENT')
    assert document['report_date']=='2025-02-03 00:00:00' and document['chunk']==QUOTE
    for kind,identifier in [('DOCUMENT','C1'),('OBSERVATION','O0'),('AI_LABEL',lid)]:
        graph=checked(client.get(f'/api/events/evidence/{kind}/{identifier}'))
        assert graph['events'][0]['datasets'][0]['dataset_id']=='DS1'
    with sessions() as db:
        assert db.query(QCFlagHistory).count()==0 # 학습 라벨 승인이 QC Flag를 변경하지 않는다.
        assert db.query(LabelReviewSnapshot).count()==1
        assert db.query(EventEvidence).filter_by(observation_id='O2').count()==0
    feature=checked(client.get('/api/events/feature-lineage/O0/evidence_value/event-causal-1'))
    assert feature['datasets']==['DS1']
    path=Path(settings.DATASET_SNAPSHOT_DIR)/f"{built['data_hash']}.json"
    assert hashlib.sha256(path.read_bytes()).hexdigest()==built['data_hash']
    assert checked(client.post('/api/datasets/DS1/build',headers=OP))['data_hash']==built['data_hash']


def test_pending_label_is_not_training_data_and_reviewer_is_required(env):
    client,sessions=env
    eid,lid=create_chain(client)
    assert client.post('/api/approvals/approve',headers=OP,json={'target_type':'AI_LABEL','target_id':lid}).status_code==403
    checked(register_dataset(client))
    built=checked(client.post('/api/datasets/DS1/build',headers=OP))
    assert built['sample_count']==0 and built['unreviewed_count']==2
    assert checked(client.post('/api/datasets/DS1/validate',headers=OP))['status']=='INVALID'
    repeated=checked(client.post(f'/api/events/{eid}/label-candidates',headers=OP,json={'label_version':'1'}))
    assert repeated['label_id']==lid
    with sessions() as db: assert db.query(ApprovalHistory).count()==1


def test_alias_ambiguity_and_scope_mismatch_are_not_auto_resolved(env):
    client,sessions=env
    eid,lid=create_chain(client)
    with sessions() as db:
        db.add(SensorMetadata(sensor_id='S2',station_id='ST1',variable_code='TIDE'));db.commit()
    checked(client.post('/api/events/sensor-aliases',headers=REVIEW,json={'station_id':'ST1','sensor_id':'S2',
        'variable_code':'TIDE','alias_text':'주 조위계','mapping_version':'1','valid_start':'2024-01-01T00:00:00Z'}))
    result=checked(client.post('/api/events/resolve-sensor',headers=OP,json={'station_id':'ST1','variable_code':'TIDE',
        'expression':'주 조위계','event_start':'2025-02-01T00:00:00Z'}))
    assert result['status']=='AMBIGUOUS'
    bad=client.post('/api/events/sensor-aliases',headers=REVIEW,json={'station_id':'ST1','sensor_id':'S1',
        'variable_code':'WAVE','alias_text':'파고계','mapping_version':'1','valid_start':'2024-01-01T00:00:00Z'})
    assert bad.status_code==422
    assert client.post(f'/api/events/{eid}/evidence',headers=OP,json={'kind':'OBSERVATION','target_id':'O2'}).status_code==422


def test_timezone_required_and_report_date_not_used_as_event_date(env):
    client,_=env
    response=client.post('/api/events',headers=OP,json={'event_type':'TEST','event_start':'2025-02-01T00:00:00'})
    assert response.status_code==422
    response=client.post('/api/events/from-document',headers=OP,json={'station_id':'ST1','variable_code':'TIDE',
        'expression':'S1','chunk_id':'C1','event_type':'TEST','period_quote':'없는 원문',
        'event_start':'2025-02-01T00:00:00Z'})
    assert response.status_code==422


@pytest.mark.parametrize('mutation',['label','feature_future','source','document','snapshot'])
def test_mutated_or_future_evidence_prevents_approval(env,mutation):
    client,sessions=env
    eid,lid,built=complete_chain(client)
    assert checked(client.post('/api/datasets/DS1/validate',headers=OP))['status']=='INVALID'
    with sessions() as db:
        if mutation=='label': db.get(AILabel,lid).quality_label='NORMAL'
        if mutation=='feature_future': db.query(FeatureProvenance).first().available_at=START+timedelta(days=1)
        if mutation=='source': db.get(ObservationStandard,'O0').value_standard=1000
        if mutation=='document': db.query(DocumentIndex).first().chunk_text='원문 변조'
        db.commit()
    if mutation=='snapshot': (Path(settings.DATASET_SNAPSHOT_DIR)/f"{built['data_hash']}.json").write_text('{}')
    assert client.post('/api/datasets/DS1/approve',headers=REVIEW).status_code==409


def test_station_and_time_split_leakage_and_build_recheck(env):
    client,sessions=env
    complete_chain(client)
    station=register_dataset(client,'DS2',dataset_split='VALIDATION',period_start='2025-02-02T00:00:00Z',period_end='2025-02-03T00:00:00Z')
    assert station.status_code==409 and 'station_leakage' in station.text
    temporal=register_dataset(client,'DS3',dataset_split='TEST',station_scope=['ST2'],period_end='2025-02-01T00:03:00Z')
    assert temporal.status_code==409 and 'temporal_split_leakage' in temporal.text
    checked(register_dataset(client,'DS4',dataset_split='TEST',station_scope=['ST2'],period_start='2025-02-02T00:00:00Z',period_end='2025-02-03T00:00:00Z'))
    with sessions() as db:
        db.get(DatasetRegistry,'DS4').station_scope=['ST1'];db.commit()
    assert checked(client.post('/api/datasets/DS1/validate',headers=OP))['status']=='INVALID'


def test_many_to_many_links_and_duplicate_requests(env):
    client,sessions=env
    eid,_=create_chain(client)
    second=checked(client.post('/api/events',headers=OP,json={'event_type':'SECOND_REVIEW','station_id':'ST1',
        'sensor_id':'S1','variable_code':'TIDE','event_start':'2025-02-01T00:00:00Z','event_end':'2025-02-01T00:02:00Z'}))
    for _ in range(2):
        checked(client.post(f"/api/events/{second['event_id']}/evidence",headers=OP,json={'kind':'DOCUMENT','target_id':'C1','quote':QUOTE}))
        checked(client.post(f'/api/events/{eid}/link-observations',headers=OP))
    reverse=checked(client.get('/api/events/evidence/DOCUMENT/C1'))
    assert len(reverse['events'])==2
    with sessions() as db:
        assert db.query(EventEvidence).filter_by(event_id=eid,observation_id='O0').count()==1


def test_label_modify_validation_and_feature_version_are_enforced(env):
    client,_=env
    eid,lid=create_chain(client)
    invalid=client.post('/api/approvals/modify',headers=REVIEW,json={'target_type':'AI_LABEL','target_id':lid,
                                                                  'changes':{'label_confidence':'certain'}})
    assert invalid.status_code==422
    checked(client.post('/api/approvals/approve',headers=REVIEW,json={'target_type':'AI_LABEL','target_id':lid}))
    checked(client.post(f'/api/events/{eid}/features',headers=OP))
    checked(register_dataset(client,feature_version='unknown-version'))
    result=checked(client.post('/api/datasets/DS1/build',headers=OP))
    assert 'feature_definitions_missing' in result['validation_errors']
    assert checked(client.post('/api/datasets/DS1/validate',headers=OP))['status']=='INVALID'


def test_open_event_closes_only_with_actual_source_period(env):
    client,_=env
    event=checked(client.post('/api/events/from-document',headers=OP,json={'station_id':'ST1','variable_code':'TIDE',
        'expression':'S1','chunk_id':'C1','event_type':'TEST','period_quote':QUOTE,
        'event_start':'2025-02-01T00:00:00Z'}))
    eid=event['event_id']
    assert client.post(f'/api/events/{eid}/link-observations',headers=OP).status_code==409
    bad=client.post(f'/api/events/{eid}/close',headers=OP,json={'event_end':'2025-02-01T00:02:00Z','source_quote':'확인되지 않은 종료'})
    assert bad.status_code==422
    checked(client.post(f'/api/events/{eid}/close',headers=OP,json={'event_end':'2025-02-01T00:02:00Z','source_quote':QUOTE}))
    assert checked(client.post(f'/api/events/{eid}/link-observations',headers=OP))['observations']==2
