"""One native-clock QC workspace; raw literals never become approved QC flags.

Operational ledgers are counted read-only. Without physical-source/codebook and
availability bindings, their contents cannot be backdated into a raw July view.
"""
from collections import Counter, defaultdict
from datetime import date, datetime, time
from pathlib import Path
import re

from fastapi import HTTPException
from sqlalchemy import inspect, text
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import settings
from app.models.domain import StationMetadata
from app.services import lake_browser as lake, observation_asof as dated, metric_completion as metrics
from app.services.native_month_metrics import SOURCES, asset_month, digest, file_hash, quote, typed_key
from app.services.qc_rule_engine import catalog as rule_catalog
from app.services.station_classification import reference_records, resolve_scope, sql_scope

SCHEMA='qc-workspace-1'
MAX_MONTHS=48
CASE_LIMIT=15
QC_FIELDS={'qc_raw','mq_raw','n1_aqc_raw','QC_FLAG','MQC_FLAG','N1_AQC_FLAG'}
TABLES=('qc_rule_definition','qc_rule_result','qc_flag_history','ai_label','ai_prediction_result',
        'approval_history','agent_task_approvals','agent_workflow_run','agent_workflow_transition',
        'source_contract_packets','source_contract_decisions','source_observation_binding',
        'quality_collection_report','daily_inspection_report','operation_log','event_registry',
        'model_registry','dataset_registry')
BLOCKERS=['SOURCE_SEMANTIC_UNIT_AND_SENSOR_EPISODE_UNRESOLVED',
          'SOURCE_QC_CODEBOOK_EFFECTIVE_PERIOD_UNRESOLVED',
          'NATIVE_CLOCK_TIMEZONE_AND_AVAILABILITY_UNRESOLVED',
          'APPROVED_QC_LEDGER_NOT_BOUND_TO_SELECTED_RAW_ROWS']


def validate_scope(source,start,end,day,clock,station='',item='',network='',sea='',qc_field='',
                   qc_literal=None,qc_literal_is_null=False):
    if source not in SOURCES:raise HTTPException(422,'QC 원천은 기준일 조회를 지원하는 보존 원천을 선택하세요.')
    month_pattern=r'20\d{2}-(0[1-9]|1[0-2])'
    if not all(isinstance(v,str) and re.fullmatch(month_pattern,v) for v in (start,end)):
        raise HTTPException(422,'조회 월 형식이 잘못됐습니다.')
    try:
        selected_day=date.fromisoformat(str(day));selected_clock=time.fromisoformat(str(clock))
    except (TypeError,ValueError):raise HTTPException(422,'원문 기준일시 형식이 잘못됐습니다.') from None
    if selected_clock.tzinfo is not None:raise HTTPException(422,'기준시각은 offset 없는 원문 시계 기준입니다.')
    span=(int(end[:4])-int(start[:4]))*12+int(end[5:])-int(start[5:])+1
    if span<1 or span>MAX_MONTHS or end>str(selected_day)[:7]:
        raise HTTPException(422,'조회 기간은 기준월까지 최대 48개월입니다.')
    for value,bound in ((station,40),(item,80),(network,80),(sea,80),(qc_field,32)):
        if not isinstance(value,str) or len(value)>bound:raise HTTPException(422,'QC 필터 길이가 잘못됐습니다.')
    if qc_field and qc_field not in QC_FIELDS:raise HTTPException(422,'지원되지 않는 원천 QC 필드입니다.')
    if qc_literal is not None and (not isinstance(qc_literal,str) or len(qc_literal)>128):
        raise HTTPException(422,'QC 원문 literal 길이가 잘못됐습니다.')
    if not isinstance(qc_literal_is_null,bool) or (qc_literal is not None and qc_literal_is_null):
        raise HTTPException(422,'QC NULL 필터와 literal 필터를 함께 사용할 수 없습니다.')
    if (qc_literal is not None or qc_literal_is_null) and not qc_field:
        raise HTTPException(422,'원문 literal 필터에는 QC 필드가 필요합니다.')
    return dict(source=source,from_month=start,to_month=end,as_of_day=str(selected_day),
        as_of_time=str(selected_clock),cutoff_native=str(datetime.combine(selected_day,selected_clock)),
        station=station,item=item,network=network,sea=sea,qc_field=qc_field,
        qc_literal=qc_literal,qc_literal_is_null=qc_literal_is_null)


