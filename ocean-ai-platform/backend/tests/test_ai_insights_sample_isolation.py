"""Independent HTTP, causal and numerical boundaries for disposable AI samples."""
import ast
import hashlib
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4

import numpy as np
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler

from app.core.config import settings
from app.core.database import get_db
from app.core.security import authorize_api, current_actor
from app.ml.anomaly_artifact import sha256
from app.services import ai_insights_sample as sample


def key(label):
    return label + ':' + uuid4().hex


@pytest.fixture
def client(monkeypatch):
    from app.api import routes_agents, routes_ai_insights_sample, routes_qc_sample
    from app.core import database
    from app.services import lake_browser, qc_sample, source_contract_snapshot

    monkeypatch.setattr(settings, 'AI_INSIGHTS_SAMPLE_ENABLED', True)
    monkeypatch.setattr(settings, 'QC_SAMPLE_ENABLED', True)
    monkeypatch.setattr(settings, 'ENVIRONMENT', 'development')
    monkeypatch.setattr(settings, 'API_IDENTITIES', {
        'real-reviewer': {'token': 'isolated-real-operator-ai-test', 'role': 'reviewer'},
    })
    accesses = []

    def operational_bomb(*args, **kwargs):
        accesses.append('OPERATIONAL_ACCESS')
        pytest.fail('AI sample attempted operational SQL/source/ingestion access')

    monkeypatch.setattr(database, 'SessionLocal', operational_bomb)
    monkeypatch.setattr(database.engine, 'connect', operational_bomb)
    monkeypatch.setattr(lake_browser, 'connection', operational_bomb)
    monkeypatch.setattr(lake_browser, 'context', operational_bomb)
    monkeypatch.setattr(source_contract_snapshot, 'ingest_approved_source', operational_bomb)
    monkeypatch.setattr(source_contract_snapshot, 'create_candidate_snapshot', operational_bomb)
    app = FastAPI(dependencies=[Depends(authorize_api)])
    app.include_router(routes_ai_insights_sample.router)
    app.include_router(routes_qc_sample.router)
    app.include_router(routes_agents.router)
    app.dependency_overrides[get_db] = operational_bomb

    @app.get('/api/ai-isolation/actor')
    def actor_identity(actor=Depends(current_actor)):
        return {'user_id': actor.user_id, 'role': actor.role}

    sample.reset_store_for_tests()
    qc_sample.reset_store_for_tests()
    with TestClient(app) as http:
        yield http
    assert accesses == []
    sample.reset_store_for_tests()
    qc_sample.reset_store_for_tests()


def context(client):
    response = client.get('/api/ai-insights-sample/context')
    assert response.status_code == 200, response.text
    assert response.headers['cache-control'] == 'no-store'
    assert response.headers['referrer-policy'] == 'no-referrer'
    return response.json()


def session(client, bootstrap=None, request_key=None):
    response = client.post('/api/ai-insights-sample/sessions',
        headers={'X-AI-Sample-Token': bootstrap or context(client)['bootstrap_token']},
        json={'request_key': request_key or key('create')})
    assert response.status_code in (200, 201), response.text
    return response.json()


def headers(created):
    return {'X-AI-Sample-Token': created['session_token']}


def path(created, suffix):
    return '/api/ai-insights-sample/sessions/' + created['session_id'] + suffix


def overview(client, created):
    response = client.get(path(created, '/overview'), headers=headers(created))
    assert response.status_code == 200, response.text
    return response.json()


def detail(client, created, scenario='spike'):
    response = client.get(path(created, '/scenarios/' + scenario), headers=headers(created))
    assert response.status_code == 200, response.text
    return response.json()


def body(packet, action, request_key=None):
    return {'action': action, 'comment': 'Independent synthetic review only',
        'expected_revision': packet['revision'],
        'recommendation_sha256': packet['recommendation_sha256'],
        'request_key': request_key or key(action)}


