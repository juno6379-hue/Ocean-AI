"""Read-only identity, period and event review; candidate grain is never approval.

Raw station/item codes are source identifiers, not canonical facility/sensor IDs.
Date bounds retain their precision. A held month, provision date or inventory
installation month cannot establish a physical sensor's operating interval.
"""
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
import calendar
import hashlib
import json
import re
from pathlib import Path
from app.services.source_contract_review import exact_scope_key as _shared_scope_key

VERSION = 'identity-period-event-review-1'
GRAIN = ('source_group', 'station_code', 'item_code', 'depth_step', 'depth_from', 'depth_to', 'month')
DECISIONS = ('station_dictionary_decision', 'item_dictionary_decision', 'source_identity_decision',
             'unit_reference_decision', 'unit_application_decision', 'sensor_decision',
             'period_decision', 'timezone_decision', 'qc_evidence_decision', 'qc_approval_decision')


def verify_document_alias(original_path, expected_sha256, canonical_path, allowed_root):
    """Prove bytes at an explicitly proposed preservation location, without edits.

    The recorded original path remains provenance. A matching name/size or an
    earlier migration receipt is insufficient; SHA256 is re-read at use time.
    Approval of the document's meaning/period is deliberately not returned.
    """
    if not re.fullmatch(r'[0-9a-f]{64}', str(expected_sha256)):
        raise ValueError('INVALID_SOURCE_SHA256')
    path, root = Path(canonical_path).resolve(), Path(allowed_root).resolve()
    if not path.is_relative_to(root) or path.is_symlink() or not path.is_file():
        raise ValueError('CANONICAL_SOURCE_NOT_ALLOWED_OR_MISSING')
    before = path.stat()
    with path.open('rb') as stream:
        actual = hashlib.file_digest(stream, 'sha256').hexdigest()
    after = path.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise ValueError('CANONICAL_SOURCE_CHANGED_DURING_READ')
    if actual != expected_sha256:
        raise ValueError('CANONICAL_SOURCE_HASH_MISMATCH')
    return {'original_recorded_path': str(original_path), 'canonical_preservation_path': str(path),
            'source_sha256': actual, 'bytes': after.st_size, 'mtime_ns': after.st_mtime_ns,
            'checked_at': datetime.now(timezone.utc).isoformat(), 'status': 'CANONICAL_ALIAS_HASH_VERIFIED',
            'approval_status': 'UNAPPROVED', 'meaning_or_period_approval': False}


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
        separators=(',', ':'), default=str, allow_nan=False).encode('utf-8')).hexdigest()


def array(value):
    if value is None or value == '':
        return []
    parsed = json.loads(value) if isinstance(value, str) else value
    if not isinstance(parsed, list):
        raise ValueError('EVIDENCE_LIST_REQUIRED')
    return parsed


def month(value):
    if isinstance(value, (date, datetime)):
        return value.strftime('%Y-%m')
    if not isinstance(value, str):
        raise ValueError('MONTH_OR_VALID_ISO_DATE_REQUIRED')
    if re.fullmatch(r'\d{4}-\d{2}', value):
        datetime.strptime(value, '%Y-%m')
        return value
    if re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
        return date.fromisoformat(value).strftime('%Y-%m')
    if re.match(r'^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}', value):
        return datetime.fromisoformat(value.replace('Z', '+00:00')).strftime('%Y-%m')
    raise ValueError('MONTH_OR_VALID_ISO_DATE_REQUIRED')


def grain(row):
    return {key: month(row[key]) if key == 'month' else row.get(key) for key in GRAIN}


def candidate_id(row):
    return 'channel-month:' + digest({'grain_version': VERSION, **grain(row)})


def exact_scope_key(row):
    """Shared cross-agent key: canonical month and depth NULL/value/type retained."""
    return _shared_scope_key(grain(row))


def rehydrate_report_table(table):
    """Expand only physically merged PDF cells, retaining their source bounding box.

    A bare empty/NULL cell is never blindly filled from the preceding row. A
    spanning source cell must cover the new row's top boundary at the same column.
    """
    result, previous = [], {}
    for i, values in enumerate(table['rows']):
        row, evidence, errors = list(values), [], []
        row_top = table['row_bboxes'][i][1]
        for j, value in enumerate(values):
            cell = table['cells'][i][j]
            if value is not None and cell is not None:
                previous[j] = (value, cell, i)
                evidence.append({'column': j, 'source_row': i, 'bbox': cell, 'kind': 'EXPLICIT_CELL'})
            elif value is None:
                old = previous.get(j)
                if old and old[1][1] <= row_top < old[1][3] - .01:
                    row[j] = old[0]
                    evidence.append({'column': j, 'source_row': old[2], 'bbox': old[1], 'kind': 'SPANNING_CELL'})
                else:
                    errors.append('EMPTY_UNMERGED_CELL:' + str(j))
        result.append({'source_row': i, 'values': row, 'cell_provenance': evidence, 'validation_errors': errors})
    return result


