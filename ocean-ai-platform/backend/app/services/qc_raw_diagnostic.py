"""Causal raw-value experiments with native clocks, no physical QC authority.

This separate schema cannot be loaded by the production/statistical artifact
loader. It does not invent units, UTC, physical sensors, QC labels or cause truth.
"""
from collections import Counter
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path

import numpy as np

SERIES = "raw-native-diagnostic-series-1"
ARTIFACT = "raw-native-diagnostic-artifact-1"
REPORT = "raw-native-diagnostic-prediction-1"
GRAIN = ("source_group", "source_station_code", "source_item_code", "depth_step", "depth_from", "depth_to")


class RawDiagnosticError(ValueError):
    pass


def canonical(value):
    raw = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode()
    if len(raw) > 8 * 1024 * 1024:
        raise RawDiagnosticError("RAW_DIAGNOSTIC_JSON_LIMIT")
    return raw


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def recipe_sha256():
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def hash_file(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def read_raw_parquet_series(path, expected_sha256, manifest_path,
        expected_manifest_sha256, grain, columns, identifier_transform='IDENTITY',
        limit=500, offset=0, ordering='RAW_FILE_ORDER'):
    """Bounded reader of exact raw cells; file bytes are rehashed before/after.

    Column maps are supplied explicitly. It does not guess aliases, units,
    sensors, source clock offsets or interpret any flag string.
    """
    import pyarrow.parquet as pq
    if type(limit) is not int or not 40 <= limit <= 10000 or type(offset) is not int or offset < 0:
        raise RawDiagnosticError('BOUNDED_RAW_SELECTION_REQUIRED')
    if identifier_transform not in {'IDENTITY', 'STRIP_SQLPLUS_PADDING'}:
        raise RawDiagnosticError('EXPLICIT_IDENTIFIER_TRANSFORM_REQUIRED')
    if ordering not in {'RAW_FILE_ORDER', 'NATIVE_CLOCK_ASCENDING'}:
        raise RawDiagnosticError('EXPLICIT_NATIVE_ORDERING_REQUIRED')
    path, manifest_path = Path(path), Path(manifest_path)
    for target in (path, manifest_path):
        if any(p.is_symlink() or (getattr(p.lstat(), 'st_file_attributes', 0) & 0x400)
               for p in [target, *target.parents]):
            raise RawDiagnosticError('SOURCE_REPARSE_PATH_REJECTED')
    if not _hash(expected_sha256) or hash_file(path) != expected_sha256 or not _hash(expected_manifest_sha256) or hash_file(manifest_path) != expected_manifest_sha256:
        raise RawDiagnosticError('ACTUAL_SOURCE_OR_MANIFEST_HASH_MISMATCH')
    if not isinstance(columns, dict) or any(not isinstance(columns.get(k), str) for k in ('station', 'item', 'clock', 'value')) or not isinstance(columns.get('qc', []), list):
        raise RawDiagnosticError('EXPLICIT_COLUMN_MAP_REQUIRED')
    keys = list(dict.fromkeys([v for k, v in columns.items() if k != 'qc'] + columns.get('qc', [])))
    pf = pq.ParquetFile(path)
    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result: raise RawDiagnosticError('MANIFEST_DUPLICATE_JSON_KEY')
            result[key] = value
        return result
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'), object_pairs_hook=unique_object,
        parse_constant=lambda value: (_ for _ in ()).throw(RawDiagnosticError('MANIFEST_NONFINITE_JSON')))
    descriptors = []
    for descriptor in manifest.get('files', []):
        if not isinstance(descriptor, dict) or not isinstance(descriptor.get('path'), str): continue
        relative = Path(descriptor['path'])
        if relative.is_absolute() or '..' in relative.parts: continue
        if any((ancestor/relative).resolve() == path.resolve() for ancestor in manifest_path.parents):
            descriptors.append(descriptor)
    if len(descriptors) != 1 or descriptors[0].get('sha256') != expected_sha256 or descriptors[0].get('rows') != pf.metadata.num_rows:
        raise RawDiagnosticError('PARQUET_NOT_EXACTLY_BOUND_TO_MANIFEST')
    if any(k not in pf.schema_arrow.names for k in keys):
        raise RawDiagnosticError('COLUMN_MAP_NOT_IN_SOURCE_SCHEMA')
    rows, skipped = [], 0
    normalize = (lambda x: x.strip() if isinstance(x, str) else x) if identifier_transform == 'STRIP_SQLPLUS_PADDING' else lambda x: x
    for rg in range(pf.num_row_groups):
        row_index = 0
        for batch in pf.iter_batches(batch_size=8192, row_groups=[rg], columns=keys):
            for raw in batch.to_pylist():
                index = row_index; row_index += 1
                if normalize(raw[columns['station']]) != grain['source_station_code'] or normalize(raw[columns['item']]) != grain['source_item_code']:
                    continue
                actual_depth = {key: raw[columns[key]] if key in columns else None for key in GRAIN[3:]}
                if digest(actual_depth) != digest({key: grain[key] for key in GRAIN[3:]}):
                    continue
                if ordering == 'RAW_FILE_ORDER' and skipped < offset:
                    skipped += 1; continue
                locator = f"parquet_row_group={rg};row_index={index};column={columns['value']}"
                rows.append({'row_id': digest({'sha256': expected_sha256, 'locator': locator}),
                    'grain': grain, 'clock_raw': raw[columns['clock']], 'value_raw': raw[columns['value']],
                    'source': {'sha256': expected_sha256, 'locator': locator},
                    'raw_literals': raw, 'source_qc_raw': {k: raw[k] for k in columns.get('qc', [])}})
                if len(rows) > 50000: raise RawDiagnosticError('RAW_ORDERING_MATCH_LIMIT')
                if ordering == 'RAW_FILE_ORDER' and len(rows) == limit: break
            if ordering == 'RAW_FILE_ORDER' and len(rows) == limit: break
        if ordering == 'RAW_FILE_ORDER' and len(rows) == limit: break
    ordering_audit = {'policy': ordering, 'scope': 'ONE_EXACT_PARQUET_FILE_NOT_WHOLE_MONTH',
        'source_match_rows_read': len(rows), 'original_clock_reversals': None,
        'original_duplicate_clock_rows': None, 'native_sort_is_online_availability': False}
    if ordering == 'NATIVE_CLOCK_ASCENDING':
        try: stamps = [datetime.strptime(r['clock_raw'], '%Y-%m-%d %H:%M:%S') for r in rows]
        except (KeyError,TypeError,ValueError): raise RawDiagnosticError('RAW_NATIVE_CLOCK_PARSE_FAILED') from None
        ordering_audit['original_clock_reversals'] = sum(a>b for a,b in zip(stamps,stamps[1:]))
        ordering_audit['original_duplicate_clock_rows'] = len(stamps)-len(set(stamps))
        rows = [r for _,r in sorted(zip(stamps,rows),key=lambda pair:pair[0])][offset:offset+limit]
    if len(rows) != limit:
        raise RawDiagnosticError('EXACT_RAW_SELECTION_INSUFFICIENT')
    if hash_file(path) != expected_sha256 or hash_file(manifest_path) != expected_manifest_sha256:
        raise RawDiagnosticError('SOURCE_CHANGED_DURING_RAW_READ')
    series = {'schema_version': SERIES, 'grain': grain, 'clock_format': '%Y-%m-%d %H:%M:%S',
        'source_manifest_sha256': expected_manifest_sha256, 'parquet_sha256': expected_sha256,
        'selection': {'offset': offset, 'limit': limit, 'column_map': columns,
            'identifier_transform': identifier_transform, 'ordering_audit': ordering_audit}, 'rows': rows,
        'manifest_parquet_descriptor': descriptors[0],
        'physical_scope': None, 'unit': None, 'timezone': None, 'approved': False,
        'status': 'RAW_DIAGNOSTIC_ONLY'}
    validate_series(series)
    return series


