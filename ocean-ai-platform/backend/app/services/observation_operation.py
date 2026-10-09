"""Versioned data-flow diagnostics at one native-clock cutoff.

These labels describe the held observations in a recent window. They do not
assert equipment health, approved QC, a timezone, or a receipt collection rate.
Raw groups remain separated by source, station, item and typed depth.
"""
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from functools import lru_cache
from pathlib import Path
import json
import math
import re
import threading
import uuid

import duckdb
from fastapi import HTTPException

from app.core.config import settings
from app.services import lake_browser as lake
from app.services.native_month_metrics import (
    KEYS, SOURCES, asset_month, digest, fetch, file_hash, quote, typed_key,
)

NATIVE_PATTERN = r'[0-9]{4}-[0-9]{2}-[0-9]{2}[ T][0-9]{2}:[0-9]{2}:[0-9]{2}(\.[0-9]{1,6})?'
POLICY = {
    'version': 'observation-data-flow-20261009-v1',
    'basis': 'OBSERVATION_DIAGNOSTIC',
    'window_hours': 24,
    'history_days': 7,
    'minimum_unique_clocks': 12,
    'minimum_interval_dominance_percent': 80,
    'normal_grid_percent': 99,
    'abnormal_grid_percent': 90,
    'normal_finite_percent': 99,
    'abnormal_finite_percent': 90,
    'abnormal_interpreted_bad_qc_percent': 10,
    'abnormal_interpreted_bad_or_missing_qc_percent': 10,
    'interpreted_qc_denominator': 'UNIQUE_NATIVE_CLOCK_WORST_LITERAL',
    'warning_delay_intervals': 3,
    'warning_delay_floor_seconds': 300,
    'abnormal_delay_intervals': 10,
    'abnormal_delay_floor_seconds': 1800,
    'phase_required': 'UNANIMOUS',
    'station_aggregation': 'WORST_CHANNEL_WITH_INCOMPLETE_EVALUATION_WARNING',
    'approval_status': 'DEVELOPMENT_POLICY_UNAPPROVED',
}
POLICY_HASH = digest(POLICY)
RECIPE_HASH = digest({'code': file_hash(__file__), 'policy': POLICY_HASH})
SEVERITY = {'UNVERIFIED': -1, 'NORMAL': 0, 'WARNING': 1, 'ABNORMAL': 2}
_lock = threading.Lock()
_EPOCH = datetime(1970, 1, 1)


def native_clock(value):
    if isinstance(value, datetime):
        return value if value.tzinfo is None else None
    if not isinstance(value, str) or not re.fullmatch(NATIVE_PATTERN, value):
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def epoch_us(value):
    delta = value - _EPOCH
    return (delta.days * 86400 + delta.seconds) * 1000000 + delta.microseconds


def window_bounds(cutoff, policy=None):
    policy = policy or POLICY
    end = native_clock(cutoff)
    if end is None:
        raise HTTPException(422, '운영 진단 기준시각은 offset 없는 원문 시계여야 합니다.')
    start = end - timedelta(hours=policy['window_hours'])
    return start, end


def _intervals(clocks):
    ordered = sorted(set(clocks))
    counts = Counter(epoch_us(b) - epoch_us(a) for a, b in zip(ordered, ordered[1:]))
    return [{'microseconds': gap, 'count': count} for gap, count in sorted(counts.items()) if gap > 0]


def _candidate(distribution):
    if not distribution:
        return None
    most = max(row['count'] for row in distribution)
    choices = [row['microseconds'] for row in distribution if row['count'] == most]
    return choices[0] if len(choices) == 1 else None


def _phases(points, interval):
    if interval is None:
        return []
    grouped = defaultdict(lambda: {'unique_timestamp_count': 0, 'raw_rows': 0})
    for clock, rows in points.items():
        group = grouped[epoch_us(clock) % interval]
        group['unique_timestamp_count'] += 1
        group['raw_rows'] += len(rows)
    return [dict(microseconds=phase, **counts) for phase, counts in sorted(grouped.items())]


def _numeric(literal):
    try:
        value = float(literal)
    except (TypeError, ValueError, OverflowError):
        return None
    return value if math.isfinite(value) else None