def review(client, created, packet, action, payload=None):
    return client.post(path(created, '/scenarios/' + packet['scenario']['scenario_id'] + '/review'),
        headers=headers(created), json=payload or body(packet, action))


def reset(client, created, revision=None, request_key=None):
    return client.post(path(created, '/reset'), headers=headers(created),
        json={'expected_session_revision': revision or overview(client, created)['session_revision'],
            'request_key': request_key or key('reset')})


def replay_business(packet):
    return {k: v for k, v in packet.items() if k not in ('idempotent_replay', 'result_sha256')}


@pytest.mark.parametrize('enabled,environment', [(False, 'development'), (True, 'production'), (True, 'staging')])
def test_disabled_or_nonlocal_hides_all_read_write_and_report_routes(client, monkeypatch, enabled, environment):
    created = session(client)
    packet = detail(client, created)
    monkeypatch.setattr(settings, 'AI_INSIGHTS_SAMPLE_ENABLED', enabled)
    monkeypatch.setattr(settings, 'ENVIRONMENT', environment)
    requests = [('GET', '/context', None), ('POST', '/sessions', {'request_key': key('hidden')}),
        ('GET', '/sessions/' + created['session_id'] + '/overview', None),
        ('GET', '/sessions/' + created['session_id'] + '/scenarios/spike', None),
        ('GET', '/sessions/' + created['session_id'] + '/scenarios/spike/report', None),
        ('POST', '/sessions/' + created['session_id'] + '/scenarios/spike/review', body(packet, 'APPROVE')),
        ('POST', '/sessions/' + created['session_id'] + '/reset', {'expected_session_revision': 1, 'request_key': key('hidden-reset')})]
    for method, suffix, payload in requests:
        assert client.request(method, '/api/ai-insights-sample' + suffix, headers=headers(created), json=payload).status_code == 404


def test_per_context_bootstrap_creation_idempotency_and_two_session_isolation(client):
    first_boot, second_boot = context(client)['bootstrap_token'], context(client)['bootstrap_token']
    assert first_boot != second_boot
    shared_key = key('same-public-key')
    first, second = session(client, first_boot, shared_key), session(client, second_boot, shared_key)
    assert first['session_id'] != second['session_id']
    assert first['session_token'] != second['session_token']
    assert replay_business(session(client, first_boot, shared_key)) == replay_business(first)
    untouched = detail(client, second)
    attacks = [('GET', '/overview', None), ('GET', '/scenarios/spike', None),
        ('POST', '/scenarios/spike/review', body(untouched, 'APPROVE')),
        ('POST', '/reset', {'expected_session_revision': 1, 'request_key': key('cross-reset')}),
        ('GET', '/scenarios/spike/report', None)]
    for method, suffix, payload in attacks:
        assert client.request(method, path(second, suffix), headers=headers(first), json=payload).status_code == 401
    assert detail(client, second) == untouched
    assert client.get(path(first, '/overview'), headers={'X-AI-Sample-Token': first_boot}).status_code == 401
    assert client.post('/api/ai-insights-sample/sessions', headers=headers(first), json={'request_key': key('wrong-authority')}).status_code == 401


def test_sample_tokens_cannot_authorize_actual_workflow_even_if_configured_as_real_admin(client, monkeypatch):
    created = session(client)
    monkeypatch.setattr(settings, 'API_IDENTITIES', {'misconfigured': {'token': created['session_token'], 'role': 'admin'}})
    authorization = {'Authorization': 'Bearer ' + created['session_token']}
    assert client.get('/api/ai-isolation/actor', headers=authorization).status_code == 401
    payload = {'request_key': key('actual'), 'expected_recommendation_sha256': 'a' * 64,
        'expected_revision': 0, 'comment': 'No actual action', 'decision': 'APPROVED'}
    assert client.post('/api/agents/workflows/actual-id/decision', headers=authorization, json=payload).status_code == 401


