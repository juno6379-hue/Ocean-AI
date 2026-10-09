"""Isolated authority and stored-result regressions; no actual inference/writes."""
import copy
import json
from datetime import datetime,timedelta,timezone
from types import SimpleNamespace as N
import pytest
from sqlalchemy import create_engine,event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.core.database import Base,get_db
from app.core.config import settings
from app.core.security import Actor
from app.models.domain import (ObservationRaw,ObservationStandard,QCRuleResult,QCRuleDefinition,ModelRegistry,AIPredictionResult,
    OperationLog,DocumentIndex,DailyInspectionReport,SensorMetadata)
from app.models.source_contracts import SourceContractDecision
from app.models.source_observation_binding import SourceObservationBinding
from app.services import qc_candidate_review as q
from app.services.qc_overview import resolve_window
from app.services.source_contract_review import exact_scope_key
from app.api import routes_qc_candidates

UTC=timezone.utc
NOW=datetime(2026,7,9,12,tzinfo=UTC)


def window(): return resolve_window(now=NOW)


def fixture():
    grain=dict(source_group='ISOLATED_ACTUAL_SHAPED_FIXTURE',station_code='ST',item_code='TEMP_RAW',month='2026-07',depth_step=None,depth_from=None,depth_to=None)
    proof=dict(canonical_station_id='ST',canonical_sensor_id='S',standard_variable='AIR_TEMP',source_item_code='TEMP_RAW',
        source_group=grain['source_group'],source_station_code='ST',source_month='2026-07',exact_scope_key=exact_scope_key(grain),
        timestamp_utc='2026-07-09T10:00:00+00:00',value=25.0,source_value_raw='25.0',unit='degC',source_unit='degC',quantity_kind='SCALAR',
        physical_sensor_id='PHYSICAL-SERIAL',sensor_episode_id='EP1',timezone='UTC',qc_rule_version='V1',
        depth={'step':None,'from':None,'to':None},effective_start='2026-01-01T00:00:00Z',effective_end='2027-01-01T00:00:00Z',
        qc_effective_start='2026-01-01T00:00:00Z',qc_effective_end='2027-01-01T00:00:00Z',
        source_sha256='a'*64,parquet_sha256='b'*64,source_row_locator='parquet_row_group=0;row_index=1',
        available_at='2026-07-09T10:05:00Z',qc_available_at='2026-07-09T10:05:00Z',
        source_qc_raw='BAD',source_mqc_raw='B ',source_n1_aqc_raw='',qc_eligible=False,
        source_receive_timestamp_utc='2026-07-09T10:05:00Z',source_receive_clock_policy='LOCAL_OBSERVED_TIMEZONE')
    observation=N(observation_id='O1',station_id='ST',sensor_id='S',variable_code='AIR_TEMP',source_item_code='TEMP_RAW',
        standard_unit='degC',timestamp_utc=datetime(2026,7,9,10),value_standard=25.0,water_step=None,from_depth=None,to_depth=None)
    raw=N(source_system=grain['source_group'],value_raw=25.,source_item_code='TEMP_RAW',qc_flag='BAD',mqc_flag='B ',water_step=None,from_depth=None,to_depth=None)
    binding=N(payload=proof,contract_id='C1',approval_history_id=1,receipt_sha256='c'*64,
        source_sha256='a'*64,parquet_sha256='b'*64,source_row_locator=proof['source_row_locator'],exact_scope_key=proof['exact_scope_key'],
        created_at=datetime(2026,7,9,10,6),bound_at_utc=datetime(2026,7,9,10,6,tzinfo=UTC))
    receipt=dict(contract_id='C1',observations={'O1':proof},approval_receipt={'approval_history_id':1,'decided_at':'2026-07-09T09:00:00Z'})
    return observation,binding,receipt,raw


def observation(): return q._registered_row(*fixture(),window())


def rule(observation,flag='4',rid='R1',kind='GR'):
    config=dict(qc_rule_id=rid,rule_version='V1',kind=kind,parameters={'max_delay_seconds':60} if kind=='DE' else {'min':-50,'max':40})
    definition=N(qc_rule_id=rid,rule_version='V1',threshold_definition=copy.deepcopy({k:v for k,v in config.items() if k not in ('qc_rule_id','rule_version')}))
    facts=dict(physical_sensor_id=observation['physical_sensor_id'],sensor_episode_id=observation['sensor_episode_id'],
        evidence={'sha256':observation['receipt_sha256'],'locator':observation['source_row_locator']})
    provenance=dict(engine_version=q.engine.ENGINE_VERSION,event_clock_policy='EXPLICIT_OFFSET_INSTANT',**q.engine.implementation_hashes(),
        source_facts=facts,evidence_scope={k:observation[k] for k in ('station_id','sensor_id','variable_code','unit')},
        event_at=observation['observation_time'],available_at='2026-07-09T10:07:00Z',executed_at_utc='2026-07-09T10:07:00Z',
        configuration=config,rule_spec_sha256=q.digest(config),input_observation_ids=['O1'],input_window_sha256='d'*64)
    row=N(qc_result_id=rid,observation_id='O1',station_id='ST',sensor_id='S',variable_code='AIR_TEMP',timestamp_utc=datetime(2026,7,9,10),
        provenance_json=provenance,qc_rule_id=rid,qc_rule_name=kind,rule_version='V1',result_flag=flag,
        evaluation_status='MISSING' if flag=='9' else 'NOT_EVALUATED' if flag=='NOT_EVALUATED' else 'EVALUATED',threshold_value=60.,input_value=25.,result_reason='FIXTURE')
    return row,definition


