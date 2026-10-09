"""Ephemeral, token-separated synthetic QC cases; no DB/source/identity imports.

Only the existing pure Rule engine reads its checked-in definitions. Synthetic
missing planned slots use the declared -999 Rule input and remain null in the
display series. A sample review never approves an operational observation.
"""
from collections import Counter, defaultdict
from copy import deepcopy
from datetime import datetime, timedelta
from functools import lru_cache
import math
import re
import secrets
from threading import RLock
import time

from app.services.qc_rule_engine import (GUIDE_SHA256, KINDS, catalog, digest,
                                        execute_rules, implementation_hashes)

VERSION = 'QC_SAMPLE_SYNTHETIC_V1'
TTL_SECONDS = 14400
MAX_SESSIONS = 64
BOOTSTRAP_TTL_SECONDS = 300
MAX_BOOTSTRAPS = 256
MAX_ACTIONS_PER_SESSION = 512
KEY = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._:-]{7,127}$')
START = datetime.fromisoformat('2026-07-09T14:40:00+09:00')
END = datetime.fromisoformat('2026-07-09T15:40:00+09:00')
AS_OF = datetime.fromisoformat('2026-07-09T15:41:20+09:00')
SCENARIOS = (
    ('normal', '정상', '명시된 가상 단위·센서·간격으로 정상 범위를 검증합니다.', 50),
    ('late', '수신 지연', '선택 관측값이 8분 늦게 수신되어 DE Rule을 초과합니다.', 50),
    ('missing', '결측', '3개 예정 슬롯이 수신되지 않았습니다. 보간 없이 null로 표시합니다.', 30),
    ('spike', 'Spike · 범위 초과', '가상 수온 45도로 급변하여 SP 주의와 GR 범위 초과 BAD가 함께 계산됩니다.', 30),
)
_LOCK = RLock()
_BOOTSTRAPS = {}
_SESSIONS = {}
_CREATES = {}


class SampleError(ValueError):
    def __init__(self, code, status=409):
        self.code, self.status = code, status
        super().__init__(code)


def sample_window():
    value = dict(source='SAMPLE', start=START.isoformat(), end=END.isoformat(),
                 as_of=AS_OF.isoformat(), clock_basis='EXPLICIT_SYNTHETIC_OFFSET',
                 offset='+09:00', granularity='minute')
    return dict(value, window_id=digest(value))


def flag_catalog():
    rows = (('1', '정상', 'GOOD', '#10b981'), ('3', '주의 / Suspect', 'SUSPECT', '#f59e0b'),
            ('4', 'BAD', 'BAD', '#ef4444'), ('9', '결측 판정', 'MISSING', '#a855f7'),
            ('NOT_EVALUATED', 'Rule 미평가', 'NOT_EVALUATED', '#94a3b8'),
            ('UNKNOWN', '미확인', 'UNKNOWN', '#9ca3af'))
    return [dict(code=code, label=label, semantic=meaning, color=color,
                 color_policy='QC_DISPLAY_TONES_2', source='SAMPLE', stage='SAMPLE_RULE_QC')
            for code, label, meaning, color in rows]


def _key(value):
    if not isinstance(value, str) or not KEY.fullmatch(value):
        raise SampleError('SAMPLE_REQUEST_KEY_INVALID', 422)


def _token(actual, expected):
    return isinstance(actual, str) and len(actual) <= 200 and secrets.compare_digest(actual, expected)


def _seal(packet):
    packet.pop('result_sha256', None)
    packet['result_sha256'] = digest(packet)
    return packet


def _markers():
    return dict(source='SAMPLE', is_sample=True, approved=False, transient=True,
                production_writes=0, operational_writes=0, source_reads=0,
                model_training=0, final_qc_writes=0, restart_erases_state=True)


