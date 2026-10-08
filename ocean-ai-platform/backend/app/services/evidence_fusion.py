"""Deterministic evidence support; no probability, QC decision or approval authority."""
from collections import defaultdict, Counter
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re

VERSION = 'evidence-fusion-v1'
WEIGHTS = {'RULE': .30, 'AI': .25, 'METADATA': .15, 'OPERATION': .15, 'RAG': .15}
KINDS = {'RULE': {'RULE_RESULT','RULE_ANALYSIS','GUIDE_RULE_RESULT'}, 'AI': {'AI_LABEL','ANOMALY_ANALYSIS'},
    'METADATA': {'SENSOR_METADATA','STATION_METADATA','SOURCE_CONTRACT','EQUIPMENT_METADATA'},
    'OPERATION': {'OPERATION_LOG','EVENT_REGISTRY'}, 'RAG': {'DOCUMENT_CHUNK','DOCUMENT_EVENT'}}
SCOPE_KEYS = ('station_id','sensor_id','variable_code','unit')

class FusionError(ValueError):
    def __init__(self, code): self.code=code;super().__init__(code)

def canonical(value):
    return json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode('utf-8')

def digest(value):return hashlib.sha256(canonical(value)).hexdigest()

def clock(value):
    if not isinstance(value,str):raise FusionError('EXPLICIT_OFFSET_CLOCK_REQUIRED')
    try:stamp=datetime.fromisoformat(value.replace('Z','+00:00'))
    except ValueError:raise FusionError('INVALID_CLOCK')
    if stamp.tzinfo is None or stamp.utcoffset() is None:raise FusionError('EXPLICIT_OFFSET_CLOCK_REQUIRED')
    return stamp.astimezone(timezone.utc)

def validate_scope(scope):
    if not isinstance(scope,dict) or any(not isinstance(scope.get(k),str) or not scope[k].strip() for k in SCOPE_KEYS):
        raise FusionError('EXACT_STATION_SENSOR_VARIABLE_UNIT_REQUIRED')
    result={k:scope[k] for k in SCOPE_KEYS}
    for k in ('period_start','period_end','as_of'):result[k]=clock(scope.get(k)).isoformat()
    if clock(result['period_start'])>=clock(result['period_end']):raise FusionError('INVALID_SCOPE_PERIOD')
    if clock(result['period_end'])>clock(result['as_of']):raise FusionError('FUTURE_SCOPE_PERIOD')
    if scope.get('sensor_episode_id'):result['sensor_episode_id']=scope['sensor_episode_id']
    return result

