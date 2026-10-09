"""Read-only, as-of inspection and event evidence, separate from raw QC literals.

An empty table is missing evidence, not an all-clear report. Current mutable
event/QC fields cannot describe a past version without a version availability
time. Native source clocks are never assigned UTC or KST by this reader.
"""
from collections import Counter, defaultdict
from copy import deepcopy
from datetime import datetime, timezone
import math
import re
from zoneinfo import ZoneInfo

from sqlalchemy import func, inspect, select
from sqlalchemy.exc import SQLAlchemyError

from app.models.domain import (
    DailyInspectionReport, EventRegistry, OperationLog,
    QCFlagHistory, QualityCollectionReport,
)

SCHEMA = 'observation-operation-evidence-1'
MODELS = {
    'daily_inspection_report': ('inspection', DailyInspectionReport, 'report_date'),
    'operation_log': ('operations', OperationLog, 'event_time'),
    'quality_collection_report': ('quality_reports', QualityCollectionReport, 'period_end'),
    'qc_flag_history': ('qc_history', QCFlagHistory, 'timestamp_utc'),
    'event_registry': ('event_registry', EventRegistry, 'event_start'),
}
SEVERITY = {'NORMAL': 0, 'WARNING': 1, 'ABNORMAL': 2}
MAX_ROWS = 20_000


class EvidenceReadError(RuntimeError):
    """The query failed; callers must not turn this into an empty ledger."""


def _native(value):
    if isinstance(value, datetime):
        if value.tzinfo is not None:
            raise ValueError('NATIVE_CLOCK_OFFSET_NOT_ALLOWED')
        return value
    if not isinstance(value, str) or not re.fullmatch(
            r'\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?', value):
        raise ValueError('EXACT_NATIVE_CLOCK_REQUIRED')
    return datetime.fromisoformat(value)


def _json(value):
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json(item) for item in value]
    return value


def _clock(value, record, source, native_timezone, database_timezone, utc_field=False):
    if value is None:
        raise ValueError('RECORD_CLOCK_MISSING')
    if source == 'SIMULATION':
        if record.get('clock_basis') != 'NATIVE_SIMULATION':
            raise ValueError('SIMULATION_CLOCK_BASIS_REQUIRED')
        return _native(value)
    if native_timezone is None:
        raise ValueError('SOURCE_NATIVE_TIMEZONE_UNVERIFIED')
    try:
        stamp = value if isinstance(value, datetime) else datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        target_zone = timezone.utc if native_timezone == 'UTC' else ZoneInfo(native_timezone)
        if stamp.tzinfo is None:
            clock_zone = 'UTC' if utc_field else database_timezone
            if clock_zone is None:
                raise ValueError('DATABASE_CLOCK_TIMEZONE_UNVERIFIED')
            stamp = stamp.replace(tzinfo=timezone.utc if clock_zone == 'UTC' else ZoneInfo(clock_zone))
        return stamp.astimezone(target_zone).replace(tzinfo=None)
    except (TypeError, KeyError):
        raise ValueError('RECORD_CLOCK_INVALID') from None


def _blank(state='MISSING', reason='NO_STATION_RECORDS'):
    return dict(state=state, matched_records=0 if state == 'MISSING' else None,
                eligible_records=0, rejected_records=0, reasons=[reason],
                diagnostic_state=None, signal_reasons=[], latest=None, records=[], excluded=[],
                scope_groups=[], excluded_scope_groups=[])


def _identity(record):
    return str(next((record[key] for key in ('event_id', 'inspection_id', 'report_id', 'id')
                     if record.get(key) is not None), 'UNIDENTIFIED'))