def _prune():
    now = time.monotonic()
    expired = [key for key, value in _SESSIONS.items() if now >= value['expires']]
    for key in expired:
        del _SESSIONS[key]
    for key in list(_BOOTSTRAPS):
        if now >= _BOOTSTRAPS[key]['expires']:
            del _BOOTSTRAPS[key]
    for key in list(_CREATES):
        if key[0] not in _BOOTSTRAPS or _CREATES[key]['session_id'] not in _SESSIONS:
            del _CREATES[key]


def context():
    with _LOCK:
        _prune()
        if len(_BOOTSTRAPS)>=MAX_BOOTSTRAPS:
            raise SampleError('SAMPLE_BOOTSTRAP_CAPACITY_REACHED',429)
        bootstrap_token='qc-sample-bootstrap-'+secrets.token_urlsafe(32)
        _BOOTSTRAPS[digest(dict(bootstrap_token=bootstrap_token))]=dict(expires=time.monotonic()+BOOTSTRAP_TTL_SECONDS)
    return _seal(dict(schema_version='qc-sample-context-1', **_markers(),
        bootstrap_token=bootstrap_token, bootstrap_expires_in_seconds=BOOTSTRAP_TTL_SECONDS,
        fixed_clock=AS_OF.isoformat(), window=sample_window(),
        scenario_catalog=[dict(scenario_id=key, label=label, description=description)
                          for key, label, description, _ in SCENARIOS],
        flag_catalog=flag_catalog(), sample_definition_version=VERSION,
        expires_in_seconds=TTL_SECONDS, max_sessions=MAX_SESSIONS,
        capabilities=dict(create_session=True, operational_identity=False,
                          trained_ai=False, definitive_qc=False)))


def _definition():
    return dict(version=VERSION, source='SAMPLE', synthetic=True, window=sample_window(),
        variable_code='WATER_TEMP', unit='degree_C', cadence_seconds=60, planned_slots=61,
        normal_value='20 + 0.25*sin(index*0.22)', delayed_index=50, delay_seconds=480,
        missing_indices=[29, 30, 31], missing_rule_sentinel=-999,
        missing_display_value=None, spike_index=30, spike_peak=45,
        thresholds=dict(DE_max_delay_seconds=300, SP_max_delta=1,
                        GR_min=0, GR_max=40, GD_duration_seconds=120),
        production_approval=False, trained_model=False)


def _provenance():
    hashes = implementation_hashes()
    return dict(**_markers(), rule_engine_version=catalog()['engine_version'],
        rule_implementation_sha256=hashes['implementation_sha256'],
        sample_definition_version=VERSION, sample_definition_sha256=digest(_definition()),
        rule_catalog_sha256=hashes['catalog_sha256'],
        clock_warning='명시된 가상 +09:00 시각이며 실제 원천의 시간대를 확정하지 않습니다.',
        missing_policy='EXPLICIT_SYNTHETIC_SENTINEL_FOR_ABSENT_SLOT; DISPLAY_NULL; NO_INTERPOLATION',
        ai_status='NOT_RUN', rule_authority='CONDITIONAL_SYNTHETIC_CONFIGURATION_NOT_SOURCE_APPROVAL')


def _specs(reference):
    quantity = catalog()['items']['WATER_TEMP']['quantity_kind']
    configs = {
        'WT': {}, 'ER': dict(sentinels=[-999]),
        'GR': dict(min=0, max=40, boundary='CLOSED'),
        'GD': dict(duration_seconds=120, interval_seconds=60, duration_boundary='AT_LEAST'),
        'SP': dict(interval_seconds=60, max_delta=1, difference='LINEAR'),
        'DE': dict(max_delay_seconds=300),
    }
    return [dict(qc_rule_id='QC-SAMPLE-'+kind, rule_version=VERSION, kind=kind,
        parameters=dict(variable_code='WATER_TEMP', unit='degree_C', quantity_kind=quantity,
                        missing_sentinels=[-999], calendar_timezone='UTC', failure_flag='3',
                        **configs.get(kind, {})),
        provenance=dict(guide_sha256=GUIDE_SHA256, pdf_pages=[23, 81],
            profile_id='EXPLICIT_SYNTHETIC_TEST_CONFIGURATION',
            configuration_reference=reference, conflict_resolution=reference),
        sample_configured=kind in configs,
        unconfigured_reason=None if kind in configs else 'SAMPLE_RELATED_OR_HISTORICAL_EVIDENCE_NOT_SUPPLIED')
        for kind in KINDS]


