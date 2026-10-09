"""HTTP trust boundaries for disposable QC samples; no operational DB fixture."""
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.database import get_db
from app.core.security import authorize_api, current_actor


def key(label):
    return label + ':' + uuid4().hex


@pytest.fixture
def client(monkeypatch):
    from app.api import routes_agents, routes_qc_sample
    from app.core import database
    from app.services import qc_sample

    monkeypatch.setattr(settings, 'QC_SAMPLE_ENABLED', True)
    monkeypatch.setattr(settings, 'ENVIRONMENT', 'development')
    monkeypatch.setattr(settings, 'API_IDENTITIES', {
        'real-reviewer': {'token': 'isolated-real-review-token', 'role': 'reviewer'},
    })
    accesses = []

    def database_bomb(*args, **kwargs):
        accesses.append('OPERATIONAL_DATABASE_ACCESS')
        pytest.fail('A sample request attempted to access the operational database')

    monkeypatch.setattr(database, 'SessionLocal', database_bomb)
    monkeypatch.setattr(database.engine, 'connect', database_bomb)
    app = FastAPI(dependencies=[Depends(authorize_api)])
    app.include_router(routes_qc_sample.router)
    app.include_router(routes_agents.router)
    app.dependency_overrides[get_db] = database_bomb

    @app.get('/api/sample-isolation/actor')
    def actor_identity(actor=Depends(current_actor)):
        return {'user_id': actor.user_id, 'role': actor.role}

    qc_sample.reset_store_for_tests()
    with TestClient(app) as test_client:
        yield test_client
    assert accesses == []
    qc_sample.reset_store_for_tests()


def bootstrap(client):
    response = client.get('/api/qc-sample/context')
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload['source'] == 'SAMPLE' and payload['is_sample'] is True
    assert payload['bootstrap_token'].startswith('qc-sample-')
    return payload['bootstrap_token']


def session(client, bootstrap_token=None, request_key=None):
    response = client.post('/api/qc-sample/sessions',
        headers={'X-QC-Sample-Token': bootstrap_token or bootstrap(client)},
        json={'request_key': request_key or key('create')})
    assert response.status_code in (200, 201), response.text
    result = response.json()
    assert result['source'] == 'SAMPLE' and result['is_sample'] is True
    assert result['session_token'].startswith('qc-sample-')
    assert result['session_revision'] == 1
    return result


def headers(created):
    return {'X-QC-Sample-Token': created['session_token']}


def retry_payload(packet):
    """Replay annotations may differ; entity, revision, evidence must not."""
    return {k: v for k, v in packet.items() if k not in {'idempotent_replay', 'result_sha256'}}


def overview(client, created):
    response = client.get('/api/qc-sample/sessions/' + created['session_id'] + '/overview',
        headers=headers(created))
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload['source'] == 'SAMPLE' and payload['is_sample'] is True
    return payload


def detail(client, created, case_id):
    response = client.get('/api/qc-sample/sessions/' + created['session_id'] + '/cases/' + case_id,
        headers=headers(created))
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload['source'] == 'SAMPLE' and payload['is_sample'] is True
    return payload


def scenario(client, created, name):
    candidate = next(row for row in overview(client, created)['cases'] if row['scenario_id'] == name)
    return detail(client, created, candidate['case_id'])


def review_body(payload, action, *, request_key=None, comment='Isolated sample review'):
    return dict(action=action, comment=comment, expected_revision=payload['revision'],
        recommendation_sha256=payload['recommendation_sha256'], request_key=request_key or key(action))


def review(client, created, payload, action, *, body=None):
    return client.post('/api/qc-sample/sessions/' + created['session_id'] + '/cases/' + payload['case']['case_id'] + '/review',
        headers=headers(created), json=body or review_body(payload, action))


@pytest.mark.parametrize('enabled,environment', [(False, 'development'), (True, 'production'), (True, 'staging')])
def test_disabled_or_nonlocal_mode_hides_reads_and_writes(client, monkeypatch, enabled, environment):
    created = session(client)
    monkeypatch.setattr(settings, 'QC_SAMPLE_ENABLED', enabled)
    monkeypatch.setattr(settings, 'ENVIRONMENT', environment)
    endpoints = [('/context', 'GET', None), ('/sessions', 'POST', {'request_key': key('disabled')}),
        ('/sessions/' + created['session_id'] + '/overview', 'GET', None),
        ('/sessions/' + created['session_id'] + '/reset', 'POST', {'expected_session_revision': 1, 'request_key': key('reset')})]
    for endpoint, method, body in endpoints:
        response = client.request(method, '/api/qc-sample' + endpoint, headers=headers(created), json=body)
        assert response.status_code == 404


