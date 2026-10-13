"""Isolated actual-source-byte fixtures for system mapping and atomic bindings."""
import hashlib
import json
from datetime import datetime

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.models.domain import (ApprovalHistory, AuditLog, StationMetadata, SensorMetadata,
                               ObservationRaw, ObservationStandard, MDCItemMapping)
from app.models.source_contracts import SourceContractPacket, SourceContractDecision
from app.models.source_observation_binding import SourceObservationBinding
from app.services import source_auto_mapping as auto
from app.services import source_contract_authority as authority
from app.services.source_contract_snapshot import source_authority, DependencyError
from app.services.observation_mapping import map_item


@pytest.fixture
def case(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, 'SOURCE_AUTO_MAPPING_ENABLED', True)
    monkeypatch.setattr(settings, 'DATA_MODE', 'live')
    monkeypatch.setattr(authority, 'SOURCE_ROOT', tmp_path)
    folder = tmp_path / 'GR_OBS_ST_202607'
    folder.mkdir()
    rows = [dict(OBS_POST_ID='DT_TEST', OBS_ITEM_CODE=code,
                 OBS_TIME='2026-07-09 15:41:00', OBS_VALUE=value,
                 RECEIVE_TIME='2026-07-09 15:42:00', QC_FLAG=flag,
                 MQC_FLAG=None, FR_DEPTH=None, WATER_STEP=None, TO_DEPTH=None)
            for code,value,flag in [('WATER_TEMP','23.94',None), ('WIND_DIRECT','359.0',''),
                                    ('WIND_SPEED','5.2','G '), ('AIR_PRES','1008.0','1'),
                                    ('AIR_TEMP','27.2',None), ('SALINITY',None,None),
                                    ('GNSS_X','3727.0',None)]]
    pq.write_table(pa.Table.from_pylist(rows), folder / 'raw.parquet', row_group_size=2)
    original = tmp_path / 'deleted.csv'
    manifest = dict(status='VERIFIED', source_system='GR_OBS_ST', source_path=str(original),
                    source_size=1000, source_sha256='a'*64,
                    raw_path=str(folder / 'raw.parquet'),
                    raw_sha256=hashlib.sha256((folder / 'raw.parquet').read_bytes()).hexdigest(),
                    raw_rows=len(rows), csv_recount_rows=len(rows))
    (folder / 'manifest.json').write_text(json.dumps(manifest), encoding='utf8')
    engine = create_engine('sqlite://', connect_args={'check_same_thread':False}, poolclass=StaticPool)
    tables = (StationMetadata, SensorMetadata, ObservationRaw, ObservationStandard,
              MDCItemMapping, ApprovalHistory, SourceContractPacket, SourceContractDecision,
              SourceObservationBinding, AuditLog)
    for model in tables:
        model.__table__.create(engine)
    with Session(engine) as db:
        db.add(StationMetadata(station_id='DT_TEST', station_name='Synthetic isolated station'))
        db.commit()
        packet = auto.prepare_manifest(folder / 'manifest.json')
        yield tmp_path, folder, rows, packet, db


def approved(case):
    _, _, _, packet, db = case
    receipt, sha = auto.approve_manifest(db, packet)
    auto.adopt_mapping(db)
    db.commit()
    return receipt, sha


def batches(packet):
    return list(auto.selected_batches(packet, datetime(2026,7,9), datetime(2026,7,9,15,41,20), batch_size=2))


def test_system_approval_maps_all_core_items_with_exact_values_clock_flags_and_row_groups(case):
    _, _, _, packet, db = case
    receipt, sha = approved(case)
    counts = []
    for rows in batches(packet):
        counts.append(auto.ingest_batch(db, receipt, sha, rows))
        db.commit()
    assert sum(c['inserted_rows'] for c in counts) == 6
    assert db.query(ObservationRaw).count() == db.query(ObservationStandard).count() == db.query(SourceObservationBinding).count() == 6
    wind = db.query(ObservationStandard).filter_by(variable_code='WIND_DIRECT').one()
    assert wind.value_standard == 359 and wind.standard_unit == 'DEG'
    assert wind.timestamp_utc == datetime(2026,7,9,6,41)
    assert wind.receive_time == datetime(2026,7,9,6,42)
    assert wind.qc_flag == ''
    speed = db.query(ObservationRaw).filter_by(variable_code='WIND_SPEED').one()
    assert speed.qc_flag == 'G ' and speed.mqc_flag is None and speed.value_status == 'UNREVIEWED'
    binding = db.get(SourceObservationBinding, db.query(ObservationStandard).filter_by(variable_code='WIND_SPEED').one().observation_id)
    assert binding.source_row_locator == 'parquet_row_group=1;row_index=0'
    assert binding.bound_at_utc.utcoffset().total_seconds() == 0
    assert binding.payload['physical_sensor_id'] is None
    assert binding.payload['training_eligible'] is False
    assert binding.created_by == auto.SYSTEM_ID
    assert receipt['approval_receipt']['reviewer_role'] == 'system'
    assert receipt['packet']['source_availability_policy'] == 'VERIFIED_PRESERVED_TRANSFORM_ONLY'
    assert auto.summary(db)['registered_bindings'] == 6
    assert all(s.status == 'LOGICAL_SOURCE_CHANNEL' for s in db.query(SensorMetadata))
    assert db.query(ObservationStandard).filter_by(variable_code='GNSS_X').count() == 0
    assert db.query(ObservationStandard).filter_by(variable_code='SALINITY').one().value_standard is None