def _reported_date_token(raw, context_year):
    raw = raw.strip().replace('`', '').replace("'", '')
    parts = [int(x) for x in raw.split('.') if x.strip()]
    explicit = False
    if len(parts) == 3:
        year, mon, day = parts
        year = year + 2000 if year < 100 else year
        explicit = True
        val, precision = date(year, mon, day).isoformat(), 'DAY'
    elif len(parts) == 2 and parts[0] >= 20:
        year, mon = parts
        year = year + 2000 if year < 100 else year
        explicit = True
        val, precision = f'{year:04}-{mon:02}', 'MONTH'
        date_bounds(val, 'MONTH')
    elif len(parts) == 2:
        mon, day = parts
        val, precision = date(context_year, mon, day).isoformat(), 'DAY'
    else:
        raise ValueError('REPORTED_DATE_TOKEN_UNRESOLVED')
    return {'value': val, 'precision': precision,
            'year_evidence': 'EXPLICIT_REPORT_TOKEN' if explicit else 'REPORT_CONTEXT_YEAR_CANDIDATE',
            'raw': raw, 'timezone': None, 'utc': None}


def reported_date_candidates(text_value, context_year):
    """Keep condition intervals, QC-processing intervals and action dates apart.

    Roles are lexical candidates supported by the exact statement context. An
    unknown phrase remains unclassified. Omitted years use an explicit caller
    report-context candidate; neither year nor boundary semantics is approval.
    """
    text_value = text_value or ''
    results = []
    for match in re.finditer(r'\(([^()]*)\)', text_value):
        body = match.group(1)
        if not re.search(r'\d{1,4}\.\d{1,2}', body):
            continue
        prefix = text_value[:match.start()].split('→')[-1].strip()
        if '오측처리' in prefix:
            role = 'REPORTED_QC_PROCESSING_INTERVAL'
        elif any(k in prefix for k in ('세척', '정비', '교체', '점검', '복구', '제거', '리셋', '재설치',
                                      '정상화', '재설정', '재연결', '차단해제', '조치', '수정', '전원 직결')):
            role = 'REPORTED_ACTION_TIME'
        elif any(k in prefix for k in ('고장', '이상', '손상', '지연', '결측', '방전', '의심', '편차',
                                      '품질저하', '감도 하락', '위치 이탈', '소손')):
            role = 'REPORTED_CONDITION_INTERVAL'
        else:
            role = 'UNCLASSIFIED_REPORTED_DATE_CANDIDATE'
        for part in body.split(','):
            found = re.findall(r"[`']?\d{1,4}\.\d{1,2}(?:\.\d{1,2})?", part)
            entry = {'role': role, 'raw_parenthetical': body, 'raw_segment': part.strip(),
                     'statement_context': prefix, 'reported_start': None, 'reported_end': None,
                     'open_end_reported': '지속' in part, 'endpoint_policy': 'UNAPPROVED',
                     'status': 'CANDIDATE_DATE_ROLE_NOT_APPROVED'}
            try:
                if not found:
                    raise ValueError('DATE_TOKEN_MISSING')
                entry['reported_start'] = _reported_date_token(found[0], context_year)
                if len(found) > 1:
                    entry['reported_end'] = _reported_date_token(found[1], int(entry['reported_start']['value'][:4]))
                    if entry['reported_start']['value'] > entry['reported_end']['value']:
                        raise ValueError('DATE_RANGE_REVERSED')
                elif '~' not in part:
                    entry['reported_end'] = dict(entry['reported_start'])
                entry['validation_errors'] = []
            except ValueError as e:
                entry['validation_errors'] = [str(e)]
            results.append(entry)
    return results


