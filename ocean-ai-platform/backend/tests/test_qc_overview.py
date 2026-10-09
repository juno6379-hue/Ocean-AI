"""Operational clock, aggregate scope and truthful empty/partial QC regressions."""
from datetime import datetime,timedelta,timezone
import json
import re

import pytest
from fastapi import HTTPException
from sqlalchemy import event

from app.models.domain import StationMetadata
from app.services import qc_overview as qc
from app.services import qc_workspace as archive
from app.services import qc_candidate_review as candidates
from test_qc_workspace import case as source_case

NOW=datetime(2026,10,9,15,41,20,tzinfo=timezone(timedelta(hours=5,minutes=30)))
ARCHIVE_ARGS=dict(source='GD_OBS_VBU',preset='custom',date_from='2026-07-09T12:01:00',date_to='2026-07-09T12:02:00')


def freeze_scope_census(case):
    view=case[2]
    proof=dict(checks=[dict(check=name,passed=True) for name in (
        'observation_accounting','one_row_per_source_station_item_depth_month','parquet_reread')],
        artifact_sha256={name:qc.file_hash(view/name) for name in (
            'station-item-month-validation.parquet','file-only-timeseries.duckdb')},
        scope='ISOLATED_TEST_FIXTURE_NOT_OPERATIONAL_APPROVAL')
    (view/'verification.json').write_text(json.dumps(proof),encoding='utf-8')
    return proof


@pytest.fixture
def case(source_case):
    freeze_scope_census(source_case)
    yield source_case


def packet(case,monkeypatch,**extra):
    monkeypatch.setattr(qc,'reference_records',archive.reference_records)
    response=case[0].get('/api/qc/overview',params={**ARCHIVE_ARGS,**extra})
    assert response.status_code==200,response.text
    return response.json()


def test_backend_today_and_presets_use_actual_offset_and_calendar_boundaries(monkeypatch):
    monkeypatch.setattr(qc,'server_now',lambda:NOW)
    today=qc.resolve_window()
    assert today['start']=='2026-10-09T00:00:00+05:30'
    assert today['end']==NOW.isoformat() and today['offset']=='+05:30'
    assert today['granularity']=='hour' and today['source']=='REGISTERED'
    assert qc.validate_window_identity(today)==today
    assert qc.resolve_window(preset='yesterday')['start']=='2026-10-08T00:00:00+05:30'
    assert qc.resolve_window(preset='yesterday')['end']=='2026-10-08T23:59:59.999999+05:30'
    assert qc.resolve_window(preset='7d')['start']=='2026-10-03T00:00:00+05:30'
    assert qc.resolve_window(preset='30d')['start']=='2026-09-10T00:00:00+05:30'
    assert qc.resolve_window(preset='7d')['granularity']=='day'
    context=qc.context();assert context['default_preset']=='today' and context['default_source']=='REGISTERED'
    assert context['server_now']==NOW.isoformat()
    sha=context.pop('result_sha256');assert qc.digest(context)==sha


def test_display_tones_2_changes_colors_without_source_codebook_or_flag_remapping():
    catalog=qc.flag_catalog();flags={row['code']:row for row in catalog}
    assert {code:row['semantic'] for code,row in flags.items()}==dict(
        **{'1':'GOOD','3':'SUSPECT','4':'BAD','9':'MISSING'},NOT_EVALUATED='NOT_EVALUATED',UNKNOWN='UNKNOWN')
    assert flags['9']['color']=='#a855f7' and flags['UNKNOWN']['color']=='#9ca3af'
    assert flags['NOT_EVALUATED']['color']=='#94a3b8'
    assert all(row['color_policy']=='QC_DISPLAY_TONES_2' for row in catalog)


