"""Bounded read-only first-stage QC dashboard, with one immutable clock window.

REGISTERED means receipt-verified observations, never legacy/simulated rows.
Archive clocks and code strings remain native/uninterpreted. Missing received
values and missing scheduled transmissions are deliberately separate quantities.
"""
from collections import Counter, defaultdict
from copy import deepcopy
from datetime import datetime, time, timedelta, timezone
from functools import lru_cache
from pathlib import Path
import time as stopwatch
import duckdb

from fastapi import HTTPException
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import settings
from app.models.domain import StationMetadata, QCRuleDefinition
from app.services import lake_browser as lake, observation_asof as dated, qc_workspace as archive
from app.services.native_month_metrics import SOURCES, digest, file_hash, quote
from app.services.qc_rule_engine import catalog as rule_catalog, implementation_hashes
from app.services.station_classification import reference_records, resolve_scope, sql_scope

SCHEMA='qc-overview-1'
PRESETS=('today','yesterday','7d','30d','custom')
MAX_DAYS=31
REGISTERED_BATCH_SIZE=500
REGISTERED_TIME_BUDGET_SECONDS=40
FLAG_CODES=('1','3','4','9','NOT_EVALUATED','UNKNOWN')
COUNT_KEYS=('normal','suspect','bad','missing','unknown')
WINDOW_KEYS=('source','mode','preset','start','end','as_of','clock_basis','offset','granularity')


def server_now():
    """The backend OS local clock, carrying its real offset; no assumed KST."""
    return datetime.now().astimezone()


def _parse(value, aware):
    if not isinstance(value,str) or len(value)>40:
        raise HTTPException(422,'조회 시각 형식이 잘못됐습니다.')
    try:stamp=datetime.fromisoformat(value.replace('Z','+00:00'))
    except ValueError:raise HTTPException(422,'조회 시각 형식이 잘못됐습니다.') from None
    if (stamp.tzinfo is not None and stamp.utcoffset() is not None)!=aware:
        raise HTTPException(422,'운영 시각은 offset이 필요하며 보존 원문 시각에는 offset을 붙일 수 없습니다.')
    return stamp


def resolve_window(source='REGISTERED',preset='today',date_from=None,date_to=None,*,now=None):
    if source!='REGISTERED' and source not in SOURCES:
        raise HTTPException(422,'지원되지 않는 QC 원천입니다.')
    if preset not in PRESETS:raise HTTPException(422,'지원되지 않는 QC 조회 기간입니다.')
    actual=now if now is not None else server_now()
    if actual.tzinfo is None or actual.utcoffset() is None:
        raise HTTPException(503,'서버 운영 시계의 offset을 확인할 수 없습니다.')
    operating=source=='REGISTERED'
    if not operating and preset!='custom':
        raise HTTPException(422,'보존 원문 조회는 명시적인 원문 시작·종료 시각이 필요합니다.')
    if preset=='custom':
        if date_from is None or date_to is None:raise HTTPException(422,'사용자 지정 기간은 시작·종료 시각이 필요합니다.')
        begin=_parse(date_from,operating);end=_parse(date_to,operating)
        if operating:
            begin=begin.astimezone(actual.tzinfo);end=end.astimezone(actual.tzinfo)
            if end>actual:raise HTTPException(422,'운영 조회 종료 시각이 서버 현재시각을 초과합니다.')
    else:
        if date_from is not None or date_to is not None:raise HTTPException(422,'빠른 기간과 사용자 지정 시각을 함께 사용할 수 없습니다.')
        midnight=datetime.combine(actual.date(),time(),tzinfo=actual.tzinfo)
        if preset=='yesterday':begin=midnight-timedelta(days=1);end=midnight-timedelta(microseconds=1)
        else:begin=midnight-timedelta(days={'today':0,'7d':6,'30d':29}[preset]);end=actual
    if end<begin or end-begin>=timedelta(days=MAX_DAYS):
        raise HTTPException(422,'QC 운영 조회는 시작 이후 최대 31일 이내입니다.')
    granularity='hour' if preset in ('today','yesterday') or preset=='custom' and end-begin<timedelta(days=2) else 'day'
    offset=actual.strftime('%z') if operating else None
    if offset:offset=offset[:3]+':'+offset[3:]
    window=dict(source=source,mode='OPERATIONAL' if operating else 'ARCHIVE',preset=preset,
        start=begin.isoformat(),end=end.isoformat(),as_of=end.isoformat(),
        clock_basis='SERVER_LOCAL_OFFSET' if operating else 'UNAPPROVED_NATIVE_SOURCE_CLOCK',
        offset=offset,granularity=granularity)
    window['window_id']=digest(window)
    return window


def validate_window_identity(window):
    if not isinstance(window,dict) or set(window)!=set(WINDOW_KEYS)|{'window_id'}:
        raise HTTPException(422,'QC 조회 기간 계약이 일치하지 않습니다.')
    if digest({k:window[k] for k in WINDOW_KEYS})!=window['window_id']:
        raise HTTPException(409,'QC 조회 기간 식별자가 일치하지 않습니다.')
    source=window['source'];operating=source=='REGISTERED'
    if source not in ('REGISTERED',*SOURCES) or window['preset'] not in PRESETS:
        raise HTTPException(422,'QC 조회 원천·기간 계약이 잘못됐습니다.')
    start=_parse(window['start'],operating);end=_parse(window['end'],operating);as_of=_parse(window['as_of'],operating)
    if start>end or end-start>=timedelta(days=MAX_DAYS) or end!=as_of or window['granularity'] not in ('hour','day'):
        raise HTTPException(422,'QC 조회 기간 범위가 잘못됐습니다.')
    if window['mode']!=('OPERATIONAL' if operating else 'ARCHIVE') or window['clock_basis']!=('SERVER_LOCAL_OFFSET' if operating else 'UNAPPROVED_NATIVE_SOURCE_CLOCK'):
        raise HTTPException(422,'QC 조회 시계 계약이 잘못됐습니다.')
    if operating:
        offset=end.strftime('%z');offset=offset[:3]+':'+offset[3:]
        if window['offset']!=offset or start.utcoffset()!=end.utcoffset() or end>server_now():
            raise HTTPException(422,'QC 운영 시계 offset 또는 기준시각이 잘못됐습니다.')
    elif window['offset'] is not None or window['preset']!='custom':
        raise HTTPException(422,'보존 원문 시계 계약이 잘못됐습니다.')
    return window


