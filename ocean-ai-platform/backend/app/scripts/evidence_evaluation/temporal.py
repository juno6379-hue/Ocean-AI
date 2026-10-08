"""근거 기반 기간 후보와 평가 적격성. 날짜 후보를 운영 승인으로 승격하지 않는다."""
from datetime import datetime, timedelta
import calendar
import hashlib
import json
import re

VERSION = 'evidence-evaluation-1.0'


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    default=str).encode()).hexdigest()


def date_bounds(raw):
    """문서 날짜의 가능한 경계. 월/일 정밀도를 임의의 정확 시각으로 바꾸지 않는다."""
    if re.fullmatch(r'\d{4}-\d{2}-\d{2}', raw):
        lower = datetime.strptime(raw, '%Y-%m-%d')
        return lower, lower + timedelta(days=1), 'day'
    if re.fullmatch(r'\d{4}-\d{2}', raw):
        lower = datetime.strptime(raw, '%Y-%m')
        return lower, lower + timedelta(days=calendar.monthrange(lower.year, lower.month)[1]), 'month'
    raise ValueError('UNSUPPORTED_DATE_PRECISION')


def sensor_period_candidates(events):
    """같은 관측소·장비 표현·serial의 교체 설치/회수만 짝짓는다. 추출 검토가 필수다."""
    result = []
    for start in events:
        if start['event_type'] != 'SENSOR_REPLACEMENT':
            continue
        serial = re.search(r'→\s*([A-Za-z0-9-]+)', start.get('source_excerpt', ''))
        if not serial:
            continue
        serial = serial.group(1)
        ends = [e for e in events if e['event_type'] == 'SENSOR_REMOVAL'
                and e['station_id'] == start['station_id']
                and e.get('equipment_expression') == start.get('equipment_expression')
                and re.search(r's/n\s*[:：]\s*' + re.escape(serial) + r'(?![A-Za-z0-9])',
                              e.get('source_excerpt', ''), re.I)
                and e['date_text'] > start['date_text']]
        # 회수 후보가 여러 개이면 임의 선택하지 않고 모호성을 남긴다.
        for end in ends:
            lo, hi, _ = date_bounds(start['date_text'])
            elo, ehi, _ = date_bounds(end['date_text'])
            result.append({
                'period_id': digest([start['event_id'], end['event_id']]),
                'period_kind': 'SENSOR_DEPLOYMENT', 'station_claim': start['station_id'],
                'equipment_expression': start.get('equipment_expression'), 'serial_claim': serial,
                'start_lower': lo.isoformat(), 'start_upper': hi.isoformat(),
                'end_lower': elo.isoformat(), 'end_upper': ehi.isoformat(),
                'start_assertion': start['event_id'], 'end_assertion': end['event_id'],
                'status': 'CANDIDATE', 'timezone': None, 'physical_sensor_id': None,
                'blockers': ['DOCUMENT_REVIEW_REQUIRED', 'STATION_IDENTITY_UNAPPROVED',
                             'CHANNEL_ITEM_BINDING_UNAPPROVED', 'TIMEZONE_UNCONFIRMED',
                             'INTERMEDIATE_INTERRUPTION_UNREVIEWED']
                            + (['AMBIGUOUS_REMOVALS'] if len(ends) != 1 else []),
            })
    return result


def calendar_relation(period, first, last):
    """원천 달력상 겹침만 반환한다. 같은 센서라는 판정은 아니다."""
    first, last = datetime.fromisoformat(str(first)), datetime.fromisoformat(str(last))
    sl, su, el, eu = [datetime.fromisoformat(period[k]) for k in
                      ('start_lower', 'start_upper', 'end_lower', 'end_upper')]
    if last < sl or first >= eu:
        return 'NO_CALENDAR_OVERLAP'
    if first >= su and last < el:
        return 'INSIDE_CANDIDATE_CALENDAR_WINDOW'
    return 'BOUNDARY_OR_PARTIAL_OVERLAP_UNCERTAIN'


def evaluation_blockers(row):
    """허용 목록 방식의 gate. 상태 미기재·근거 미확정은 허용하지 않는다."""
    checks = {
        'STATION_OPERATION_UNAPPROVED': row.get('station_operation_approved') is True,
        'ITEM_OPERATION_UNAPPROVED': row.get('item_operation_approved') is True,
        'SENSOR_DEPLOYMENT_UNAPPROVED': row.get('sensor_deployment_approved') is True,
        'IDENTITY_UNAPPROVED': row.get('identity_approved') is True,
        'UNIT_UNAPPROVED': row.get('unit_approved') is True,
        'TIMEZONE_UNAPPROVED': row.get('timezone_approved') is True,
        'QC_POLICY_UNAPPROVED': row.get('qc_policy_approved') is True,
        'RAW_RECONCILIATION_UNVERIFIED': row.get('raw_reconciled') is True,
        'ROW_MEMBERSHIP_UNFROZEN': row.get('membership_hash') is not None,
        'SPLIT_UNREVIEWED': row.get('split_reviewed') is True,
    }
    if row.get('task') == 'anomaly_detection':
        checks['LABEL_UNAPPROVED'] = row.get('labels_approved') is True
    return sorted(k for k, valid in checks.items() if not valid)


def validate_splits(records, embargo_seconds=0):
    """정답 도달 시각으로 분할 경계를 확인하고 사건·내용 해시의 분할 중복을 거부한다."""
    if embargo_seconds < 0:
        raise ValueError('NEGATIVE_EMBARGO')
    order = ['TRAIN', 'VALIDATION', 'TEST']
    errors, groups, ids, locked = [], {k: [] for k in order}, set(), {}
    for r in records:
        if r['split'] not in groups:
            raise ValueError('UNKNOWN_SPLIT')
        if r['id'] in ids:
            errors.append('DUPLICATE_MEMBER')
        ids.add(r['id']); groups[r['split']].append(r)
        for key in ('event_id', 'document_family', 'content_sha256'):
            if r.get(key):
                group = (key, r[key])
                if group in locked and locked[group] != r['split']:
                    errors.append(key.upper() + '_LEAKAGE')
                locked[group] = r['split']
        if datetime.fromisoformat(r['label_end']) < datetime.fromisoformat(r['timestamp']):
            errors.append('REVERSED_LABEL_WINDOW')
        if r.get('feature_available_at') and r['feature_available_at'] > r['timestamp']:
            errors.append('FUTURE_FEATURE')
    if not all(groups.values()):
        errors.append('MISSING_SPLIT')
    for a, b in zip(order, order[1:]):
        if groups[a] and groups[b]:
            end = max(datetime.fromisoformat(r['label_end']) for r in groups[a])
            start = min(datetime.fromisoformat(r['timestamp']) for r in groups[b])
            if end + timedelta(seconds=embargo_seconds) >= start:
                errors.append('TEMPORAL_OR_EMBARGO_LEAKAGE')
    return sorted(set(errors))
