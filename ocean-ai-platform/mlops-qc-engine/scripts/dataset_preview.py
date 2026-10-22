"""Read-only, streaming CSV inspection. Never trains models or accesses a DB."""
import csv
import contextlib
import hashlib
import importlib
import json
import math
import re
import sys
import sqlite3
import tempfile
import threading
import time
import uuid
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[1]
for _path_entry in (str(BASE), str(BASE / "scripts")):
    if _path_entry not in sys.path:
        sys.path.insert(0, _path_entry)
sys.modules.setdefault("dataset_preview", sys.modules[__name__])
sys.modules.setdefault("scripts.dataset_preview", sys.modules[__name__])

from scripts.local_trial_manifest import _JSON_LOCK, _is_retryable_permission_error, read_json, write_json
from scripts.workspace_paths import (
    ensure_no_z_access,
    get_standard_obs_root,
    get_standard_prd_root,
    get_tide_2023_export_root,
    reject_z_path,
    resolve_additional_data_roots,
    resolve_data_workspace,
    resolve_export_roots,
    resolve_project_path,
    resolve_training_csv_path,
)

WORKSPACE = resolve_data_workspace(BASE)
OUTPUT = BASE / "reports/dataset_previews"
MONTHLY_INDEX_PATH = BASE / "reports/monthly_anomaly_index.json"
MONTHLY_INDEX_LOCK = threading.Lock()
MONTHLY_INDEX_SYNC_MAX_BYTES = 32 * 1024 * 1024
MONTHLY_INDEX_CSV_CHUNK_THRESHOLD = 32 * 1024 * 1024
SHA256_CACHE_PATH = BASE / "reports/dataset_jobs/sha256_cache.json"
SHA256_CACHE_LOCK = threading.Lock()
SHA256_CACHE_MIN_BYTES = 1024 * 1024
_SHA256_MEM_CACHE: dict[tuple[str, int, int], str] = {}
_SHA256_DISK_LOADED = False
_DEFAULT_EXPORTS = resolve_export_roots()
EXPORT_ROOT = _DEFAULT_EXPORTS["export_root"]
TIDE_EXPORT_ROOT = _DEFAULT_EXPORTS["tide_export_root"]
TIDE_EXPORT_UTF8_ROOT = _DEFAULT_EXPORTS["tide_export_utf8_root"]
TIDE_2023_EXPORT_ROOT = get_tide_2023_export_root()
ALLOWED_ROOTS = tuple(resolve_additional_data_roots(BASE))
OBS_FIELDS = {"OBS_POST_ID", "OBS_ITEM_CODE", "OBS_TIME", "OBS_VALUE", "MQC_FLAG"}
PRD_FIELDS = {"OBS_POST_ID", "OBS_TIME", "TIDE_PRE_VAL"}
LOG_FIELDS = {"timestamp", "station", "sensor", "real_obs", "tide_pre_val", "mqc_flag"}
SQLPLUS_GD_OBS_ST_RAW = (
    "OBS_POST_I",
    "OBS_ITEM_CODE",
    "OBS_TIME",
    "OBS_VALUE",
    "QC",
    "MQ",
    "N1_AQC_FLA",
)
SQLPLUS_GD_OBS_ST_MAP = {
    "OBS_POST_I": "OBS_POST_ID",
    "OBS_ITEM_CODE": "OBS_ITEM_CODE",
    "OBS_TIME": "OBS_TIME",
    "OBS_VALUE": "OBS_VALUE",
    "QC": "QC_FLAG",
    "MQ": "MQC_FLAG",
    "N1_AQC_FLA": "N1_AQC_FLAG",
}
MAX_ROWS = 200_000_000


def allowed_roots():
    roots = []
    seen = set()
    for root in (resolve_data_workspace(BASE), WORKSPACE, *resolve_additional_data_roots(BASE)):
        ensure_no_z_access(root)
        key = str(root).casefold()
        if key not in seen:
            seen.add(key)
            roots.append(root)
    return tuple(roots)


def source_path(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("CSV 파일 경로를 선택해 주세요.")
    ensure_no_z_access(value)
    original = Path(value).expanduser().resolve()
    roots = []
    for root in allowed_roots():
        ensure_no_z_access(root)
        roots.append(root.resolve() if root.exists() else root)
    if not any(original.is_relative_to(root) for root in roots):
        raise ValueError("관할해역 작업 폴더 또는 설정된 외부 반출 폴더의 CSV를 선택해 주세요.")
    path = resolve_training_csv_path(original, BASE)
    ensure_no_z_access(path)
    if not any(path.is_relative_to(root) for root in roots):
        raise ValueError("관할해역 작업 폴더 또는 설정된 외부 반출 폴더의 CSV를 선택해 주세요.")
    if path.suffix.lower() != ".csv" or not path.is_file():
        raise ValueError("완성된 .csv 파일을 선택해 주세요. .part 파일은 사용할 수 없습니다.")
    if path.stat().st_size > 20 * 1024 ** 3:
        raise ValueError("이번 검사에서는 파일당 최대 20GB까지 지원합니다.")
    return path


def _load_sha256_disk_cache_unlocked() -> None:
    global _SHA256_DISK_LOADED
    if _SHA256_DISK_LOADED:
        return
    _SHA256_DISK_LOADED = True
    if not SHA256_CACHE_PATH.is_file():
        return
    try:
        raw = read_json(SHA256_CACHE_PATH)
        for entry in raw.get("entries", []):
            key = (str(entry["path"]), int(entry["bytes"]), int(entry["mtime_ns"]))
            val = str(entry["sha256"])
            if len(val) == 64:
                _SHA256_MEM_CACHE[key] = val
    except (OSError, ValueError, KeyError, TypeError):
        pass


def _save_sha256_disk_cache_unlocked() -> None:
    try:
        SHA256_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": "sha256-cache-1",
            "entries": [
                {"path": k[0], "bytes": k[1], "mtime_ns": k[2], "sha256": v}
                for k, v in list(_SHA256_MEM_CACHE.items())[-500:]
            ],
        }
        tid = threading.get_ident()
        tmp = SHA256_CACHE_PATH.with_name(f"{SHA256_CACHE_PATH.name}.part.{tid}.{uuid.uuid4().hex[:8]}")
        try:
            with _JSON_LOCK:
                tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            for attempt in range(16):
                try:
                    with _JSON_LOCK:
                        tmp.replace(SHA256_CACHE_PATH)
                    break
                except OSError as error:
                    if not _is_retryable_permission_error(error) or attempt == 15:
                        raise
                    time.sleep(0.05)
        finally:
            with contextlib.suppress(OSError):
                tmp.unlink(missing_ok=True)
    except OSError:
        pass


def sha256(path):
    p = Path(path)
    stat = p.stat()
    resolved = str(p.resolve())
    use_cache = stat.st_size >= SHA256_CACHE_MIN_BYTES and "dataset_test_fixtures" not in resolved
    cache_key = (resolved, stat.st_size, stat.st_mtime_ns) if use_cache else None
    if cache_key is not None:
        with SHA256_CACHE_LOCK:
            _load_sha256_disk_cache_unlocked()
            cached = _SHA256_MEM_CACHE.get(cache_key)
            if cached is not None:
                return cached
    digest = hashlib.sha256()
    with p.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    result = digest.hexdigest()
    if cache_key is not None:
        after = p.stat()
        if (after.st_size, after.st_mtime_ns) == (stat.st_size, stat.st_mtime_ns):
            with SHA256_CACHE_LOCK:
                _SHA256_MEM_CACHE[cache_key] = result
                _save_sha256_disk_cache_unlocked()
    return result


def normalize_header(raw_header, column_normalization="strict"):
    if column_normalization not in {"strict", "sqlplus_gd_obs_st"}:
        raise ValueError("지원하지 않는 컬럼 정규화 옵션입니다.")
    if tuple(raw_header) == SQLPLUS_GD_OBS_ST_RAW:
        return [SQLPLUS_GD_OBS_ST_MAP[col] for col in raw_header], dict(SQLPLUS_GD_OBS_ST_MAP)
    return list(raw_header), None