def flag_catalog():
    # These are the existing engine's result flags, not source QC codebooks.
    # Colors are presentation tokens, explicitly versioned, never source facts.
    rows=(('1','정상','GOOD','#10b981'),('3','주의 / Suspect','SUSPECT','#f59e0b'),
          ('4','BAD','BAD','#ef4444'),('9','결측 판정','MISSING','#a855f7'),
          ('NOT_EVALUATED','Rule 미평가','NOT_EVALUATED','#94a3b8'),('UNKNOWN','미해석 / 미확인','UNKNOWN','#9ca3af'))
    hashes=implementation_hashes()
    return [dict(code=code,label=label,semantic=semantic,color=color,stage='RULE_QC' if code!='UNKNOWN' else 'UNINTERPRETED',
        definition_source='qc_rule_engine._evaluate/execute' if code!='UNKNOWN' else 'NO_VALID_BOUND_RULE_RESULT',
        implementation_sha256=hashes['implementation_sha256'],color_policy='QC_DISPLAY_TONES_2') for code,label,semantic,color in rows]


def context():
    now=server_now();window=resolve_window(now=now)
    packet=dict(schema_version='qc-context-1',server_now=now.isoformat(),today=str(now.date()),
        current_time=now.time().isoformat(),today_start=window['start'],clock_basis='SERVER_LOCAL_OFFSET',offset=window['offset'],
        default_source='REGISTERED',default_preset='today',presets=list(PRESETS),max_custom_days=MAX_DAYS,
        sources=[dict(value='REGISTERED',label='승인 계약에 연결된 운영 관측자료',mode='OPERATIONAL',available=True,
                      requires_explicit_window=False,clock_basis='SERVER_LOCAL_OFFSET')]+
                [dict(value=value,label=value+' · 보존 원문',mode='ARCHIVE',available=True,
                      requires_explicit_window=True,clock_basis='UNAPPROVED_NATIVE_SOURCE_CLOCK') for value in SOURCES],
        flag_catalog=flag_catalog(),default_window=window,
        capabilities=dict(operational_mock=False,raw_mutation=False,automatic_final_qc=False,production_writes=0))
    packet['result_sha256']=digest(packet)
    return packet


def _rate(count,total):return 100*count/total if total and count is not None else None
def _count_key(code):return {'1':'normal','3':'suspect','4':'bad','9':'missing'}.get(code,'unknown')
def _counts():return {k:0 for k in COUNT_KEYS}


def _buckets(window):
    begin=datetime.fromisoformat(window['start']);end=datetime.fromisoformat(window['end'])
    step=timedelta(hours=1) if window['granularity']=='hour' else timedelta(days=1)
    cursor=begin.replace(minute=0,second=0,microsecond=0) if window['granularity']=='hour' else begin.replace(hour=0,minute=0,second=0,microsecond=0)
    while cursor<=end:
        yield cursor,max(cursor,begin),min(cursor+step-timedelta(microseconds=1),end)
        cursor+=step


def _bucket(stamp,window):
    when=datetime.fromisoformat(str(stamp).replace('Z','+00:00'))
    if window['mode']=='OPERATIONAL':when=when.astimezone(datetime.fromisoformat(window['start']).tzinfo)
    return (when.replace(minute=0,second=0,microsecond=0) if window['granularity']=='hour' else when.replace(hour=0,minute=0,second=0,microsecond=0)).isoformat()


def _metrics(counts,total,partial=False,archive_mode=False,missing_literals=0):
    state='PARTIAL' if partial else 'NO_DATA' if not total else 'SOURCE_QC_UNINTERPRETED' if archive_mode else 'RULE_QC'
    result={}
    for name in ('normal','suspect','bad','missing'):
        count=missing_literals if archive_mode and name=='missing' else counts[name]
        unavailable=archive_mode and name!='missing' or partial or not total
        result[name]=dict(count=None if unavailable else count,rate=None if unavailable else _rate(count,total),
            denominator=total,stage='RAW_VALUE_LITERAL' if archive_mode and name=='missing' else 'RULE_QC',state=state,
            denominator_basis='ELIGIBLE_RECEIVED_ROWS_NOT_EXPECTED_TRANSMISSIONS')
    return result


def _rules(db,results,registry):
    catalog=rule_catalog();definitions=[]
    with db.no_autoflush:
        if registry['counts'].get('qc_rule_definition') is not None:
            definitions=[dict(rule_id=r.qc_rule_id,rule_name=r.qc_rule_name,rule_version=r.rule_version,
                              active=r.active,rule_type=r.qc_rule_group) for r in db.query(QCRuleDefinition).limit(251).all()]
    grouped=defaultdict(list)
    for row in results:grouped[row.get('rule_type') or row.get('rule_kind')].append(row)
    anomalies=sum(r.get('result_flag') in ('3','4','9') for r in results)
    rows=[]
    for rule in catalog['rules']:
        selected=grouped.get(rule['kind'],[])
        evaluated=sum(r.get('evaluation_status') in ('EVALUATED','MISSING') for r in selected)
        bad=sum(r.get('result_flag') in ('3','4','9') for r in selected)
        rows.append(dict(rule_id=rule['kind'],rule_name=rule['name_ko'],rule_type=rule['kind'],rule_version=catalog['engine_version'],
            evaluated_count=evaluated,anomaly_count=bad,share=_rate(bad,anomalies),
            state='EVALUATED' if evaluated else 'NOT_EVALUATED',not_evaluated_count=len(selected)-evaluated,
            definition_basis='ENGINE_CATALOG',requires_explicit_source_configuration=rule.get('requires_explicit_source_configuration',True)))
    return dict(catalog_version=catalog['engine_version'],registered_definition_count=registry['counts'].get('qc_rule_definition'),
        registered_definitions=definitions[:250],definitions_truncated=len(definitions)>250,items=rows,
        result_count=len(results),unmapped_result_count=sum(len(v) for key,v in grouped.items() if key not in {r['kind'] for r in catalog['rules']}))


def _ledger_cards(registry):
    counts=registry['counts']
    return {key:dict(count=0 if all(counts.get(t)==0 for t in tables) else None,rate=None,denominator=None,stage='REVIEW_WORKFLOW',
        state='GLOBAL_EMPTY' if all(counts.get(t)==0 for t in tables) else 'UNVERIFIED_SCOPE',
        scope='GLOBAL_LEDGER_EMPTY_PROVES_SELECTED_SCOPE_EMPTY_ONLY') for key,tables in (
        ('pending',('qc_flag_history','ai_label','agent_task_approvals','agent_workflow_run')),
        ('completed',('approval_history','agent_workflow_run','agent_workflow_transition')))}