def date_bounds(raw, precision):
    """Inclusive date bounds, not an invented exact event time or sensor period."""
    if precision.upper() == 'YEAR':
        if len(raw) != 4:
            raise ValueError('DATE_PRECISION_MISMATCH')
        year = int(raw)
        return date(year, 1, 1).isoformat(), date(year, 12, 31).isoformat()
    if precision.upper() == 'MONTH':
        if len(raw) != 7:
            raise ValueError('DATE_PRECISION_MISMATCH')
        year, mon = map(int, raw.split('-'))
        return date(year, mon, 1).isoformat(), date(year, mon, calendar.monthrange(year, mon)[1]).isoformat()
    if precision.upper() == 'DAY':
        value = date.fromisoformat(raw)
        return value.isoformat(), value.isoformat()
    raise ValueError('DATE_PRECISION_REQUIRED')


def utc(value):
    result = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError('TIMEZONE_REQUIRED')
    return result.astimezone(timezone.utc)


def evidence_time_errors(evidence, origin):
    """Only explicitly available input can be used at a forecast origin.

    A retrospective label may be reviewed after the event, but is never an input
    at the event time. Neither report_date nor file mtime substitutes available_at.
    """
    errors = []
    if evidence.get('role') != 'FEATURE_INPUT':
        return ['NOT_AN_ASOF_FEATURE_INPUT']
    try:
        available = utc(evidence['available_at'])
        if available > utc(origin):
            errors.append('POST_ORIGIN_EVIDENCE')
        # A date-only report uses its document's local date; UTC midnight
        # comparison would falsely reject normal KST/UTC date-boundary cases.
        if evidence.get('report_created_at') and utc(evidence['report_created_at']) > available:
            errors.append('AVAILABLE_BEFORE_REPORTED_DATE')
    except (KeyError, TypeError, ValueError):
        errors.append('AVAILABLE_AT_OR_ORIGIN_UNVERIFIED')
    if not re.fullmatch(r'[0-9a-f]{64}', str(evidence.get('source_sha256', ''))) or not evidence.get('locator'):
        errors.append('SOURCE_LOCATOR_MISSING')
    return sorted(set(errors))


def sensor_binding_errors(bindings):
    """Reject missing/reversed/unapproved periods and overlapping exact scopes.

    Adjacent [start,end) intervals are permitted. Different source namespaces,
    depth bins and items are never collapsed into a single sensor scope.
    """
    issues, groups = [], defaultdict(list)
    for i, binding in enumerate(bindings):
        ident = binding.get('record_id', str(i))
        errors = []
        required = ('source_group', 'station_code', 'source_item_code', 'physical_sensor_id',
                    'sensor_episode_id', 'unit', 'standard_variable')
        if any(not binding.get(k) for k in required):
            errors.append('EXACT_SENSOR_SCOPE_MISSING')
        if binding.get('approval_status') != 'APPROVED' or not binding.get('approval_id'):
            errors.append('SENSOR_BINDING_UNAPPROVED')
        try:
            start, end = utc(binding['effective_start']), utc(binding['effective_end'])
            if start >= end:
                raise ValueError('INVALID')
            scope = tuple(binding.get(k) for k in ('source_group', 'station_code', 'source_item_code'))
            scope += (digest(binding.get('depth')),)
            groups[scope].append((start, end, ident))
        except (KeyError, ValueError, TypeError):
            errors.append('SENSOR_INTERVAL_UNVERIFIED')
        for error in errors:
            issues.append({'record_id': ident, 'error': error})
    for rows in groups.values():
        rows.sort()
        for i, (start, end, ident) in enumerate(rows):
            for other_start, other_end, other in rows[i + 1:]:
                if other_start >= end:
                    break
                if start < other_end:
                    issues.append({'record_id': ident, 'other_record_id': other, 'error': 'OVERLAPPING_SENSOR_PERIODS'})
    return issues


