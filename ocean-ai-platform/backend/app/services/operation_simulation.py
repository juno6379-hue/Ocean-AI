"""Deterministic synthetic faults using the actual diagnostic/QC/AI/gate code.

No get_db/SessionLocal, source scanning, real identities, or filesystem writes.
The explicitly declared UTC simulation clock does not resolve a real clock.
"""
from collections import Counter
from datetime import datetime, timedelta, timezone
import math

import numpy as np
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.core.security import Actor
from app.agents import multi_agent_workflow as workflow
from app.models.domain import ModelRegistry, RetrainingHistory, ReportRegistry, ObservationStandard, ObservationRaw
from app.services.anomaly_analysis import fit_analysis, analyze_series
from app.services.evidence_fusion import digest
from app.services.qc_rule_engine import execute_rules, catalog, GUIDE_SHA256
from app.services.observation_operation import summarize_channel, classify_channel, aggregate_station, native_clock

VERSION = 'operation-quality-simulation-v1'
SCENARIOS = [
    ('normal', '정상 흐름', '1분 관측·유효 값·명시된 가상 QC 및 점검 이력', 'NORMAL'),
    ('delay', '관측 지연', '마지막 10분의 관측이 아직 도착하지 않음', 'WARNING'),
    ('missing', '결측 구간', '최근 24시간 중 25%의 관측 시각 누락', 'ABNORMAL'),
    ('bad_qc', '원문 QC 이상', '가상 코드북에서 B로 정의한 QC 20% 발생', 'ABNORMAL'),
    ('spike', '순간 급변', '독립된 시험 구간에 수온 급변 주입', 'NORMAL'),
    ('temp_drift', '수온 drift', '시험 구간 후반 수온과 독립 기준 센서의 차이가 증가', 'NORMAL'),
    ('sal_drift', '염분 drift', '시험 구간 후반 염분과 독립 기준 센서의 차이가 증가', 'NORMAL'),
    ('persistence', '지속 동일 값', '시험 구간 후반 응답이 고정됨', 'NORMAL'),
    ('biofouling', '생물 부착 후보', '시험 구간 후반 독립 센서 대비 응답 변동이 감소', 'NORMAL'),
    ('tide_residual', '조위 residual', '동일 기준면의 가상 예측 조위 대비 편차 주입', 'NORMAL'),
    ('maintenance', '점검 사건', '기준시각 전에 알려진 미해결 장비 점검 사건', 'ABNORMAL'),
    ('recovery', '점검 후 복구', '동일 사건·센서와 정확히 연결된 복구 이력', 'NORMAL'),
    ('future', '미래 근거 제외', '기준시각 뒤 관측과 점검 사건을 추가하여 과거 판정 보호', 'NORMAL'),
    ('duplicate', '동일 시각 충돌', '동일 센서·시각의 서로 다른 원문 값', 'WARNING'),
    ('cadence_change', '관측 간격 변경', '과거 1분에서 최근 2분으로 변경되어 분모 확정 보류', 'WARNING'),
]


def scenarios():
    return {'source': 'SIMULATION', 'is_simulation': True, 'approved': False,
            'scenarios': [dict(scenario_id=s, label=l, description=d, expected_operation_state=e)
                          for s, l, d, e in SCENARIOS]}


def _observations(kind, cutoff):
    end = cutoff.replace(second=0, microsecond=0)
    rows = []
    for i in range(2880):
        when = end - timedelta(minutes=2879-i)
        if kind == 'delay' and when > end-timedelta(minutes=10):
            continue
        if kind == 'missing' and 1440 <= i < 1800:
            continue
        if kind == 'cadence_change' and i >= 1440 and i % 2:
            continue
        rows.append(dict(observed_time_raw=str(when), value_raw=f'{20+math.sin(i*.3):.6f}',
            source_qc_raw='B' if kind == 'bad_qc' and i >= 1440 and i % 5 == 0 else 'G',
            received_time_raw=str(when+timedelta(seconds=1)), source='SIMULATION'))
    if kind == 'future':
        rows.append(dict(rows[-1], observed_time_raw=str(cutoff+timedelta(hours=1)), value_raw='999'))
    if kind == 'duplicate':
        rows.append(dict(rows[-1], value_raw='999'))
    return rows