def unevaluated_rule_report(series, executed_at):
    """Attempt all 12 physical checks with genuinely unresolved source inputs."""
    from app.services.qc_rule_engine import catalog, execute_rules, GUIDE_SHA256
    validate_series(series)
    records = [{'observation_id': r['row_id'], 'station_id': None, 'sensor_id': None,
        'variable_code': None, 'unit': None, 'timestamp_utc': None, 'available_at': None,
        'value': float(r['value_raw']), 'source_facts': None, 'raw_native_source': r}
        for r in series['rows']]
    rules = [{'kind': r['kind'], 'qc_rule_id': 'raw-unresolved-'+r['kind'],
        'rule_version': catalog()['engine_version'], 'parameters': {},
        'provenance': {'guide_sha256': GUIDE_SHA256, 'pdf_pages': r['pdf_pages'],
            'profile_id': 'NOT_SELECTED_SOURCE_CONTRACT_UNRESOLVED'}} for r in catalog()['rules']]
    return execute_rules(records, rules, {'as_of': executed_at, 'executed_at': executed_at})


def _hash(value):
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def validate_series(series):
    canonical(series)
    if not isinstance(series, dict) or series.get("schema_version") != SERIES:
        raise RawDiagnosticError("RAW_SERIES_SCHEMA_REQUIRED")
    grain, rows = series.get("grain"), series.get("rows")
    if not isinstance(grain, dict) or set(grain) != set(GRAIN) or any(not isinstance(grain[k], str) or not grain[k] for k in GRAIN[:3]):
        raise RawDiagnosticError("EXACT_RAW_GRAIN_REQUIRED")
    if any(type(grain[k]) not in {str, int, float, type(None)} for k in GRAIN[3:]):
        raise RawDiagnosticError("TYPED_RAW_DEPTH_REQUIRED")
    if not isinstance(rows, list) or not 40 <= len(rows) <= 10000:
        raise RawDiagnosticError("BOUNDED_RAW_ROWS_REQUIRED")
    if not _hash(series.get("source_manifest_sha256")):
        raise RawDiagnosticError("SOURCE_MANIFEST_HASH_REQUIRED")
    times, values, ids, cells = [], [], set(), set()
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("row_id"), str) or row["row_id"] in ids:
            raise RawDiagnosticError("RAW_ROW_ID_MISSING_OR_DUPLICATE")
        ids.add(row["row_id"])
        if digest(row.get("grain")) != digest(grain):
            raise RawDiagnosticError("MIXED_RAW_GRAIN")
        source = row.get("source")
        if not isinstance(source, dict) or not _hash(source.get("sha256")) or not isinstance(source.get("locator"), str) or not source["locator"]:
            raise RawDiagnosticError("EXACT_PARQUET_CELL_REFERENCE_REQUIRED")
        cell = (source["sha256"], source["locator"])
        if cell in cells:
            raise RawDiagnosticError("RAW_SOURCE_CELL_REUSE")
        cells.add(cell)
        try:
            stamp = datetime.strptime(row["clock_raw"], series["clock_format"])
        except (KeyError, TypeError, ValueError):
            raise RawDiagnosticError("RAW_NATIVE_CLOCK_PARSE_FAILED") from None
        if stamp.tzinfo is not None:
            raise RawDiagnosticError("NATIVE_CLOCK_MUST_REMAIN_TIMEZONE_UNRESOLVED")
        if times and stamp <= times[-1]:
            raise RawDiagnosticError("RAW_CLOCK_DUPLICATE_OR_REVERSAL")
        times.append(stamp)
        literal = row.get("value_raw")
        try:
            value = float(literal)
        except (ValueError, TypeError):
            raise RawDiagnosticError("RAW_VALUE_NONNUMERIC_OR_MISSING") from None
        if isinstance(literal, bool) or not math.isfinite(value):
            raise RawDiagnosticError("RAW_VALUE_NONFINITE")
        values.append(value)
    return times, np.array(values, dtype=float)