def test_qc_and_ai_sample_tokens_are_mutually_rejected_and_real_auth_cookie_are_never_accepted(client):
    created = session(client)
    qc_boot = client.get('/api/qc-sample/context').json()['bootstrap_token']
    qc_response = client.post('/api/qc-sample/sessions', headers={'X-QC-Sample-Token': qc_boot}, json={'request_key': key('qc-create')})
    assert qc_response.status_code == 200
    qc_created = qc_response.json()
    assert client.get(path(created, '/overview'), headers={'X-AI-Sample-Token': qc_created['session_token']}).status_code == 401
    assert client.get('/api/qc-sample/sessions/' + qc_created['session_id'] + '/overview',
        headers={'X-QC-Sample-Token': created['session_token']}).status_code == 401
    for addition in ({'Authorization': 'Bearer isolated-real-operator-ai-test'}, {'Cookie': 'operator=isolated-cookie'}):
        assert client.get(path(created, '/overview'), headers={**headers(created), **addition}).status_code == 401
    assert client.get(path(created, '/overview'), headers={'X-AI-Sample-Token': 'isolated-real-operator-ai-test'}).status_code == 401


@pytest.mark.parametrize('suffix', ['?source=REGISTERED', '?source=SAMPLE&source=REGISTERED', '?station=actual-station'])
def test_query_and_payload_injection_cannot_target_operational_sources(client, suffix):
    created = session(client)
    assert client.get(path(created, '/overview') + suffix, headers=headers(created)).status_code == 422
    response = client.post('/api/ai-insights-sample/sessions', headers={'X-AI-Sample-Token': context(client)['bootstrap_token']},
        json={'request_key': key('injected'), 'source': 'REGISTERED', 'workflow_id': 'actual-workflow'})
    assert response.status_code == 422


def test_approval_is_a_stop_gate_and_report_requires_explicit_resume_with_sample_authority(client):
    created = session(client)
    initial = detail(client, created)
    download_path = path(created, '/scenarios/spike/report')
    assert client.get(download_path, headers=headers(created)).status_code == 409
    assert review(client, created, initial, 'RESUME').status_code == 409
    assert review(client, created, initial, 'APPROVE').status_code == 200
    approved = detail(client, created)
    assert approved['workflow']['status'] == 'APPROVED'
    assert approved['workflow']['blocked'] and not approved['workflow']['downstream_executed']
    assert approved['workflow']['report_status'] == 'BLOCKED'
    assert client.get(download_path, headers=headers(created)).status_code == 409
    assert review(client, created, approved, 'RESUME').status_code == 200
    completed = detail(client, created)
    assert completed['workflow']['status'] == 'COMPLETED'
    assert completed['workflow']['report_status'] == 'READY'
    response = client.get(download_path, headers=headers(created))
    assert response.status_code == 200, response.text
    report = response.json()
    assert report['source'] == 'SAMPLE' and report['approved'] is False
    assert report['session_id'] == created['session_id']
    assert report['scenario_id'] == 'spike'
    assert report['generation'] == completed['generation']
    assert report['revision'] == completed['revision']
    assert report['recommendation_sha256'] == completed['recommendation_sha256']
    assert report['session_revision'] == completed['session_revision']
    assert report['filename'] == 'ai-sample-spike.md'
    assert report['markdown_hash_kind'] == 'UTF8_BYTES_SHA256'
    assert report['markdown_sha256'] == hashlib.sha256(report['markdown'].encode('utf-8')).hexdigest()
    assert report['report_sha256'] == sha256(report['report'])
    assert report['report']['scenario']['recommendation_sha256'] == completed['recommendation_sha256']
    assert report['report']['scenario']['revision'] == completed['revision']
    assert report['delivered'] is False and report['report']['recipients'] == []
    assert 'SAMPLE' in report['markdown'] and '운영 미승인' in report['markdown']
    assert overview(client, created)['kpis']['review_report_ready_count'] == 1