def summarize_channel(records, cutoff, channel=None, *, policy=None):
    """Pure fixture adapter used by simulation and independently testable logic.

    Input records use observed_time_raw/value_raw/source_qc_raw. No simulated
    records are added to actual source scans or database tables.
    """
    policy = policy or POLICY
    start, end = window_bounds(cutoff, policy)
    history_start = start - timedelta(days=policy['history_days'])
    recent, history = defaultdict(list), defaultdict(list)
    invalid = future = 0
    for row in records:
        clock = native_clock(row.get('observed_time_raw'))
        if clock is None:
            invalid += 1
        elif clock > end:
            future += 1
        elif start < clock <= end:
            recent[clock].append(row)
        elif history_start < clock <= start:
            history[clock].append(row)
    raw = [row for group in recent.values() for row in group]
    missing = sum(row.get('value_raw') is None or not str(row['value_raw']).strip() for row in raw)
    nonfinite = nonnumeric = 0
    for row in raw:
        literal = row.get('value_raw')
        if literal is None or not str(literal).strip():
            continue
        try:
            value = float(literal)
            nonfinite += not math.isfinite(value)
        except (ValueError, TypeError, OverflowError):
            nonnumeric += 1
    distribution = _intervals(recent)
    history_distribution = _intervals(history)
    qc = Counter(row.get('source_qc_raw') for row in raw)
    qc_clocks = Counter(tuple(sorted({row.get('source_qc_raw') for row in group},key=lambda value:str(value)))
                        for group in recent.values())
    return dict(channel or {}, raw_rows=len(raw), unique_timestamps=len(recent),
        finite_unique_timestamps=sum(all(_numeric(row.get('value_raw')) is not None for row in group) for group in recent.values()),
        missing_rows=missing, nonfinite_rows=nonfinite, nonnumeric_rows=nonnumeric,
        duplicate_rows=len(raw)-len(recent),
        duplicate_conflict_slots=sum(len({row.get('value_raw') for row in group}) > 1 for group in recent.values()),
        latest_clock=str(max(recent)) if recent else None,
        history_latest_clock=str(max(history)) if history else None,
        interval_distribution=distribution, phase_distribution=_phases(recent, _candidate(distribution)),
        history_interval_distribution=history_distribution,
        history_phase_distribution=_phases(history, _candidate(history_distribution)),
        history_unique_timestamps=len(history),
        source_qc_primary_field='source_qc_raw',
        qc_codes=[dict(field='source_qc_raw', literal=literal, count=count) for literal, count in sorted(qc.items(), key=lambda entry: str(entry[0]))],
        qc_clock_codes=[dict(literals=list(literals),unique_timestamp_count=count)
                        for literals,count in sorted(qc_clocks.items(),key=lambda entry:str(entry[0]))],
        invalid_clock_rows_excluded=invalid, future_rows_excluded=future)


def _cadence(distribution, unique, policy):
    candidate = _candidate(distribution)
    total = sum(row['count'] for row in distribution)
    dominant = max((row['count'] for row in distribution), default=0)
    percent = 100 * dominant / total if total else None
    status = 'INFERRED'
    if unique < policy['minimum_unique_clocks']:
        status = 'INSUFFICIENT_CLOCKS'
    elif candidate is None:
        status = 'AMBIGUOUS_INTERVAL_MODE'
    elif dominant * 100 < total * policy['minimum_interval_dominance_percent']:
        status = 'INTERVAL_MODE_NOT_DOMINANT'
    return dict(status=status, inferred=True, interval_microseconds=candidate,
        interval_seconds=candidate/1000000 if candidate else None,
        dominance_percent=percent, unique_clocks=unique)