def test_context_bootstrap_and_session_tokens_are_distinct_authorities(client):
    token = bootstrap(client)
    created = session(client, token)
    assert token != created['session_token']
    response = client.get('/api/qc-sample/sessions/' + created['session_id'] + '/overview',
        headers={'X-QC-Sample-Token': token})
    assert response.status_code in (401, 403, 404)
    response = client.post('/api/qc-sample/sessions', headers=headers(created), json={'request_key': key('wrong-authority')})
    assert response.status_code in (401, 403, 404)


def test_creation_exact_retry_reuses_one_session_and_token(client):
    token = bootstrap(client)
    request_key = key('idempotent-create')
    first = session(client, token, request_key)
    replay = session(client, token, request_key)
    assert replay['idempotent_replay'] is True
    assert retry_payload(replay) == retry_payload(first)


def test_distinct_bootstrap_contexts_cannot_share_session_via_same_creation_request_key(client):
    first_bootstrap, second_bootstrap = bootstrap(client), bootstrap(client)
    assert first_bootstrap != second_bootstrap
    request_key = key('public-shared-request-key')
    first = session(client, first_bootstrap, request_key)
    second = session(client, second_bootstrap, request_key)
    assert first['session_id'] != second['session_id']
    assert first['session_token'] != second['session_token']
    assert retry_payload(session(client, first_bootstrap, request_key)) == retry_payload(first)
    assert retry_payload(session(client, second_bootstrap, request_key)) == retry_payload(second)
    response = client.get('/api/qc-sample/sessions/' + second['session_id'] + '/overview', headers=headers(first))
    assert response.status_code == 401


def test_two_session_tokens_cannot_cross_read_review_or_reset(client):
    first, second = session(client), session(client)
    assert first['session_id'] != second['session_id']
    assert first['session_token'] != second['session_token']
    original = scenario(client, second, 'spike')
    prefix = '/api/qc-sample/sessions/' + second['session_id']
    attacks = [('/overview', 'GET', None), ('/cases/' + original['case']['case_id'], 'GET', None),
        ('/cases/' + original['case']['case_id'] + '/review', 'POST', review_body(original, 'APPROVE')),
        ('/reset', 'POST', {'expected_session_revision': 1, 'request_key': key('cross-reset')})]
    for endpoint, method, body in attacks:
        response = client.request(method, prefix + endpoint, headers=headers(first), json=body)
        assert response.status_code in (401, 403, 404)
    own_prefix = '/api/qc-sample/sessions/' + first['session_id'] + '/cases/' + original['case']['case_id']
    own = client.get(own_prefix, headers=headers(first))
    if own.status_code == 200:
        # Case ids may be local to a session, but foreign recommendation authority cannot be reused.
        assert own.json()['session_id'] == first['session_id']
        assert own.json()['recommendation_sha256'] != original['recommendation_sha256']
        assert client.post(own_prefix + '/review', headers=headers(first),
            json=review_body(original, 'APPROVE')).status_code == 409
    else:
        assert own.status_code == 404
    assert detail(client, second, original['case']['case_id']) == original


def test_sample_tokens_never_authorize_real_workflow_even_if_registered_as_actual_identity(client, monkeypatch):
    created = session(client)
    monkeypatch.setattr(settings, 'API_IDENTITIES', {
        'misconfigured-sample': {'token': created['session_token'], 'role': 'admin'},
    })
    authorization = {'Authorization': 'Bearer ' + created['session_token']}
    assert client.get('/api/sample-isolation/actor', headers=authorization).status_code == 401
    body = dict(request_key=key('real'), expected_recommendation_sha256='a' * 64, expected_revision=0,
        comment='Must never reach real workflow', decision='APPROVED')
    response = client.post('/api/agents/workflows/actual-workflow-id/decision', headers=authorization, json=body)
    assert response.status_code == 401


def test_real_operator_token_cannot_replace_sample_session_auth(client):
    created = session(client)
    for header in ({'Authorization': 'Bearer isolated-real-review-token'},
        {'X-QC-Sample-Token': 'isolated-real-review-token'}):
        response = client.get('/api/qc-sample/sessions/' + created['session_id'] + '/overview', headers=header)
        assert response.status_code in (401, 403, 404)


