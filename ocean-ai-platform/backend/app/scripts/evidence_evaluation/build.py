"""문서 후보 추출→기간 후보→전량 coverage gate→평가 프로토콜을 생성/보존 적재한다.

원문을 외부 모델에 보내지 않는다. 승인·Label·운영 모델을 자동 생성하지 않는다.
prepare/apply는 분리하며 apply는 해시·행 수·실행 잠금으로 재실행을 검증한다.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys

sys.path.insert(0,str(Path(__file__).resolve().parent))
from temporal import VERSION, digest, date_bounds, sensor_period_candidates, calendar_relation, evaluation_blockers
from benchmark import PROTOCOLS


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()


def dump(path, data):
    with path.open('x',encoding='utf8') as f:json.dump(data,f,ensure_ascii=False,indent=2,default=str)


def engine():
    from sqlalchemy import create_engine
    from app.core.config import settings
    return create_engine(settings.DATABASE_URL,connect_args={'connect_timeout':10})


def prepare(base, out):
    from sqlalchemy import text
    out.mkdir(parents=True,exist_ok=False)
    inputs={}
    def read(p):
        inputs[str(p)]=sha(p)
        return json.loads(p.read_text(encoding='utf8'))
    for p in Path(__file__).parent.glob('*.py'):inputs[str(p)]=sha(p)
    inputs[str(Path(__file__).with_name('schema.sql'))]=sha(Path(__file__).with_name('schema.sql'))
    e=engine()
    with e.connect() as c, c.begin():
        c.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY'))
        c.execute(text("SET LOCAL statement_timeout='90s'"))
        if c.execute(text('select current_database()')).scalar()!='ocean_ai_db':raise ValueError('WRONG_DB')
        rid=c.execute(text('select run_id from foundation.v_current_run')).scalar_one()
        def q(sql):return [dict(r) for r in c.execute(text(sql),{'r':rid}).mappings()]
        stations=q('select * from foundation.station_record where run_id=:r')
        contracts=q('select station_key,item_code_raw,approval_status from foundation.channel_contract where run_id=:r')
        coverage=q('select c.*,s.station_id_raw,s.namespace,a.source_path from foundation.observation_coverage c join foundation.station_record s using(run_id,station_key) join foundation.source_asset a using(run_id,asset_id) where c.run_id=:r')
        docs=q('select document_id from foundation.document_record where run_id=:r')
        ingestion=q('select run_id,started_at,completed_at,input_manifest from foundation.ingestion_run where run_id=:r')
    e.dispose()
    dump(out/'foundation-input-snapshot.json',{'stations':stations,'contracts':contracts,'coverage':coverage,'ingestion':ingestion})
    events=read(base/'outputs/operational-documents/v1/events.json')
    index=read(base/'outputs/full-lake/document-extraction/effective-index.json')
    document_ids={d['document_id'] for d in docs}
    assertions=[]; periods=[]
    for event in events:
        assertions.append({'assertion_id':event['event_id'],'document_id':event['evidence']['document_id'],
                           'station_key':None,'kind':event['event_type'],'payload':event})
    # 원천 관측소 시작일은 개소/항목 개시 의미 미확정 상태로 보존한다.
    for station in stations:
        for raw in station['source_payload'].get('snapshots',[]):
            date=raw.get('source_start_date_raw')
            if date:
                aid=digest([station['station_key'],raw])
                assertions.append({'assertion_id':aid,'document_id':None,'station_key':station['station_key'],
                    'kind':'STATION_SOURCE_START_DATE','payload':{'date_raw':date,'semantic_status':'START_DATE_MEANING_UNCONFIRMED','source':raw}})
                periods.append({'period_id':digest(['station',aid]),'period_kind':'STATION_OPERATION',
                    'start_assertion':aid,'end_assertion':None,'station_claim':station['station_id_raw'],
                    'start_raw':date,'end_status':'UNKNOWN','status':'CANDIDATE',
                    'blockers':['OPEN_CLOSE_RELOCATION_HISTORY_UNREVIEWED','SOURCE_START_DATE_MEANING_UNCONFIRMED']})
    # 문서 본문의 날짜+업무 단어 동시 출현을 근거 후보로 추출한다. 문서 제목 연도를 사건 날짜로 쓰지 않는다.
    scanned=set(); skipped=[]; chunks=0
    terms={'STATION_OPERATION':r'개소|신설|폐소|이설|운영중단|운영 중단|관측재개|관측 재개',
           'ITEM_OPERATION':r'관측개시|관측 개시|측정개시|측정 개시|관측중단|관측 중단',
           'SENSOR_EVENT':r'센서|교체|교정|회수|설치|장비',
           'QC_POLICY':r'품질관리|품질처리|QC|검사기준'}
    date_rx=re.compile(r'(?<!\d)((?:19|20)\d{2})[.\-/년]\s*(\d{1,2})(?:[.\-/월]\s*(\d{1,2}))?')
    for d in index:
        h=d['sha256']
        if h in scanned:continue
        scanned.add(h)
        p=base/'outputs/full-lake/document-extraction'/d['text_artifact']
        if not p.exists():skipped.append({'sha256':h,'reason':'TEXT_ARTIFACT_MISSING'});continue
        obj=read(p)
        if obj['source_sha256']!=h:raise ValueError('DOCUMENT_HASH_LINK_MISMATCH')
        did='sha256:'+h
        if did not in document_ids:raise ValueError('DOCUMENT_NOT_IN_FOUNDATION')
        for ch in obj['chunks']:
            chunks+=1
            text_body=ch['text'].replace('\x00',' ')
            for match in date_rx.finditer(text_body):
                raw=match.group(0); y,m,day=match.groups()
                try:date_bounds(f'{int(y):04}-{int(m):02}'+(f'-{int(day):02}' if day else ''))
                except ValueError:continue
                begin=max(0,match.start()-80); end=min(len(text_body),match.end()+180)
                excerpt=text_body[begin:end]
                kinds=[k for k,rx in terms.items() if re.search(rx,excerpt,re.I)]
                if not kinds:continue
                aid=digest([h,ch['locator'],match.start(),raw])
                assertions.append({'assertion_id':aid,'document_id':did,'station_key':None,
                    'kind':'DOCUMENT_DATE_MENTION','payload':{
                        'date_raw':raw,'date_precision':'day' if day else 'month',
                        'candidate_kinds':kinds,'locator':ch['locator'],
                        'text_offset':match.start(),'excerpt':excerpt,
                        'station_tokens':sorted(set(re.findall(r'\b(?:DT|SO|KG|TW|UN|HB|RD)_\d{4}\b',excerpt))),
                        'scope_status':'MENTION_ONLY_NOT_EVENT_OR_STATION_BINDING',
                        'text_artifact_sha256':inputs[str(p)]}})
    # 동일 명칭을 전체 문서에 전파하거나 단순 키워드 날짜를 승인 사건으로 만들지 않는다.
    assertions=list({a['assertion_id']:a for a in assertions}.values())
    sensor_periods=sensor_period_candidates(events); periods.extend(sensor_periods)
    matches=[]
    for p in sensor_periods:
        compatible={'C/T':{'WTP','SAL','WATER_TEMP','SALINITY','CONDUCTIVITY'}}.get(p['equipment_expression'],set())
        for row in coverage:
            if row['station_id_raw']!=p['station_claim'] or row['first_raw_clock'] is None:continue
            relation=calendar_relation(p,row['first_raw_clock'],row['last_raw_clock'])
            if relation=='NO_CALENDAR_OVERLAP':continue
            matches.append({'period_id':p['period_id'],'coverage_id':row['coverage_id'],
                'relation':relation,'item_compatible':row['item_code_raw'] in compatible,
                'payload':{'station_claim':p['station_claim'],'namespace':row['namespace'],
                           'item_code':row['item_code_raw'],'source':row['source_path'],
                           'blockers':p['blockers']+([] if row['item_code_raw'] in compatible else ['INCOMPATIBLE_ITEM'])}})
    reviews=[]; counts=Counter()
    if any(c['approval_status']=='APPROVED' for c in contracts):
        raise ValueError('NEW_APPROVALS_REQUIRE_REVIEW_ADAPTER')
    for row in coverage:
        # 현재 승인 기간이 없는 스냅샷만 감사한다. 새 승인은 별도 승인 원장 연결 후 평가한다.
        blockers=evaluation_blockers({'task':'forecast'})
        counts.update(blockers)
        reviews.append({'coverage_id':row['coverage_id'],'status':'BLOCKED','payload':{
            'source':row['source_path'],'station':row['station_id_raw'],'item':row['item_code_raw'],
            'first_clock':row['first_raw_clock'],'last_clock':row['last_raw_clock'],
            'rows':row['row_count'],'blockers':blockers,
            'note':'RAW_RECONCILIATION_UNVERIFIED means no approved row-level evaluation membership proof; previous raw file hash checks are retained separately.'}})
    datasets=[]
    for task,protocol in PROTOCOLS.items():
        reasons=list(counts) if task in ('forecast','anomaly_detection') else ['REVIEWED_GOLD_SET_MISSING','DOCUMENT_FAMILY_SPLIT_UNREVIEWED','CORPUS_RECONCILIATION_PENDING']
        if task=='anomaly_detection':reasons.append('LABEL_UNAPPROVED')
        if task=='report_generation':reasons.append('BLIND_REVIEW_AND_FACT_RUBRIC_REQUIRED')
        payload={'task':task,'eligible_members':0,'status':'BLOCKED','reasons':reasons,
                 'protocol_hash':digest(protocol),'membership':[],
                 'candidate_coverage_groups':len(coverage) if task in ('forecast','anomaly_detection') else 0}
        datasets.append({**payload,'dataset_hash':digest(payload)})
    tables={'assertions':assertions,'periods':periods,'matches':matches,'coverage_reviews':reviews,
            'datasets':datasets,'protocols':PROTOCOLS}
    for name,rows in tables.items():dump(out/(name+'.json'),rows)
    summary={'version':VERSION,'foundation_run':rid,'documents_scanned':len(scanned),'chunks_scanned':chunks,
             'skipped_documents':skipped,'assertions':len(assertions),'period_candidates':len(periods),
             'sensor_period_candidates':len(sensor_periods),'calendar_candidates':len(matches),
             'item_compatible_candidates':sum(m['item_compatible'] for m in matches),
             'coverage_groups_reviewed':len(reviews),'approved_dataset_members':0,
             'blocker_counts':dict(counts),'model_selection':'NOT_RUN_BLOCKED_DATASET'}
    dump(out/'summary.json',summary)
    files={p.name:sha(p) for p in out.iterdir() if p.is_file()}
    manifest={'version':VERSION,'foundation_run':rid,'inputs':inputs,'files':files,
              'created_at_utc':datetime.now(timezone.utc).isoformat()}
    manifest['fingerprint']=digest([rid,inputs,files]);manifest['run_id']='evidence-eval-'+manifest['fingerprint'][:20]
    dump(out/'manifest.json',manifest)
    print(json.dumps(summary,ensure_ascii=False))


def apply(out):
    from sqlalchemy import text
    m=json.loads((out/'manifest.json').read_text(encoding='utf8'))
    for name,h in m['files'].items():
        if sha(out/name)!=h:raise ValueError('OUTPUT_CHANGED:'+name)
    schema=Path(__file__).with_name('schema.sql')
    if sha(schema) not in {h for p,h in m['inputs'].items() if Path(p).name=='schema.sql'}:raise ValueError('SQL_CHANGED')
    read=lambda name:json.loads((out/(name+'.json')).read_text(encoding='utf8'))
    r=m['run_id'];fr=m['foundation_run'];e=engine()
    counts={}
    with e.begin() as c:
        if c.execute(text('select current_database()')).scalar()!='ocean_ai_db':raise ValueError('WRONG_DB')
        c.execute(text("SET LOCAL lock_timeout='5s'"));c.execute(text("SET LOCAL statement_timeout='180s'"))
        if not c.execute(text('SELECT pg_try_advisory_xact_lock(20261005,6502)')).scalar():raise ValueError('ALREADY_RUNNING')
        c.exec_driver_sql(schema.read_text(encoding='utf8'))
        old=c.execute(text('select fingerprint from evidence_eval.run where run_id=:r'),{'r':r}).scalar()
        if old is not None and old!=m['fingerprint']:raise ValueError('RUN_CONFLICT')
        mappings={
            'assertion':[{**a,'run_id':r,'foundation_run':fr,'payload':json.dumps(a['payload'],ensure_ascii=False)} for a in read('assertions')],
            'period_candidate':[{'run_id':r,'period_id':p['period_id'],'period_kind':p['period_kind'],
                                 'start_assertion':p['start_assertion'],'end_assertion':p['end_assertion'],'payload':json.dumps(p,ensure_ascii=False)} for p in read('periods')],
            'coverage_review':[{'run_id':r,'foundation_run':fr,**x,'payload':json.dumps(x['payload'],ensure_ascii=False)} for x in read('coverage_reviews')],
            'temporal_candidate':[{'run_id':r,'foundation_run':fr,**x,'payload':json.dumps(x['payload'],ensure_ascii=False)} for x in read('matches')],
            'dataset_snapshot':[{'run_id':r,'task':x['task'],'dataset_hash':x['dataset_hash'],'status':x['status'],'eligible_members':0,'payload':json.dumps(x,ensure_ascii=False)} for x in read('datasets')],
            'benchmark_protocol':[{'run_id':r,'task':k,'protocol_hash':digest(v),'payload':json.dumps(v,ensure_ascii=False)} for k,v in read('protocols').items()],
        }
        if old is None:
            c.execute(text('INSERT INTO evidence_eval.run(run_id,foundation_run,fingerprint,manifest) VALUES (:r,:fr,:fp,CAST(:m AS jsonb))'),{'r':r,'fr':fr,'fp':m['fingerprint'],'m':json.dumps(m)})
            for table,rows in mappings.items():
                if rows:
                    keys=list(rows[0]); cols=','.join(keys)
                    vals=','.join('CAST(:payload AS jsonb)' if k=='payload' else ':'+k for k in keys)
                    statement=text(f'INSERT INTO evidence_eval.{table} ({cols}) VALUES ({vals})')
                    for i in range(0,len(rows),500):c.execute(statement,rows[i:i+500])
        for table,rows in mappings.items():
            n=c.execute(text(f'SELECT count(*) FROM evidence_eval.{table} WHERE run_id=:r'),{'r':r}).scalar()
            if n!=len(rows):raise ValueError('COUNT_MISMATCH:'+table)
            counts[table]=n
        constraints=c.execute(text("select bool_and(convalidated) from pg_constraint where connamespace='evidence_eval'::regnamespace")).scalar()
        if not constraints:raise ValueError('INVALID_CONSTRAINT')
    e.dispose()
    result={'run_id':r,'counts':counts,'constraints_validated':True,'status':'IDEMPOTENT_VERIFIED' if old else 'COMMITTED'}
    path=out/('idempotency.json' if old else 'applied.json')
    if not path.exists():dump(path,result)
    print(json.dumps(result))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['prepare','apply']);p.add_argument('--base',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if a.mode=='prepare':prepare(a.base,a.output)
    else:apply(a.output)