def prediction(observation):
    scope={k:observation[k] for k in q.SCOPE_KEYS}|{'depth':observation['depth']}
    metadata=dict(schema_version='qc-stored-ai-1',observation_id='O1',authority_sha256=observation['authority_sha256'],scope=scope,
        available_at='2026-07-09T10:07:00Z',version_available_at='2026-07-09T10:07:00Z',model_version='M1',model_sha256='e'*64,drift_score=.25,level_shift=None)
    row=N(id=1,station_id='ST',sensor_id='S',variable_code='AIR_TEMP',timestamp_utc=datetime(2026,7,9,10),model_id='M1',
        predicted_value=23.,anomaly_score=.7,confidence=None,recommended_flag='SUSPECT',cause_candidate=None,explanation=metadata)
    model=N(model_version='M1',model_name='Stored fixture model',metrics_json=dict(available_at='2026-07-09T09:00:00Z',artifact_sha256='e'*64,training_data_end_utc='2026-07-01T00:00:00Z'),
        training_data_end=datetime(2026,7,1),target_variable='AIR_TEMP',status='CANDIDATE',deployment_status='CANDIDATE',deployment_stage='CANDIDATE',is_champion=False)
    return row,model


@pytest.fixture
def db():
    engine=create_engine('sqlite://',poolclass=StaticPool,connect_args={'check_same_thread':False})
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine,expire_on_commit=False)() as session: yield session
    engine.dispose()


def test_flag_catalog_namespaces_are_not_source_aliases():
    catalog=q.flag_catalog()
    assert {r['code']:r['meaning'] for r in catalog['flags']}=={'1':'GOOD','3':'SUSPECT','4':'BAD','9':'MISSING','NOT_EVALUATED':'NOT_EVALUATED'}
    assert catalog['source_qc']['interpreted'] is False and '2' not in {r['code'] for r in catalog['flags']}
    assert catalog['approval_codes']['accepted'] and catalog['display_catalog'][0]['semantic']=='GOOD'


def test_bad_raw_and_training_ineligible_source_stays_in_monitoring():
    row=observation()
    assert row['value']==25 and row['qc_source_literals']['source_qc_raw']=='BAD'
    assert row['source_proof']['qc_eligible'] is False and row['source_qc_interpreted'] is False
    assert row['delay_minutes']==5 and row['delay_flag']=='NOT_EVALUATED' and row['is_late'] is None
    assert row['late_history'][0]['delay_minutes']==5
    assert row['available_at']=='2026-07-09T10:06:00+00:00'


@pytest.mark.parametrize('change,expected',[
    ('wrong_station','CANONICAL_OBSERVATION_SCOPE'),('wrong_sensor','CANONICAL_OBSERVATION_SCOPE'),
    ('value','SCALAR_VALUE'),('hash','BINDING_SOURCE_SHA256'),('raw_simulated','SIMULATED_SOURCE'),
    ('naive_binding','BINDING_RECORD_AVAILABILITY'),('future_binding','POST_CUTOFF_SOURCE'),
    ('future_received','POST_CUTOFF_RECEIPT'),('source_episode_end','SOURCE_OR_QC_EPISODE'),
    ('depth','TYPED_DEPTH_CHANGED'),('naive_available','EXPLICIT_OFFSET'),('receipt_observation','APPROVED_PROOF')])
def test_wrong_and_future_source_never_becomes_candidate(change,expected):
    obs,binding,receipt,raw=fixture()
    if change=='wrong_station': obs.station_id='OTHER'
    if change=='wrong_sensor': obs.sensor_id='OTHER'
    if change=='value': obs.value_standard=99
    if change=='hash': binding.source_sha256='f'*64
    if change=='raw_simulated': raw.source_system='MDC_WEB_OBS_ST_SIMULATED'
    if change=='naive_binding': binding.bound_at_utc=datetime(2026,7,9,10,6)
    if change=='future_binding': binding.bound_at_utc=NOW+timedelta(microseconds=1)
    if change=='future_received': binding.payload['source_receive_timestamp_utc']=(NOW+timedelta(microseconds=1)).isoformat()
    if change=='source_episode_end': binding.payload['effective_end']=binding.payload['timestamp_utc']
    if change=='depth': obs.water_step=1.
    if change=='naive_available': binding.payload['available_at']='2026-07-09T10:05:00'
    if change=='receipt_observation': receipt['observations']={}
    with pytest.raises(q.CandidateError,match=expected): q._registered_row(obs,binding,receipt,raw,window())


def test_receive_absent_is_not_ingest_time():
    args=fixture();args[1].payload['source_receive_timestamp_utc']=None
    row=q._registered_row(*args,window())
    assert row['received_time'] is row['delay_minutes'] is row['is_late'] is None
    assert row['delay_flag']=='NOT_EVALUATED' and row['late_history']==[]


def test_rule_delay_flag_only_from_persisted_threshold_version():
    obs=observation();row,definition=rule(obs,'3',kind='DE')
    result=q._rule_result(row,obs,definition,window());point=q._point(obs,[result])
    assert point['value']==25 and point['delay_minutes']==5 and point['is_late'] is True
    assert point['delay_flag']=='3' and point['delay_policy']['threshold_seconds']==60
    assert 'source_proof' not in point


def test_sentinel_missing_rule_is_in_queue_not_filtered_for_training():
    obs=observation();row,definition=rule(obs,'9')
    result=q._rule_result(row,obs,definition,window())
    assert result['meaning']=='MISSING' and q.priority_queue([result])['total']==1


@pytest.mark.parametrize('change,expected',[
    ('source_scope','RULE_EXACT_SCOPE'),('epoch','RULE_SENSOR_EPISODE'),('future','RULE_AVAILABILITY'),
    ('version','RULE_DEFINITION'),('source_hash','RULE_SOURCE_BINDING'),('namespace','RULE_FLAG_NAMESPACE'),
    ('undefined_flag','RULE_FLAG_UNDEFINED'),('flag_status','RULE_FLAG_STATUS_CONFLICT'),('input_value','RULE_INPUT_VALUE')])