def test_extra_fields_and_duplicate_queries_cannot_select_operational_source(client):
    token = bootstrap(client)
    response = client.post('/api/qc-sample/sessions', headers={'X-QC-Sample-Token': token},
        json={'request_key': key('source-injection'), 'source': 'REGISTERED', 'workflow_id': 'real-workflow'})
    assert response.status_code == 422
    created = session(client, token)
    for suffix in ('?source=REGISTERED', '?source=SAMPLE&source=REGISTERED'):
        response = client.get('/api/qc-sample/sessions/' + created['session_id'] + '/overview' + suffix,
            headers=headers(created))
        assert response.status_code == 422


def test_approval_stops_until_explicit_resume_and_remains_nondefinitive_sample(client):
    created = session(client)
    initial = scenario(client, created, 'spike')
    assert initial['workflow']['status'] == 'PENDING'
    assert initial['workflow']['blocked'] is True
    assert initial['workflow']['downstream_executed'] is False
    assert initial['workflow']['definitive_qc'] is False
    assert review(client, created, initial, 'RESUME').status_code == 409
    response = review(client, created, initial, 'APPROVE')
    assert response.status_code == 200, response.text
    approved = detail(client, created, initial['case']['case_id'])
    assert approved['workflow']['status'] == 'APPROVED'
    assert approved['workflow']['blocked'] is True and approved['workflow']['downstream_executed'] is False
    response = review(client, created, approved, 'RESUME')
    assert response.status_code == 200, response.text
    completed = detail(client, created, initial['case']['case_id'])
    assert completed['workflow']['status'] == 'COMPLETED'
    assert completed['workflow']['definitive_qc'] is False
    assert completed['source'] == 'SAMPLE' and completed['production_writes'] == 0
    history = completed['workflow']['history']
    assert sum(row['action'] == 'APPROVE' for row in history) == 1
    assert sum(row['action'] == 'RESUME' for row in history) == 1
    assert history[-1]['to_state'] == 'COMPLETED'
    assert any(row['from_state'] == 'APPROVED' and row['to_state'] == 'RESUMING' for row in history)


@pytest.mark.parametrize('action,state', [('HOLD', 'HELD'), ('REJECT', 'REJECTED')])
def test_hold_and_reject_do_not_resume_or_affect_other_sessions(client, action, state):
    first, second = session(client), session(client)
    initial = scenario(client, first, 'late')
    untouched = scenario(client, second, 'late')
    assert review(client, first, initial, action).status_code == 200
    stopped = detail(client, first, initial['case']['case_id'])
    assert stopped['workflow']['status'] == state and stopped['workflow']['blocked'] is True
    assert review(client, first, stopped, 'RESUME').status_code == 409
    assert detail(client, second, untouched['case']['case_id']) == untouched


def test_review_exact_retries_are_idempotent_but_payload_or_stale_authority_conflict(client):
    created = session(client)
    initial = scenario(client, created, 'normal')
    body = review_body(initial, 'COMMENT', request_key=key('same-comment'))
    first = review(client, created, initial, 'COMMENT', body=body)
    assert first.status_code == 200, first.text
    replay = review(client, created, initial, 'COMMENT', body=body).json()
    assert replay['idempotent_replay'] is True
    assert retry_payload(replay) == retry_payload(first.json())
    changed = dict(body, comment='Changed reuse of the same key')
    assert review(client, created, initial, 'COMMENT', body=changed).status_code == 409
    after = detail(client, created, initial['case']['case_id'])
    assert len(after['workflow']['history']) == len(initial['workflow']['history']) + 1
    assert review(client, created, initial, 'APPROVE').status_code == 409
    wrong_hash = review_body(after, 'APPROVE')
    wrong_hash['recommendation_sha256'] = 'f' * 64
    assert review(client, created, after, 'APPROVE', body=wrong_hash).status_code == 409
    assert detail(client, created, initial['case']['case_id']) == after


def test_reset_rotates_candidate_authority_clears_reviews_and_preserves_other_session(client):
    first, second = session(client), session(client)
    old = scenario(client, first, 'spike')
    untouched = scenario(client, second, 'spike')
    assert review(client, first, old, 'HOLD').status_code == 200
    current_revision = overview(client, first)['session_revision']
    body = dict(expected_session_revision=current_revision, request_key=key('reset'))
    url = '/api/qc-sample/sessions/' + first['session_id'] + '/reset'
    response = client.post(url, headers=headers(first), json=body)
    assert response.status_code == 200, response.text
    replay = client.post(url, headers=headers(first), json=body).json()
    assert replay['idempotent_replay'] is True
    assert retry_payload(replay) == retry_payload(response.json())
    refreshed = scenario(client, first, 'spike')
    assert refreshed['workflow']['status'] == 'PENDING'
    assert all(row['action'] == 'CREATE' for row in refreshed['workflow']['history'])
    assert overview(client, first)['session_revision'] == current_revision + 1
    assert refreshed['case']['case_id'] != old['case']['case_id'] or refreshed['recommendation_sha256'] != old['recommendation_sha256']
    assert review(client, first, old, 'APPROVE').status_code in (404, 409)
    assert client.post(url, headers=headers(first), json=dict(body, request_key=key('stale-reset'))).status_code == 409
    assert detail(client, second, untouched['case']['case_id']) == untouched