def _evidence(kind, cutoff):
    from app.services.observation_operation_evidence import evaluate_records
    native = lambda minutes: str(cutoff+timedelta(minutes=minutes))
    records = {key: [] for key in ('operation_log', 'daily_inspection_report', 'quality_collection_report', 'qc_flag_history', 'event_registry')}
    records['daily_inspection_report'].append(dict(station_id='SIM-STATION', sensor_id='SIM-SENSOR',
        report_id='SIM-INSPECTION-1', report_date=native(-30), available_at=native(-25),
        diagnostic_state='NORMAL', signal_reason='SYNTHETIC_INSPECTION_CHECKLIST_PASSED',
        follow_up_required=False, clock_basis='NATIVE_SIMULATION'))
    if kind in {'maintenance', 'recovery', 'future'}:
        minutes = 60 if kind == 'future' else -120
        records['event_registry'].append(dict(station_id='SIM-STATION', sensor_id='SIM-SENSOR',
            event_id='SIM-EVENT-1', event_start=native(minutes), event_end=None, status='OPEN',
            severity='ABNORMAL', available_at=native(minutes), version_available_at=native(minutes),
            clock_basis='NATIVE_SIMULATION'))
    if kind == 'recovery':
        records['operation_log'].append(dict(station_id='SIM-STATION', sensor_id='SIM-SENSOR',
            event_type='RECOVERY', event_time=native(-60), available_at=native(-60),
            resolution_of='SIM-EVENT-1', clock_basis='NATIVE_SIMULATION'))
    result = evaluate_records(records, ['SIM-STATION'], str(cutoff), native(-1440), source='SIMULATION')['SIM-STATION']
    result['qc_semantics'] = dict(state='USABLE', mapping={'G': 'GOOD', 'B': 'BAD'},
        source='SIMULATION', source_group='SIMULATION', station_code='SIM-STATION', physical_sensor_id='SIM-SENSOR',
        item_code='TIDE' if kind == 'tide_residual' else 'SALINITY' if kind == 'sal_drift' else 'WATER_TEMP',
        field='source_qc_raw', clock_basis='NATIVE_SIMULATION', codebook_version='SYNTHETIC-QC-v1',
        effective_start=native(-5000), effective_end=native(5000), available_at=native(-5000), version_available_at=native(-5000))
    return result