def _worst(results):
    # This is a declared SAMPLE display aggregation, not final QC flag approval.
    priority = {'4': 5, '9': 4, '3': 3, '1': 2, 'NOT_EVALUATED': 1, 'UNKNOWN': 0}
    return max((row['result_flag'] for row in results), key=lambda code: priority.get(code, 0), default='UNKNOWN')


@lru_cache(maxsize=1)
def _template():
    reference = dict(sha256=digest(_definition()), locator='SAMPLE:QC_SAMPLE_SYNTHETIC_V1:GENERATED_NO_REAL_SOURCE')
    specs = _specs(reference)
    template = {}
    names = {row['kind']: row['name_ko'] for row in catalog()['rules']}
    for kind, label, description, selected_index in SCENARIOS:
        station = 'SAMPLE-'+kind.upper()
        facts = dict(physical_sensor_id=station+'-SENSOR', sensor_episode_id=station+'-EPISODE',
            quantity_kind=catalog()['items']['WATER_TEMP']['quantity_kind'],
            clock_semantics='EXPLICIT_SYNTHETIC_OFFSET', source_timezone_name='Etc/GMT-9',
            effective_start=(START-timedelta(hours=1)).isoformat(),
            effective_end=(END+timedelta(hours=1)).isoformat(),
            available_at=(START-timedelta(minutes=1)).isoformat(),
            version_available_at=(START-timedelta(minutes=1)).isoformat(), evidence=reference)
        inputs, display = [], []
        for index in range(61):
            clock = START + timedelta(minutes=index)
            absent = kind == 'missing' and index in (29, 30, 31)
            value = round(20 + .25*math.sin(index*.22), 6)
            if kind == 'spike' and index == 30:
                value = 45.0
            received = None if absent else clock+timedelta(seconds=480 if kind=='late' and index==50 else 1)
            available = AS_OF if absent else received
            observation_id = 'SAMPLE:'+kind+':'+str(index)
            record = dict(observation_id=observation_id, station_id=station, sensor_id=station+'-CHANNEL',
                variable_code='WATER_TEMP', unit='degree_C', timestamp_utc=clock.isoformat(),
                value=-999.0 if absent else value, received_at=received.isoformat() if received else None,
                available_at=available.isoformat(), receive_evidence=reference if received else None,
                source_facts=facts)
            inputs.append(record)
            display.append(dict(observation_id=observation_id, observation_time=clock.isoformat(),
                value=None if absent else value, rule_input_value=record['value'],
                source_literal=None if absent else str(value), received_time=record['received_at'],
                available_at=record['available_at'], delay_seconds=None if absent else (received-clock).total_seconds(),
                is_missing=absent, is_late=False if absent else (received-clock).total_seconds()>300,
                observed=not absent, record_kind='SCHEDULED_SLOT_GAP' if absent else 'SYNTHETIC_OBSERVATION',
                interpolated=False))
        report = execute_rules(inputs, specs, dict(as_of=AS_OF.isoformat(), executed_at=AS_OF.isoformat()))
        grouped = defaultdict(list)
        for row in report['results']:
            grouped[row['observation_id']].append(row)
        for row in display:
            results = grouped[row['observation_id']]
            row['flag'] = _worst(results)
            row['rule_flags'] = [dict(rule_id=result['kind'], flag=result['result_flag'], reason=result['result_reason']) for result in results]
        target = display[selected_index]
        results = grouped[target['observation_id']]
        rule_summary = []
        for rule in specs:
            selected = [row for row in report['results'] if row['kind']==rule['kind']]
            evaluated = sum(row['evaluation_status'] in ('EVALUATED', 'MISSING') for row in selected)
            anomalies = sum(row['result_flag'] in ('3', '4', '9') for row in selected)
            rule_summary.append(dict(rule_id=rule['kind'], rule_name=names[rule['kind']], evaluated_count=evaluated,
                anomaly_count=anomalies, not_evaluated_count=len(selected)-evaluated,
                full_test_evaluated_count=sum(row['evaluation_status']=='EVALUATED' for row in selected),
                missing_precheck_count=sum(row['evaluation_status']=='MISSING' for row in selected),
                sample_configured=rule['sample_configured'],
                state='EVALUATED' if evaluated else 'NOT_EVALUATED'))
        template[kind] = dict(scenario_id=kind, label=label, description=description, station_id=station,
            station_name='샘플 '+label+' 관측소', variable_code='WATER_TEMP', unit='degree_C',
            observation_time=target['observation_time'], value=target['value'], flag=target['flag'],
            meaning=next(row['semantic'] for row in flag_catalog() if row['code']==target['flag']),
            rule_ids=[row['kind'] for row in results if row['result_flag'] in ('3','4','9')],
            delay_seconds=target['delay_seconds'], is_missing=target['is_missing'],
            series=dict(rows=display, unit='degree_C', cadence_seconds=60, planned_slots=61,
                received_slots=sum(row['observed'] for row in display), missing_slots=sum(row['is_missing'] for row in display),
                interpolated=False), rules=results, rule_specs=specs, rule_summary=rule_summary,
            rule_result_count=len(report['results']), source_facts=facts,
            evidence=[dict(kind='SYNTHETIC_SOURCE_CONTRACT', source='SAMPLE', label='명시된 가상 원천·센서 계약',
                           sha256=reference['sha256'], description='실제 원천·계정·승인과 관계없는 고정 샘플 정의입니다.'),
                      dict(kind='ACTUAL_RULE_EXECUTION', source='SAMPLE', label='기존 Rule 엔진 계산 결과',
                           sha256=report['result_sha256'], description='WT/ER/GR/GD/SP/DE는 가상 설정으로 계산합니다. 다른 Rule의 관련·과거 근거는 제공하지 않았으며, 결측 sentinel 선행 검사 9는 과거 baseline 검사 완료를 뜻하지 않습니다.')])
    return template


