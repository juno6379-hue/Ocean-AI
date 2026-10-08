"""증거 파일을 별도 PostgreSQL foundation 스키마에 보존 적재한다.

prepare는 입력 해시와 COPY 파일을 만들고, apply는 단일 트랜잭션으로 추가한다.
미확정 센서·시간대·단위는 HOLD로 남긴다. public 관측/승인 테이블은 수정하지 않는다.
"""
from pathlib import Path
from datetime import datetime, timezone, date
from collections import defaultdict, Counter
import argparse,csv,hashlib,json,os

TABLES={
'source_asset':['run_id','asset_id','source_kind','namespace','source_path','source_sha256','byte_size','mtime_ns','processing_status','role_hint','metadata'],
'station_record':['run_id','station_key','namespace','station_id_raw','station_name_raw','metadata_present','source_payload'],
'equipment_record':['run_id','equipment_id','station_key','source_table','equipment_code','serial_raw','installed_at_raw','removed_at_raw','checked_at_raw','source_payload'],
'channel_contract':['run_id','contract_id','station_key','item_code_raw','equipment_code','unit_raw','approval_status','blockers','source_payload'],
'channel_equipment_candidate':['run_id','contract_id','equipment_id','match_status'],
'parquet_artifact':['run_id','artifact_id','asset_id','artifact_path','sha256','row_count','source_format','original_manifest','manifest_sha256'],
'document_record':['run_id','document_id','sha256','extraction_status','chunk_count','evidence_metadata'],
'document_location':['run_id','document_id','asset_id'],
'operation_event':['run_id','event_id','document_id','station_id_claim','event_type','event_date_raw','date_precision','event_date','equipment_expression','description','source_locator','source_excerpt','source_payload'],
'observation_coverage':['run_id','coverage_id','asset_id','station_key','item_code_raw','depth_identity','month_raw','first_raw_clock','last_raw_clock','row_count','null_count','profile_reference'],
'qc_review_interval':['run_id','interval_id','asset_id','station_key','item_code_raw','first_source_record','last_source_record','first_raw_clock','last_raw_clock','guide_document_id','review_status'],
'reference_definition':['run_id','reference_id','document_id','reference_type','source_locator','definition'],
}
RUN='foundation-20261005-v1'
def js(d):return json.dumps(d,ensure_ascii=False,sort_keys=True,separators=(',',':'),default=str)
def ident(*v):return hashlib.sha256(js(v).encode()).hexdigest()
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(4*1024**2),b''):h.update(b)
 return h.hexdigest()
def load(p):return json.loads(Path(p).read_text(encoding='utf8'))
def fid(p):return hashlib.sha256(os.path.normcase(os.path.normpath(str(p))).encode()).hexdigest()