def _quality_inputs(kind, cutoff):
    family = 'TIDE' if kind == 'tide_residual' else 'SAL' if kind == 'sal_drift' else 'TEMP'
    variable = 'TIDE' if family == 'TIDE' else 'SALINITY' if family == 'SAL' else 'WATER_TEMP'
    unit = 'm' if family == 'TIDE' else 'psu' if family == 'SAL' else 'degree_C'
    start = cutoff.replace(second=0, microsecond=0, tzinfo=timezone.utc)-timedelta(minutes=540)
    stamp = lambda i: (start+timedelta(minutes=i)).isoformat()
    scope = dict(station_id='SIM-STATION', sensor_id='SIM-SENSOR', sensor_episode_id='SIM-EPISODE', variable_code=variable, unit=unit)
    ref = {'sha256': digest({'kind': 'SIMULATION', 'version': VERSION}), 'locator': 'SYNTHETIC-TEST-ONLY'}
    facts = {key: dict(documented=True, value=value, evidence=[ref], start=stamp(-100), end=stamp(1000)) for key, value in {
        'semantic': variable, 'unit': unit, 'clock': 'UTC_WITH_EXPLICIT_OFFSET', 'qc': 'SYNTHETIC-QC-v1',
        'sensor_episode': 'SIM-EPISODE', 'datum': 'SYNTHETIC-DATUM'}.items()}
    facts['semantic']['variable_family'] = family
    facts['sensor_episode']['physical_sensor_id'] = scope['sensor_id']
    reference = dict(kind='PREDICTED_TIDE' if family == 'TIDE' else 'INDEPENDENT_SENSOR',
        unit=unit, station_id=scope['station_id'], variable_code=variable, datum='SYNTHETIC-DATUM', evidence=[ref],
        sensor_id='SIM-REFERENCE', sensor_episode_id='SIM-REFERENCE-EPISODE', effective_start=stamp(-1),
        effective_end=stamp(1000), qc_version='SYNTHETIC-QC-v1', qc_effective_start=stamp(-1),
        qc_effective_end=stamp(1000), model_training_end=stamp(-100))
    rng = np.random.default_rng(61)
    rows = []
    for i in range(540):
        baseline = 20+math.sin(i*.3)*.8+math.sin(i*.075)*.4
        value = float(baseline+rng.normal(0, .015))
        if i >= 440:
            if kind in {'temp_drift', 'sal_drift'}: value += (i-440)*.01
            elif kind == 'tide_residual': value += .5
            elif kind == 'persistence': value = 20.
            elif kind == 'biofouling': value = 20+(baseline-20)*.01
        if kind == 'spike' and i in (420, 460, 500): value += 4.
        rows.append(dict(row_id=str(i), timestamp=stamp(i), available_at=stamp(i), qc_available_at=stamp(i),
            scope=scope, value=value, qc_eligible=True, source=dict(sha256=ref['sha256'], locator=f'SIMULATION:primary:{i}'),
            reference=dict(value=float(baseline), timestamp=stamp(i), available_at=stamp(i), qc_available_at=stamp(i),
                unit=unit, station_id=scope['station_id'], variable_code=variable, datum='SYNTHETIC-DATUM',
                issued_at=stamp(i-1), sensor_id='SIM-REFERENCE', sensor_episode_id='SIM-REFERENCE-EPISODE',
                source=dict(sha256=ref['sha256'], locator=f'SIMULATION:reference:{i}'), qc_eligible=True)))
    base = dict(schema_version='ocean-anomaly-series-1', scope=scope, facts=facts, reference_contract=reference,
        candidate_context={key: dict(applicable=True, evidence=[ref]) for key in ('BIOFOULING_CANDIDATE', 'SENSOR_DEGRADATION_CANDIDATE')})
    fit = dict(base, as_of=stamp(380), rows=rows[:380])
    testrows = rows[380:]
    if kind == 'delay': testrows = testrows[:-10]
    if kind == 'bad_qc':
        for row in testrows:
            row['qc_eligible'] = (int(row['row_id'])+2340) % 5 != 0
    test = dict(base, as_of=cutoff.replace(tzinfo=timezone.utc).isoformat(), rows=testrows)
    modes = ['TIDE_RESIDUAL', 'SPIKE', 'PERSISTENCE'] if family == 'TIDE' else ['SPIKE', 'PERSISTENCE', 'DRIFT', 'BIOFOULING_CANDIDATE', 'SENSOR_DEGRADATION_CANDIDATE']
    protocol = dict(schema_version='ocean-anomaly-protocol-1', protocol_id='SYNTHETIC-ONLY', version=VERSION,
        variable_family=family, modes=modes, cadence_seconds=60, window_samples=8, min_train_samples=50,
        min_calibration_samples=50, scale_floor=.001, persistence_epsilon=.001, calibration_quantile=.99,
        periods={'TRAIN': dict(start=stamp(0), end=stamp(220)), 'CALIBRATION': dict(start=stamp(220), end=stamp(380))},
        membership_sha256={'TRAIN': digest(sorted(str(i) for i in range(220))), 'CALIBRATION': digest(sorted(str(i) for i in range(220, 380)))})
    qfacts = dict(physical_sensor_id='SIM-SENSOR', sensor_episode_id='SIM-EPISODE', quantity_kind=catalog()['items'][variable]['quantity_kind'],
        clock_semantics='EXPLICIT_SYNTHETIC_UTC', source_timezone_name='UTC', effective_start=stamp(-100), effective_end=stamp(1000), reference_datum='SYNTHETIC-DATUM', evidence=ref)
    qcrows = [dict(observation_id=r['row_id'], station_id=scope['station_id'], sensor_id=scope['sensor_id'],
        variable_code=variable, unit=unit, timestamp_utc=r['timestamp'], available_at=(datetime.fromisoformat(r['timestamp'])+timedelta(seconds=1)).isoformat(), value=r['value'], source_facts=qfacts,
        received_at=(datetime.fromisoformat(r['timestamp'])+timedelta(seconds=1)).isoformat(), receive_evidence=ref) for r in test['rows']]
    specs = []
    for name, params in [('WT', {}), ('ER', {'sentinels': [-999]}), ('GR', {'min': -50, 'max': 60, 'boundary': 'CLOSED'}),
                         ('GD', {'duration_seconds': 120, 'interval_seconds': 60, 'duration_boundary': 'AT_LEAST'}),
                         ('SP', {'max_delta': 1, 'interval_seconds': 60, 'difference': 'LINEAR'}), ('DE', {'max_delay_seconds': 300})]:
        specs.append(dict(qc_rule_id='SIM-'+name, rule_version=VERSION, kind=name,
            parameters=dict(variable_code=variable, unit=unit, quantity_kind=qfacts['quantity_kind'], missing_sentinels=[-999], calendar_timezone='UTC', failure_flag='3', **params),
            provenance=dict(guide_sha256=GUIDE_SHA256, pdf_pages=[23, 81], profile_id='EXPLICIT_SYNTHETIC_TEST_CONFIGURATION', configuration_reference=ref, conflict_resolution=ref)))
    return fit, test, protocol, qcrows, specs


