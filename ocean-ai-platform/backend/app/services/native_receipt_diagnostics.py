"""Literal observation/receipt clock arithmetic, without an operational clock contract.

The immutable packets preserve exact source/depth grains and integer-microsecond
histograms. Filtered percentiles are calculated from pooled pairs, never from
channel percentiles. A native naive clock is not converted to UTC.
"""
from __future__ import annotations

import bisect
import hashlib
import json
import math
import os
import re
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = "native-receipt-diagnostics-1"
KIND = "SOURCE_CLOCK_DIFFERENCE_NOT_OPERATIONAL_DELAY"
DEFAULT_ROOT = Path("D:/AI_Observation/outputs/observation-metric-recalculation-20261009/receipt-diagnostics/release-v4")
DATA_ROOT = Path("D:/AI_Observation/data_lake")
CATALOG_ROOT = Path("D:/AI_Observation/outputs/share-validation")
SOURCES = {"GD_OBS_ST_MONTHLY", "GD_OBS_BU", "GD_OBS_VBU", "GR_OBS_ST", "HISTORICAL_RECONCILED"}
MAX_PACKET_BYTES = 64 * 1024 * 1024
NATIVE_RECEIPT_PARTITION_ROWS = 2**63
YEAR_PATTERN = r"(?:[1-9]\d{3}|0[1-9]\d{2}|00[1-9]\d|000[1-9])"
ISO_CLOCK = re.compile(r"^" + YEAR_PATTERN + r"-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12]\d|3[01])[ T](?:[01]\d|2[0-3]):[0-5]\d:[0-5]\d(?:\.\d{1,6})?(?:Z|[+-](?:[01]\d|2[0-3]):[0-5]\d)?$")
MONTH = re.compile(r"^" + YEAR_PATTERN + r"-(?:0[1-9]|1[0-2])$")
SHA = re.compile(r"^[0-9a-f]{64}$")
GRAIN = ("source_group", "station_code", "item_code", "depth_step", "depth_from", "depth_to")
COUNT_KEYS = ("raw_rows", "receipt_null_rows", "receipt_invalid_rows", "observation_null_rows",
              "observation_invalid_rows", "comparable_pair_rows", "negative_difference_rows",
              "clock_mixed_pair_rows", "receipt_field_absent_rows")


class ReceiptDiagnosticError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def canonical_bytes(body):
    return json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def sha_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def guarded_path(path, root):
    """Check every existing ancestor before the first read or write."""
    path, root = Path(os.path.abspath(path)), Path(os.path.abspath(root))
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise ReceiptDiagnosticError("PATH_OUTSIDE_ROOT") from exc
    for ancestor in [path, *path.parents]:
        if ancestor.exists() or ancestor.is_symlink():
            stat = ancestor.lstat()
            if ancestor.is_symlink() or getattr(stat, "st_file_attributes", 0) & 0x400:
                raise ReceiptDiagnosticError("REPARSE_PATH_FORBIDDEN")
    return path