def _references(db,window):
    month='2026-07' if window['mode']=='ARCHIVE' and window['end'][:7]=='2026-07' else None
    metadata=reference_records(db.query(StationMetadata).limit(10001).all(),month)
    if len(metadata)>10000:raise HTTPException(503,'관측소 기준정보 조회 한도를 초과했습니다.')
    return metadata,month


def _filters(metadata,groups):
    names={r['station_id']:r.get('reference_name') or r.get('station_name') or r['station_id'] for r in metadata}
    codes={r['station_id'] for r in groups}
    return dict(stations=[dict(station_id=code,station_name=names.get(code,code)) for code in sorted(codes)],
        variables=[dict(variable_code=code,label=code) for code in sorted({r['variable_code'] for r in groups})],
        networks=[dict(value=v,label=v) for v in sorted({r['network_type'] for r in metadata if r.get('network_type')})]+[dict(value='__UNREGISTERED__',label='DB 기준정보 미등록')],
        seas=[dict(value=v,label=v) for v in sorted({r['sea_area'] for r in metadata if r.get('sea_area')})]+[dict(value='__UNASSIGNED__',label='해역 미지정')])


def _packet(window,scope,metadata,registry,groups,trend,distribution,queue,rules,*,snapshot,
            samples=None,partial=False,exclusions=None,total=None,missing_literals=0,provenance=None):
    total=sum(r['total'] for r in groups) if total is None else total
    counts=_counts()
    for row in distribution:counts[_count_key(row['code'])]+=row['count']
    archive_mode=window['mode']=='ARCHIVE';catalog=flag_catalog();catalog_by={r['code']:r for r in catalog}
    flag_rows=[dict(code=r['code'],label=catalog_by[r['code']]['label'],semantic=catalog_by[r['code']]['semantic'],color=catalog_by[r['code']]['color'],
        count=r['count'],rate=None if partial else _rate(r['count'],total),denominator=total,stage=catalog_by[r['code']]['stage']) for r in distribution]
    indexed={r['bucket']:r for r in trend};trend_rows=[]
    for bucket,start,end in _buckets(window):
        row=indexed.get(bucket.isoformat(),dict(total=0,counts=_counts()))
        trend_rows.append(dict(bucket=bucket.isoformat(),start=start.isoformat(),end=end.isoformat(),total=row['total'],counts=row['counts'],
            rates={key:None if partial else _rate(value,row['total']) for key,value in row['counts'].items()},
            state='PARTIAL' if partial else 'DATA' if row['total'] else 'NO_DATA'))
    summary=_metrics(counts,total,partial,archive_mode,missing_literals);summary.update(_ledger_cards(registry))
    names={r['station_id']:r.get('reference_name') or r.get('station_name') or r['station_id'] for r in metadata}
    matrix=[]
    for row in groups:
        state='UNKNOWN' if archive_mode else 'BAD' if row['counts']['bad'] else 'SUSPECT' if row['counts']['suspect'] else 'MISSING' if row['counts']['missing'] else 'UNKNOWN' if row['counts']['unknown'] else 'GOOD'
        matrix.append(dict(row,station_name=names.get(row['station_id'],row['station_id']),state='PARTIAL' if partial else state,
            rates={k:None if partial else _rate(v,row['total']) for k,v in row['counts'].items()}))
    packet=dict(schema_version=SCHEMA,source=window['source'],snapshot=snapshot,window=window,scope=scope,
        total_observations=total,summary=summary,flag_catalog=catalog,flag_distribution=flag_rows,
        quality_trend=trend_rows,rule_qc_counts=rules,station_variable_matrix=matrix,review_queue=queue,
        archive_samples=samples,filters=_filters(metadata,groups),
        states=dict(overall='PARTIAL' if partial else 'NO_DATA' if not total else 'READY',
            ai='NOT_RUN' if registry['counts'].get('ai_prediction_result')==0 else 'UNVERIFIED_SCOPE',
            model='NO_MODEL' if registry['counts'].get('model_registry')==0 else 'UNVERIFIED_SCOPE',
            evidence='NO_EVIDENCE' if all(registry['counts'].get(t)==0 for t in ('operation_log','daily_inspection_report','quality_collection_report','event_registry')) else 'UNVERIFIED_SCOPE',
            source_contract='UNRESOLVED' if archive_mode else 'RECEIPT_VERIFIED_ONLY',review='PARTIAL' if partial else 'NO_CASES' if queue['total']==0 else 'AVAILABLE'),
        capabilities=dict(review=False,hold=False,flag_change=False,approve=False,run_ai=False,
            operator_authentication_configured=bool(settings.API_IDENTITIES),
            reason='실제 담당 계정은 운영 단계에서 설정합니다. 이 집계는 읽기 전용이며 기존 승인 Workflow의 실제 식별자가 있는 상세에서만 처리합니다.'),
        provenance=dict(storage='PARQUET' if archive_mode else 'POSTGRESQL',clock_basis=window['clock_basis'],
            approved=False,final_qc=False,source_qc_interpreted=False,simulated_included=False,production_writes=0,
            raw_mutation=False,imputation_applied=False,expected_transmission_denominator=None,
            historical_availability_asserted=not archive_mode,recipe_sha256=file_hash(__file__),
            excluded_counts=exclusions or {},**(provenance or {})))
    packet['result_sha256']=digest(packet)
    return packet