def _gate(scope, rule_report, ai_report, extra_evidence):
    """Exercise real durable service roles and replay gates in a disposable DB."""
    engine = create_engine('sqlite://')
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    op, reviewer = Actor('SIM-OPERATOR', 'operator'), Actor('SIM-REVIEWER', 'reviewer')
    proof = {}
    def blocked(fn, expected):
        try: fn()
        except workflow.WorkflowError as exc: return str(exc) == expected
        return False
    try:
        with sessions() as db:
            payload, fusion = workflow.analyze_inputs(db, scope, declared_evidence=extra_evidence,
                rule_report=rule_report, ai_report=ai_report,
                rag_search=lambda *args: dict(results=[], evidence_status='SYNTHETIC_ISOLATED', vector_status='EMPTY'))
            pending = workflow.start_workflow(db, payload, fusion, op, 'SIM-START'); db.commit()
            sha, wid = pending['recommendation_sha256'], pending['workflow_id']
            proof['pending_stopped'] = pending['status'] == 'PENDING' and pending['result'] is None and len(pending['workflow']) == 4
            proof['unapproved_resume_blocked'] = blocked(lambda: workflow.resume_workflow(db, wid, op, 'SIM-UNAPPROVED', sha, 0), 'WORKFLOW_APPROVAL_REQUIRED')
            proof['reviewer_required'] = blocked(lambda: workflow.decide_workflow(db, wid, op, 'SIM-BAD-ROLE', sha, 0, 'APPROVED'), 'REVIEWER_REQUIRED')
            approved = workflow.decide_workflow(db, wid, reviewer, 'SIM-APPROVE', sha, 0, 'APPROVED'); db.commit()
            proof['stale_revision_blocked'] = blocked(lambda: workflow.resume_workflow(db, wid, op, 'SIM-STALE', sha, 0), 'STALE_WORKFLOW_REVISION')
            done = workflow.resume_workflow(db, wid, op, 'SIM-RESUME', sha, approved['revision']); db.commit()
            replay = workflow.resume_workflow(db, wid, op, 'SIM-RESUME', sha, approved['revision']); db.commit()
            proof['resumed_once'] = replay == done and done['status'] == 'COMPLETED'
            rejected = workflow.start_workflow(db, payload, fusion, op, 'SIM-REJECT-START'); db.commit()
            refusal = workflow.decide_workflow(db, rejected['workflow_id'], reviewer, 'SIM-REJECT', rejected['recommendation_sha256'], 0, 'REJECTED'); db.commit()
            proof['rejected_resume_blocked'] = blocked(lambda: workflow.resume_workflow(db, rejected['workflow_id'], op, 'SIM-REJECT-RESUME', rejected['recommendation_sha256'], refusal['revision']), 'WORKFLOW_APPROVAL_REQUIRED')
            proof['production_writes'] = sum(db.query(model).count() for model in (ModelRegistry, RetrainingHistory, ReportRegistry, ObservationStandard, ObservationRaw))
            proof.update(status=done['status'], transitions=['PENDING', 'APPROVED', 'COMPLETED'],
                database='DISPOSABLE_IN_MEMORY_SQLITE', actual_approval_granted=False,
                training_started=done['training_started'], deployment_performed=done['deployment_performed'])
            return fusion, proof
    finally:
        engine.dispose()


