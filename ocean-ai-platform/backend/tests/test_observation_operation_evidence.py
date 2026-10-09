from contextlib import nullcontext
from datetime import datetime

import pytest
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.models.domain import OperationLog
from app.services.observation_operation_evidence import bulk_reader, evaluate_records, channel_evidence, EvidenceReadError

CUTOFF = '2026-07-09 15:41:20'
START = '2026-07-08 15:41:20'
STATION = 'SIM-STATION'


def record(**values):
    return dict(station_id=STATION, sensor_id='SIM-SENSOR',
                clock_basis='NATIVE_SIMULATION', available_at='2026-07-09 15:00:00', **values)


def incident(**changes):
    return dict(record(event_id='SIM-EVENT-1', event_start='2026-07-09 14:00:00', event_end=None,
                       status='OPEN', severity='ABNORMAL', version_available_at='2026-07-09 15:00:00'), **changes)


def test_unavailable_database_empty_table_and_absent_table_are_different():
    absent = bulk_reader(None, ['DT_0028'], CUTOFF, START)['DT_0028']
    assert absent['operations']['state'] == 'UNAVAILABLE'
    assert absent['operations']['matched_records'] is None
    engine = create_engine('sqlite://')
    OperationLog.__table__.create(engine)
    with Session(engine) as db:
        result = bulk_reader(db, ['DT_0028'], CUTOFF, START)['DT_0028']
        assert result['operations']['state'] == 'MISSING'
        assert result['operations']['matched_records'] == 0
        assert result['operations']['total_database_records'] == 0
        assert result['inspection']['state'] == 'TABLE_ABSENT'
        assert result['operations']['diagnostic_state'] is None


def test_reader_never_flushes_pending_writes_or_modifies_the_database():
    engine = create_engine('sqlite://')
    OperationLog.__table__.create(engine)
    statements = []
    event.listen(engine, 'before_cursor_execute', lambda conn, cursor, statement, params, context, many: statements.append(statement))
    with Session(engine, autoflush=True) as db:
        pending = OperationLog(station_id='DT_0028', event_time=datetime(2026, 7, 9, 14), event_type='ERROR')
        db.add(pending)
        result = bulk_reader(db, ['DT_0028'], CUTOFF, START)['DT_0028']
        assert result['operations']['matched_records'] == 0
        assert pending in db.new and pending.id is None
        assert not any(statement.lstrip().upper().startswith(('INSERT', 'UPDATE', 'DELETE')) for statement in statements)
        with db.no_autoflush:
            assert db.scalar(select(func.count()).select_from(OperationLog)) == 0


def test_database_failure_is_raised_without_credential_text_or_empty_success():
    class FailedSession:
        no_autoflush = nullcontext()
        def get_bind(self):
            raise OperationalError('connect', {}, RuntimeError('secret-password'))
    with pytest.raises(EvidenceReadError, match='OPERATION_EVIDENCE_QUERY_FAILED') as error:
        bulk_reader(FailedSession(), ['DT_0028'], CUTOFF, START)
    assert 'secret-password' not in str(error.value)


def test_unknown_native_timezone_and_mutable_current_status_cannot_be_backdated():
    db_record = dict(station_id='DT_0028', event_id='actual-current-event', event_start=datetime(2026, 7, 9, 14),
                     event_end=datetime(2026, 7, 9, 15), created_at=datetime(2026, 7, 9, 15), status='CLOSED', severity='ABNORMAL')
    result = evaluate_records({'event_registry': [db_record]}, ['DT_0028'], CUTOFF, START, source='LIVE_DB')['DT_0028']['event_registry']
    assert result['state'] == 'UNKNOWN' and result['diagnostic_state'] is None
    assert 'SOURCE_NATIVE_TIMEZONE_UNVERIFIED' in result['reasons']
    known_clock = evaluate_records({'event_registry': [db_record]}, ['DT_0028'], CUTOFF, START,
                                   source='LIVE_DB', native_timezone='UTC', database_timezone='UTC')['DT_0028']['event_registry']
    assert 'ASOF_VERSION_AVAILABILITY_UNVERIFIED' in known_clock['reasons']
    assert known_clock['eligible_records'] == 0


def test_inspection_exact_station_availability_and_window_are_all_required():
    valid = record(inspection_id='valid', report_date='2026-07-09 14:00:00', issue_found=True, follow_up_required=True)
    records = [valid, {**valid, 'inspection_id': 'future-event', 'report_date': '2026-07-10 00:00:00'},
               {**valid, 'inspection_id': 'late-arrival', 'available_at': '2026-10-09 00:00:00'},
               {**valid, 'inspection_id': 'old', 'report_date': '2026-07-01 00:00:00'},
               {**valid, 'inspection_id': 'wrong-station', 'station_id': 'OTHER-STATION'}]
    component = evaluate_records({'daily_inspection_report': records}, [STATION], CUTOFF, START)[STATION]['inspection']
    assert component['matched_records'] == 4 and component['eligible_records'] == 1
    assert component['rejected_records'] == 3 and component['diagnostic_state'] == 'WARNING'
    assert component['signal_reasons'] == ['INSPECTION_FOLLOW_UP_REQUIRED']