def aggregate_registered(rows,results,window,scope,*,limit=30,offset=0):
    """Aggregate only the peer reader's verified DTOs, not ORM raw flags."""
    grouped_results=defaultdict(list)
    for result in results:grouped_results[result['observation_id']].append(result)
    groups=defaultdict(lambda:dict(total=0,counts=_counts(),top_rule=None,recent_issue_time=None))
    trends=defaultdict(lambda:dict(total=0,counts=_counts()));flags=Counter();candidates=[];selected_results=[]
    severity={'4':4,'3':3,'9':2,'1':1,'NOT_EVALUATED':0,'UNKNOWN':-1}
    for row in rows:
        valid=[r for r in grouped_results.get(row['observation_id'],[]) if r.get('result_flag') in FLAG_CODES]
        valid.sort(key=lambda r:(severity[r['result_flag']],r.get('executed_at_utc') or '',r.get('qc_result_id') or ''),reverse=True)
        code=valid[0]['result_flag'] if valid else 'UNKNOWN'
        if scope['flag'] and code!=scope['flag']:continue
        selected_results.extend(valid);key=_count_key(code);flags[code]+=1
        group=groups[(row['station_id'],row['variable_code'])];group['total']+=1;group['counts'][key]+=1
        bucket=_bucket(row['observation_time'],window);trends[bucket]['total']+=1;trends[bucket]['counts'][key]+=1
        if code in ('3','4','9'):
            rule=valid[0];group['recent_issue_time']=max(group['recent_issue_time'] or '',row['observation_time'])
            candidates.append(dict(id='qc:'+rule['qc_result_id'],kind='REGISTERED_QC_CANDIDATE',observation_id=row['observation_id'],
                station_id=row['station_id'],variable_code=row['variable_code'],sensor_id=row['sensor_id'],physical_sensor_id=row['physical_sensor_id'],
                observation_time=row['observation_time'],received_time=row.get('received_time'),available_at=row['available_at'],
                value=row['value'],unit=row['unit'],flag=code,rule_id=rule.get('rule_id') or rule.get('qc_rule_id'),
                rule_name=rule.get('rule_name') or rule.get('qc_rule_name'),severity=code,review_status='UNVERIFIED',
                ai_score=None,authority_sha256=row['authority_sha256'],source_group=row['source_group']))
    rulecounts=defaultdict(Counter);observations={r['observation_id']:r for r in rows}
    for r in selected_results:
        if r.get('result_flag') in ('3','4','9'):
            obs=observations.get(r['observation_id'])
            if obs:rulecounts[(obs['station_id'],obs['variable_code'])][r.get('rule_id') or r.get('qc_rule_id')]+=1
    for key,count in rulecounts.items():groups[key]['top_rule']=count.most_common(1)[0][0]
    candidates.sort(key=lambda r:(severity[r['flag']],r['observation_time'],r['id']),reverse=True)
    return dict(groups=[dict(station_id=s,variable_code=v,**g) for (s,v),g in sorted(groups.items())],
        trend=[dict(bucket=b,**r) for b,r in sorted(trends.items())],
        distribution=[dict(code=code,count=flags[code]) for code in FLAG_CODES],results=selected_results,
        queue=dict(rows=candidates[offset:offset+limit],total=len(candidates),limit=limit,offset=offset,state='NO_CASES' if not candidates else 'AVAILABLE'))


class RegisteredAccumulator:
    """Request-local totals and bounded queue; no full-period minute collection."""
    def __init__(self,window,scope,limit,offset):
        self.window=window;self.scope=scope;self.limit=limit;self.offset=offset
        self.groups={};self.trend={};self.flags=Counter();self.rules=defaultdict(Counter)
        self.queue=[];self.queue_total=0;self.rule_total=0;self.verified=0;self.selected=0
        self.authority_chain=digest([])

    @staticmethod
    def priority(row):
        return ({'4':0,'3':1,'9':2,'1':3,'NOT_EVALUATED':4,'UNKNOWN':5}[row['flag']],
                -datetime.fromisoformat(row['observation_time'].replace('Z','+00:00')).timestamp(),row['id'])

    def add(self,rows,rule_batches):
        self.verified+=len(rows);by_id={r['observation_id']:r for r in rows}
        best={};per_observation=defaultdict(lambda:defaultdict(Counter));rulecounts=defaultdict(Counter)
        excluded=Counter();scanned_rules=0;selected_rows=[]
        for batch in rule_batches:
            excluded.update({'rule:'+k:v for k,v in batch.get('excluded_counts',{}).items()})
            scanned_rules+=batch.get('scanned_count',len(batch['rows']))
            if batch.get('truncated'):excluded['RULE_SCAN_TRUNCATED']+=1
            for result in batch['rows']:
                obs=result['observation_id'];code=result.get('result_flag',result.get('flag'))
                if obs not in by_id or code not in FLAG_CODES:
                    excluded['RULE_READER_CONTRACT_MISMATCH']+=1;continue
                r=dict(result,flag=code,id='qc:'+result['qc_result_id'],observation_time=by_id[obs]['observation_time'])
                prior=best.get(obs)
                if prior is None or self.priority(r)<self.priority(prior):best[obs]=r
                kind=result.get('rule_type') or result.get('rule_kind')
                per_observation[obs][kind]['total']+=1
                if result.get('evaluation_status') in ('EVALUATED','MISSING'):per_observation[obs][kind]['evaluated']+=1
                if code in ('3','4','9'):
                    per_observation[obs][kind]['anomaly']+=1;rulecounts[obs][result.get('rule_id')]+=1
        for row in rows:
            representative=best.get(row['observation_id']);code=representative['flag'] if representative else 'UNKNOWN'
            self.authority_chain=digest([self.authority_chain,row['authority_sha256']])
            if self.scope['flag'] and code!=self.scope['flag']:continue
            selected_rows.append(row)
            self.selected+=1;countkey=_count_key(code);self.flags[code]+=1
            groupkey=(row['station_id'],row['variable_code'])
            group=self.groups.setdefault(groupkey,dict(total=0,counts=_counts(),rules=Counter(),recent_issue_time=None))
            group['total']+=1;group['counts'][countkey]+=1;group['rules'].update(rulecounts[row['observation_id']])
            bucket=_bucket(row['observation_time'],self.window);trend=self.trend.setdefault(bucket,dict(total=0,counts=_counts()))
            trend['total']+=1;trend['counts'][countkey]+=1
            for kind,counts in per_observation[row['observation_id']].items():
                self.rules[kind].update(counts);self.rule_total+=counts['total']
            if code not in ('3','4','9'):continue
            current=group['recent_issue_time']
            if current is None or datetime.fromisoformat(row['observation_time'])>datetime.fromisoformat(current):group['recent_issue_time']=row['observation_time']
            self.queue_total+=1
            self.queue.append(dict(id=representative['id'],kind='REGISTERED_QC_CANDIDATE',observation_id=row['observation_id'],
                station_id=row['station_id'],variable_code=row['variable_code'],sensor_id=row['sensor_id'],physical_sensor_id=row['physical_sensor_id'],
                observation_time=row['observation_time'],received_time=row.get('received_time'),available_at=row['available_at'],
                value=row['value'],unit=row['unit'],flag=code,rule_id=representative.get('rule_id'),rule_name=representative.get('rule_name'),
                severity=code,review_status=representative.get('review_status','UNVERIFIED'),ai_score=None,
                authority_sha256=row['authority_sha256'],source_group=row['source_group'],delay_minutes=row.get('delay_minutes'),delay_flag=row.get('delay_flag')))
        self.queue.sort(key=self.priority);del self.queue[self.offset+self.limit:]
        return dict(excluded),scanned_rules,selected_rows

    def grouped(self):
        groups=[]
        for (station,item),raw in sorted(self.groups.items()):
            rows=dict(raw);rules=rows.pop('rules')
            groups.append(dict(station_id=station,variable_code=item,top_rule=rules.most_common(1)[0][0] if rules else None,**rows))
        return dict(groups=groups,trend=[dict(bucket=b,**r) for b,r in sorted(self.trend.items())],
            distribution=[dict(code=code,count=self.flags[code]) for code in FLAG_CODES])


