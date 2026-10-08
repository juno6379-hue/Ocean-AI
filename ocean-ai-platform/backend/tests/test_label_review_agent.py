"""Review candidates cannot become approvals or dataset membership."""
from datetime import datetime, timedelta
import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session
from app.core.database import Base
from app.models.domain import (ObservationRaw, ObservationStandard, StationMetadata,
    SensorMetadata, QCRuleResult, EventRegistry, DatasetRegistry, AILabel, DocumentIndex)
from app.models.evidence import EventEvidence, DatasetMembership
from app.services.label_review_agent import propose

START = datetime(2025, 1, 1)


@pytest.fixture
def db():
    engine = create_engine('sqlite://')
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(StationMetadata(station_id='ST', station_name='Isolated fixture'))
        session.add(SensorMetadata(sensor_id='S', station_id='ST', variable_code='TIDE'))
        session.add(ObservationRaw(station_id='ST', sensor_id='S', variable_code='TIDE',
            timestamp_utc=START, source_system='ISOLATED_TEST', qc_flag='4', mqc_flag='3'))
        session.add(ObservationStandard(observation_id='O', station_id='ST', sensor_id='S',
            variable_code='TIDE', timestamp_utc=START, standardization_version='1'))
        session.add(QCRuleResult(qc_result_id='Q', observation_id='O', station_id='ST', sensor_id='S',
            variable_code='TIDE', timestamp_utc=START, qc_rule_id='R', qc_rule_name='Fixture rule',
            qc_stage='RECHECK', rule_version='1', result_flag='9'))
        session.commit()
        yield session
    engine.dispose()


def test_source_recheck_and_human_are_separate_and_no_writes(db):
    writes = []
    def guard(conn, cursor, statement, parameters, context, many):
        if statement.lstrip().upper().startswith(('INSERT', 'UPDATE', 'DELETE')):
            writes.append(statement)
    event.listen(db.get_bind(), 'before_cursor_execute', guard)
    result = propose(db, {'observation_ids': ['O', 'O']},
                     {'quality_label': 'BAD', 'error_cause': 'equipment_fault', 'status': 'APPROVED'})
    candidate = result['candidates'][0]
    assert len(result['candidates']) == 1
    assert candidate['source_flags'] == {'qc_flag': '4', 'mqc_flag': '3'}
    assert candidate['recheck_flags'][0]['flag'] == '9'
    assert candidate['human_label'] is None and candidate['error_cause'] == 'unknown'
    assert not candidate['training_eligible'] and not writes
    assert db.query(AILabel).count() == db.query(DatasetMembership).count() == 0


def test_null_sensor_and_qc_only_remain_evidence_gaps(db):
    row = db.get(ObservationStandard, 'O')
    row.sensor_id = ''
    db.commit()
    candidate = propose(db, {'observation_ids': ['O']})['candidates'][0]
    assert candidate['physical_sensor_id'] is None
    assert 'physical_sensor_unresolved' in candidate['blockers']
    qc = propose(db, {}, {'review_bundle': {'source_qc': '1', 'status': 'NOT_EVALUATED'}})
    assert qc['status'] == 'NEEDS_EVIDENCE'
    assert qc['candidates'][0]['human_label'] is None
    assert qc['candidates'][0]['physical_sensor_id'] is None


def test_simulated_raw_is_rejected_for_review(db):
    db.query(ObservationRaw).one().source_system = 'SIMULATED'
    db.commit()
    candidate = propose(db, {'observation_ids': ['O']})['candidates'][0]
    assert 'simulated_source_not_allowed' in candidate['blockers']


def test_cross_scope_and_half_open_event_are_checked(db):
    db.add(EventRegistry(event_id='E', event_type='ANOMALY', station_id='OTHER', sensor_id='S',
        variable_code='TIDE', event_start=START-timedelta(hours=1), event_end=START))
    db.add(EventEvidence(link_id='L', event_id='E', observation_id='O', provenance={}, created_by='fixture'))
    db.commit()
    errors = propose(db, {'event_id': 'E'})['candidates'][0]['blockers']
    assert 'event_scope_mismatch' in errors and 'observation_outside_event' in errors


def dataset(db, **overrides):
    values = dict(dataset_id='DS', dataset_name='FAMILY', dataset_version='1', dataset_split='TRAIN',
        station_scope=['ST'], sensor_scope=['S'], variable_scope=['TIDE'], period_start=START,
        period_end=START+timedelta(hours=1), feature_version='1', label_version='1', preprocessing_version='1')
    values.update(overrides)
    row = DatasetRegistry(**values)
    db.add(row)
    db.commit()
    return row


