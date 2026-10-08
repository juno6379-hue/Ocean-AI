# 파일 역할: 파일 목록·처리 이력·중복 검사와 벡터 및 관계형 색인 적재를 관리합니다.
"""Resumable report ingestion, content deduplication and per-file audit ledger."""
import hashlib
import json
import logging
import re
import sqlite3
import time
import os
from contextlib import contextmanager
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import inspect, text
from app.core.database import SessionLocal, engine
from app.models.domain import DocumentIndex, StationMetadata, SensorMetadata
from app.rag.document_contract import (STATE_DIR, PARSER_VERSION, CHUNK_VERSION,
    initialize_contract, load_contract, get_collection, embed)
from app.rag.report_parser import SUPPORTED, classify, parse, report_date, semantic_blocks, STATION_CODE

LOG = logging.getLogger(__name__)
LEDGER = STATE_DIR / 'ingestion.sqlite3'


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def connect_ledger():
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    c=sqlite3.connect(LEDGER, timeout=60)
    c.row_factory=sqlite3.Row
    c.execute('PRAGMA journal_mode=WAL')
    c.executescript('''
    CREATE TABLE IF NOT EXISTS files (
      path TEXT PRIMARY KEY, root TEXT, size INTEGER, mtime_ns INTEGER,
      document_type TEXT, eligible INTEGER, status TEXT, reason TEXT,
      checksum TEXT, document_id TEXT, duplicate_of TEXT,
      chunks INTEGER DEFAULT 0, attempts INTEGER DEFAULT 0,
      parser_version TEXT, chunk_version TEXT, embedding_version TEXT,
      model TEXT, collection_name TEXT, updated_at TEXT);
    CREATE INDEX IF NOT EXISTS ix_files_checksum ON files(checksum,document_type);
    CREATE TABLE IF NOT EXISTS vector_cache (cache_key TEXT PRIMARY KEY, vector TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS errors (id INTEGER PRIMARY KEY, path TEXT, stage TEXT, reason TEXT, created_at TEXT);
    CREATE TABLE IF NOT EXISTS runs (run_id TEXT PRIMARY KEY, root TEXT, status TEXT, started_at TEXT, ended_at TEXT, summary TEXT);
    ''')
    return c


def inventory(root):
    # 원본은 읽기만 하며, 대상 외 파일도 제외 사유를 남겨 완료율 분모를 추적한다.
    root=Path(root).resolve()
    if not root.is_dir():raise ValueError('Source directory does not exist')
    c=connect_ledger(); count=0
    try:
        for path in root.rglob('*'):
            if not path.is_file():continue
            s=path.stat(); kind=classify(path.relative_to(root))
            eligible=kind!='OTHER' and path.suffix.lower() in SUPPORTED
            reason='' if eligible else ('OUTSIDE_REQUESTED_REPORT_TYPES' if kind=='OTHER' else 'UNSUPPORTED_ASSET_FORMAT:'+path.suffix.lower())
            if path.name.startswith('~$'):
                eligible=False; reason='OFFICE_TEMPORARY_LOCK_FILE'
            old=c.execute('select * from files where path=?',(str(path),)).fetchone()
            if old and old['size']==s.st_size and old['mtime_ns']==s.st_mtime_ns and old['eligible']==int(eligible):
                continue
            c.execute('''INSERT INTO files(path,root,size,mtime_ns,document_type,eligible,status,reason,updated_at)
              VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(path) DO UPDATE SET root=excluded.root,size=excluded.size,
              mtime_ns=excluded.mtime_ns,document_type=excluded.document_type,eligible=excluded.eligible,
              status=excluded.status,reason=excluded.reason,checksum=NULL,document_id=NULL,
              duplicate_of=NULL,chunks=0,updated_at=excluded.updated_at''',
              (str(path),str(root),s.st_size,s.st_mtime_ns,kind,int(eligible),'PENDING' if eligible else 'EXCLUDED',reason,utc_now()))
            count+=1
            if count%500==0:c.commit()
        c.commit()
    finally:c.close()
    return status(root)