def bind_queue_reviews(queue,observations,reviews):
    """Attach only same-observation verified review states to this bounded batch.

    Exclusions from the actual reader are exact observation IDs, so one
    uncertain workflow never contaminates another observation's queue state.
    An old/test reader lacking this attribution retains a conservative fallback.
    """
    ids={r['observation_id'] for r in observations};by_id=defaultdict(list)
    excluded=Counter(reviews.get('excluded_counts',{}))
    per_observation=reviews.get('excluded_by_observation')
    attributed=isinstance(per_observation,dict) and set(per_observation)<=ids
    if per_observation is not None and not attributed:
        excluded['WORKFLOW_EXCLUSION_SCOPE_MISMATCH']+=1
    statuses={'PENDING','APPROVED','REJECTED','CANCELLED','RESUMING','COMPLETED'}
    for review in reviews['rows']:
        if review.get('observation_id') not in ids or review.get('status') not in statuses or not isinstance(review.get('workflow_id'),str) or not review['workflow_id']:
            excluded['WORKFLOW_READER_SCOPE_OR_STATUS_MISMATCH']+=1;attributed=False;continue
        by_id[review['observation_id']].append(review)
    verified=[]
    for oid,rows in by_id.items():
        if len(rows)!=1:excluded['AMBIGUOUS_CANDIDATE_WORKFLOWS']+=1
        elif not (per_observation.get(oid) if attributed else excluded):verified.append(rows[0])
    for row in queue:
        oid=row['observation_id']
        if oid not in ids:continue
        matches=by_id.get(oid,[]);match=matches[0] if len(matches)==1 else None
        relevant=Counter(per_observation.get(oid,{}) if attributed else excluded)
        row.update(review_workflow_id=None,review_workflow_revision=None,review_available_at=None,
            review_recommendation_sha256=None,review_definitive_qc=False)
        if relevant:
            row.update(review_status='AMBIGUOUS' if 'AMBIGUOUS_CANDIDATE_WORKFLOWS' in relevant else 'UNVERIFIED',
                review_evidence_status='UNVERIFIED',review_reasons=sorted(relevant),
                review_reason_scope='EXACT_OBSERVATION' if attributed else 'BATCH_EXCLUSIONS_WITHOUT_OBSERVATION_ATTRIBUTION')
        elif match:
            row.update(review_status=match['status'],review_evidence_status='VERIFIED_LINKED_WORKFLOW',review_reasons=[],
                review_workflow_id=match['workflow_id'],review_workflow_revision=match.get('revision'),
                review_available_at=match.get('available_at'),review_recommendation_sha256=match.get('recommendation_sha256'))
        elif len(matches)>1:
            row.update(review_status='AMBIGUOUS',review_evidence_status='UNVERIFIED',review_reasons=['AMBIGUOUS_CANDIDATE_WORKFLOWS'])
        else:row.update(review_status='NO_LINKED_WORKFLOW',review_evidence_status='NO_LINKED_WORKFLOW',review_reasons=[])
    return verified,dict(excluded)


