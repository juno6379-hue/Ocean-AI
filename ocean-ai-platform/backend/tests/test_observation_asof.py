"""Cutoffs must select actual rows, preserve channels, and shorten calendar grids."""
import hashlib
import json
from collections import Counter
import duckdb
import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.api.routes_lake_browser import router
from app.core.config import settings
from app.services import lake_browser as lake
from app.services import observation_asof as dated

@pytest.fixture
def case(tmp_path,monkeypatch):
    clocks=['2026-07-09 12:00:00','2026-07-09 12:01:00','2026-07-09 12:02:00',
      '2026-07-09 12:02:00','2026-07-09 12:02:00.000001','2026-07-09 23:59:59.999999',
      '2026-07-10 00:00:00','2026-07-30 00:00:00','bad-clock','2026-07-09T12:00:00+09:00',
      '2026-07-09 12:00:00','2026-07-10 00:00:00']
    stations=['A']*11+['FUTURE'];depths=[None]*10+['2',None]
    values=['0','-1','2',None,'999','9','10','30','888','777','222','100']
    p=tmp_path/'native.parquet'
    pq.write_table(pa.table(dict(OBS_POST_ID=stations,OBS_ITEM_CODE=['TEMP']*12,OBS_TIME=clocks,
      OBS_VALUE=values,QC_FLAG=['G']*3+[None]+['B']*8,WATER_STEP=depths)),p)
    counts=Counter(zip(stations,depths))
    catalog=[dict(source_group='GD_OBS_VBU',station_code=s,station_name=s,item_code='TEMP',
      depth_step=d,depth_from=None,depth_to=None,month='2026-07-01',held_rows=n,
      first_clock=None,last_clock=None) for (s,d),n in counts.items()]
    pq.write_table(pa.Table.from_pylist(catalog),tmp_path/'station-item-month-validation.parquet')
    authority=tmp_path/'file-only-timeseries.duckdb'
    with duckdb.connect(str(authority)) as c:
        c.execute('CREATE TABLE source_assets(parquet_path VARCHAR,source_group VARCHAR,source_path VARCHAR,source_sha256 VARCHAR,parquet_sha256 VARCHAR)')
        c.execute('INSERT INTO source_assets VALUES (?,?,?,?,?)',[str(p),'GD_OBS_VBU','VBU_202607.csv','a'*64,hashlib.sha256(p.read_bytes()).hexdigest()])
    monkeypatch.setattr(lake,'snapshot',lambda:(tmp_path,tmp_path))
    monkeypatch.setattr(settings,'SHARE_MONTHLY_LAKE_ROOT',str(tmp_path))
    monkeypatch.setattr(settings,'MONTHLY_REPORT_MATCHING_ROOT',str(tmp_path/'published'))
    monkeypatch.setattr(settings,'LAKE_WEB_POSTGRES_CATALOG',False)
    app=FastAPI();app.include_router(router)
    return TestClient(app),p,tmp_path

ARGS=dict(source='GD_OBS_VBU',from_month='2026-07',to_month='2026-07',as_of_day='2026-07-09',as_of_time='12:02:00')

def test_every_screen_uses_same_actual_cutoff_and_excludes_future_only_station(case):
    client,_,_=case
    summary=client.get('/api/lake/summary',params=ARGS);assert summary.status_code==200,summary.text
    summary=summary.json()
    assert summary['totals']['held_rows']==5 and summary['totals']['stations']==1
    assert summary['totals']['last_clock']=='2026-07-09 12:02:00'
    assert summary['unlocatable_clock_rows_excluded']==2
    detail=client.get('/api/lake/stations/A',params=ARGS).json()
    assert sum(r['held_rows'] for r in detail['months'])==5
    assert detail['as_of_time']=='12:02:00'
    metrics=client.get('/api/lake/metric-completion',params=ARGS).json()['raw']
    assert metrics['held_rows']==5 and metrics['missing_value_rows']==1
    shallow=next(r for r in detail['months'] if r['depth_step'] is None)
    assert shallow['duplicate_timestamp_rows']==1 and shallow['grid']['expected_slots']==12243
    assert shallow['grid']['held_slots']==3
    series=client.get('/api/lake/series',params=dict(source='GD_OBS_VBU',month='2026-07',station='A',item='TEMP',tail=True,as_of_day='2026-07-09',as_of_time='12:02:00')).json()
    assert [r['value_raw'] for r in series['rows']]==[None,'2','-1','0']
    assert series['as_of_time']==detail['as_of_time']
    assert all(r['observed_time_raw']<=summary['totals']['last_clock'] for r in series['rows'])
    deep=client.get('/api/lake/series',params=dict(source='GD_OBS_VBU',month='2026-07',station='A',item='TEMP',depth_step='2',as_of_day='2026-07-09',as_of_time='12:02:00')).json()
    assert [r['value_raw'] for r in deep['rows']]==['222']

def test_inclusive_day_end_differs_from_exact_second_and_original_full_month(case):
    client,_,_=case
    day={k:v for k,v in ARGS.items() if k!='as_of_time'}
    result=client.get('/api/lake/summary',params=day).json()
    assert result['totals']['held_rows']==7 and result['totals']['last_clock']=='2026-07-09 23:59:59.999999'
    full=client.get('/api/lake/summary',params={k:v for k,v in ARGS.items() if not k.startswith('as_of_')}).json()
    assert full['totals']['held_rows']==12
    assert client.get('/api/lake/summary',params={**ARGS,'to_month':'2026-08'}).status_code==422
    assert client.get('/api/lake/summary',params={**ARGS,'as_of_day':'2026-02-30'}).status_code==422
    assert client.get('/api/lake/summary',params={**ARGS,'as_of_time':'12:02:00+09:00'}).status_code==422
    assert client.get('/api/lake/series',params=dict(source='GD_OBS_VBU',month='2026-08',station='A',item='TEMP',as_of_day='2026-07-09')).status_code==422

