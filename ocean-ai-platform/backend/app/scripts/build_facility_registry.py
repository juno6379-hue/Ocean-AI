"""Append an evidence registry for the July 2026 facility review.

Observation coverage is never an operation interval. Year/month assertions use
date bounds and precision, not an invented event day. Existing metadata,
observation Parquet and vector documents are left intact. This is a review
registry, not an approved July operational census.
"""
import argparse, calendar, hashlib, json, sqlite3
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
import pyarrow as pa
import pyarrow.parquet as pq
from sqlalchemy import text
from app.core.database import engine
from app.rag.document_contract import load_contract, get_collection

def dumps(v): return json.dumps(v,ensure_ascii=False,sort_keys=True,default=str,separators=(',',':'))
def digest(v): return hashlib.sha256(dumps(v).encode()).hexdigest()
def read_sqlite(path,table):
    with sqlite3.connect(Path(path).as_uri()+'?mode=ro',uri=True) as c:
        c.row_factory=sqlite3.Row
        return [dict(r) for r in c.execute('select * from '+table)]
def date_bounds(value):
    if len(value)==4:return value+'-01-01',value+'-12-31','YEAR'
    if len(value)==7:
        y,m=map(int,value.split('-'));return value+'-01',f'{value}-{calendar.monthrange(y,m)[1]:02}','MONTH'
    raise ValueError('Only explicit year/month evidence is supported')

def facility_name(legacy_name, dictionary_rows):
    """Preserve exact-code source evidence; never merge facilities by name.

    A unique dictionary name may fill a missing legacy display name. Conflicting
    names remain explicit and do not approve identity, lifecycle or sea region.
    """
    names = sorted({r['name'].strip() for r in dictionary_rows
                    if isinstance(r.get('name'), str) and r['name'].strip()})
    legacy = legacy_name.strip() if isinstance(legacy_name, str) else None
    legacy = legacy or None
    conflict = len(names) > 1 or bool(legacy and names and names != [legacy])
    value = legacy or (names[0] if len(names) == 1 else None)
    return value, {
        'status': 'CONFLICT' if conflict else 'SOURCE_DICTIONARY_EXACT_CODE' if names else 'LEGACY_ONLY' if legacy else 'MISSING',
        'legacy_name': legacy, 'dictionary_names': names,
        'dictionary_evidence': dictionary_rows,
        'identity_approved': False,
    }

# Columns not evidenced remain typed NULL, with an explicit reason in payload.
SCHEMAS={
 'source_identity':{'station_code':'text','namespace':'text','station_name_raw':'text','metadata_present':'bool','payload':'json'},
 'facility':{'station_code':'text','station_name':'text','legacy_network':'text','program_code':'text','facility_type':'text','lifecycle_state':'text','operating_asof':'bool','valid_from':'text','valid_to':'text','payload':'json'},
 'lifecycle_claim':{'event_type':'text','entity_name':'text','entity_level':'text','station_code':'text','successor_code':'text','date_earliest':'text','date_latest':'text','date_precision':'text','source_sha256':'text','locator':'text','review_status':'text','payload':'json'},
 'channel_month':{'station_code':'text','item_code':'text','source_group':'text','month':'text','held_rows':'bigint','first_clock':'text','last_clock':'text','physical_sensor_id':'text','nominal_interval_seconds':'bigint','valid_from':'text','valid_to':'text','approval_status':'text','payload':'json'},
 'equipment_claim':{'station_code':'text','equipment_code':'text','manufacturer':'text','model':'text','serial_raw':'text','measurement_method':'text','accuracy':'text','measurement_range':'text','operating_environment':'text','structure_type':'text','valid_from':'text','valid_to':'text','source_sha256':'text','locator':'text','payload':'json'},
 'document':{'source_sha256':'text','path':'text','sql_chunks':'bigint','vector_state':'text','payload':'json'},
 'document_link':{'station_code':'text','item_code':'text','link_role':'text','source_sha256':'text','locator':'text','payload':'json'},
 'reference_claim':{'claim_kind':'text','source_sha256':'text','locator':'text','applies_to':'text','payload':'json'},
}