def registry_counts(db):
    if db is None:return {'state':'UNAVAILABLE','counts':{key:None for key in TABLES},
        'missing_tables':list(TABLES),'scope':'GLOBAL_REGISTERED_NOT_SELECTED_RESULTS'}
    try:
        with db.no_autoflush:
            existing=set(inspect(db.get_bind()).get_table_names())
            counts={key:db.execute(text('SELECT count(*) FROM '+key)).scalar_one() if key in existing else None for key in TABLES}
        missing=[key for key in TABLES if key not in existing]
        return dict(state='TABLES_ABSENT' if missing else 'AVAILABLE',counts=counts,missing_tables=missing,
                    scope='GLOBAL_REGISTERED_NOT_SELECTED_RESULTS')
    except (SQLAlchemyError,AttributeError,TypeError):
        raise HTTPException(503,'QC 등록 원장 조회 실패') from None


def _rate(count,total):return 100*count/total if count is not None and total else None


def _metrics(rows):
    raw=metrics.raw_metrics(rows)
    return dict(held_rows=raw['held_rows'],qc_present_rows=raw['source_qc_present_rows'],
        qc_presence_rate=raw['source_qc_presence_rate'],missing_rows=raw['missing_value_rows'],
        missing_rate=raw['missing_value_rate'],unassessed_rate=100.0 if raw['held_rows'] else None,
        interpreted=False)


def _scope_matches(code,scope):
    return scope is None or (code in scope['include'] if 'include' in scope else code not in scope['exclude'])


def _files(view,scope):
    authority=view/'file-only-timeseries.duckdb'
    assets=[r for r in lake.monthly_assets(str(authority),authority.stat().st_mtime_ns)
            if r['source_group']==scope['source'] and scope['from_month']<=asset_month(r)<=scope['to_month']]
    root=lake.historical_root() if scope['source']=='GD_OBS_ST_MONTHLY' else Path(settings.SHARE_MONTHLY_LAKE_ROOT)
    files=[]
    for row in assets:
        path=lake.inside(root,row['parquet_path']);stat=path.stat()
        lake.verify_file(str(path),stat.st_mtime_ns,stat.st_size,row['parquet_sha256'])
        files.append(dict(row,parquet_path=str(path),bytes=stat.st_size,mtime_ns=stat.st_mtime_ns))
    return files