def classify_channel(stats, cutoff, window_start=None, *, evidence=None, policy=None):
    """Classify an exact channel using explicit thresholds, with no QC guess."""
    policy = policy or POLICY
    start, end = window_bounds(cutoff, policy)
    if window_start is not None and native_clock(window_start) != start:
        raise ValueError('OPERATION_WINDOW_MISMATCH')
    # The public pure classifier must apply the same identity/as-of gate as
    # live requests and simulation; a caller's USABLE label is insufficient.
    from app.services.observation_operation_evidence import channel_evidence,bulk_reader
    if not evidence:
        evidence=bulk_reader(None,[stats.get('station_code')],str(end),str(start))[stats.get('station_code')]
    evidence=channel_evidence(evidence,stats.get('station_code'),stats.get('physical_sensor_id'),
        stats.get('item_code'),source_group=stats.get('source_group'),
        source_qc_primary_field=stats.get('source_qc_primary_field'),
        cutoff_native_literal=str(end),window_start_native_literal=str(start))
    cadence = _cadence(stats.get('interval_distribution', []), stats.get('unique_timestamps', 0), policy)
    history = _cadence(stats.get('history_interval_distribution', []), stats.get('history_unique_timestamps', 0), policy)
    cadence['history_interval_seconds'] = history['interval_seconds'] if history['status'] == 'INFERRED' else None
    reasons, state = [], 'NORMAL'
    def signal(new, reason):
        nonlocal state
        if SEVERITY[new] > SEVERITY[state]:
            state = new
        reasons.append(reason)
    raw_rows = stats.get('raw_rows', 0)
    unique = stats.get('unique_timestamps', 0)
    finite = stats.get('finite_unique_timestamps', 0)
    latest = native_clock(stats.get('latest_clock')) or native_clock(stats.get('history_latest_clock'))
    # A selected earlier period can identify a channel stale beyond the scan lookback.
    prior = native_clock(stats.get('last_selected_clock'))
    if prior is not None and prior <= end and (latest is None or prior > latest):
        latest = prior
    if latest is not None and latest > end:
        raise ValueError('OPERATION_FUTURE_LATEST_CLOCK')
    delay = (epoch_us(end)-epoch_us(latest))/1000000 if latest else None
    expected = held = finite_slots = None
    phases = stats.get('phase_distribution', [])
    interval = cadence['interval_microseconds']
    changed = (cadence['status'] == history['status'] == 'INFERRED'
               and interval != history['interval_microseconds'])
    if changed:
        cadence['status'] = 'CADENCE_CHANGED'
        signal('WARNING', 'CADENCE_CHANGED_FROM_PREVIOUS_HISTORY')
    elif cadence['status'] != 'INFERRED':
        signal('WARNING', cadence['status'])
    elif len(phases) != 1:
        cadence['status'] = 'PHASE_UNSTABLE'
        signal('WARNING', 'MULTIPLE_OR_MISSING_CLOCK_PHASES')
    elif (history['status']=='INFERRED' and len(stats.get('history_phase_distribution',[]))==1
          and phases[0]['microseconds']!=stats['history_phase_distribution'][0]['microseconds']):
        cadence['status']='PHASE_CHANGED'
        signal('WARNING','CLOCK_PHASE_CHANGED_FROM_PREVIOUS_HISTORY')
    else:
        phase = phases[0]['microseconds']
        expected = (epoch_us(end)-phase)//interval - (epoch_us(start)-phase)//interval
        held, finite_slots = unique, finite
        if expected <= 0 or not 0 <= finite <= unique <= expected:
            raise ValueError('OPERATION_GRID_COUNTS_INCONSISTENT')
        if unique * 100 < expected * policy['abnormal_grid_percent']:
            signal('ABNORMAL', 'RECENT_INFERRED_GRID_AVAILABILITY_BELOW_ABNORMAL_THRESHOLD')
        elif unique * 100 < expected * policy['normal_grid_percent']:
            signal('WARNING', 'RECENT_INFERRED_GRID_AVAILABILITY_BELOW_NORMAL_THRESHOLD')
    delay_interval = interval or (history['interval_microseconds'] if history['status'] == 'INFERRED' else None)
    warning_delay = max(policy['warning_delay_floor_seconds'], policy['warning_delay_intervals']*(delay_interval or 0)/1000000)
    abnormal_delay = max(policy['abnormal_delay_floor_seconds'], policy['abnormal_delay_intervals']*(delay_interval or 0)/1000000)
    if delay is not None and delay > abnormal_delay:
        signal('ABNORMAL', 'LAST_OBSERVATION_AGE_EXCEEDS_ABNORMAL_THRESHOLD')
    elif delay is not None and delay > warning_delay:
        signal('WARNING', 'LAST_OBSERVATION_AGE_EXCEEDS_WARNING_THRESHOLD')
    if unique:
        if finite * 100 < unique * policy['abnormal_finite_percent']:
            signal('ABNORMAL', 'RECENT_FINITE_VALUE_FRACTION_BELOW_ABNORMAL_THRESHOLD')
        elif finite * 100 < unique * policy['normal_finite_percent']:
            signal('WARNING', 'RECENT_FINITE_VALUE_FRACTION_BELOW_NORMAL_THRESHOLD')
    elif latest is None:
        state = 'UNVERIFIED'
        reasons = ['NO_CURRENT_OR_PRIOR_OBSERVATION_EVIDENCE']
    else:
        signal('WARNING', 'NO_OBSERVATIONS_IN_RECENT_WINDOW')
    if stats.get('duplicate_conflict_slots', 0):
        signal('WARNING', 'CONFLICTING_VALUES_AT_DUPLICATE_CLOCKS')
    evidence = evidence or {}
    for component in ('inspection', 'operations', 'quality_reports', 'qc_history', 'event_registry'):
        entry = evidence.get(component, {})
        diagnostic = entry.get('diagnostic_state')
        if entry.get('state') == 'USABLE' and diagnostic in SEVERITY and diagnostic != 'UNVERIFIED':
            signal(diagnostic, 'DATED_'+component.upper()+'_EVIDENCE_'+diagnostic)
    qc_known = evidence.get('qc_semantics', {}).get('state') == 'USABLE' and bool(evidence.get('qc_semantics',{}).get('mapping'))
    qc_interpreted = Counter()
    qc_unknown_clocks = 0
    if qc_known:
        mapping = evidence['qc_semantics'].get('mapping', {})
        # Replayed raw rows do not multiply QC evidence at one exact clock.
        # Conflicting mapped codes retain the worst point-level assessment.
        for group in stats.get('qc_clock_codes', []):
            codes={mapping.get(literal,'UNKNOWN') for literal in group['literals']}
            count=group['unique_timestamp_count']
            qc_unknown_clocks+=count if 'UNKNOWN' in codes else 0
            assessment='BAD' if 'BAD' in codes else 'MISSING' if 'MISSING' in codes else 'SUSPECT' if 'SUSPECT' in codes else 'UNKNOWN' if 'UNKNOWN' in codes else 'GOOD'
            qc_interpreted[assessment]+=count
        bad = qc_interpreted['BAD']
        if bad and unique and bad*100 >= unique*policy['abnormal_interpreted_bad_qc_percent']:
            signal('ABNORMAL', 'RECENT_INTERPRETED_BAD_QC_AT_ABNORMAL_THRESHOLD')
        elif (bad+qc_interpreted['MISSING']) and unique and (bad+qc_interpreted['MISSING'])*100 >= unique*policy['abnormal_interpreted_bad_or_missing_qc_percent']:
            signal('ABNORMAL','RECENT_INTERPRETED_BAD_OR_MISSING_QC_AT_ABNORMAL_THRESHOLD')
        elif qc_interpreted['MISSING']:
            signal('WARNING','RECENT_INTERPRETED_MISSING_QC_PRESENT')
        elif bad or qc_interpreted['SUSPECT']:
            signal('WARNING', 'RECENT_INTERPRETED_BAD_OR_SUSPECT_QC_PRESENT')
    qc_complete = qc_known and not qc_unknown_clocks and bool(qc_interpreted)
    inspection_missing = evidence.get('inspection', {}).get('state') != 'USABLE'
    limitations = ['RECEIPT_COLLECTION_RATE_NOT_EVALUATED', 'SOURCE_TIMEZONE_UNAPPROVED',
        'SOURCE_UNIT_AND_SENSOR_EFFECTIVE_PERIOD_UNCONFIRMED', 'EQUIPMENT_HEALTH_NOT_EVALUATED']
    if not qc_complete:
        limitations.append('SOURCE_QC_CODEBOOK_EFFECTIVE_PERIOD_MISSING')
    if inspection_missing:
        limitations.append('DATED_INSPECTION_EVIDENCE_MISSING_OR_UNUSABLE')
    return dict(stats, state=state, reasons=reasons or ['RECENT_OBSERVATION_FLOW_WITHIN_DEVELOPMENT_THRESHOLDS'],
        basis=policy['basis'], policy_version=policy['version'], policy_hash=digest(policy),
        window_start=str(start), window_end=str(end), last_clock=str(latest) if latest else None,
        delay_seconds=delay, cadence=cadence,
        observed_grid=dict(expected_slots=expected, held_slots=held, finite_slots=finite_slots,
            availability_percent=100*held/expected if expected else None,
            finite_percent=100*finite/unique if unique else None,
            denominator='INFERRED_OBSERVATION_GRID', sampling_contract_approved=False),
        collection_rate=None, confidence='LOW', equipment_state='UNVERIFIED',
        qc_evidence='AVAILABLE_REFERENCE' if qc_complete else 'UNKNOWN', qc_interpreted=dict(qc_interpreted),
        qc_interpreted_basis='UNIQUE_NATIVE_CLOCK_WORST_LITERAL',qc_unknown_clocks=qc_unknown_clocks,
        inspection_missing=inspection_missing, qc_interpretation_missing=not qc_complete,
        not_evaluated=limitations)


