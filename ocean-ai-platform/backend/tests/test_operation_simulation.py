"""Faults use actual production-shaped pure engines, not mock stage statuses."""
import pytest
from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient

from app.core.security import authorize_api
from app.api.routes_operation_simulation import router
from app.services.operation_simulation import SCENARIOS, run_simulation, _quality_inputs
from app.services.evidence_fusion import digest
from app.services.anomaly_analysis import fit_analysis, analyze_series
from datetime import datetime


@pytest.mark.parametrize('scenario_id,_,__,expected', SCENARIOS)
def test_synthetic_operation_and_quality_gate(scenario_id, _, __, expected):
    r = run_simulation(scenario_id, '2026-07-09', '15:41:20')
    assert r['all_checks_passed'], r['assertions']
    assert r['operation']['state'] == expected
    assert r['source'] == 'SIMULATION' and r['approved'] is False and r['production_completed'] is False
    assert r['result_sha256'] == digest({k: v for k, v in r.items() if k != 'result_sha256'})
    assert r['quality_pipeline']['rule']['not_evaluated_count'] == 3  # warm-up windows are retained
    assert r['quality_pipeline']['workflow']['production_writes'] == 0
    assert r['quality_pipeline']['workflow']['actual_approval_granted'] is False
    assert r['quality_pipeline']['ai']['anomaly_count'] >= 0
    if scenario_id == 'future':
        assert r['operation']['channels'][0]['future_rows_excluded'] == 1
        assert r['operation']['evidence']['event_registry']['eligible_records'] == 0
    if scenario_id == 'spike':
        assert max(float(row['value_raw']) for row in r['rows']) > 23


def test_simulation_is_reproducible_and_never_uses_live_session(monkeypatch):
    from app.core import database
    monkeypatch.setattr(database, 'SessionLocal', lambda *args: pytest.fail('live session must not open'))
    from app.services import operation_simulation
    monkeypatch.setattr(operation_simulation.workflow, 'SessionLocal', lambda *args: pytest.fail('live session must not open'))
    first = run_simulation('spike', '2026-07-09', '15:41:20.123456')
    second = run_simulation('spike', '2026-07-09', '15:41:20.123456')
    assert first == second
    assert first['operation']['window_end'] == '2026-07-09 15:41:20.123456'


def test_sample_fit_and_test_reuse_cannot_cross_fixed_split():
    fit, test, protocol, _, __ = _quality_inputs('spike', datetime(2026, 7, 9, 15, 41, 20))
    model = fit_analysis(fit, protocol)
    test['rows'][0]['source'] = fit['rows'][0]['source']
    assert analyze_series(test, model['artifact'])['blockers'] == ['FIT_TEST_SOURCE_RECORD_REUSE']


def test_simulation_api_is_loopback_bounded_and_has_no_identity_configuration_requirement():
    app = FastAPI(dependencies=[Depends(authorize_api)])
    app.include_router(router)
    remote = TestClient(app, client=('192.0.2.1', 1))
    assert remote.get('/api/operation-simulation/scenarios').status_code == 403
    local = TestClient(app, client=('127.0.0.1', 1))
    assert len(local.get('/api/operation-simulation/scenarios').json()['scenarios']) == len(SCENARIOS)
    assert local.post('/api/operation-simulation/run', json={'padding': 'x'*2048}).status_code == 413
    body = dict(scenario_id='normal', as_of_day='2026-07-09', as_of_time='15:41:20')
    assert local.post('/api/operation-simulation/run', json=dict(body, actor='admin')).status_code == 422
    assert local.post('/api/operation-simulation/run', json=dict(body, scenario_id='arbitrary')).status_code == 422
    assert local.post('/api/operation-simulation/run', json=dict(body, as_of_time='25:00:00')).status_code == 422
    response = local.post('/api/operation-simulation/run', json=body)
    assert response.status_code == 200 and response.json()['all_checks_passed']