def _cases(generation, session_id):
    cases = deepcopy(_template())
    for kind, case in cases.items():
        case['case_id'] = 'sample-'+kind+'-g'+str(generation)
        case['revision'] = 1
        case['recommendation_sha256'] = digest(dict(sample_definition=_definition(), session_id=session_id, case_id=case['case_id'],
            target_rule_results=case['rules'], evidence=case['evidence']))
        case['workflow'] = dict(status='PENDING', blocked=True, downstream_executed=False,
            approved=False, definitive_qc=False, history=[dict(sequence=1, action='CREATE', from_state=None,
                to_state='PENDING', comment='샘플 검토가 필요하여 후속 단계에서 정지했습니다.',
                actor='SAMPLE_ENGINE', sample_clock=AS_OF.isoformat())])
    return {case['case_id']:case for case in cases.values()}


def _session(token, session_id):
    _prune()
    session = _SESSIONS.get(session_id)
    if session is None or not _token(token, session['token']):
        raise SampleError('SAMPLE_SESSION_NOT_FOUND_OR_TOKEN_INVALID', 401)
    return session


def _session_receipt(session, replay=False):
    return _seal(dict(schema_version='qc-sample-session-1', **_markers(), session_id=session['id'],
        session_token=session['token'], session_revision=session['revision'], generation=session['generation'],
        expires_in_seconds=TTL_SECONDS, idempotent_replay=replay, window=sample_window(),
        session_history=deepcopy(session['history'])))