@pytest.mark.parametrize('action,state', [('HOLD', 'HELD'), ('REJECT', 'REJECTED'), ('COMMENT', 'PENDING')])
def test_review_variants_remain_blocked_without_changing_other_sessions(client, action, state):
    first, second = session(client), session(client)
    initial = detail(client, first, 'salinity-drift')
    untouched = detail(client, second, 'salinity-drift')
    assert review(client, first, initial, action).status_code == 200
    changed = detail(client, first, 'salinity-drift')
    assert changed['workflow']['status'] == state
    assert changed['workflow']['blocked'] and changed['workflow']['approved'] is False
    assert review(client, first, changed, 'RESUME').status_code == 409
    assert detail(client, second, 'salinity-drift') == untouched


def test_review_idempotency_stale_revision_hash_and_concurrent_compare_and_swap(client):
    created = session(client)
    initial = detail(client, created)
    payload = body(initial, 'APPROVE')
    first = review(client, created, initial, 'APPROVE', payload)
    replay = review(client, created, initial, 'APPROVE', payload)
    assert first.status_code == replay.status_code == 200
    assert replay.json()['idempotent_replay'] is True
    assert replay_business(first.json()) == replay_business(replay.json())
    assert review(client, created, initial, 'APPROVE', {**payload, 'comment': 'changed'}).status_code == 409
    assert review(client, created, initial, 'HOLD').status_code == 409
    current = detail(client, created)
    assert review(client, created, current, 'RESUME', {**body(current, 'RESUME'), 'recommendation_sha256': '0' * 64}).status_code == 409
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda action: review(client, created, current, action), ('HOLD', 'REJECT')))
    assert sorted(r.status_code for r in responses) == [200, 409]
    final = detail(client, created)
    assert final['revision'] == current['revision'] + 1
    assert len(final['workflow']['history']) == len(current['workflow']['history']) + 1


def test_reset_invalidates_old_generation_hash_and_successful_review_replay_without_mutating_peer(client):
    first, second = session(client), session(client)
    initial = detail(client, first)
    untouched = detail(client, second)
    payload = body(initial, 'APPROVE')
    assert review(client, first, initial, 'APPROVE', payload).status_code == 200
    old_revision = overview(client, first)['session_revision']
    reset_key = key('reset-replay')
    response = reset(client, first, old_revision, reset_key)
    assert response.status_code == 200
    replay = reset(client, first, old_revision, reset_key)
    assert replay.status_code == 200 and replay.json()['idempotent_replay']
    fresh = detail(client, first)
    assert fresh['generation'] == initial['generation'] + 1
    assert fresh['revision'] == 1 and fresh['workflow']['status'] == 'PENDING'
    assert fresh['recommendation_sha256'] != initial['recommendation_sha256']
    assert review(client, first, initial, 'APPROVE', payload).status_code == 409
    assert review(client, first, initial, 'APPROVE').status_code == 409
    assert client.get(path(first, '/scenarios/spike/report'), headers=headers(first)).status_code == 409
    assert detail(client, second) == untouched