def test_archive_native_window_is_explicit_and_never_inherits_operating_timezone(monkeypatch):
    monkeypatch.setattr(qc,'server_now',lambda:NOW)
    window=qc.resolve_window(**ARCHIVE_ARGS)
    assert window['offset'] is None and window['mode']=='ARCHIVE'
    assert window['clock_basis']=='UNAPPROVED_NATIVE_SOURCE_CLOCK'
    assert qc.validate_window_identity(window)==window
    for args in (dict(source='GD_OBS_VBU'),dict(source='REGISTERED',preset='custom',date_from='2026-10-09T00:00:00',date_to=NOW.isoformat()),
        dict(source='REGISTERED',preset='custom',date_from=NOW.isoformat(),date_to=(NOW+timedelta(seconds=1)).isoformat()),
        {**ARCHIVE_ARGS,'date_to':'2026-07-09T12:02:00+09:00'},
        {**ARCHIVE_ARGS,'date_from':'2026-05-01T00:00:00'},
        {**ARCHIVE_ARGS,'date_to':'2026-07-09T12:00:00'}):
        with pytest.raises(HTTPException):qc.resolve_window(**args)
    altered=dict(window,end='2026-07-09T12:03:00')
    with pytest.raises(HTTPException) as err:qc.validate_window_identity(altered)
    assert err.value.status_code==409
    altered['window_id']=qc.digest({k:altered[k] for k in qc.WINDOW_KEYS})
    with pytest.raises(HTTPException):qc.validate_window_identity(altered)


def test_one_exact_custom_window_drives_all_archive_widgets(case,monkeypatch):
    data=packet(case,monkeypatch)
    assert data['total_observations']==5
    assert data['window']['start']==ARCHIVE_ARGS['date_from'] and data['window']['end']==ARCHIVE_ARGS['date_to']
    assert data['summary']['missing']['count']==1 and data['summary']['missing']['denominator']==5
    assert data['summary']['missing']['rate']==20
    assert data['summary']['normal']['count'] is None and data['summary']['bad']['rate'] is None
    assert sum(r['count'] for r in data['flag_distribution'])==5
    assert next(r for r in data['flag_distribution'] if r['code']=='UNKNOWN')['count']==5
    assert sum(r['total'] for r in data['station_variable_matrix'])==5
    assert len(data['quality_trend'])==1 and data['quality_trend'][0]['total']==5
    assert data['quality_trend'][0]['start']==ARCHIVE_ARGS['date_from']
    assert data['quality_trend'][0]['end']==ARCHIVE_ARGS['date_to']
    assert len(data['archive_samples']['rows'])==5
    assert all(r['id'].startswith('archive:') and r['kind']=='ARCHIVE_RAW_SAMPLE' for r in data['archive_samples']['rows'])
    assert data['review_queue']['rows']==[] and data['rule_qc_counts']['result_count']==0
    assert len(data['rule_qc_counts']['items'])==12
    assert data['states']['ai']=='NOT_RUN' and data['states']['model']=='NO_MODEL'
    assert data['provenance']['simulated_included'] is False
    assert data['provenance']['expected_transmission_denominator'] is None
    literals={r['literal'] for r in data['provenance']['archive_qc_literal_distribution']}
    assert None in literals and '' in literals and ' G ' in literals and 'G ' in literals
    sha=data.pop('result_sha256');assert qc.digest(data)==sha


def test_common_station_network_sea_and_flag_filter_apply_to_all_widgets(case,monkeypatch):
    data=packet(case,monkeypatch,station_id='A',variable_code='TEMP',network='TIDE',sea='WEST')
    assert data['total_observations']==4
    assert data['quality_trend'][0]['total']==4 and len(data['station_variable_matrix'])==1
    assert all(r['station_code']=='A' for r in data['archive_samples']['rows'])
    assert packet(case,monkeypatch,network='__UNREGISTERED__')['total_observations']==1
    empty=packet(case,monkeypatch,flag='4')
    assert empty['total_observations']==0 and empty['states']['overall']=='NO_DATA'
    assert empty['summary']['missing']['rate'] is None
    assert empty['archive_samples']['rows']==[] and empty['station_variable_matrix']==[]
    assert all(r['total']==0 for r in empty['quality_trend'])