def _record_errors(table, record, cutoff, window_start, source, native_timezone, database_timezone):
    errors, clocks = [], {}
    time_field = MODELS[table][2]
    # created_at describes DB recording, not the observation or document date.
    available = record.get('available_at') if source == 'SIMULATION' else record.get('created_at')
    try:
        clocks['available_at'] = _clock(available, record, source, native_timezone, database_timezone)
        if clocks['available_at'] > cutoff:
            errors.append('POST_CUTOFF_AVAILABLE_RECORD')
        clocks['event_time'] = _clock(record.get(time_field), record, source, native_timezone,
                                      database_timezone, utc_field=table in {'qc_flag_history', 'event_registry', 'operation_log'})
        if clocks['event_time'] > cutoff:
            errors.append('POST_CUTOFF_EVENT')
        if table not in {'event_registry', 'operation_log'} and clocks['event_time'] < window_start:
            errors.append('OUTSIDE_DIAGNOSTIC_WINDOW')
        if clocks['available_at'] < clocks['event_time']:
            errors.append('AVAILABLE_BEFORE_EVENT')
    except ValueError as error:
        errors.append(str(error))
    if table in {'event_registry', 'qc_flag_history'}:
        if source != 'SIMULATION' or record.get('version_available_at') is None:
            # Both tables are updated by existing APIs without an as-of version ledger.
            errors.append('ASOF_VERSION_AVAILABILITY_UNVERIFIED')
        else:
            try:
                version = _clock(record['version_available_at'], record, source, native_timezone, database_timezone)
                if version > cutoff:
                    errors.append('POST_CUTOFF_RECORD_VERSION')
                if 'available_at' in clocks and version < clocks['available_at']:
                    errors.append('VERSION_BEFORE_AVAILABLE_RECORD')
            except ValueError as error:
                errors.append(str(error))
    if table == 'quality_collection_report':
        try:
            start = _clock(record.get('period_start'), record, source, native_timezone, database_timezone)
            end = clocks['event_time']
            if start > end:
                errors.append('REPORT_PERIOD_REVERSED')
            if start < window_start:
                errors.append('REPORT_AGGREGATE_EXTENDS_BEFORE_DIAGNOSTIC_WINDOW')
            counts = [record.get(key) for key in ('total_expected_count', 'total_received_count',
                      'qc_normal_count', 'qc_suspect_count', 'qc_bad_count', 'qc_missing_count')]
            if any(value is not None and (type(value) is not int or value < 0) for value in counts):
                errors.append('REPORT_COUNTS_INVALID')
            rate = record.get('collection_rate')
            if rate is not None and (not isinstance(rate, (float, int)) or not math.isfinite(rate) or not 0 <= rate <= 100):
                errors.append('REPORT_RATE_INVALID')
        except (ValueError, KeyError) as error:
            errors.append(str(error))
    if table == 'event_registry':
        end = record.get('event_end')
        if end is not None:
            try:
                clocks['event_end'] = _clock(end, record, source, native_timezone, database_timezone, utc_field=True)
                if clocks.get('event_time') is not None and clocks['event_end'] <= clocks['event_time']:
                    errors.append('EVENT_PERIOD_REVERSED')
                if clocks['event_end'] > cutoff:
                    errors.append('POST_CUTOFF_RESOLUTION')
                if clocks.get('available_at') is not None and clocks['available_at'] < clocks['event_end']:
                    errors.append('RESOLUTION_NOT_YET_AVAILABLE')
            except ValueError as error:
                errors.append(str(error))
        if record.get('status') in {'RESOLVED', 'CLOSED'} and end is None:
            errors.append('RESOLVED_EVENT_END_MISSING')
        if record.get('status') not in {'OPEN', 'RESOLVED', 'CLOSED'}:
            errors.append('EVENT_STATUS_UNMAPPED')
    return sorted(set(errors)), clocks


def _signal(table, record, clocks, source, qc_mapping):
    if source == 'SIMULATION' and record.get('diagnostic_state') in SEVERITY and record.get('signal_reason'):
        return record['diagnostic_state'], [str(record['signal_reason'])]
    if table == 'daily_inspection_report' and record.get('follow_up_required') is True:
        return 'WARNING', ['INSPECTION_FOLLOW_UP_REQUIRED']
    if table == 'quality_collection_report':
        reasons = [key.upper() + '_POSITIVE' for key in ('qc_suspect_count', 'qc_bad_count', 'qc_missing_count')
                   if isinstance(record.get(key), int) and record[key] > 0]
        return ('WARNING' if reasons else None), reasons
    if table == 'event_registry':
        ended = clocks.get('event_end') is not None
        if ended:
            return None, []
        if record.get('severity') in SEVERITY:
            return record['severity'], ['EXPLICIT_ACTIVE_EVENT_SEVERITY']
    if table == 'qc_flag_history' and source == 'SIMULATION':
        flag = record.get('qc_flag_final')
        if flag in qc_mapping:
            return qc_mapping[flag], ['SIMULATION_CODEBOOK_LITERAL:' + str(flag)]
    return None, []