def rows(path, encoding, column_normalization="strict", header_metadata=None):
    if encoding not in {"utf-8-sig", "cp949"}:
        raise ValueError("인코딩은 UTF-8 또는 CP949를 선택해 주세요.")
    with path.open(encoding=encoding, newline="") as stream:
        # Detect only the complete known GD_OBS_ST SQLPlus signature. Short or
        # unrelated headings keep their names in both supported parsing modes.
        reader = csv.reader(stream, strict=True)
        raw_header = None
        for _ in range(50):
            line = next(reader, None)
            if line is None:
                raise ValueError("CSV에서 컬럼 이름을 찾지 못했습니다.")
            if not line or not any(x.strip() for x in line):
                continue
            if re.match(r"^(old|new)\s+\d+:", line[0].strip(), re.I):
                continue
            if all(re.fullmatch(r"[-\s]+", value) for value in line if value.strip()):
                continue
            raw_header = [x.strip() for x in line]
            break
        if raw_header is None or len(set(raw_header)) != len(raw_header):
            raise ValueError("컬럼 이름이 없거나 중복되었습니다.")
        if header_metadata is not None:
            header_metadata["raw_header"] = list(raw_header)
        header, _ = normalize_header(raw_header, column_normalization)
        yield header
        for index, line in enumerate(reader, 1):
            if index > MAX_ROWS:
                raise ValueError("2억 행 제한을 넘었습니다. 기간별 파일로 나누어 주세요.")
            if not line or not any(x.strip() for x in line):
                continue
            stripped = [x.strip() for x in line]
            if all(re.fullmatch(r"[-\s]+", x) for x in stripped if x):
                continue
            if stripped == raw_header or stripped == header or tuple(stripped) == SQLPLUS_GD_OBS_ST_RAW:
                continue
            if re.match(r"^(old|new)\s+\d+:", stripped[0], re.I):
                continue
            if len(stripped) == 1 and re.match(r"^\d+\s+rows?\s+selected\.?$", stripped[0], re.I):
                continue
            if len(stripped) != len(header):
                raise ValueError(f"CSV {reader.line_num}행의 컬럼 수가 다릅니다. SQL 출력 메시지도 확인해 주세요.")
            yield dict(zip(header, stripped))


def profile(value, encoding="utf-8-sig", column_normalization="strict"):
    path = source_path(value)
    header_metadata = {}
    iterator = rows(path, encoding, column_normalization=column_normalization, header_metadata=header_metadata)
    try:
        header = next(iterator)
        sqlplus_detected = tuple(header_metadata["raw_header"]) == SQLPLUS_GD_OBS_ST_RAW
        kind = (
            "historical"
            if LOG_FIELDS <= set(header)
            else "observation"
            if OBS_FIELDS <= set(header)
            else "prediction"
            if PRD_FIELDS <= set(header)
            else "unsupported"
        )
        sample = []
        for _, row in zip(range(5), iterator):
            sample.append(row)
        return {
            "path": str(path),
            "bytes": path.stat().st_size,
            "columns": header,
            "kind": kind,
            "sqlplus_gd_obs_st_detected": sqlplus_detected,
            "column_normalization": column_normalization,
            "sample": sample,
            "sample_only": True,
        }
    finally:
        iterator.close()


def _monthly_file_key(path: Path):
    observation = re.fullmatch(r"(?:data_|GD_OBS_ST_)(\d{6})\.csv", path.name, re.I)
    if observation:
        return "observation", observation.group(1)
    prediction = re.fullmatch(r"(?:pred_|GO_TIDE_PRE_DATA_)(\d{6})\.csv", path.name, re.I)
    return ("prediction", prediction.group(1)) if prediction else None


def _monthly_source_priority(path: Path):
    """Give local standardized files precedence without depending on scan order."""
    key = _monthly_file_key(path)
    if key is None:
        return 99
    if key[0] == "observation":
        if path.parent == get_standard_obs_root(BASE):
            return 0
        return 1 if path.name.upper().startswith("GD_OBS_ST_") else 2
    if path.parent == get_standard_prd_root(BASE):
        return 0
    if path.name.lower().startswith("pred_"):
        return 5
    exports = resolve_export_roots()
    for priority, root in enumerate((exports["tide_2023_export_root"], exports["tide_export_root"],
                                     exports["tide_export_utf8_root"], exports["export_root"]), 1):
        if path.is_relative_to(root):
            return priority
    return 4


def _display_name(path: Path) -> str:
    ws = resolve_data_workspace(BASE)
    exports = resolve_export_roots()
    for root, label in ((get_standard_obs_root(BASE), "로컬 표준 관측/GD_OBS_ST/"),
                        (get_standard_prd_root(BASE), "로컬 표준 예측/GO_TIDE_PRE_DATA/"),
                        (exports["tide_2023_export_root"], "2023 예측 반출/")):
        if path.is_relative_to(root):
            return label + str(path.relative_to(root))
    if path.is_relative_to(ws):
        return str(path.relative_to(ws))
    if path.is_relative_to(BASE):
        return str(path.relative_to(BASE))
    for key, label in (("export_root", "반출자료/"), ("tide_export_root", "조위반출/"),
                       ("tide_export_utf8_root", "조위반출_UTF8/")):
        if path.is_relative_to(exports[key]):
            return label + str(path.relative_to(exports[key]))
    return path.name


def _iter_checked_csvs(folder: Path, *, recursive: bool = True):
    """List a directory only after checking it and every encountered child."""
    ensure_no_z_access(folder)
    if not folder.exists():
        return
    pending = [(folder, frozenset())]
    while pending:
        current, ancestors = pending.pop()
        ensure_no_z_access(current)
        key = str(current.resolve()).casefold()
        if key in ancestors:
            raise ValueError(f"카탈로그 경로의 링크 순환(cycle): {current}")
        for child in sorted(current.iterdir()):
            ensure_no_z_access(child)
            if child.is_dir():
                if recursive:
                    pending.append((child, ancestors | {key}))
            elif child.suffix.lower() == ".csv" and child.is_file():
                yield child


def catalog():
    ws = resolve_data_workspace(BASE)
    exports = resolve_export_roots()
    candidates = []
    seen_files = set()
    scan_folders = [
        get_standard_obs_root(BASE), get_standard_prd_root(BASE),
        exports["tide_2023_export_root"], exports["export_root"],
        exports["tide_export_root"], exports["tide_export_utf8_root"],
        ws / "정형데이터", ws / "DB_Exporting",
    ]
    for extra_root in resolve_additional_data_roots(BASE):
        if extra_root not in (ws, BASE) and extra_root not in scan_folders:
            scan_folders.append(extra_root)
    for folder in scan_folders:
        for csv_path in sorted(_iter_checked_csvs(folder)):
            key = str(csv_path.resolve()).casefold()
            reject_z_path(key)
            if key not in seen_files:
                seen_files.add(key)
                candidates.append(csv_path)
    logs = ws / "2026년_AI_품질처리_데이터백업/운영코드/AI_anomaly_detection/debug_logs"
    for csv_path in sorted(_iter_checked_csvs(logs, recursive=False))[:80]:
        key = str(csv_path.resolve()).casefold()
        if key not in seen_files:
            seen_files.add(key)
            candidates.append(csv_path)
    # Catalog every distinct source path, including the preserved D: exports.
    # Automatic month matching chooses one preferred source independently.
    candidates.sort(key=lambda path: (_monthly_source_priority(path), str(path).casefold()))
    mapping = ws / "2026년_AI_품질처리_데이터백업/운영코드/AI_anomaly_detection/mappingBySea.csv"
    ensure_no_z_access(mapping)
    if mapping.is_file():
        with mapping.open(encoding="utf-8-sig", newline="") as stream:
            stations = list(csv.DictReader(stream))
    else:
        stations = _fallback_mapping_rows_from_manifest()
    return {
        "files": [{"path": str(path), "name": _display_name(path), "bytes": path.stat().st_size}
                  for path in candidates],
        "mapping": stations,
        "workspace": str(ws),
        "allowed_roots": [str(root) for root in allowed_roots() if root.exists()],
    }


def _fallback_mapping_rows_from_manifest() -> list[dict[str, str]]:
    """Build mappingBySea.csv compatible rows from 2025_operation_64_manifest.json when external backup is absent."""
    manifest_path = BASE / "manifests" / "2025_operation_64_manifest.json"
    if not manifest_path.is_file():
        return []
    try:
        manifest = read_json(manifest_path)
    except Exception:
        return []
    by_code: dict[str, dict[str, str]] = {}
    for item in manifest.get("models") or []:
        code = str(item.get("station_code") or "").strip()
        if not code:
            continue
        row = by_code.setdefault(
            code,
            {
                "NAME": str(item.get("station_name") or code).strip(),
                "CODE": code,
                "SEA_INFO": str(item.get("sea_info") or "").strip(),
                "INFO_FLAG": str(item.get("info_flag") or "Y").strip(),
                "TIDE1(MAIN)": "",
                "TIDE2(SUB1)": "",
                "TIDE3(SUB2)": "",
            },
        )
        col = str(item.get("mapping_column") or "TIDE1(MAIN)").strip()
        sensor = str(item.get("sensor_code") or "").strip()
        if col in row and sensor:
            row[col] = sensor
        elif sensor and not row["TIDE1(MAIN)"]:
            row["TIDE1(MAIN)"] = sensor
    return list(by_code.values())