def test_verified_rule_flags_do_not_read_source_literal_and_queue_is_bounded():
    window=qc.resolve_window('REGISTERED','custom','2026-07-09T00:00:00+00:00','2026-07-09T12:00:00+00:00',now=NOW)
    scope=dict(station_id='',variable_code='',network='',sea='',flag='')
    rows=[dict(observation_id=str(n),station_id='S',variable_code='TEMP',sensor_id='SID',physical_sensor_id='P',
        observation_time=f'2026-07-09T10:{n:02d}:00+00:00',available_at='2026-07-09T11:00:00+00:00',value=n,unit='C',
        authority_sha256='a'*64,source_group='REAL',qc_source_literals={'source_qc_raw':'BAD'}) for n in range(5)]
    results=[dict(observation_id=str(n),qc_result_id='R'+str(n),result_flag=code,rule_type='SP',rule_id='RULE-SP',
        rule_name='Spike',evaluation_status='MISSING' if code=='9' else 'EVALUATED') for n,code in enumerate(('1','3','4','9'))]
    aggregate=qc.aggregate_registered(rows,results,window,scope,limit=2,offset=0)
    assert {r['code']:r['count'] for r in aggregate['distribution']}=={'1':1,'3':1,'4':1,'9':1,'NOT_EVALUATED':0,'UNKNOWN':1}
    assert [r['flag'] for r in aggregate['queue']['rows']]==['4','3'] and aggregate['queue']['total']==3
    filtered=qc.aggregate_registered(rows,results,window,{**scope,'flag':'3'},limit=2)
    assert sum(r['total'] for r in filtered['groups'])==1 and sum(r['total'] for r in filtered['trend'])==1
    assert filtered['queue']['total']==1


def test_warm_cache_rechecks_manifest_hash_and_response_has_only_fifteen_samples(case,monkeypatch):
    assert packet(case,monkeypatch)['query']['raw_rows_sent']==5
    assert packet(case,monkeypatch)['total_observations']==5
    case[1].write_bytes(case[1].read_bytes()+b' ')
    response=case[0].get('/api/qc/overview',params=ARCHIVE_ARGS)
    assert response.status_code==409


def test_overview_and_context_get_only_strict_filters_and_zero_writes(case,monkeypatch):
    db,engine=case[3],case[4];db.add(StationMetadata(station_id='PENDING',station_name='Pending'))
    statements=[]
    listener=lambda conn,cursor,statement,parameters,context,executemany:statements.append(statement)
    event.listen(engine,'before_cursor_execute',listener)
    try:
        data=packet(case,monkeypatch);assert data['provenance']['production_writes']==0 and db.new
        assert not any(re.match(r'\s*(INSERT|UPDATE|DELETE|CREATE|ALTER)',s,re.I) for s in statements)
        assert case[0].post('/api/qc/overview',json={}).status_code==405
        assert case[0].post('/api/qc/context',json={}).status_code==405
        assert case[0].get('/api/qc/context?source=GD_OBS_VBU').status_code==422
        assert case[0].get('/api/qc/overview?source=REGISTERED&source=GD_OBS_VBU').status_code==422
        for extra in ({'extra':'x'},{'queue_limit':31},{'queue_offset':1001},{'flag':'FAKE'}):
            assert case[0].get('/api/qc/overview',params={**ARCHIVE_ARGS,**extra}).status_code==422
    finally:event.remove(engine,'before_cursor_execute',listener)


def test_default_registered_source_does_not_scan_unbound_legacy_observations(case,monkeypatch):
    monkeypatch.setattr(qc,'reference_records',archive.reference_records)
    response=case[0].get('/api/qc/overview')
    assert response.status_code==200,response.text
    data=response.json()
    assert data['source']=='REGISTERED' and data['window']['preset']=='today'
    assert data['total_observations']==0 and data['states']['overall']=='NO_DATA'
    assert data['summary']['normal']['rate'] is None and data['summary']['pending']['count']==0
    assert data['archive_samples'] is None


def test_query_error_is_not_empty_or_secret_exposure(case,monkeypatch):
    def fail(db):raise HTTPException(503,'QC 등록 원장 조회 실패')
    monkeypatch.setattr(archive,'registry_counts',fail)
    response=case[0].get('/api/qc/overview')
    assert response.status_code==503