def test_persisted_rule_requires_actual_binding_and_version(change,expected):
    obs=observation();row,definition=rule(obs)
    if change=='source_scope': row.provenance_json['evidence_scope']['unit']='other'
    if change=='epoch': row.provenance_json['source_facts']['sensor_episode_id']='other'
    if change=='future': row.provenance_json['available_at']=(NOW+timedelta(microseconds=1)).isoformat()
    if change=='version': definition.threshold_definition['parameters']['max']=400
    if change=='source_hash': row.provenance_json['source_facts']['evidence']['sha256']='f'*64
    if change=='namespace': row.provenance_json['engine_version']='LEGACY_RANGE'
    if change=='undefined_flag': row.result_flag='G'
    if change=='flag_status': row.evaluation_status='MISSING'
    if change=='input_value': row.input_value=26
    with pytest.raises(q.CandidateError,match=expected): q._rule_result(row,obs,definition,window())


def test_bad_then_suspect_then_recent_and_no_duplicate_observation_queue():
    obs=observation();bad,_=rule(obs);baddef=rule(obs)[1]
    bad=q._rule_result(bad,obs,baddef,window())
    suspect=copy.deepcopy(bad)|dict(id='qc:S1',qc_result_id='S1',observation_id='O2',flag='3',meaning='SUSPECT',priority=1,observation_time='2026-07-09T11:59:00Z')
    older=copy.deepcopy(suspect)|dict(id='qc:S0',qc_result_id='S0',observation_id='O3',observation_time='2026-07-09T11:58:00Z')
    duplicate=copy.deepcopy(suspect)|dict(observation_id='O1')
    result=q.priority_queue([suspect,older,bad,duplicate],2)
    assert result['total']==3 and [r['id'] for r in result['rows']]==['qc:R1','qc:S1']


def test_bounded_actual_series_keeps_gap_duplicates_and_cutoff_microseconds():
    begin=datetime(2026,7,9,10,tzinfo=UTC)
    rows=[dict(observation_id=str(i),observation_time=(begin+timedelta(minutes=i)).isoformat(),value=float(i),actual_value=True,is_gap=False) for i in range(20) if i!=10]
    rows.append(dict(rows[0],observation_id='duplicate'))
    rows.append(dict(rows[-1],observation_id='future',observation_time=(NOW+timedelta(microseconds=1)).isoformat()))
    result=q.surrounding_packet(rows,rows[0]['observation_time'],NOW.isoformat())
    assert len(result['rows'])==20 and len(result['gaps'])==1
    assert result['gaps'][0]['observation_time']=='2026-07-09T10:10:00+00:00'
    assert result['gaps'][0]['value'] is None and result['interpolation'] is False
    assert all(r['observation_id']!='future' for r in result['rows'])


def test_stored_ai_available_with_actual_expected_residual_and_declared_model_state():
    obs=observation();row,model=prediction(obs)
    result=q.stored_ai([row],[model],obs,window())
    value=result['results'][0]
    assert result['status']=='AVAILABLE' and value['predicted_value']==23 and value['residual']==2
    assert value['anomaly_score']==.7 and value['confidence'] is None and value['drift_score']==.25
    assert value['active_approved_serving'] is None and value['registry_declares_active_approved'] is False
    assert result['inference_executed'] is False


@pytest.mark.parametrize('change', ['future_result','future_model','future_training','wrong_sensor','wrong_authority','wrong_model','plain_explanation','naive_version'])
def test_stored_ai_cannot_mix_july_later_models_or_wrong_source(change):
    obs=observation();row,model=prediction(obs)
    if change=='future_result': row.explanation['available_at']='2026-07-31T00:00:00Z'
    if change=='future_model': model.metrics_json['available_at']='2026-07-31T00:00:00Z'
    if change=='future_training': model.metrics_json['training_data_end_utc']='2026-07-31T00:00:00Z'
    if change=='wrong_sensor': row.sensor_id='OTHER'
    if change=='wrong_authority': row.explanation['authority_sha256']='f'*64
    if change=='wrong_model': row.model_id='M2'
    if change=='plain_explanation': row.explanation='Legacy unbound explanation'
    if change=='naive_version': row.explanation['version_available_at']='2026-07-09T10:07:00'
    result=q.stored_ai([row],[model],obs,window())
    assert result['status']=='UNVERIFIED' and result['results']==[] and result['excluded_counts']


def test_ai_no_model_and_not_executed_are_distinct():
    obs=observation();_,model=prediction(obs)
    assert q.stored_ai([],[],obs,window())['status']=='NO_MODEL'
    assert q.stored_ai([],[model],obs,window())['status']=='NOT_EXECUTED'


def test_registered_zero_and_unbound_simulated_db_rows_are_distinct(db):
    db.add(ObservationStandard(observation_id='SIM',station_id='ST',sensor_id='S',variable_code='AIR_TEMP',timestamp_utc=datetime(2026,7,9,10),value_standard=123,standardization_version='SIMULATED'))
    db.commit()
    result=q.registered_rows(db,window())
    assert result['selected_count']==0 and result['rows']==[] and result['status']=='NO_DATA'