@pytest.mark.parametrize('revision', [True, 1.0, '1', 0, -1])
def test_review_revision_requires_positive_json_integer_without_coercion(client, revision):
    created = session(client)
    initial = scenario(client, created, 'normal')
    body = review_body(initial, 'APPROVE')
    body['expected_revision'] = revision
    assert review(client, created, initial, 'APPROVE', body=body).status_code == 422
    assert detail(client, created, initial['case']['case_id']) == initial


def test_simultaneous_conflicting_reviews_apply_one_transition_only(client):
    created = session(client)
    initial = scenario(client, created, 'spike')
    bodies = [review_body(initial, action) for action in ('APPROVE', 'REJECT')]
    with ThreadPoolExecutor(max_workers=2) as workers:
        futures = [workers.submit(review, client, created, initial, body['action'], body=body) for body in bodies]
        responses = [future.result(timeout=15) for future in futures]
    assert sorted(response.status_code for response in responses) == [200, 409]
    updated = detail(client, created, initial['case']['case_id'])
    assert updated['revision'] == initial['revision'] + 1
    assert updated['workflow']['status'] in ('APPROVED', 'REJECTED')
    assert len(updated['workflow']['history']) == len(initial['workflow']['history']) + 1


def test_approval_does_not_rewrite_raw_rows_or_engine_flags(client):
    created = session(client)
    initial = scenario(client, created, 'missing')
    source_rows = deepcopy(initial['series']['rows'])
    rule_results = deepcopy(initial['rules'])
    assert review(client, created, initial, 'APPROVE').status_code == 200
    updated = detail(client, created, initial['case']['case_id'])
    assert updated['series']['rows'] == source_rows
    assert updated['rules'] == rule_results
    assert updated['workflow']['definitive_qc'] is False


def test_sample_packets_bind_real_engine_results_and_never_claim_trained_or_approved_models(client, monkeypatch):
    from app.services import qc_rule_engine, qc_sample

    executions = []

    def execute_actual_engine(records, rules, context):
        result = qc_rule_engine.execute_rules(records, rules, context)
        executions.append((records[0]['station_id'], deepcopy(result)))
        return result

    monkeypatch.setattr(qc_sample, 'execute_rules', execute_actual_engine)
    created = session(client)
    assert len(executions) == 4
    reports = dict(executions)
    expected_flags = {'normal': '1', 'late': '3', 'missing': '9', 'spike': '4'}
    for name, expected_flag in expected_flags.items():
        payload = scenario(client, created, name)
        assert payload['case']['flag'] == expected_flag
        target = next(row for row in payload['series']['rows']
            if row['observation_time'] == payload['case']['observation_time'])
        actual = [row for row in reports[payload['case']['station_id']]['results']
            if row['observation_id'] == target['observation_id']]
        assert payload['rules'] == actual
        assert len(payload['rules']) == 12
        assert payload['ai'] == dict(status='NOT_RUN', trained_model=False, result=None)
        assert payload['approved'] is False and payload['workflow']['definitive_qc'] is False
        assert payload['production_writes'] == payload['operational_writes'] == payload['source_reads'] == 0
        assert payload['model_training'] == payload['final_qc_writes'] == 0
        assert all(row['approved'] is False and row['analysis_only'] is True for row in actual)
    summary = overview(client, created)['summary']
    assert all(summary[state]['count'] == 1 and summary[state]['denominator'] == 4
        for state in ('normal', 'suspect', 'bad', 'missing'))
    rule_summary = {row['rule_id']: row for row in overview(client, created)['rule_qc_counts']['items']}
    for kind in ('RR', 'SR', 'ST'):
        assert rule_summary[kind]['full_test_evaluated_count'] == 0
        assert rule_summary[kind]['missing_precheck_count'] == 3
        assert rule_summary[kind]['sample_configured'] is False