def report_event_links(rows, events):
    """Reconcile every listed event ID against exact raw codes and month bounds.

    Wildcard station-wide claims remain broad candidates and cannot identify a
    defective sensor. A report month match is not exact event interval approval.
    """
    by_id = {e['id']: e for e in events}
    links, errors = [], []
    for row in rows:
        for event_id in array(row.get('event_ids')):
            event = by_id.get(event_id)
            issue = None
            if event is None:
                issue = 'EVENT_REFERENCE_MISSING'
            elif row['station_code'] not in array(event.get('station_codes')):
                issue = 'EVENT_STATION_MISMATCH'
            elif row['item_code'] not in array(event.get('item_codes')) and '*' not in array(event.get('item_codes')):
                issue = 'EVENT_ITEM_MISMATCH'
            elif not event.get('period_start') or not event.get('period_end_inclusive'):
                issue = 'EVENT_PERIOD_MISSING'
            else:
                try:
                    start_raw, end_raw = str(event['period_start']), str(event['period_end_inclusive'])
                    start = date_bounds(start_raw, 'MONTH')[0] if re.fullmatch(r'\d{4}-\d{2}', start_raw) else date.fromisoformat(start_raw).isoformat()
                    end = date_bounds(end_raw, 'MONTH')[1] if re.fullmatch(r'\d{4}-\d{2}', end_raw) else date.fromisoformat(end_raw).isoformat()
                    if start > end:
                        issue = 'EVENT_PERIOD_REVERSED'
                    elif not month(start_raw) <= month(row['month']) <= month(end_raw):
                        issue = 'EVENT_MONTH_MISMATCH'
                except (TypeError, ValueError):
                    issue = 'EVENT_PERIOD_INVALID'
            if issue:
                errors.append({'candidate_id': candidate_id(row), 'exact_scope_key': exact_scope_key(row), 'event_id': event_id, 'error': issue})
            else:
                links.append({'candidate_id': candidate_id(row), 'exact_scope_key': exact_scope_key(row), 'event_id': event_id,
                    'source_sha256': event.get('sha256'), 'locator': event.get('locator'),
                    'match_kind': 'STATION_WIDE_MONTH_CANDIDATE' if '*' in array(event.get('item_codes')) else 'EXACT_RAW_CODE_MONTH_CANDIDATE',
                    'physical_sensor_id': None, 'event_start_utc': None, 'event_end_utc': None,
                    'report_date': None, 'available_at': None, 'approval_status': 'UNAPPROVED',
                    'training_eligible': False})
    return {'links': links, 'validation_errors': errors}


def review_channels(rows, snapshot_sha256, snapshot_id):
    """Freeze an exhaustively enumerated review queue, not a training dataset."""
    decisions, reasons = {key: Counter() for key in DECISIONS}, Counter()
    candidates, seen, duplicate_ids = [], set(), []
    source_groups, cross_source = Counter(), defaultdict(list)
    for row in rows:
        key = candidate_id(row)
        if key in seen:
            duplicate_ids.append(key)
        seen.add(key)
        blockers = []
        for decision in DECISIONS:
            value = row.get(decision)
            decisions[decision][str(value)] += 1
            if value != '해소':
                blockers.append(decision.upper() + '_UNRESOLVED')
        for field in ('physical_sensor_id', 'standard_unit', 'timezone_name', 'valid_from', 'valid_to'):
            if not row.get(field):
                blockers.append(field.upper() + '_MISSING')
        if row.get('approval_status') != 'APPROVED':
            blockers.append('IDENTIFIER_PERIOD_EVENT_APPROVAL_MISSING')
        # No accepted row-level dataset membership/approval/split is supplied to
        # this service. Resolved reference decisions cannot silently create it.
        blockers += ['ROW_MEMBERSHIP_UNFROZEN', 'SPLIT_UNREVIEWED']
        blockers = sorted(set(blockers))
        reasons.update(blockers)
        item = {'candidate_id': key, 'exact_scope_key': exact_scope_key(row), **grain(row), 'held_rows': row.get('held_rows'),
                'first_clock_raw': str(row.get('first_clock')) if row.get('first_clock') else None,
                'last_clock_raw': str(row.get('last_clock')) if row.get('last_clock') else None,
                'physical_sensor_id': row.get('physical_sensor_id'), 'sensor_episode_id': None,
                'standard_variable': None, 'unit': row.get('standard_unit'),
                'timezone_name': row.get('timezone_name'), 'effective_start': row.get('valid_from'),
                'effective_end': row.get('valid_to'), 'event_ids': array(row.get('event_ids')),
                'management_event_ids': array(row.get('management_event_ids')),
                'installation_claim_ids': array(row.get('installation_claim_ids')),
                'physical_sensor_candidate_ids': array(row.get('physical_sensor_candidate_ids')),
                'evidence_hash': digest(row), 'validation_errors': blockers,
                'approval_status': 'UNAPPROVED', 'training_eligible': False, 'split': 'UNASSIGNED'}
        candidates.append(item)
        source_groups[row['source_group']] += 1
        overlap_key = tuple(grain(row)[k] for k in GRAIN if k != 'source_group')
        cross_source[overlap_key].append((row['source_group'], key))
    cross_source_candidates = [{'grain': dict(zip([k for k in GRAIN if k != 'source_group'], key)),
                               'candidate_ids': [r[1] for r in group],
                               'source_groups': sorted(set(r[0] for r in group)),
                               'decision': 'DO_NOT_MERGE_VALUE_TIMESTAMP_PROVENANCE_RECONCILIATION_REQUIRED'}
                              for key, group in cross_source.items() if len(set(r[0] for r in group)) > 1]
    membership_hash = digest(sorted((x['candidate_id'], x['evidence_hash']) for x in candidates))
    receipt = {'schema_version': VERSION, 'contract_id': 'identity-review:' + membership_hash,
               'status': 'DRAFT_BLOCKED', 'snapshot_id': snapshot_id, 'snapshot_sha256': snapshot_sha256,
               'coverage_complete': not duplicate_ids, 'coverage_role': 'REVIEW_QUEUE_ENUMERATION_ONLY',
               'approval_complete': False, 'training_eligible': False, 'eligible_members': 0,
               'split_status': 'UNASSIGNED_REQUIRES_PROTOCOL_AND_REVIEW', 'membership_grain': list(GRAIN),
               'candidate_count': len(candidates), 'unique_candidate_count': len(seen),
               'source_groups': dict(source_groups), 'decision_counts': {k: dict(v) for k, v in decisions.items()},
               'blocker_counts': dict(reasons), 'duplicate_candidate_ids': sorted(set(duplicate_ids)),
               'candidate_membership_hash': membership_hash,
               'exact_scope_key_schema': 'source-contract-review-v1/type-sensitive-canonical-month',
               'exact_scope_keys_hash': digest(sorted(x['exact_scope_key'] for x in candidates)),
               'cross_source_overlap_candidate_count': len(cross_source_candidates),
               'validation_errors': ['IDENTIFIER_PERIOD_EVENT_APPROVAL_MISSING', 'ROW_MEMBERSHIP_UNFROZEN', 'SPLIT_UNREVIEWED'],
               'note': 'Held rows can overlap across source groups. No source code is promoted to a canonical physical ID.'}
    return receipt, candidates, cross_source_candidates


