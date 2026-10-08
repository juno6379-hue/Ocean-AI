"""Administrator-only read probes for registered sources; no ingestion/approval.

Adapters expose a stable probe interface. Adding an external database does not
change dashboard schemas or silently enable live synchronization. A successful
probe proves SELECT access only, not mapping, units, timestamps or QC semantics.
"""
from datetime import datetime, timezone
from pathlib import Path
import os
import sqlite3
import time
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from app.core.config import settings
from app.core.database import engine
from app.core.security import Actor, current_actor
from app.api.routes_foundation import foundation_summary, snapshot

router=APIRouter(prefix='/api/integrations',tags=['Administrator integrations'])


def administrator(actor: Actor=Depends(current_actor)):
    if actor.role!='admin':raise HTTPException(403,'Administrator role required')
    return actor


def sources():
    entries=[
        {'id':'operational-postgres','label':'운영 PostgreSQL','adapter':'sqlalchemy','mode':'stored_operational_data','configured':True},
        {'id':'monthly-parquet','label':'월별 Parquet 원천층','adapter':'parquet_manifest','mode':'batch_files','configured':True},
        {'id':'validation-registry','label':'문서·기간 검증표','adapter':'sqlite_readonly','mode':'validation_snapshot','configured':True},
    ]
    reserved={x['id'] for x in entries}
    for key,config in settings.EXTERNAL_SOURCE_CONNECTIONS.items():
        if key in reserved:continue
        entries.append({'id':key,'label':config.get('label',key),'adapter':config.get('adapter','sqlalchemy'),
                        'mode':'external_not_activated','configured':bool(os.environ.get(config.get('connection_env','')))})
    return entries


@router.get('')
def list_sources(actor: Actor=Depends(administrator)):
    return {'sources':sources(),'live_ingestion_enabled':settings.MDC_SYNC_ENABLED,
            'note':'연결 시험은 조회만 수행합니다. 실시간 수집 활성화·매핑 승인과 별개입니다.'}


def sql_probe(target):
    with target.connect() as conn:
        if target.dialect.name=='postgresql':
            conn.execute(text('SET LOCAL statement_timeout = 5000'))
            conn.execute(text('SET TRANSACTION READ ONLY'))
        value=conn.execute(text('SELECT 1 FROM DUAL' if target.dialect.name=='oracle' else 'SELECT 1')).scalar()
    return {'connection':value==1,'read_probe':'SELECT_CONSTANT','schema_mapping_verified':False}


def probe(source_id):
    if source_id=='operational-postgres':return sql_probe(engine)
    if source_id=='monthly-parquet':
        state=foundation_summary()
        return {'connection':True,'verified_files':state['verified_monthly_files'],'read_probe':'MANIFEST_READ','payload_rehashed':False}
    if source_id=='validation-registry':
        _,view=snapshot()
        with sqlite3.connect((view/'validation.sqlite3').as_uri()+'?mode=ro',uri=True,timeout=5) as db:
            count=db.execute('select count(*) from monthly_validation').fetchone()[0]
        return {'connection':True,'read_probe':'VALIDATION_ROW_COUNT','rows':count}
    config=settings.EXTERNAL_SOURCE_CONNECTIONS.get(source_id)
    if not config:raise HTTPException(404,'Registered source not found')
    if config.get('adapter','sqlalchemy')!='sqlalchemy':raise HTTPException(422,'Adapter not implemented')
    dsn=os.environ.get(config.get('connection_env',''))
    if not dsn:raise HTTPException(409,'Server connection secret is not configured')
    url=make_url(dsn)
    if url.get_backend_name()!='postgresql':
        # New dialects need their own timeout and read-scope validation first.
        raise HTTPException(422,'Only the PostgreSQL external probe is implemented; other adapters require implementation')
    external=create_engine(url,connect_args={'connect_timeout':5},pool_pre_ping=True)
    try:return sql_probe(external)
    finally:external.dispose()


@router.post('/{source_id}/test')
def test_source(source_id:str,actor: Actor=Depends(administrator)):
    started=time.monotonic()
    try:
        result=probe(source_id)
        return {'source_id':source_id,'tested_at':datetime.now(timezone.utc).isoformat(),'duration_ms':round((time.monotonic()-started)*1000),
                'status':'CONNECTED','details':result,'ingestion_started':False,'approval_changed':False}
    except HTTPException:raise
    except Exception as exc:
        # Driver messages may include credentials or DSNs; return only their type.
        return {'source_id':source_id,'tested_at':datetime.now(timezone.utc).isoformat(),'duration_ms':round((time.monotonic()-started)*1000),
                'status':'FAILED','error_type':type(exc).__name__,'ingestion_started':False,'approval_changed':False}