def fixed_membership(series, train_count, calibration_count):
    """Freeze explicit ordered row IDs; callers choose sizes, never random split."""
    validate_series(series)
    n = len(series["rows"])
    if type(train_count) is not int or type(calibration_count) is not int or min(train_count, calibration_count, n-train_count-calibration_count) < 12:
        raise RawDiagnosticError("THREE_ORDERED_NONEMPTY_SPLITS_REQUIRED")
    ids = [row["row_id"] for row in series["rows"]]
    return {"TRAIN": ids[:train_count], "CALIBRATION": ids[train_count:train_count+calibration_count], "TEST": ids[train_count+calibration_count:]}


def _plan(series, policy):
    if not isinstance(policy, dict) or policy.get("schema_version") != "raw-native-diagnostic-policy-1":
        raise RawDiagnosticError("RAW_POLICY_SCHEMA_REQUIRED")
    membership = policy.get("membership")
    if not isinstance(membership, dict) or set(membership) != {"TRAIN", "CALIBRATION", "TEST"} or any(not isinstance(v, list) or len(v) < 12 for v in membership.values()):
        raise RawDiagnosticError("FIXED_RAW_MEMBERSHIP_REQUIRED")
    flattened = membership["TRAIN"] + membership["CALIBRATION"] + membership["TEST"]
    if flattened != [row["row_id"] for row in series["rows"]] or len(set(flattened)) != len(flattened):
        raise RawDiagnosticError("RAW_MEMBERSHIP_OVERLAP_ORDER_OR_COVERAGE")
    window = policy.get("window_samples")
    if type(window) is not int or not 4 <= window <= 64 or window > min(map(len, membership.values())):
        raise RawDiagnosticError("RAW_WINDOW_REQUIRED")
    q, floor = policy.get("calibration_quantile"), policy.get("raw_numeric_scale_floor")
    if type(q) not in {int, float} or not .5 < q < 1 or type(floor) not in {int, float} or not math.isfinite(floor) or floor <= 0:
        raise RawDiagnosticError("EXPLICIT_RAW_CALIBRATION_AND_SCALE_REQUIRED")
    return membership, window, q, floor


