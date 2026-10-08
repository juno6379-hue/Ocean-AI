"""Read-only lake API guards: validated assets, original values and bounded input."""
import hashlib
import json
import uuid
import pytest
from pathlib import Path
import pyarrow as pa
import pyarrow.parquet as pq
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.api.routes_foundation import router
from app.core.config import settings


@pytest.fixture
def lake_tmp():
    # Pytest's restrictive Windows temp ACL cannot be read in this session.
    # Use an ordinary unique directory within the authorized test workspace.
    path=Path(__file__).parent/'.work'/('foundation-'+uuid.uuid4().hex)
    path.mkdir(parents=True)
    return path


def setup_client(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, 'SHARE_MONTHLY_LAKE_ROOT', str(tmp_path))
    folder = tmp_path/'GD_OBS_BU_202609'
    folder.mkdir()
    path = folder/'raw.parquet'
    pq.write_table(pa.table({'OBS_POST_ID':['TW_0072','TW_0072','TW_9999'],
                            'OBS_ITEM_CODE':['ELECT_CONDUCT']*3,
                            'OBS_TIME':['2026-09-01 00:00:00']*3,
                            'OBS_VALUE':['0',None,'9'], 'QC_FLAG':['B',None,'G']}),path)
    manifest={'status':'VERIFIED','source_system':'GD_OBS_BU','raw_path':str(path),
              'raw_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
              'raw_rows':3,'source_sha256':'a'*64}
    (folder/'manifest.json').write_text(json.dumps(manifest),encoding='utf8')
    app=FastAPI();app.include_router(router)
    return TestClient(app),folder,manifest


def test_sample_keeps_null_zero_flags_and_unapproved_state(lake_tmp,monkeypatch):
    client,_,_=setup_client(lake_tmp,monkeypatch)
    r=client.get('/api/data-lake/foundation/observations',params=dict(source='GD_OBS_BU',month='202609',station='TW_0072',item='ELECT_CONDUCT',limit=2))
    assert r.status_code==200
    data=r.json()
    assert [r['OBS_VALUE'] for r in data['rows']]==['0',None]
    assert data['rows'][0]['QC_FLAG']=='B'
    assert data['approval_status']=='UNAPPROVED'
    assert data['unit'] is None and data['timezone'] is None


def test_changed_asset_and_unverified_manifest_are_rejected(lake_tmp,monkeypatch):
    client,folder,m=setup_client(lake_tmp,monkeypatch)
    params=dict(source='GD_OBS_BU',month='202609',station='TW_0072',item='ELECT_CONDUCT')
    m['raw_sha256']='0'*64
    (folder/'manifest.json').write_text(json.dumps(m))
    assert client.get('/api/data-lake/foundation/observations',params=params).status_code==409
    m['status']='COPYING'
    (folder/'manifest.json').write_text(json.dumps(m))
    assert client.get('/api/data-lake/foundation/observations',params=params).status_code==409


def test_unbounded_or_traversal_inputs_rejected(lake_tmp,monkeypatch):
    client,_,_=setup_client(lake_tmp,monkeypatch)
    params=dict(source='GD_OBS_BU',month='../202609',station='TW_0072',item='ELECT_CONDUCT',limit=99999)
    assert client.get('/api/data-lake/foundation/observations',params=params).status_code==422


def test_in_progress_snapshot_does_not_replace_complete_bundle(lake_tmp,monkeypatch):
    from app.api.routes_foundation import snapshot
    run=lake_tmp/'run';run.mkdir()
    (lake_tmp/'latest-run.txt').write_text(str(run),encoding='utf8')
    old=run/'validation-001';old.mkdir();new=run/'validation-002';new.mkdir()
    (run/'latest-validation.txt').write_text(str(new),encoding='utf8')
    names=['summary.json','channel-validation.json','station-item-month-validation.parquet','file-only-timeseries.duckdb','lake-manifest.json']
    for name in names:(old/name).write_text('{}',encoding='utf8')
    (old/'verification.json').write_text(json.dumps({'checks':[{'passed':True}]}),encoding='utf8')
    monkeypatch.setattr(settings,'FOUNDATION_OUTPUT_ROOT',str(lake_tmp))
    assert snapshot()[1]==old
    for name in names:(new/name).write_text('{}',encoding='utf8')
    (new/'verification.json').write_text(json.dumps({'checks':[{'passed':False}]}),encoding='utf8')
    assert snapshot()[1]==old
    (new/'verification.json').write_text(json.dumps({'checks':[{'passed':True}]}),encoding='utf8')
    assert snapshot()[1]==new


def test_deleted_source_is_reported_even_when_parquet_is_still_queryable(lake_tmp,monkeypatch):
    from app.api.routes_foundation import source_file_availability
    client,folder,manifest=setup_client(lake_tmp,monkeypatch)
    original=lake_tmp/'source.csv';original.write_text('original csv',encoding='utf8')
    info=original.stat()
    manifest.update(source_path=str(original),source_size=info.st_size,source_mtime_ns=info.st_mtime_ns)
    (folder/'manifest.json').write_text(json.dumps(manifest),encoding='utf8')
    assert source_file_availability([manifest])['counts']=={'METADATA_MATCH_NOT_REHASHED':1}
    original.unlink()
    availability=source_file_availability([manifest])
    assert availability['counts']=={'MISSING':1}
    assert availability['hash_rechecked'] is False
    response=client.get('/api/data-lake/foundation/observations',params=dict(source='GD_OBS_BU',month='202609',station='TW_0072',item='ELECT_CONDUCT'))
    assert response.status_code==200 and response.json()['approval_status']=='UNAPPROVED'


def test_changed_or_unknown_source_is_not_reported_as_preserved(lake_tmp):
    from app.api.routes_foundation import source_file_availability
    original=lake_tmp/'source.csv';original.write_text('data',encoding='utf8')
    info=original.stat()
    receipt=dict(source_path=str(original),source_size=info.st_size,source_mtime_ns=info.st_mtime_ns)
    original.write_text('longer data',encoding='utf8')
    result=source_file_availability([receipt,{'source_path':''},{'source_path':str(lake_tmp)}])
    assert result['counts']=={'SIZE_CHANGED':1,'PATH_UNRESOLVED':1,'NOT_A_FILE':1}