def build(a):
    audit=json.loads((a.audit/'audit.json').read_text(encoding='utf8'))
    cross=json.loads((a.audit/'station-store-crosswalk.json').read_text(encoding='utf8'))
    reports=json.loads((a.audit/'selected-reports.json').read_text(encoding='utf8'))
    view=a.snapshot; sqlite=view/'validation.sqlite3'
    data={t:[] for t in SCHEMAS}; paths={}
    def add(table,row):
        value={k:row.get(k) for k in SCHEMAS[table]}
        value['record_id']=digest(value);data[table].append(value)
    def doc(sha,path):
        if sha and path:paths.setdefault(sha,set()).add(path)
    for r in audit['station_records']:
        add('source_identity',{'station_code':r['station_id_raw'],'namespace':r['namespace'],'station_name_raw':r['station_name_raw'],'metadata_present':r['metadata_present'],'payload':r})
    name_evidence = defaultdict(list)
    for candidate in read_sqlite(sqlite, 'source_station_dictionary'):
        name_evidence[candidate['code']].append(candidate)
    for r in cross:
        old=r['db_metadata'] or {}
        name, name_resolution = facility_name(old.get('station_name'), name_evidence[r['station_code']])
        add('facility',{'station_code':r['station_code'],'station_name':name,
            'legacy_network':old.get('network_type'),'lifecycle_state':'UNCONFIRMED','payload':{
            **r,'name_resolution':name_resolution,'as_of':a.as_of,'reason':'Legacy classification may include historical/survey locations; no approved lifecycle interval.',
            'count_role':'REGISTERED_OR_DATA_HELD_CODE_NOT_CANONICAL_ACTIVE_FACILITY'}})
    for r in pq.read_table(view/'station-item-month-validation.parquet').to_pylist():
        # Preserve the actual source/item/depth/month grain and evidence candidates.
        add('channel_month',{'station_code':r['station_code'],'item_code':r['item_code'],'source_group':r['source_group'],
            'month':str(r['month'])[:7],'held_rows':r['held_rows'],'first_clock':str(r['first_clock']) if r['first_clock'] else None,
            'last_clock':str(r['last_clock']) if r['last_clock'] else None,'physical_sensor_id':r['physical_sensor_id'],
            'valid_from':r['valid_from'],'valid_to':r['valid_to'],'approval_status':r['approval_status'],
            'payload':{k:r.get(k) for k in ['depth_step','depth_from','depth_to','sensor_decision','period_decision','timezone_decision',
               'source_qc_present_rows','qc_approval_decision','physical_sensor_candidate_ids','installation_claim_ids','history_evidence','reason']}})
    # Exact report assertions; code links are separately reviewed candidates.
    plan=reports[1]; sha=plan['sha256']; doc(sha,plan['path'])
    lifecycle=[
      ('RETIRED','굴업도','FACILITY','DT_0038',None,'2020',21,'Report names the tide station; exact name/type DB match.'),
      ('RETIRED','순천만','FACILITY','DT_0055',None,'2021',21,'Not the unrelated UN_* environmental stations.'),
      ('RETIRED','경인항','FACILITY','DT_0058',None,'2022',21,'Not the TW_0077 buoy of the same name.'),
      ('RETIRED','복사초','FACILITY',None,None,'2024',21,'DT_0041/RT_0051 identity unresolved; do not count twice.'),
      ('RELOCATED','굴업도 → 향화도','FACILITY','DT_0038','DT_0066','2020',21,'Report successor name and exact tide-code candidates.'),
      ('RELOCATED','순천만 → 여호항','FACILITY','DT_0055','DT_0092','2021',21,'Exclude same-name SO historical survey codes.'),
      ('RELOCATED','경인항 → 소무의도','FACILITY','DT_0058','DT_0093','2022',21,'Separate place/site change from a rename.'),
      ('COMMISSIONED','독도','FACILITY','DT_0903',None,'2024',21,'New-code candidate; do not replace old DT_0040 history.'),
      ('COMMISSIONED','비금도','FACILITY','DT_0095',None,'2025',21,'Trial and operational commissioning dates need separate claims.'),
      ('MERGED','백령도서부·백령도동부 → 백령도','HF_AREA',None,None,'2022-01',45,'Area merge does not mean antennas removed.'),
      ('RETIRED','태안','HF_AREA',None,None,'2022',45,'Area retirement; no individual antenna retirement asserted.'),
      ('RELOCATED','평택·당진항 → 군산항','HF_AREA',None,None,'2023-12',45,'Area name/date, not a sensor validity interval.'),
      ('RELOCATED','안섬포구 → 자치섬','HF_SITE',None,None,'2023',45,'Site code crosswalk pending.'),
      ('RELOCATED','서부두 → 말도','HF_SITE',None,None,'2023',45,'Site code crosswalk pending.'),
      ('RELOCATED','한진포구 → 야미도','HF_SITE',None,None,'2023',45,'Site code crosswalk pending.'),
    ]
    for event,name,level,code,successor,date,page,reason in lifecycle:
        lo,hi,precision=date_bounds(date)
        add('lifecycle_claim',{'event_type':event,'entity_name':name,'entity_level':level,'station_code':code,'successor_code':successor,
            'date_earliest':lo,'date_latest':hi,'date_precision':precision,'source_sha256':sha,'locator':f'pdf_page:{page}',
            'review_status':'REPORT_VISUALLY_CHECKED_CODE_CANDIDATE','payload':{'date_raw':date,'reason':reason,'approval_status':'UNAPPROVED',
            'exact_event_date':None,'asof_20260731_reopening_check':'NOT_COMPLETE'}})
    for r in data['facility']:
        claims=[x for x in data['lifecycle_claim'] if x['station_code']==r['station_code']]
        r['payload']['lifecycle_claim_ids']=[x['record_id'] for x in claims]
        if any(x['event_type']=='RETIRED' for x in claims):r['lifecycle_state']='RETIRED_REPORTED_REOPENING_UNCHECKED'
        elif r['station_code'] in {'DT_0041','RT_0051'}:r['lifecycle_state']='RETIRED_NAME_CODE_AMBIGUOUS'
        elif claims:r['lifecycle_state']='COMMISSION_OR_CHANGE_REPORTED'
        r['record_id']=digest({k:v for k,v in r.items() if k!='record_id'})
    for table in ['reviewed_sensor_claims','management_installation_claims','history_claims']:
        for r in read_sqlite(sqlite,table):
            doc(r['sha256'],r['path'])
            codes=[r['station_code']] if r.get('station_code') else json.loads(r.get('station_codes') or '[]')
            for code in codes or [None]:
                add('document_link',{'station_code':code,'link_role':table,'source_sha256':r['sha256'],'locator':r['locator'],'payload':r})
                if table!='history_claims':
                    add('equipment_claim',{'station_code':code,'manufacturer':r.get('manufacturer'),'model':r.get('model'),
                     'serial_raw':r.get('serial'),'valid_from':r.get('valid_from'),'valid_to':r.get('valid_to'),
                     'source_sha256':r['sha256'],'locator':r['locator'],'payload':{**r,
                     'missing_spec_reason':'Measurement method/accuracy/range/environment and channel validity need exact model/document evidence.'}})
    for event in data['lifecycle_claim']:
        add('document_link',{'station_code':event['station_code'],'link_role':'LIFECYCLE_REPORT_ASSERTION','source_sha256':sha,'locator':event['locator'],'payload':event})
    for r in reports:doc(r['sha256'],r['path'])
    add('reference_claim',{'claim_kind':'NETWORK_COUNTS','source_sha256':reports[0]['sha256'],'locator':'pdf_page:1/table:1-1','applies_to':'REPORT_2025_ONLY',
        'payload':{'tide':55,'marine':2,'buoy':36,'hf_sites':44,'hf_areas':16,'science':3,'total':140,'related_agency_buoys_excluded':6,
        'table_basis':'2025-12','prose_basis':'2025-11','basis_conflict':True,'approved_for_20260731':False}})
    add('reference_claim',{'claim_kind':'PLANNED_EQUIPMENT_TYPES','source_sha256':sha,'locator':'pdf_page:21/table:14-8','applies_to':'NEW_SITE_PLANNING_NOT_INSTALLED_EQUIPMENT',
        'payload':{'A':{'structure':'건물형(우물식)','method':['디지털 부표식','레이더식(MIROS)'],'items':['조위','수온','염분','기압','기온','풍향','풍속']},
        'B':{'structure':'타워형','method':['레이더식(MIROS)'],'items':['조위','기압','기온','풍향','풍속']},
        'C':{'structure':'TRBM','method':['압력식(비 실시간)'],'items':['조위','수온','염분']},'do_not_assign_to_existing_sensors':True}})
    ledger=Path(r'C:\AI_Observation\ocean-ai-platform\backend\app\data\document_pipeline\ingestion.sqlite3')
    bysha=defaultdict(list)
    for r in read_sqlite(ledger,'files'):
        if r.get('checksum'):bysha[r['checksum']].append(r)
    contract=load_contract();collection=get_collection(contract,create=False)
    selected_shas={r['sha256'] for r in reports}
    with engine.connect() as c:
        sqlcounts={r[0]:r[1] for r in c.execute(text('select document_id,count(*) from document_index where embedding_version=:v group by document_id'),{'v':contract['embedding_version']})}
    for sha,locations in paths.items():
        rows=bysha[sha]; ids={r['document_id'] for r in rows if r.get('document_id') in sqlcounts}
        vector_state='LIVE_ID_RECONCILIATION_REQUIRED';checks=[]
        if sha in selected_shas:
            for did in ids:
                with engine.connect() as c:
                    sql_ids=set(c.execute(text('select chunk_id from document_index where document_id=:d and embedding_version=:v'),{'d':did,'v':contract['embedding_version']}).scalars())
                vector_ids=set(collection.get(where={'document_id':did},include=[])['ids'])
                checks.append({'document_id':did,'sql_chunks':len(sql_ids),'vector_chunks':len(vector_ids),'ids_equal':sql_ids==vector_ids})
            vector_state='SQL_VECTOR_IDS_MATCH' if checks and all(c['ids_equal'] for c in checks) else 'UNPUBLISHED_OR_PARTIAL'
        add('document',{'source_sha256':sha,'path':sorted(locations)[0],'sql_chunks':sum(sqlcounts[d] for d in ids),
            'vector_state':vector_state,'payload':{'locations':sorted(locations),'document_ids':sorted(ids),'vector_checks':checks,'embedding_version':contract['embedding_version'],
            'ledger':[{k:r.get(k) for k in ['path','document_id','status','embedding_version','chunks']} for r in rows],
            'unpublished_reason':'No active SQL document ID' if not ids else None}})
    now=datetime.now(timezone.utc);run_id='facility-'+now.strftime('%Y%m%dT%H%M%SZ')
    target=a.output/run_id;target.mkdir(parents=True,exist_ok=False)
    manifest={'run_id':run_id,'as_of':a.as_of,'snapshot':view.name,'created_at':now.isoformat(),
       'status':'PREPARED_REVIEW_ONLY','operating_facility_count':None,'official_20260731_count_status':'NOT_ESTABLISHED','files':{}}
    sqltypes={'text':'TEXT','json':'JSONB','bool':'BOOLEAN','bigint':'BIGINT'}
    arrowtypes={'text':pa.string(),'json':pa.string(),'bool':pa.bool_(),'bigint':pa.int64()}
    for table,columns in SCHEMAS.items():
        rows=list({r['record_id']:r for r in data[table]}.values());data[table]=rows
        export=[{'run_id':run_id,**{k:dumps(v) if columns.get(k)=='json' else v for k,v in r.items()}} for r in rows]
        schema=pa.schema([('run_id',pa.string()),('record_id',pa.string())]+[(k,arrowtypes[t]) for k,t in columns.items()])
        dest=target/(table+'.parquet');pq.write_table(pa.Table.from_pylist(export,schema=schema),dest,compression='zstd')
        actual=pq.read_table(dest).to_pylist()
        if actual!=export:raise RuntimeError('Parquet reread mismatch: '+table)
        with dest.open('rb') as f:sha=hashlib.file_digest(f,'sha256').hexdigest()
        manifest['files'][table]={'path':str(dest),'rows':len(export),'sha256':sha,'reread':'PASS'}
    # Publish all relational rows atomically. A failure leaves unapproved prepared
    # files for inspection; it never makes a partial SQL run appear complete.
    with engine.begin() as c:
        c.execute(text('CREATE SCHEMA IF NOT EXISTS facility_registry'))
        c.execute(text('CREATE TABLE IF NOT EXISTS facility_registry.run(run_id TEXT PRIMARY KEY, as_of DATE NOT NULL, manifest JSONB NOT NULL)'))
        c.execute(text('INSERT INTO facility_registry.run VALUES(:r,:d,CAST(:m AS JSONB))'),{'r':run_id,'d':a.as_of,'m':dumps(manifest)})
        for table,columns in SCHEMAS.items():
            cols=', '.join('"'+k+'" '+sqltypes[t] for k,t in columns.items())
            c.execute(text(f'CREATE TABLE IF NOT EXISTS facility_registry.{table}(run_id TEXT REFERENCES facility_registry.run(run_id),record_id TEXT,{cols},PRIMARY KEY(run_id,record_id))'))
            names=['run_id','record_id',*columns]
            vals=[f'CAST(:{k} AS JSONB)' if columns.get(k)=='json' else ':'+k for k in names]
            stmt=text(f'INSERT INTO facility_registry.{table} ('+','.join('"'+k+'"' for k in names)+') VALUES ('+','.join(vals)+')')
            export=[{'run_id':run_id,**{k:dumps(v) if columns.get(k)=='json' else v for k,v in r.items()}} for r in data[table]]
            for i in range(0,len(export),500):c.execute(stmt,export[i:i+500])
            count=c.execute(text(f'SELECT count(*) FROM facility_registry.{table} WHERE run_id=:r'),{'r':run_id}).scalar_one()
            if count!=len(export):raise RuntimeError('SQL row count mismatch: '+table)
            manifest['files'][table]['sql_rows']=count
        manifest['status']='PUBLISHED_REVIEW_ONLY'
        c.execute(text('UPDATE facility_registry.run SET manifest=CAST(:m AS JSONB) WHERE run_id=:r'),{'m':dumps(manifest),'r':run_id})
    (target/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf8')
    (a.audit/'registry-publication.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(manifest,ensure_ascii=False,indent=2),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--audit',type=Path,required=True);p.add_argument('--snapshot',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--as-of',default='2026-07-31')
    build(p.parse_args())