def raw_cases(files,scope,station_scope,selected_rows):
    """Bounded newest exact raw rows; source field/NULL/empty/padding stay distinct."""
    fields=scope['qc_field'];literal=scope['qc_literal'];null=scope['qc_literal_is_null']
    if fields:
        matching=sum(c['count'] for row in selected_rows for c in row.get('qc_codes',[])
                     if c['field']==fields and (null and c['literal'] is None or
                        not null and (literal is None or c['literal']==literal)))
    else:matching=sum(row['raw_rows'] for row in selected_rows)
    result=dict(rows=[],total_matching_rows=matching,limit=CASE_LIMIT,
        ordering='NATIVE_CLOCK_DESC_FILE_ROW_DESC',population='RAW_SOURCE_ROWS_NOT_ANOMALY_RESULTS',
        sampling='LATEST_MATCHING_ROWS_MAX_15',source_qc_interpreted=False)
    if not matching:return result
    if not files:raise HTTPException(503,'QC 사례에 필요한 원천 파일이 없습니다.')
    paths=[r['parquet_path'] for r in files]
    with lake.connection() as c:
        c.read_parquet(paths,hive_partitioning=False,filename=True,file_row_number=True,union_by_name=True).create_view('raw_files')
        columns={r[0] for r in c.execute('DESCRIBE raw_files').fetchall()}
        def col(name):return quote(name) if name in columns else 'NULL::VARCHAR'
        if scope['source']=='GD_OBS_ST_MONTHLY':
            projection="trim(station_raw) station_code,trim(item_raw) item_code,time_raw observed_time_raw,value_raw,qc_raw source_qc_raw,mq_raw source_mq_raw,n1_aqc_raw source_n1_qc_raw,NULL::VARCHAR depth_step,NULL::VARCHAR depth_from,NULL::VARCHAR depth_to"
            predicate=" WHERE record_class='OBSERVATION_SHAPED_UNVALIDATED'"
            aliases={'qc_raw':'source_qc_raw','mq_raw':'source_mq_raw','n1_aqc_raw':'source_n1_qc_raw'}
        else:
            if 'FROM_DEPTH' in columns and 'FR_DEPTH' in columns:raise HTTPException(409,'원천 수심 별칭 충돌')
            depth_from='FROM_DEPTH' if 'FROM_DEPTH' in columns else 'FR_DEPTH'
            projection='trim(OBS_POST_ID) station_code,trim(OBS_ITEM_CODE) item_code,OBS_TIME observed_time_raw,OBS_VALUE value_raw,'+','.join(col(name)+' '+alias for name,alias in (
                ('QC_FLAG','source_qc_raw'),('MQC_FLAG','source_mq_raw'),('N1_AQC_FLAG','source_n1_qc_raw'),
                ('WATER_STEP','depth_step'),(depth_from,'depth_from'),('TO_DEPTH','depth_to')))
            predicate=''
            aliases={'QC_FLAG':'source_qc_raw','MQC_FLAG':'source_mq_raw','N1_AQC_FLAG':'source_n1_qc_raw'}
        if fields not in aliases and fields:return result
        c.execute('CREATE VIEW normalized AS SELECT '+projection+',filename,file_row_number FROM raw_files'+predicate)
        begin=scope['from_month']+'-01 00:00:00'
        stop=dated.day_bounds(scope['to_month'],scope['as_of_day'],scope['as_of_time'])[1]
        where='regexp_full_match(CAST(observed_time_raw AS VARCHAR),?) AND try_cast(observed_time_raw AS TIMESTAMP)>=?::TIMESTAMP AND try_cast(observed_time_raw AS TIMESTAMP)<?::TIMESTAMP'
        args=[dated.NATIVE_PATTERN,begin,str(stop)]
        for field,key in (('station_code','station'),('item_code','item')):
            if scope[key]:where+=' AND '+field+'=?';args.append(scope[key])
        if station_scope:
            # Intersect the DB classification with the exact held source codes.
            # A large NOT IN registry is unnecessarily expensive for two held
            # unregistered codes and cannot improve this already-bound scope.
            source_codes=sorted({row['station_code'] for row in selected_rows})
            extra,values=sql_scope({'include':source_codes})
            where+=extra;args+=values
        if fields and null:where+=' AND '+aliases[fields]+' IS NULL'
        elif fields and literal is not None:where+=' AND '+aliases[fields]+'=?';args.append(literal)
        rows=lake.records(c.execute('SELECT * FROM normalized WHERE '+where+
            ' ORDER BY try_cast(observed_time_raw AS TIMESTAMP) DESC,filename DESC,file_row_number DESC LIMIT ?',args+[CASE_LIMIT]))
    lookup={str(Path(r['parquet_path']).resolve()):r for r in files}
    for row in rows:
        asset=lookup[str(Path(row.pop('filename')).resolve())]
        path=Path(asset['parquet_path']);stat=path.stat()
        lake.verify_file(str(path),stat.st_mtime_ns,stat.st_size,asset['parquet_sha256'])
        row.update(file=path.name,source_sha256=asset['source_sha256'],parquet_sha256=asset['parquet_sha256'],
            source_group=scope['source'],physical_sensor_id=None,unit=None,timezone=None,
            classification='UNINTERPRETED',available_at=None,approved=False,
            historical_availability_asserted=False,workflow_id=None,workflow_revision=None,recommendation_sha256=None)
        row['case_key']=digest(dict(parquet_sha256=row['parquet_sha256'],file_row_number=row['file_row_number']))
    if len(rows)!=min(matching,CASE_LIMIT):raise HTTPException(409,'QC 사례 원문과 집계 분모가 일치하지 않습니다.')
    result['rows']=rows
    return result