def prepare(base,lake,out,sql):
 out.mkdir(parents=True,exist_ok=False)
 inputs={};counts=Counter();handles={};writers={}
 def evidence(p):
  p=Path(p);inputs[str(p)]=sha(p);return p
 def read(p):return load(evidence(p))
 for t in TABLES:
  handles[t]=(out/(t+'.csv')).open('x',encoding='utf8',newline='');writers[t]=csv.writer(handles[t])
 def row(t,*values):
  assert len(values)+1==len(TABLES[t]),(t,len(values))
  writers[t].writerow([RUN]+['\\N' if v is None else js(v) if isinstance(v,(dict,list)) else v for v in values]);counts[t]+=1
 evidence(sql)
 assets=set()
 empty_extra=read(lake/'metadata/closeout_20261005_v1/additional-empty-source-status.json')
 empty_ids={d['source_id'] for d in empty_extra['records']}
 reg=evidence(base/'outputs/full-lake/closeout-20261005-v2/file-source-registry.jsonl')
 with reg.open(encoding='utf8') as f:
  for s in f:
   d=json.loads(s);aid=d['source_id'];assert aid not in assets;assets.add(aid)
   row('source_asset',aid,'FILE','FILE_LOCATION',d['path'],d.get('source_sha256'),d['bytes'],d['mtime_ns'],
       'SOURCE_EMPTY_CONFIRMED' if aid in empty_ids else d['processing_status'],d['role_hint'],
       {'inventory_scope':d['scope'],'family':d['family'],'extension':d['extension'],'source_identity_evidence':d['content_identity']})
 print('prepared_assets',len(assets),flush=True)
 def asset(aid,kind,namespace,path,payload=None,digest=None):
  if aid not in assets:
   assets.add(aid);row('source_asset',aid,kind,namespace,path,digest,None,None,'SNAPSHOT_REGISTERED_UNAPPROVED',None,payload or {})
  return aid
 objects=read(base/'outputs/full-lake/closeout-20261005-v2/mdc-object-backlog.json')['objects']
 db_assets={}
 for d in objects:
  name=d['owner']+'.'+d['table'];aid=ident('MDC_OBJECT',name);db_assets[name]=aid
  asset(aid,'DB_OBJECT','MDC',name,d)
 for d in read(base/'outputs/full-lake/closeout-20261005-v1/project-root-additional-assets.json'):
  asset(fid(d['path']),'FILE','FILE_LOCATION',d['path'],d)
 for d in read(base/'outputs/full-lake/closeout-20261005-v1/archive-source-backlog.json')['archives']:
  key=d['archive_id'];asset(ident('ARCHIVE',key),'ARCHIVE_CONTAINER','ARCHIVE_ID:'+key,d['path'],d,d.get('prior_full_sha256'))
 cloud=evidence(base/'outputs/inventory-closeout/drive-local-reconciliation.jsonl')
 with cloud.open(encoding='utf8') as f:
  for s in f:
   d=json.loads(s);key=d['drive_id']
   asset(ident('DRIVE',key),'CLOUD_LOCATION','DRIVE_ID:'+key,d['drive_path'],d)

 stations={}
 def station(namespace,sid,payload=None,name=None):
  sid=str(sid) if sid is not None else 'UNRESOLVED_STATION'
  key=ident(namespace,sid)
  if key not in stations:stations[key]=[namespace,sid,name,bool(payload),{'snapshots':[payload]} if payload else {'reason':'SOURCE_ID_PRESENT_NO_STATION_HISTORY_BINDING'}]
  elif payload:
   old=stations[key];old[2]=name or old[2];old[3]=True;old[4].setdefault('snapshots',[]).append(payload)
  return key
 for s in read(base/'outputs/standardization/station-identity-register.json'):
  station('MDC_OCEAN_WEB',s['source_station_id'],s,s.get('source_name'))
 eq=read(base/'outputs/full-lake/mdc-current-evidence.json')['queries']
 equipment_by_key=defaultdict(list)
 for i,d in enumerate(eq['equipment']['rows']):
  key=station('MDC_OCEAN_WEB',d.get('obs_post_id'));eid=ident('equipment',i,d)
  row('equipment_record',eid,key,'MDC_EQUIPMENT_SNAPSHOT',d.get('te_code'),d.get('te_no'),d.get('te_start'),d.get('te_end'),d.get('last_check_date'),d)
  if d.get('te_code') is not None:equipment_by_key[(key,str(d['te_code']))].append(eid)
 for i,d in enumerate(eq['buoy_equipment']['rows']):
  key=station('MDC_BUOY_METADATA',d.get('station_id'));eid=ident('buoy-equipment',i,d)
  row('equipment_record',eid,key,'MDC_BUOY_EQUIPMENT_SNAPSHOT',d.get('equip_type'),d.get('equip_id'),d.get('equip_ins_date'),None,None,d)
 contracts=evidence(base/'outputs/full-lake/source-contract-review.jsonl')
 with contracts.open(encoding='utf8') as f:
  for i,s in enumerate(f):
   d=json.loads(s);key=station('MDC_OCEAN_WEB',d['station_id']);cid=ident('contract',i,d)
   row('channel_contract',cid,key,d['item'],d.get('equipment_code'),d['metadata'].get('unit'),'HOLD',d['blocking_reasons'],d)
   matches=equipment_by_key.get((key,str(d.get('equipment_code'))),[]) if d.get('equipment_code') is not None else []
   for eid in matches:row('channel_equipment_candidate',cid,eid,'UNIQUE_KEY_CANDIDATE' if len(matches)==1 else 'AMBIGUOUS_KEY_CANDIDATE')

 for family,fmt in [('mdc_full_20261004','oracle_string_snapshot'),('monthly_spool_20261004','sqlplus_string_records'),('historical_raw_20261005','positional_csv_strings')]:
  for p in (lake/'metadata'/family).glob('*.json'):
   if p.name in ('run-status.json','worklist.json'):continue
   d=read(p)
   if d['status'] not in ('RAW_SNAPSHOT_COMPLETE','RAW_PARSED_RECONCILED','RAW_CSV_STRINGS_COMPLETE'):continue
   if family.startswith('mdc'):
    name=d['table'];name=name if '.' in name else 'OCEAN_WEB.'+name;aid=db_assets[name]
   else:
    source=d.get('source_path',d.get('path'));aid=fid(source);assert aid in assets,source
   for a in d['files']:row('parquet_artifact',ident(a['path']),aid,a['path'],a['sha256'],a['rows'],fmt,str(p),inputs[str(p)])

 raw_manifest=lake/'metadata/raw/manifest.json';raw=read(raw_manifest);profile_assets={}
 for a in raw['files']:
  source=a['source_id'];aid=ident('CURATED_RAW_SNAPSHOT',source);profile_assets[source]=aid
  asset(aid,'CURATED_RAW_SNAPSHOT','CANONICAL_RAW',source,{'source_sha256':a.get('source_sha256'),'manifest':str(raw_manifest)},a.get('source_sha256'))
  row('parquet_artifact',ident(a['path']),aid,a['path'],a['sha256'],a['rows'],'canonical_raw',str(raw_manifest),inputs[str(raw_manifest)])
 docs={};locations=set()
 for d in read(base/'outputs/full-lake/document-extraction/effective-index.json'):
  did='sha256:'+d['sha256'];docs.setdefault(did,[d['sha256'],d['status'],d.get('chunks'),{'source':'full-lake/document-extraction','semantic_review':'PENDING'}])
  aid=asset(fid(d['path']),'FILE','FILE_LOCATION',d['path']);locations.add((did,aid))
 for d in read(base/'outputs/operational-documents/v1/documents.json'):
  did=d['document_id'];docs.setdefault(did,[d['source_sha256'],d['status'],None,{}]);docs[did][3]['structured_evidence']=d
  aid=asset(fid(d['source_path']),'FILE','FILE_LOCATION',d['source_path']);locations.add((did,aid))
 for did,v in docs.items():row('document_record',did,*v)
 for did,aid in sorted(locations):row('document_location',did,aid)
 for d in read(base/'outputs/operational-documents/v1/events.json'):
  when=date.fromisoformat(d['date_text']) if d['date_precision']=='day' else None
  row('operation_event',d['event_id'],d['evidence']['document_id'],d['station_id'],d['event_type'],d['date_text'],d['date_precision'],when,
      d.get('equipment_expression'),d['description'],'pdf_page:'+str(d['evidence']['pdf_page']),d.get('source_excerpt'),d)
 source_stations=defaultdict(set)
 p=base/'outputs/full-lake/closeout-20261005-v1/structural-qc/monthly-structural-counts.json'
 for i,d in enumerate(read(p)):
  source=d['source_id'];key=station('CANONICAL_RAW:'+source,d['station_id_raw']);source_stations[source].add(key)
  row('observation_coverage',ident('pilot',i,d),profile_assets[source],key,d['item_code_raw'],{},d['month_raw_clock'],d['first_raw_clock'],d['last_raw_clock'],d['rows'],None,str(p))
 for p in (lake/'metadata/mdc_full_20261004/profiles').glob('*.json'):
  profile=read(p);name=profile['source_table'];aid=db_assets['OCEAN_WEB.'+name]
  for i,d in enumerate(profile['groups']):
   key=station('MDC_OCEAN_WEB',d.get('OBS_POST_ID'))
   row('observation_coverage',ident(name,i,d),aid,key,d['OBS_ITEM_CODE'],{k:d[k] for k in ('WATER_STEP','FR_DEPTH','TO_DEPTH') if k in d},d['month_raw_clock'],d['first_raw_clock'],d['last_raw_clock'],d['records'],d.get('null_values'),str(p))
 for i,d in enumerate(read(base/'outputs/operational-documents/v1/qc-evidence-links.json')):
  source=d['source_id'];assert len(source_stations[source])==1
  row('qc_review_interval',ident('qc',i,d),profile_assets[source],next(iter(source_stations[source])),d['item'],d['first_source_record'],d['last_source_record'],d['start_raw_clock'],d['end_raw_clock'],d['guide_reference'],d['status'])
 codebook=read(base/'outputs/full-lake/closeout-20261005-v1/qc-reference-codebook.json');did='sha256:'+codebook['source_sha256'];assert did in docs
 row('reference_definition','qc-codebook-revised','sha256:'+codebook['source_sha256'],'QC_GUIDE_REFERENCE','pdf_page:23;pdf_page:35',codebook)
 for key,v in stations.items():row('station_record',key,*v)
 for h in handles.values():h.close()
 for p,digest in inputs.items():assert sha(p)==digest,('INPUT_CHANGED',p)
 manifest={'run_id':RUN,'created_at_utc':datetime.now(timezone.utc).isoformat(),'inputs':inputs,'tables':{t:{'columns':cols,'rows':counts[t],'sha256':sha(out/(t+'.csv'))} for t,cols in TABLES.items()},'public_mutations':False}
 manifest['fingerprint']=ident(manifest['inputs'],manifest['tables'])
 with (out/'prepared-manifest.json').open('x',encoding='utf8') as f:json.dump(manifest,f,ensure_ascii=False,indent=2)
 print('PREPARED',js(counts),flush=True)

