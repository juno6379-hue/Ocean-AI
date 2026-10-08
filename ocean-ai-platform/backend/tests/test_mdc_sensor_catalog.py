# 파일 역할: 실제 소스 코드별 센서 분리, 단위 충돌, 버전 멱등성과 시뮬레이션 계보 차단을 검증합니다.
from datetime import datetime
import pytest
from test_event_evidence import env, complete_chain, checked, OP, REVIEW
from app.models.domain import SensorMetadata, ObservationRaw
from app.models.evidence import MDCSensorCatalog
from app.services.mdc_sensor_catalog import catalog_records, sync_catalog, resolve_catalog, item_semantics


def source():
    return {'equipment': [{'obs_post_id': 'ST1', 'te_code': 'A'}], 'items': [
        {'obs_post_id': 'ST1', 'te_code': 'A', 'obs_item_code': 'WAVE_HEIGHT', 'unit': 'm'},
        {'obs_post_id': 'ST1', 'te_code': 'A', 'obs_item_code': 'WAVE_PERIOD', 'unit': 'sec'},
        {'obs_post_id': 'ST1', 'te_code': 'B', 'obs_item_code': 'WAVE_HEIGHT', 'unit': 'cm'}]}


def test_distinct_channels_immutable_versions_and_unreviewed_aliases(env):
    client, sessions = env
    data = source()
    with sessions() as db:
        first = sync_catalog(db, data, ['ST1']); db.commit()
        again = sync_catalog(db, data, ['ST1']); db.commit()
        assert first['inserted_catalog_rows'] == 3 and again['inserted_catalog_rows'] == 0
        assert db.query(MDCSensorCatalog).count() == 3
        assert db.query(SensorMetadata).filter_by(sensor_type='MDC_SOURCE_CHANNEL').count() == 3
        assert resolve_catalog(db, first['catalog_version'], 'ST1', 'WAVE_HEIGHT', datetime(2018, 1, 1))['status'] == 'AMBIGUOUS'
        period = resolve_catalog(db, first['catalog_version'], 'ST1', 'WAVE_PERIOD', datetime(2018, 1, 1))
        assert period['status'] == 'REVIEW_REQUIRED'
        assert 'HISTORICAL_VALIDITY_UNKNOWN' in period['candidates'][0]['issues']
        data['items'][1]['unit'] = 'm'
        changed = sync_catalog(db, data, ['ST1']); db.commit()
        assert changed['catalog_version'] != first['catalog_version']
        assert db.query(MDCSensorCatalog).count() == 6
    catalog = checked(client.get('/api/events/mdc-sensor-catalog?station_id=ST1&limit=2'))
    assert catalog['total'] == 6 and len(catalog['items']) == 2
    assert catalog['is_demo'] is False
    assert checked(client.get('/api/events/reference-catalog?station_id=ST1'))['reviewed_aliases'] == []


@pytest.mark.parametrize('code,unit,variable,expected_issue', [
    ('WAVE_PERIOD', 'm', 'WAVE_PERIOD', 'SOURCE_UNIT_CONFLICT'),
    ('WAVE_DIRECT', 'deg', 'WAVE_DIRECT', None),
    ('WIND_SPEED', 'psu', 'WIND_SPEED', 'SOURCE_UNIT_CONFLICT'),
    ('SEA_LEVEL', None, 'SEA_LEVEL', 'SOURCE_UNIT_MISSING'),
    ('SALINITY2', 'psu', 'SALINITY', None),
])
def test_semantics_never_conflate_wave_height_period_direction(code, unit, variable, expected_issue):
    actual, _, issues = item_semantics(code, unit)
    assert actual == variable
    if expected_issue: assert expected_issue in issues
    else: assert not issues


def test_duplicate_source_key_is_not_silently_selected():
    data = source(); data['items'].append(dict(data['items'][0], unit='cm'))
    records = catalog_records(data, {'ST1'})
    assert len(records) == 3
    duplicate = next(r for r in records if r['te_code'] == 'A' and r['source_item_code'] == 'WAVE_HEIGHT')
    assert 'DUPLICATE_SOURCE_KEY' in duplicate['issues'] and len(duplicate['source_payload']['items']) == 2


def test_simulated_source_cannot_reenter_existing_chain(env):
    client, sessions = env
    eid, lid, _ = complete_chain(client)
    with sessions() as db:
        for row in db.query(ObservationRaw): row.source_system = 'MDC_WEB_OBS_VBU_SIMULATED'
        db.commit()
    for url, payload in [
        (f'/api/events/{eid}/link-observations', None),
        (f'/api/events/{eid}/features', None),
        (f'/api/events/{eid}/label-candidates', {'label_version': '2'}),
    ]:
        result = client.post(url, headers=OP, json=payload)
        assert result.status_code == 409 and result.json()['detail'] == 'simulated_source_not_allowed'
    result = checked(client.post('/api/datasets/DS1/validate', headers=OP))
    assert result['status'] == 'INVALID'
    assert client.post('/api/datasets/DS1/approve', headers=REVIEW).status_code == 409


def test_missing_raw_source_blocks_features(env):
    client, sessions = env
    eid, _, _ = complete_chain(client)
    with sessions() as db:
        db.query(ObservationRaw).delete(); db.commit()
    result = client.post(f'/api/events/{eid}/features', headers=OP)
    assert result.status_code == 409 and result.json()['detail'] == 'raw_observation_missing'