def aggregate_station(station, channels, cutoff, *, evidence=None, policy=None):
    policy = policy or POLICY
    start, end = window_bounds(cutoff, policy)
    evaluated = [channel for channel in channels if channel['state'] != 'UNVERIFIED']
    state = max((channel['state'] for channel in evaluated), key=lambda value: SEVERITY[value], default='UNVERIFIED')
    incomplete = len(evaluated) != len(channels)
    reasons = sorted({reason for channel in channels if channel['state'] == state for reason in channel['reasons']})
    if not channels:
        reasons=['NO_SELECTED_CHANNEL_EVIDENCE']
    if incomplete and state == 'NORMAL':
        state = 'WARNING'
        reasons.append('CHANNELS_NOT_EVALUATED')
    grids = [channel['observed_grid'] for channel in channels if channel['observed_grid']['expected_slots'] is not None]
    expected, held = sum(g['expected_slots'] for g in grids), sum(g['held_slots'] for g in grids)
    missing = [channel for channel in channels if channel.get('inspection_missing')]
    unknown_qc = [channel for channel in channels if channel.get('qc_interpretation_missing')]
    return dict(station_code=station, state=state, basis=policy['basis'],
        policy_version=policy['version'], policy_hash=digest(policy), thresholds=policy,
        window_start=str(start), window_end=str(end), channels_total=len(channels),
        channels_evaluated=len(evaluated), channels_not_evaluated=len(channels)-len(evaluated),
        channels=channels, reason=' · '.join(reasons), reasons=reasons,
        collection_rate=None, observed_grid_availability_percent=100*held/expected if expected else None,
        observed_grid=dict(expected_slots=expected, held_slots=held, eligible_channels=len(grids),
            excluded_channels=len(channels)-len(grids), denominator='INFERRED_OBSERVATION_GRID'),
        confidence='LOW', equipment_state='UNVERIFIED',
        inspection_missing=bool(missing) or not channels, qc_interpretation_missing=bool(unknown_qc) or not channels,
        qc_evidence='UNKNOWN' if unknown_qc or not channels else 'AVAILABLE_REFERENCE',
        evidence=evidence or {}, not_evaluated=sorted({value for channel in channels for value in channel['not_evaluated']}))