def _registered(db,window,scope,metadata,registry,limit,offset):
    from app.services.qc_candidate_review import (iter_registered_batches,iter_registered_rule_batches,
        verify_cached_authority,verify_definition_cache,registered_review_states,verify_workflow_cache)
    station_scope=resolve_scope(db,scope['network'],scope['sea']);receipt_cache={};definition_cache={};workflow_cache={}
    accumulator=RegisteredAccumulator(window,scope,limit,offset)
    exclusions=Counter();selected_count=None;scanned=0;scanned_rules=0;expired=False;started=stopwatch.monotonic();workflow_states={}
    for batch in iter_registered_batches(db,window,scope['station_id'],scope['variable_code'],
            batch_size=REGISTERED_BATCH_SIZE,receipt_cache=receipt_cache,station_scope=station_scope):
        if batch.get('missing_tables'):raise HTTPException(503,'QC 승인 원천 원장이 준비되지 않았습니다.')
        selected_count=batch['selected_count'];scanned+=batch['scanned_count'];exclusions.update(batch.get('excluded_counts',{}))
        rows=[r for r in batch['rows'] if archive._scope_matches(r['station_id'],station_scope)]
        rules=iter_registered_rule_batches(db,rows,window,batch_size=REGISTERED_BATCH_SIZE,definition_cache=definition_cache)
        excluded,rules_scanned,selected_rows=accumulator.add(rows,rules);exclusions.update(excluded);scanned_rules+=rules_scanned
        if registry['counts']['agent_workflow_run']:
            reviews=registered_review_states(db,selected_rows,window,workflow_cache=workflow_cache)
        else:reviews=dict(rows=[],excluded_counts={})
        verified_reviews,review_excluded=bind_queue_reviews(accumulator.queue,selected_rows,reviews)
        exclusions.update({'workflow:'+k:v for k,v in review_excluded.items()})
        if registry['counts']['agent_workflow_run']:
            for review in verified_reviews:
                existing=workflow_states.get(review['workflow_id'])
                if existing is not None and existing!=review['status']:exclusions['WORKFLOW_STATUS_CHANGED_DURING_QUERY']+=1
                workflow_states[review['workflow_id']]=review['status']
        if stopwatch.monotonic()-started>REGISTERED_TIME_BUDGET_SECONDS:
            expired=True;exclusions['REQUEST_TIME_BUDGET_EXCEEDED']+=1;break
    if selected_count is None:selected_count=0
    if scanned!=selected_count:exclusions['SOURCE_POPULATION_CHANGED_OR_NOT_FULLY_SCANNED']+=abs(selected_count-scanned) or 1
    verify_cached_authority(db,receipt_cache);verify_definition_cache(db,definition_cache);verify_workflow_cache(db,workflow_cache)
    partial=bool(exclusions or expired)
    grouped=accumulator.grouped();rules=_rules(db,[],registry)
    anomaly_total=sum(r['anomaly'] for r in accumulator.rules.values())
    for rule in rules['items']:
        counts=accumulator.rules.get(rule['rule_type'],Counter())
        rule.update(evaluated_count=counts['evaluated'],anomaly_count=counts['anomaly'],not_evaluated_count=counts['total']-counts['evaluated'],
                    share=None if partial else _rate(counts['anomaly'],anomaly_total),state='PARTIAL' if partial else 'EVALUATED' if counts['evaluated'] else 'NOT_EVALUATED')
    rules.update(result_count=accumulator.rule_total,unmapped_result_count=sum(v['total'] for k,v in accumulator.rules.items() if k not in {r['rule_type'] for r in rules['items']}))
    queue=dict(rows=accumulator.queue[offset:offset+limit],total=None if partial else accumulator.queue_total,validated_subset_total=accumulator.queue_total,
               limit=limit,offset=offset,state='PARTIAL' if partial else 'NO_CASES' if not accumulator.queue_total else 'AVAILABLE')
    packet=_packet(window,scope,metadata,registry,grouped['groups'],grouped['trend'],grouped['distribution'],queue,rules,
        snapshot='REGISTERED_RECEIPTS:'+accumulator.authority_chain,partial=partial,exclusions=dict(exclusions),
        provenance=dict(aggregation='KEYSET_BATCH_VERIFIED_FULL_WINDOW_SERVER_AGGREGATES',batch_size=REGISTERED_BATCH_SIZE,
            time_budget_seconds=REGISTERED_TIME_BUDGET_SECONDS,time_budget_exceeded=expired,selected_registered_candidates=selected_count,
            scanned_registered_candidates=scanned,validated_observations=accumulator.verified,selected_verified_observations=accumulator.selected,
            scanned_rule_results=scanned_rules,validated_rule_results=accumulator.rule_total,
            unknown_observations=accumulator.flags['UNKNOWN']+accumulator.flags['NOT_EVALUATED'],
            complete_population_aggregation=not partial,receipt_cache_scope='REQUEST_LOCAL',
            snapshot_consistency='READ_TRANSACTION_COUNT_AND_KEYSET_POPULATION_CHECK'))
    if registry['counts']['agent_workflow_run']:
        for key,status in (('pending','PENDING'),('completed','COMPLETED')):
            count=sum(value==status for value in workflow_states.values());total=len(workflow_states)
            packet['summary'][key]=dict(count=None if partial else count,rate=None if partial else _rate(count,total),denominator=total,
                state='PARTIAL' if partial else 'VERIFIED_LINKED_WORKFLOWS' if total else 'NO_LINKED_WORKFLOWS',
                stage='RECOMMENDATION_WORKFLOW',definitive_qc=False,
                completed_means='RECOMMENDATION_WORKFLOW_COMPLETED_NOT_FINAL_QC',denominator_basis='DISTINCT_EXACT_LINKED_WORKFLOW_IDS')
    packet['provenance']['linked_workflow_count']=len(workflow_states)
    packet['provenance']['snapshot_kind']='VERIFIED_OBSERVATION_CENSUS_FINGERPRINT_NOT_DATASET'
    packet.pop('result_sha256',None);packet['result_sha256']=digest(packet)
    return packet