def timestamp(value, time_alignment="exact_minute"):
    if time_alignment not in {"exact_minute", "minute_floor"}:
        raise ValueError("시각 정렬 기준은 exact_minute 또는 minute_floor만 지원합니다.")
    raw = value.replace("T", " ").strip()
    try:
        result = datetime.fromisoformat(raw)
    except ValueError as exc:
        raise ValueError("시각은 YYYY-MM-DD HH:MM:SS 형식이어야 합니다.") from exc
    if result.tzinfo is not None:
        raise ValueError("시간대 표시가 없는 시각만 결합합니다.")
    if time_alignment == "exact_minute":
        if result.second or result.microsecond:
            raise ValueError("시간대 표시가 없는 정각 1분 시각만 결합합니다.")
        return result
    return result.replace(second=0, microsecond=0)


def finite(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _accumulate_target_row(
    row: dict,
    kind: str,
    effective_alignment: str,
    start: datetime,
    stop: datetime,
    counts: Counter,
    values: dict,
    source_timestamps: dict,
    conflicts: set,
    anomaly_values: dict,
    anomaly_source_timestamps: dict,
    anomaly_conflicts: set,
) -> None:
    counts["target_rows"] += 1
    raw_ts = row["timestamp" if kind == "historical" else "OBS_TIME"].strip()
    try:
        time = timestamp(raw_ts, time_alignment=effective_alignment)
    except ValueError:
        counts["invalid_time"] += 1
        return
    if effective_alignment == "minute_floor" and not raw_ts.endswith(":00"):
        counts["non_zero_second_normalized_rows"] += 1
    if not start <= time < stop:
        counts["outside_period"] += 1
        return
    counts["within_period"] += 1
    if kind != "prediction":
        mqc_val = row["mqc_flag" if kind == "historical" else "MQC_FLAG"].strip()
        if mqc_val != "G":
            counts["mqc_not_G"] += 1
            if mqc_val == "B":
                counts["mqc_B_rows"] += 1
                b_val = (
                    (finite(row["real_obs"]), finite(row["tide_pre_val"]))
                    if kind == "historical"
                    else (finite(row["OBS_VALUE"]),)
                )
                if not any(x is None for x in b_val):
                    if time in anomaly_conflicts or time in conflicts or time in values:
                        anomaly_conflicts.add(time)
                        anomaly_values.pop(time, None)
                        anomaly_source_timestamps.pop(time, None)
                    elif time in anomaly_values:
                        if anomaly_values[time] != b_val:
                            anomaly_conflicts.add(time)
                            del anomaly_values[time]
                            anomaly_source_timestamps.pop(time, None)
                    else:
                        anomaly_values[time] = b_val
                        anomaly_source_timestamps[time] = raw_ts
            return
    if kind == "historical":
        val = (finite(row["real_obs"]), finite(row["tide_pre_val"]))
    else:
        val = (finite(row["OBS_VALUE" if kind == "observation" else "TIDE_PRE_VAL"]),)
    if any(x is None for x in val):
        counts["missing_or_nonfinite_value"] += 1
        return
    if time in anomaly_values:
        anomaly_conflicts.add(time)
        anomaly_values.pop(time, None)
        anomaly_source_timestamps.pop(time, None)
    if time in conflicts:
        counts["duplicate_conflict_rows"] += 1
    elif time in values:
        if values[time] == val:
            counts["identical_duplicate_rows"] += 1
        else:
            conflicts.add(time)
            del values[time]
            source_timestamps.pop(time, None)
            counts["duplicate_conflict_rows"] += 1
    else:
        values[time] = val
        source_timestamps[time] = raw_ts


def read_values(
    path,
    kind,
    station,
    sensor,
    start,
    stop,
    encoding,
    progress,
    column_normalization="strict",
    time_alignment="exact_minute",
    return_anomalies=False,
) -> Any:
    counts = Counter()
    values = {}
    source_timestamps = {}
    conflicts = set()
    anomaly_values = {}
    anomaly_source_timestamps = {}
    anomaly_conflicts = set()
    path_obj = Path(path)
    required = {"historical": LOG_FIELDS, "observation": OBS_FIELDS, "prediction": PRD_FIELDS}[kind]
    station_key = "station" if kind == "historical" else "OBS_POST_ID"
    sensor_key = "sensor" if kind == "historical" else "OBS_ITEM_CODE"
    effective_alignment = time_alignment if kind != "prediction" else "exact_minute"

    if path_obj.stat().st_size >= MONTHLY_INDEX_CSV_CHUNK_THRESHOLD:
        if encoding not in {"utf-8-sig", "cp949"}:
            raise ValueError("인코딩은 UTF-8 또는 CP949를 선택해 주세요.")
        pd: Any = importlib.import_module("pandas")
        with path_obj.open(encoding=encoding, newline="") as stream:
            reader = csv.reader(stream, strict=True)
            raw_header = None
            header_line = 0
            for _ in range(50):
                line = next(reader, None)
                if line is None:
                    raise ValueError("CSV에서 컬럼 이름을 찾지 못했습니다.")
                if not line or not any(x.strip() for x in line):
                    continue
                if re.match(r"^(old|new)\s+\d+:", line[0].strip(), re.I):
                    continue
                raw_header = [x.strip() for x in line]
                header_line = reader.line_num
                break
            if raw_header is None or len(set(raw_header)) != len(raw_header):
                raise ValueError("컬럼 이름이 없거나 중복되었습니다.")
        header, _ = normalize_header(raw_header, column_normalization)
        if not required <= set(header):
            raise ValueError("필수 컬럼이 없습니다: " + ", ".join(sorted(required - set(header))))
        rename = dict(zip(raw_header, header))
        usecols = [col for col in raw_header if rename[col] in required]
        header_token_map = {rename[col]: {rename[col], col} for col in usecols}
        with pd.read_csv(
            path_obj,
            encoding=encoding,
            skiprows=header_line,
            names=raw_header,
            usecols=usecols,
            dtype=str,
            keep_default_na=False,
            na_filter=False,
            chunksize=250_000,
        ) as chunks:
            for frame in chunks:
                frame = frame.rename(columns=rename)
                frame_cols = list(frame.columns)
                st_series = frame[station_key]
                non_dt_mask = ~st_series.str.startswith("DT_", na=False)
                skipped = 0
                if non_dt_mask.any():
                    for non_dt_vals in frame.loc[non_dt_mask].itertuples(index=False, name=None):
                        stripped = [v.strip() if isinstance(v, str) else "" for v in non_dt_vals]
                        non_empty = [x for x in stripped if x]
                        if not non_empty:
                            skipped += 1
                        elif all(re.fullmatch(r"-+", x) for x in non_empty):
                            skipped += 1
                        elif all(
                            val in header_token_map[col]
                            for col, val in zip(frame_cols, stripped)
                            if val
                        ):
                            skipped += 1
                        elif len(non_empty) == 1 and re.match(r"^\d+\s+rows?\s+selected\.?$", non_empty[0], re.I):
                            skipped += 1
                counts["rows_scanned"] += len(frame) - skipped
                if counts["rows_scanned"] > MAX_ROWS:
                    raise ValueError("2억 행 제한을 넘었습니다. 기간별 파일로 나누어 주세요.")
                if callable(progress):
                    progress({"stage": kind, "file": path_obj.name, "rows_scanned": counts["rows_scanned"]})
                mask = st_series.str.contains(station, regex=False, na=False)
                if kind != "prediction":
                    mask &= frame[sensor_key].str.contains(sensor, regex=False, na=False)
                if not mask.any():
                    continue
                sub = frame.loc[mask]
                cols = list(sub.columns)
                for row_vals in sub.itertuples(index=False, name=None):
                    row_dict = {col: (val.strip() if isinstance(val, str) else "") for col, val in zip(cols, row_vals)}
                    if row_dict[station_key] != station or (kind != "prediction" and row_dict[sensor_key] != sensor):
                        continue
                    _accumulate_target_row(
                        row_dict,
                        kind,
                        effective_alignment,
                        start,
                        stop,
                        counts,
                        values,
                        source_timestamps,
                        conflicts,
                        anomaly_values,
                        anomaly_source_timestamps,
                        anomaly_conflicts,
                    )
        counts["conflict_minutes"] = len(conflicts)
        counts["usable_unique_minutes"] = len(values)
        if kind != "prediction":
            counts["usable_anomaly_minutes"] = len(anomaly_values)
        if return_anomalies:
            return values, dict(counts), source_timestamps, anomaly_values, anomaly_source_timestamps
        return values, dict(counts), source_timestamps

    iterator = rows(path, encoding, column_normalization=column_normalization)
    try:
        header = set(next(iterator))
        if not required <= header:
            raise ValueError("필수 컬럼이 없습니다: " + ", ".join(sorted(required - header)))
        for row in iterator:
            if not isinstance(row, dict):
                raise ValueError("CSV 데이터 행을 해석하지 못했습니다.")
            counts["rows_scanned"] += 1
            if counts["rows_scanned"] % 50000 == 0 and callable(progress):
                progress({"stage": kind, "file": path_obj.name, "rows_scanned": counts["rows_scanned"]})
            if row[station_key] != station or (kind != "prediction" and row[sensor_key] != sensor):
                continue
            _accumulate_target_row(
                row,
                kind,
                effective_alignment,
                start,
                stop,
                counts,
                values,
                source_timestamps,
                conflicts,
                anomaly_values,
                anomaly_source_timestamps,
                anomaly_conflicts,
            )
        counts["conflict_minutes"] = len(conflicts)
        counts["usable_unique_minutes"] = len(values)
        if kind != "prediction":
            counts["usable_anomaly_minutes"] = len(anomaly_values)
        if counts["rows_scanned"] == 0 or counts["rows_scanned"] % 50000 != 0:
            if callable(progress):
                progress({"stage": kind, "file": path_obj.name, "rows_scanned": counts["rows_scanned"]})
        if return_anomalies:
            return values, dict(counts), source_timestamps, anomaly_values, anomaly_source_timestamps
        return values, dict(counts), source_timestamps
    finally:
        iterator.close()


def continuity(times, start, stop):
    segments = []
    longest_gap = 0
    previous = start - timedelta(minutes=1)
    for time in times:
        gap = int((time - previous).total_seconds() // 60) - 1
        longest_gap = max(longest_gap, gap)
        if not segments or gap:
            segments.append({"start": time.isoformat(sep=" "), "end": time.isoformat(sep=" "), "minutes": 1})
        else:
            segments[-1]["end"] = time.isoformat(sep=" ")
            segments[-1]["minutes"] += 1
        previous = time
    longest_gap = max(longest_gap, int((stop - previous).total_seconds() // 60) - 1)
    return {
        "segments": len(segments),
        "longest_continuous_minutes": max((x["minutes"] for x in segments), default=0),
        "longest_missing_minutes": longest_gap,
        "contiguous_4_input_1_target_windows": sum(max(0, x["minutes"] - 4) for x in segments),
        "largest_segments": sorted(segments, key=lambda x: x["minutes"], reverse=True)[:10],
    }


def _count_labeled_anomaly_eval_windows(valid_times, anomaly_times) -> int:
    """Count anomaly ('B') timestamps preceded by 4 contiguous normal ('G') minutes."""
    valid_set = {
        datetime.fromisoformat(t) if isinstance(t, str) else t
        for t in valid_times
    }
    anom_list = [
        datetime.fromisoformat(t) if isinstance(t, str) else t
        for t in anomaly_times
    ]
    return sum(
        1
        for t in anom_list
        if all((t - timedelta(minutes=offset)) in valid_set for offset in (4, 3, 2, 1))
    )


def _read_multiple_values(
    paths,
    kind,
    station,
    sensor,
    start,
    stop,
    encoding="utf-8-sig",
    progress=lambda _: None,
    column_normalization: str = "strict",
    time_alignment: str = "exact_minute",
    return_anomalies: bool = False,
) -> Any:
    if len(paths) == 1:
        def _single_progress(info, _name=Path(paths[0]).name):
            if callable(progress):
                progress({
                    **info,
                    "file": info.get("file", _name),
                    "file_index": info.get("file_index", 1),
                    "total_files": info.get("total_files", 1),
                })
        return read_values(
            paths[0],
            kind,
            station,
            sensor,
            start,
            stop,
            encoding,
            _single_progress,
            column_normalization=column_normalization,
            time_alignment=time_alignment,
            return_anomalies=return_anomalies,
        )
    merged_values = {}
    merged_sources = {}
    conflicts = set()
    merged_anomalies = {}
    merged_anomaly_sources = {}
    anomaly_conflicts = set()
    agg_counts = Counter()
    intra_conflicts = 0
    total_files = len(paths)
    for file_idx, path in enumerate(paths, 1):
        prior_rows = int(agg_counts.get("rows_scanned", 0))

        def _file_progress(info, _idx=file_idx, _name=Path(path).name, _prior=prior_rows):
            if callable(progress):
                progress({
                    **info,
                    "file": info.get("file", _name),
                    "file_index": _idx,
                    "total_files": total_files,
                    "rows_scanned": _prior + int(info.get("rows_scanned", 0)),
                })
        res = read_values(
            path,
            kind,
            station,
            sensor,
            start,
            stop,
            encoding,
            _file_progress,
            column_normalization=column_normalization,
            time_alignment=time_alignment,
            return_anomalies=True,
        )
        vals, counts, src_ts, anom_vals, anom_src_ts = res
        intra_conflicts += counts.get("conflict_minutes", 0)
        for k, v in counts.items():
            if k not in {"conflict_minutes", "usable_unique_minutes", "usable_anomaly_minutes"}:
                agg_counts[k] += v
        for t, val in vals.items():
            if t in merged_anomalies:
                anomaly_conflicts.add(t)
                merged_anomalies.pop(t, None)
                merged_anomaly_sources.pop(t, None)
            if t in conflicts:
                agg_counts["duplicate_conflict_rows"] += 1
            elif t in merged_values:
                if merged_values[t] == val:
                    agg_counts["identical_duplicate_rows"] += 1
                else:
                    conflicts.add(t)
                    del merged_values[t]
                    merged_sources.pop(t, None)
                    agg_counts["duplicate_conflict_rows"] += 1
            else:
                merged_values[t] = val
                merged_sources[t] = src_ts.get(t, t.isoformat(sep=" "))
        for t, b_val in anom_vals.items():
            if t in anomaly_conflicts or t in conflicts or t in merged_values:
                anomaly_conflicts.add(t)
                merged_anomalies.pop(t, None)
                merged_anomaly_sources.pop(t, None)
            elif t in merged_anomalies:
                if merged_anomalies[t] != b_val:
                    anomaly_conflicts.add(t)
                    del merged_anomalies[t]
                    merged_anomaly_sources.pop(t, None)
            else:
                merged_anomalies[t] = b_val
                merged_anomaly_sources[t] = anom_src_ts.get(t, t.isoformat(sep=" "))
    agg_counts["conflict_minutes"] = intra_conflicts + len(conflicts)
    agg_counts["usable_unique_minutes"] = len(merged_values)
    if kind != "prediction":
        agg_counts["usable_anomaly_minutes"] = len(merged_anomalies)
    if return_anomalies:
        return merged_values, dict(agg_counts), merged_sources, merged_anomalies, merged_anomaly_sources
    return merged_values, dict(agg_counts), merged_sources


def analyze(request, progress=lambda _: None):
    mode = request.get("mode", "paired")
    if mode not in {"paired", "historical"}:
        raise ValueError("관측·예측 CSV 두 벌 또는 과거 상세 로그를 선택해 주세요.")
    station, sensor = request.get("station", ""), request.get("sensor", "")
    if not re.fullmatch(r"DT_\d{4}", station) or not re.fullmatch(r"[A-Z0-9_]+", sensor):
        raise ValueError("관측소와 센서를 선택해 주세요.")
    try:
        start = datetime.strptime(request["date_start"], "%Y-%m-%d")
        stop = datetime.strptime(request["date_end"], "%Y-%m-%d") + timedelta(days=1)
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("시작 날짜와 마지막 날짜를 선택해 주세요.") from exc
    if not start < stop or stop - start > timedelta(days=366 * 5):
        raise ValueError("기간은 시작 날짜 이상, 최대 5년으로 선택해 주세요.")
    encoding = request.get("encoding", "utf-8-sig")
    column_normalization = request.get("column_normalization", "strict")
    time_alignment = request.get("time_alignment", "exact_minute")
    if column_normalization not in {"strict", "sqlplus_gd_obs_st"}:
        raise ValueError("지원하지 않는 컬럼 정규화 옵션입니다.")
    if time_alignment not in {"exact_minute", "minute_floor"}:
        raise ValueError("시각 정렬 기준은 exact_minute 또는 minute_floor만 지원합니다.")
    raw_obs_paths = request.get("observation_paths") or [request.get("observation_path")]
    observations = [source_path(p) for p in raw_obs_paths if p]
    if not observations:
        raise ValueError("CSV 파일을 선택해 주세요.")
    if mode == "paired":
        raw_prd_paths = request.get("prediction_paths") or [request.get("prediction_path")]
        predictions = [source_path(p) for p in raw_prd_paths if p]
        if not predictions:
            raise ValueError("예측 CSV 파일을 선택해 주세요.")
    else:
        predictions = []
    paths = observations + predictions
    total_all_files = max(1, len(paths))
    sources = []
    file_stats = []
    for idx, path in enumerate(paths, 1):
        stat = path.stat()
        file_stats.append((stat.st_size, stat.st_mtime_ns))
        if callable(progress):
            progress({
                "stage": "hash",
                "stage_index": 1,
                "stage_total": 4,
                "percent": round(10.0 * idx / total_all_files, 1),
                "file": path.name,
                "file_index": idx,
                "total_files": len(paths),
                "stage_file_index": idx,
                "stage_total_files": len(paths),
                "rows_scanned": 0,
            })
        sources.append({"path": str(path), "bytes": stat.st_size, "sha256": sha256(path)})
    obs_stage_end = 50.0 if predictions else 85.0

    def _obs_progress(info):
        if not callable(progress):
            return
        f_idx = int(info.get("file_index", 1))
        f_tot = max(1, int(info.get("total_files", len(observations))))
        pct = round(10.0 + (obs_stage_end - 10.0) * (f_idx / f_tot), 1)
        progress({
            **info,
            "stage": info.get("stage", "historical" if mode == "historical" else "observation"),
            "stage_index": 2,
            "stage_total": 4,
            "percent": pct,
            "file_index": f_idx,
            "total_files": len(paths),
            "stage_file_index": f_idx,
            "stage_total_files": f_tot,
            "rows_scanned": int(info.get("rows_scanned", 0)),
        })

    obs, obs_counts, obs_source_ts, anom_obs, anom_source_ts = _read_multiple_values(
        observations,
        "historical" if mode == "historical" else "observation",
        station,
        sensor,
        start,
        stop,
        encoding,
        _obs_progress,
        column_normalization=column_normalization,
        time_alignment=time_alignment,
        return_anomalies=True,
    )
    obs_rows_total = int(obs_counts.get("rows_scanned", 0))
    if predictions:
        def _prd_progress(info):
            if not callable(progress):
                return
            f_idx = int(info.get("file_index", 1))
            f_tot = max(1, int(info.get("total_files", len(predictions))))
            pct = round(50.0 + 35.0 * (f_idx / f_tot), 1)
            progress({
                **info,
                "stage": "prediction",
                "stage_index": 3,
                "stage_total": 4,
                "percent": pct,
                "file_index": len(observations) + f_idx,
                "total_files": len(paths),
                "stage_file_index": f_idx,
                "stage_total_files": f_tot,
                "rows_scanned": obs_rows_total + int(info.get("rows_scanned", 0)),
            })

        prd, prd_counts, _ = _read_multiple_values(
            predictions,
            "prediction",
            station,
            sensor,
            start,
            stop,
            encoding,
            _prd_progress,
            column_normalization="strict",
            time_alignment="exact_minute",
        )
        times = sorted(obs.keys() & prd.keys())
        values = [(t, obs[t][0], prd[t][0], obs_source_ts.get(t, t.isoformat(sep=" "))) for t in times]
        anom_times = sorted((anom_obs.keys() & prd.keys()) - set(times))
        anom_values = [
            (t, anom_obs[t][0], prd[t][0], anom_source_ts.get(t, t.isoformat(sep=" ")))
            for t in anom_times
        ]
    else:
        prd_counts = None
        times = sorted(obs)
        values = [(t, obs[t][0], obs[t][1], obs_source_ts.get(t, t.isoformat(sep=" "))) for t in times]
        anom_times = sorted(set(anom_obs.keys()) - set(times))
        anom_values = [
            (t, anom_obs[t][0], anom_obs[t][1], anom_source_ts.get(t, t.isoformat(sep=" ")))
            for t in anom_times
        ]
    for path, source, before_stat in zip(paths, sources, file_stats):
        after_stat = path.stat()
        if (after_stat.st_size, after_stat.st_mtime_ns) != before_stat or source["sha256"] != sha256(path):
            raise ValueError("검사 도중 원본 CSV가 변경되었습니다. 결과를 저장하지 않습니다.")
    expected = int((stop - start).total_seconds() // 60)
    monthly = []
    cursor = start
    actual = Counter(t.strftime("%Y-%m") for t in times)
    while cursor < stop:
        next_month = (cursor.replace(day=28) + timedelta(days=4)).replace(day=1)
        end = min(next_month, stop)
        count = int((end - cursor).total_seconds() // 60)
        key = cursor.strftime("%Y-%m")
        monthly.append({
            "month": key,
            "expected_minutes": count,
            "valid_minutes": actual[key],
            "valid_percent": round(actual[key] / count * 100, 3),
        })
        cursor = end
    total_rows_scanned = obs_rows_total + int((prd_counts or {}).get("rows_scanned", 0))
    if callable(progress):
        progress({
            "stage": "saving_csv",
            "stage_index": 4,
            "stage_total": 4,
            "percent": 90.0,
            "file": "joined.csv",
            "file_index": len(paths),
            "total_files": len(paths),
            "stage_file_index": len(paths),
            "stage_total_files": len(paths),
            "rows_scanned": total_rows_scanned,
        })
    data_id = datetime.now().strftime("%Y%m%dT%H%M%S") + "_" + uuid.uuid4().hex[:8]
    folder = OUTPUT / data_id
    folder.mkdir(parents=True, exist_ok=False)
    joined = folder / "joined.csv"
    with joined.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["OBS_POST_ID", "OBS_ITEM_CODE", "OBS_TIME", "OBS", "PRD"])
        for time, obs_value, prd_value, _ in values:
            writer.writerow([station, sensor, time.isoformat(sep=" "), obs_value, prd_value])
    provenance_csv = folder / "joined_provenance.csv"
    with provenance_csv.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["OBS_POST_ID", "OBS_ITEM_CODE", "OBS_TIME", "SOURCE_OBS_TIMESTAMP", "OBS", "PRD"])
        for time, obs_value, prd_value, src_ts in values:
            writer.writerow([station, sensor, time.isoformat(sep=" "), src_ts, obs_value, prd_value])
    labeled_rows = sorted(
        [(t, o, p, src_ts, "G") for t, o, p, src_ts in values]
        + [(t, o, p, src_ts, "B") for t, o, p, src_ts in anom_values],
        key=lambda item: item[0],
    )
    labeled_csv = folder / "joined_labeled.csv"
    with labeled_csv.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["OBS_POST_ID", "OBS_ITEM_CODE", "OBS_TIME", "SOURCE_OBS_TIMESTAMP", "OBS", "PRD", "MQC_FLAG"])
        for time, obs_value, prd_value, src_ts, mqc_flag in labeled_rows:
            writer.writerow([station, sensor, time.isoformat(sep=" "), src_ts, obs_value, prd_value, mqc_flag])
    contiguous_4g_1b_windows = _count_labeled_anomaly_eval_windows(times, anom_times)
    continuity_report = continuity(times, start, stop)
    applied_mapping = dict(SQLPLUS_GD_OBS_ST_MAP) if column_normalization == "sqlplus_gd_obs_st" else None
    filter_desc = (
        "MQC_FLAG exactly G; finite OBS and PRD; exact one-minute timestamp; conflicting duplicates excluded"
        if time_alignment == "exact_minute"
        else "MQC_FLAG exactly G; finite OBS and PRD; minute_floor timestamp alignment (source_obs_timestamp preserved); conflicting duplicates excluded"
    )
    summary = {
        "dataset_id": data_id,
        "schema_version": "dataset-preview-1",
        "inspector_sha256": sha256(Path(__file__)),
        "source_read_only": True,
        "mode": mode,
        "provenance": "HISTORICAL_DEBUG_LOG" if mode == "historical" else "USER_SELECTED_LOCAL_CSV",
        "station": station,
        "sensor": sensor,
        "date_start": start.date().isoformat(),
        "date_end": (stop - timedelta(days=1)).date().isoformat(),
        "period_end_exclusive": stop.isoformat(sep=" "),
        "expected_minutes": expected,
        "valid_minutes": len(times),
        "anomaly_minutes": len(anom_times),
        "labeled_minutes": len(labeled_rows),
        "contiguous_labeled_4g_input_1b_target_windows": contiguous_4g_1b_windows,
        "valid_percent": round(len(times) / expected * 100, 3),
        "equivalent_days": round(len(times) / 1440, 6),
        "missing_minutes": expected - len(times),
        "unmatched_observation_minutes": len(obs) - len(times),
        "first_valid_time": times[0].isoformat(sep=" ") if times else None,
        "last_valid_time": times[-1].isoformat(sep=" ") if times else None,
        "column_normalization": column_normalization,
        "applied_column_mapping": applied_mapping,
        "time_alignment": time_alignment,
        "observation": obs_counts,
        "prediction": prd_counts,
        "continuity": continuity_report,
        "monthly": monthly,
        "meets_draft_365_day_volume": len(times) >= 365 * 1440,
        "training_approved": False,
        "training_executed": False,
        "sources": sources,
        "encoding": encoding,
        "filter": filter_desc,
        "joined_csv": {"path": str(joined), "sha256": sha256(joined)},
        "joined_provenance_csv": {"path": str(provenance_csv), "sha256": sha256(provenance_csv)},
        "joined_labeled_csv": {"path": str(labeled_csv), "sha256": sha256(labeled_csv)},
        "preview": [
            {"time": t.isoformat(sep=" "), "source_obs_timestamp": src_ts, "obs": o, "prd": p}
            for t, o, p, src_ts in values[:100]
        ],
    }
    write_json(folder / "dataset_manifest.json", summary)
    return summary


def load_result(data_id):
    if not re.fullmatch(r"\d{8}T\d{6}_[0-9a-f]{8}", data_id):
        raise ValueError("잘못된 검사 기록 ID입니다.")
    path = OUTPUT / data_id / "dataset_manifest.json"
    if not path.is_file():
        raise ValueError("검사 기록을 찾지 못했습니다.")
    result = read_json(path)
    for key in ("joined_csv", "joined_provenance_csv", "joined_labeled_csv"):
        entry = result.get(key)
        if isinstance(entry, dict) and entry.get("path"):
            entry["path"] = str(resolve_project_path(entry["path"], BASE))
    return result


def friendly_station_label(station_code: str, station_name: str | None = None) -> str:
    """Return human-friendly Korean station label such as '인천 조위관측소'."""
    code = str(station_code or "").strip()
    name = str(station_name or "").strip()
    if not name:
        ws = resolve_data_workspace(BASE)
        mapping_csv = ws / "2026년_AI_품질처리_데이터백업/운영코드/AI_anomaly_detection/mappingBySea.csv"
        if mapping_csv.is_file():
            with mapping_csv.open(encoding="utf-8-sig", newline="") as stream:
                for row in csv.DictReader(stream):
                    if row.get("CODE") == code:
                        name = str(row.get("NAME", "")).strip()
                        break
        else:
            for row in _fallback_mapping_rows_from_manifest():
                if row.get("CODE") == code:
                    name = str(row.get("NAME", "")).strip()
                    break
    if not name or name == code:
        return code
    if name.endswith("관측소"):
        return name
    return f"{name} 조위관측소"


def friendly_sensor_label(sensor_code: str) -> str:
    """Return human-friendly Korean sensor label such as 'LASER 센서' or 'VEGA 센서'."""
    raw = str(sensor_code or "").strip()
    if not raw:
        return "기본 센서"
    core = raw[len("TIDE_LEVEL_"):] if raw.startswith("TIDE_LEVEL_") else raw
    m_num = re.fullmatch(r"([A-Za-z0-9]+)_(\d+)", core)
    if m_num:
        base_name, num_str = m_num.group(1).upper(), m_num.group(2)
        if base_name == "BUOY":
            return f"부표(BUOY) {num_str}호 센서"
        return f"{base_name} {num_str}호 센서"
    upper = core.upper()
    if upper == "BUOY":
        return "부표(BUOY) 센서"
    if upper == "PRESSURE":
        return "수압(PRESSURE) 센서"
    if upper == "WT_VALUE" or upper == "WT":
        return "수온(WT) 센서"
    return f"{core} 센서"


def _last_day_of_ym(ym: str) -> str:
    year = int(ym[:4])
    month = int(ym[4:6])
    nxt = datetime(year + 1, 1, 1) if month == 12 else datetime(year, month + 1, 1)
    last_dt = nxt - timedelta(days=1)
    return last_dt.date().isoformat()


def _iter_month_index_rows(path: Path, station: str, sensor: str):
    """Use the C CSV reader for large exports and keep only the requested pair."""
    if path.stat().st_size < MONTHLY_INDEX_CSV_CHUNK_THRESHOLD:
        iterator = rows(path, "utf-8-sig", column_normalization="sqlplus_gd_obs_st")
        try:
            header = set(next(iterator))
            required = {"OBS_POST_ID", "OBS_ITEM_CODE", "OBS_TIME", "MQC_FLAG"}
            if not required <= header:
                raise ValueError("월별 관측 CSV의 필수 컬럼이 없습니다: " + ", ".join(sorted(required - header)))
            for row in iterator:
                if not isinstance(row, dict):
                    raise ValueError("CSV 데이터 행을 해석하지 못했습니다.")
                if (not station or row["OBS_POST_ID"] == station) and (not sensor or row["OBS_ITEM_CODE"] == sensor):
                    yield row
        finally:
            iterator.close()
        return
    pd: Any = importlib.import_module("pandas")
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.reader(stream, strict=True)
        for raw_header in reader:
            if not raw_header or not any(value.strip() for value in raw_header):
                continue
            if re.match(r"^(old|new)\s+\d+:", raw_header[0].strip(), re.I):
                continue
            raw_header = [value.strip() for value in raw_header]
            header_line = reader.line_num
            break
        else:
            raise ValueError("CSV에서 컬럼 이름을 찾지 못했습니다.")
    normalized, _ = normalize_header(raw_header, "sqlplus_gd_obs_st")
    rename = dict(zip(raw_header, normalized))
    wanted = {"OBS_POST_ID", "OBS_ITEM_CODE", "OBS_TIME", "MQC_FLAG"}
    if not wanted <= set(normalized):
        raise ValueError("월별 관측 CSV의 필수 컬럼이 없습니다.")
    usecols = [column for column in raw_header if rename[column] in wanted]
    with pd.read_csv(path, encoding="utf-8-sig", skiprows=header_line, names=raw_header,
                     usecols=usecols, dtype=str, keep_default_na=False, chunksize=200000) as chunks:
        for frame in chunks:
            frame = frame.rename(columns=rename)
            for column in wanted:
                frame[column] = frame[column].str.strip()
            mask = frame["MQC_FLAG"].isin(["G", "B"])
            if station:
                mask &= frame["OBS_POST_ID"].eq(station)
            if sensor:
                mask &= frame["OBS_ITEM_CODE"].eq(sensor)
            selected = frame.loc[mask]
            for values in selected.itertuples(index=False, name=None):
                yield dict(zip(selected.columns, values))


def load_or_build_monthly_anomaly_index(
    catalog_data: dict | None = None, cache_path: Path | None = None,
    station: str = "", sensor: str = "", selected_yms: list[str] | None = None,
    source_budget_bytes: int | None = 32 * 1024 * 1024, progress=lambda _: None,
) -> dict:
    """Build a scoped, deduplicated index; large unscanned months stay explicitly pending."""
    cache_path = Path(cache_path or MONTHLY_INDEX_PATH)
    cat = catalog_data if catalog_data is not None else catalog()
    selected = set(selected_yms) if selected_yms is not None else None
    grouped: dict[str, dict[str, Path]] = {}
    for item in cat.get("files", []):
        ensure_no_z_access(item["path"])
        path = resolve_training_csv_path(item["path"], BASE)
        match = re.fullmatch(r"(?:data_|GD_OBS_ST_)(\d{6})\.csv", path.name, re.I)
        if match and (selected is None or match.group(1) in selected):
            grouped.setdefault(match.group(1), {})[str(path).casefold()] = path
    for ym, sources in grouped.items():
        priority = min(_monthly_source_priority(path) for path in sources.values())
        grouped[ym] = {key: path for key, path in sources.items() if _monthly_source_priority(path) == priority}
    scope_key = f"{station}|{sensor}" if station or sensor else "*"
    with MONTHLY_INDEX_LOCK:
        old = {}
        cache_error = None
        if cache_path.is_file():
            try:
                old = read_json(cache_path)
            except (OSError, ValueError) as exc:
                cache_error = f"{type(exc).__name__}: {exc}"
        if old.get("schema_version") != "monthly-anomaly-index-3":
            old = {}
        scopes = old.get("scopes") or {}
        scope = scopes.get(scope_key) or {}
        months = {}
        budget = source_budget_bytes
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cumulative_rows_scanned = 0
        total_months = len(grouped)
        for month_number, (ym, sources) in enumerate(sorted(grouped.items()), 1):
            month_file_name = sorted(sources.values())[0].name if sources else f"GD_OBS_ST_{ym}.csv"
            if callable(progress):
                progress({
                    "stage": "month_index",
                    "ym": ym,
                    "month": month_number,
                    "total_months": total_months,
                    "percent": round(month_number / max(1, total_months) * 100.0, 1),
                    "file": month_file_name,
                    "rows_scanned": cumulative_rows_scanned,
                })
            fingerprints, errors = [], []
            for path in sorted(sources.values()):
                try:
                    stat = path.stat()
                    fingerprints.append({"path": str(path), "bytes": stat.st_size, "mtime_ns": stat.st_mtime_ns})
                except OSError as exc:
                    errors.append({"path": str(path), "error": f"{type(exc).__name__}: {exc}"})
            previous = scope.get(ym) or {}
            if not errors and previous.get("fingerprints") == fingerprints and previous.get("complete"):
                months[ym] = previous
                cumulative_rows_scanned += int((previous.get("counts") or {}).get("rows_scanned") or 0)
                if callable(progress):
                    progress({
                        "stage": "month_index",
                        "ym": ym,
                        "month": month_number,
                        "total_months": total_months,
                        "percent": round(month_number / max(1, total_months) * 100.0, 1),
                        "file": month_file_name,
                        "rows_scanned": cumulative_rows_scanned,
                    })
                continue
            source_bytes = sum(item["bytes"] for item in fingerprints)
            if budget is not None and source_bytes > budget:
                months[ym] = {"fingerprints": fingerprints, "entries": [], "errors": errors,
                              "counts": {}, "complete": False, "pending": True}
                continue
            if budget is not None:
                budget -= source_bytes
            if (
                MONTHLY_INDEX_CSV_CHUNK_THRESHOLD > 0
                and len(fingerprints) == 1
                and not errors
                and source_bytes >= MONTHLY_INDEX_CSV_CHUNK_THRESHOLD
                and re.fullmatch(r"DT_\d{4}", station)
                and re.fullmatch(r"TIDE_LEVEL_[A-Z0-9_]+", sensor)
            ):
                try:
                    from scripts.refresh_standardized_month_index import scan_standard_month
                    fast_month = scan_standard_month(Path(fingerprints[0]["path"]), ym, [scope_key])[scope_key]
                except Exception:
                    fast_month = None
                if fast_month is not None:
                    cumulative_rows_scanned += int((fast_month.get("counts") or {}).get("rows_scanned") or 0)
                    if callable(progress):
                        progress({
                            "stage": "month_index",
                            "ym": ym,
                            "month": month_number,
                            "total_months": total_months,
                            "percent": round(month_number / max(1, total_months) * 100.0, 1),
                            "file": month_file_name,
                            "rows_scanned": cumulative_rows_scanned,
                        })
                    months[ym] = fast_month
                    continue
            counters = Counter()
            entries = []
            with tempfile.TemporaryDirectory(prefix="monthly_index_", dir=cache_path.parent) as temporary:
                with contextlib.closing(sqlite3.connect(str(Path(temporary) / "minutes.db"))) as db:
                    db.execute("CREATE TABLE minutes(station TEXT,sensor TEXT,time TEXT,flag TEXT,PRIMARY KEY(station,sensor,time)) WITHOUT ROWID")
                    statement = ("INSERT INTO minutes VALUES(?,?,?,?) ON CONFLICT(station,sensor,time) "
                                 "DO UPDATE SET flag='CONFLICT' WHERE flag<>excluded.flag")
                    for fingerprint in fingerprints:
                        path = Path(fingerprint["path"])
                        iterator = _iter_month_index_rows(path, station, sensor)
                        db.execute("SAVEPOINT source_file")
                        try:
                            batch = []
                            for row in iterator:
                                counters["rows_scanned"] += 1
                                if counters["rows_scanned"] % 200000 == 0 and callable(progress):
                                    progress({
                                        "stage": "month_index",
                                        "ym": ym,
                                        "month": month_number,
                                        "total_months": total_months,
                                        "percent": round(month_number / max(1, total_months) * 100.0, 1),
                                        "file": month_file_name,
                                        "rows_scanned": cumulative_rows_scanned + counters["rows_scanned"],
                                    })
                                flag = row["MQC_FLAG"].strip()
                                if flag not in {"G", "B"}:
                                    counters["other_flag_rows"] += 1
                                    continue
                                try:
                                    stamp = timestamp(row["OBS_TIME"], time_alignment="minute_floor")
                                except ValueError:
                                    counters["invalid_time_rows"] += 1
                                    continue
                                if stamp.strftime("%Y%m") != ym:
                                    counters["outside_month_rows"] += 1
                                    continue
                                if not re.fullmatch(r"DT_\d{4}", row["OBS_POST_ID"]) or not row["OBS_ITEM_CODE"]:
                                    counters["invalid_identity_rows"] += 1
                                    continue
                                batch.append((row["OBS_POST_ID"], row["OBS_ITEM_CODE"], stamp.isoformat(), flag))
                                if len(batch) >= 10000:
                                    db.executemany(statement, batch)
                                    batch.clear()
                            if batch:
                                db.executemany(statement, batch)
                            after = path.stat()
                            if (after.st_size, after.st_mtime_ns) != (fingerprint["bytes"], fingerprint["mtime_ns"]):
                                raise ValueError("인덱스 검사 도중 원본 CSV가 변경되었습니다.")
                            db.execute("RELEASE source_file")
                        except (OSError, UnicodeError, csv.Error, ValueError, StopIteration) as exc:
                            db.execute("ROLLBACK TO source_file")
                            db.execute("RELEASE source_file")
                            errors.append({"path": str(path), "error": f"{type(exc).__name__}: {exc}"})
                        finally:
                            iterator.close()
                    counters["conflict_minutes"] = db.execute("SELECT count(*) FROM minutes WHERE flag='CONFLICT'").fetchone()[0]
                    for st, sn, good, bad in db.execute(
                        "SELECT station,sensor,SUM(flag='G'),SUM(flag='B') FROM minutes WHERE flag IN ('G','B') GROUP BY station,sensor"
                    ):
                        entries.append({"station": st, "sensor": sn, "ym": ym,
                                        "normal_g_count": good, "anomaly_b_count": bad,
                                        "has_real_anomalies": bad > 0, "count_source": "raw_csv",
                                        "complete": not errors, "raw_count_pending": False})
            cumulative_rows_scanned += counters["rows_scanned"]
            if callable(progress):
                progress({
                    "stage": "month_index",
                    "ym": ym,
                    "month": month_number,
                    "total_months": total_months,
                    "percent": round(month_number / max(1, total_months) * 100.0, 1),
                    "file": month_file_name,
                    "rows_scanned": cumulative_rows_scanned,
                })
            months[ym] = {"fingerprints": fingerprints, "entries": entries, "errors": errors,
                          "counts": dict(counters), "complete": not errors, "pending": False}
        scope.update(months)
        scopes[scope_key] = scope
        errors = [error for month in months.values() for error in month["errors"]]
        pending = sorted(ym for ym, month in months.items() if month.get("pending"))
        complete = not pending and not errors
        result = {"schema_version": "monthly-anomaly-index-3", "scopes": scopes, "months": months,
                  "station": station, "sensor": sensor, "index_complete": complete,
                  "index_status": "READY" if complete else ("ERROR" if errors else "PENDING"),
                  "pending_yms": pending,
                  "entries": [entry for month in months.values() for entry in month["entries"]],
                  "errors": errors, "cache_rebuild_reason": cache_error}
        tid = threading.get_ident()
        temporary_json = cache_path.with_name(f"{cache_path.name}.part.{tid}.{uuid.uuid4().hex[:8]}")
        try:
            with _JSON_LOCK:
                temporary_json.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            for attempt in range(16):
                try:
                    with _JSON_LOCK:
                        temporary_json.replace(cache_path)
                    break
                except OSError as error:
                    if not _is_retryable_permission_error(error) or attempt == 15:
                        raise
                    time.sleep(0.05)
        finally:
            with contextlib.suppress(OSError):
                temporary_json.unlink(missing_ok=True)
        return result


def recommend_test_months(
    station: str = "", sensor: str = "", exclude_yms: list[str] | None = None,
) -> dict:
    """Only confirm a ranking after all available unseen raw months are indexed."""
    cat = catalog()
    mapping = cat.get("mapping", [])
    names = {row.get("CODE", ""): row.get("NAME", "") for row in mapping}
    station = str(station or "").strip() or "DT_0001"
    sensor = str(sensor or "").strip()
    if not sensor:
        mapping_row = next((row for row in mapping if row.get("CODE") == station), {})
        main = mapping_row.get("TIDE1(MAIN)")
        sensor = f"TIDE_LEVEL_{main}" if main and main != "-" else "TIDE_LEVEL_LASER"
    excluded = {re.sub(r"[^0-9]", "", str(value))[:6] for value in exclude_yms or []}
    obs_by_ym, prd_by_ym = {}, {}
    for item in sorted(cat.get("files", []), key=lambda item: (_monthly_source_priority(Path(item["path"])), str(item["path"]).casefold())):
        path = str(item["path"])
        ensure_no_z_access(path)
        obs = re.fullmatch(r"(?:data_|GD_OBS_ST_)(\d{6})\.csv", Path(path).name, re.I)
        prd = re.fullmatch(r"(pred_|go_tide_pre_data_)(\d{6})\.csv", Path(path).name, re.I)
        if obs:
            obs_by_ym.setdefault(obs.group(1), path)
        if prd:
            prd_by_ym.setdefault(prd.group(2), path)
    available_yms = sorted((set(obs_by_ym) & set(prd_by_ym)) - excluded)
    index = load_or_build_monthly_anomaly_index(
        catalog_data=cat, station=station, sensor=sensor, selected_yms=available_yms,
        source_budget_bytes=MONTHLY_INDEX_SYNC_MAX_BYTES,
    )
    matching = {entry["ym"]: entry for entry in index["entries"]
                if entry["station"] == station and entry["sensor"] == sensor}
    known_history = {}
    history_errors = []
    for path in sorted(OUTPUT.glob("*/dataset_manifest.json")):
        try:
            doc = read_json(path)
            ym = str(doc.get("date_start", ""))[:7].replace("-", "")
            if ym != str(doc.get("date_end", ""))[:7].replace("-", "") or "anomaly_minutes" not in doc:
                continue
            bad = doc["anomaly_minutes"]
            if not isinstance(bad, int) or bad < 0:
                raise ValueError("분석 이력의 실제 B 건수가 올바르지 않습니다.")
            key = (doc["station"], doc["sensor"], ym)
            entry = {"station": doc["station"], "sensor": doc["sensor"], "ym": ym,
                     "normal_g_count": doc.get("valid_minutes"), "anomaly_b_count": bad,
                     "anomaly_minutes": bad, "anomaly_eval_windows": doc.get("contiguous_labeled_4g_input_1b_target_windows"),
                     "has_real_anomalies": bad > 0, "count_source": "analysis_summary",
                     "raw_count_pending": True, "dataset_id": doc.get("dataset_id"),
                     "source_manifest": str(path)}
            if key not in known_history or known_history[key]["anomaly_b_count"] < bad:
                known_history[key] = entry
        except (OSError, ValueError, KeyError, TypeError) as exc:
            history_errors.append({"path": str(path), "error": f"{type(exc).__name__}: {exc}"})
    ready, snapshot_errors = {}, []
    for path in sorted((BASE / "reports/ocean_ai_snapshots").glob("*/snapshot_manifest.json"), reverse=True):
        try:
            doc = read_json(path)
            if doc.get("station") != station or doc.get("sensor") != sensor:
                continue
            ym = str(doc.get("date_start", ""))[:7].replace("-", "")
            if str(doc.get("date_end", ""))[:7].replace("-", "") != ym:
                continue
            if doc.get("date_start") == f"{ym[:4]}-{ym[4:]}-01" and doc.get("date_end") == _last_day_of_ym(ym):
                ready.setdefault(ym, doc["snapshot_id"])
        except (OSError, ValueError, KeyError, TypeError) as exc:
            snapshot_errors.append({"path": str(path), "error": f"{type(exc).__name__}: {exc}"})
    recommendations = []
    for ym in available_yms:
        raw_month = index["months"].get(ym) or {}
        if raw_month.get("complete") and ym not in matching:
            # A completed raw scan supersedes older analysis records for this pair.
            known_history.pop((station, sensor, ym), None)
            continue
        entry = matching.get(ym)
        if entry is None and not raw_month.get("complete"):
            entry = known_history.get((station, sensor, ym))
        if entry is None:
            entry = {"station": station, "sensor": sensor, "ym": ym, "normal_g_count": None,
                     "anomaly_b_count": None, "has_real_anomalies": None,
                     "count_source": None, "raw_count_pending": ym in index["pending_yms"]}
        bad = entry["anomaly_b_count"]
        label = f"{ym[:4]}년 {int(ym[4:])}월"
        if bad is None:
            reason, badge = "실제 B 건수를 아직 확인하지 않은 달", "실제 B 미확인"
        elif entry.get("raw_count_pending"):
            reason, badge = f"확인된 분석 기록에 실제 B {bad:,}건 · 원본 월별 집계 대기", f"확인된 기록 {bad:,}건"
        else:
            reason = f"원본 CSV 실제 B {bad:,}건 · 미학습 기간 비교" if bad else "실제 B가 없는 달 · 오경보와 정상 분류 성능 비교"
            badge = f"실제 이상치 {bad:,}건" if bad else "정상 자료 비교"
        recommendations.append({
            **entry, "label": label, "date_start": f"{ym[:4]}-{ym[4:]}-01", "date_end": _last_day_of_ym(ym),
            "anomaly_eval_windows": entry.get("anomaly_eval_windows"), "ready_snapshot_id": ready.get(ym),
            "observation_path": obs_by_ym[ym], "prediction_path": prd_by_ym[ym], "reason": reason, "badge": badge,
        })
    recommendations.sort(key=lambda entry: (entry["anomaly_b_count"] is None, -(entry["anomaly_b_count"] or 0), -int(entry["ym"])))
    for rank, entry in enumerate(recommendations, 1):
        entry["rank"] = rank if index["index_complete"] else None
    global_entries = sorted((entry for entry in known_history.values() if entry["anomaly_b_count"] > 0),
                            key=lambda entry: (-entry["anomaly_b_count"], -int(entry["ym"]), entry["station"], entry["sensor"]))
    champion = dict(global_entries[0]) if global_entries else None
    if champion:
        champion.update(station_name=names.get(champion["station"], champion["station"]),
                        station_display=friendly_station_label(champion["station"], names.get(champion["station"])),
                        sensor_display=friendly_sensor_label(champion["sensor"]), complete=False)
    return {"station": station, "station_name": names.get(station, station),
            "station_display": friendly_station_label(station, names.get(station)),
            "sensor": sensor, "sensor_display": friendly_sensor_label(sensor),
            "excluded_yms": sorted(excluded), "top_recommendation": recommendations[0] if recommendations else None,
            "recommendations": recommendations, "global_anomaly_champion": champion,
            "index_complete": index["index_complete"], "index_status": index["index_status"],
            "pending_yms": index["pending_yms"], "index_errors": index["errors"] + history_errors + snapshot_errors}