def _stream_case(monkeypatch,total):
    def batches(db,window,station='',item='',*,batch_size=500,receipt_cache=None,station_scope=None):
        for base in range(0,total,batch_size):
            rows=[dict(observation_id=str(n),station_id='A',variable_code='TEMP',sensor_id='S',physical_sensor_id='P',
                observation_time='2026-07-09T01:00:00+00:00',available_at='2026-07-09T01:01:00+00:00',value=n,unit='C',
                authority_sha256=qc.digest(n),source_group='ISOLATED_TEST_FIXTURE') for n in range(base,min(total,base+batch_size))]
            yield dict(rows=rows,selected_count=total,scanned_count=len(rows),excluded_counts={},missing_tables=[])
    def rule_batches(db,rows,window,*,batch_size=500,definition_cache=None):
        results=[dict(observation_id=r['observation_id'],qc_result_id='R'+r['observation_id'],flag=('1','3','4','9','NOT_EVALUATED')[int(r['observation_id'])%5],
            rule_type='SP',rule_id='SP',rule_name='Spike',evaluation_status='MISSING' if int(r['observation_id'])%5==3 else 'NOT_EVALUATED' if int(r['observation_id'])%5==4 else 'EVALUATED') for r in rows]
        yield dict(rows=results,scanned_count=len(results),excluded_counts={})
    monkeypatch.setattr(candidates,'iter_registered_batches',batches)
    monkeypatch.setattr(candidates,'iter_registered_rule_batches',rule_batches)


def test_full_population_stream_exceeds_old_10000_cap_with_bounded_queue(case,monkeypatch):
    monkeypatch.setattr(qc,'reference_records',archive.reference_records)
    _stream_case(monkeypatch,10501)
    response=case[0].get('/api/qc/overview',params=dict(source='REGISTERED',preset='custom',date_from='2026-07-09T00:00:00+00:00',date_to='2026-07-09T02:00:00+00:00',queue_limit=3,queue_offset=1))
    assert response.status_code==200,response.text
    data=response.json()
    assert data['total_observations']==10501
    assert data['provenance']['selected_registered_candidates']==10501
    assert data['provenance']['scanned_registered_candidates']==10501
    assert data['provenance']['complete_population_aggregation'] is True
    assert data['summary']['normal']['count']==2101 and data['summary']['normal']['denominator']==10501
    assert data['review_queue']['total']==6300 and len(data['review_queue']['rows'])==3
    assert all(r['flag']=='4' for r in data['review_queue']['rows'])
    assert data['rule_qc_counts']['result_count']==10501
    assert data['quality_trend'][1]['total']==10501
    assert len(data['station_variable_matrix'])==1


def test_stream_time_budget_partial_never_returns_full_population_rates(case,monkeypatch):
    monkeypatch.setattr(qc,'reference_records',archive.reference_records)
    _stream_case(monkeypatch,1000)
    monkeypatch.setattr(qc,'REGISTERED_TIME_BUDGET_SECONDS',-1)
    response=case[0].get('/api/qc/overview',params=dict(source='REGISTERED',preset='custom',date_from='2026-07-09T00:00:00+00:00',date_to='2026-07-09T02:00:00+00:00'))
    assert response.status_code==200,response.text
    data=response.json()
    assert data['states']['overall']=='PARTIAL' and data['summary']['normal']['rate'] is None
    assert data['review_queue']['total'] is None and data['review_queue']['validated_subset_total']==300
    assert data['provenance']['selected_registered_candidates']==1000
    assert data['provenance']['scanned_registered_candidates']==500
    assert data['provenance']['time_budget_exceeded'] is True
    assert data['provenance']['complete_population_aggregation'] is False
    assert data['provenance']['excluded_counts']['REQUEST_TIME_BUDGET_EXCEEDED']==1
    assert all(r['rate'] is None for r in data['flag_distribution'])


