"""Ephemeral AI experiments on generated data; no DB, live source or queue calls.

The fitted causal anomaly engine and numeric Ridge helper are reused. The
synthetic contracts and labels have no operational source/approval authority.
"""
from collections import Counter, defaultdict
from copy import deepcopy
from datetime import datetime, timedelta
from functools import lru_cache
import re
import secrets
import hashlib
from threading import RLock
import time

import numpy as np
from app.ml.anomaly_artifact import sha256
from app.services.anomaly_analysis import fit_analysis, analyze_series
from app.services.raw_model_comparison import _fit_model, _predict, _metrics

VERSION = 'AI_INSIGHTS_SYNTHETIC_V1'
START = datetime.fromisoformat('2026-06-01T00:00:00+09:00')
VALIDATION_START = datetime.fromisoformat('2026-06-21T00:00:00+09:00')
TEST_START = datetime.fromisoformat('2026-06-28T00:00:00+09:00')
AS_OF = datetime.fromisoformat('2026-07-09T15:41:20+09:00')
END = datetime.fromisoformat('2026-07-09T16:00:00+09:00')
TTL_SECONDS, BOOTSTRAP_TTL_SECONDS = 14400, 300
MAX_SESSIONS, MAX_BOOTSTRAPS, MAX_ACTIONS = 64, 256, 128
KEY = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._:-]{7,127}$')
SCENARIOS = (
    ('normal', '정상 변동', 'TEMP', 'WATER_TEMP', 'degree_C', 34.2, 126.2),
    ('high-temp-neighbor', '고수온 · 인접 센서 동반 상승', 'TEMP', 'WATER_TEMP', 'degree_C', 34.6, 127.2),
    ('spike', '센서 Spike 후보', 'TEMP', 'WATER_TEMP', 'degree_C', 35.1, 129.4),
    ('salinity-drift', '염분 Drift 후보', 'SAL', 'SALINITY', 'psu', 36.1, 125.6),
)
_LOCK, _BOOTSTRAPS, _SESSIONS, _CREATES = RLock(), {}, {}, {}


class SampleError(ValueError):
    def __init__(self, code, status=409):
        self.code, self.status = code, status
        super().__init__(code)


def markers():
    return dict(source='SAMPLE', is_sample=True, approved=False,
        production_eligible=False, transient=True, operational_writes=0,
        model_registry_writes=0, final_qc_writes=0, source_reads=0,
        operational_model_count=0, training_queue_writes=0, restart_erases_state=True)


def window():
    return dict(start=START.isoformat(), end_exclusive=END.isoformat(), as_of=AS_OF.isoformat(),
        latest_observation='2026-07-09T15:00:00+09:00', cadence_seconds=3600,
        effective_as_of=AS_OF.isoformat(),end_boundary_note='16:00 IS THE NEXT_HOURLY_GRID_BOUNDARY; NO_OBSERVATION_AFTER_AS_OF_IS_GENERATED',
        clock_basis='EXPLICIT_SYNTHETIC_OFFSET',
        periods=dict(TRAIN=dict(start=START.isoformat(), end=VALIDATION_START.isoformat()),
                     VALIDATION=dict(start=VALIDATION_START.isoformat(), end=TEST_START.isoformat()),
                     TEST=dict(start=TEST_START.isoformat(), end=END.isoformat())))


def definition():
    return dict(version=VERSION, window=window(), generator='NUMPY_DEFAULT_RNG_20260709_PLUS_CASE_INDEX',
        base_temperature='22 + .8*sin(index*.3) + .4*sin(index*.075)',
        base_salinity='33 + .25*sin(index*.3) + .1*sin(index*.075)', primary_noise_sd=.015,
        reference_noise_sd=.008, high_temperature_ramp_hours=36, high_temperature_rise=6,
        spike_test_indices=[80, 160, 240, 276], spike_increase=5,
        drift_start_test_index=200, drift_per_hour=.035, modes=['SPIKE','DRIFT'],
        lag_samples=3, ridge_alphas=[.01, .1, 1.], calibration_quantile=.99,
        anomaly_window_samples=8, thresholds_authority='DECLARED_SYNTHETIC_EXPERIMENT_POLICY',
        environmental_temperature_threshold=26., environmental_max_paired_difference=.25,
        synthetic_units_known=True, real_source_facts_confirmed=False)


def _seal(packet):
    packet.pop('result_sha256', None)
    packet['result_sha256'] = sha256(packet)
    return packet


def _split(timestamp):
    return 'TRAIN' if timestamp < VALIDATION_START else 'VALIDATION' if timestamp < TEST_START else 'TEST'