def build_packet(scope,view,all_rows,names,metadata,station_scope,registry,cases,unlocatable=0,files=()):
    selected=[r for r in all_rows if _scope_matches(r['station_code'],station_scope)
              and (not scope['station'] or r['station_code']==scope['station'])
              and (not scope['item'] or r['item_code']==scope['item'])]
    raw=metrics.raw_metrics(selected);total=raw['held_rows']
    full_codes={r['station_code'] for r in all_rows};index=defaultdict(list)
    for row in metadata:index[row['station_id']].append(row)
    station_options=[]
    scoped_rows=[r for r in all_rows if _scope_matches(r['station_code'],station_scope)]
    for code in sorted(full_codes):
        rows=[r for r in scoped_rows if r['station_code']==code]
        if not rows:continue
        refs=index.get(code,[]);ref=refs[0] if len(refs)==1 else {}
        station_options.append(dict(station_code=code,station_name=names.get(code) or ref.get('reference_name') or ref.get('station_name') or code,
            network_type=ref.get('network_type'),sea_area=ref.get('sea_area'),
            classification_state='RESOLVED' if len(refs)==1 else 'AMBIGUOUS' if refs else 'UNREGISTERED',held_rows=sum(r['raw_rows'] for r in rows)))
    item_options=Counter()
    for row in scoped_rows:
        if not scope['station'] or row['station_code']==scope['station']:item_options[row['item_code']]+=row['raw_rows']
    network_counts=Counter();sea_counts=Counter()
    for code in full_codes:
        refs=index.get(code,[])
        if len(refs)==1:
            # Registered NULL network fields are not absent registry rows and
            # resolve_scope has no invented network-NULL selector.
            if refs[0].get('network_type'):network_counts[refs[0]['network_type']]+=1
            sea_counts[refs[0].get('sea_area') or '__UNASSIGNED__']+=1
        elif not refs:network_counts['__UNREGISTERED__']+=1
    by_month=defaultdict(list);by_grain=defaultdict(list)
    for row in selected:
        by_month[row['month'][:7]].append(row);by_grain[(row['station_code'],row['item_code'])].append(row)
    monthly=[]
    for month in metrics.calendar_months(scope['from_month'],scope['to_month']):
        monthly.append(dict(month=month,**_metrics(by_month.get(month,[]))))
    matrix=[]
    for (code,item),rows in sorted(by_grain.items()):
        grains={typed_key(r)[2:] for r in rows}
        matrix.append(dict(station_code=code,station_name=names.get(code) or code,item_code=item,state='UNKNOWN',
            **_metrics(rows),typed_grains=[dict(zip(('depth_step','depth_from','depth_to'),[pair[1] for pair in grain])) for grain in sorted(grains,key=str)],
            depth_aggregation='ALL_SELECTED_TYPED_DEPTHS_WEIGHTED_BY_RAW_ROWS'))
    field_totals=Counter()
    for row in raw['qc_codes']:field_totals[row['field']]+=row['count']
    distribution=[dict(field=r['field'],literal=r['literal'],count=r['count'],denominator=field_totals[r['field']],
        rate=_rate(r['count'],field_totals[r['field']]),interpreted=False) for r in raw['qc_codes']]
    unavailable=dict(count=None,rate=None,denominator=None,status='NOT_EVALUATED')
    counts=registry['counts']
    pending_empty=all(counts.get(key)==0 for key in ('qc_flag_history','ai_label','agent_task_approvals','agent_workflow_run'))
    completed_empty=all(counts.get(key)==0 for key in ('approval_history','agent_workflow_run','agent_workflow_transition'))
    catalog=rule_catalog()
    rules=dict(catalog_version=catalog['engine_version'],catalog_count=len(catalog['rules']),
        registered_definition_count=counts.get('qc_rule_definition'),result_count=0 if counts.get('qc_rule_result')==0 else None,
        registered_result_global_count=counts.get('qc_rule_result'),items=[dict(rule,status='NOT_EVALUATED',
            evaluated_count=0 if counts.get('qc_rule_result')==0 else None,
            anomaly_count=0 if counts.get('qc_rule_result')==0 else None,not_evaluated_count=None,reasons=BLOCKERS)
            for rule in catalog['rules']])
    reason='실제 담당 계정은 운영 단계에서 설정합니다. 원천·센서·QC 판본과 승인 이력이 현재 선택 자료에 연결되지 않았습니다.'
    packet=dict(schema_version=SCHEMA,source=scope['source'],snapshot=Path(view).name,
        from_month=scope['from_month'],to_month=scope['to_month'],as_of_day=scope['as_of_day'],as_of_time=scope['as_of_time'],cutoff_native=scope['cutoff_native'],
        scope={key:scope[key] for key in ('station','item','network','sea','qc_field','qc_literal','qc_literal_is_null')},
        filters=dict(stations=station_options,items=[dict(item_code=key,held_rows=value) for key,value in sorted(item_options.items())],
            networks=[dict(value=key,label='DB 기준정보 미등록' if key=='__UNREGISTERED__' else '관측망 미지정' if key=='__UNASSIGNED__' else key,count=value) for key,value in sorted(network_counts.items())],
            network_unassigned_station_codes=sorted(code for code in full_codes if len(index.get(code,[]))==1 and not index[code][0].get('network_type')),
            seas=[dict(value=key,label='해역 미지정' if key=='__UNASSIGNED__' else key,count=value) for key,value in sorted(sea_counts.items())]),
        cards=dict(held_rows=total,normal=dict(unavailable),warning=dict(unavailable),bad=dict(unavailable),
            missing=dict(count=raw['missing_value_rows'],rate=raw['missing_value_rate'],denominator=total,status='RAW_VALUE_LITERAL'),
            unassessed=dict(count=total,rate=100.0 if total else None,denominator=total,status='SOURCE_QC_UNINTERPRETED'),
            pending=dict(count=0 if pending_empty else None,status='GLOBAL_EMPTY' if pending_empty else 'UNVERIFIED_SCOPE'),
            completed=dict(count=0 if completed_empty else None,status='GLOBAL_EMPTY' if completed_empty else 'UNVERIFIED_SCOPE')),
        raw=raw,distribution=distribution,monthly=monthly,matrix=matrix,cases=cases,rules=rules,
        review=dict(status='NOT_EVALUATED',ai_prediction_count=0 if counts.get('ai_prediction_result')==0 else None,
            ai_label_count=0 if counts.get('ai_label')==0 else None,workflow_count=0 if counts.get('agent_workflow_run')==0 else None,
            approved_count=0 if counts.get('approval_history')==0 else None,source_fact_status='UNRESOLVED',reasons=BLOCKERS),
        capabilities=dict(review=False,hold=False,flag_change=False,approve=False,reason=reason,
            operator_authentication_configured=bool(settings.API_IDENTITIES)),global_registry=registry,
        provenance=dict(storage='PARQUET',clock_basis='UNAPPROVED_NATIVE_OBSERVATION_CLOCK',source_qc_interpreted=False,
            approved=False,simulated_included=False,production_writes=0,physical_scope_resolved=False,
            timezone=None,unit=None,recipe_sha256=file_hash(__file__),asof_recipe_sha256=dated.RECIPE_SHA,
            unlocatable_clock_rows_excluded=unlocatable,unlocatable_count_scope='ALL_SOURCE_FILES_IN_SELECTED_MONTHS_BEFORE_STATION_ITEM_FILTERS',
            source_files=[dict(file=Path(r['parquet_path']).name,month=asset_month(r),source_sha256=r['source_sha256'],parquet_sha256=r['parquet_sha256']) for r in files],
            note='QC 문자값 분포와 원시 빈값률입니다. 승인 정상률·BAD 비율, 실제 수신 결측률, 과거 조회 당시 가용성을 확정하지 않습니다.'))
    packet['result_sha256']=digest(packet)
    return packet


def workspace(db,source,start,end,day,clock,station='',item='',network='',sea='',qc_field='',qc_literal=None,qc_literal_is_null=False):
    scope=validate_scope(source,start,end,day,clock,station,item,network,sea,qc_field,qc_literal,qc_literal_is_null)
    with db.no_autoflush:
        registry=registry_counts(db)
        reference_month='2026-07' if scope['as_of_day'][:7]=='2026-07' else None
        metadata=reference_records(db.query(StationMetadata).all(),reference_month)
        station_scope=resolve_scope(db,network,sea,reference_month)
        view,rows,names,unlocatable=dated.selected_rows(source,start,end,scope['as_of_day'],as_of_time=scope['as_of_time'])
        selected=[r for r in rows if _scope_matches(r['station_code'],station_scope) and
            (not station or r['station_code']==station) and (not item or r['item_code']==item)]
        files=_files(view,scope)
        cases=raw_cases(files,scope,station_scope,selected)
        if lake.context()[0]!=view:raise HTTPException(409,'QC 조회 중 검증본이 변경됐습니다.')
        return build_packet(scope,view,rows,names,metadata,station_scope,registry,cases,unlocatable,files)