def test_recovery_clears_only_the_exact_event_and_same_sensor_after_start():
    recovery = record(id='recovery', event_type='RECOVERY', event_time='2026-07-09 15:00:00', resolution_of='SIM-EVENT-1',
                      diagnostic_state='NORMAL', signal_reason='EXPLICIT_SIMULATION_RECOVERY')
    for change in ({'resolution_of': 'unrelated'}, {'sensor_id': 'OTHER-SENSOR'}, {'event_time': '2026-07-09 13:00:00'}):
        result = evaluate_records({'event_registry': [incident()], 'operation_log': [{**recovery, **change}]},
                                  [STATION], CUTOFF, START)[STATION]
        assert len(result['event_registry']['active_events']) == 1
        assert result['event_registry']['diagnostic_state'] == 'ABNORMAL'
    result = evaluate_records({'event_registry': [incident()], 'operation_log': [recovery]}, [STATION], CUTOFF, START)[STATION]
    assert not result['event_registry']['active_events']
    assert result['event_registry']['diagnostic_state'] is None
    assert result['event_registry']['recovered_events'][0]['resolved_by_operation_id'] == 'recovery'


def test_future_record_version_and_future_resolution_do_not_clear_an_event():
    future = incident(version_available_at='2026-07-10 00:00:00')
    component = evaluate_records({'event_registry': [future]}, [STATION], CUTOFF, START)[STATION]['event_registry']
    assert component['eligible_records'] == 0 and 'POST_CUTOFF_RECORD_VERSION' in component['reasons']
    future_end = incident(event_end='2026-07-10 00:00:00', status='RESOLVED')
    component = evaluate_records({'event_registry': [future_end]}, [STATION], CUTOFF, START)[STATION]['event_registry']
    assert component['eligible_records'] == 0 and 'POST_CUTOFF_RESOLUTION' in component['reasons']


def test_simulation_qc_codebook_is_exact_and_cannot_be_applied_to_live_literals():
    qc = record(id='qc', timestamp_utc='2026-07-09 14:00:00', qc_flag_final='BAD', version_available_at='2026-07-09 15:00:00')
    mapping = {'GOOD': 'NORMAL', 'BAD': 'ABNORMAL'}
    result = evaluate_records({'qc_flag_history': [qc]}, [STATION], CUTOFF, START, qc_mapping=mapping)[STATION]
    assert result['qc_history']['diagnostic_state'] == 'ABNORMAL'
    assert result['qc_semantics']['state'] == 'KNOWN_SIMULATION'
    unknown = evaluate_records({'qc_flag_history': [{**qc, 'qc_flag_final': 'BAD '}]}, [STATION], CUTOFF, START, qc_mapping=mapping)[STATION]
    assert unknown['qc_history']['diagnostic_state'] is None
    with pytest.raises(ValueError, match='SIMULATION_CODEBOOK_CANNOT_INTERPRET_LIVE_QC'):
        evaluate_records({}, [STATION], CUTOFF, START, source='LIVE_DB', qc_mapping=mapping)


def test_default_normal_strings_in_inspection_and_raw_ok_are_not_normal_operation():
    inspect_record = record(inspection_id='inspection', report_date='2026-07-09 14:00:00', issue_found=False,
                            follow_up_required=False, equipment_status='NORMAL', communication_status='NORMAL', power_status='NORMAL')
    result = evaluate_records({'daily_inspection_report': [inspect_record]}, [STATION], CUTOFF, START)[STATION]
    assert result['inspection']['state'] == 'USABLE' and result['inspection']['diagnostic_state'] is None
    assert result['qc_semantics']['mapping'] == {} and result['qc_semantics']['state'] == 'UNKNOWN'
    with pytest.raises(ValueError, match='EXACT_NATIVE_CLOCK_REQUIRED'):
        evaluate_records({}, [STATION], CUTOFF+'+09:00', START)


def bound(evidence, sensor='SIM-SENSOR', item='WATER_TEMP', **overrides):
    options = dict(source_group='SIMULATION', source_qc_primary_field='source_qc_raw',
                   cutoff_native_literal=CUTOFF, window_start_native_literal=START)
    options.update(overrides)
    return channel_evidence(evidence, STATION, sensor, item, **options)


def test_channel_scope_does_not_copy_another_sensor_or_item_fault():
    normal = incident(event_id='matching-normal', severity='NORMAL', variable_code='WATER_TEMP')
    wrong_sensor = incident(event_id='other-sensor', sensor_id='OTHER-SENSOR', variable_code='WATER_TEMP')
    wrong_item = incident(event_id='other-item', variable_code='SALINITY')
    evidence = evaluate_records({'event_registry': [normal, wrong_sensor, wrong_item]}, [STATION], CUTOFF, START)
    selected = bound(evidence)['event_registry']
    assert selected['diagnostic_state'] == 'NORMAL'
    assert selected['eligible_records'] == 1
    assert selected['active_events'][0]['event_id'] == 'matching-normal'
    unknown = bound(evidence, sensor=None)['event_registry']
    assert unknown['state'] == 'UNKNOWN' and unknown['diagnostic_state'] is None
    assert 'PHYSICAL_SENSOR_IDENTITY_UNVERIFIED' in unknown['reasons']


