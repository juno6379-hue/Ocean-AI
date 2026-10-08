"""Cross-screen source contract: isolated channels, paging, nulls and lineage."""
import hashlib
import json
import uuid
from pathlib import Path
import duckdb
import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.api.routes_lake_browser import router
from app.core.config import settings
from app.services import lake_browser as lake


@pytest.fixture
def fixture(monkeypatch):
    root=Path(__file__).parent/'.work'/('lake-browser-'+uuid.uuid4().hex)
    root.mkdir(parents=True)
    month=root/'GD_OBS_VBU_202607';month.mkdir()
    p=month/'raw.parquet'
    # Out-of-order rows, duplicate clocks, different stations/depths and months.
    pq.write_table(pa.table({
        'OBS_POST_ID':['TW_1']*6+['TW_2'], 'OBS_ITEM_CODE':['TEMP']*7,
        'OBS_TIME':['2026-07-01 00:01:00','2026-07-01 00:00:00','2026-07-01 00:00:00','2026-07-01 00:00:00','2026-08-01 00:00:00','2026-07-01 00:02:00','2026-07-01 00:00:00'],
        'OBS_VALUE':['3','0',None,'99','88','NaN','77'], 'QC_FLAG':['G','B',None,'B','B','M','G'],
        'WATER_STEP':[None,None,None,'2',None,None,None],
    }),p)
    coverage=root/'station-item-month-validation.parquet'
    pq.write_table(pa.table({'source_group':['GD_OBS_VBU'],'station_code':['TW_1'],'station_name':['관측소'],
        'item_code':['TEMP'],'month':['2026-07-01'],'held_rows':[4],
        'first_clock':['2026-07-01 00:00:00'],'last_clock':['2026-07-01 00:02:00'],
        'depth_step':[None],'depth_from':[None],'depth_to':[None]}),coverage)
    cat=root/'file-only-timeseries.duckdb'
    with duckdb.connect(str(cat)) as c:
        c.execute('create table source_assets(parquet_path varchar,source_group varchar,source_path varchar,source_sha256 varchar,parquet_sha256 varchar)')
        c.execute('insert into source_assets values (?,?,?,?,?)',[str(p),'GD_OBS_VBU','source_202607.csv','a'*64,hashlib.sha256(p.read_bytes()).hexdigest()])
    monkeypatch.setattr(lake,'snapshot',lambda:(root,root))
    monkeypatch.setattr(settings,'SHARE_MONTHLY_LAKE_ROOT',str(root))
    monkeypatch.setattr(settings,'INTEGRATED_LAKE_ROOT',str(root))
    monkeypatch.setattr(settings,'LAKE_WEB_POSTGRES_CATALOG',False)
    app=FastAPI();app.include_router(router)
    return TestClient(app),p,cat


def test_order_paging_duplicates_nulls_and_depth_isolation(fixture):
    client,_,_=fixture
    args=dict(source='GD_OBS_VBU',station='TW_1',item='TEMP',month='2026-07',limit=2)
    a=client.get('/api/lake/series',params=args);assert a.status_code==200,a.text
    a=a.json();assert [r['value_raw'] for r in a['rows']]==['0',None]
    assert a['has_more'] and a['rows'][0]['source_qc_raw']=='B'
    assert all(r['physical_sensor_id'] is None and r['timezone'] is None and r['unit'] is None for r in a['rows'])
    b=client.get('/api/lake/series',params={**args,'offset':2}).json()
    assert [r['value_raw'] for r in b['rows']]==['3','NaN'] and not b['has_more']
    assert b['rows'][1]['value_numeric'] is None
    deep=client.get('/api/lake/series',params={**args,'depth_step':'2'}).json()
    assert [r['value_raw'] for r in deep['rows']]==['99']
    assert a['approval_status']=='UNAPPROVED'


def test_summary_and_detail_share_scope_without_simulation(fixture):
    client,_,_=fixture
    args=dict(source='GD_OBS_VBU',from_month='2026-07',to_month='2026-07')
    s=client.get('/api/lake/summary',params=args).json()
    d=client.get('/api/lake/stations/TW_1',params=args).json()
    assert s['totals']['held_rows']==sum(r['held_rows'] for r in d['months'])==4
    assert s['simulated_included'] is False
    assert client.get('/api/lake/summary',params={**args,'from_month':'2026-08'}).status_code==422
    assert client.get('/api/lake/summary',params={**args,'source':'SIMULATED'}).status_code==422


def test_bad_hash_is_not_served_and_injection_is_a_literal(fixture):
    client,p,cat=fixture
    args=dict(source='GD_OBS_VBU',station="TW_1' OR 1=1 --",item='TEMP',month='2026-07')
    assert client.get('/api/lake/series',params=args).json()['rows']==[]
    with duckdb.connect(str(cat)) as c:c.execute("update source_assets set parquet_sha256=?",['0'*64])
    lake.monthly_assets.cache_clear()
    assert client.get('/api/lake/series',params={**args,'station':'TW_1'}).status_code==409
    assert client.get('/api/lake/series',params={**args,'month':'../202607'}).status_code==422


def test_catalog_path_escape_rejected(fixture):
    client,p,cat=fixture
    with duckdb.connect(str(cat)) as c:c.execute('update source_assets set parquet_path=?',[str(p.parent.parent.parent/'outside.parquet')])
    lake.monthly_assets.cache_clear()
    assert client.get('/api/lake/series',params=dict(source='GD_OBS_VBU',station='TW_1',item='TEMP',month='2026-07')).status_code==503