def test_scoped_review_workflows_are_deduplicated_not_final_qc(case,monkeypatch):
    monkeypatch.setattr(qc,'reference_records',archive.reference_records)
    _stream_case(monkeypatch,10)
    counts=archive.registry_counts(case[3]);counts['counts']['agent_workflow_run']=2
    monkeypatch.setattr(archive,'registry_counts',lambda db:counts)
    def reviews(db,rows,window,*,workflow_cache=None):
        return dict(rows=[dict(observation_id=r['observation_id'],workflow_id='W'+str(int(r['observation_id'])//5),
            status='PENDING' if int(r['observation_id'])<5 else 'COMPLETED') for r in rows],excluded_counts={})
    monkeypatch.setattr(candidates,'registered_review_states',reviews)
    params=dict(source='REGISTERED',preset='custom',date_from='2026-07-09T00:00:00+00:00',date_to='2026-07-09T02:00:00+00:00',flag='3')
    response=case[0].get('/api/qc/overview',params=params)
    assert response.status_code==200,response.text
    data=response.json();assert data['total_observations']==2
    assert data['summary']['pending']['count']==1 and data['summary']['completed']['count']==1
    assert data['summary']['pending']['denominator']==2
    assert data['summary']['completed']['stage']=='RECOMMENDATION_WORKFLOW'
    assert data['summary']['completed']['definitive_qc'] is False
    assert data['provenance']['linked_workflow_count']==2
    assert {r['observation_id']:r['review_status'] for r in data['review_queue']['rows']}=={'1':'PENDING','6':'COMPLETED'}
    assert all(r['review_evidence_status']=='VERIFIED_LINKED_WORKFLOW' and r['review_definitive_qc'] is False for r in data['review_queue']['rows'])


def test_unbound_workflow_history_is_unknown_partial_not_zero_completed(case,monkeypatch):
    monkeypatch.setattr(qc,'reference_records',archive.reference_records)
    _stream_case(monkeypatch,5)
    counts=archive.registry_counts(case[3]);counts['counts']['agent_workflow_run']=1
    monkeypatch.setattr(archive,'registry_counts',lambda db:counts)
    monkeypatch.setattr(candidates,'registered_review_states',lambda *args,**kwargs:dict(rows=[],excluded_counts={'WORKFLOW_OBSERVATION_BINDING_UNVERIFIED':1}))
    response=case[0].get('/api/qc/overview',params=dict(source='REGISTERED',preset='custom',date_from='2026-07-09T00:00:00+00:00',date_to='2026-07-09T02:00:00+00:00'))
    assert response.status_code==200,response.text
    data=response.json();assert data['states']['overall']=='PARTIAL'
    assert data['summary']['completed']['count'] is None and data['summary']['pending']['count'] is None
    assert data['provenance']['excluded_counts']['workflow:WORKFLOW_OBSERVATION_BINDING_UNVERIFIED']==1
    assert all(r['review_status']=='UNVERIFIED' and 'WORKFLOW_OBSERVATION_BINDING_UNVERIFIED' in r['review_reasons'] for r in data['review_queue']['rows'])


def test_source_qc_namespace_and_first_stage_results_do_not_assert_training_eligibility():
    catalog=qc.flag_catalog()
    assert {r['code'] for r in catalog}=={'1','3','4','9','NOT_EVALUATED','UNKNOWN'}
    assert next(r for r in catalog if r['code']=='1')['definition_source'].startswith('qc_rule_engine')
    assert all(r['stage'] in ('RULE_QC','UNINTERPRETED') for r in catalog)
    assert not any('training_eligible' in r or r.get('approved') for r in catalog)


def test_duckdb_resource_error_is_503_and_not_empty_success(case,monkeypatch):
    monkeypatch.setattr(qc,'reference_records',archive.reference_records)
    def unavailable(*args):raise qc.duckdb.OutOfMemoryException('private source path')
    monkeypatch.setattr(qc,'_archive_query',unavailable)
    response=case[0].get('/api/qc/overview',params=ARCHIVE_ARGS)
    assert response.status_code==503 and 'private' not in response.text


@pytest.mark.parametrize('status',['PENDING','APPROVED','REJECTED','CANCELLED','RESUMING','COMPLETED'])
def test_queue_binds_actual_status_only_to_exact_observation_and_current_batch(status):
    queue=[dict(observation_id='A',review_status='UNVERIFIED'),dict(observation_id='B',review_status='UNVERIFIED'),dict(observation_id='PREVIOUS',review_status='COMPLETED')]
    observations=[dict(observation_id='A'),dict(observation_id='B')]
    reviews=dict(rows=[dict(observation_id='B',workflow_id='W',status=status,revision=2,available_at='2026-07-09T01:01:00+00:00',recommendation_sha256='a'*64)],excluded_counts={})
    verified,excluded=qc.bind_queue_reviews(queue,observations,reviews)
    assert not excluded and len(verified)==1
    assert queue[0]['review_status']=='NO_LINKED_WORKFLOW'
    assert queue[1]['review_status']==status and queue[1]['review_workflow_id']=='W' and queue[1]['review_workflow_revision']==2
    assert queue[2]==dict(observation_id='PREVIOUS',review_status='COMPLETED')


def test_queue_rejects_wrong_observation_contract_and_ambiguous_reviews():
    queue=[dict(observation_id='A',review_status='UNVERIFIED')];observations=[dict(observation_id='A')]
    verified,excluded=qc.bind_queue_reviews(queue,observations,dict(rows=[dict(observation_id='OTHER',workflow_id='W',status='PENDING')],excluded_counts={}))
    assert verified==[] and excluded['WORKFLOW_READER_SCOPE_OR_STATUS_MISMATCH']==1
    assert queue[0]['review_status']=='UNVERIFIED' and queue[0]['review_workflow_id'] is None
    reviews=dict(rows=[dict(observation_id='A',workflow_id=wid,status='PENDING') for wid in ('W1','W2')],excluded_counts={})
    verified,excluded=qc.bind_queue_reviews(queue,observations,reviews)
    assert verified==[] and excluded['AMBIGUOUS_CANDIDATE_WORKFLOWS']==1
    assert queue[0]['review_status']=='AMBIGUOUS' and queue[0]['review_workflow_id'] is None


def test_registered_queue_has_confirmed_no_workflow_when_global_ledger_empty(case,monkeypatch):
    monkeypatch.setattr(qc,'reference_records',archive.reference_records)
    _stream_case(monkeypatch,5)
    response=case[0].get('/api/qc/overview',params=dict(source='REGISTERED',preset='custom',date_from='2026-07-09T00:00:00+00:00',date_to='2026-07-09T02:00:00+00:00'))
    assert response.status_code==200,response.text
    data=response.json()
    assert data['summary']['pending']['count']==0 and data['summary']['completed']['count']==0
    assert all(r['review_status']=='NO_LINKED_WORKFLOW' for r in data['review_queue']['rows'])


def test_positive_scope_intersection_removes_only_db_codes_absent_from_complete_source(case,monkeypatch):
    db=case[3]
    db.add_all([StationMetadata(station_id='NO_SOURCE_'+str(index),station_name='Isolated missing source',network_type='TIDE',sea_area='WEST') for index in range(20)])
    db.commit();captured=[];query=qc._archive_query
    def recording(*args,**kwargs):
        captured.append(json.loads(args[6]));return query(*args,**kwargs)
    monkeypatch.setattr(qc,'_archive_query',recording)
    data=packet(case,monkeypatch,network='TIDE',sea='WEST')
    assert captured[-1]=={'include':['A']}
    assert data['total_observations']==4 and data['provenance']['invalid_clock_rows_excluded']==2
    assert all(row['station_code']=='A' for row in data['archive_samples']['rows'])
    assert data['provenance']['catalog_census_verification_sha256']==qc.file_hash(case[2]/'verification.json')
    assert data['provenance']['scope_predicate_policy']=='VERIFIED_SOURCE_MONTH_STATION_INTERSECTION'
    # A source-held but unregistered code is retained by its own exact filter.
    unregistered=packet(case,monkeypatch,network='__UNREGISTERED__')
    assert unregistered['total_observations']==1 and unregistered['archive_samples']['rows'][0]['station_code']=='B'


def test_positive_scope_explicit_station_contradiction_and_empty_intersection_are_no_data(case,monkeypatch):
    db=case[3];db.add(StationMetadata(station_id='ABSENT',station_name='Isolated absent source',network_type='OTHER',sea_area='OTHER'));db.commit()
    for filters in (dict(network='TIDE',station_id='B'),dict(network='OTHER'),dict(sea='OTHER')):
        data=packet(case,monkeypatch,**filters)
        assert data['total_observations']==0 and data['archive_samples']['rows']==[]
        assert data['station_variable_matrix']==[] and data['provenance']['invalid_clock_rows_excluded']==0
        assert data['summary']['missing']['rate'] is None


def test_positive_scope_unclassified_registered_code_is_preserved(case,monkeypatch):
    db=case[3];db.add(StationMetadata(station_id='B',station_name='Isolated unclassified source',network_type=None,sea_area=None));db.commit()
    data=packet(case,monkeypatch,sea='__UNASSIGNED__')
    assert data['total_observations']==1 and data['archive_samples']['rows'][0]['station_code']=='B'
    assert data['archive_samples']['rows'][0]['source_qc_raw']=='0'
    assert next(row for row in data['flag_distribution'] if row['code']=='UNKNOWN')['count']==1
    assert data['summary']['normal']['count'] is None


@pytest.mark.parametrize('change',['missing_proof','accounting','grain_census','parquet_reread','catalog_sha','assets_sha','incomplete_catalog'])
def test_positive_scope_incomplete_or_unbound_catalog_fails_closed(case,change,monkeypatch):
    monkeypatch.setattr(qc,'reference_records',archive.reference_records)
    path=case[2]/'verification.json';proof=json.loads(path.read_text(encoding='utf-8'))
    if change=='missing_proof':path.unlink()
    else:
        if change in ('accounting','grain_census','parquet_reread'):
            name={'accounting':'observation_accounting','grain_census':'one_row_per_source_station_item_depth_month','parquet_reread':'parquet_reread'}[change]
            next(row for row in proof['checks'] if row['check']==name)['passed']=False
        elif change=='catalog_sha':proof['artifact_sha256']['station-item-month-validation.parquet']='0'*64
        elif change=='assets_sha':proof['artifact_sha256']['file-only-timeseries.duckdb']='0'*64
        elif change=='incomplete_catalog':
            import pyarrow.parquet as pq
            import pyarrow.compute as pc
            catalog=case[2]/'station-item-month-validation.parquet';table=pq.read_table(catalog)
            pq.write_table(table.filter(pc.equal(table['station_code'],'A')),catalog)
        path.write_text(json.dumps(proof),encoding='utf-8')
    response=case[0].get('/api/qc/overview',params={**ARCHIVE_ARGS,'sea':'WEST'})
    assert response.status_code==409 and response.json()['detail']['code']=='QC_POSITIVE_SCOPE_CATALOG_UNVERIFIED'
    assert response.json()['detail']['mutation_performed'] is False


def test_positive_scope_retains_registered_station_with_only_invalid_clocks(case,monkeypatch):
    import pyarrow as pa
    import pyarrow.parquet as pq
    source=case[1];table=pq.read_table(source)
    row=dict(OBS_POST_ID='C',OBS_ITEM_CODE='TEMP',OBS_TIME='unlocatable-native-clock',
        OBS_VALUE='15',QC_FLAG='BAD',WATER_STEP=None)
    pq.write_table(pa.concat_tables([table,pa.Table.from_pylist([row],schema=table.schema)]),source)
    catalog=case[2]/'station-item-month-validation.parquet';table=pq.read_table(catalog)
    grain=dict(source_group='GD_OBS_VBU',station_code='C',station_name='C',item_code='TEMP',depth_step=None,
        depth_from=None,depth_to=None,month='2026-07-01',held_rows=1,first_clock=None,last_clock=None)
    pq.write_table(pa.concat_tables([table,pa.Table.from_pylist([grain],schema=table.schema)]),catalog)
    with qc.duckdb.connect(str(case[2]/'file-only-timeseries.duckdb')) as connection:
        connection.execute('UPDATE source_assets SET parquet_sha256=?',[qc.file_hash(source)])
    freeze_scope_census(case)
    db=case[3];db.add(StationMetadata(station_id='C',station_name='Isolated invalid-clock-only station',network_type='INVALID_ONLY',sea_area='OTHER'));db.commit()
    data=packet(case,monkeypatch,network='INVALID_ONLY')
    assert data['total_observations']==0 and data['states']['overall']=='NO_DATA'
    assert data['archive_samples']['rows']==[] and data['station_variable_matrix']==[]
    assert data['provenance']['invalid_clock_rows_excluded']==1
    assert data['summary']['normal']['count'] is None and data['summary']['missing']['rate'] is None


def test_positive_scope_verification_changes_during_cached_aggregation_are_rejected(case,monkeypatch):
    packet(case,monkeypatch,sea='WEST');original=qc._archive_query
    def changed(*args,**kwargs):
        result=original(*args,**kwargs)
        path=case[2]/'verification.json';proof=json.loads(path.read_text(encoding='utf-8'));proof['changed_after_query']=True
        path.write_text(json.dumps(proof),encoding='utf-8');return result
    monkeypatch.setattr(qc,'_archive_query',changed)
    response=case[0].get('/api/qc/overview',params={**ARCHIVE_ARGS,'sea':'WEST'})
    assert response.status_code==409 and response.json()['detail']['code']=='QC_POSITIVE_SCOPE_CATALOG_CHANGED'