def test_station_wide_inspection_is_allowed_but_sensor_specific_inspection_needs_binding():
    broad = record(inspection_id='station', report_date='2026-07-09 14:00:00', follow_up_required=True)
    broad['sensor_id'] = None
    specific = {**broad, 'inspection_id': 'specific', 'sensor_id': 'SIM-SENSOR'}
    evidence = evaluate_records({'daily_inspection_report': [broad, specific]}, [STATION], CUTOFF, START)
    selected = bound(evidence, sensor=None)['inspection']
    assert selected['eligible_records'] == 1 and selected['diagnostic_state'] == 'WARNING'
    assert selected['scope_unbound_records'] == 1


def test_display_record_limit_does_not_lose_a_matching_sensor_group():
    records = []
    for index in range(40):
        row = record(inspection_id=f'report-{index}', report_date=f'2026-07-09 14:{index:02d}:00',
                     diagnostic_state='ABNORMAL' if index >= 5 else 'NORMAL', signal_reason='EXPLICIT_SYNTHETIC_INSPECTION')
        row['sensor_id'] = 'OTHER-SENSOR' if index >= 5 else 'SIM-SENSOR'
        records.append(row)
    evidence = evaluate_records({'daily_inspection_report': records}, [STATION], CUTOFF, START)
    selected = bound(evidence)['inspection']
    assert selected['eligible_records'] == 5 and selected['diagnostic_state'] == 'NORMAL'
    assert selected['latest']['sensor_id'] == 'SIM-SENSOR'
    assert len(evidence[STATION]['inspection']['records']) == 25
    assert evidence[STATION]['inspection']['diagnostic_state'] == 'ABNORMAL'  # input unchanged


def test_recovered_event_scope_does_not_keep_its_former_abnormal_signal():
    recovery = record(id='recovery', event_type='RECOVERY', event_time='2026-07-09 15:00:00', resolution_of='SIM-EVENT-1')
    evidence = evaluate_records({'event_registry': [incident()], 'operation_log': [recovery]}, [STATION], CUTOFF, START)
    selected = bound(evidence)['event_registry']
    assert selected['diagnostic_state'] is None
    assert not selected['active_events'] and len(selected['recovered_events']) == 1


def test_recovery_outside_display_limit_is_still_used_in_complete_event_reconciliation():
    recovery = record(id='recovery', event_type='RECOVERY', event_time='2026-07-09 14:55:00', resolution_of='SIM-EVENT-1')
    operations = [recovery]
    operations.extend({**record(id=f'note-{i}', event_type='NOTE', event_time=f'2026-07-09 15:00:{i:02d}'),
                       'available_at': '2026-07-09 15:01:00'} for i in range(30))
    evidence = evaluate_records({'event_registry': [incident()], 'operation_log': operations}, [STATION], CUTOFF, START)
    assert len(evidence[STATION]['operations']['records']) == 25
    selected = bound(evidence)['event_registry']
    assert not selected['active_events']
    assert selected['recovered_events'][0]['derived_state'] == 'RECOVERED'


def test_qc_codebook_requires_exact_source_sensor_field_availability_and_effective_period():
    evidence = evaluate_records({}, [STATION], CUTOFF, START)[STATION]
    evidence['qc_semantics'] = dict(state='USABLE', source='SIMULATION', source_group='SIMULATION',
        station_code=STATION, physical_sensor_id='SIM-SENSOR', item_code='WATER_TEMP', field='source_qc_raw',
        clock_basis='NATIVE_SIMULATION', codebook_version='SIM-QC-v1', mapping={'G': 'GOOD', 'B': 'BAD'},
        effective_start='2026-07-01 00:00:00', effective_end='2026-08-01 00:00:00',
        available_at='2026-07-01 00:00:00', version_available_at='2026-07-01 00:00:00')
    assert bound(evidence)['qc_semantics']['state'] == 'USABLE'
    changes = [{'available_at': '2026-10-09 00:00:00'}, {'version_available_at': '2026-10-09 00:00:00'},
               {'effective_start': '2026-07-09 14:00:00'}, {'effective_end': CUTOFF},
               {'physical_sensor_id': 'OTHER-SENSOR'}, {'field': 'MQC_FLAG'}, {'source_group': 'GD_OBS_ST_MONTHLY'}]
    for change in changes:
        changed = {**evidence, 'qc_semantics': {**evidence['qc_semantics'], **change}}
        selected = bound(changed)['qc_semantics']
        assert selected['state'] == 'UNKNOWN' and selected['mapping'] == {}
    selected = bound(evidence, source_group='GD_OBS_ST_MONTHLY')
    assert selected['qc_semantics']['mapping'] == {}
    assert selected['inspection']['state'] == 'UNKNOWN'
    with pytest.raises(ValueError, match='EVIDENCE_EXACT_CUTOFF_MISMATCH'):
        bound(evidence, cutoff_native_literal='2026-07-09 15:42:20')