def _features(times, values, begin, end, window, cadence):
    out = {"SPIKE": [], "PERSISTENCE": []}
    for i in range(begin, end):
        # Split-local warm-up avoids consuming calibration/test rows for fit.
        for mode, width in (("SPIKE", 2), ("PERSISTENCE", window)):
            start = i-width+1
            if start < begin or any((times[j]-times[j-1]).total_seconds() != cadence for j in range(start+1, i+1)):
                out[mode].append((i, None, "SPLIT_WARMUP_OR_NATIVE_CLOCK_GAP"))
            else:
                value = abs(values[i]-values[i-1]) if mode == "SPIKE" else float(np.std(values[start:i+1]))
                out[mode].append((i, float(value), None))
    return out


def fit_raw_diagnostic(series, policy):
    times, values = validate_series(series)
    membership, window, q, floor = _plan(series, policy)
    nt, nc = len(membership["TRAIN"]), len(membership["CALIBRATION"])
    intervals = Counter((times[i]-times[i-1]).total_seconds() for i in range(1, nt))
    count = max(intervals.values()); modes = [v for v, n in intervals.items() if n == count]
    if len(modes) != 1:
        raise RawDiagnosticError("TRAIN_NATIVE_CADENCE_MODE_TIE")
    cadence = modes[0]
    train = _features(times, values, 0, nt, window, cadence)
    cal = _features(times, values, nt, nt+nc, window, cadence)
    models = {}
    for mode in train:
        a = np.array([v for _, v, e in train[mode] if e is None])
        b = np.array([v for _, v, e in cal[mode] if e is None])
        if min(len(a), len(b)) < 8:
            raise RawDiagnosticError("INSUFFICIENT_CONTIGUOUS_TRAIN_CALIBRATION")
        center = float(np.median(a)); scale = max(float(np.median(np.abs(a-center))*1.4826), floor)
        scores = np.maximum(0, (b-center)/scale if mode == "SPIKE" else (center-b)/scale)
        models[mode] = {"center": center, "scale": scale, "threshold": float(np.quantile(scores, q, method="higher")),
            "calibration_scores": sorted(map(float, scores)), "train_eligible": len(a), "calibration_eligible": len(b)}
    body = {"schema_version": ARTIFACT, "status": "RAW_DIAGNOSTIC_ONLY", "approved": False,
        "production_eligible": False, "physical_qc_evaluated": False, "unit": None, "timezone": None,
        "physical_sensor_id": None, "source_qc_interpreted": False, "source_series_sha256": digest(series),
        "source_manifest_sha256": series["source_manifest_sha256"], "grain": series["grain"], "policy": policy,
        "membership_sha256": digest(membership), "recipe_sha256": recipe_sha256(), "native_cadence_seconds": cadence,
        "cadence_authority": "TRAIN_OBSERVED_NATIVE_CLOCK_MODE_NOT_APPROVED_SCHEDULE", "models": models,
        "fit_scope": "TRAIN_ONLY_PARAMETERS_CALIBRATION_ONLY_THRESHOLDS_NO_TEST_FIT"}
    return {"artifact": body, "sha256": digest(body)}