def test_published_packet_and_source_changes_fail_closed(case):
    client,p,root=case
    assert client.get('/api/lake/summary',params=ARGS).status_code==200
    marker=next((root/'published').rglob('published.json'))
    content=json.loads(marker.read_text());packet=marker.parent/content['packet']
    original=packet.read_bytes();packet.write_bytes(original+b' ')
    assert client.get('/api/lake/summary',params=ARGS).status_code==409
    packet.write_bytes(original)
    p.write_bytes(p.read_bytes()+b' ')
    assert client.get('/api/lake/summary',params=ARGS).status_code==409

def test_absent_qc_has_no_percentage_not_zero(case,monkeypatch):
    _,p,root=case
    table=pq.read_table(p).drop(['QC_FLAG']);pq.write_table(table,p)
    census=pq.read_table(root/'station-item-month-validation.parquet').to_pylist()
    for r in census:r['source_group']='GR_OBS_ST'
    pq.write_table(pa.Table.from_pylist(census),root/'station-item-month-validation.parquet')
    with duckdb.connect(str(root/'file-only-timeseries.duckdb')) as c:c.execute('UPDATE source_assets SET source_group=?,parquet_sha256=?',['GR_OBS_ST',hashlib.sha256(p.read_bytes()).hexdigest()])
    result=dated.completion('GR_OBS_ST','2026-07','2026-07','2026-07-09',as_of_time='12:02:00')
    assert result['raw']['source_qc_field_state']=='ABSENT'
    assert result['raw']['source_qc_presence_rate'] is None

def test_sea_network_scope_applies_include_and_exclude_to_actual_day_rows(case):
    result=dated.overview('GD_OBS_VBU','2026-07','2026-07','2026-07-09',{'include':['FUTURE']},'12:02:00')
    assert result['totals']['stations']==0
    assert result['operation_summary']['normal']==0
    result=dated.overview('GD_OBS_VBU','2026-07','2026-07','2026-07-09',{'exclude':['A']},'12:02:00')
    assert result['totals']['held_rows']==0
    result=dated.overview('GD_OBS_VBU','2026-07','2026-07','2026-07-09',{'include':['A']},'12:02:00')
    assert result['totals']['held_rows']==5
    assert result['stations'][0]['operation']['basis']=='OBSERVATION_DIAGNOSTIC'
    assert result['stations'][0]['operation']['equipment_state']=='UNVERIFIED'
    assert result['stations'][0]['operation']['collection_rate'] is None


def test_excluded_phase_candidate_uses_cutoff_denominator_and_retains_exclusion(case):
    client,p,root=case
    table=pq.read_table(p).to_pydict()
    table['OBS_TIME'][4]='2026-07-09 12:02:30'
    pq.write_table(pa.table(table),p)
    with duckdb.connect(str(root/'file-only-timeseries.duckdb')) as c:
        c.execute('UPDATE source_assets SET parquet_sha256=?',[hashlib.sha256(p.read_bytes()).hexdigest()])
    result=client.get('/api/lake/stations/A',params={**ARGS,'as_of_time':'12:03:30'}).json()
    shallow=next(r for r in result['months'] if r['depth_step'] is None)
    grid=shallow['grid']
    assert grid['status']=='PHASE_UNSTABLE_MULTIPLE_REMAINDERS'
    assert grid['expected_slots'] is None and grid['holding_fraction_percent'] is None
    assert grid['candidate_phase_accounting']['expected_slots']==12244
    assert grid['candidate_phase_accounting']['usable_for_holding_fraction'] is False
    assert grid['whole_calendar_month_denominator'] is False


def test_completed_prior_month_reports_full_calendar_denominator(case):
    client,_,_=case
    result=client.get('/api/lake/stations/A',params={**ARGS,'as_of_day':'2026-08-01'}).json()
    shallow=next(r for r in result['months'] if r['depth_step'] is None)
    assert shallow['grid']['whole_calendar_month_denominator'] is True
    assert shallow['grid']['period_end_native_exclusive']=='2026-08-01 00:00:00'
    result=client.get('/api/lake/metric-completion',params=ARGS).json()
    assert result['raw']['grid']['as_of_time']==ARGS['as_of_time']
    assert result['raw']['stations'][0]['grid']['as_of_time']==ARGS['as_of_time']


def test_empty_series_preserves_graph_scope_and_paging_contract(case):
    client,_,_=case
    args=dict(source='GD_OBS_VBU',station='A',item='TEMP',month='2026-06',limit=240,offset=240,
        tail=True,as_of_day=ARGS['as_of_day'],as_of_time=ARGS['as_of_time'])
    response=client.get('/api/lake/series',params=args)
    assert response.status_code==200
    result=response.json()
    assert result['rows']==[] and result['has_more'] is False
    for key in ('source','month','station','item','limit','offset','tail','as_of_day','as_of_time'):
        assert result[key]==args[key]
