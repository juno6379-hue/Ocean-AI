"""The QC view uses one raw cutoff and cannot imply approval from code strings."""
from collections import Counter
import hashlib
import json
import re

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from fastapi import FastAPI,HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine,event
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api.routes_qc_workspace import router
from app.core.config import settings
from app.core.database import Base,get_db
from app.models.domain import StationMetadata
from app.models.agent_workflow import AgentWorkflowRun,AgentWorkflowTransition
from app.services import lake_browser as lake,station_classification as classification
from app.services import qc_workspace as qc

ARGS=dict(source='GD_OBS_VBU',from_month='2026-07',to_month='2026-07',as_of_day='2026-07-09',as_of_time='12:02:00')

@pytest.fixture
def case(tmp_path,monkeypatch):
    clocks=['2026-07-09 12:00:00','2026-07-09 12:01:00','2026-07-09 12:02:00',
            '2026-07-09 12:02:00','2026-07-09 12:02:00.000001','2026-07-30 00:00:00',
            'bad-clock','2026-07-09T12:00:00+09:00','2026-07-09 12:02:00','2026-07-09 12:01:00']
    stations=['A']*8+['A','B'];depths=[None]*8+['2',None]
    values=['0',None,'2','2','999','30','888','777','20','9']
    codes=['OK','',None,'G ','BAD','B','B','B',' G ','0']
    p=tmp_path/'source.parquet'
    pq.write_table(pa.table(dict(OBS_POST_ID=stations,OBS_ITEM_CODE=['TEMP']*10,OBS_TIME=clocks,
        OBS_VALUE=values,QC_FLAG=codes,WATER_STEP=depths)),p)
    catalog=[dict(source_group='GD_OBS_VBU',station_code=s,station_name=s,item_code='TEMP',depth_step=d,
        depth_from=None,depth_to=None,month='2026-07-01',held_rows=n,first_clock=None,last_clock=None)
        for (s,d),n in Counter(zip(stations,depths)).items()]
    pq.write_table(pa.Table.from_pylist(catalog),tmp_path/'station-item-month-validation.parquet')
    with duckdb.connect(str(tmp_path/'file-only-timeseries.duckdb')) as c:
        c.execute('CREATE TABLE source_assets(parquet_path VARCHAR,source_group VARCHAR,source_path VARCHAR,source_sha256 VARCHAR,parquet_sha256 VARCHAR)')
        c.execute('INSERT INTO source_assets VALUES (?,?,?,?,?)',[str(p),'GD_OBS_VBU','VBU_202607.csv','a'*64,hashlib.sha256(p.read_bytes()).hexdigest()])
    monkeypatch.setattr(lake,'snapshot',lambda:(tmp_path,tmp_path))
    monkeypatch.setattr(settings,'SHARE_MONTHLY_LAKE_ROOT',str(tmp_path))
    monkeypatch.setattr(settings,'MONTHLY_REPORT_MATCHING_ROOT',str(tmp_path/'published'))
    monkeypatch.setattr(settings,'LAKE_WEB_POSTGRES_CATALOG',False)
    monkeypatch.setattr(settings,'API_IDENTITIES',{})
    def references(rows,month=None):
        return [dict(station_id=r.station_id,station_name=r.station_name,network_type=r.network_type,sea_area=r.sea_area) for r in rows]
    monkeypatch.setattr(qc,'reference_records',references)
    monkeypatch.setattr(classification,'reference_records',references)
    engine=create_engine('sqlite://',poolclass=StaticPool,connect_args={'check_same_thread':False})
    Base.metadata.create_all(engine)
    db=Session(engine)
    db.add(StationMetadata(station_id='A',station_name='Station A',network_type='TIDE',sea_area='WEST'))
    db.commit()
    app=FastAPI();app.include_router(router);app.dependency_overrides[get_db]=lambda:db
    yield TestClient(app),p,tmp_path,db,engine
    db.close();engine.dispose()

def get(case,**extra):
    response=case[0].get('/api/qc/workspace',params={**ARGS,**extra})
    assert response.status_code==200,response.text
    return response.json()