def test_replay_is_idempotent_for_approval_sensor_raw_standard_and_binding(case):
    _, _, _, packet, db = case
    receipt, sha = approved(case)
    for rows in batches(packet):
        auto.ingest_batch(db, receipt, sha, rows)
    db.commit()
    again, other_sha = auto.approve_manifest(db, packet)
    assert again == receipt and other_sha == sha
    counts = [auto.ingest_batch(db, receipt, sha, rows) for rows in batches(packet)]
    db.commit()
    assert sum(c['already_bound_rows'] for c in counts) == 6
    assert sum(c['inserted_rows'] for c in counts) == 0
    assert db.query(SourceContractPacket).count() == db.query(SourceContractDecision).count() == 1
    assert db.query(ApprovalHistory).count() == 2
    assert db.query(SensorMetadata).count() == db.query(SourceObservationBinding).count() == 6


def test_operational_system_receipt_does_not_grant_training_or_full_source_authority(case):
    _, _, _, _, db = case
    receipt, sha = approved(case)
    assert auto.verify_receipt(db, receipt, sha)['training_eligible'] is False
    with pytest.raises(DependencyError):
        source_authority(db, receipt, sha)
    with pytest.raises(authority.SourceContractError):
        authority.verify_approved_receipt(db, receipt, sha)


@pytest.mark.parametrize('field,value', [('OBS_VALUE','999'), ('QC_FLAG','BAD'), ('RECEIVE_TIME','2026-07-09 15:40:00')])
def test_supplied_literal_cannot_impersonate_a_verified_source_row(case, field, value):
    _, _, _, packet, db = case
    receipt, sha = approved(case)
    rows = batches(packet)[0]
    rows[0][field] = value
    with pytest.raises(authority.SourceContractError, match='AUTO_SOURCE_LITERAL_MISMATCH'):
        auto.ingest_batch(db, receipt, sha, rows)
    db.rollback()
    assert db.query(SourceObservationBinding).count() == db.query(ObservationStandard).count() == 0


def test_changed_parquet_and_revoked_approval_fail_closed(case):
    _, folder, _, packet, db = case
    receipt, sha = approved(case)
    db.get(SourceContractPacket, packet['contract_id']).status = 'REVOKED'
    db.commit()
    with pytest.raises(authority.SourceContractError, match='AUTO_SOURCE_APPROVAL_REVOKED'):
        auto.ingest_batch(db, receipt, sha, batches(packet)[0])
    db.get(SourceContractPacket, packet['contract_id']).status = 'APPROVED'
    db.commit()
    with (folder / 'raw.parquet').open('ab') as handle:
        handle.write(b'tampered')
    with pytest.raises(authority.SourceContractError):
        auto.verify_receipt(db, receipt, sha)


def test_disabled_policy_and_unregistered_station_cannot_write(case, monkeypatch):
    _, _, _, packet, db = case
    monkeypatch.setattr(settings, 'SOURCE_AUTO_MAPPING_ENABLED', False)
    with pytest.raises(authority.SourceContractError, match='SOURCE_AUTO_MAPPING_DISABLED'):
        auto.approve_manifest(db, packet)
    assert db.query(SourceContractPacket).count() == 0
    monkeypatch.setattr(settings, 'SOURCE_AUTO_MAPPING_ENABLED', True)
    receipt, sha = approved(case)
    db.query(StationMetadata).delete()
    db.commit()
    counts = auto.ingest_batch(db, receipt, sha, batches(packet)[0])
    db.commit()
    assert counts['quarantined_rows'] == 2 and counts['inserted_rows'] == 0
    assert db.query(SourceObservationBinding).count() == 0


def test_source_bounds_include_cutoff_and_do_not_include_future_rows(case):
    _, _, _, packet, _ = case
    assert batches(packet)
    assert list(auto.selected_batches(packet, datetime(2026,7,9), datetime(2026,7,9,15,40,59))) == []
    with pytest.raises(authority.SourceContractError):
        auto.window('2026-07-09T15:41:20+09:00')