@lru_cache(maxsize=8)
def _archive_query(source,start,end,granularity,station,item,scope_json,files_json):
    """SQL projection/aggregation; never materialize the full minute population."""
    import json
    files=json.loads(files_json);station_scope=json.loads(scope_json)
    if not files:return dict(groups=[],trend=[],distribution=[dict(code='UNKNOWN',count=0)],samples=[],missing_literals=0,raw_distribution=[],invalid_clock_rows=0)
    with lake.connection() as c:
        c.execute('SET preserve_insertion_order=false')
        c.read_parquet([f['parquet_path'] for f in files],hive_partitioning=False,filename=True,file_row_number=True,union_by_name=True).create_view('raw_files')
        cols={r[0] for r in c.execute('DESCRIBE raw_files').fetchall()}
        def col(name):return quote(name) if name in cols else 'NULL::VARCHAR'
        if source=='GD_OBS_ST_MONTHLY':
            projection='trim(station_raw) station_code,trim(item_raw) item_code,time_raw observed_time_raw,value_raw,qc_raw source_qc_raw,mq_raw source_mq_raw,n1_aqc_raw source_n1_qc_raw,NULL::VARCHAR depth_step,NULL::VARCHAR depth_from,NULL::VARCHAR depth_to'
            predicate=" WHERE record_class='OBSERVATION_SHAPED_UNVALIDATED'"
            qc_fields=[alias for original,alias in (('qc_raw','source_qc_raw'),('mq_raw','source_mq_raw'),('n1_aqc_raw','source_n1_qc_raw')) if original in cols]
        else:
            if 'FROM_DEPTH' in cols and 'FR_DEPTH' in cols:raise HTTPException(409,'원천 수심 별칭 충돌')
            projection='trim(OBS_POST_ID) station_code,trim(OBS_ITEM_CODE) item_code,OBS_TIME observed_time_raw,OBS_VALUE value_raw,'+','.join(col(k)+' '+alias for k,alias in (
                ('QC_FLAG','source_qc_raw'),('MQC_FLAG','source_mq_raw'),('N1_AQC_FLAG','source_n1_qc_raw'),('WATER_STEP','depth_step'),
                ('FROM_DEPTH' if 'FROM_DEPTH' in cols else 'FR_DEPTH','depth_from'),('TO_DEPTH','depth_to')))
            predicate=''
            qc_fields=[alias for original,alias in (('QC_FLAG','source_qc_raw'),('MQC_FLAG','source_mq_raw'),('N1_AQC_FLAG','source_n1_qc_raw')) if original in cols]
        c.execute('CREATE VIEW normalized AS SELECT '+projection+',filename,file_row_number FROM raw_files'+predicate)
        extra,args=sql_scope(station_scope)
        filters=''
        for field,value in (('station_code',station),('item_code',item)):
            if value:filters+=' AND '+field+'=?';args.append(value)
        where='native_clock>=?::TIMESTAMP AND native_clock<=?::TIMESTAMP'+extra+filters
        values=[start,end]+args
        # Lazy view plus SQL aggregates avoids materializing millions of minute
        # rows in Python, a temporary table, or the browser.
        pattern=dated.NATIVE_PATTERN.replace("'","''")
        c.execute("CREATE VIEW selected AS SELECT *,CASE WHEN regexp_full_match(CAST(observed_time_raw AS VARCHAR),'"+pattern+"') THEN try_cast(observed_time_raw AS TIMESTAMP) END native_clock FROM normalized")
        # A single GROUPING SETS pass computes every full-population aggregate.
        # Three independent QC fields are grouped directly, avoiding the large
        # correlated LATERAL join and any replication of the minute population.
        aggregation="""SELECT station_code,item_code,date_trunc('"""+granularity+"""',native_clock) bucket,
          source_qc_raw,source_mq_raw,source_n1_qc_raw,
          grouping_id(station_code,item_code,bucket,source_qc_raw,source_mq_raw,source_n1_qc_raw) grain,
          count(*) n,count(*) FILTER(WHERE value_raw IS NULL OR trim(value_raw)='') missing
          FROM selected WHERE """+where+""" GROUP BY GROUPING SETS
          ((station_code,item_code),(bucket),(source_qc_raw),(source_mq_raw),(source_n1_qc_raw),())"""
        aggregates=lake.records(c.execute(aggregation,values))
        group_rows=[dict(station_code=r['station_code'],item_code=r['item_code'],total=r['n'],missing_literals=r['missing']) for r in aggregates if r['grain']==15 and r['n']]
        group_rows.sort(key=lambda r:(r['station_code'],r['item_code']))
        trend=[dict(bucket=r['bucket'],total=r['n']) for r in aggregates if r['grain']==55 and r['n']]
        trend.sort(key=lambda r:r['bucket'])
        qc_masks={59:'source_qc_raw',61:'source_mq_raw',62:'source_n1_qc_raw'}
        raw_distribution=[dict(field=qc_masks[r['grain']],literal=r[qc_masks[r['grain']]],count=r['n']) for r in aggregates if r['grain'] in qc_masks and qc_masks[r['grain']] in qc_fields and r['n']]
        raw_distribution.sort(key=lambda r:(r['field'],r['literal'] is not None,r['literal'] or ''))
        samples=lake.records(c.execute('SELECT * EXCLUDE(native_clock) FROM selected WHERE '+where+' ORDER BY native_clock DESC,filename DESC,file_row_number DESC LIMIT 15',values))
        invalid=c.execute('SELECT count(*) FROM selected WHERE native_clock IS NULL'+extra+filters,args).fetchone()[0]
    lookup={str(Path(f['parquet_path']).resolve()):f for f in files}
    for r in samples:
        asset=lookup[str(Path(r.pop('filename')).resolve())]
        r.update(file=Path(asset['parquet_path']).name,source_group=source,source_sha256=asset['source_sha256'],parquet_sha256=asset['parquet_sha256'],
            physical_sensor_id=None,unit=None,timezone=None,classification='UNINTERPRETED',available_at=None,approved=False,historical_availability_asserted=False)
        r['case_key']=digest(dict(parquet_sha256=r['parquet_sha256'],file_row_number=r['file_row_number']))
        r['id']='archive:'+r['parquet_sha256']+':'+str(r['file_row_number']);r['kind']='ARCHIVE_RAW_SAMPLE'
    total=sum(r['total'] for r in group_rows)
    return dict(groups=[dict(station_id=r['station_code'],variable_code=r['item_code'],total=r['total'],counts={**_counts(),'unknown':r['total']},
                            top_rule=None,recent_issue_time=None,raw_missing_literals=r['missing_literals']) for r in group_rows],
        trend=[dict(bucket=r['bucket'].isoformat(),total=r['total'],counts={**_counts(),'unknown':r['total']}) for r in trend],
        distribution=[dict(code=code,count=total if code=='UNKNOWN' else 0) for code in FLAG_CODES],samples=samples,
        missing_literals=sum(r['missing_literals'] for r in group_rows),raw_distribution=raw_distribution[:2000],
        raw_distribution_truncated=len(raw_distribution)>2000,invalid_clock_rows=invalid)


def _positive_catalog_scope(view,window,station_scope,authority_sha,catalog_sha):
    """Narrow a positive DB scope only through the complete, frozen census.

    The validation proof accounts for observation-shaped rows before clock
    parsing, so invalid clocks and raw/unregistered codes remain in its census.
    Never use an unbound or incomplete catalog to discard a DB station code.
    """
    import json
    verification=view/'verification.json'
    try:
        proof_bytes=verification.read_bytes()
        proof=json.loads(proof_bytes)
    except (OSError,ValueError):
        raise HTTPException(409,dict(code='QC_POSITIVE_SCOPE_CATALOG_UNVERIFIED',mutation_performed=False)) from None
    checks=proof.get('checks') if isinstance(proof,dict) else None
    hashes=proof.get('artifact_sha256') if isinstance(proof,dict) else None
    required={'observation_accounting','one_row_per_source_station_item_depth_month','parquet_reread'}
    passed={row.get('check') for row in checks if isinstance(row,dict) and row.get('passed') is True} if isinstance(checks,list) else set()
    if (not required<=passed or not isinstance(hashes,dict)
            or hashes.get('station-item-month-validation.parquet')!=catalog_sha
            or hashes.get('file-only-timeseries.duckdb')!=authority_sha):
        raise HTTPException(409,dict(code='QC_POSITIVE_SCOPE_CATALOG_UNVERIFIED',mutation_performed=False))
    import hashlib
    verification_sha=hashlib.sha256(proof_bytes).hexdigest()
    with lake.connection() as c:
        c.read_parquet(str(view/'station-item-month-validation.parquet')).create_view('catalog')
        codes={r[0] for r in c.execute('SELECT DISTINCT station_code FROM catalog WHERE source_group=? AND CAST(month AS VARCHAR)>=? AND CAST(month AS VARCHAR)<=?',
            [window['source'],window['start'][:7]+'-01',window['end'][:7]+'-31']).fetchall()}
    return {'include':sorted(set(station_scope['include'])&codes)},verification_sha