def test_keyset_census_over_10000_with_bounded_batches_shared_receipt_and_raw_bulk_query(db,monkeypatch):
    size=10003;start=datetime(2026,7,9)
    standards=[];raws=[];bindings=[]
    for i in range(size):
        stamp=start+timedelta(seconds=i)
        standards.append(ObservationStandard(observation_id=f'O{i:05}',station_id='ST',sensor_id='S',variable_code='AIR_TEMP',timestamp_utc=stamp,value_standard=1,standardization_version='ISOLATED_TEST'))
        raws.append(ObservationRaw(station_id='ST',sensor_id='S',variable_code='AIR_TEMP',timestamp_utc=stamp,value_raw=1,source_system='ISOLATED_TEST'))
        bindings.append(SourceObservationBinding(observation_id=f'O{i:05}',contract_id='C',approval_history_id=1,receipt_sha256='a'*64,source_sha256='b'*64,parquet_sha256='c'*64,source_row_locator=str(i),exact_scope_key='d'*64,payload={},created_by='ISOLATED_TEST'))
    db.add_all(standards+raws+bindings+[SourceContractDecision(approval_history_id=1,contract_id='C',packet_sha256='e'*64,decision='APPROVED',reviewer_id='ISOLATED_TEST',reviewer_role='reviewer',receipt_sha256='a'*64,receipt={})]);db.commit()
    verification=[];rawqueries=[]
    monkeypatch.setattr(q,'verify_approved_receipt',lambda *args,**kw:verification.append(1))
    monkeypatch.setattr(q,'_registered_row',lambda o,b,r,raw,w:dict(observation_id=o.observation_id,raw_present=raw is not None))
    def query(conn,cursor,statement,parameters,context,many):
        if 'FROM observation_raw' in statement: rawqueries.append(1)
    event.listen(db.get_bind(),'before_cursor_execute',query)
    cache={};seen=[];batches=0
    for batch in q.iter_registered_batches(db,window(),batch_size=500,receipt_cache=cache):
        assert len(batch['rows'])<=500 and batch['selected_count']==size and not batch['truncated']
        assert all(r['raw_present'] for r in batch['rows'])
        seen.extend(r['observation_id'] for r in batch['rows']);batches+=1
    assert len(seen)==len(set(seen))==size and batches==21 and len(rawqueries)==21
    assert len(verification)==1
    q.verify_cached_authority(db,cache);assert len(verification)==2
    assert next(q.iter_registered_batches(db,window(),station_scope={'include':[]}))['selected_count']==0


def test_source_revocation_or_definition_change_during_scan_fails_closed(db,monkeypatch):
    monkeypatch.setattr(q,'verify_approved_receipt',lambda *a,**kw:(_ for _ in ()).throw(q.SourceContractError('SOURCE_APPROVAL_NOT_CURRENT')))
    with pytest.raises(q.CandidateError,match='SOURCE_AUTHORITY_CHANGED'): q.verify_cached_authority(db,{'a'*64:dict(receipt={},error=None)})
    row=QCRuleDefinition(qc_rule_id='R',rule_version='1',qc_rule_name='Range',algorithm_description='ISOLATED',threshold_definition={'max':5})
    db.add(row);db.commit();snapshot=q._definition_snapshot(row)
    cache={('R','1'):dict(definition=N(**snapshot),sha256=q.digest(snapshot))}
    row.threshold_definition={'max':10};db.commit()
    with pytest.raises(q.CandidateError,match='RULE_DEFINITION_CHANGED'): q.verify_definition_cache(db,cache)


def test_archive_id_is_exact_sha_and_file_row_not_anomaly_claim():
    row=dict(parquet_sha256='a'*64,file_row_number=14)
    assert q.archive_candidate_id(row)=='archive:'+'a'*64+':14'
    with pytest.raises(q.CandidateError): q.archive_candidate_id(row|{'file_row_number':True})


def test_candidate_get_frozen_window_wrong_scope_and_no_mutation(db,monkeypatch):
    app=FastAPI();app.include_router(routes_qc_candidates.router);app.dependency_overrides[get_db]=lambda:db
    client=TestClient(app);w=window()
    params=dict(source='REGISTERED',preset=w['preset'],date_from=w['start'],date_to=w['end'],as_of=w['as_of'],clock_basis=w['clock_basis'],offset=w['offset'],granularity=w['granularity'],mode=w['mode'],window_id=w['window_id'])
    response=client.get('/api/qc/candidates/qc:R',params=params)
    assert response.status_code==404
    response=client.get('/api/qc/candidates/qc:R',params=params|{'date_to':'2026-07-09T12:00:00.000001+00:00'})
    assert response.status_code==409
    response=client.get('/api/qc/candidates/qc:R',params=list(params.items())+[('as_of',w['as_of'])])
    assert response.status_code==422
    assert db.query(QCRuleResult).count()==0 and client.post('/api/qc/candidates/qc:R').status_code==405


def test_readonly_snapshot_existing_postgres_transaction_must_be_consistent():
    class FakeDB:
        def __init__(self,isolation,readonly): self.isolation=isolation;self.readonly=readonly;self.commands=[]
        def get_bind(self): return N(dialect=N(name='postgresql'))
        def in_transaction(self): return True
        def execute(self,sql):
            self.commands.append(str(sql));return N(scalar_one=lambda:self.isolation if 'isolation' in str(sql) else self.readonly)
    valid=FakeDB('repeatable read','on')
    assert q.begin_readonly_snapshot(valid)['read_only'] is True
    assert all(c.startswith('SHOW') for c in valid.commands)
    with pytest.raises(q.CandidateError,match='REQUIRES_FRESH'): q.begin_readonly_snapshot(FakeDB('read committed','on'))