def recipe():
    return {'version':VERSION,'weights':WEIGHTS,'aggregation':'MAX_WITHIN_CATEGORY_FIXED_DENOMINATOR',
        'implementation_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'score_kind':'WEIGHTED_EVIDENCE_SUPPORT_NOT_PROBABILITY'}

def fuse_evidence(scope,evidence,fetch_status=None):
    scope=validate_scope(scope)
    if not isinstance(evidence,list) or len(evidence)>5000:raise FusionError('BOUNDED_EVIDENCE_LIST_REQUIRED')
    fetch_status=fetch_status or {}
    accepted=[];excluded=[];groups=defaultdict(list);duplicates=0;conflicts=[]
    def reject(item,reason):excluded.append({'source_id':item.get('source_id'),'category':item.get('category'),'reason':reason,'evidence':item})
    for original in evidence:
        if not isinstance(original,dict):raise FusionError('EVIDENCE_OBJECT_REQUIRED')
        item=json.loads(canonical(original));category=item.get('category');reason=None
        if category not in WEIGHTS:reason='UNKNOWN_CATEGORY'
        elif item.get('source_kind') not in KINDS[category]:reason='SOURCE_KIND_CATEGORY_MISMATCH'
        elif item.get('result_status')!='EVALUATED':reason='EVIDENCE_'+str(item.get('result_status','MISSING'))
        elif not isinstance(item.get('scope'),dict) or any(item['scope'].get(k)!=scope[k] for k in SCOPE_KEYS):reason='EVIDENCE_SCOPE_MISSING_OR_MISMATCH'
        elif scope.get('sensor_episode_id') and item['scope'].get('sensor_episode_id')!=scope['sensor_episode_id']:reason='SENSOR_EPISODE_MISMATCH'
        elif not isinstance(item.get('source_id'),str) or not item['source_id']:reason='SOURCE_ID_MISSING'
        elif not isinstance(item.get('source_sha256'),str) or not re.fullmatch('[0-9a-f]{64}',item['source_sha256']):reason='EXACT_SOURCE_HASH_REQUIRED'
        elif not isinstance(item.get('locator'),(str,dict)) or not item['locator']:reason='SOURCE_LOCATOR_REQUIRED'
        elif item.get('assessment') not in {'ANOMALY','NORMAL','CONTEXT','UNKNOWN'}:reason='ASSESSMENT_INVALID'
        elif type(item.get('support_strength')) not in {int,float} or not math.isfinite(item['support_strength']) or not 0<=item['support_strength']<=1:reason='SUPPORT_STRENGTH_INVALID'
        if not reason:
            try:
                event,available=clock(item.get('event_at')),clock(item.get('available_at'))
                if event>clock(scope['as_of']) or available>clock(scope['as_of']):reason='FUTURE_EVIDENCE'
                elif available<event:reason='AVAILABLE_BEFORE_EVENT'
                elif category in {'RULE','AI'} and not clock(scope['period_start'])<=event<clock(scope['period_end']):reason='EVIDENCE_OUTSIDE_OBSERVATION_PERIOD'
            except FusionError as exc:reason=exc.code
        if reason:reject(item,reason);continue
        item['event_at']=event.isoformat();item['available_at']=available.isoformat()
        # A payload APPROVED/confidence claim has no authority in this analysis.
        item['approved']=False;item['analysis_only']=True
        key=digest({'sha256':item['source_sha256'],'locator':item['locator']})
        groups[key].append(item)
    for key,items in sorted(groups.items()):
        signature=lambda x:digest({k:x[k] for k in ('category','source_kind','assessment','support_strength','scope','event_at','available_at')})
        if len({signature(x) for x in items})>1:
            conflicts.append({'kind':'CONTRADICTORY_DUPLICATE_PROVENANCE','provenance_id':key,'source_ids':sorted(x['source_id'] for x in items)})
            for item in items:reject(item,'CONTRADICTORY_DUPLICATE_PROVENANCE')
            continue
        item=sorted(items,key=lambda x:(x['source_id'],digest(x)))[0]
        item['provenance_id']=key;accepted.append(item);duplicates+=len(items)-1
    strengths={k:{'ANOMALY':0.0,'NORMAL':0.0} for k in WEIGHTS}
    coverage={}
    for category in WEIGHTS:
        members=[x for x in accepted if x['category']==category]
        for assessment in ('ANOMALY','NORMAL'):
            strengths[category][assessment]=max((x['support_strength'] for x in members if x['assessment']==assessment),default=0.0)
        status=(fetch_status.get(category) or {}).get('status')
        coverage[category]={'status':'PRESENT' if members else ('ERROR' if status=='ERROR' else 'MISSING'),
            'eligible_unique_evidence':len(members),'fetch_status':fetch_status.get(category),
            'excluded_count':sum(x['category']==category for x in excluded)}
    anomaly=sum(WEIGHTS[k]*strengths[k]['ANOMALY'] for k in WEIGHTS)
    normal=sum(WEIGHTS[k]*strengths[k]['NORMAL'] for k in WEIGHTS)
    claims=defaultdict(list)
    for item in accepted:
        if item['assessment'] in {'ANOMALY','NORMAL'} and item['support_strength']>0:
            claims[digest({'scope':item['scope'],'event_at':item['event_at']})].append(item)
    for key,members in sorted(claims.items()):
        if {x['assessment'] for x in members}=={'ANOMALY','NORMAL'}:
            conflicts.append({'kind':'ANOMALY_NORMAL_DISAGREEMENT','observation_scope_id':key,
                'event_at':members[0]['event_at'],'source_ids':sorted(x['source_id'] for x in members)})
    recommendation=('REVIEW_CONFLICT' if conflicts else 'REVIEW_ANOMALY' if anomaly else 'REVIEW_NORMAL_CANDIDATE' if normal else 'INSUFFICIENT_EVIDENCE')
    return {'schema_version':VERSION,'status':'ANALYSIS_ONLY','approved':False,'definitive_qc':False,
        'scope':scope,'recipe':recipe(),'score_kind':'WEIGHTED_EVIDENCE_SUPPORT_NOT_PROBABILITY',
        'recommendation_score':round(anomaly,8) if anomaly or normal else None,
        'anomaly_support':round(anomaly,8),'normal_support':round(normal,8),
        'coverage_weight':round(sum(WEIGHTS[k] for k,v in coverage.items() if v['status']=='PRESENT'),8),
        'coverage':coverage,'missing_categories':[k for k,v in coverage.items() if v['status']!='PRESENT'],
        'recommendation':recommendation,'conflicts':conflicts,'duplicate_count':duplicates,
        'accepted_evidence':accepted,'excluded_evidence':sorted(excluded,key=lambda x:(str(x['category']),str(x['source_id']),x['reason'])),
        'actions':['현재 범위의 원문·규칙·장비·운영·문서 근거 검토','미확정 단위·가용시각·센서 구간 확인']}

def rule_evidence(result):
    flag=result.get('result_flag');status=result.get('evaluation_status','NOT_EVALUATED')
    assessment='ANOMALY' if flag in {'3','4'} else 'NORMAL' if flag=='1' else 'UNKNOWN'
    if flag=='9':status='MISSING'
    provenance=result.get('provenance_json',result.get('provenance',{}))
    sha=provenance.get('input_window_sha256') or digest(result)
    return {'category':'RULE','source_kind':'RULE_ANALYSIS','source_id':str(result.get('qc_result_id') or result.get('observation_id',''))+':'+str(result.get('qc_rule_id',result.get('rule_id','')))+':'+str(result.get('rule_version','')),
        'source_sha256':sha,'locator':'rule-result:'+str(result.get('observation_id'))+':'+str(result.get('qc_rule_id',result.get('rule_id')))+':'+str(result.get('rule_version')),
        'scope':result.get('scope',{}),'event_at':result.get('event_at',result.get('observed_at')),'available_at':result.get('available_at'),
        'assessment':assessment,'support_strength':(0.5 if flag=='3' else 1.0) if status=='EVALUATED' and assessment!='UNKNOWN' else 0.0,
        'result_status':status,'provenance':provenance,'approved':False}

def ai_evidence(result):
    row=str(result.get('observation_id',result.get('row_id',result.get('result_id',''))))
    return {'category':'AI','source_kind':'ANOMALY_ANALYSIS','source_id':row+':'+str(result.get('mode','')),
        'source_sha256':result.get('report_sha256') or result.get('result_sha256') or digest(result),
        'locator':{'row_id':row,'mode':result.get('mode'),'artifact_sha256':result.get('artifact_sha256')},
        'scope':result.get('scope',{}),'event_at':result.get('event_at',result.get('observed_at')),'available_at':result.get('available_at'),
        'assessment':result.get('assessment','UNKNOWN'),'support_strength':result.get('support_strength'),
        'result_status':result.get('result_status',result.get('evaluation_status',result.get('status','NOT_EVALUATED'))),
        'provenance':{'analysis_result':result,'source_records':result.get('source_records',[]),
            'calibration_rank':result.get('calibration_rank'),'source_authority':'DECLARED_DEVELOPMENT_CONTRACT'},
        'score_kind':result.get('score_kind'),'approved':False}


def fuse_raw_diagnostics(series, artifact, ai_report, rule_report):
    """Separate native-clock review. It cannot authorize physical Fusion/QC.

    Recompute fixed held-out predictions and verify whole reports, preserving
    rule non-evaluation. No fabricated canonical scope or UTC is needed here.
    """
    from app.services.qc_raw_diagnostic import (analyze_raw_diagnostic,
        digest as raw_digest, REPORT as raw_schema, unevaluated_rule_report)
    if not isinstance(ai_report,dict) or ai_report.get('schema_version')!=raw_schema or ai_report!=analyze_raw_diagnostic(series,artifact):
        raise FusionError('RAW_DIAGNOSTIC_PREDICTION_MISMATCH')
    if not isinstance(rule_report,dict) or rule_report.get('schema_version')!='guide-qc-report-v1' or rule_report.get('result_sha256')!=digest({k:v for k,v in rule_report.items() if k!='result_sha256'}):
        raise FusionError('RULE_REPORT_CHECKSUM_MISMATCH')
    # This path has no physical source facts. Conditional evaluated Rule results
    # may not be silently relabelled as raw diagnostics for the same raw grain.
    if any(r.get('evaluation_status')!='NOT_EVALUATED' for r in rule_report.get('results',[])):
        raise FusionError('RAW_FUSION_REQUIRES_UNEVALUATED_PHYSICAL_RULES')
    try:
        executed_at=rule_report['results'][0]['provenance_json']['executed_at_utc']
        if rule_report!=unevaluated_rule_report(series,executed_at):
            raise FusionError('RAW_RULE_GRAIN_MEMBERSHIP_OR_RECIPE_MISMATCH')
    except (KeyError,IndexError,TypeError,ValueError) as exc:
        if isinstance(exc,FusionError):raise
        raise FusionError('RAW_RULE_GRAIN_MEMBERSHIP_OR_RECIPE_MISMATCH') from None
    results=ai_report['results'];eligible=[r for r in results if r['result_status']=='RAW_DIAGNOSTIC_EVALUATED']
    candidates=[r for r in eligible if r['candidate']]
    result={'schema_version':'raw-native-diagnostic-fusion-1','status':'RAW_DIAGNOSTIC_ONLY',
        'grain':series['grain'],'source_series_sha256':raw_digest(series),'artifact_sha256':artifact['sha256'],
        'ai_report_sha256':ai_report['result_sha256'],'rule_report_sha256':rule_report['result_sha256'],
        'raw_numeric_candidate_count':len(candidates),'raw_evaluated_count':len(eligible),
        'raw_support':max((r['calibration_rank'] for r in candidates),default=None),
        'score_kind':'RAW_EMPIRICAL_RANK_NOT_PROBABILITY_NOT_PHYSICAL_FUSION_SCORE',
        'physical_rule_status':'NOT_EVALUATED','physical_fusion_status':'NOT_EVALUATED',
        'physical_scope':None,'unit':None,'timezone':None,'source_qc_interpreted':False,
        'approved':False,'production_eligible':False,'cause_attribution':'NOT_ESTABLISHED',
        'rule_blocker_counts':dict(sorted(Counter(r['result_reason'] for r in rule_report.get('results',[])).items())),
        'coverage':{'RAW_AI':'EVALUATED' if eligible else 'NOT_EVALUATED','PHYSICAL_RULE':'NOT_EVALUATED',
            'METADATA':'UNRESOLVED','OPERATION':'UNRESOLVED','RAG':'NOT_LINKED'},
        'operational_evidence_eligible':False,'training_registry_writes':0}
    result['result_sha256']=digest(result)
    return result