def test_one_cutoff_whole_population_raw_distribution_not_approved_good(case):
    packet=get(case)
    assert packet['schema_version']=='qc-workspace-1'
    assert packet['cutoff_native']=='2026-07-09 12:02:00'
    assert packet['raw']['held_rows']==6
    assert packet['raw']['missing_value_rows']==1
    assert packet['cards']['missing']['denominator']==6
    assert packet['cards']['unassessed']['rate']==100
    for key in ('normal','warning','bad'):
        assert packet['cards'][key]==dict(count=None,rate=None,denominator=None,status='NOT_EVALUATED')
    assert {r['literal']:r['count'] for r in packet['distribution']}=={'OK':1,'':1,None:1,'G ':1,' G ':1,'0':1}
    assert sum(r['count'] for r in packet['distribution'])==6
    assert all(r['interpreted'] is False and r['denominator']==6 for r in packet['distribution'])
    assert packet['rules']['catalog_count']==12 and packet['rules']['result_count']==0
    assert packet['cards']['pending']==dict(count=0,status='GLOBAL_EMPTY')
    assert packet['cards']['completed']==dict(count=0,status='GLOBAL_EMPTY')
    assert packet['review']['source_fact_status']=='UNRESOLVED'
    assert not any(packet['capabilities'][key] for key in ('review','hold','flag_change','approve'))
    sha=packet.pop('result_sha256');assert qc.digest(packet)==sha

def test_exact_station_item_sea_network_and_unregistered_scope(case):
    packet=get(case,station='A',item='TEMP',network='TIDE',sea='WEST')
    assert packet['raw']['held_rows']==5
    assert packet['scope']['station']=='A' and packet['scope']['item']=='TEMP'
    assert len(packet['matrix'])==1 and packet['matrix'][0]['state']=='UNKNOWN'
    assert {r['depth_step'] for r in packet['matrix'][0]['typed_grains']}=={'2',None}
    assert packet['matrix'][0]['missing_rate']==20
    assert packet['monthly'][0]['held_rows']==5
    assert all(row['station_code']=='A' for row in packet['cases']['rows'])
    assert get(case,network='__UNREGISTERED__')['raw']['held_rows']==1
    assert get(case,network='__UNREGISTERED__',sea='__UNASSIGNED__')['raw']['held_rows']==1
    assert get(case,sea='__UNASSIGNED__')['raw']['held_rows']==0
    assert get(case,network='TIDE',sea='EAST')['raw']['held_rows']==0
    assert get(case,item='WRONG')['cases']['rows']==[]

def test_case_literal_filters_preserve_null_empty_and_padding(case):
    null=get(case,qc_field='QC_FLAG',qc_literal_is_null='true')
    empty=get(case,qc_field='QC_FLAG',qc_literal='')
    padded=get(case,qc_field='QC_FLAG',qc_literal=' G ')
    for packet,literal in ((null,None),(empty,''),(padded,' G ')):
        assert packet['cases']['total_matching_rows']==1
        assert packet['cases']['rows'][0]['source_qc_raw']==literal
        assert packet['cases']['rows'][0]['parquet_sha256']==hashlib.sha256(case[1].read_bytes()).hexdigest()
        assert packet['cases']['rows'][0]['physical_sensor_id'] is None
        assert packet['cases']['rows'][0]['available_at'] is None
        assert packet['cases']['rows'][0]['historical_availability_asserted'] is False
    assert get(case,qc_field='QC_FLAG',qc_literal='G')['cases']['total_matching_rows']==0
    assert get(case,qc_field='QC_FLAG',qc_literal='BAD')['cases']['total_matching_rows']==0

def test_future_microsecond_offset_clock_and_reversed_selection_fail_closed(case):
    packet=get(case)
    assert len(packet['cases']['rows'])==6
    assert all(row['observed_time_raw']<=ARGS['as_of_day']+' '+ARGS['as_of_time'] for row in packet['cases']['rows'])
    assert packet['provenance']['unlocatable_clock_rows_excluded']==2
    for extra in ({'to_month':'2026-08'},{'from_month':'2026-08'},
        {'from_month':'2021-01'},{'as_of_time':'12:02:00+09:00'},
        {'qc_literal':'G'},{'qc_field':'QC_FLAG','qc_literal':'G','qc_literal_is_null':'true'},
        {'qc_field':'__illegal__'},{'source':'HISTORICAL_RECONCILED'}):
        assert case[0].get('/api/qc/workspace',params={**ARGS,**extra}).status_code==422
    assert case[0].get('/api/qc/workspace',params={**ARGS,'unexpected':'true'}).status_code==422
    assert case[0].get('/api/qc/workspace?station=A&station=B').status_code==422

def test_source_changes_reject_cached_metrics_and_cases(case):
    assert get(case)['raw']['held_rows']==6
    case[1].write_bytes(case[1].read_bytes()+b' ')
    response=case[0].get('/api/qc/workspace',params=ARGS)
    assert response.status_code==409