def create_session(token, request_key):
    _key(request_key)
    if not isinstance(token,str) or not token.startswith('qc-sample-bootstrap-') or len(token)>200:
        raise SampleError('SAMPLE_BOOTSTRAP_TOKEN_REQUIRED', 401)
    with _LOCK:
        _prune()
        bootstrap_sha=digest(dict(bootstrap_token=token))
        if bootstrap_sha not in _BOOTSTRAPS:
            raise SampleError('SAMPLE_BOOTSTRAP_TOKEN_EXPIRED_OR_INVALID',401)
        create_key=(bootstrap_sha,request_key)
        if create_key in _CREATES:
            packet=deepcopy(_CREATES[create_key]['packet']);packet['idempotent_replay']=True
            return _seal(packet)
        if len(_SESSIONS)>=MAX_SESSIONS:
            raise SampleError('SAMPLE_SESSION_CAPACITY_REACHED', 429)
        session_id='qc-sample-session-'+secrets.token_urlsafe(18)
        session=dict(id=session_id, token='qc-sample-token-'+secrets.token_urlsafe(32), revision=1,
            generation=1, expires=time.monotonic()+TTL_SECONDS, cases=_cases(1,session_id), actions={},
            history=[dict(sequence=1,action='CREATE_SESSION',generation=1,session_revision=1,
                          sample_clock=AS_OF.isoformat(),actor='SAMPLE_ENGINE')])
        _SESSIONS[session_id]=session
        packet=_session_receipt(session)
        _CREATES[create_key]=dict(session_id=session_id,packet=deepcopy(packet))
        return packet


def _case_row(case):
    keys=('case_id','scenario_id','label','description','station_id','station_name','variable_code','unit',
          'observation_time','value','flag','meaning','rule_ids','delay_seconds','is_missing','revision','recommendation_sha256')
    return dict({key:deepcopy(case[key]) for key in keys}, review_status=case['workflow']['status'])


def _workflow(case):
    workflow=deepcopy(case['workflow']);state=workflow['status']
    workflow.update(revision=case['revision'],recommendation_sha256=case['recommendation_sha256'],
        capabilities=dict(comment=True, approve=state in ('PENDING','HELD'), hold=state in ('PENDING','APPROVED'),
                          reject=state in ('PENDING','HELD','APPROVED'), resume=state=='APPROVED'))
    return workflow


def _detail(session, case, replay=False):
    return _seal(dict(schema_version='qc-sample-detail-1', **_markers(), session_id=session['id'],
        session_revision=session['revision'],generation=session['generation'],window=sample_window(),
        case=_case_row(case),revision=case['revision'],recommendation_sha256=case['recommendation_sha256'],
        series=deepcopy(case['series']),rules=deepcopy(case['rules']),rule_specs=deepcopy(case['rule_specs']),
        equipment=dict(source='SAMPLE',synthetic=True,station_id=case['station_id'],
            physical_sensor_id=case['source_facts']['physical_sensor_id'],
            sensor_episode_id=case['source_facts']['sensor_episode_id'],label='가상 수온 센서',unit=case['unit']),
        source_facts=deepcopy(case['source_facts']),evidence=deepcopy(case['evidence']),
        session_history=deepcopy(session['history']),
        ai=dict(status='NOT_RUN',trained_model=False,result=None),workflow=_workflow(case),
        provenance=_provenance(),idempotent_replay=replay))


def detail(token, session_id, case_id):
    with _LOCK:
        session=_session(token,session_id);case=session['cases'].get(case_id)
        if case is None:raise SampleError('SAMPLE_CASE_NOT_FOUND',404)
        return _detail(session,case)