def aggregate_summary(operations, cutoff, *, policy=None):
    policy = policy or POLICY
    start, end = window_bounds(cutoff, policy)
    counts = Counter(operation['state'] for operation in operations)
    expected = sum(operation['observed_grid']['expected_slots'] for operation in operations)
    held = sum(operation['observed_grid']['held_slots'] for operation in operations)
    return dict(normal=counts['NORMAL'], warning=counts['WARNING'], abnormal=counts['ABNORMAL'],
        unclassified=counts['UNVERIFIED'], collection_rate=None,
        observed_grid_availability_percent=100*held/expected if expected else None,
        basis=policy['basis'], policy_version=policy['version'], policy_hash=digest(policy),
        thresholds=policy, window_start=str(start), window_end=str(end),
        stations_total=len(operations), confidence='LOW', equipment_state='UNVERIFIED',
        reason='최근 24시간의 자료 흐름 진단입니다. 관측 간격·분모는 원천 시각에서 추정했으며 장비 정상·승인 QC·실제 수신 수집률은 확정하지 않습니다.')


def _source_identity(view, source, cutoff):
    start, end = window_bounds(cutoff)
    history_start = start-timedelta(days=POLICY['history_days'])
    authority = view/'file-only-timeseries.duckdb'
    catalog = view/'station-item-month-validation.parquet'
    assets = [asset for asset in lake.monthly_assets(str(authority), authority.stat().st_mtime_ns)
              if asset['source_group'] == source
              and str(history_start)[:7] <= asset_month(asset) <= str(end)[:7]]
    root = lake.historical_root() if source == 'GD_OBS_ST_MONTHLY' else Path(settings.SHARE_MONTHLY_LAKE_ROOT)
    signatures = []
    for asset in assets:
        path = lake.inside(root, asset['parquet_path'])
        stat = path.stat()
        signatures.append((str(path),stat.st_size,stat.st_mtime_ns,asset['parquet_sha256']))
        lake.verify_file(str(path), stat.st_mtime_ns, stat.st_size, asset['parquet_sha256'])
    return assets, signatures, file_hash(authority), file_hash(catalog)