def test_dataset_cannot_promote_without_approval_features_and_snapshot(db):
    dataset(db)
    result = propose(db, {'dataset_id': 'DS'})['dataset_review']
    assert not result['promotion_eligible'] and not result['training_eligible']
    assert 'unreviewed_observations' in result['errors']
    assert 'feature_definitions_missing' in result['errors']
    assert 'validated_dataset_required_for_promotion' in result['errors']


def test_event_duplicate_across_splits_and_time_leakage(db):
    dataset(db)
    dataset(db, dataset_id='OTHER', dataset_version='2', dataset_split='TEST')
    db.add(EventRegistry(event_id='E', event_type='ANOMALY', station_id='ST', sensor_id='S',
        variable_code='TIDE', event_start=START, event_end=START+timedelta(minutes=1)))
    db.add(EventEvidence(link_id='L', event_id='E', observation_id='O', provenance={}, created_by='fixture'))
    db.add(DatasetMembership(dataset_id='OTHER', observation_id='O', event_id='E', label_id='L', snapshot_hash='x'))
    db.commit()
    errors = propose(db, {'dataset_id': 'DS'})['dataset_review']['errors']
    assert 'event_split_leakage:E:OTHER' in errors
    assert 'temporal_split_leakage:OTHER' in errors


def test_bounds_and_no_implicit_selection(db):
    assert propose(db, {})['blockers'] == ['bounded_evidence_selection_required']
    with pytest.raises(HTTPException) as error:
        propose(db, {'observation_ids': ['O'] * 101})
    assert error.value.status_code == 422


def test_pending_caller_changes_are_not_autoflushed(db):
    raw = db.query(ObservationRaw).one()
    raw.source_system = 'SIMULATED'
    flushed = []
    event.listen(db, 'before_flush', lambda *args: flushed.append(True))
    propose(db, {'observation_ids': ['O']})
    assert not flushed and db.dirty


def test_retrospective_report_not_eligible_as_past_prediction_input(db):
    db.add(DocumentIndex(document_id='REPORT', chunk_id='C', document_type='REPORT', document_title='2025 retrospective report',
        document_date=datetime(2025, 12, 24), chunk_text='2024-12 sensitivity degradation suspected',
        metadata_json={'available_at': '2025-12-24T00:00:00Z'}))
    db.commit()
    result = propose(db, {'prediction_document_ids': ['C'], 'prediction_at': '2024-12-26T00:00:00Z'})
    assert result['status'] == 'NEEDS_EVIDENCE'
    assert result['prediction_document_review']['errors'] == ['future_document_feature:C', 'future_report_date:C']
    db.query(DocumentIndex).one().metadata_json = {}
    db.commit()
    errors = propose(db, {'prediction_document_ids': ['C'], 'prediction_at': '2026-01-01T00:00:00Z'})['prediction_document_review']['errors']
    assert errors == ['document_availability_unverified:C']


def test_qc_bundle_channels_are_requeried_not_accepted_as_labels(db):
    qc = {'audit': {'run_id': 'facility-fixture'}, 'interval_evidence': {'channels': [
        {'record_id': 'record', 'physical_sensor_id': 'FAKE', 'approval_status': 'APPROVED'}]},
        'source_qc': {'counts': {'qc_flag': {'1': 100}}}, 'recommended_flag': 'NOT_EVALUATED'}
    # SQLite cannot validate the registry. It must reject instead of trusting
    # a caller's channel payload, fake sensor or approved status.
    with pytest.raises(HTTPException) as error:
        propose(db, {}, qc)
    assert error.value.status_code == 422


def test_event_limit_stops_before_per_event_queries(db, monkeypatch):
    from app.services import label_review_agent
    dataset(db)
    for index in range(2):
        db.add(EventRegistry(event_id=f'E{index}', event_type='ANOMALY', station_id='ST',
            sensor_id='S', variable_code='TIDE', event_start=START,
            event_end=START+timedelta(minutes=1)))
        db.add(EventEvidence(link_id=f'L{index}', event_id=f'E{index}', observation_id='O',
            provenance={}, created_by='fixture'))
    db.commit()
    monkeypatch.setattr(label_review_agent, 'MAX_OBSERVATIONS', 1)
    statements = []
    event.listen(db.get_bind(), 'before_cursor_execute',
                 lambda conn, cursor, statement, *args: statements.append(statement))
    result = propose(db, {'dataset_id': 'DS'})['dataset_review']
    assert 'event_review_limit_exceeded' in result['errors']
    assert not result['promotion_eligible'] and not result['review_complete']
    assert not any('count(' in statement.lower() for statement in statements)