def overview(token, session_id):
    with _LOCK:
        session=_session(token,session_id);cases=list(session['cases'].values());total=len(cases)
        flags=Counter(case['flag'] for case in cases);states=Counter(case['workflow']['status'] for case in cases)
        summary={key:dict(count=flags[code],rate=100*flags[code]/total,denominator=total,stage='SAMPLE_CASE')
                 for key,code in (('normal','1'),('suspect','3'),('bad','4'),('missing','9'))}
        for row in summary.values():row['denominator_basis']='REPRESENTATIVE_SAMPLE_CASES'
        summary.update({key:dict(count=states[state],rate=100*states[state]/total,denominator=total,
                                stage='SAMPLE_REVIEW_WORKFLOW',definitive_qc=False)
                        for key,state in (('pending','PENDING'),('completed','COMPLETED'))})
        rows=[_case_row(case) for case in cases]
        trend={};matrix=[]
        count_key={'1':'normal','3':'suspect','4':'bad','9':'missing'}
        empty=lambda:dict(normal=0,suspect=0,bad=0,missing=0,unknown=0)
        for case in cases:
            counts=empty()
            for point in case['series']['rows']:
                bucket=point['observation_time'];entry=trend.setdefault(bucket,dict(bucket=bucket,start=bucket,end=bucket,total=0,counts=empty()))
                key=count_key.get(point['flag'],'unknown');entry['counts'][key]+=1;entry['total']+=1;counts[key]+=1
            matrix.append(dict(station_id=case['station_id'],station_name=case['station_name'],variable_code=case['variable_code'],
                label=case['label'],total=case['series']['planned_slots'],counts=counts))
        rules=[]
        for index,kind in enumerate(KINDS):
            rows_for_kind=[case['rule_summary'][index] for case in cases]
            evaluated=sum(row['evaluated_count'] for row in rows_for_kind)
            rules.append(dict(rule_id=kind,rule_name=rows_for_kind[0]['rule_name'],evaluated_count=evaluated,
                anomaly_count=sum(row['anomaly_count'] for row in rows_for_kind),
                not_evaluated_count=sum(row['not_evaluated_count'] for row in rows_for_kind),
                full_test_evaluated_count=sum(row['full_test_evaluated_count'] for row in rows_for_kind),
                missing_precheck_count=sum(row['missing_precheck_count'] for row in rows_for_kind),
                sample_configured=rows_for_kind[0]['sample_configured'],
                state='EVALUATED' if evaluated else 'NOT_EVALUATED'))
        return _seal(dict(schema_version='qc-sample-overview-1',**_markers(),session_id=session['id'],
            session_revision=session['revision'],generation=session['generation'],window=sample_window(),
            flag_catalog=flag_catalog(),summary=summary,
            counts=dict(case_count=total,planned_slots=sum(case['series']['planned_slots'] for case in cases),
                received_slots=sum(case['series']['received_slots'] for case in cases),
                missing_slots=sum(case['series']['missing_slots'] for case in cases),
                card_denominator_basis='REPRESENTATIVE_SAMPLE_CASES',series_denominator_basis='SYNTHETIC_PLANNED_SLOTS'),
            flag_distribution=[dict(code=row['code'],label=row['label'],color=row['color'],count=flags[row['code']],
                rate=100*flags[row['code']]/total,denominator=total) for row in flag_catalog()],
            quality_trend=sorted(trend.values(),key=lambda row:row['bucket']),
            rule_qc_counts=dict(catalog_count=12,result_count=sum(case['rule_result_count'] for case in cases),items=rules),
            station_variable_matrix=matrix,cases=rows,review_queue=dict(rows=deepcopy(rows),total=total),
            session_history=deepcopy(session['history']),
            states=dict(ai='NOT_RUN',model='NO_MODEL',approval='SAMPLE_ONLY'),provenance=_provenance()))


def _replay(session, request_key, fingerprint):
    stored=session['actions'].get(request_key)
    if stored is not None:
        if stored['fingerprint']!=fingerprint:raise SampleError('SAMPLE_IDEMPOTENCY_KEY_REUSED')
        packet=deepcopy(stored['packet']);packet['idempotent_replay']=True
        return _seal(packet)
    if len(session['actions'])>=MAX_ACTIONS_PER_SESSION:
        raise SampleError('SAMPLE_ACTION_CAPACITY_REACHED',429)
    return None