def apply(out,sql):
 from sqlalchemy import create_engine
 from app.core.config import settings
 manifest=load(out/'prepared-manifest.json')
 # 배포 경로가 달라도 준비 단계에서 확정한 SQL 내용 해시는 같아야 한다.
 schema_hashes={h for p,h in manifest['inputs'].items() if Path(p).name=='foundation_registry_v1.sql'}
 assert len(schema_hashes)==1 and sha(sql) in schema_hashes,'SCHEMA_CHANGED'
 for name,d in manifest['tables'].items():assert sha(out/(name+'.csv'))==d['sha256'],'PREPARED_COPY_CHANGED'
 engine=create_engine(settings.DATABASE_URL,connect_args={'connect_timeout':10})
 connection=engine.raw_connection()
 try:
  cur=connection.cursor();cur.execute('SELECT current_database()');assert cur.fetchone()[0]=='ocean_ai_db','UNEXPECTED_TARGET_DATABASE'
  cur.execute("SET LOCAL lock_timeout='5s'");cur.execute("SET LOCAL statement_timeout='600s'")
  cur.execute('SELECT pg_try_advisory_xact_lock(20261005,6401)');assert cur.fetchone()[0],'IMPORT_ALREADY_RUNNING'
  cur.execute(sql.read_text(encoding='utf8'))
  cur.execute('SELECT input_manifest,status FROM foundation.ingestion_run WHERE run_id=%s',(RUN,));existing=cur.fetchone()
  if existing:
   assert existing[0]['fingerprint']==manifest['fingerprint'] and existing[1]=='COMPLETE','EXISTING_DIFFERENT_OR_INCOMPLETE_RUN'
   for name,d in manifest['tables'].items():
    cur.execute('SELECT count(*) FROM foundation.'+name+' WHERE run_id=%s',(RUN,));assert cur.fetchone()[0]==d['rows'],'EXISTING_COUNT_MISMATCH'
   connection.rollback();print('IDEMPOTENT_VERIFIED_NO_INSERT',flush=True);return
  cur.execute('INSERT INTO foundation.ingestion_run(run_id,input_manifest,status) VALUES (%s,%s::jsonb,\'LOADING\')',(RUN,js(manifest)))
  order=['source_asset','station_record','equipment_record','channel_contract','channel_equipment_candidate','parquet_artifact','document_record','document_location','operation_event','observation_coverage','qc_review_interval','reference_definition']
  for name in order:
   cols=','.join(TABLES[name])
   with (out/(name+'.csv')).open(encoding='utf8',newline='') as f:cur.copy_expert('COPY foundation.'+name+' ('+cols+") FROM STDIN WITH (FORMAT CSV, NULL '\\N')",f)
   cur.execute('SELECT count(*) FROM foundation.'+name+' WHERE run_id=%s',(RUN,));actual=cur.fetchone()[0];assert actual==manifest['tables'][name]['rows'],name
   print('LOADED',name,actual,flush=True)
  cur.execute("UPDATE foundation.ingestion_run SET status='COMPLETE',completed_at=now(),counts=%s::jsonb WHERE run_id=%s",(js({t:d['rows'] for t,d in manifest['tables'].items()}),RUN))
  connection.commit();print('COMMITTED',RUN,flush=True)
 except BaseException:
  connection.rollback();raise
 finally:connection.close();engine.dispose()

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('mode',choices=['prepare','apply']);p.add_argument('--base',type=Path,required=True);p.add_argument('--lake',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--schema',type=Path,required=True);a=p.parse_args()
 if a.mode=='prepare':prepare(a.base.resolve(),a.lake.resolve(),a.output.resolve(),a.schema.resolve())
 else:apply(a.output.resolve(),a.schema.resolve())
