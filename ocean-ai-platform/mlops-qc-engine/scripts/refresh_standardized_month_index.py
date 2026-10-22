"""Scan each standard monthly export once for several existing index scopes."""
from __future__ import annotations

import csv
import ntpath
import re
from collections import Counter
from pathlib import Path
from scripts.workspace_paths import ensure_no_z_access

OBS_HEADER = b"OBS_POST_ID,OBS_ITEM_CODE,OBS_TIME,OBS_VALUE,QC_FLAG,MQC_FLAG,N1_AQC_FLAG"


def scan_standard_month(
    path: str | Path, ym: str, scopes: list[str], *, chunk_size: int = 64 * 1024 * 1024,
) -> dict:
    """Produce the existing cache schema, deduplicating G/B by scoped minute.

    The C regular-expression engine filters irrelevant station/sensor rows before
    Python CSV parsing. Every requested scope gets an explicit, scanned result,
    including a genuine zero when that sensor has no rows in the file.
    """
    ensure_no_z_access(path)
    if not re.fullmatch(r"\d{4}(?:0[1-9]|1[0-2])", ym) or chunk_size < 1:
        raise ValueError("유효한 월과 양수 청크 크기가 필요합니다.")
    requested = sorted(set(scopes))
    pairs = {}
    for scope in requested:
        parts = scope.split("|")
        if len(parts) != 2 or not re.fullmatch(r"DT_\d{4}", parts[0]) or not re.fullmatch(r"TIDE_LEVEL_[A-Z0-9_]+", parts[1]):
            raise ValueError("관측소|조위센서 형식의 스코프가 필요합니다.")
        pairs[tuple(parts)] = scope
    if not requested:
        raise ValueError("최소 하나의 스코프가 필요합니다.")
    stations = [value.encode("ascii") for value in sorted({pair[0] for pair in pairs})]
    pair_patterns = [
        rb'"?[ \t]*' + re.escape(station.encode("ascii"))
        + rb'[ \t]*"?[ \t]*,[ \t]*"?[ \t]*' + re.escape(sensor.encode("ascii"))
        + rb'[ \t]*"?[ \t]*,'
        for station, sensor in pairs
    ]
    pattern = re.compile(
        rb'^[ \t]*(?:' + b"|".join(pair_patterns) + rb')[^\r\n]*(?:\r?\n|$)', re.MULTILINE,
    )
    from scripts.dataset_preview import timestamp

    source = Path(path).resolve()
    before = source.stat()
    states: dict[str, dict[str, int]] = {scope: {} for scope in requested}
    counters: dict[str, Counter] = {scope: Counter() for scope in requested}
    year, month = int(ym[:4]), int(ym[4:])

    def consume(block: bytes) -> None:
        matches = []
        for station in stations:
            offset = 0
            while True:
                position = block.find(station, offset)
                if position < 0:
                    break
                start = block.rfind(b"\n", 0, position) + 1
                offset = position + len(station)
                if block.rfind(b",", start, position) >= 0:
                    continue
                match = pattern.match(block, start)
                if match:
                    matches.append(match)
                    offset = match.end()
        for match in matches:
            fields = next(csv.reader([match.group().decode("utf-8")], skipinitialspace=True, strict=True))
            if len(fields) != 7:
                raise ValueError("표준 관측 CSV 데이터 행은 7개 컬럼이어야 합니다.")
            station, sensor = fields[0].strip(), fields[1].strip()
            scope = pairs.get((station, sensor))
            if scope is None:
                continue
            flag = fields[5].strip()
            if flag not in {"G", "B"}:
                continue
            counts = counters[scope]
            counts["rows_scanned"] += 1
            try:
                stamp = timestamp(fields[2].strip(), time_alignment="minute_floor")
            except ValueError:
                counts["invalid_time_rows"] += 1
                continue
            if (stamp.year, stamp.month) != (year, month):
                counts["outside_month_rows"] += 1
                continue
            minute = stamp.isoformat()
            bit = 1 if flag == "G" else 2
            states[scope][minute] = states[scope].get(minute, 0) | bit

    with source.open("rb", buffering=1024 * 1024) as stream:
        if stream.readline(1024 * 1024).rstrip(b"\r\n") != OBS_HEADER:
            raise ValueError("1행에 정식 7개 컬럼 헤더가 있는 표준 관측 CSV가 필요합니다.")
        tail = b""
        while True:
            chunk = stream.read(chunk_size)
            if not chunk:
                break
            block = tail + chunk
            end = block.rfind(b"\n") + 1
            if end:
                consume(block[:end])
            tail = block[end:]
            if len(tail) > 1024 * 1024:
                raise ValueError("관측 CSV에서 비정상적으로 긴 데이터 행을 발견했습니다.")
        if tail:
            consume(tail)
    after = source.stat()
    if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns):
        raise ValueError("월별 집계 중 원본 CSV가 변경되었습니다.")
    fingerprint = {"path": str(source), "bytes": after.st_size, "mtime_ns": after.st_mtime_ns}
    result = {}
    for scope in requested:
        station, sensor = scope.split("|")
        flags = Counter(states[scope].values())
        counters[scope]["conflict_minutes"] = flags[3]
        result[scope] = {
            "fingerprints": [dict(fingerprint)], "errors": [],
            "counts": dict(counters[scope]), "complete": True, "pending": False,
            "entries": [{
                "station": station, "sensor": sensor, "ym": ym,
                "normal_g_count": flags[1], "anomaly_b_count": flags[2],
                "has_real_anomalies": flags[2] > 0, "count_source": "raw_csv",
                "complete": True, "raw_count_pending": False,
            }],
        }
    return result