def analyze_raw_diagnostic(series, enveloped):
    if not isinstance(enveloped, dict) or not isinstance(enveloped.get("artifact"), dict) or digest(enveloped["artifact"]) != enveloped.get("sha256"):
        raise RawDiagnosticError("RAW_ARTIFACT_CHECKSUM_MISMATCH")
    body = enveloped["artifact"]
    # Reproduce numeric fit from the immutable input; a rewritten envelope hash
    # cannot turn altered thresholds or an approval flag into a valid artifact.
    if fit_raw_diagnostic(series, body.get("policy")) != enveloped:
        raise RawDiagnosticError("RAW_ARTIFACT_PARAMETERS_OR_INPUT_CHANGED")
    times, values = validate_series(series)
    membership, window, _, _ = _plan(series, body["policy"])
    start = len(membership["TRAIN"]) + len(membership["CALIBRATION"])
    features = _features(times, values, start, len(times), window, body["native_cadence_seconds"])
    results = []
    for mode, points in features.items():
        model = body["models"][mode]
        for index, value, error in points:
            score = None if error else max(0., (value-model["center"])/model["scale"] if mode == "SPIKE" else (model["center"]-value)/model["scale"])
            rank = None if error else float(np.searchsorted(model["calibration_scores"], score, side="right")/len(model["calibration_scores"]))
            row = series["rows"][index]
            results.append({"row_id": row["row_id"], "mode": mode, "clock_raw": row["clock_raw"],
                "result_status": "NOT_EVALUATED" if error else "RAW_DIAGNOSTIC_EVALUATED", "reason": error,
                "raw_score": score, "threshold": model["threshold"], "calibration_rank": rank,
                "candidate": False if error else score > model["threshold"], "source": row["source"],
                "physical_qc": "NOT_EVALUATED", "cause_attribution": "NOT_ESTABLISHED"})
    report = {"schema_version": REPORT, "status": "RAW_DIAGNOSTIC_ONLY", "grain": series["grain"],
        "source_series_sha256": digest(series), "artifact_sha256": enveloped["sha256"], "membership_sha256": body["membership_sha256"],
        "approved": False, "production_eligible": False, "unit": None, "timezone": None,
        "results": results, "registered_models": 0, "deployed_models": 0,
        "summary": dict(Counter(r["result_status"] for r in results))}
    report["result_sha256"] = digest(report)
    return report
