"""A frozen technical audit cannot become current after alteration or snapshot change."""
import hashlib
import json
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes_lake_browser import router
from app.core.config import settings
from app.services import monthly_report_matching as matching
from app.services.station_classification import reference_records, resolve_scope


@pytest.fixture
def audit(tmp_path, monkeypatch):
    directory = tmp_path / '202607'
    directory.mkdir()
    packet = {'report_month': '2026-07', 'snapshot': 'verified-july',
              'publication_sha256': 'a' * 64,
              'source_summaries': [{'source': 'GD_OBS_ST_MONTHLY', 'station_count': 2}],
              'official_totals': {'public_count': 120, 'restricted_count': 20}}

    def publish(value):
        data = json.dumps(value).encode()
        (directory / 'publication-match.json').write_bytes(data)
        (directory / 'published.json').write_text(json.dumps({
            'report_month': '2026-07', 'sha256': hashlib.sha256(data).hexdigest()}), encoding='utf-8')

    publish(packet)
    monkeypatch.setattr(settings, 'MONTHLY_REPORT_MATCHING_ROOT', str(tmp_path))
    monkeypatch.setattr(matching.lake_browser, 'context', lambda: (Path('verified-july'), None))
    app = FastAPI()
    app.include_router(router)
    return TestClient(app), directory, packet, publish


def test_current_audit_selects_one_source_without_merging_counts(audit):
    client, _, _, _ = audit
    data = client.get('/api/lake/publication-comparison').json()
    assert data['audit_state'] == 'CURRENT' and data['approval_status'] == 'UNAPPROVED'
    assert data['selected_source_summary']['station_count'] == 2
    history = client.get('/api/lake/publication-comparison', params={'source': 'HISTORICAL_RECONCILED'}).json()
    assert history['selected_source_summary'] is None
    assert history['official_totals']['public_count'] == 120


def test_altered_record_is_rejected_instead_of_displayed(audit):
    client, directory, _, _ = audit
    (directory / 'publication-match.json').write_text('{}', encoding='utf-8')
    assert client.get('/api/lake/publication-comparison').status_code == 409


def test_older_snapshot_is_explicitly_stale(audit, monkeypatch):
    client, _, _, _ = audit
    monkeypatch.setattr(matching.lake_browser, 'context', lambda: (Path('new-snapshot'), None))
    data = client.get('/api/lake/publication-comparison').json()
    assert data['audit_state'] == 'STALE' and data['current_snapshot'] == 'new-snapshot'
    assert data['stale_note'] and data['approval_status'] == 'UNAPPROVED'


def test_wrong_month_cannot_reuse_valid_checksum(audit):
    client, _, packet, publish = audit
    publish({**packet, 'report_month': '2026-06'})
    assert client.get('/api/lake/publication-comparison').status_code == 409


def test_missing_month_and_invalid_source_remain_explicit(audit):
    client, _, _, _ = audit
    assert client.get('/api/lake/publication-comparison', params={'month': '2026-08'}).status_code == 404
    assert client.get('/api/lake/publication-comparison', params={'month': '../../outside'}).status_code == 422
    assert client.get('/api/lake/publication-comparison', params={'source': 'SIMULATED'}).status_code == 422


def test_july_reference_is_period_bound_and_does_not_mutate_registry(audit):
    _, _, packet, publish = audit
    record = {'station_id': 'DT_0042', 'station_name': '교본초', 'network_type': '해양관측소',
              'sea_area': '동해', 'latitude': 34.7047222222222, 'longitude': 128.306388888889}
    binding = {'station_code': record['station_id'], 'binding_status': 'COORDINATE_CORROBORATED_UNIQUE',
               'catalog_identity': {k: record[k] for k in ('station_name','network_type','sea_area','latitude','longitude')},
               'network_type': '해양관측소', 'sea_area': '남해', 'report_name': '교본초'}
    publish({**packet, 'station_references': [binding]})
    july = reference_records([record], '2026-07')[0]
    assert july['sea_area'] == '남해' and july['metadata_sea_area'] == '동해'
    assert july['reference_month'] == '2026-07'
    assert reference_records([record])[0]['sea_area'] == '동해'
    assert record['sea_area'] == '동해'
    changed = reference_records([{**record, 'longitude': 129.0}], '2026-07')[0]
    assert changed['sea_area'] == '동해' and changed['classification_basis'] == 'LEGACY_DB_REFERENCE_INPUT_CHANGED'


def test_ambiguous_binding_is_never_used_for_filtering(audit):
    _, _, packet, publish = audit
    from types import SimpleNamespace
    record = SimpleNamespace(station_id='DT_0042', station_name='교본초', network_type='해양관측소',
                             sea_area='동해', latitude=34.7047222222222, longitude=128.306388888889)
    class DB:
        def query(self,*args): return self
        def all(self): return [record]
    publish({**packet,'station_references':[{'station_code':'DT_0042','binding_status':'NAME_ONLY_CANDIDATE',
                                           'network_type':'해양관측소','sea_area':'남해'}]})
    assert resolve_scope(DB(), '해양관측소','남해','2026-07') == {'include':[]}
    assert resolve_scope(DB(), '해양관측소','동해','2026-07') == {'include':['DT_0042']}


def test_missing_report_coast_preserves_metadata_coast(audit):
    _, _, packet, publish = audit
    record = {'station_id':'HB_0001','station_name':'가상참조','network_type':'해양관측부이',
              'sea_area':'남해','latitude':34.0,'longitude':128.0}
    publish({**packet,'station_references':[{
        'station_code':record['station_id'],'binding_status':'COORDINATE_CORROBORATED_UNIQUE',
        'catalog_identity':dict(record),'network_type':record['network_type'],
        'sea_area':None,'report_name':record['station_name']}]})
    july = reference_records([record], '2026-07')[0]
    assert july['sea_area'] == '남해' and july['metadata_sea_area'] == '남해'
    assert july['reference_month'] == '2026-07' and record['sea_area'] == '남해'