def status(root=None):
    if not LEDGER.exists():return {'status':'NOT_STARTED','files':0,'is_demo':False}
    c=connect_ledger()
    try:
        where=' WHERE root=?' if root else ''
        params=(str(Path(root).resolve()),) if root else ()
        rows=c.execute('select document_type,status,eligible,count(*) as n,sum(chunks) as chunks from files'+where+' group by document_type,status,eligible',params).fetchall()
        counts=Counter()
        for r in rows:counts[r['status']]+=r['n']
        total=sum(counts.values())
        eligible=sum(r['n'] for r in rows if r['eligible'])
        success=counts['SUCCEEDED']+counts['DUPLICATE']
        resolved=sum(v for k,v in counts.items() if k in {'SUCCEEDED','DUPLICATE','EXCLUDED','FAILED'})
        by_type={}
        for row in rows:
            group=by_type.setdefault(row['document_type'],Counter())
            group[row['status']]+=row['n']
        latest=c.execute('select run_id,root,status,started_at,ended_at from runs order by started_at desc limit 1').fetchone()
        return {'files':total,'eligible_files':eligible,'counts':dict(counts),
          'success_percent':round(100*success/eligible,2) if eligible else 0,
          'accounted_percent':round(100*resolved/total,2) if total else 0,
          'eligible_processed_percent':round(100*(success+counts['FAILED'])/eligible,2) if eligible else 0,
          'unique_successful_documents':counts['SUCCEEDED'],
          'indexed_chunks':sum(r['chunks'] for r in rows if r['status']=='SUCCEEDED'),
          'by_type':{k:dict(v) for k,v in by_type.items()},
          'latest_run':dict(latest) if latest else None,'is_demo':False}
    finally:c.close()