def _archive(db,window,scope,metadata,registry,limit,offset):
    import json
    view,catalog_path=lake.context();authority_path=view/'file-only-timeseries.duckdb'
    authority_sha=file_hash(authority_path);catalog_sha=file_hash(catalog_path)
    month=window['end'][:7] if window['end'][:7]=='2026-07' else None
    station_scope=resolve_scope(db,scope['network'],scope['sea'],month)
    files=archive._files(view,dict(source=window['source'],from_month=window['start'][:7],to_month=window['end'][:7]))
    # Make an unregistered filter a small positive source-code set, rather than
    # a large NOT IN registry predicate over every minute row.
    verification_sha=None
    if station_scope is not None and 'include' in station_scope:
        station_scope,verification_sha=_positive_catalog_scope(view,window,station_scope,authority_sha,catalog_sha)
    elif station_scope is not None and 'exclude' in station_scope:
        with lake.connection() as c:
            c.read_parquet(str(view/'station-item-month-validation.parquet')).create_view('catalog')
            codes=[r[0] for r in c.execute('SELECT DISTINCT station_code FROM catalog WHERE source_group=? AND CAST(month AS VARCHAR)>=? AND CAST(month AS VARCHAR)<=?',
                [window['source'],window['start'][:7]+'-01',window['end'][:7]+'-31']).fetchall()]
        station_scope={'include':sorted(set(codes)-set(station_scope['exclude']))}
    minimal=[{k:r[k] for k in ('parquet_path','source_sha256','parquet_sha256','mtime_ns','bytes')} for r in files]
    calculated=deepcopy(_archive_query(window['source'],window['start'],window['end'],window['granularity'],scope['station_id'],scope['variable_code'],
        json.dumps(station_scope,sort_keys=True,ensure_ascii=False),json.dumps(minimal,sort_keys=True,ensure_ascii=False)))
    if scope['flag'] and scope['flag']!='UNKNOWN':
        calculated.update(groups=[],trend=[],distribution=[dict(code=code,count=0) for code in FLAG_CODES],samples=[],missing_literals=0,raw_distribution=[])
    # Recheck authority after aggregation and on every warm-cache request.
    for row in files:
        p=Path(row['parquet_path']);stat=p.stat();lake.verify_file(str(p),stat.st_mtime_ns,stat.st_size,row['parquet_sha256'])
    if lake.context()[0]!=view:raise HTTPException(409,'QC 조회 중 검증본이 변경됐습니다.')
    if file_hash(authority_path)!=authority_sha or file_hash(catalog_path)!=catalog_sha:
        raise HTTPException(409,'QC 조회 중 원천 파일 목록·카탈로그가 변경됐습니다.')
    if verification_sha is not None and file_hash(view/'verification.json')!=verification_sha:
        raise HTTPException(409,dict(code='QC_POSITIVE_SCOPE_CATALOG_CHANGED',mutation_performed=False))
    total=sum(r['total'] for r in calculated['groups'])
    packet=_packet(window,scope,metadata,registry,calculated['groups'],calculated['trend'],calculated['distribution'],
        dict(rows=[],total=0,limit=limit,offset=offset,state='NO_BOUND_RULE_CANDIDATES'),_rules(db,[],registry),snapshot=view.name,
        samples=dict(rows=calculated['samples'],total_matching_rows=total,limit=15,state='NO_DATA' if not total else 'RAW_SAMPLES',population='RAW_SOURCE_ROWS_NOT_ANOMALY_RESULTS'),
        missing_literals=calculated['missing_literals'],
        provenance=dict(aggregation='DUCKDB_HOURLY_OR_DAILY_SERVER_AGGREGATES',source_files=[dict(file=Path(f['parquet_path']).name,source_sha256=f['source_sha256'],parquet_sha256=f['parquet_sha256']) for f in files],
            invalid_clock_rows_excluded=calculated['invalid_clock_rows'],invalid_clock_count_scope='SELECTED_SOURCE_MONTH_FILES_AND_STATION_FILTER_BEFORE_PERIOD_FILTER',
            raw_distribution_truncated=calculated.get('raw_distribution_truncated',False),
            physical_scope_resolved=False,timezone=None,unit=None,archive_qc_literal_distribution=calculated['raw_distribution']))
    packet['provenance'].update(source_assets_sha256=authority_sha,catalog_sha256=catalog_sha,source_csv_current_preservation_asserted=False,
                                depth_aggregation='ALL_SELECTED_TYPED_DEPTHS_WEIGHTED_BY_RAW_ROWS')
    if verification_sha is not None:
        packet['provenance'].update(catalog_census_verification_sha256=verification_sha,
            scope_predicate_policy='VERIFIED_SOURCE_MONTH_STATION_INTERSECTION')
    return packet


def overview(db,source='REGISTERED',preset='today',date_from=None,date_to=None,station_id='',variable_code='',network='',sea='',flag='',queue_limit=30,queue_offset=0,*,now=None):
    begin=stopwatch.monotonic();window=resolve_window(source,preset,date_from,date_to,now=now)
    scope=dict(station_id=station_id,variable_code=variable_code,network=network,sea=sea,flag=flag)
    if any(not isinstance(v,str) or len(v)>128 for v in scope.values()) or flag and flag not in FLAG_CODES:
        raise HTTPException(422,'QC 필터 값이 잘못됐습니다.')
    if isinstance(queue_limit,bool) or not isinstance(queue_limit,int) or not 1<=queue_limit<=30 or isinstance(queue_offset,bool) or not isinstance(queue_offset,int) or not 0<=queue_offset<=1000:
        raise HTTPException(422,'QC 검토 목록 조회 한도가 잘못됐습니다.')
    try:
        with db.no_autoflush:
            from app.services.qc_candidate_review import begin_readonly_snapshot,CandidateError
            snapshot_policy=begin_readonly_snapshot(db)
            registry=archive.registry_counts(db)
            if registry['state']!='AVAILABLE':raise HTTPException(503,'QC 운영 원장 테이블이 준비되지 않았습니다.')
            metadata,_=_references(db,window)
            packet=(_registered if source=='REGISTERED' else _archive)(db,window,scope,metadata,registry,queue_limit,queue_offset)
            packet['query']=dict(elapsed_seconds=stopwatch.monotonic()-begin,raw_rows_sent=len((packet['archive_samples'] or {}).get('rows',[])),
                                 registered_batch_size=REGISTERED_BATCH_SIZE,queue_limit=queue_limit,server_aggregation=True,snapshot_policy=snapshot_policy)
            packet.pop('result_sha256',None);packet['result_sha256']=digest(packet)
            return packet
    except (SQLAlchemyError,duckdb.Error,OSError):
        raise HTTPException(503,dict(code='QC_OVERVIEW_STORAGE_UNAVAILABLE',mutation_performed=False,reason='QC 운영 집계 조회 실패')) from None
    except CandidateError as exc:raise HTTPException(409,dict(code=exc.code,mutation_performed=False)) from None