def candidate_api_fixture(db,monkeypatch,*,with_ai=True):
    """Reusable API harness: source-authority DTO boundary is explicitly isolated.

    It runs the real stored Rule/AI lookup, definition version check and GET
    route. It does not claim that a fixture receipt is a production approval.
    """
    obs=observation();r,d=rule(obs,'3',kind='DE')
    db.add(QCRuleDefinition(qc_rule_id=d.qc_rule_id,rule_version=d.rule_version,qc_rule_name='Delay',algorithm_description='ISOLATED',threshold_definition=d.threshold_definition))
    fields=dict(vars(r));fields['qc_stage']='RULE'
    db.add(QCRuleResult(**fields))
    neighbors=[]
    for i in range(16):
        if i==7:continue
        original,binding,receipt,raw=fixture();stamp=datetime(2026,7,9,10,i,tzinfo=UTC)
        original.observation_id=f'O{i+1}';original.timestamp_utc=stamp.replace(tzinfo=None)
        proof=binding.payload;proof['timestamp_utc']=stamp.isoformat()
        proof['available_at']=proof['qc_available_at']=(stamp+timedelta(minutes=5)).isoformat()
        proof['source_receive_timestamp_utc']=proof['available_at'];binding.bound_at_utc=stamp+timedelta(minutes=6)
        proof['source_row_locator']=binding.source_row_locator=f'parquet_row_group=0;row_index={i+1}'
        receipt['observations']={original.observation_id:proof}
        current=q._registered_row(original,binding,receipt,raw,window())
        if i==0: current=obs
        neighbors.append(current)
    if with_ai:
        ai,model=prediction(obs)
        db.add(AIPredictionResult(**(vars(ai)|{'explanation':json.dumps(ai.explanation)})));db.add(ModelRegistry(**vars(model)))
    db.commit()
    def fixture_reader(db,window,station='',item='',**kwargs):
        oid=kwargs.get('observation_id');rows=[r for r in neighbors if not oid or r['observation_id']==oid]
        return dict(rows=rows,status='AVAILABLE',selected_count=len(rows),scanned_count=len(rows),truncated=False,excluded_counts={},missing_tables=[])
    monkeypatch.setattr(q,'registered_rows',fixture_reader)
    app=FastAPI();app.include_router(routes_qc_candidates.router);app.dependency_overrides[get_db]=lambda:db
    w=window();params=dict(source=w['source'],mode=w['mode'],preset=w['preset'],date_from=w['start'],date_to=w['end'],as_of=w['as_of'],clock_basis=w['clock_basis'],offset=w['offset'],granularity=w['granularity'],window_id=w['window_id'])
    return TestClient(app),params,obs


@pytest.mark.parametrize('with_ai',[True,False])
def test_actual_candidate_get_stored_ai_gap_delay_and_no_final_write(db,monkeypatch,with_ai):
    client,params,obs=candidate_api_fixture(db,monkeypatch,with_ai=with_ai)
    response=client.get('/api/qc/candidates/qc:R1',params=params)
    assert response.status_code==200,response.text
    packet=response.json()
    assert packet['window']['window_id']==params['window_id'] and packet['observation']['value']==25
    assert packet['observation']['delay_minutes']==5 and packet['observation']['delay_flag']=='3'
    assert packet['surrounding_timeseries']['gaps'][0]['value'] is None
    assert packet['surrounding_timeseries']['interpolation'] is False
    assert packet['ai']['status']==('AVAILABLE' if with_ai else 'NO_MODEL')
    assert not packet['ai']['inference_executed'] and packet['workflow']['status']=='NO_LINKED_WORKFLOW'
    assert packet['provenance']['mutations']==[] and packet['provenance']['query_snapshot']['read_only_service']
    assert db.query(QCRuleResult).count()==1
    assert client.get('/api/qc/candidates/qc:R1',params=params|{'station':'WRONG'}).status_code==422


def archive_fixture(tmp_path,monkeypatch):
    import hashlib
    import pyarrow as pa
    import pyarrow.parquet as pq
    from app.services import lake_browser as lake,qc_workspace
    view=tmp_path/'immutable-fixture';view.mkdir()
    rows=[]
    for i in range(16):
        if i==7:continue
        rows.append(dict(OBS_POST_ID='ST ',OBS_ITEM_CODE='TEMP ',OBS_TIME=f'2026-07-09 10:{i:02}:00',OBS_VALUE='' if i==3 else f'{20+i/10:.1f}',
            QC_FLAG='G ',MQC_FLAG=None,N1_AQC_FLAG='',WATER_STEP='10',FR_DEPTH='01',TO_DEPTH=None))
    rows.append(dict(rows[0],WATER_STEP='11',OBS_VALUE='999'))
    path=view/'raw.parquet';pq.write_table(pa.Table.from_pylist(rows),path)
    sha=hashlib.sha256(path.read_bytes()).hexdigest()
    asset=dict(parquet_path=str(path),parquet_sha256=sha,source_sha256='f'*64,month='2026-07',source_group='GR_OBS_ST')
    monkeypatch.setattr(lake,'context',lambda:(view,view/'unused'))
    def verified_files(view,scope):
        stat=path.stat();lake.verify_file(str(path),stat.st_mtime_ns,stat.st_size,sha)
        return [asset]
    monkeypatch.setattr(qc_workspace,'_files',verified_files)
    w=resolve_window('GR_OBS_ST','custom','2026-07-09 00:00:00','2026-07-09 10:12:00',now=NOW)
    return q.archive_candidate_id(dict(parquet_sha256=sha,file_row_number=0)),w,view,path


def test_actual_archive_parquet_locator_typed_depth_gap_null_future_and_no_db_mix(tmp_path,monkeypatch):
    cid,w,view,path=archive_fixture(tmp_path,monkeypatch)
    packet=q.archive_detail(None,cid,w,view.name,station='ST',item='TEMP')
    observation=packet['observation'];series=packet['surrounding_timeseries']
    assert packet['kind']=='ARCHIVE_RAW_SAMPLE' and observation['station_literal']=='ST '
    assert observation['source_qc_raw']=='G ' and observation['source_mqc_raw'] is None
    assert observation['received_time'] is observation['delay_minutes'] is None
    assert len(series['rows'])==12 and len(series['gaps'])==1
    assert all(r['depth_step']=='10' and r['value']!=999 for r in series['rows'])
    assert max(r['observation_time'] for r in series['rows'])=='2026-07-09 10:12:00'
    assert any(r['value_raw']=='' and r['value'] is None and not r['is_gap'] for r in series['rows'])
    assert packet['ai']['results']==[] and packet['workflow']['status']=='NO_LINKED_WORKFLOW'
    assert packet['provenance']['historical_availability_asserted'] is False and packet['capabilities']==[]
    with pytest.raises(q.CandidateError,match='SCOPE_MISMATCH'): q.archive_detail(None,cid,w,view.name,station='WRONG')
    with pytest.raises(q.CandidateError,match='SNAPSHOT_CHANGED'): q.archive_detail(None,cid,w,'OTHER')