def test_route_is_get_only_and_no_pending_session_changes_are_flushed(case):
    _,_,_,db,engine=case
    db.add(StationMetadata(station_id='PENDING',station_name='pending'))
    statements=[]
    listener=lambda conn,cursor,statement,parameters,context,executemany:statements.append(statement)
    event.listen(engine,'before_cursor_execute',listener)
    try:
        packet=get(case)
        assert packet['provenance']['production_writes']==0
        assert db.new
        assert not any(re.match(r'\s*(INSERT|UPDATE|DELETE|CREATE|ALTER)',s,re.I) for s in statements)
        assert case[0].post('/api/qc/workspace',json={}).status_code==405
    finally:event.remove(engine,'before_cursor_execute',listener)

def test_query_failure_is_failure_not_empty_qc_history(monkeypatch):
    class BadDB:
        no_autoflush=__import__('contextlib').nullcontext()
        def get_bind(self):raise __import__('sqlalchemy').exc.OperationalError('private-credentials','secret',Exception('secret'))
    with pytest.raises(HTTPException) as error:qc.registry_counts(BadDB())
    assert error.value.status_code==503 and 'secret' not in str(error.value.detail)

def test_absent_ledger_tables_and_empty_scope_are_unknown_not_zero(case,monkeypatch):
    engine=create_engine('sqlite://');db=Session(engine)
    try:
        counts=qc.registry_counts(db)
        assert counts['state']=='TABLES_ABSENT' and counts['counts']['qc_flag_history'] is None
    finally:db.close();engine.dispose()
    packet=get(case,station='ABSENT')
    assert packet['raw']['held_rows']==0
    assert packet['cards']['missing']['rate'] is None
    assert packet['monthly'][0]['missing_rate'] is None
    assert packet['matrix']==[] and packet['cases']['total_matching_rows']==0

def test_nonempty_history_without_native_source_binding_is_not_backdated(case,monkeypatch):
    monkeypatch.setattr(qc,'registry_counts',lambda db:{'state':'AVAILABLE',
        'counts':{key:1 for key in qc.TABLES},'missing_tables':[],
        'scope':'GLOBAL_REGISTERED_NOT_SELECTED_RESULTS'})
    packet=get(case)
    assert packet['global_registry']['counts']['qc_flag_history']==1
    assert packet['cards']['normal']['rate'] is None
    assert packet['cards']['bad']['count'] is None
    assert packet['cards']['pending']==dict(count=None,status='UNVERIFIED_SCOPE')
    assert packet['cards']['completed']==dict(count=None,status='UNVERIFIED_SCOPE')
    assert packet['rules']['result_count'] is None
    assert packet['review']['ai_prediction_count'] is None
    assert packet['review']['approved_count'] is None
    assert packet['raw']['held_rows']==6 and packet['cases']['total_matching_rows']==6

def test_cases_are_latest_fifteen_rows_and_exact_population_count(case):
    _,p,root,_,_=case
    values=pq.read_table(p).to_pydict()
    additions=20
    for key,value in {'OBS_POST_ID':'A','OBS_ITEM_CODE':'TEMP','OBS_TIME':'2026-07-09 12:01:30',
        'OBS_VALUE':'4','QC_FLAG':'RAW-NOT-A-FLAG','WATER_STEP':None}.items():values[key].extend([value]*additions)
    pq.write_table(pa.table(values),p)
    rows=pq.read_table(root/'station-item-month-validation.parquet').to_pylist()
    next(row for row in rows if row['station_code']=='A' and row['depth_step'] is None)['held_rows']+=additions
    pq.write_table(pa.Table.from_pylist(rows),root/'station-item-month-validation.parquet')
    with duckdb.connect(str(root/'file-only-timeseries.duckdb')) as c:
        c.execute('UPDATE source_assets SET parquet_sha256=?',[hashlib.sha256(p.read_bytes()).hexdigest()])
    packet=get(case,qc_field='QC_FLAG',qc_literal='RAW-NOT-A-FLAG')
    assert packet['raw']['held_rows']==26
    assert packet['cases']['total_matching_rows']==20 and len(packet['cases']['rows'])==15
    assert len({row['case_key'] for row in packet['cases']['rows']})==15
    assert [row['file_row_number'] for row in packet['cases']['rows']]==list(range(29,14,-1))
    assert all(row['classification']=='UNINTERPRETED' for row in packet['cases']['rows'])