def scenario_inputs(scenario_id):
    """Deterministic generated inputs, useful for independent test oracles."""
    chosen = next((r for r in SCENARIOS if r[0] == scenario_id), None)
    if chosen is None:
        raise SampleError('AI_SAMPLE_SCENARIO_NOT_FOUND', 404)
    _, title, family, variable, unit, lat, lon = chosen
    index = next(i for i, r in enumerate(SCENARIOS) if r[0] == scenario_id)
    rng = np.random.default_rng(20260709+index)
    station = 'AI-SAMPLE-'+str(index+1)
    scope = dict(station_id=station, sensor_id=station+'-PRIMARY',
        sensor_episode_id=station+'-EPISODE', variable_code=variable, unit=unit)
    evidence = [dict(sha256=sha256(definition()), locator='SAMPLE:GENERATED_DEFINITION:'+VERSION)]
    facts = {key:dict(documented=True, value=value, evidence=evidence,
        start=(START-timedelta(hours=1)).isoformat(), end=(END+timedelta(hours=1)).isoformat(),
        available_at=(START-timedelta(hours=1)).isoformat()) for key, value in {
        'semantic':variable, 'unit':unit, 'clock':'UTC_WITH_EXPLICIT_OFFSET',
        'qc':'SYNTHETIC_DECLARED_USABLE_NO_REAL_QC_AUTHORITY', 'sensor_episode':scope['sensor_episode_id']}.items()}
    facts['semantic']['variable_family'] = family
    facts['sensor_episode']['physical_sensor_id'] = scope['sensor_id']
    reference_contract = dict(kind='INDEPENDENT_SENSOR', unit=unit, station_id=station,
        variable_code=variable, sensor_id=station+'-INDEPENDENT-NEIGHBOR',
        sensor_episode_id=station+'-REFERENCE-EPISODE', evidence=evidence,
        effective_start=(START-timedelta(hours=1)).isoformat(), effective_end=(END+timedelta(hours=1)).isoformat(),
        qc_version='SYNTHETIC_REFERENCE_QC', qc_effective_start=(START-timedelta(hours=1)).isoformat(),
        qc_effective_end=(END+timedelta(hours=1)).isoformat())
    source_sha = sha256(dict(definition=definition(), scenario_id=scenario_id, channel='primary'))
    reference_sha = sha256(dict(definition=definition(), scenario_id=scenario_id, channel='independent_reference'))
    rows, labels = [], {}
    count = int((END-START).total_seconds()//3600)
    for i in range(count):
        timestamp = START+timedelta(hours=i)
        base = (22+.8*np.sin(i*.3)+.4*np.sin(i*.075)) if family=='TEMP' else (33+.25*np.sin(i*.3)+.1*np.sin(i*.075))
        primary, ref = float(base+rng.normal(0,.015)), float(base+rng.normal(0,.008))
        local = int((timestamp-TEST_START).total_seconds()//3600)
        label, environment = False, False
        if timestamp >= TEST_START:
            if scenario_id == 'high-temp-neighbor':
                rise = 6*max(0., min(1., (local-(280-36))/36))
                primary += rise; ref += rise; environment = rise > 0
            elif scenario_id == 'spike':
                if local in definition()['spike_test_indices']:
                    primary += 5
                label = local in definition()['spike_test_indices'] or local-1 in definition()['spike_test_indices']
            elif scenario_id == 'salinity-drift':
                drift = max(0., local-200)*.035
                primary += drift; label = drift > 0
        row_id = scenario_id+':'+str(i).zfill(4)
        labels[row_id] = dict(sensor_deviation=label, environmental_change=environment,
            truth_authority='EXPLICIT_SYNTHETIC_INJECTION_NOT_HUMAN_QC')
        stamp = timestamp.isoformat()
        rows.append(dict(row_id=row_id, timestamp=stamp, available_at=stamp, qc_available_at=stamp,
            scope=scope, value=primary, qc_eligible=True,
            source=dict(sha256=source_sha, locator='SAMPLE:primary:'+row_id),
            reference=dict(value=ref, timestamp=stamp, available_at=stamp, qc_available_at=stamp,
                unit=unit, station_id=station, variable_code=variable, sensor_id=reference_contract['sensor_id'],
                sensor_episode_id=reference_contract['sensor_episode_id'], qc_eligible=True,
                source=dict(sha256=reference_sha, locator='SAMPLE:reference:'+row_id))))
    base = dict(schema_version='ocean-anomaly-series-1', scope=scope, facts=facts,
        reference_contract=reference_contract, candidate_context={})
    membership = {s:[r['row_id'] for r in rows if _split(datetime.fromisoformat(r['timestamp']))==s]
                  for s in ('TRAIN','VALIDATION','TEST')}
    protocol = dict(schema_version='ocean-anomaly-protocol-1', protocol_id='AI-SAMPLE-'+scenario_id,
        version=VERSION, variable_family=family, modes=['SPIKE','DRIFT'], cadence_seconds=3600,
        window_samples=8, min_train_samples=100, min_calibration_samples=100, scale_floor=.01,
        persistence_epsilon=.001, calibration_quantile=.99,
        periods=dict(TRAIN=window()['periods']['TRAIN'], CALIBRATION=window()['periods']['VALIDATION']),
        membership_sha256=dict(TRAIN=sha256(sorted(membership['TRAIN'])), CALIBRATION=sha256(sorted(membership['VALIDATION']))))
    test_ids=set(membership['TEST'])
    fit = dict(base, as_of=TEST_START.isoformat(), rows=[r for r in rows if r['row_id'] not in test_ids])
    test = dict(base, as_of=AS_OF.isoformat(), rows=[r for r in rows if r['row_id'] in test_ids])
    return dict(scenario_id=scenario_id, title=title, family=family, variable_code=variable, unit=unit,
        lat=lat, lon=lon, scope=scope, rows=rows, labels=labels, membership=membership,
        fit=fit, test=test, protocol=protocol)


def forecast_comparison(rows, membership):
    """Reuse the numeric TRAIN-only Ridge implementation on split-local pairs."""
    if set(membership) != {'TRAIN','VALIDATION','TEST'} or sum(membership.values(), []) != [r['row_id'] for r in rows]:
        raise SampleError('AI_SAMPLE_FIXED_MEMBERSHIP_INVALID')
    if len({r['row_id'] for r in rows}) != len(rows):
        raise SampleError('AI_SAMPLE_DUPLICATE_MEMBERSHIP')
    lookup = {r['row_id']:r for r in rows}
    pairs = {}
    for split, ids in membership.items():
        selected = []
        for j in range(3, len(ids)):
            block = [lookup[rid] for rid in ids[j-3:j+1]]
            times = [datetime.fromisoformat(r['timestamp']) for r in block]
            if any((right-left).total_seconds()!=3600 for left,right in zip(times,times[1:])):
                raise SampleError('AI_SAMPLE_CAUSAL_CADENCE_INVALID')
            if any(t.tzinfo is None or _split(t)!=split or t>AS_OF for t in times):
                raise SampleError('AI_SAMPLE_SPLIT_OR_ASOF_INVALID')
            selected.append(dict(origin_id=block[-2]['row_id'], target_id=block[-1]['row_id'],
                feature_row_ids=[r['row_id'] for r in block[:-1]], x=[r['value'] for r in block[:-1]],
                target=block[-1]['value'], persistence=block[-2]['value']))
        if len(selected)<100:
            raise SampleError('AI_SAMPLE_MINIMUM_COMMON_PAIRS_REQUIRED')
        pairs[split] = selected
    train, validation = pairs['TRAIN'], pairs['VALIDATION']
    x=np.asarray([r['x'] for r in train]); y=np.asarray([r['target'] for r in train])
    vx=np.asarray([r['x'] for r in validation]); vy=np.asarray([r['target'] for r in validation])
    candidates=[]; models={}
    for alpha in definition()['ridge_alphas']:
        model=_fit_model(x,y,alpha); models[alpha]=model
        candidates.append(dict(candidate='RIDGE', alpha=alpha, preprocessing_fit='TRAIN_ONLY',
            parameters_fit='TRAIN_ONLY', validation_metrics=_metrics(vy,_predict(model,vx))))
    best=min(candidates,key=lambda r:(r['validation_metrics']['mae'],r['alpha']))
    persistence=_metrics(vy,[r['persistence'] for r in validation])
    selected='RIDGE' if best['validation_metrics']['mae']<persistence['mae'] else 'PERSISTENCE'
    test=pairs['TEST']; predicted=_predict(models[best['alpha']],[r['x'] for r in test])
    validation_metrics=dict(RIDGE=best['validation_metrics'], PERSISTENCE=persistence)
    test_metrics=dict(RIDGE=_metrics([r['target'] for r in test],predicted),
                      PERSISTENCE=_metrics([r['target'] for r in test],[r['persistence'] for r in test]))
    artifact=dict(schema_version='ai-sample-forecast-artifact-1', **markers(),
        selected_model=selected, ridge_model=models[best['alpha']],
        candidates=candidates, selection='VALIDATION_MAE_ONLY_TEST_NOT_USED',
        training_data_sha256=sha256([lookup[rid] for rid in membership['TRAIN']]),
        membership_sha256=sha256(membership), pair_membership_sha256={s:sha256([
            {k:r[k] for k in ('origin_id','target_id','feature_row_ids')} for r in pairs[s]]) for s in pairs},
        preprocessing_fit='TRAIN_ONLY', parameters_fit='TRAIN_ONLY', refit_after_selection=False,
        lag_samples=3, horizon_seconds=3600, horizon_authority='DECLARED_SYNTHETIC_HOURLY_CONTRACT')
    paired=[dict(row, ridge=float(value), selected_prediction=float(value) if selected=='RIDGE' else row['persistence'])
            for row,value in zip(test,predicted)]
    return dict(status='TRAINED_DEVELOPMENT_BASELINE',selected_model=selected,
        selected_alpha=best['alpha'], candidates=[dict(candidate='PERSISTENCE', learned_parameters=False, validation_metrics=persistence)]+candidates,
        split_counts={s:len(ids) for s,ids in membership.items()}, pair_counts={s:len(pairs[s]) for s in pairs},
        excluded_warmup_per_split=3, validation_metrics=validation_metrics, test_metrics=test_metrics,
        prediction_next=float(_predict(models[best['alpha']],[[r['value'] for r in rows[-3:]]])[0]) if selected=='RIDGE' else rows[-1]['value'],
        horizon_seconds=3600, artifact=artifact, artifact_sha256=sha256(artifact), paired_test_predictions=paired)


def _confusion(truth, predicted):
    tp=sum(t and p for t,p in zip(truth,predicted));fp=sum(not t and p for t,p in zip(truth,predicted))
    fn=sum(t and not p for t,p in zip(truth,predicted));tn=sum(not t and not p for t,p in zip(truth,predicted))
    return dict(tp=tp,fp=fp,fn=fn,tn=tn,evaluated_count=len(truth),
        precision=tp/(tp+fp) if tp+fp else None, recall=tp/(tp+fn) if tp+fn else None,
        false_positive_rate=fp/(fp+tn) if fp+tn else None,
        false_negative_rate=fn/(tp+fn) if tp+fn else None,
        definition='ANY_SPIKE_OR_DRIFT_WHEN_BOTH_EVALUATED_VS_SENSOR_DEVIATION_INJECTION_LABEL; ENVIRONMENTAL_RISE_IS_NOT_SENSOR_FAULT_TRUTH')


def calculate_scenario(inputs):
    fitted=fit_analysis(inputs['fit'],inputs['protocol'])
    if fitted.get('status')!='FITTED' or fitted.get('blockers'):
        raise SampleError('AI_SAMPLE_FIT_NOT_EVALUATED')
    report=analyze_series(inputs['test'],fitted['artifact'])
    if report.get('status')!='ANALYSIS_ONLY':
        raise SampleError('AI_SAMPLE_ANALYSIS_NOT_EVALUATED')
    forecast=forecast_comparison(inputs['rows'],inputs['membership'])
    forecast.update(prediction_origin_timestamp=inputs['rows'][-1]['timestamp'],
        prediction_target_timestamp=(datetime.fromisoformat(inputs['rows'][-1]['timestamp'])+timedelta(hours=1)).isoformat(),
        prediction_is_observation=False,prediction_kind='FUTURE_SYNTHETIC_HOURLY_FORECAST_NOT_OBSERVED')
    by_id=defaultdict(list)
    for result in report['results']: by_id[result['row_id']].append(result)
    prediction_by_id={r['target_id']:r for r in forecast['paired_test_predictions']}
    display=[];truth=[];predictions=[]
    for row in inputs['test']['rows']:
        results=by_id[row['row_id']];evaluated=all(r['result_status']=='EVALUATED' for r in results)
        triggered=any(r['assessment']=='ANOMALY' for r in results)
        ranks=[r['calibration_rank'] for r in results if r['calibration_rank'] is not None]
        label=inputs['labels'][row['row_id']]
        if evaluated:
            truth.append(label['sensor_deviation']); predictions.append(triggered)
        pair=prediction_by_id.get(row['row_id'])
        display.append(dict(row_id=row['row_id'],timestamp=row['timestamp'],value=row['value'],
            reference_value=row['reference']['value'], injection_label=label['sensor_deviation'],
            environmental_injection=label['environmental_change'], split='TEST',
            prediction=None if pair is None else pair['selected_prediction'],
            prediction_origin_id=None if pair is None else pair['origin_id'],
            anomaly_score=max((r['score'] for r in results if r['score'] is not None),default=None),
            calibration_rank=max(ranks,default=None),
            assessment='NOT_EVALUATED' if not evaluated else 'ANOMALY' if triggered else 'NORMAL',
            modes=results))
    scenario_id=inputs['scenario_id']; target=display[-1]
    if scenario_id=='spike':target=next(r for r in reversed(display) if r['injection_label'])
    last=display[-1]
    environment=dict(status='NOT_APPLICABLE',reason='TEMPERATURE_ONLY_SYNTHETIC_CONDITION',candidate=False)
    if inputs['family']=='TEMP':
        environment=dict(status='EVALUATED',candidate=last['value']>=26. and last['reference_value']>=26.
            and abs(last['value']-last['reference_value'])<=.25,
            primary_value=last['value'],neighbor_value=last['reference_value'],unit=inputs['unit'],
            temperature_threshold=26.,max_paired_difference=.25,
            policy_authority='DECLARED_SYNTHETIC_CONDITION_NOT_OPERATIONAL_WARNING_THRESHOLD',
            cause_attribution='NOT_ESTABLISHED',neighbor_sensor_id=inputs['fit']['reference_contract']['sensor_id'])
    if environment['candidate']:
        assessment='ENVIRONMENTAL_CHANGE_CANDIDATE';severity='WATCH'
    elif target['assessment']=='ANOMALY':
        assessment='SENSOR_DEVIATION_CANDIDATE';severity='ALERT'
    else:assessment='NORMAL_SAMPLE';severity='NORMAL'
    evaluation=_confusion(truth,predictions)
    facts=dict(sample_definition_sha256=sha256(definition()), input_sha256=sha256(inputs['rows']),
        injection_labels_sha256=sha256(inputs['labels']), source_contract_sha256=sha256(inputs['fit']['facts']),
        anomaly_artifact_sha256=fitted['artifact']['sha256'], anomaly_report_sha256=report['result_sha256'],
        forecast_artifact_sha256=forecast['artifact_sha256'], membership_sha256=sha256(inputs['membership']))
    evidence=[dict(kind=kind,source='SAMPLE',sha256=digest,label=kind.replace('_',' '),
                   authority='SYNTHETIC_DEVELOPMENT_ONLY') for kind,digest in facts.items()]
    explanations=[
        '시간 분리 TRAIN 480행 / VALIDATION 168행 / TEST 280행을 고정했습니다.',
        'SPIKE와 DRIFT는 기존 fitted 통계 엔진으로 계산했고 99% calibration quantile은 합성 정책입니다.',
        'Ridge의 전처리·계수는 TRAIN만 사용하고 후보는 VALIDATION MAE로 선정했습니다. TEST로 다시 선정하지 않습니다.',
        '센서 고장 원인은 확정하지 않으며, 점수는 경험적 calibration 순위로 고장 확률이 아닙니다.',
    ]
    if scenario_id=='high-temp-neighbor':explanations.append('주 센서와 독립 인접 센서에 동일한 +6도 ramp를 명시적으로 주입했습니다. 환경 변화 후보와 센서 편차를 구분합니다.')
    if scenario_id=='salinity-drift':explanations.append('TEST 후반 주 센서에 시간당 +0.035 psu를 주입했고 독립 센서에는 주입하지 않았습니다.')
    if scenario_id=='spike':explanations.append('TEST의 80/160/240/276번째 값에 +5도를 주입했습니다. 다음 정상 복귀도 Spike transition 정답에 포함합니다.')
    recommendation=dict(action='REVIEW_SYNTHETIC_EVIDENCE', cause_attribution='NOT_ESTABLISHED',
        description='샘플 근거 검토 후 별도 재개로 분석 보고서 초안만 생성합니다.',
        transient_retraining_recommendation=scenario_id in ('spike','salinity-drift'),
        training_queue_writes=0, final_qc_changed=False)
    return dict(scenario_id=scenario_id,title=inputs['title'],station_id=inputs['scope']['station_id'],
        station_name='가상 AI 관측소 '+str(next(i+1 for i,r in enumerate(SCENARIOS) if r[0]==scenario_id)),
        variable_code=inputs['variable_code'],unit=inputs['unit'],lat=inputs['lat'],lon=inputs['lon'],
        virtual=True,assessment=assessment,severity=severity,current_value=display[-1]['value'],
        selected_observation=target['timestamp'], latest_at=display[-1]['timestamp'],
        selected_value=target['value'],selected_prediction=target['prediction'],
        selected_reference_value=target['reference_value'],selected_row_id=target['row_id'],
        score=dict(value=target['calibration_rank'],kind='EMPIRICAL_CALIBRATION_RANK_NOT_PROBABILITY'),
        uncertainty=None,confidence_probability=None,series=display,anomaly_evaluation=evaluation,
        anomaly_evaluated_row_count=evaluation['evaluated_count'],
        not_evaluated_row_count=len(display)-evaluation['evaluated_count'],
        forecast=forecast,evidence=evidence,explanation=explanations,recommendation=recommendation,
        environment_evaluation=environment,
        fitted_anomaly_artifact=fitted['artifact'],anomaly_report=report,
        definition_sha256=sha256(definition()),membership=inputs['membership'],
        injection_labels=inputs['labels'], sample_contract=inputs['fit']['facts'])


@lru_cache(maxsize=1)
def _template():
    return {spec[0]:calculate_scenario(scenario_inputs(spec[0])) for spec in SCENARIOS}


def _key(value):
    if not isinstance(value,str) or not KEY.fullmatch(value):raise SampleError('AI_SAMPLE_REQUEST_KEY_INVALID',422)


def _prune():
    now=time.monotonic()
    for store in (_BOOTSTRAPS,_SESSIONS):
        for key in list(store):
            if now>=store[key]['expires']:del store[key]
    for key in list(_CREATES):
        if key[0] not in _BOOTSTRAPS or _CREATES[key]['session_id'] not in _SESSIONS:del _CREATES[key]


def context():
    with _LOCK:
        _prune()
        if len(_BOOTSTRAPS)>=MAX_BOOTSTRAPS:raise SampleError('AI_SAMPLE_BOOTSTRAP_CAPACITY_REACHED',429)
        token='ai-sample-bootstrap-'+secrets.token_urlsafe(32)
        _BOOTSTRAPS[sha256(token)]=dict(expires=time.monotonic()+BOOTSTRAP_TTL_SECONDS)
    return _seal(dict(schema_version='ai-sample-context-1',**markers(),bootstrap_token=token,
        bootstrap_expires_in_seconds=BOOTSTRAP_TTL_SECONDS,expires_in_seconds=TTL_SECONDS,
        fixed_clock=AS_OF.isoformat(),window=window(),sample_definition_version=VERSION,
        sample_definition_sha256=sha256(definition()),
        scenario_catalog=[dict(scenario_id=r[0],title=r[1],variable_code=r[3],unit=r[4]) for r in SCENARIOS],
        capabilities=dict(trained_development_baseline=True,production_training=False,operational_identity=False,
                          approve_sample_review=True,resume_sample_report=True)))


def _cases(generation,session_id):
    cases={}
    for key,template in _template().items():
        cases[key]=dict(scenario_id=key,revision=1,
            recommendation_sha256=sha256(dict(session_id=session_id,generation=generation,scenario_id=key,
                recommendation=template['recommendation'],evidence=template['evidence'])),
            workflow=dict(status='PENDING',blocked=True,downstream_executed=False,report_status='BLOCKED',
                approved=False,history=[dict(sequence=1,action='CREATE',from_state=None,to_state='PENDING',
                    actor='SAMPLE_ENGINE',sample_clock=AS_OF.isoformat(),comment='샘플 검토 대기 · 후속 단계 정지')]))
    return cases


def _session(token,session_id):
    _prune();session=_SESSIONS.get(session_id)
    if session is None or not isinstance(token,str) or not token.isascii() or len(token)>200 or not secrets.compare_digest(token,session['token']):
        raise SampleError('AI_SAMPLE_SESSION_NOT_FOUND_OR_TOKEN_INVALID',401)
    return session


def _session_packet(session,replay=False):
    return _seal(dict(schema_version='ai-sample-session-1',**markers(),session_id=session['id'],
        session_token=session['token'],session_revision=session['revision'],generation=session['generation'],
        window=window(),expires_in_seconds=TTL_SECONDS,idempotent_replay=replay))


def create_session(token,request_key):
    _key(request_key)
    if not isinstance(token,str) or not token.startswith('ai-sample-bootstrap-') or len(token)>200:
        raise SampleError('AI_SAMPLE_BOOTSTRAP_TOKEN_REQUIRED',401)
    with _LOCK:
        _prune();identity=sha256(token)
        if identity not in _BOOTSTRAPS:raise SampleError('AI_SAMPLE_BOOTSTRAP_TOKEN_EXPIRED_OR_INVALID',401)
        key=(identity,request_key)
        if key in _CREATES:
            packet=deepcopy(_CREATES[key]['packet']);packet['idempotent_replay']=True;return _seal(packet)
        if len(_SESSIONS)>=MAX_SESSIONS:raise SampleError('AI_SAMPLE_SESSION_CAPACITY_REACHED',429)
        session_id='ai-sample-session-'+secrets.token_urlsafe(18)
        session=dict(id=session_id,token='ai-sample-token-'+secrets.token_urlsafe(32),revision=1,generation=1,
            expires=time.monotonic()+TTL_SECONDS,cases=_cases(1,session_id),actions={})
        _SESSIONS[session_id]=session
        packet=_session_packet(session);_CREATES[key]=dict(session_id=session_id,packet=deepcopy(packet))
        return packet


def _workflow(case):
    workflow=deepcopy(case['workflow']);state=workflow['status']
    workflow['capabilities']=dict(comment=True,approve=state in ('PENDING','HELD'),
        hold=state in ('PENDING','APPROVED'),reject=state in ('PENDING','HELD','APPROVED'),resume=state=='APPROVED')
    workflow.update(revision=case['revision'],recommendation_sha256=case['recommendation_sha256'])
    return workflow


def _summary(case):
    template=_template()[case['scenario_id']]
    keys=('scenario_id','title','station_id','station_name','variable_code','unit','lat','lon','virtual',
          'assessment','severity','current_value','selected_observation','latest_at','score','uncertainty',
          'selected_value','selected_prediction','selected_reference_value','selected_row_id',
          'confidence_probability','anomaly_evaluated_row_count','not_evaluated_row_count')
    return dict({key:deepcopy(template[key]) for key in keys},revision=case['revision'],
        recommendation_sha256=case['recommendation_sha256'],workflow_status=case['workflow']['status'],
        report_status=case['workflow']['report_status'],selected_forecast=template['forecast']['selected_model'],
        forecast_validation_metrics=deepcopy(template['forecast']['validation_metrics']),
        forecast_test_metrics=deepcopy(template['forecast']['test_metrics']))


def overview(token,session_id):
    with _LOCK:
        session=_session(token,session_id);cases=list(session['cases'].values());rows=[_summary(c) for c in cases]
        templates=list(_template().values())
        kpis=dict(virtual_station_count=len(rows),case_count=len(rows),analysis_report_count=len(templates),
            review_report_ready_count=sum(c['workflow']['report_status']=='READY' for c in cases),
            evaluated_test_rows=sum(t['anomaly_evaluated_row_count'] for t in templates),
            test_rows=sum(len(t['series']) for t in templates),
            anomaly_count=sum(r['assessment']=='ANOMALY' for t in templates for r in t['series']),
            forecast_model_count=len(templates),fitted_ridge_model_count=sum(len(definition()['ridge_alphas']) for _ in templates),
            fitted_anomaly_modes_count=sum(sum(m['status']=='FITTED' for m in t['fitted_anomaly_artifact']['artifact']['models'].values()) for t in templates),
            operational_model_count=0,pending_review_count=sum(c['workflow']['status']=='PENDING' for c in cases),
            retraining_candidate_count=sum(bool(t['recommendation']['transient_retraining_recommendation']) for t in templates),
            case_denominator_basis='FOUR_REPRESENTATIVE_SYNTHETIC_SCENARIOS',
            row_denominator_basis='TEST_ROWS_PER_CASE; NO_TEMPERATURE_SALINITY_VALUE_POOLING')
        stations=[dict(station_id=r['station_id'],station_name=r['station_name'],lat=r['lat'],lon=r['lon'],
            virtual=True,scenario_id=r['scenario_id'],variable_code=r['variable_code'],unit=r['unit'],
            current_value=r['current_value'],status=r['assessment']) for r in rows]
        return _seal(dict(schema_version='ai-sample-overview-1',**markers(),session_id=session['id'],
            session_revision=session['revision'],generation=session['generation'],window=window(),
            kpis=kpis,stations=stations,scenarios=rows,
            algorithm_catalog=[dict(name='TRAIN_ONLY_STANDARDIZED_RIDGE',status='FITTED',candidate_alphas=definition()['ridge_alphas']),
                dict(name='PERSISTENCE',status='COMPUTED_BASELINE',learned_parameters=False),
                dict(name='CAUSAL_ROBUST_SPIKE_AND_PAIRED_REFERENCE_DRIFT',status='FITTED_AND_CALIBRATED'),
                dict(name='LSTM/XGBoost/Transformer',status='NOT_IMPLEMENTED_IN_THIS_SAMPLE',trained=False)],
            limitations=['합성 계약·정답으로만 평가합니다. 실제 원천·QC·운영 모델의 성과가 아닙니다.',
                '경험적 calibration 순위는 신뢰확률이 아닙니다. 장비 고장 원인은 확정하지 않습니다.',
                '분석 계산보고서 4개와 승인·재개 뒤 생성하는 검토보고서 수를 분리합니다.']))


def _case(session,scenario_id):
    case=session['cases'].get(scenario_id)
    if case is None:raise SampleError('AI_SAMPLE_SCENARIO_NOT_FOUND',404)
    return case


def detail(token,session_id,scenario_id):
    with _LOCK:
        session=_session(token,session_id);case=_case(session,scenario_id);template=_template()[scenario_id]
        return _seal(dict(schema_version='ai-sample-detail-1',**markers(),session_id=session_id,
            session_revision=session['revision'],generation=session['generation'],window=window(),
            scenario=_summary(case),revision=case['revision'],recommendation_sha256=case['recommendation_sha256'],
            series=deepcopy(template['series']),anomaly_evaluation=deepcopy(template['anomaly_evaluation']),
            forecast=deepcopy(template['forecast']),evidence=deepcopy(template['evidence']),
            environment_evaluation=deepcopy(template['environment_evaluation']),
            explanation=deepcopy(template['explanation']),recommendation=deepcopy(template['recommendation']),
            workflow=_workflow(case),sample_contract=deepcopy(template['sample_contract']),
            injection_labels_sha256=sha256(template['injection_labels']),membership_sha256=sha256(template['membership']),
            anomaly_artifact_sha256=template['fitted_anomaly_artifact']['sha256'],
            anomaly_report_sha256=template['anomaly_report']['result_sha256']))


def _replay(session,key,fingerprint):
    stored=session['actions'].get(key)
    if stored is not None:
        if stored['fingerprint']!=fingerprint:raise SampleError('AI_SAMPLE_IDEMPOTENCY_KEY_REUSED')
        packet=deepcopy(stored['packet']);packet['idempotent_replay']=True;return _seal(packet)
    if len(session['actions'])>=MAX_ACTIONS:raise SampleError('AI_SAMPLE_ACTION_CAPACITY_REACHED',429)
    return None


def review(token,session_id,scenario_id,action,comment,expected_revision,recommendation_sha256,request_key):
    _key(request_key)
    if action not in ('COMMENT','APPROVE','HOLD','REJECT','RESUME'):raise SampleError('AI_SAMPLE_ACTION_INVALID',422)
    if not isinstance(comment,str) or not comment.strip() or len(comment)>2000:raise SampleError('AI_SAMPLE_COMMENT_REQUIRED',422)
    fingerprint=sha256(dict(scenario_id=scenario_id,action=action,comment=comment,
                           expected_revision=expected_revision,recommendation_sha256=recommendation_sha256))
    with _LOCK:
        session=_session(token,session_id);case=_case(session,scenario_id)
        replay=_replay(session,request_key,fingerprint)
        if replay is not None:return replay
        if type(expected_revision) is not int or expected_revision!=case['revision']:raise SampleError('AI_SAMPLE_STALE_REVISION')
        if recommendation_sha256!=case['recommendation_sha256']:raise SampleError('AI_SAMPLE_RECOMMENDATION_CHANGED')
        state=case['workflow']['status']
        allowed=dict(COMMENT=True,APPROVE=state in ('PENDING','HELD'),HOLD=state in ('PENDING','APPROVED'),
                     REJECT=state in ('PENDING','HELD','APPROVED'),RESUME=state=='APPROVED')
        if not allowed[action]:raise SampleError('AI_SAMPLE_WORKFLOW_GATE_BLOCKED')
        target=dict(COMMENT=state,APPROVE='APPROVED',HOLD='HELD',REJECT='REJECTED',RESUME='COMPLETED')[action]
        history=case['workflow']['history']
        history.append(dict(sequence=len(history)+1,action=action,from_state=state,to_state=target,
            comment=comment.strip(),actor='SAMPLE_REVIEWER_NOT_OPERATIONAL_IDENTITY',sample_clock=AS_OF.isoformat()))
        case['workflow'].update(status=target,blocked=target!='COMPLETED',downstream_executed=target=='COMPLETED',
                                report_status='READY' if target=='COMPLETED' else 'BLOCKED')
        case['revision']+=1;session['revision']+=1
        packet=_seal(dict(schema_version='ai-sample-review-1',**markers(),session_id=session_id,
            session_revision=session['revision'],generation=session['generation'],scenario=_summary(case),
            revision=case['revision'],recommendation_sha256=case['recommendation_sha256'],
            workflow=_workflow(case),idempotent_replay=False))
        session['actions'][request_key]=dict(fingerprint=fingerprint,packet=deepcopy(packet))
        return packet


def report(token,session_id,scenario_id):
    with _LOCK:
        session=_session(token,session_id);case=_case(session,scenario_id)
        if case['workflow']['status']!='COMPLETED' or case['workflow']['report_status']!='READY':
            raise SampleError('AI_SAMPLE_REPORT_REQUIRES_APPROVAL_AND_EXPLICIT_RESUME')
        template=_template()[scenario_id]
        structured=dict(schema_version='ai-sample-report-1',**markers(),scenario=_summary(case),
            sample_as_of=AS_OF.isoformat(),window=window(),workflow=_workflow(case),
            anomaly_evaluation=deepcopy(template['anomaly_evaluation']),
            validation_metrics=deepcopy(template['forecast']['validation_metrics']),
            test_metrics=deepcopy(template['forecast']['test_metrics']),evidence=deepcopy(template['evidence']),
            explanation=deepcopy(template['explanation']),recommendation=deepcopy(template['recommendation']),
            delivered=False,recipients=[],report_authority='SAMPLE_REVIEW_ONLY_NOT_OPERATIONAL_APPROVAL')
        forecast=template['forecast'];evaluation=template['anomaly_evaluation']
        metric_lines=[]
        for candidate in ('RIDGE','PERSISTENCE'):
            validation=forecast['validation_metrics'][candidate];test=forecast['test_metrics'][candidate]
            metric_lines.append('- '+candidate+': VALIDATION MAE '+format(validation['mae'],'.6f')+
                ', TEST MAE '+format(test['mae'],'.6f')+', RMSE '+format(test['rmse'],'.6f')+
                ' '+template['unit']+' / 공통 TEST '+str(test['count'])+'쌍')
        metric_lines.append('- 이상 검출: TP '+str(evaluation['tp'])+', FP '+str(evaluation['fp'])+
            ', FN '+str(evaluation['fn'])+', TN '+str(evaluation['tn'])+' / '+str(evaluation['evaluated_count'])+'행')
        metric_lines.append('- 정상행 오탐률: '+format(100*evaluation['false_positive_rate'],'.4f')+'%'+
            ' (FP / (FP + TN), 합성 TEST 기준)')
        markdown='\n'.join(['# AI 인사이트 합성 샘플 보고서', '', '**SAMPLE · 운영 미승인 · 실제 발송 없음**',
            '', template['title'], '기준 시각: '+AS_OF.isoformat(),
            '변수: '+template['variable_code']+' / 가상 단위: '+template['unit'],
            '선정된 개발 기준선: '+template['forecast']['selected_model'],
            '시간 분할: TRAIN 480 / VALIDATION 168 / TEST 280행 (각 분할 3행 warmup 제외)',
            'TEST 평가행: '+str(template['anomaly_evaluation']['evaluated_count']),
            '근거 calibration 순위는 확률이 아닙니다. 고장 원인은 확정하지 않습니다.', '',
            *metric_lines, '',
            *('- '+text for text in template['explanation']), '',
            '검토 승인 뒤 명시적 재개를 실행했습니다. 운영 모델 등록·QC·학습 큐 변경은 0입니다.'])
        return _seal(dict(schema_version='ai-sample-report-download-1',**markers(),session_id=session_id,
            session_revision=session['revision'],generation=session['generation'],revision=case['revision'],
            recommendation_sha256=case['recommendation_sha256'],
            scenario_id=scenario_id,format='MARKDOWN',filename='ai-sample-'+scenario_id+'.md',
            markdown=markdown,markdown_sha256=hashlib.sha256(markdown.encode('utf-8')).hexdigest(),
            markdown_hash_kind='UTF8_BYTES_SHA256',report=structured,
            report_sha256=sha256(structured),delivered=False))


def reset(token,session_id,expected_session_revision,request_key):
    _key(request_key);fingerprint=sha256(dict(action='RESET',expected_session_revision=expected_session_revision))
    with _LOCK:
        session=_session(token,session_id);replay=_replay(session,request_key,fingerprint)
        if replay is not None:return replay
        if type(expected_session_revision) is not int or expected_session_revision!=session['revision']:
            raise SampleError('AI_SAMPLE_STALE_SESSION_REVISION')
        session['generation']+=1;session['revision']+=1;session['cases']=_cases(session['generation'],session_id)
        # A reset creates a new review generation. Old success receipts may not
        # authorize or appear to authorize a new generation with the same IDs.
        session['actions'].clear()
        packet=_session_packet(session)
        session['actions'][request_key]=dict(fingerprint=fingerprint,packet=deepcopy(packet))
        return packet


def reset_store_for_tests():
    """No public endpoint; isolated test cleanup only."""
    with _LOCK:
        _BOOTSTRAPS.clear();_SESSIONS.clear();_CREATES.clear()