@pytest.mark.parametrize('scenario_id', ['normal', 'high-temp-neighbor', 'spike', 'salinity-drift'])
def test_fixed_split_asof_causality_membership_and_exact_ui_series_binding(scenario_id):
    inputs = sample.scenario_inputs(scenario_id)
    result = sample._template()[scenario_id]
    memberships = inputs['membership']
    assert {split: len(rows) for split, rows in memberships.items()} == {'TRAIN': 480, 'VALIDATION': 168, 'TEST': 280}
    sets = [set(rows) for rows in memberships.values()]
    assert all(not left & right for index, left in enumerate(sets) for right in sets[index + 1:])
    assert len(set.union(*sets)) == len(inputs['rows']) == 928
    lookup = {row['row_id']: row for row in inputs['rows']}
    for row in inputs['rows']:
        assert datetime.fromisoformat(row['timestamp']) <= sample.AS_OF
        assert datetime.fromisoformat(row['available_at']) <= sample.AS_OF
        assert row['scope']['unit'] == inputs['unit']
    assert {row['row_id'] for row in inputs['fit']['rows']} == sets[0] | sets[1]
    assert {row['row_id'] for row in inputs['test']['rows']} == sets[2]
    assert result['membership'] == memberships
    assert len(result['series']) == 280
    for point in result['series']:
        raw = lookup[point['row_id']]
        assert point['timestamp'] == raw['timestamp'] and point['value'] == raw['value']
        assert point['reference_value'] == raw['reference']['value']
        assert point['injection_label'] == inputs['labels'][point['row_id']]['sensor_deviation']
        assert point['environmental_injection'] == inputs['labels'][point['row_id']]['environmental_change']
        for mode in point['modes']:
            assert datetime.fromisoformat(mode['window_end']) <= datetime.fromisoformat(point['timestamp'])
            assert all(datetime.fromisoformat(lookup[rid]['timestamp']) <= datetime.fromisoformat(point['timestamp']) for rid in mode['source_ids'])
            assert mode['score_kind'] == 'EMPIRICAL_CALIBRATION_RANK_NOT_PROBABILITY'
    assert result['uncertainty'] is None and result['confidence_probability'] is None
    assert result['forecast']['pair_counts'] == {'TRAIN': 477, 'VALIDATION': 165, 'TEST': 277}
    assert result['forecast']['artifact']['selection'] == 'VALIDATION_MAE_ONLY_TEST_NOT_USED'
    assert result['forecast']['artifact']['refit_after_selection'] is False


def test_ridge_train_only_scaler_predictions_validation_selection_and_metrics_independent_sklearn_oracle():
    inputs = sample.scenario_inputs('spike')
    result = sample._template()['spike']['forecast']
    lookup = {row['row_id']: row for row in inputs['rows']}
    arrays = {}
    for split, ids in inputs['membership'].items():
        values = [lookup[rid]['value'] for rid in ids]
        arrays[split] = (np.array([values[i - 3:i] for i in range(3, len(values))]), np.array(values[3:]))
    train_x, train_y = arrays['TRAIN']
    scaler = StandardScaler().fit(train_x)
    candidates = []
    fitted = {}
    for alpha in (.01, .1, 1.):
        model = Ridge(alpha=alpha).fit(scaler.transform(train_x), train_y)
        fitted[alpha] = model
        vx, vy = arrays['VALIDATION']
        candidates.append((float(np.mean(np.abs(vy - model.predict(scaler.transform(vx))))), alpha))
    best_mae, best_alpha = min(candidates)
    assert result['selected_alpha'] == best_alpha
    artifact_model = result['artifact']['ridge_model']
    assert artifact_model['mean'] == pytest.approx(scaler.mean_, abs=1e-12)
    assert artifact_model['scale'] == pytest.approx(scaler.scale_, abs=1e-12)
    assert artifact_model['coef'] == pytest.approx(fitted[best_alpha].coef_, abs=1e-10)
    tx, ty = arrays['TEST']
    predicted = fitted[best_alpha].predict(scaler.transform(tx))
    pairs = result['paired_test_predictions']
    assert [row['ridge'] for row in pairs] == pytest.approx(predicted, abs=1e-10)
    persistence = np.array([lookup[row['origin_id']]['value'] for row in pairs])
    for name, prediction in [('RIDGE', predicted), ('PERSISTENCE', persistence)]:
        metric = result['test_metrics'][name]
        assert metric['count'] == 277
        assert metric['mae'] == pytest.approx(np.mean(np.abs(ty - prediction)), abs=1e-10)
        assert metric['rmse'] == pytest.approx(np.sqrt(np.mean((ty - prediction) ** 2)), abs=1e-10)
    assert result['validation_metrics']['RIDGE']['mae'] == pytest.approx(best_mae, abs=1e-10)
    selected = 'RIDGE' if best_mae < result['validation_metrics']['PERSISTENCE']['mae'] else 'PERSISTENCE'
    assert result['selected_model'] == selected
    for pair in pairs:
        assert pair['feature_row_ids'][-1] == pair['origin_id']
        assert datetime.fromisoformat(lookup[pair['target_id']]['timestamp']) - datetime.fromisoformat(lookup[pair['origin_id']]['timestamp']) == timedelta(hours=1)
        assert pair['selected_prediction'] == pytest.approx(pair['ridge'] if selected == 'RIDGE' else pair['persistence'])