def _scope_groups(entries, active_event_ids=None):
    """Complete compact groups; the 25-record display limit never changes scope."""
    groups = {}
    for entry in entries:
        record = entry['record']
        sensor = record.get('sensor_id')
        item = record.get('source_item_code', record.get('variable_code'))
        key = (sensor, item)
        if key not in groups:
            groups[key] = dict(sensor_id=sensor, item_code=item, eligible_records=0,
                               diagnostic_state=None, signal_reasons=[], latest=_json(record),
                               latest_native_clock=entry['clocks']['event_time'].isoformat(' '))
        group = groups[key]
        group['eligible_records'] += 1
        signal = entry['signal']
        if active_event_ids is not None and record.get('event_id') not in active_event_ids:
            signal = None
        if signal is not None:
            old = group['diagnostic_state']
            if old is None or SEVERITY[signal] > SEVERITY[old]:
                group['diagnostic_state'] = signal
            group['signal_reasons'] = sorted(set(group['signal_reasons'] + entry['signal_reasons']))
    return list(groups.values())


def _excluded_scope_groups(excluded):
    groups = {}
    for record in excluded:
        key = (record.get('sensor_id'), record.get('item_code'))
        if key not in groups:
            groups[key] = dict(sensor_id=key[0], item_code=key[1], rejected_records=0, reason_counts={})
        group = groups[key]
        group['rejected_records'] += 1
        counts = Counter(group['reason_counts'])
        counts.update(record['reasons'])
        group['reason_counts'] = dict(counts)
    return list(groups.values())