def checksum(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()


def reference_maps():
    with SessionLocal() as db:
        stations={}
        for row in db.query(StationMetadata).all():
            if row.station_name:stations.setdefault(row.station_name,set()).add(row.station_id)
        sensors={r.sensor_id:r.station_id for r in db.query(SensorMetadata).all()}
    return stations,sensors


def extract_metadata(unit, path, kind, date, date_source, references):
    stations,sensors=references
    content=unit.text
    context=getattr(unit,'context','') or content
    codes=set(STATION_CODE.findall(context.upper()))
    if not codes:
        for name,ids in stations.items():
            if re.search(r'(?<![가-힣A-Za-z0-9])'+re.escape(name)+r'(?![가-힣A-Za-z0-9])',context):codes.update(ids)
    station=next(iter(codes)) if len(codes)==1 else None
    sensor_ids=[sid for sid,st in sensors.items() if st==station and re.search(r'(?<![A-Za-z0-9_])'+re.escape(sid)+r'(?![A-Za-z0-9_])',context)]
    variables=set()
    for word,code in [('조위','TIDE'),('수온','WATER_TEMP'),('염분','SALINITY'),('기온','AIR_TEMP'),('기압','AIR_PRES'),('풍속','WIND_SPEED'),('풍향','WIND_DIRECT'),('파고','WAVE')]:
        if word in context or re.search(r'\b'+code+r'\b',context):variables.add(code)
    return {'document_type':kind,'document_title':path.stem,'document_date':date.isoformat() if date else None,
        'date_source':date_source,'related_station_id':station,'station_candidates':sorted(codes),
        'related_sensor_id':sensor_ids[0] if len(sensor_ids)==1 else None,
        'related_variable_code':next(iter(variables)) if len(variables)==1 else None,
        'variable_candidates':sorted(variables),'section_name':unit.section,'page_no':unit.page,
        'source_locator':unit.locator,'source_path':str(path),'event_id':None,
        'event_type':'MAINTENANCE' if any(w in content for w in ['점검','정비']) else None,
        'error_type':'COMMUNICATION' if any(w in content for w in ['수신장애','통신장애']) else None,
        'period_start':None,'period_end':None,'mapping_status':'RESOLVED_STATION' if station else 'NEEDS_REVIEW'}


def migrate_index():
    # Add only the missing field this ingestion writes; no unrelated schema mutation.
    existing={x['name'] for x in inspect(engine).get_columns('document_index')}
    if 'parser_version' not in existing:
        with engine.begin() as c:c.execute(text('ALTER TABLE document_index ADD COLUMN parser_version VARCHAR'))


def cached_embeddings(texts, contract, ledger):
    keys=[hashlib.sha256((contract.get('model_digest',contract['model'])+'\0'+t).encode()).hexdigest() for t in texts]
    found={}
    for key in set(keys):
        row=ledger.execute('select vector from vector_cache where cache_key=?',(key,)).fetchone()
        if row:found[key]=json.loads(row[0])
    pending=list(dict.fromkeys(k for k in keys if k not in found))
    by_key=dict(zip(keys,texts))
    for start in range(0,len(pending),24):
        batch=pending[start:start+24]
        vectors=embed([by_key[k] for k in batch],contract)
        for key,vector in zip(batch,vectors):
            found[key]=vector
            ledger.execute('insert or replace into vector_cache values(?,?)',(key,json.dumps(vector)))
        ledger.commit()
    return [found[k] for k in keys]


def process_file(row, contract, collection, ledger, references):
    path=Path(row['path']); kind=row['document_type']
    sha=checksum(path)
    doc_id=hashlib.sha256((kind+'\0'+sha).encode()).hexdigest()
    ledger.execute('update files set checksum=?,document_id=? where path=?',(sha,doc_id,str(path)))
    previous=ledger.execute("select * from files where document_id=? and status='SUCCEEDED' and embedding_version=? and path!=? limit 1",(doc_id,contract['embedding_version'],str(path))).fetchone()
    # 경로가 달라도 유형과 내용 해시가 같은 사본은 검증된 원본 색인을 공유한다.
    if previous:
        return 'DUPLICATE',previous['chunks'],previous['path']
    units=parse(path,should_stop=lambda:(STATE_DIR/'stop.request').exists())
    if not units or not any(u.text.strip() for u in units):raise ValueError('EMPTY_TEXT: no extracted report content')
    date,date_source=report_date(path,units)
    chunks=semantic_blocks(units,kind)
    if not chunks:raise ValueError('EMPTY_CHUNKS')
    records=[]
    for i,u in enumerate(chunks):
        cid=hashlib.sha256((doc_id+contract['embedding_version']+str(i)+u.text).encode()).hexdigest()
        meta=extract_metadata(u,path,kind,date,date_source,references)
        meta.update(chunk_id=cid,document_id=doc_id,source_checksum=sha,chunk_version=CHUNK_VERSION,
                    embedding_version=contract['embedding_version'],embedding_model=contract['model'],
                    collection=contract['collection'],parser_version=PARSER_VERSION)
        records.append((cid,u,meta))
    for start in range(0,len(records),48):
        if (STATE_DIR/'stop.request').exists():raise InterruptedError('중단 요청: 다음 실행에서 이 파일을 재개합니다.')
        batch=records[start:start+48]
        texts=[u.text for _,u,_ in batch]
        vectors=cached_embeddings(texts,contract,ledger)
        metadatas=[]
        for cid,u,meta in batch:
            m={k:v for k,v in meta.items() if isinstance(v,(str,int,float,bool)) and v is not None}
            if date:m['document_date_epoch']=date.replace(tzinfo=timezone.utc).timestamp()
            metadatas.append(m)
        collection.upsert(ids=[r[0] for r in batch],documents=texts,embeddings=vectors,metadatas=metadatas)
        # 긴 문서도 파일 완료를 기다리지 않고 청크 진행량을 확인할 수 있게 한다.
        ledger.execute('update files set chunks=?,updated_at=? where path=?',(start+len(batch),utc_now(),str(path)))
        ledger.commit()
        print(json.dumps({'event':'chunk_progress','path':str(path),'chunks':start+len(batch),'total_chunks':len(records)},ensure_ascii=False),flush=True)
    # 문서 전체 벡터가 저장된 뒤 관계형 색인을 공개하여 미완성 문서가 검색되지 않게 한다.
    with SessionLocal() as db:
        for cid,u,meta in records:
            obj=db.query(DocumentIndex).filter(DocumentIndex.chunk_id==cid).first()
            if obj is None:
                obj=DocumentIndex(document_id=doc_id,chunk_id=cid); db.add(obj)
            for key,value in dict(document_type=kind,document_title=path.stem,document_date=date,
                related_station_id=meta['related_station_id'],related_sensor_id=meta['related_sensor_id'],
                related_variable_code=meta['related_variable_code'],section_name=u.section,page_no=u.page,
                chunk_text=u.text,embedding_id=cid,embedding_model=contract['model'],
                embedding_version=contract['embedding_version'],parser_version=PARSER_VERSION,
                metadata_json=meta,event_type=meta['event_type'],error_type=meta['error_type']).items():
                setattr(obj,key,value)
        db.commit()
    return 'SUCCEEDED',len(records),None


@contextmanager
def worker_lock():
    STATE_DIR.mkdir(parents=True,exist_ok=True)
    with (STATE_DIR/'worker.lock').open('a+b') as lock:
        lock.seek(0); lock.write(b'0'); lock.flush(); lock.seek(0)
        try:
            if os.name=='nt':
                import msvcrt
                msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        except OSError as exc:
            raise RuntimeError('An ingestion worker is already running') from exc
        yield


def run(root, limit=None, retry_failed=False):
    with worker_lock():
        return _run(root,limit,retry_failed)


def _run(root, limit=None, retry_failed=False):
    contract=initialize_contract()
    if contract['parser_version']!=PARSER_VERSION or contract['chunk_version']!=CHUNK_VERSION:
        raise RuntimeError('Parser/chunk version changed; create a new contract before ingestion')
    migrate_index(); collection=get_collection(contract,create=True)
    inventory(root)
    ledger=connect_ledger(); run_id=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')
    root=str(Path(root).resolve())
    ledger.execute("update files set status='PENDING' where root=? and status='RUNNING'",(root,))
    ledger.execute("update files set status='PENDING',chunks=0 where root=? and eligible=1 and embedding_version is not null and embedding_version!=?",(root,contract['embedding_version']))
    if retry_failed:ledger.execute("update files set status='PENDING' where root=? and status='FAILED'",(root,))
    ledger.execute("update runs set status='INTERRUPTED',ended_at=? where status='RUNNING'",(utc_now(),))
    ledger.execute('insert into runs values(?,?,?,?,?,?)',(run_id,root,'RUNNING',utc_now(),None,None)); ledger.commit()
    references=reference_maps(); processed=0
    # Round-robin report types, prioritizing PDFs within each type for early real evidence.
    rows=ledger.execute("select * from files where root=? and eligible=1 and status='PENDING' order by size,path",(root,)).fetchall()
    groups={}
    for row in rows:groups.setdefault(row['document_type'],[]).append(row)
    ordered=[]
    while any(groups.values()):
        for group in groups.values():
            if group:ordered.append(group.pop(0))
    try:
        for row in ordered:
            if (STATE_DIR/'stop.request').exists():break
            if limit is not None and processed>=limit:break
            path=row['path']
            ledger.execute("update files set status='RUNNING',reason='',attempts=attempts+1,parser_version=?,chunk_version=?,embedding_version=?,model=?,collection_name=?,updated_at=? where path=?",(PARSER_VERSION,CHUNK_VERSION,contract['embedding_version'],contract['model'],contract['collection'],utc_now(),path)); ledger.commit()
            print(json.dumps({'event':'file_start','path':path,'type':row['document_type']},ensure_ascii=False),flush=True)
            try:
                state,chunks,duplicate=process_file(row,contract,collection,ledger,references)
                ledger.execute('update files set status=?,chunks=?,duplicate_of=?,reason=?,updated_at=? where path=?',(state,chunks,duplicate,'CONTENT_IDENTICAL' if duplicate else '',utc_now(),path))
            except InterruptedError:
                ledger.execute("update files set status='PENDING',reason='INTERRUPTED',updated_at=? where path=?",(utc_now(),path))
                ledger.commit()
                break
            except Exception as exc:
                reason=f'{type(exc).__name__}: {exc}'[:2000]
                ledger.execute("update files set status='FAILED',reason=?,updated_at=? where path=?",(reason,utc_now(),path))
                ledger.execute('insert into errors(path,stage,reason,created_at) values(?,?,?,?)',(path,'PARSE_EMBED_INDEX',reason,utc_now()))
                print(json.dumps({'event':'file_failed','path':path,'reason':reason},ensure_ascii=False),flush=True)
            ledger.commit(); processed+=1
            print(json.dumps({'event':'progress','processed_this_run':processed,**status(root)},ensure_ascii=False),flush=True)
        summary=status(root)
        pending=summary['counts'].get('PENDING',0)+summary['counts'].get('RUNNING',0)
        state='PARTIAL' if pending else ('COMPLETED_WITH_ERRORS' if summary['counts'].get('FAILED',0) else 'COMPLETED')
        ledger.execute('update runs set status=?,ended_at=?,summary=? where run_id=?',(state,utc_now(),json.dumps(summary,ensure_ascii=False),run_id)); ledger.commit()
        return status(root)
    finally:ledger.close()


def file_records(status_filter=None, limit=100):
    c=connect_ledger()
    try:
        query='select * from files'; args=[]
        if status_filter:query+=' where status=?'; args.append(status_filter)
        query+=' order by updated_at desc limit ?'; args.append(max(1,min(limit,500)))
        return [dict(r) for r in c.execute(query,args)]
    finally:c.close()