def test_test_values_cannot_change_fit_scaler_parameters_alpha_or_validation_selection():
    inputs = sample.scenario_inputs('normal')
    original = sample.forecast_comparison(inputs['rows'], inputs['membership'])
    changed = deepcopy(inputs['rows'])
    test_ids = set(inputs['membership']['TEST'])
    for row in changed:
        if row['row_id'] in test_ids:
            row['value'] += 10000
    altered = sample.forecast_comparison(changed, inputs['membership'])
    assert original['artifact']['ridge_model'] == altered['artifact']['ridge_model']
    assert original['selected_alpha'] == altered['selected_alpha']
    assert original['selected_model'] == altered['selected_model']
    assert original['validation_metrics'] == altered['validation_metrics']
    assert original['test_metrics'] != altered['test_metrics']


@pytest.mark.parametrize('corruption', ['overlap', 'duplicate', 'future', 'gap'])
def test_forecast_input_rejects_split_reuse_future_target_and_cadence_corruption(corruption):
    inputs = sample.scenario_inputs('normal')
    rows, membership = deepcopy(inputs['rows']), deepcopy(inputs['membership'])
    if corruption == 'overlap': membership['TEST'][0] = membership['TRAIN'][0]
    if corruption == 'duplicate': rows[1]['row_id'] = rows[0]['row_id']
    if corruption == 'future': rows[-1]['timestamp'] = '2026-07-09T16:00:00+09:00'
    if corruption == 'gap': rows[-1]['timestamp'] = '2026-07-09T15:30:00+09:00'
    with pytest.raises(sample.SampleError):
        sample.forecast_comparison(rows, membership)


def test_synthetic_injection_truth_confusion_and_kpi_denominators_are_independently_recomputed(client):
    created = session(client)
    packet = overview(client, created)
    rows, evaluated, anomaly_count = 0, 0, 0
    for scenario in packet['scenarios']:
        name = scenario['scenario_id']
        d = detail(client, created, name)
        series = d['series']
        rows += len(series)
        eligible = [point for point in series if all(mode['result_status'] == 'EVALUATED' for mode in point['modes'])]
        evaluated += len(eligible)
        anomaly_count += sum(point['assessment'] == 'ANOMALY' for point in series)
        tp = sum(point['injection_label'] and point['assessment'] == 'ANOMALY' for point in eligible)
        fp = sum(not point['injection_label'] and point['assessment'] == 'ANOMALY' for point in eligible)
        fn = sum(point['injection_label'] and point['assessment'] != 'ANOMALY' for point in eligible)
        tn = sum(not point['injection_label'] and point['assessment'] != 'ANOMALY' for point in eligible)
        metric = d['anomaly_evaluation']
        assert [metric[k] for k in ('tp', 'fp', 'fn', 'tn')] == [tp, fp, fn, tn]
        assert metric['evaluated_count'] == len(eligible)
        assert metric['precision'] == (tp / (tp + fp) if tp + fp else None)
        assert metric['recall'] == (tp / (tp + fn) if tp + fn else None)
        assert metric['false_positive_rate'] == (fp / (fp + tn) if fp + tn else None)
        assert metric['false_negative_rate'] == (fn / (tp + fn) if tp + fn else None)
        assert d['scenario']['confidence_probability'] is None and d['scenario']['uncertainty'] is None
        assert d['scenario']['current_value'] == series[-1]['value']
        assert d['scenario']['unit'] == ('psu' if name == 'salinity-drift' else 'degree_C')
        if name == 'normal': assert not any(point['injection_label'] or point['environmental_injection'] for point in series)
        if name == 'high-temp-neighbor':
            assert not any(point['injection_label'] for point in series)
            assert sum(point['environmental_injection'] for point in series) == 35
            assert all(abs(point['value'] - point['reference_value']) < .1 for point in series)
            assert d['scenario']['assessment'] == 'ENVIRONMENTAL_CHANGE_CANDIDATE'
        if name == 'spike': assert [i for i, point in enumerate(series) if point['injection_label']] == [80, 81, 160, 161, 240, 241, 276, 277]
        if name == 'salinity-drift': assert sum(point['injection_label'] for point in series) == 79
        assert d['operational_model_count'] == d['model_registry_writes'] == d['training_queue_writes'] == d['source_reads'] == 0
    kpis = packet['kpis']
    assert kpis['case_count'] == kpis['virtual_station_count'] == kpis['analysis_report_count'] == 4
    assert kpis['test_rows'] == rows == 1120
    assert kpis['evaluated_test_rows'] == evaluated
    assert kpis['anomaly_count'] == anomaly_count
    assert kpis['operational_model_count'] == 0
    assert kpis['review_report_ready_count'] == 0