def evaluate_records(records_by_table, station_codes, cutoff_native_literal, window_start_literal,
                     *, source='SIMULATION', native_timezone=None, database_timezone=None, qc_mapping=None):
    """Evaluate an explicit ledger without writes; synthetic input stays labelled.

    SIMULATION needs NATIVE_SIMULATION clocks and explicit available_at/version
    times. Live DB rows use created_at recording time and never inherit the
    simulation QC codebook. Inspection defaults do not prove normal operation.
    """
    if source not in {'SIMULATION', 'LIVE_DB'}:
        raise ValueError('EVIDENCE_SOURCE_REQUIRED')
    cutoff, start = _native(cutoff_native_literal), _native(window_start_literal)
    if start > cutoff:
        raise ValueError('DIAGNOSTIC_WINDOW_REVERSED')
    stations = list(dict.fromkeys(station_codes))
    if any(not isinstance(code, str) or not code or len(code) > 100 for code in stations):
        raise ValueError('EXACT_STATION_CODE_REQUIRED')
    if set(records_by_table) - set(MODELS):
        raise ValueError('EVIDENCE_TABLE_UNRECOGNIZED')
    qc_mapping = qc_mapping or {}
    if qc_mapping and source != 'SIMULATION':
        raise ValueError('SIMULATION_CODEBOOK_CANNOT_INTERPRET_LIVE_QC')
    if any(not isinstance(key, str) or state not in SEVERITY for key, state in qc_mapping.items()):
        raise ValueError('SIMULATION_CODEBOOK_INVALID')
    result = {code: dict(schema_version=SCHEMA, station_id=code, source=source, approval_status='DEFERRED',
                       as_of_native=cutoff.isoformat(' '), window_start_native=start.isoformat(' '),
                       clock_basis='NATIVE_SIMULATION' if source == 'SIMULATION' else (
                           'EXPLICIT_DATABASE_TO_NATIVE_CLOCK' if native_timezone is not None and database_timezone is not None
                           else 'DATABASE_WITH_SOURCE_TIMEZONE_UNVERIFIED'),
                       **{component: _blank() for component, _, _ in MODELS.values()},
                       qc_semantics=dict(state='KNOWN_SIMULATION' if qc_mapping else 'UNKNOWN', mapping=dict(qc_mapping),
                           reasons=[] if qc_mapping else ['SOURCE_SPECIFIC_QC_CODEBOOK_EFFECTIVE_PERIOD_MISSING']))
              for code in stations}
    grouped = defaultdict(list)
    for table, rows in records_by_table.items():
        for record in rows:
            station = record.get('station_id')
            if station not in result:
                continue
            grouped[(station, table)].append(dict(record))
    validated = {}
    for (station, table), records in grouped.items():
        component = result[station][MODELS[table][0]]
        component.update(state='UNKNOWN', matched_records=len(records), reasons=[])
        valid, excluded, reasons = [], [], Counter()
        for record in records:
            errors, clocks = _record_errors(table, record, cutoff, start, source, native_timezone, database_timezone)
            if errors:
                reasons.update(errors)
                excluded.append(dict(record_id=_identity(record), sensor_id=record.get('sensor_id'),
                                     item_code=record.get('source_item_code', record.get('variable_code')), reasons=errors))
                continue
            signal, signal_reasons = _signal(table, record, clocks, source, qc_mapping)
            valid.append(dict(record=record, clocks=clocks, signal=signal, signal_reasons=signal_reasons))
        valid.sort(key=lambda entry: (entry['clocks']['event_time'], _identity(entry['record'])), reverse=True)
        validated[(station, table)] = valid
        component.update(state='USABLE' if valid else 'UNKNOWN', eligible_records=len(valid),
                         rejected_records=len(excluded), reasons=sorted(reasons), reason_counts=dict(reasons),
                         records=[_json(entry['record']) for entry in valid[:25]], excluded=excluded[:25],
                         latest=_json(valid[0]['record']) if valid else None,
                         scope_groups=_scope_groups(valid), excluded_scope_groups=_excluded_scope_groups(excluded))
        signals = [entry['signal'] for entry in valid if entry['signal'] is not None]
        component['diagnostic_state'] = max(signals, key=SEVERITY.get) if signals else None
        component['signal_reasons'] = sorted({reason for entry in valid for reason in entry['signal_reasons']})
        if table == 'event_registry':
            component['active_events'] = [_json(entry['record']) for entry in valid if entry['clocks'].get('event_end') is None]
            component['recovered_events'] = [_json(entry['record']) for entry in valid if entry['clocks'].get('event_end') is not None]
    # Explicit recovery can close exactly its own event, never an unrelated sensor.
    for station in stations:
        operations, events = result[station]['operations'], result[station]['event_registry']
        active = events.get('active_events', [])
        recovered = events.get('recovered_events', [])
        for operation_entry in reversed(validated.get((station, 'operation_log'), [])):
            record = operation_entry['record']
            if record.get('event_type') != 'RECOVERY' or not record.get('resolution_of'):
                continue
            target = next((event for event in active if event.get('event_id') == record['resolution_of']), None)
            if target is None or record.get('sensor_id') != target.get('sensor_id'):
                continue
            event_time = _clock(record['event_time'], record, source, native_timezone, database_timezone, utc_field=True)
            event_start = _clock(target['event_start'], target, source, native_timezone, database_timezone, utc_field=True)
            if event_time < event_start:
                continue
            active.remove(target)
            recovered.append({**target, 'derived_state': 'RECOVERED',
                              'resolved_by_operation_id': _identity(record), 'recovery_time': _json(record['event_time'])})
        signals = [event['severity'] for event in active if event.get('severity') in SEVERITY]
        events['diagnostic_state'] = max(signals, key=SEVERITY.get) if signals else None
        if not signals:
            events['signal_reasons'] = []
        events['active_events'], events['recovered_events'] = active, recovered
        events['scope_groups'] = _scope_groups(validated.get((station, 'event_registry'), []),
                                                {event['event_id'] for event in active})
    return result