def read_json(path, root, expected_sha=None, limit=MAX_PACKET_BYTES):
    path = guarded_path(path, root)
    before = path.stat()
    if not 0 < before.st_size <= limit:
        raise ReceiptDiagnosticError("JSON_SIZE_INVALID")
    data = path.read_bytes()
    after = path.stat()
    if (before.st_size, before.st_mtime_ns, before.st_ino) != (after.st_size, after.st_mtime_ns, after.st_ino):
        raise ReceiptDiagnosticError("FILE_CHANGED_DURING_READ")
    digest = hashlib.sha256(data).hexdigest()
    if expected_sha is not None and digest != expected_sha:
        raise ReceiptDiagnosticError("PACKET_CHECKSUM_MISMATCH")
    def strict_object(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise ReceiptDiagnosticError("JSON_DUPLICATE_KEY")
            value[key] = item
        return value
    def invalid_constant(value):
        raise ReceiptDiagnosticError("JSON_NONFINITE")
    def finite_float(value):
        result = float(value)
        if not math.isfinite(result):
            raise ReceiptDiagnosticError("JSON_NONFINITE")
        return result
    try:
        return json.loads(data, object_pairs_hook=strict_object, parse_constant=invalid_constant, parse_float=finite_float), digest
    except ReceiptDiagnosticError:
        raise
    except (ValueError, UnicodeError) as exc:
        raise ReceiptDiagnosticError("JSON_INVALID") from exc


def parse_clock(literal):
    """Return NULL/INVALID/NAIVE_NATIVE/EXPLICIT_OFFSET and exact microseconds."""
    if literal is None or (isinstance(literal, str) and not literal.strip()):
        return "NULL", None
    if not isinstance(literal, str) or not ISO_CLOCK.fullmatch(literal.strip()):
        return "INVALID", None
    try:
        value = datetime.fromisoformat(literal.strip().replace("Z", "+00:00"))
        aware = value.utcoffset() is not None
        origin = datetime(1970, 1, 1, tzinfo=timezone.utc) if aware else datetime(1970, 1, 1)
        delta = (value.astimezone(timezone.utc) if aware else value) - origin
        microseconds = (delta.days * 86400 + delta.seconds) * 1_000_000 + delta.microseconds
        return "EXPLICIT_OFFSET" if aware else "NAIVE_NATIVE", microseconds
    except (ValueError, OverflowError):
        return "INVALID", None


def typed_grain(row):
    return tuple((type(row.get(key)).__name__, row.get(key)) for key in GRAIN)


def weighted_quantile(histogram, q):
    """SQL quantile_cont convention for an integer-value frequency table."""
    pairs = sorted((int(value), int(count)) for value, count in histogram.items() if count)
    size = sum(count for _, count in pairs)
    if not size:
        return None
    rank = (size - 1) * q
    low, high = math.floor(rank), math.ceil(rank)
    def at(index):
        cumulative = 0
        for value, count in pairs:
            cumulative += count
            if index < cumulative:
                return value
        raise ReceiptDiagnosticError("HISTOGRAM_RANK_INVALID")
    left, right = at(low), at(high)
    return (left + (right - left) * (rank - low)) / 1_000_000


def compact_points(points):
    """Lossless constant-frequency arithmetic runs; no rounding or binning."""
    counts = Counter()
    for point in points:
        counts[point['microseconds']] += point['count']
    result = []
    for value, count in sorted(counts.items()):
        if result:
            last = result[-1]
            end = last['start'] + last['step'] * (last['points'] - 1)
            if count == last['count'] and value > end and (last['points'] == 1 or value - end == last['step']):
                if last['points'] == 1:
                    last['step'] = value - end
                last['points'] += 1
                continue
        result.append({'start':value,'step':0,'points':1,'count':count})
    return result


def histogram_runs(row):
    return row.get('difference_runs', []) + [
        {'start':p['microseconds'],'step':0,'points':1,'count':p['count']}
        for p in row['difference_histogram']]


def run_count_leq(run, value):
    if value < run['start']:
        return 0
    points = run['points'] if run['step'] == 0 else min(run['points'], (value-run['start'])//run['step']+1)
    return points * run['count']


def run_statistics(runs):
    if not runs:
        return None
    size = sum(r['points']*r['count'] for r in runs)
    minimum = min(r['start'] for r in runs)
    maximum = max(r['start']+r['step']*(r['points']-1) for r in runs)
    total = sum((2*r['start']+r['step']*(r['points']-1))*r['points']*r['count']//2 for r in runs)
    # Dense legacy runs remain immutable. Vectorize only exact, bounded integer
    # arithmetic; retain Python integers for ranges beyond signed int64.
    count_leq = lambda value: sum(run_count_leq(r,value) for r in runs)
    if len(runs)>256 and maximum-minimum <= 2**63-2 and size <= 2**63-1:
        import numpy as np
        starts=np.fromiter((r['start'] for r in runs),dtype=np.int64,count=len(runs))
        steps=np.fromiter((max(r['step'],1) for r in runs),dtype=np.int64,count=len(runs))
        points=np.fromiter((r['points'] for r in runs),dtype=np.int64,count=len(runs))
        counts=np.fromiter((r['count'] for r in runs),dtype=np.int64,count=len(runs))
        def count_leq(value):
            # Mask before subtraction so future starts cannot underflow.
            active=starts<=value
            offsets=np.subtract(value,starts,where=active,out=np.zeros_like(starts))
            matched=np.where(active,np.minimum(offsets//steps+1,points),0)
            return int(np.sum(matched*counts,dtype=np.int64))
    def quantile(q):
        rank = (size-1)*q
        def at(index):
            lo,hi = minimum,maximum
            while lo < hi:
                mid = (lo+hi)//2
                if count_leq(mid) > index:
                    hi = mid
                else:
                    lo = mid+1
            return lo
        low,high = math.floor(rank),math.ceil(rank)
        left,right = at(low),at(high)
        return (left+(right-left)*(rank-low))/1_000_000
    return {'min':minimum/1_000_000,'max':maximum/1_000_000,'mean':total/size/1_000_000,
            'p50':quantile(.5),'p95':quantile(.95)}


def pooled_stats(rows):
    result = {key: sum(row[key] for row in rows) if all(row.get(key) is not None for row in rows) else None for key in COUNT_KEYS}
    field_states = {row["receipt_field_state"] for row in rows}
    result["receipt_field_state"] = next(iter(field_states)) if len(field_states) == 1 else "MIXED" if rows else None
    if field_states == {"FIELD_ABSENT"}:
        result["receipt_null_rows"] = result["receipt_invalid_rows"] = None
    modes = {mode for row in rows for mode in row["clock_representations"]}
    points = Counter()
    runs = [run for row in rows for run in row.get('difference_runs', [])]
    for row in rows:
        points.update({point['microseconds']:point['count'] for point in row['difference_histogram']})
    runs.extend({'start':value,'step':0,'points':1,'count':count} for value,count in points.items())
    result["clock_representation"] = next(iter(modes)) if len(modes) == 1 else None
    if len(modes) > 1:
        state = "MIXED_CLOCK_REPRESENTATIONS"
    elif field_states == {"FIELD_ABSENT"}:
        state = "FIELD_ABSENT"
    elif not rows or not runs:
        state = "NO_COMPARABLE_PAIRS"
    else:
        state = "CALCULATED_NATIVE_CLOCK_DIFFERENCE"
    result.update(state=state, diagnostic_kind=KIND, approved=False, operational_delay=False,
                  physical_clock_contract_approved=False, difference_seconds=None)
    if runs and len(modes) == 1:
        if any(row.get('difference_runs') for row in rows):
            result['difference_seconds'] = run_statistics(runs)
        else:
            size=sum(points.values())
            result['difference_seconds']={'min':min(points)/1_000_000,'max':max(points)/1_000_000,
                'mean':sum(value*count for value,count in points.items())/size/1_000_000,
                'p50':weighted_quantile(points,.5),'p95':weighted_quantile(points,.95)}
    for name in ("received", "observed"):
        candidates = [row[f"last_{name}"] for row in rows if row.get(f"last_{name}")]
        # Do not compare absolute instants and naive local-calendar ticks.
        modes_for_last = {mode for row in rows for mode in row.get(f"{name}_clock_representations", [])}
        complete = all(row["raw_rows"] == 0 or row.get(f"last_{name}") is not None for row in rows)
        last = max(candidates, key=lambda entry: (entry["microseconds"], entry["literal"])) if candidates and complete and len(modes_for_last) == 1 else None
        result[f"last_{name}_clock_raw"] = last["literal"] if last else None
        result[f"last_{name}_locator"] = last["source"] if last else None
    return result


def verify_sources(files, verified_root, cache=None):
    """Fresh whole-file checks, not a previous migration ledger assertion."""
    import pyarrow.parquet as pq
    seen = set()
    for spec in files:
        if not isinstance(spec, dict) or not isinstance(spec.get("path"), str) or not SHA.fullmatch(str(spec.get("sha256", ""))):
            raise ReceiptDiagnosticError("SOURCE_DESCRIPTOR_INVALID")
        path = guarded_path(spec["path"], verified_root)
        if str(path) in seen:
            raise ReceiptDiagnosticError("SOURCE_DESCRIPTOR_DUPLICATE")
        seen.add(str(path))
        before = path.stat()
        signature = (before.st_size, before.st_mtime_ns, before.st_ino, spec["sha256"],
                     spec["bytes"], spec["footer_rows"], tuple(spec["columns"]))
        if cache is not None and cache.get(str(path)) == signature:
            continue
        if before.st_size != spec["bytes"] or sha_file(path) != spec["sha256"]:
            raise ReceiptDiagnosticError("SOURCE_CHECKSUM_MISMATCH")
        footer = pq.ParquetFile(path)
        if footer.metadata.num_rows != spec["footer_rows"] or footer.schema_arrow.names != spec["columns"]:
            raise ReceiptDiagnosticError("SOURCE_FOOTER_MISMATCH")
        after = path.stat()
        if (before.st_size, before.st_mtime_ns, before.st_ino) != (after.st_size, after.st_mtime_ns, after.st_ino):
            raise ReceiptDiagnosticError("SOURCE_CHANGED_DURING_VERIFICATION")
        if cache is not None:
            cache[str(path)] = signature


def validate_packet(packet):
    if not isinstance(packet, dict) or packet.get("schema_version") != SCHEMA or packet.get("approved") is not False or packet.get("operational_delay") is not False:
        raise ReceiptDiagnosticError("PACKET_CONTRACT_INVALID")
    if packet.get("diagnostic_kind") != KIND or packet.get("source") not in SOURCES or not MONTH.fullmatch(str(packet.get("month", ""))):
        raise ReceiptDiagnosticError("PACKET_SCOPE_INVALID")
    rows = packet.get("channels")
    if not isinstance(rows, list) or len(rows) > 20000:
        raise ReceiptDiagnosticError("PACKET_CHANNELS_INVALID")
    seen = set()
    for row in rows:
        if not isinstance(row, dict) or row.get("source_group") != packet["source"] or row.get("month") != packet["month"]:
            raise ReceiptDiagnosticError("CHANNEL_SCOPE_INVALID")
        try:
            key = typed_grain(row)
            if key in seen:
                raise ReceiptDiagnosticError("DUPLICATE_TYPED_GRAIN")
            seen.add(key)
        except TypeError as exc:
            raise ReceiptDiagnosticError("DEPTH_TYPE_INVALID") from exc
        if type(row.get("raw_rows")) is not int or not 0 <= row["raw_rows"] < 2**63:
            raise ReceiptDiagnosticError("COUNT_INVALID")
        for name in COUNT_KEYS:
            value = row.get(name)
            if value is None and name in {"receipt_null_rows", "receipt_invalid_rows"} and row.get("receipt_field_state") == "FIELD_ABSENT":
                continue
            if value is None and name in {"observation_null_rows", "observation_invalid_rows"} and packet.get("computation_level") == "SCHEMA_ONLY_RECEIPT_ABSENCE_WITH_FROZEN_CATALOG_COUNTS":
                continue
            if type(value) is not int or not 0 <= value <= row.get("raw_rows", -1):
                raise ReceiptDiagnosticError("COUNT_INVALID")
        hist = row.get("difference_histogram")
        if not isinstance(hist, list) or len(hist) > 2_000_000:
            raise ReceiptDiagnosticError("HISTOGRAM_INVALID")
        values = set()
        for point in hist:
            if not isinstance(point, dict) or type(point.get("microseconds")) is not int or not -(2**63) <= point["microseconds"] < 2**63 or type(point.get("count")) is not int or point["count"] <= 0 or point["microseconds"] in values:
                raise ReceiptDiagnosticError("HISTOGRAM_INVALID")
            values.add(point["microseconds"])
        compact = row.get('difference_runs', [])
        if not isinstance(compact,list) or len(compact)>2_000_000 or (compact and hist):
            raise ReceiptDiagnosticError('HISTOGRAM_INVALID')
        for run in compact:
            if not isinstance(run,dict) or set(run)!={'start','step','points','count'} or any(type(run[k]) is not int for k in run):
                raise ReceiptDiagnosticError('HISTOGRAM_INVALID')
            end = run['start']+run['step']*(run['points']-1)
            if not -(2**63)<=run['start']<2**63 or not -(2**63)<=end<2**63 or run['step']<0 or run['points']<=0 or run['count']<=0 or (run['points']>1 and run['step']==0) or (run['points']==1 and run['step']!=0):
                raise ReceiptDiagnosticError('HISTOGRAM_INVALID')
        runs = histogram_runs(row)
        if sum(r['points']*r['count'] for r in runs) != row["comparable_pair_rows"] or sum(run_count_leq(r,-1) for r in runs) != row["negative_difference_rows"]:
            raise ReceiptDiagnosticError("HISTOGRAM_COUNT_MISMATCH")
        if not isinstance(row.get("clock_representations"), list) or any(mode not in {"NAIVE_NATIVE", "EXPLICIT_OFFSET"} for mode in row["clock_representations"]):
            raise ReceiptDiagnosticError("CLOCK_MODE_INVALID")
        if row.get("receipt_field_state") not in {"PRESENT", "FIELD_ABSENT"}:
            raise ReceiptDiagnosticError("RECEIPT_FIELD_STATE_INVALID")
        for name in ("received", "observed"):
            modes = row.get(f"{name}_clock_representations")
            if not isinstance(modes, list) or len(set(modes)) != len(modes) or any(mode not in {"NAIVE_NATIVE", "EXPLICIT_OFFSET"} for mode in modes):
                raise ReceiptDiagnosticError("LAST_CLOCK_MODE_INVALID")
            last = row.get(f"last_{name}")
            if last is not None and (not isinstance(last, dict) or not isinstance(last.get("literal"), str)
                                     or type(last.get("microseconds")) is not int or last.get("clock_representation") not in modes
                                     or not isinstance(last.get("source"), dict)):
                raise ReceiptDiagnosticError("LAST_CLOCK_INVALID")
            if last is not None:
                kind, ticks = parse_clock(last["literal"])
                source_literal = last["source"].get("receipt_clock_raw" if name == "received" else "observation_clock_raw")
                if (kind, ticks) != (last["clock_representation"], last["microseconds"]) or source_literal != last["literal"]:
                    raise ReceiptDiagnosticError("LAST_CLOCK_LITERAL_BINDING_MISMATCH")
        if row["observation_null_rows"] is not None and row["observation_invalid_rows"] is not None and row["observation_null_rows"] + row["observation_invalid_rows"] > row["raw_rows"]:
            raise ReceiptDiagnosticError("OBSERVATION_COUNT_ACCOUNTING_INVALID")
        if row["receipt_field_state"] == "FIELD_ABSENT" and (row["comparable_pair_rows"] or row["clock_mixed_pair_rows"] or row["receipt_field_absent_rows"] != row["raw_rows"]):
            raise ReceiptDiagnosticError("ABSENT_FIELD_ACCOUNTING_INVALID")
    if not isinstance(packet.get("files"), list) or not packet["files"]:
        raise ReceiptDiagnosticError("SOURCE_FILES_MISSING")


def _months(start, end):
    if not isinstance(start, str) or not isinstance(end, str) or not MONTH.fullmatch(start) or not MONTH.fullmatch(end) or start > end:
        return None
    year, month = map(int, start.split("-"))
    months = []
    while f"{year:04d}-{month:02d}" <= end:
        months.append(f"{year:04d}-{month:02d}")
        if len(months) > 240:
            return None
        month += 1
        if month == 13:
            year, month = year + 1, 1
    return months


def receipt_diagnostics(source, start, end, station="", item="", station_scope=None, snapshot=None, root=None, source_root=None, catalog_root=None):
    """Read a verified immutable packet; unknown months never borrow July data."""
    root = Path(root or DEFAULT_ROOT)
    base = {"diagnostic_kind": KIND, "approved": False, "operational_delay": False,
            "scope": {"source": source, "from_month": start, "to_month": end, "station": station, "item": item,
                      "station_scope_applied": station_scope is not None, "snapshot": snapshot},
            "raw": None, "stations": [], "channels": []}
    months = _months(start, end)
    if months is None:
        return {**base, "state": "UNAVAILABLE_PERIOD", "reason": "정확한 YYYY-MM 기간이 필요합니다."}
    if not isinstance(source, str) or source not in SOURCES or not isinstance(snapshot, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", snapshot):
        return {**base, "state": "UNAVAILABLE", "reason": "원천 또는 검증본을 확인할 수 없습니다."}
    if not isinstance(station, str) or not isinstance(item, str):
        return {**base, "state": "INVALID_SCOPE", "reason": "시설·항목 조건은 문자열이어야 합니다."}
    if station_scope is not None:
        if not isinstance(station_scope, dict) or len(station_scope) != 1 or not set(station_scope).issubset({"include", "exclude"}):
            return {**base, "state": "INVALID_SCOPE", "reason": "시설 필터 형식이 잘못되었습니다."}
        values = next(iter(station_scope.values()))
        if not isinstance(values, (list, set, tuple)) or any(not isinstance(value, str) for value in values):
            return {**base, "state": "INVALID_SCOPE", "reason": "시설 필터 값이 잘못되었습니다."}
    packets, digests, unavailable, source_cache, dependency_cache = [], [], [], {}, {}
    try:
        for month in months:
            directory = root / snapshot / source / month
            pointer = guarded_path(directory / "published.json", root)
            if not pointer.is_file():
                unavailable.append(month)
                continue
            marker, _ = read_json(pointer, root, limit=16_384)
            if not isinstance(marker, dict) or marker.get("schema_version") != SCHEMA or marker.get("approved") is not False:
                raise ReceiptDiagnosticError("POINTER_INVALID")
            relative = marker.get("packet_path")
            if not isinstance(relative, str) or Path(relative).name != relative or not SHA.fullmatch(str(marker.get("packet_sha256", ""))):
                raise ReceiptDiagnosticError("POINTER_INVALID")
            packet, digest = read_json(directory / relative, root, marker["packet_sha256"])
            validate_packet(packet)
            if any(packet.get(key) != value or marker.get(key) != value for key, value in (("snapshot", snapshot), ("source", source), ("month", month))):
                raise ReceiptDiagnosticError("POINTER_SCOPE_MISMATCH")
            # A packet is bound to the current preserved source, not just a past checksum.
            trusted_source_root = Path(source_root or DATA_ROOT)
            if Path(packet["verified_source_root"]).resolve() != trusted_source_root.resolve():
                raise ReceiptDiagnosticError("SOURCE_ROOT_MISMATCH")
            verify_sources(packet["files"], trusted_source_root, source_cache)
            if packet.get("computation_level") == "SCHEMA_ONLY_RECEIPT_ABSENCE_WITH_FROZEN_CATALOG_COUNTS":
                dependencies = packet.get("catalog_dependencies")
                if not isinstance(dependencies, list) or len(dependencies) != 2 or packet["source"] not in {"GD_OBS_ST_MONTHLY", "GD_OBS_VBU"}:
                    raise ReceiptDiagnosticError("CATALOG_DEPENDENCIES_INVALID")
                for dependency in dependencies:
                    dependency_path = guarded_path(dependency["path"], catalog_root or CATALOG_ROOT)
                    if dependency_path.parent.name != snapshot or not SHA.fullmatch(str(dependency.get("sha256", ""))):
                        raise ReceiptDiagnosticError("CATALOG_DEPENDENCY_CHANGED")
                    before = dependency_path.stat()
                    signature = (before.st_size, before.st_mtime_ns, before.st_ino, dependency["sha256"])
                    if dependency_cache.get(str(dependency_path)) != signature:
                        if sha_file(dependency_path) != dependency["sha256"]:
                            raise ReceiptDiagnosticError("CATALOG_DEPENDENCY_CHANGED")
                        after = dependency_path.stat()
                        if (after.st_size, after.st_mtime_ns, after.st_ino, dependency["sha256"]) != signature:
                            raise ReceiptDiagnosticError("CATALOG_DEPENDENCY_CHANGED")
                        dependency_cache[str(dependency_path)] = signature
                if any("RECEIVE_TIME" in {column.upper() for column in file["columns"]} or "RECEIVED_AT_RAW" in {column.upper() for column in file["columns"]} for file in packet["files"]):
                    raise ReceiptDiagnosticError("RECEIPT_FIELD_ABSENCE_CONTRADICTED")
            packets.append(packet)
            digests.append({"month": month, "packet_sha256": digest})
        if unavailable:
            return {**base, "state": "UNAVAILABLE_PERIOD", "unavailable_months": unavailable,
                    "available_months": [packet["month"] for packet in packets], "reason": "해당 기간의 전수 시계차 기록이 없습니다. 다른 월 수치를 대입하지 않습니다."}
        rows = [row for packet in packets for row in packet["channels"]
                if (not station or row["station_code"] == station) and (not item or row["item_code"] == item)]
        if station_scope is not None:
            included = "include" in station_scope
            allowed = set(station_scope["include" if included else "exclude"])
            rows = [row for row in rows if (row["station_code"] in allowed) == included]
        by_station = {}
        for row in rows:
            by_station.setdefault(row["station_code"], []).append(row)
        overall = pooled_stats(rows)
        return {**base, "state": overall["state"] if rows else "EMPTY_SCOPE", "raw": overall,
                "stations": [{"station_code": code, "receipt_diagnostics": pooled_stats(group)} for code, group in sorted(by_station.items())],
                "channels": [{key: row[key] for key in (*GRAIN, "month")} | pooled_stats([row]) for row in rows],
                "packet_receipts": digests, "verification_level": "FRESH_PRESERVED_PARQUET_SHA_AND_FOOTER",
                "computation_levels": sorted({packet.get("computation_level", "FULL_NATIVE_ROW_CLOCK_SCAN") for packet in packets}),
                "limitations": ["음수·평균·백분위는 두 원문 시계의 산술 차입니다. 실제 통신 지연이나 정상·중단 판정이 아닙니다.",
                                "원문 시계의 시간대·동기화·허용 지연·물리 센서 운영 계약은 승인되지 않았습니다."]}
    except (OSError, KeyError, TypeError, ValueError, OverflowError) as exc:
        return {**base, "state": "INVALID_PACKET", "error_code": getattr(exc, "code", "PACKET_UNREADABLE"),
                "reason": "보존 원천 또는 시계차 기록의 검증에 실패했습니다."}


def inspect_files(entries, source, source_root):
    import pyarrow.parquet as pq
    result = []
    for entry in entries:
        path = guarded_path(entry["path"], source_root)
        before = path.stat()
        digest = sha_file(path)
        if digest != entry["sha256"]:
            raise ReceiptDiagnosticError("SOURCE_CHECKSUM_MISMATCH")
        footer = pq.ParquetFile(path)
        offsets, total = [], 0
        for index in range(footer.metadata.num_row_groups):
            offsets.append(total)
            total += footer.metadata.row_group(index).num_rows
        after = path.stat()
        if (before.st_size, before.st_mtime_ns, before.st_ino) != (after.st_size, after.st_mtime_ns, after.st_ino):
            raise ReceiptDiagnosticError("SOURCE_CHANGED_DURING_VERIFICATION")
        result.append({"path": str(path), "sha256": digest, "bytes": before.st_size,
                       "footer_rows": footer.metadata.num_rows, "columns": footer.schema_arrow.names,
                       "row_group_offsets": offsets, "source_group": source})
    return result


def _locator(sample, files_by_path):
    if sample is None:
        return None
    spec = files_by_path[str(Path(sample["filename"]))]
    row = sample["row_number"]
    group = bisect.bisect_right(spec["row_group_offsets"], row) - 1
    return {"path": spec["path"], "sha256": spec["sha256"], "file_row_number": row, "row_group": group,
            "row_index": row - spec["row_group_offsets"][group],
            "locator": f"parquet_row_group={group};row_index={row - spec['row_group_offsets'][group]}",
            "observation_clock_raw": sample["observation_clock_raw"], "receipt_clock_raw": sample["receipt_clock_raw"]}


def calculate_source(entries, source, snapshot, source_root, months=None):
    """Bounded exact DuckDB scans; large GR inputs partition by source station."""
    import duckdb
    files = inspect_files(entries, source, source_root)
    if not files:
        raise ReceiptDiagnosticError("SOURCE_FILES_MISSING")
    names = set(files[0]["columns"])
    if any(set(spec["columns"]) != names for spec in files):
        raise ReceiptDiagnosticError("SOURCE_SCHEMA_CHANGED")
    if source == "GD_OBS_ST_MONTHLY":
        station, item, observed, received = "trim(station_raw)", "trim(item_raw)", "time_raw", "NULL::VARCHAR"
        where = "record_class='OBSERVATION_SHAPED_UNVALIDATED'"
    elif source == "HISTORICAL_RECONCILED":
        station, item, observed = "station_id_raw", "item_code_raw", "observed_at_raw"
        received, where = "received_at_raw", "TRUE"
    else:
        station, item, observed = '"OBS_POST_ID"', '"OBS_ITEM_CODE"', '"OBS_TIME"'
        received, where = '"RECEIVE_TIME"' if "RECEIVE_TIME" in names else "NULL::VARCHAR", "TRUE"
    field_state = "FIELD_ABSENT" if received == "NULL::VARCHAR" else "PRESENT"
    depth = lambda name: f'"{name}"' if name in names else "NULL::VARCHAR"
    depth_columns = [depth("WATER_STEP"), depth("FR_DEPTH" if "FR_DEPTH" in names else "FROM_DEPTH"), depth("TO_DEPTH")]
    if "FR_DEPTH" in names and "FROM_DEPTH" in names:
        raise ReceiptDiagnosticError("DUAL_DEPTH_COLUMNS_REVIEW_REQUIRED")
    regex = ISO_CLOCK.pattern.replace("\\d", "[0-9]")
    def clock_type(column):
        return f"CASE WHEN {column} IS NULL OR trim({column})='' THEN 'NULL' WHEN NOT regexp_full_match(trim({column}), ?) THEN 'INVALID' WHEN regexp_matches(trim({column}), '(Z|[+-][0-9]{{2}}:[0-9]{{2}})$') THEN 'EXPLICIT_OFFSET' ELSE 'NAIVE_NATIVE' END"
    def ticks(column, kind):
        return f"CASE WHEN {kind}='EXPLICIT_OFFSET' THEN epoch_us(try_cast(trim({column}) AS TIMESTAMPTZ)) WHEN {kind}='NAIVE_NATIVE' THEN epoch_us(try_cast(trim({column}) AS TIMESTAMP)) END"
    query = f"""
    WITH raw AS (
      SELECT {station} AS station_code,{item} AS item_code,{depth_columns[0]} AS depth_step,
             {depth_columns[1]} AS depth_from,{depth_columns[2]} AS depth_to,
             {observed} AS obs_raw,{received} AS receipt_raw,filename,file_row_number,
             substr(trim({observed}),1,7) AS month
      FROM read_parquet(?,filename=true,file_row_number=true) WHERE {where}
    ), kinds AS (
      SELECT *,{clock_type('obs_raw')} AS obs_kind,{clock_type('receipt_raw')} AS recv_kind FROM raw
    ), parsed AS (
      SELECT *,{ticks('obs_raw','obs_kind')} AS obs_us,{ticks('receipt_raw','recv_kind')} AS recv_us FROM kinds
    ), pairs AS (
      SELECT *,CASE WHEN obs_kind IN ('NAIVE_NATIVE','EXPLICIT_OFFSET') AND obs_us IS NULL THEN 'INVALID' ELSE obs_kind END AS observation_state,
               CASE WHEN recv_kind IN ('NAIVE_NATIVE','EXPLICIT_OFFSET') AND recv_us IS NULL THEN 'INVALID' ELSE recv_kind END AS receipt_state,
               CASE WHEN obs_kind=recv_kind AND obs_us IS NOT NULL AND recv_us IS NOT NULL THEN recv_us-obs_us END AS delta_us
      FROM parsed
    )
    SELECT station_code,item_code,depth_step,depth_from,depth_to,month,observation_state,receipt_state,
           CASE WHEN delta_us IS NOT NULL THEN obs_kind END AS pair_mode,delta_us,count(*) AS n,
           arg_min(struct_pack(filename:=filename,row_number:=file_row_number,observation_clock_raw:=obs_raw,receipt_clock_raw:=receipt_raw),filename||':'||lpad(cast(file_row_number AS VARCHAR),16,'0')) AS example,
           max(recv_us) AS last_recv_us,arg_max(receipt_raw,recv_us) AS last_recv_raw,
           arg_max(struct_pack(filename:=filename,row_number:=file_row_number,observation_clock_raw:=obs_raw,receipt_clock_raw:=receipt_raw),recv_us) AS last_recv_example,
           max(obs_us) AS last_obs_us,arg_max(obs_raw,obs_us) AS last_obs_raw,
           arg_max(struct_pack(filename:=filename,row_number:=file_row_number,observation_clock_raw:=obs_raw,receipt_clock_raw:=receipt_raw),obs_us) AS last_obs_example
    FROM pairs GROUP BY station_code,item_code,depth_step,depth_from,depth_to,month,observation_state,receipt_state,pair_mode,delta_us
    ORDER BY station_code,item_code,depth_step,depth_from,depth_to,month,observation_state,receipt_state,pair_mode,delta_us
    """
    # Keep raw locator/string aggregate states once per grain/clock category.
    # Per-difference groups need only exact integer frequencies; a repeated
    # receipt clock otherwise creates millions of redundant raw string states.
    keys='station_code,item_code,depth_step,depth_from,depth_to,month,observation_state,receipt_state'
    pair_mode="CASE WHEN delta_us IS NOT NULL THEN obs_kind END AS pair_mode"
    prefix=query.split('    SELECT station_code,item_code,depth_step,depth_from,depth_to,month,observation_state,receipt_state,')[0]
    sample='struct_pack(filename:=filename,row_number:=file_row_number,observation_clock_raw:=obs_raw,receipt_clock_raw:=receipt_raw)'
    metadata_query=prefix+f"""
    SELECT {keys},{pair_mode},
      arg_min({sample},filename||':'||lpad(cast(file_row_number AS VARCHAR),16,'0')) AS example,
      min(delta_us) AS min_delta_us,arg_min({sample},delta_us) AS min_delta_example,
      max(delta_us) AS max_delta_us,arg_max({sample},delta_us) AS max_delta_example,
      max(recv_us) AS last_recv_us,arg_max(receipt_raw,recv_us) AS last_recv_raw,
      arg_max({sample},recv_us) AS last_recv_example,
      max(obs_us) AS last_obs_us,arg_max(obs_raw,obs_us) AS last_obs_raw,
      arg_max({sample},obs_us) AS last_obs_example
    FROM pairs GROUP BY {keys},pair_mode
    """
    query=prefix+f"""
    SELECT {keys},{pair_mode},delta_us,count(*) AS n
    FROM pairs GROUP BY {keys},pair_mode,delta_us
    ORDER BY {keys},pair_mode,delta_us
    """
    connection = duckdb.connect(":memory:")
    connection.execute("SET threads=1")
    connection.execute("SET preserve_insertion_order=false")
    connection.execute("SET memory_limit='1536MB'")
    connection.execute("SET TimeZone='UTC'")
    spill_root=Path(source_root).resolve().parent/'work/native-receipt-spill'
    spill_root.mkdir(parents=True,exist_ok=True)
    spill=tempfile.TemporaryDirectory(prefix='clock-',dir=spill_root)
    connection.execute('SET temp_directory=?',[spill.name])
    def stream_aggregates():
        try:
            paths=[spec['path'] for spec in files]
            metadata_cursor=connection.execute(metadata_query,[paths,regex,regex])
            metadata_columns=[column[0] for column in metadata_cursor.description]
            metadata_keys=(*keys.split(','),'pair_mode')
            metadata={}
            for values in metadata_cursor.fetchall():
                row=dict(zip(metadata_columns,values))
                metadata[tuple(row[name] for name in metadata_keys)]=row

            def materialize(columns,values):
                aggregate=dict(zip(columns,values))
                detail=metadata[tuple(aggregate[name] for name in metadata_keys)]
                for name in ('last_recv_us','last_recv_raw','last_recv_example','last_obs_us','last_obs_raw','last_obs_example'):
                    aggregate[name]=detail[name]
                delta=aggregate['delta_us']
                aggregate['example']=(detail['example'] if delta is None else
                                      detail['min_delta_example'] if delta==detail['min_delta_us'] else
                                      detail['max_delta_example'] if delta==detail['max_delta_us'] else None)
                return aggregate

            partitioned=source=='GR_OBS_ST' and sum(spec['footer_rows'] for spec in files)>NATIVE_RECEIPT_PARTITION_ROWS
            if not partitioned:
                try:
                    cursor=connection.execute(query,[paths,regex,regex])
                except duckdb.OutOfMemoryException:
                    if source!='GR_OBS_ST':
                        raise
                    partitioned=True
                else:
                    columns=[column[0] for column in cursor.description]
                    while batch := cursor.fetchmany(4096):
                        for values in batch:
                            yield materialize(columns,values)
                    return
            partitions=connection.execute(f'SELECT DISTINCT {station} FROM read_parquet(?) WHERE {where}',[paths]).fetchall()
            for partition in partitions:
                current=query.replace(f'WHERE {where}\n',f'WHERE {where} AND ({station}) IS NOT DISTINCT FROM ?\n',1) if partitioned else query
                parameters=[paths,partition[0],regex,regex] if partitioned else [paths,regex,regex]
                try:
                    cursor=connection.execute(current,parameters)
                except duckdb.OutOfMemoryException:
                    # No rows from this station have been yielded. Retry exact
                    # source grains, retaining their original physical locators.
                    expressions=[station,item,*depth_columns]
                    grains=connection.execute(
                        f"SELECT DISTINCT {','.join(expressions)} FROM read_parquet(?) "
                        f"WHERE {where} AND ({station}) IS NOT DISTINCT FROM ?",
                        [paths,partition[0]],
                    ).fetchall()
                    filters=' AND '.join(f'({expression}) IS NOT DISTINCT FROM ?' for expression in expressions)
                    grain_query=query.replace(f'WHERE {where}\n',f'WHERE {where} AND {filters}\n',1)
                    for grain in grains:
                        cursor=connection.execute(grain_query,[paths,*grain,regex,regex])
                        columns=[column[0] for column in cursor.description]
                        while batch := cursor.fetchmany(4096):
                            for values in batch:
                                yield materialize(columns,values)
                else:
                    columns=[column[0] for column in cursor.description]
                    while batch := cursor.fetchmany(4096):
                        for values in batch:
                            yield materialize(columns,values)
        finally:
            connection.close()
            assert Path(spill.name).resolve().parent==spill_root.resolve()
            spill.cleanup()
    aggregated = stream_aggregates()
    by_month, excluded, excluded_examples = {}, Counter(), []
    files_by_path = {spec["path"]: spec for spec in files}
    for aggregate in aggregated:
        month = aggregate["month"]
        if not isinstance(month, str) or not MONTH.fullmatch(month) or (months is not None and month not in months):
            excluded[str(month)] += aggregate["n"]
            if len(excluded_examples) < 10:
                excluded_examples.append({"native_month_literal": month, "rows": aggregate["n"],
                                          "source": _locator(aggregate["example"], files_by_path)})
            continue
        row_key = tuple((type(aggregate[name]).__name__, aggregate[name]) for name in ("station_code", "item_code", "depth_step", "depth_from", "depth_to"))
        month_rows = by_month.setdefault(month, {})
        if row_key not in month_rows:
            row = {name: aggregate[name] for name in ("station_code", "item_code", "depth_step", "depth_from", "depth_to")}
            row.update(source_group=source, month=month, receipt_field_state=field_state,
                       clock_representations=[], received_clock_representations=[], observed_clock_representations=[],
                       difference_histogram=[], examples=[], last_received=None, last_observed=None)
            row.update({name: 0 for name in COUNT_KEYS})
            month_rows[row_key] = row
        row = month_rows[row_key]
        count, observed_state, receipt_state = aggregate["n"], aggregate["observation_state"], aggregate["receipt_state"]
        row["raw_rows"] += count
        row["observation_null_rows"] += count if observed_state == "NULL" else 0
        row["observation_invalid_rows"] += count if observed_state == "INVALID" else 0
        row["receipt_null_rows"] += count if receipt_state == "NULL" else 0
        row["receipt_invalid_rows"] += count if receipt_state == "INVALID" else 0
        row["receipt_field_absent_rows"] += count if field_state == "FIELD_ABSENT" else 0
        mixed = observed_state in {"NAIVE_NATIVE", "EXPLICIT_OFFSET"} and receipt_state in {"NAIVE_NATIVE", "EXPLICIT_OFFSET"} and observed_state != receipt_state
        row["clock_mixed_pair_rows"] += count if mixed else 0
        delta = aggregate["delta_us"]
        if delta is not None:
            row["comparable_pair_rows"] += count
            row["negative_difference_rows"] += count if delta < 0 else 0
            row["difference_histogram"].append({"microseconds": delta, "count": count})
            if len(row['difference_histogram']) >= 4096:
                row.setdefault('difference_runs', []).extend(compact_points(row['difference_histogram']))
                row['difference_histogram'].clear()
            if aggregate["pair_mode"] not in row["clock_representations"]:
                row["clock_representations"].append(aggregate["pair_mode"])
        # Retain representative failing literals and signed extremes without copying all raw values.
        category = "MIXED_PAIR" if mixed else f"OBS_{observed_state}_RECEIPT_{receipt_state}" if observed_state in {"INVALID", "NULL"} or receipt_state in {"INVALID", "NULL"} else "COMPARABLE"
        existing = row["examples"]
        if category != "COMPARABLE":
            if not any(entry["category"] == category for entry in existing):
                existing.append({'category':category,'difference_microseconds':delta,'source':_locator(aggregate['example'],files_by_path)})
        elif aggregate['example'] is not None:
            extremes = row.setdefault('_comparable_extremes',[])
            candidate = {'category':category,'difference_microseconds':delta,'_source':aggregate['example']}
            extremes[:] = [min(extremes+[candidate],key=lambda r:r['difference_microseconds']),max(extremes+[candidate],key=lambda r:r['difference_microseconds'])]
        for name, prefix, state in (("received", "recv", receipt_state), ("observed", "obs", observed_state)):
            tick = aggregate[f"last_{prefix}_us"]
            if tick is not None:
                if state not in row[f"{name}_clock_representations"]:
                    row[f"{name}_clock_representations"].append(state)
                old = row[f"last_{name}"]
                if old is None or tick > old["microseconds"]:
                    row[f"last_{name}"] = {'literal':aggregate[f'last_{prefix}_raw'],'microseconds':tick,
                        'clock_representation':state,'source':_locator(aggregate[f'last_{prefix}_example'],files_by_path)}
    checked_at = datetime.now(timezone.utc).isoformat()
    packets = []
    for month, groups in sorted(by_month.items()):
        rows = list(groups.values())
        for row in rows:
            for example in row.pop('_comparable_extremes',[]):
                row['examples'].append({'category':example['category'],'difference_microseconds':example['difference_microseconds'],
                    'source':_locator(example['_source'],files_by_path)})
            # A naive and an aware pair can share a numeric delta, consolidate frequencies.
            if row.get('difference_runs'):
                row['difference_runs'].extend(compact_points(row['difference_histogram']))
                row['difference_histogram'].clear()
            else:
                histogram = Counter()
                for point in row['difference_histogram']:
                    histogram[point['microseconds']] += point['count']
                row['difference_histogram'] = [{'microseconds': value, 'count': count} for value, count in sorted(histogram.items())]
            row["clock_representations"].sort()
            row["received_clock_representations"].sort()
            row["observed_clock_representations"].sort()
            if field_state == "FIELD_ABSENT":
                row["receipt_null_rows"] = row["receipt_invalid_rows"] = None
            row["statistics"] = pooled_stats([row])
        rows.sort(key=lambda row: canonical_bytes({name: row[name] for name in GRAIN}))
        packet = {"schema_version": SCHEMA, "diagnostic_kind": KIND, "source": source, "month": month, "snapshot": snapshot,
                  "generated_at": checked_at, "approved": False, "operational_delay": False,
                  "verified_source_root": str(Path(source_root)), "files": files,
                  "raw": pooled_stats(rows), "channels": rows, "excluded_native_month_rows": dict(excluded),
                  "excluded_native_month_examples": excluded_examples,
                  "method": {"time_basis": "ORIGINAL_NATIVE_CALENDAR_WITH_EXPLICIT_OFFSET_WHEN_PRESENT",
                             "precision": "MICROSECONDS_MAX_SIX_FRACTION_DIGITS", "difference": "RECEIVE_MINUS_OBSERVATION",
                             "quantiles": "POOLED_PAIR_QUANTILE_CONT", "date_only": "INVALID_NO_MIDNIGHT_INFERENCE",
                             "mixed_naive_offset": "EXCLUDED_PAIR_AND_NO_MIXED_REPRESENTATION_AGGREGATE",
                             "identifier_transform": "STRIP_SQLPLUS_PADDING" if source == "GD_OBS_ST_MONTHLY" else "IDENTITY",
                             "clock_timezone_inferred": False, "reception_state_calculated": False}}
        validate_packet(packet)
        packets.append(packet)
    verify_sources(files, source_root)
    return packets


def publish_packets(packets, output_root):
    output_root = Path(output_root)
    receipts = []
    for packet in packets:
        validate_packet(packet)
        directory = guarded_path(output_root / packet["snapshot"] / packet["source"] / packet["month"], output_root)
        directory.mkdir(parents=True, exist_ok=True)
        data = canonical_bytes(packet)
        digest = hashlib.sha256(data).hexdigest()
        name = f"packet-{digest}.json"
        path = guarded_path(directory / name, output_root)
        if path.exists():
            if path.read_bytes() != data:
                raise ReceiptDiagnosticError("IMMUTABLE_PACKET_CHANGED")
        else:
            with path.open("xb") as handle:
                handle.write(data)
        marker = {key: packet[key] for key in ("schema_version", "snapshot", "source", "month")}
        marker.update(packet_path=name, packet_sha256=digest, approved=False)
        marker_path = guarded_path(directory / "published.json", output_root)
        marker_data = canonical_bytes(marker)
        if marker_path.exists():
            if marker_path.read_bytes() != marker_data:
                raise ReceiptDiagnosticError("IMMUTABLE_POINTER_EXISTS")
        else:
            with marker_path.open("xb") as handle:
                handle.write(marker_data)
        receipts.append({"source": packet["source"], "month": packet["month"], "packet_path": str(path),
                         "packet_sha256": digest, "raw_rows": packet["raw"]["raw_rows"],
                         "channel_months": len(packet["channels"]), "raw": packet["raw"]})
    return receipts


def calculate_field_absence_coverage(snapshot_path, source_root, sources=("GD_OBS_ST_MONTHLY", "GD_OBS_VBU"), emit=None):
    """Fresh schema/SHA/footers + exact frozen catalogue, without a raw row scan.

    This proves a missing field, not a receipt count or a clock. Null/invalid
    observation categories are deliberately unknown unless separately scanned.
    """
    import duckdb
    import pyarrow.parquet as pq
    snapshot_path = Path(snapshot_path)
    catalog_path = snapshot_path / "station-item-month-validation.parquet"
    assets_path = snapshot_path / "file-only-timeseries.duckdb"
    catalog_sha, assets_sha = sha_file(catalog_path), sha_file(assets_path)
    catalog = pq.read_table(catalog_path).to_pylist()
    db = duckdb.connect(str(assets_path), read_only=True, config={"threads": 1, "memory_limit": "256MB"})
    try:
        cursor = db.execute("SELECT * FROM source_assets")
        names = [column[0] for column in cursor.description]
        assets = [dict(zip(names, values)) for values in cursor.fetchall()]
    finally:
        db.close()
    packets = []
    for source in sources:
        if source not in {"GD_OBS_ST_MONTHLY", "GD_OBS_VBU"}:
            raise ReceiptDiagnosticError("SCHEMA_ABSENCE_SOURCE_UNSUPPORTED")
        by_month = {}
        for asset in assets:
            if asset["source_group"] != source:
                continue
            matches = re.findall(r"(?<!\d)(20\d{2}(?:0[1-9]|1[0-2]))(?!\d)", str(asset["source_path"]).replace("\\", "/").rsplit("/", 1)[-1])
            if len(matches) != 1:
                raise ReceiptDiagnosticError("SOURCE_ASSET_MONTH_AMBIGUOUS")
            month = matches[0][:4] + "-" + matches[0][4:]
            by_month.setdefault(month, []).append({"path": asset["parquet_path"], "sha256": asset["parquet_sha256"]})
        for month, entries in sorted(by_month.items()):
            files = inspect_files(entries, source, source_root)
            if any({name.upper() for name in file["columns"]} & {"RECEIVE_TIME", "RECEIVED_AT_RAW"} for file in files):
                raise ReceiptDiagnosticError("RECEIPT_FIELD_ABSENCE_CONTRADICTED")
            selected = [row for row in catalog if row["source_group"] == source and str(row["month"])[:7] == month]
            if not selected:
                raise ReceiptDiagnosticError("SOURCE_CATALOG_MONTH_MISSING")
            rows = []
            for original in selected:
                row = {key: original[key] for key in GRAIN}
                row.update(month=month, raw_rows=original["held_rows"], receipt_field_state="FIELD_ABSENT",
                           receipt_null_rows=None, receipt_invalid_rows=None, observation_null_rows=None, observation_invalid_rows=None,
                           comparable_pair_rows=0, negative_difference_rows=0, clock_mixed_pair_rows=0,
                           receipt_field_absent_rows=original["held_rows"], clock_representations=[],
                           received_clock_representations=[], observed_clock_representations=[], difference_histogram=[],
                           examples=[], last_received=None, last_observed=None,
                           catalog_first_clock=original["first_clock"].isoformat(sep=" ") if isinstance(original["first_clock"], datetime) else original["first_clock"],
                           catalog_last_clock=original["last_clock"].isoformat(sep=" ") if isinstance(original["last_clock"], datetime) else original["last_clock"],
                           catalog_count_basis="EXACT_FROZEN_TYPED_GRAIN_NOT_NEW_ROW_RESCAN")
                row["statistics"] = pooled_stats([row])
                rows.append(row)
            if sum(row["raw_rows"] for row in rows) > sum(file["footer_rows"] for file in files):
                raise ReceiptDiagnosticError("CATALOG_ROWS_EXCEED_PHYSICAL_FOOTERS")
            rows.sort(key=lambda row: canonical_bytes({key: row[key] for key in GRAIN}))
            packet = {"schema_version": SCHEMA, "source": source, "month": month, "snapshot": snapshot_path.name,
                      "diagnostic_kind": KIND, "approved": False, "operational_delay": False,
                      "generated_at": datetime.now(timezone.utc).isoformat(),
                      "computation_level": "SCHEMA_ONLY_RECEIPT_ABSENCE_WITH_FROZEN_CATALOG_COUNTS",
                      "verified_source_root": str(Path(source_root)), "files": files, "channels": rows, "raw": pooled_stats(rows),
                      "catalog_dependencies": [{"path": str(catalog_path), "sha256": catalog_sha}, {"path": str(assets_path), "sha256": assets_sha}],
                      "method": {"receipt_field_state": "SCHEMA_ABSENCE_ALL_EXACT_SOURCE_ASSETS",
                                 "row_count_basis": "FROZEN_VERIFIED_CATALOG", "new_row_clock_scan": False,
                                 "observation_null_or_invalid_categories": "NOT_RECALCULATED", "clock_timezone_inferred": False}}
            validate_packet(packet)
            packets.append(packet)
            if emit:
                emit({"stage": "FIELD_ABSENCE_SOURCE_MONTH_VERIFIED", "source": source, "month": month,
                      "files": len(files), "channel_months": len(rows), "catalog_held_rows": packet["raw"]["raw_rows"]})
    if sha_file(catalog_path) != catalog_sha or sha_file(assets_path) != assets_sha:
        raise ReceiptDiagnosticError("CATALOG_CHANGED_DURING_VERIFICATION")
    return packets