def test_service_and_router_import_only_declared_pure_analysis_modules_without_operational_authority():
    allowed = {'app.ml.anomaly_artifact', 'app.services.anomaly_analysis', 'app.services.raw_model_comparison',
        'app.core.config', 'app.services'}
    for name in ('ai_insights_sample.py', '../api/routes_ai_insights_sample.py'):
        file = Path(sample.__file__).parent / name
        tree = ast.parse(file.read_text(encoding='utf-8'))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith('app.'):
                assert node.module in allowed
            if isinstance(node, ast.Import):
                assert not any(alias.name.startswith(('sqlalchemy', 'app.core.database', 'app.models')) for alias in node.names)


def test_expired_bootstrap_cannot_create_sessions_but_existing_session_has_independent_lifetime(client, monkeypatch):
    clock = [1000.0]
    monkeypatch.setattr(sample.time, 'monotonic', lambda: clock[0])
    bootstrap = context(client)['bootstrap_token']
    created = session(client, bootstrap)
    clock[0] += sample.BOOTSTRAP_TTL_SECONDS + 1
    assert client.post('/api/ai-insights-sample/sessions', headers={'X-AI-Sample-Token': bootstrap},
        json={'request_key': key('expired-create')}).status_code == 401
    assert client.get(path(created, '/overview'), headers=headers(created)).status_code == 200
    clock[0] += sample.TTL_SECONDS
    assert client.get(path(created, '/overview'), headers=headers(created)).status_code == 401


@pytest.mark.parametrize('corruption', ['bool-revision', 'fractional-revision', 'blank-comment', 'extra-target', 'malformed-sha', 'wrong-action'])
def test_review_strict_input_cannot_coerce_revision_or_operational_target(client, corruption):
    created = session(client)
    initial = detail(client, created)
    payload = body(initial, 'APPROVE')
    if corruption == 'bool-revision': payload['expected_revision'] = True
    if corruption == 'fractional-revision': payload['expected_revision'] = 1.1
    if corruption == 'blank-comment': payload['comment'] = '   '
    if corruption == 'extra-target': payload['workflow_id'] = 'real-operational-id'
    if corruption == 'malformed-sha': payload['recommendation_sha256'] = 'not-a-hash'
    if corruption == 'wrong-action': payload['action'] = 'DEPLOY'
    assert review(client, created, initial, 'APPROVE', payload).status_code == 422
    assert detail(client, created) == initial