def test_missing_planned_slots_stay_null_with_declared_sentinel_and_late_has_real_receipt_delta(client):
    created = session(client)
    missing = scenario(client, created, 'missing')
    gaps = [row for row in missing['series']['rows'] if row['is_missing']]
    assert len(gaps) == missing['series']['missing_slots'] == 3
    assert missing['series']['planned_slots'] == 61 and missing['series']['received_slots'] == 58
    assert all(row['value'] is None and row['received_time'] is None and row['delay_seconds'] is None
        and row['observed'] is False and row['interpolated'] is False
        and row['rule_input_value'] == -999 for row in gaps)
    er = next(row for row in missing['rules'] if row['kind'] == 'ER')
    assert er['result_flag'] == '9' and er['evaluation_status'] == 'MISSING'
    assert all(row['interpolated'] is False for row in missing['series']['rows'])
    late = scenario(client, created, 'late')
    target = next(row for row in late['series']['rows']
        if row['observation_time'] == late['case']['observation_time'])
    delta = (datetime.fromisoformat(target['received_time'])
        - datetime.fromisoformat(target['observation_time'])).total_seconds()
    assert delta == target['delay_seconds'] == late['case']['delay_seconds'] == 480
    assert target['observed'] is True and target['is_late'] is True
    assert next(row for row in late['rules'] if row['kind'] == 'DE')['result_flag'] == '3'


def test_bad_peak_is_rule_range_failure_and_spike_retains_suspect_semantics(client):
    payload = scenario(client, session(client), 'spike')
    assert payload['case']['value'] == 45 and payload['case']['flag'] == '4'
    result_flags = {row['kind']: row['result_flag'] for row in payload['rules']}
    assert result_flags['GR'] == '4' and result_flags['SP'] == '3'
    specs = {row['kind']: row['parameters'] for row in payload['rule_specs']}
    assert specs['GR']['max'] == 40 < payload['case']['value']
    assert specs['SP']['max_delta'] == 1


def test_duplicate_sample_headers_or_combined_real_authorization_fail_closed(client):
    created = session(client)
    url = '/api/qc-sample/sessions/' + created['session_id'] + '/overview'
    duplicated = [('X-QC-Sample-Token', created['session_token']),
        ('X-QC-Sample-Token', created['session_token'])]
    assert client.get(url, headers=duplicated).status_code == 401
    combined = dict(headers(created), Authorization='Bearer isolated-real-review-token')
    assert client.get(url, headers=combined).status_code == 401


def test_expiry_removes_only_expired_session_and_cannot_replay_its_creation(client, monkeypatch):
    from app.services import qc_sample

    clock = [100.0]
    monkeypatch.setattr(qc_sample, 'time', SimpleNamespace(monotonic=lambda: clock[0]))
    token = bootstrap(client)
    request_key = key('expires')
    first = session(client, token, request_key)
    clock[0] += 100
    second = session(client, token)
    clock[0] = 100.0 + qc_sample.TTL_SECONDS
    assert client.get('/api/qc-sample/sessions/' + first['session_id'] + '/overview',
        headers=headers(first)).status_code == 401
    assert overview(client, second)['session_id'] == second['session_id']
    assert client.post('/api/qc-sample/sessions', headers={'X-QC-Sample-Token': token},
        json={'request_key': request_key}).status_code == 401
    replacement = session(client, bootstrap(client), request_key)
    assert replacement['session_id'] != first['session_id']
    assert replacement['session_token'] != first['session_token']


def test_bootstrap_expiry_prevents_new_creation_without_revoking_existing_session(client, monkeypatch):
    from app.services import qc_sample

    clock = [100.0]
    monkeypatch.setattr(qc_sample, 'time', SimpleNamespace(monotonic=lambda: clock[0]))
    token = bootstrap(client)
    created = session(client, token)
    clock[0] += qc_sample.BOOTSTRAP_TTL_SECONDS
    assert client.post('/api/qc-sample/sessions', headers={'X-QC-Sample-Token': token},
        json={'request_key': key('expired-bootstrap')}).status_code == 401
    assert overview(client, created)['session_id'] == created['session_id']
    fresh = session(client)
    assert fresh['session_id'] != created['session_id']


def test_store_loss_rotates_bootstrap_and_invalidates_all_old_session_authority(client):
    from app.services import qc_sample

    token = bootstrap(client)
    created = session(client, token)
    qc_sample.reset_store_for_tests()
    assert bootstrap(client) != token
    assert client.get('/api/qc-sample/sessions/' + created['session_id'] + '/overview',
        headers=headers(created)).status_code == 401
    assert client.post('/api/qc-sample/sessions', headers={'X-QC-Sample-Token': token},
        json={'request_key': key('old-bootstrap')}).status_code == 401