def review(token, session_id, case_id, action, comment, expected_revision, recommendation_sha256, request_key):
    _key(request_key)
    if action not in ('COMMENT','APPROVE','HOLD','REJECT','RESUME'):
        raise SampleError('SAMPLE_ACTION_INVALID',422)
    if not isinstance(comment,str) or not comment.strip() or len(comment)>2000:
        raise SampleError('SAMPLE_COMMENT_REQUIRED',422)
    fingerprint=digest(dict(case_id=case_id,action=action,comment=comment,expected_revision=expected_revision,
                            recommendation_sha256=recommendation_sha256))
    with _LOCK:
        session=_session(token,session_id)
        case=session['cases'].get(case_id)
        if case is None:raise SampleError('SAMPLE_CASE_NOT_FOUND',404)
        replay=_replay(session,request_key,fingerprint)
        if replay is not None:return replay
        if type(expected_revision) is not int or expected_revision!=case['revision']:
            raise SampleError('SAMPLE_STALE_REVISION')
        if not isinstance(recommendation_sha256,str) or recommendation_sha256!=case['recommendation_sha256']:
            raise SampleError('SAMPLE_RECOMMENDATION_CHANGED')
        current=case['workflow']['status']
        allowed={'COMMENT':True,'APPROVE':current in ('PENDING','HELD'),'HOLD':current in ('PENDING','APPROVED'),
                 'REJECT':current in ('PENDING','HELD','APPROVED'),'RESUME':current=='APPROVED'}
        if not allowed[action]:raise SampleError('SAMPLE_WORKFLOW_GATE_BLOCKED')
        target={'COMMENT':current,'APPROVE':'APPROVED','HOLD':'HELD','REJECT':'REJECTED','RESUME':'COMPLETED'}[action]
        history=case['workflow']['history']
        if action=='RESUME':
            history.append(dict(sequence=len(history)+1,action='RESUME',from_state=current,to_state='RESUMING',
                                comment=comment.strip(),actor='SAMPLE_REVIEWER',sample_clock=AS_OF.isoformat()))
            history.append(dict(sequence=len(history)+1,action='COMPLETE_SAMPLE_DRAFT',from_state='RESUMING',to_state='COMPLETED',
                                comment='승인 후 가상 후속 초안 단계만 실행했습니다.',actor='SAMPLE_ENGINE',sample_clock=AS_OF.isoformat()))
        else:
            history.append(dict(sequence=len(history)+1,action=action,from_state=current,to_state=target,
                                comment=comment.strip(),actor='SAMPLE_REVIEWER',sample_clock=AS_OF.isoformat()))
        case['workflow'].update(status=target,blocked=target!='COMPLETED',downstream_executed=target=='COMPLETED')
        case['revision']+=1;session['revision']+=1
        packet=_detail(session,case)
        session['actions'][request_key]=dict(fingerprint=fingerprint,packet=deepcopy(packet))
        return packet


def reset(token, session_id, expected_session_revision, request_key):
    _key(request_key);fingerprint=digest(dict(action='RESET',expected_session_revision=expected_session_revision))
    with _LOCK:
        session=_session(token,session_id);replay=_replay(session,request_key,fingerprint)
        if replay is not None:return replay
        if type(expected_session_revision) is not int or expected_session_revision!=session['revision']:
            raise SampleError('SAMPLE_STALE_SESSION_REVISION')
        session['generation']+=1;session['revision']+=1;session['cases']=_cases(session['generation'],session_id)
        session['history'].append(dict(sequence=len(session['history'])+1,action='RESET_SESSION',
            generation=session['generation'],session_revision=session['revision'],
            sample_clock=AS_OF.isoformat(),actor='SAMPLE_REVIEWER'))
        packet=_session_receipt(session)
        session['actions'][request_key]=dict(fingerprint=fingerprint,packet=deepcopy(packet))
        return packet


def reset_store_for_tests():
    """Test-only state cleanup. This helper has no public route."""
    with _LOCK:
        _SESSIONS.clear();_CREATES.clear();_BOOTSTRAPS.clear();_template.cache_clear()