def split_leakage_errors(members, split_order=('TRAIN', 'VALIDATION', 'TEST')):
    """Validate a supplied split; never invent assignment/ratio/holdout bounds."""
    errors, entities, identifiers, split_times = [], defaultdict(set), set(), defaultdict(list)
    for member in members:
        mid = member.get('member_id')
        if not mid or mid in identifiers:
            errors.append('MEMBER_ID_MISSING_OR_DUPLICATED')
        identifiers.add(mid)
        split = member.get('split')
        if split not in split_order:
            errors.append('SPLIT_UNASSIGNED_OR_UNKNOWN')
        for field in ('sensor_episode_id', 'event_id', 'source_record_identity', 'document_family_id'):
            value = member.get(field)
            if value:
                entities[(field, value)].add(split)
        for field in ('event_id', 'sensor_episode_id', 'source_record_identity'):
            if not member.get(field):
                errors.append(field.upper() + '_UNVERIFIED')
        try:
            origin, start, end, available = map(utc, (member['origin'], member['feature_window_start'],
                                                      member['feature_window_end'], member['available_at']))
            if not start <= end <= origin or available > origin:
                errors.append('FEATURE_FUTURE_LEAKAGE')
            target = utc(member['target_time'])
            if target <= origin:
                errors.append('TARGET_NOT_AFTER_ORIGIN')
            split_times[split].append((origin, target))
            if not utc(member['sensor_effective_start']) <= start <= end < utc(member['sensor_effective_end']):
                errors.append('FEATURE_CROSSES_SENSOR_EPISODE')
            if utc(member['target_time']) >= utc(member['sensor_effective_end']):
                errors.append('TARGET_CROSSES_SENSOR_EPISODE')
        except (KeyError, ValueError, TypeError):
            errors.append('TIME_OR_SENSOR_EPISODE_UNVERIFIED')
    for (field, ident), splits in entities.items():
        if len(splits) > 1:
            errors.append(field.upper() + '_CROSSES_SPLITS:' + str(ident))
    # This helper's supplied split order is a chronological forecasting contract.
    # Station/event separation alone does not detect future TRAIN observations.
    for i, earlier in enumerate(split_order):
        for later in split_order[i + 1:]:
            if split_times[earlier] and split_times[later]:
                if max(t[1] for t in split_times[earlier]) >= min(t[0] for t in split_times[later]):
                    errors.append('CHRONOLOGICAL_SPLIT_LEAKAGE:' + earlier + ':' + later)
    return sorted(set(errors))