def test_archive_file_changed_between_reads_fails_before_result(tmp_path,monkeypatch):
    from contextlib import contextmanager
    from app.services import lake_browser as lake
    from fastapi import HTTPException
    cid,w,view,path=archive_fixture(tmp_path,monkeypatch);original=lake.connection;calls=[]
    @contextmanager
    def changed_connection():
        with original() as connection: yield connection
        calls.append(1)
        if len(calls)==2:path.write_bytes(path.read_bytes()+b'CHANGED')
    monkeypatch.setattr(lake,'connection',changed_connection)
    with pytest.raises(HTTPException) as error:q.archive_detail(None,cid,w,view.name)
    assert error.value.status_code==409


def workflow_fixture(obs,status='PENDING'):
    scope={k:obs[k] for k in ('station_id','sensor_id','variable_code','unit','sensor_episode_id')}|dict(period_start='2026-07-09T09:00:00Z',period_end='2026-07-09T11:00:00Z',as_of='2026-07-09T11:00:00Z')
    references=[dict(model=model,pk={'observation_id':obs['observation_id']}) for model in ('ObservationStandard','SourceObservationBinding')]
    return N(workflow_id='WF',request_key='fixture',status=status,revision=0,input_sha256='1'*64,recommendation_sha256='2'*64,
        payload={'scope':scope,'bundle':{'references':references}},recommendation={},requested_by='operator',approval_history_id=None,result=None,
        created_at=datetime(2026,7,9,10,8,tzinfo=UTC),updated_at=datetime(2026,7,9,10,8,tzinfo=UTC))


def workflow_db(run):
    class Query:
        def filter(self,*args): return self
        def filter_by(self,**kwargs): return self
        def order_by(self,*args): return self
        def limit(self,*args): return self
        def all(self):
            result=[run] if self.model is q.AgentWorkflowRun and not getattr(self,'returned',False) else []
            self.returned=True
            return result
    class DB:
        def query(self,model): value=Query();value.model=model;return value
    return DB()


@pytest.mark.parametrize('status,role,enabled',[
    ('PENDING','reviewer',{'APPROVED','REJECTED','CANCEL'}),('PENDING','viewer',set()),
    ('APPROVED','operator',{'RESUME','CANCEL'}),('REJECTED','reviewer',set()),('COMPLETED','admin',set())])
def test_existing_workflow_capability_state_roles_hash_revision_and_no_final_qc(monkeypatch,status,role,enabled):
    from app.agents import multi_agent_workflow as workflow
    obs=observation();run=workflow_fixture(obs,status)
    monkeypatch.setattr(workflow,'_integrity',lambda *args,**kwargs:None)
    monkeypatch.setattr(settings,'API_IDENTITIES',{'isolated':{'role':'reviewer','token':'ISOLATED_TEST_ONLY'}})
    view,capabilities,history=q.workflow_capabilities(workflow_db(run),obs,window(),Actor('operator',role))
    assert view['status']==status and {r['action'] for r in capabilities if r['enabled']}==enabled
    assert all(r['body_template']['expected_revision']==0 and r['body_template']['expected_recommendation_sha256']=='2'*64 and r['body_template']['request_key'] for r in capabilities)
    assert all(r['definitive_qc'] is False and r['source_approval_granted'] is False for r in capabilities)


def test_no_account_and_future_unbound_workflow_remain_unavailable(monkeypatch):
    from app.agents import multi_agent_workflow as workflow
    obs=observation();run=workflow_fixture(obs)
    monkeypatch.setattr(workflow,'_integrity',lambda *a,**kw:None);monkeypatch.setattr(settings,'API_IDENTITIES',{})
    view,caps,_=q.workflow_capabilities(workflow_db(run),obs,window(),Actor('operator','reviewer'))
    assert view['status']=='PENDING' and all(not c['enabled'] for c in caps)
    assert all(c['reason']=='OPERATOR_AUTHENTICATION_NOT_CONFIGURED' for c in caps)
    run.updated_at=NOW+timedelta(microseconds=1)
    assert q.workflow_capabilities(workflow_db(run),obs,window())[0]['status']=='UNVERIFIED'
    run=workflow_fixture(obs);run.payload['bundle']['references'].pop()
    with pytest.raises(q.CandidateError,match='REFERENCES_UNVERIFIED'):q.validate_linked_workflow(None,run,obs,window())


def evidence_metadata(obs,event_at='2026-07-09T09:00:00Z'):
    return dict(observation_id=obs['observation_id'],authority_sha256=obs['authority_sha256'],scope=q._scope(obs),
        event_at=event_at,period_start='2026-07-09T09:00:00Z',period_end='2026-07-09T11:00:00Z',
        available_at='2026-07-09T10:07:00Z',version_available_at='2026-07-09T10:07:00Z')