def run_simulation(scenario_id, as_of_day, as_of_time):
    selected = next((row for row in SCENARIOS if row[0] == scenario_id), None)
    if selected is None: raise ValueError('UNKNOWN_SIMULATION_SCENARIO')
    cutoff = native_clock(as_of_day+' '+as_of_time)
    if cutoff is None: raise ValueError('EXACT_NATIVE_SIMULATION_CUTOFF_REQUIRED')
    raw = _observations(scenario_id, cutoff)
    evidence = _evidence(scenario_id, cutoff)
    fit, test, protocol, qcrows, specs = _quality_inputs(scenario_id, cutoff)
    # The visible held-out curve and diagnostic records share injected values.
    trial_values = {str(datetime.fromisoformat(r['timestamp']).replace(tzinfo=None)): r['value'] for r in test['rows']}
    for record in raw:
        if record['observed_time_raw'] in trial_values:
            record['value_raw'] = str(trial_values[record['observed_time_raw']])
    stats = summarize_channel(raw, cutoff, dict(source_group='SIMULATION', station_code='SIM-STATION',
        item_code=test['scope']['variable_code'], physical_sensor_id='SIM-SENSOR'))
    channel = classify_channel(stats, cutoff, evidence=evidence)
    operation = aggregate_station('SIM-STATION', [channel], cutoff, evidence=evidence)
    fit_result = fit_analysis(fit, protocol)
    ai_report = analyze_series(test, fit_result['artifact']) if fit_result['status'] == 'FITTED' else fit_result
    rule_report = execute_rules(qcrows, specs, dict(as_of=test['as_of'], executed_at=test['as_of']))
    scope = dict(test['scope'], period_start=test['rows'][0]['timestamp'], period_end=test['as_of'], as_of=test['as_of'])
    extra = []
    for category, source_kind in [('METADATA', 'SOURCE_CONTRACT'), ('OPERATION', 'OPERATION_LOG'), ('RAG', 'DOCUMENT_CHUNK')]:
        extra.append(dict(category=category, source_kind=source_kind, source_id='SIM-'+category,
            source_sha256=digest(dict(source='SIMULATION', category=category, scenario=scenario_id)), locator='SIMULATION:'+category,
            scope=test['scope'], event_at=test['rows'][0]['timestamp'], available_at=test['rows'][0]['timestamp'],
            assessment='CONTEXT', support_strength=0, result_status='EVALUATED', provenance={'source': 'SIMULATION'}))
    fusion, gate = _gate(scope, rule_report, ai_report, extra)
    rc = Counter(row['evaluation_status'] for row in rule_report['results'])
    ac = Counter(row['result_status'] for row in ai_report.get('results', []))
    modes = {mode: dict(evaluated_count=sum(r['mode'] == mode and r['result_status'] == 'EVALUATED' for r in ai_report.get('results', [])),
        anomaly_count=sum(r['mode'] == mode and r['assessment'] == 'ANOMALY' for r in ai_report.get('results', []))) for mode in protocol['modes']}
    checks = [dict(name='OPERATION_EXPECTATION', passed=operation['state'] == selected[3], detail=selected[3]),
        dict(name='QC_ACTUAL_ENGINE', passed=rc['EVALUATED'] > 0, detail='6 applicable configured tests; other guide tests require separate quantities/baselines'),
        dict(name='AI_HELD_OUT_ENGINE', passed=ac['EVALUATED'] > 0, detail='train/calibration/test source rows are disjoint'),
        dict(name='ALL_FUSION_CATEGORIES', passed=not fusion['missing_categories'], detail='Rule/AI/Metadata/Operation/RAG simulation evidence'),
        dict(name='PRODUCTION_WRITES_ZERO', passed=gate['production_writes'] == 0, detail='real DB and source files are never opened by this simulation')]
    checks.extend(dict(name=key.upper(), passed=bool(gate[key]), detail='actual workflow service, isolated actors/DB') for key in (
        'pending_stopped', 'unapproved_resume_blocked', 'reviewer_required', 'rejected_resume_blocked', 'resumed_once', 'stale_revision_blocked'))
    target = {'spike': 'SPIKE', 'temp_drift': 'DRIFT', 'sal_drift': 'DRIFT', 'persistence': 'PERSISTENCE', 'biofouling': 'BIOFOULING_CANDIDATE', 'tide_residual': 'TIDE_RESIDUAL'}.get(scenario_id)
    if target: checks.append(dict(name='INJECTED_AI_SIGNAL', passed=modes[target]['anomaly_count'] > 0, detail=target))
    result = dict(schema_version=VERSION, source='SIMULATION', is_simulation=True, approved=False, production_completed=False,
        scenario_id=scenario_id, label=selected[1], as_of_day=as_of_day, as_of_time=as_of_time, cutoff_native=str(cutoff),
        clock_basis='EXPLICIT_SYNTHETIC_UTC_NOT_REAL_SOURCE_TIMEZONE', rows=raw[-240:], operation=operation,
        quality_pipeline=dict(rule=dict(status='EVALUATED' if rc['EVALUATED'] else 'NOT_EVALUATED', evaluated_count=rc['EVALUATED'],
            anomaly_count=sum(r['result_flag'] in {'3', '4'} for r in rule_report['results']), not_evaluated_count=rc['NOT_EVALUATED'], kinds=[s['kind'] for s in specs], result_sha256=rule_report['result_sha256']),
            ai=dict(status='EVALUATED' if ac['EVALUATED'] else 'NOT_EVALUATED', evaluated_count=ac['EVALUATED'], anomaly_count=sum(r['assessment'] == 'ANOMALY' for r in ai_report.get('results', [])), modes=modes, not_evaluated_count=ac['NOT_EVALUATED'], artifact_sha256=ai_report.get('artifact_sha256'), result_sha256=ai_report.get('result_sha256')),
            fusion={key: fusion[key] for key in ('status', 'recommendation', 'recommendation_score', 'missing_categories', 'score_kind', 'coverage_weight')}, workflow=gate),
        assertions=checks, all_checks_passed=all(check['passed'] for check in checks))
    result['result_sha256'] = digest(result)
    return result