def test_explicit_source_identifier_registration_does_not_invent_physical_metadata(case):
    _, _, _, packet, db = case
    receipt, sha = approved(case)
    db.query(StationMetadata).delete()
    db.commit()
    counts = auto.ingest_batch(db, receipt, sha, batches(packet)[0], register_source_identifiers=True)
    db.commit()
    station = db.query(StationMetadata).one()
    assert station.station_id == station.station_name
    assert station.status == 'SOURCE_IDENTIFIER_ONLY'
    assert station.latitude is station.longitude is station.network_type is station.install_date is None
    assert counts['registered_source_identifiers'] == 1 and counts['inserted_rows'] == 2
    assert db.query(SourceObservationBinding).count() == 2
    replay = auto.ingest_batch(db, receipt, sha, batches(packet)[0], register_source_identifiers=True)
    assert replay.get('registered_source_identifiers', 0) == 0 and replay['already_bound_rows'] == 2


def test_atomic_ingest_refuses_changed_preexisting_unbound_observation(case):
    _, _, _, packet, db = case
    receipt, sha = approved(case)
    rows = batches(packet)[0]
    raw, standard, _ = auto.source_record(rows[0], packet)
    db.add(ObservationStandard(**(standard | {'value_standard':999})))
    db.commit()
    with pytest.raises(authority.SourceContractError, match='AUTO_EXISTING_OBSERVATION_CONTENT_CONFLICT'):
        auto.ingest_batch(db, receipt, sha, rows)
    db.rollback()
    assert db.query(SourceObservationBinding).count() == db.query(ObservationRaw).count() == 0


def test_replay_detects_mutated_bound_numeric_records(case):
    _, _, _, packet, db = case
    receipt, sha = approved(case)
    rows = batches(packet)[0]
    auto.ingest_batch(db, receipt, sha, rows)
    db.commit()
    db.query(ObservationStandard).filter_by(variable_code='WATER_TEMP').one().value_standard = 999
    db.commit()
    with pytest.raises(authority.SourceContractError, match='AUTO_EXISTING_OBSERVATION_CONTENT_CONFLICT'):
        auto.ingest_batch(db, receipt, sha, rows)
    db.rollback()


def test_api_reports_system_scope_and_receipt_but_requires_reviewer_for_revocation(case, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.api import routes_source_contracts as routes
    _, _, _, packet, db = case
    receipt, sha = approved(case)
    app = FastAPI()
    app.include_router(routes.router)
    app.dependency_overrides[routes.get_db] = lambda: db
    monkeypatch.setattr(settings,'API_IDENTITIES',{'op':{'token':'isolated-op','role':'operator'},
                                                 'reviewer':{'token':'isolated-review','role':'reviewer'}})
    with TestClient(app) as client:
        base = '/api/source-contracts'
        assert client.get(base).json()['packets'][0]['approval_mode'] == 'SYSTEM_POLICY'
        assert client.get(base+'/'+packet['contract_id']+'/receipt').headers['X-Content-SHA256'] == sha
        assert client.get(base+'/'+packet['contract_id']).json()['readiness_errors'] == []
        payload = dict(expected_packet_sha256=receipt['packet_sha256'], decision='REVOKED', comment='Isolated revoke')
        endpoint = base+'/'+packet['contract_id']+'/decision'
        assert client.post(endpoint,json=payload).status_code == 401
        assert client.post(endpoint,json=payload,headers={'Authorization':'Bearer isolated-op'}).status_code == 403
        result = client.post(endpoint,json=payload,headers={'Authorization':'Bearer isolated-review'})
        assert result.status_code == 200 and result.json()['status'] == 'REVOKED'
    with pytest.raises(authority.SourceContractError,match='AUTO_SOURCE_APPROVAL_REVOKED'):
        auto.verify_receipt(db,receipt,sha)


@pytest.mark.parametrize('code,expected', [('WIND_DIRECT',('WIND_DIRECT','DEG')),
                                         ('AIR_TEMP2',('AIR_TEMP','C')),
                                         ('MAX_WAVE_HEIGHT',('MAX_WAVE_HEIGHT','m')),
                                         ('MAX_WAVE_PERIOD',('MAX_WAVE_PERIOD','s')),
                                         ('WAVE_DIRECT',('WAVE_DIRECT','DEG')),
                                         ('GNSS_X',('GNSS_X','UNKNOWN'))])
def test_shared_mapping_keeps_period_height_and_direction_dimensions(code, expected):
    assert map_item(code)[:2] == expected