def evidence_fixture(db,obs):
    inspection=DailyInspectionReport(inspection_id='I1',station_id='ST',sensor_id='S',report_date=datetime(2026,7,9,9),
        equipment_status='REPORTED_READY',communication_status='CHECKED',power_status='CHECKED',issue_found=False,issue_detail='Isolated actual stored report',action_taken='Checked')
    db.add(inspection);db.flush()
    link=evidence_metadata(obs)|dict(inspection_id='I1',record_sha256=q.record_content_sha256(inspection))
    for index,kind in enumerate(('INSTALLATION','REPLACEMENT','CALIBRATION')):
        row=OperationLog(station_id='ST',sensor_id='S',event_time=datetime(2026,7,8,9,index),event_type='ISOLATED_'+kind,action_taken='Isolated equipment event')
        db.add(row);db.flush()
        metadata=evidence_metadata(obs,event_at=f'2026-07-08T09:0{index}:00Z')
        metadata['record_sha256']=q.record_content_sha256(row,excluded_fields=('event_detail',))
        metadata['equipment_event']=dict(kind=kind,event_at=metadata['event_at'],physical_sensor_id=obs['physical_sensor_id'],sensor_episode_id=obs['sensor_episode_id'])
        if index==0:metadata['inspection_refs']=[link]
        row.event_detail=json.dumps(metadata)
    document=DocumentIndex(document_id='D1',chunk_id='C1',document_type='GUIDE',document_title='Isolated exact linked reference',chunk_text='Stored evidence text',
        page_no=1,related_station_id='ST',related_sensor_id='S',related_variable_code='AIR_TEMP')
    db.add(document);db.flush()
    document.metadata_json=evidence_metadata(obs)|dict(record_sha256=q.record_content_sha256(document,excluded_fields=('metadata_json',)),source_sha256='f'*64,inspection_refs=[link])
    db.commit()
    return inspection,document


def test_exact_content_hash_version_links_show_inspection_rag_and_three_equipment_dates(db):
    obs=observation();inspection,document=evidence_fixture(db,obs)
    result=q._linked_evidence(db,obs,window());epoch=q.equipment_epoch(obs,result)
    assert len(result['operations']['rows'])==3 and result['inspection']['rows'][0]['inspection_id']=='I1'
    assert result['rag']['rows'][0]['text']=='Stored evidence text'
    assert epoch['install_date']=='2026-07-08T09:00:00Z' and epoch['replacement_date']=='2026-07-08T09:01:00Z'
    assert epoch['calibration_date']=='2026-07-08T09:02:00Z'
    assert epoch['approved_equipment_history'] is False and not result['excluded_counts']
    assert len(result['inspection']['rows'])==1  # same report linked by operation and document


@pytest.mark.parametrize('change',['report_content','future_version','wrong_physical_sensor','naive_event','document_text'])
def test_inspection_and_equipment_hash_clock_scope_mismatches_fail_closed(db,change):
    obs=observation();inspection,document=evidence_fixture(db,obs)
    if change=='report_content': inspection.issue_detail='Changed after linked version'
    if change=='document_text': document.chunk_text='Changed after linked version'
    if change in {'future_version','wrong_physical_sensor','naive_event'}:
        for operation in db.query(OperationLog).all():
            metadata=json.loads(operation.event_detail)
            if change=='future_version':metadata['version_available_at']='2026-07-31T00:00:00Z'
            if change=='wrong_physical_sensor':metadata['equipment_event']['physical_sensor_id']='OTHER'
            if change=='naive_event':metadata['equipment_event']['event_at']='2026-07-08T09:00:00'
            operation.event_detail=json.dumps(metadata)
    db.commit();result=q._linked_evidence(db,obs,window())
    assert result['excluded_counts']
    if change=='report_content': assert result['inspection']['rows']==[]
    if change=='document_text': assert result['rag']['rows']==[]
    if change in {'future_version','wrong_physical_sensor','naive_event'}:
        assert q.equipment_epoch(obs,result)['install_date'] is None


def test_current_unbound_sensor_dates_and_naive_inspection_are_not_historical_proof(db):
    obs=observation()
    db.add(SensorMetadata(sensor_id='S',station_id='ST',variable_code='AIR_TEMP',install_date=datetime(2026,7,1),calibration_date=datetime(2026,7,2),replacement_date=datetime(2026,7,3)))
    db.add(DailyInspectionReport(inspection_id='UNBOUND',station_id='ST',sensor_id='S',report_date=datetime(2026,7,9),issue_detail='Legacy unversioned report'))
    db.commit();result=q._linked_evidence(db,obs,window());epoch=q.equipment_epoch(obs,result)
    assert result['inspection']['status']=='UNVERIFIED' and result['inspection']['rows']==[]
    assert epoch['install_date'] is epoch['replacement_date'] is epoch['calibration_date'] is None


def test_workflow_bound_to_other_observation_is_no_match_not_partial(monkeypatch):
    from app.agents import multi_agent_workflow as workflow
    obs=observation();other=copy.deepcopy(obs)|{'observation_id':'O2'};run=workflow_fixture(obs)
    calls=[];monkeypatch.setattr(workflow,'_integrity',lambda *a,**kw:calls.append(1))
    assert q.validate_linked_workflow(None,run,other,window()) is None
    cache={}
    assert q.validate_linked_workflow(None,run,obs,window(),workflow_cache=cache)['status']=='PENDING'
    assert q.validate_linked_workflow(None,run,obs,window(),workflow_cache=cache)['status']=='PENDING'
    assert len(calls)==1
    q.verify_workflow_cache(None,cache);assert len(calls)==2


def test_two_observation_review_census_counts_one_pending_without_false_partial(db,monkeypatch):
    from app.agents import multi_agent_workflow as workflow
    obs=observation();other=copy.deepcopy(obs)|{'observation_id':'O2'}
    run=q.AgentWorkflowRun(**vars(workflow_fixture(obs)));db.add(run);db.flush()
    calls=[];monkeypatch.setattr(workflow,'_integrity',lambda *a,**kw:calls.append(1))
    result=q.registered_review_states(db,[obs,other],window())
    assert result['state']=='AVAILABLE' and result['excluded_counts']=={}
    assert len(result['rows'])==1 and result['rows'][0]['observation_id']=='O1' and result['rows'][0]['status']=='PENDING'
    assert calls==[1]