@lru_cache(maxsize=8)
def _cached_window(view_text, source, cutoff_text, signatures, authority_sha, catalog_sha, recipe_hash):
    """Cache observation counts only; dated DB evidence is read anew per request."""
    view = Path(view_text)
    start, end = window_bounds(cutoff_text)
    history_start = start-timedelta(days=POLICY['history_days'])
    assets, current, sha, census_sha = _source_identity(view, source, cutoff_text)
    if tuple(current) != signatures or (sha,census_sha) != (authority_sha,catalog_sha):
        raise HTTPException(409, '운영 진단 원천 목록이 조회 중 변경됐습니다.')
    if not assets:
        return []
    files = [Path(asset['parquet_path']) for asset in assets]
    work = Path(settings.MONTHLY_REPORT_MATCHING_ROOT)/'operation-window-work'/uuid.uuid4().hex
    work.mkdir(parents=True, exist_ok=True)
    c = duckdb.connect(':memory:', config={'threads':2,'memory_limit':'768MB'})
    try:
        c.execute('SET temp_directory=?',[str(work)])
        c.execute('SET preserve_insertion_order=false')
        c.read_parquet([str(path) for path in files],hive_partitioning=False).create_view('parquet_source')
        cols = {row[0] for row in c.execute('describe parquet_source').fetchall()}
        station,item,clock,value = ('station_raw','item_raw','time_raw','value_raw') if source == 'GD_OBS_ST_MONTHLY' else ('OBS_POST_ID','OBS_ITEM_CODE','OBS_TIME','OBS_VALUE')
        if 'FROM_DEPTH' in cols and 'FR_DEPTH' in cols:
            raise HTTPException(409, '운영 진단 원천의 수심 별칭이 충돌합니다.')
        depths = ['NULL::VARCHAR']*3 if source == 'GD_OBS_ST_MONTHLY' else [
            quote(name) if name in cols else 'NULL::VARCHAR'
            for name in ('WATER_STEP','FROM_DEPTH' if 'FROM_DEPTH' in cols else 'FR_DEPTH','TO_DEPTH')]
        qc_fields = [name for name in ('qc_raw','mq_raw','n1_aqc_raw') if name in cols] if source == 'GD_OBS_ST_MONTHLY' else sorted(name for name in cols if name.endswith('_FLAG'))
        primary = 'qc_raw' if source == 'GD_OBS_ST_MONTHLY' and 'qc_raw' in cols else 'QC_FLAG' if 'QC_FLAG' in cols else None
        fields = [f'trim({quote(station)}) station_code', f'trim({quote(item)}) item_code']
        fields += [f'{value} {key}' for value,key in zip(depths,KEYS[2:])]
        fields += [f'{quote(value)} value_literal', f'try_cast({quote(value)} AS DOUBLE) parsed_number',
            f"CASE WHEN regexp_full_match(CAST({quote(clock)} AS VARCHAR),'{NATIVE_PATTERN}') THEN try_cast({quote(clock)} AS TIMESTAMP) END native_clock"]
        fields += [quote(field) for field in qc_fields]
        where = " WHERE record_class='OBSERVATION_SHAPED_UNVALIDATED'" if source == 'GD_OBS_ST_MONTHLY' else ''
        c.execute('CREATE TEMP VIEW normalized_all AS SELECT '+','.join(fields)+' FROM parquet_source'+where)
        c.execute('CREATE TEMP TABLE normalized AS SELECT *,native_clock>?::TIMESTAMP recent FROM normalized_all WHERE native_clock>?::TIMESTAMP AND native_clock<=?::TIMESTAMP', [str(start),str(history_start),str(end)])
        keys=','.join(KEYS)
        c.execute(f'CREATE TEMP TABLE grains AS SELECT row_number() OVER(ORDER BY {keys}) grain_id,{keys} FROM normalized GROUP BY {keys}')
        join=' AND '.join(f'n.{key} IS NOT DISTINCT FROM g.{key}' for key in KEYS)
        c.execute('CREATE TEMP VIEW keyed AS SELECT g.grain_id,n.* FROM normalized n JOIN grains g ON '+join)
        grains = {row['grain_id']:row for row in fetch(c,'SELECT * FROM grains')}
        counts = {row['grain_id']:row for row in fetch(c, '''SELECT grain_id,
            count(*) FILTER(WHERE recent) raw_rows,
            count(*) FILTER(WHERE recent AND (value_literal IS NULL OR trim(value_literal)='')) missing_rows,
            count(*) FILTER(WHERE recent AND parsed_number IS NOT NULL AND NOT isfinite(parsed_number)) nonfinite_rows,
            count(*) FILTER(WHERE recent AND parsed_number IS NULL AND value_literal IS NOT NULL AND trim(value_literal)<>'') nonnumeric_rows,
            max(native_clock) FILTER(WHERE recent) latest_clock,
            max(native_clock) FILTER(WHERE NOT recent) history_latest_clock
            FROM keyed GROUP BY grain_id''')}
        c.execute('''CREATE TEMP TABLE points AS SELECT grain_id,native_clock,recent,
            count(*) raw_timestamp_rows,
            bool_and(parsed_number IS NOT NULL AND isfinite(parsed_number)) all_finite,
            count(DISTINCT struct_pack(literal:=value_literal)) variants
            FROM keyed GROUP BY grain_id,native_clock,recent''')
        for row in fetch(c,'''SELECT grain_id,count(*) FILTER(WHERE recent) unique_timestamps,
            count(*) FILTER(WHERE recent AND all_finite) finite_unique_timestamps,
            count(*) FILTER(WHERE recent AND variants>1) duplicate_conflict_slots,
            coalesce(sum(raw_timestamp_rows-1) FILTER(WHERE recent),0) duplicate_rows,
            count(*) FILTER(WHERE NOT recent) history_unique_timestamps
            FROM points GROUP BY grain_id'''):
            counts[row.pop('grain_id')].update(row)
        distributions = defaultdict(list)
        for row in fetch(c,'''WITH deltas AS (SELECT grain_id,recent,
            epoch_us(native_clock)-epoch_us(lag(native_clock) OVER(PARTITION BY grain_id,recent ORDER BY native_clock)) delta_us FROM points)
            SELECT grain_id,recent,delta_us AS "microseconds",count(*) count FROM deltas WHERE delta_us>0
            GROUP BY grain_id,recent,delta_us ORDER BY grain_id,recent,delta_us'''):
            distributions[(row.pop('grain_id'),row.pop('recent'))].append(row)
        modes = [(gid,recent,_candidate(dist)) for (gid,recent),dist in distributions.items() if _candidate(dist) is not None]
        c.execute('CREATE TEMP TABLE modes(grain_id BIGINT,recent BOOLEAN,interval_us BIGINT)')
        if modes:
            c.executemany('INSERT INTO modes VALUES(?,?,?)', modes)
        phases = defaultdict(list)
        for row in fetch(c,'''SELECT p.grain_id,p.recent,epoch_us(native_clock)%m.interval_us AS "microseconds",
            count(*) unique_timestamp_count,sum(raw_timestamp_rows) raw_rows
            FROM points p JOIN modes m ON p.grain_id=m.grain_id AND p.recent=m.recent
            GROUP BY p.grain_id,p.recent,"microseconds" ORDER BY p.grain_id,p.recent,"microseconds"'''):
            phases[(row.pop('grain_id'),row.pop('recent'))].append(row)
        codes = defaultdict(list)
        qc_clocks = defaultdict(list)
        if qc_fields:
            sql = 'SELECT grain_id,field,literal,count(*) count FROM keyed CROSS JOIN LATERAL (VALUES '+','.join(f"('{field}',{quote(field)})" for field in qc_fields)+') q(field,literal) WHERE recent GROUP BY grain_id,field,literal ORDER BY grain_id,field,literal'
            for row in fetch(c,sql):
                codes[row.pop('grain_id')].append(row)
        if primary:
            c.execute('CREATE TEMP VIEW qc_points AS SELECT grain_id,native_clock,list_sort(list(DISTINCT '+quote(primary)+')) literals FROM keyed WHERE recent GROUP BY grain_id,native_clock')
            for row in fetch(c,'SELECT grain_id,literals,count(*) unique_timestamp_count FROM qc_points GROUP BY grain_id,literals ORDER BY grain_id,literals'):
                qc_clocks[row.pop('grain_id')].append(row)
        result=[]
        for gid,grain in grains.items():
            count=counts[gid];count.pop('grain_id')
            for key in ('latest_clock','history_latest_clock'):
                if count[key] is not None:
                    count[key]=str(count[key])
            grain.pop('grain_id')
            result.append(dict(grain,**count,source_group=source,
                interval_distribution=distributions[(gid,True)],phase_distribution=phases[(gid,True)],
                history_interval_distribution=distributions[(gid,False)],history_phase_distribution=phases[(gid,False)],
                qc_codes=codes[gid],qc_clock_codes=qc_clocks[gid],source_qc_primary_field=primary,
                physical_sensor_id=None,unit=None,timezone=None))
        for path,signature in zip(files,signatures):
            stat=path.stat()
            if (str(path),stat.st_size,stat.st_mtime_ns,signature[3]) != signature or file_hash(path)!=signature[3]:
                raise HTTPException(409, '운영 진단 중 원천 파일이 변경됐습니다.')
        if file_hash(view/'file-only-timeseries.duckdb') != authority_sha or file_hash(view/'station-item-month-validation.parquet') != catalog_sha:
            raise HTTPException(409, '운영 진단 중 검증 카탈로그가 변경됐습니다.')
        return result
    finally:
        c.close()
        try: work.rmdir()
        except OSError: pass