@pytest.mark.parametrize('scenario_id', ['normal', 'high-temp-neighbor', 'spike', 'salinity-drift'])
def test_robust_scores_calibration_threshold_rank_and_warmup_independent_numeric_oracle(scenario_id):
    inputs = sample.scenario_inputs(scenario_id)
    template = sample._template()[scenario_id]
    lookup = {row['row_id']: row for row in inputs['rows']}
    rows = {split: [lookup[rid] for rid in ids] for split, ids in inputs['membership'].items()}
    train_values = np.array([row['value'] for row in rows['TRAIN']])
    train_residuals = np.array([row['value'] - row['reference']['value'] for row in rows['TRAIN']])
    differences = np.diff(train_values)
    delta_center = np.median(differences)
    delta_scale = max(float(np.median(abs(differences - delta_center))) * 1.4826, .01)
    residual_center = float(np.median(train_residuals))
    residual_scale = max(float(np.median(abs(train_residuals - residual_center))) * 1.4826, .01)
    artifact = template['fitted_anomaly_artifact']['artifact']
    assert artifact['fitted']['delta_scale'] == pytest.approx(delta_scale)
    assert artifact['fitted']['residual_center'] == pytest.approx(residual_center)
    assert artifact['fitted']['residual_scale'] == pytest.approx(residual_scale)
    calibration_rows = rows['VALIDATION']
    scores = {
        'SPIKE': [abs(right['value'] - left['value']) / delta_scale for left, right in zip(calibration_rows, calibration_rows[1:])],
        'DRIFT': [abs(np.median([r['value'] - r['reference']['value'] for r in calibration_rows[i - 7:i + 1]]) - residual_center) / residual_scale for i in range(7, len(calibration_rows))],
    }
    for mode, values in scores.items():
        model = artifact['models'][mode]
        assert model['calibration_scores'] == pytest.approx(sorted(values))
        assert model['threshold'] == pytest.approx(float(np.quantile(values, .99, method='higher')))
    for index, point in enumerate(template['series']):
        for mode in point['modes']:
            kind, warmup = mode['mode'], 1 if mode['mode'] == 'SPIKE' else 7
            if index < warmup:
                assert mode['result_status'] == 'NOT_EVALUATED'
                assert mode['score'] is None and mode['calibration_rank'] is None
                continue
            if kind == 'SPIKE': expected = abs(rows['TEST'][index]['value'] - rows['TEST'][index - 1]['value']) / delta_scale
            else: expected = abs(np.median([r['value'] - r['reference']['value'] for r in rows['TEST'][index - 7:index + 1]]) - residual_center) / residual_scale
            rank = sum(value <= expected for value in scores[kind]) / len(scores[kind])
            assert mode['score'] == pytest.approx(expected)
            assert mode['calibration_rank'] == pytest.approx(rank)
            assert mode['assessment'] == ('ANOMALY' if expected > artifact['models'][kind]['threshold'] else 'NORMAL')


def test_later_test_values_cannot_change_earlier_anomaly_outputs_and_future_availability_remains_unevaluated():
    from app.services.anomaly_analysis import analyze_series
    inputs = sample.scenario_inputs('salinity-drift')
    artifact = sample._template()['salinity-drift']['fitted_anomaly_artifact']
    original = sample._template()['salinity-drift']['anomaly_report']
    changed = deepcopy(inputs['test'])
    changed['rows'][-1]['value'] += 1000
    altered = analyze_series(changed, artifact)
    assert altered['status'] == 'ANALYSIS_ONLY'
    last_id = changed['rows'][-1]['row_id']
    assert [r for r in altered['results'] if r['row_id'] != last_id] == [r for r in original['results'] if r['row_id'] != last_id]
    future = deepcopy(inputs['test'])
    future['rows'][-1]['available_at'] = '2026-07-09T16:00:00+09:00'
    unavailable = analyze_series(future, artifact)
    assert unavailable['status'] == 'ANALYSIS_ONLY'
    assert all(r['result_status'] == 'NOT_EVALUATED' and r['score'] is None for r in unavailable['results'] if r['row_id'] == last_id)