def test_detail_rechecks_definition_after_evidence_lookup_before_return(db,monkeypatch):
    client,params,obs=candidate_api_fixture(db,monkeypatch)
    linked=q._linked_evidence
    def changed(db,observation,window):
        result=linked(db,observation,window)
        definition=db.query(QCRuleDefinition).first()
        definition.threshold_definition={'kind':'DE','parameters':{'max_delay_seconds':999}}
        db.flush()
        return result
    monkeypatch.setattr(q,'_linked_evidence',changed)
    response=client.get('/api/qc/candidates/qc:R1',params=params)
    assert response.status_code==422 and response.json()['detail']['code']=='RULE_DEFINITION_CHANGED_DURING_QUERY'


@pytest.mark.parametrize('ambiguous',[False,True])
def test_detail_and_overview_scan_past_one_hundred_unrelated_workflows(db,monkeypatch,ambiguous):
    from app.agents import multi_agent_workflow as workflow
    obs=observation();instances=[]
    for index in range(102):
        current=workflow_fixture(obs);current.workflow_id=f'WF{index:04}';current.request_key=f'key-{index}'
        if index<101:
            other_id=f'OTHER{index}'
            for ref in current.payload['bundle']['references']:ref['pk']['observation_id']=other_id
        if ambiguous and index==0:
            for ref in current.payload['bundle']['references']:ref['pk']['observation_id']=obs['observation_id']
        run=q.AgentWorkflowRun(**vars(current));instances.append(run);db.add(run)
    db.flush()
    monkeypatch.setattr(workflow,'_integrity',lambda *a,**kw:None)
    monkeypatch.setattr(settings,'API_IDENTITIES',{'isolated':{'role':'reviewer','token':'ISOLATED_TEST_ONLY'}})
    review=q.registered_review_states(db,[obs],window())
    detail,caps,_=q.workflow_capabilities(db,obs,window(),Actor('isolated','reviewer'))
    assert detail['scanned_workflows']==102 and detail['truncated'] is False
    if ambiguous:
        assert review['state']=='PARTIAL' and review['rows']==[]
        assert detail['status']=='AMBIGUOUS' and caps==[]
    else:
        assert review['state']=='AVAILABLE' and review['excluded_counts']=={}
        assert review['rows'][0]['workflow_id']=='WF0101' and detail['status']=='PENDING'
        assert any(c['enabled'] for c in caps)


def test_exact_observation_exclusions_align_queue_detail_and_preserve_other_observation(db,monkeypatch):
    from app.agents import multi_agent_workflow as workflow
    from app.services.qc_overview import bind_queue_reviews
    obs=observation();other=copy.deepcopy(obs)|{'observation_id':'O2'};instances=[]
    for index,target in enumerate((obs,obs,other)):
        current=workflow_fixture(target);current.workflow_id=f'WF{index}';current.request_key=f'key-{index}'
        if index==1:current.updated_at=NOW+timedelta(microseconds=1)
        run=q.AgentWorkflowRun(**vars(current));instances.append(run);db.add(run)
    db.flush();monkeypatch.setattr(workflow,'_integrity',lambda *a,**kw:None)
    monkeypatch.setattr(settings,'API_IDENTITIES',{'isolated':{'role':'reviewer','token':'ISOLATED_TEST_ONLY'}})
    result=q.registered_review_states(db,[obs,other],window())
    assert result['state']=='PARTIAL' and len(result['rows'])==1 and result['rows'][0]['observation_id']=='O2'
    assert result['excluded_by_observation']=={'O1':{'POST_CUTOFF_WORKFLOW_REVISION':1}}
    assert len(result['excluded_by_observation'])<=2
    queue=[dict(observation_id=target['observation_id']) for target in (obs,other)]
    verified,excluded=bind_queue_reviews(queue,[obs,other],result)
    assert queue[0]['review_status']=='UNVERIFIED' and queue[0]['review_reason_scope']=='EXACT_OBSERVATION'
    assert queue[1]['review_status']=='PENDING' and queue[1]['review_workflow_id']=='WF2'
    assert [r['observation_id'] for r in verified]==['O2']
    held,caps,_=q.workflow_capabilities(db,obs,window(),Actor('isolated','reviewer'))
    assert held['status']=='UNVERIFIED' and caps==[]
    accepted,caps,_=q.workflow_capabilities(db,other,window(),Actor('isolated','reviewer'))
    assert accepted['status']=='PENDING' and any(c['enabled'] for c in caps)


@pytest.mark.parametrize('bad_period',['2026-07-09T09:00:00','NOT_A_CLOCK'])
def test_explicit_other_observation_references_are_no_match_before_malformed_period(bad_period,monkeypatch):
    from app.agents import multi_agent_workflow as workflow
    obs=observation();other=copy.deepcopy(obs)|{'observation_id':'O2'};run=workflow_fixture(other)
    run.payload['scope']['period_start']=bad_period
    monkeypatch.setattr(workflow,'_integrity',lambda *a,**kw:None)
    assert q.validate_linked_workflow(None,run,obs,window()) is None
    with pytest.raises(q.CandidateError,match='EXPLICIT_OFFSET_CLOCK_REQUIRED'):
        q.validate_linked_workflow(None,run,other,window())


@pytest.mark.parametrize('kind',['DIRECTION','VECTOR','PROFILE'])
def test_typed_quantity_never_becomes_scalar_good_or_normal_denominator(kind):
    obs,binding,receipt,raw=fixture()
    binding.payload['quantity_kind']=kind
    with pytest.raises(q.CandidateError,match='SCALAR_VALUE_MISMATCH_OR_UNSUPPORTED_REPRESENTATION'):
        q._registered_row(obs,binding,receipt,raw,window())