def _qc_semantics_for_channel(semantics, station_code, physical_sensor_id, item_code,
                              source_group, field, cutoff, window_start):
    """Synthetic codebooks are technical test contracts, never a live QC fallback."""
    semantics = deepcopy(semantics or {})
    if not semantics.get('mapping'):
        return semantics
    errors = []
    expected = dict(source='SIMULATION', source_group=source_group, station_code=station_code,
                    physical_sensor_id=physical_sensor_id, item_code=item_code, field=field,
                    clock_basis='NATIVE_SIMULATION')
    if source_group != 'SIMULATION':
        errors.append('SIMULATION_CODEBOOK_CANNOT_INTERPRET_LIVE_QC')
    if physical_sensor_id is None:
        errors.append('QC_PHYSICAL_SENSOR_IDENTITY_UNVERIFIED')
    if any(semantics.get(key) != value for key, value in expected.items()):
        errors.append('QC_CODEBOOK_EXACT_SCOPE_MISMATCH')
    if not isinstance(semantics.get('codebook_version'), str) or not semantics['codebook_version']:
        errors.append('QC_CODEBOOK_VERSION_MISSING')
    mapping = semantics.get('mapping')
    if not isinstance(mapping, dict) or any(not isinstance(key, str) or value not in {
            'GOOD', 'SUSPECT', 'BAD', 'MISSING', 'UNKNOWN'} for key, value in mapping.items()):
        errors.append('QC_CODEBOOK_LITERAL_MAPPING_INVALID')
    try:
        start, end = _native(semantics['effective_start']), _native(semantics['effective_end'])
        available, version = _native(semantics['available_at']), _native(semantics['version_available_at'])
        if not start <= window_start <= cutoff < end:
            errors.append('QC_CODEBOOK_EFFECTIVE_PERIOD_MISMATCH')
        if available > cutoff or version > cutoff:
            errors.append('POST_CUTOFF_QC_CODEBOOK')
        if version < available:
            errors.append('QC_VERSION_BEFORE_AVAILABLE_CODEBOOK')
    except (ValueError, KeyError):
        errors.append('QC_CODEBOOK_EXACT_CLOCKS_REQUIRED')
    if errors:
        return dict(state='UNKNOWN', mapping={}, reasons=sorted(set(errors)), source=semantics.get('source'))
    semantics['state'] = 'USABLE'
    return semantics


def channel_evidence(evidence, station_code, physical_sensor_id, item_code=None, *,
                     source_group=None, source_qc_primary_field=None,
                     cutoff_native_literal=None, window_start_native_literal=None):
    """Bind evidence to a channel without copying another sensor's diagnosis."""
    entry = evidence.get(station_code) if station_code in evidence else evidence
    if not isinstance(entry, dict) or entry.get('station_id') != station_code:
        raise ValueError('EVIDENCE_EXACT_STATION_MISMATCH')
    result = deepcopy(entry)
    cutoff = _native(cutoff_native_literal or entry['as_of_native'])
    start = _native(window_start_native_literal or entry['window_start_native'])
    if cutoff != _native(entry['as_of_native']) or start != _native(entry['window_start_native']):
        raise ValueError('EVIDENCE_EXACT_CUTOFF_MISMATCH')
    result['physical_sensor_id'], result['item_code'] = physical_sensor_id, item_code
    if (entry.get('source') == 'SIMULATION') != (source_group == 'SIMULATION'):
        for component, _, _ in MODELS.values():
            result[component] = _blank('UNKNOWN', 'EVIDENCE_SOURCE_SCOPE_MISMATCH')
        result['qc_semantics'] = dict(state='UNKNOWN', mapping={}, reasons=['EVIDENCE_SOURCE_SCOPE_MISMATCH'])
        return result
    for component, _, _ in MODELS.values():
        original = entry[component]
        if original['matched_records'] in (None, 0):
            continue
        selected, selected_excluded, unbound, item_unbound = [], [], 0, 0
        for group in original.get('scope_groups', []):
            sensor, item = group.get('sensor_id'), group.get('item_code')
            if sensor is not None and physical_sensor_id is None:
                unbound += group['eligible_records']
                continue
            if sensor is not None and sensor != physical_sensor_id:
                continue
            if item is not None and item_code is None:
                item_unbound += group['eligible_records']
                continue
            if item is not None and item != item_code:
                continue
            selected.append(group)
        for group in original.get('excluded_scope_groups', []):
            sensor, item = group.get('sensor_id'), group.get('item_code')
            if sensor is not None and physical_sensor_id is None:
                unbound += group['rejected_records']
                continue
            if sensor is not None and sensor != physical_sensor_id:
                continue
            if item is not None and item_code is None:
                item_unbound += group['rejected_records']
                continue
            if item is not None and item != item_code:
                continue
            selected_excluded.append(group)
        signals = [group['diagnostic_state'] for group in selected if group['diagnostic_state'] is not None]
        target = result[component]
        selected_count = sum(group['eligible_records'] for group in selected)
        target['station_matched_records'] = original['matched_records']
        target['eligible_records'] = selected_count
        target['scope_groups'] = selected
        target['diagnostic_state'] = max(signals, key=SEVERITY.get) if signals else None
        target['signal_reasons'] = sorted({reason for group in selected for reason in group['signal_reasons']})
        target['scope_unbound_records'] = unbound
        target['item_unbound_records'] = item_unbound
        if unbound:
            target['reasons'] = sorted(set(target['reasons'] + ['PHYSICAL_SENSOR_IDENTITY_UNVERIFIED']))
        if item_unbound:
            target['reasons'] = sorted(set(target['reasons'] + ['SOURCE_ITEM_IDENTITY_UNVERIFIED']))
        def matches(record):
            sensor = record.get('sensor_id')
            item = record.get('source_item_code', record.get('variable_code', record.get('item_code')))
            return (sensor is None or (physical_sensor_id is not None and sensor == physical_sensor_id)) and (
                item is None or (item_code is not None and item == item_code))
        target['records'] = [record for record in original['records'] if matches(record)]
        target['excluded'] = [record for record in original['excluded'] if matches(record)]
        target['excluded_scope_groups'] = selected_excluded
        target['rejected_records'] = sum(group['rejected_records'] for group in selected_excluded)
        scoped_reasons = Counter()
        for group in selected_excluded:
            scoped_reasons.update(group['reason_counts'])
        if unbound:
            scoped_reasons['PHYSICAL_SENSOR_IDENTITY_UNVERIFIED'] += unbound
        if item_unbound:
            scoped_reasons['SOURCE_ITEM_IDENTITY_UNVERIFIED'] += item_unbound
        target['reason_counts'], target['reasons'] = dict(scoped_reasons), sorted(scoped_reasons)
        target['matched_records'] = selected_count + target['rejected_records']
        target['latest'] = max(selected, key=lambda group: group['latest_native_clock'])['latest'] if selected else None
        if selected_count:
            target['state'] = 'USABLE'
        elif unbound or item_unbound or target['rejected_records']:
            target['state'] = 'UNKNOWN'
        else:
            target['state'] = 'MISSING'
            target['reasons'] = sorted(set(target['reasons'] + ['NO_MATCHING_SENSOR_OR_ITEM_EVIDENCE']))
        for key in ('active_events', 'recovered_events'):
            if key in original:
                target[key] = [record for record in original[key] if matches(record)]
    result['qc_semantics'] = _qc_semantics_for_channel(entry.get('qc_semantics'), station_code,
        physical_sensor_id, item_code, source_group, source_qc_primary_field, cutoff, start)
    return result