def operations_for_rows(view, source, selected, as_of_day, as_of_time=None, *, db=None):
    """Join recent exact-channel counts with the selected real-source station set."""
    if source not in SOURCES:
        raise HTTPException(422, '정산된 native 월 원천의 운영 진단만 제공됩니다.')
    cutoff_text = str(as_of_day)+' '+(as_of_time or '23:59:59.999999')
    start,end = window_bounds(cutoff_text)
    assets,signatures,authority_sha,catalog_sha = _source_identity(view,source,cutoff_text)
    with _lock:
        raw = _cached_window(str(view),source,cutoff_text,tuple(signatures),authority_sha,catalog_sha,RECIPE_HASH)
    by_grain = {typed_key(row):row for row in raw}
    selected_grains = {}
    for row in selected:
        key = typed_key(row)
        if key not in selected_grains or selected_grains[key].get('last_native_clock','') < row.get('last_native_clock',''):
            selected_grains[key]=row
    stations = sorted({row['station_code'] for row in selected})
    from app.services.observation_operation_evidence import bulk_reader
    evidence = bulk_reader(db,stations,str(end),str(start))
    grouped=defaultdict(list)
    for key,row in selected_grains.items():
        stats=dict(by_grain.get(key) or dict(raw_rows=0,unique_timestamps=0,finite_unique_timestamps=0,
            missing_rows=0,nonfinite_rows=0,nonnumeric_rows=0,duplicate_rows=0,duplicate_conflict_slots=0,
            latest_clock=None,history_latest_clock=None,history_unique_timestamps=0,
            interval_distribution=[],phase_distribution=[],history_interval_distribution=[],history_phase_distribution=[],qc_codes=[],qc_clock_codes=[]))
        stats.update({key:row.get(key) for key in KEYS})
        stats.update(source_group=source,last_selected_clock=row.get('last_native_clock'))
        station_evidence=evidence.get(row['station_code'],{})
        grouped[row['station_code']].append(classify_channel(stats,str(end),evidence=station_evidence))
    operations={station:aggregate_station(station,channels,str(end),evidence=evidence.get(station,{}))
                for station,channels in grouped.items()}
    return operations,aggregate_summary(list(operations.values()),str(end))