def bulk_reader(db, station_codes, cutoff_native_literal, window_start_literal,
                *, native_timezone=None, database_timezone=None):
    """Bulk SELECT only. Missing tables and no-record tables are distinct states."""
    stations = list(dict.fromkeys(station_codes))
    result = evaluate_records({}, stations, cutoff_native_literal, window_start_literal,
                              source='LIVE_DB', native_timezone=native_timezone, database_timezone=database_timezone)
    if db is None:
        for station in stations:
            for component, _, _ in MODELS.values():
                result[station][component] = _blank('UNAVAILABLE', 'DATABASE_SESSION_UNAVAILABLE')
        return result
    records, counts, absent = {}, {}, []
    try:
        with db.no_autoflush:
            inspector = inspect(db.get_bind())
            for table, (component, model, _) in MODELS.items():
                if not inspector.has_table(table):
                    absent.append(component)
                    continue
                total = db.scalar(select(func.count()).select_from(model))
                matched = dict(db.execute(select(model.station_id, func.count()).where(
                    model.station_id.in_(stations)).group_by(model.station_id)).all()) if stations else {}
                if sum(matched.values()) > MAX_ROWS:
                    raise EvidenceReadError('OPERATION_EVIDENCE_ROW_LIMIT_EXCEEDED')
                rows = db.scalars(select(model).where(model.station_id.in_(stations))).all() if stations else []
                records[table] = [{column.name: getattr(row, column.name) for column in model.__table__.columns} for row in rows]
                counts[component] = dict(total_database_records=total, station_matched_records=matched)
    except SQLAlchemyError:
        # Do not expose connection credentials or silently produce an empty ledger.
        raise EvidenceReadError('OPERATION_EVIDENCE_QUERY_FAILED') from None
    result = evaluate_records(records, stations, cutoff_native_literal, window_start_literal,
                              source='LIVE_DB', native_timezone=native_timezone, database_timezone=database_timezone)
    for station in stations:
        for component in absent:
            result[station][component] = _blank('TABLE_ABSENT', 'EVIDENCE_TABLE_NOT_PRESENT')
        for component, count in counts.items():
            result[station][component]['total_database_records'] = count['total_database_records']
            result[station][component]['matched_records'] = count['station_matched_records'].get(station, 0)
    return result
