"""Read a chronological local QC stream without exposing reference labels to QC.

Only local ``joined_labeled.csv`` artifacts are read. Snapshot parquet files are
deliberately not used: their normal-only rows omit the real B observations.
"""

from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from typing import Any, Iterator

pd = import_module("pandas")

BASE = Path(__file__).resolve().parents[2]
_CHUNK_ROWS = 100_000
_ALIASES = {
    "timestamp": ("TIMESTAMP", "OBS_TIME"),
    "OBS": ("OBS", "OBS_VALUE"),
    "TIDE_PRE_VAL": ("TIDE_PRE_VAL", "PRD"),
    "label": ("MQC_FLAG", "MQ"),
    "station": ("OBS_POST_ID", "OBS_POST_I", "STATION"),
    "sensor": ("OBS_ITEM_CODE", "SENSOR"),
}


@dataclass
class QCStream:
    """Minute-aligned input and separate evaluator-only reference labels.

    ``frame`` has exactly timestamp, OBS and TIDE_PRE_VAL columns. ``labels``
    retains unknown labels, including empty strings, for explicit exclusion by
    the evaluator. It has no entry for a minute absent from the source.
    """

    frame: Any
    labels: dict[Any, str]
    metadata: dict[str, Any]
    station: str
    sensor: str
    start_time: Any
    end_time: Any
    warmup_start: Any

    def iter_points(self) -> Iterator[dict[str, Any]]:
        """Yield fresh QC inputs; never copy source MQC_FLAG or AI_FLAG values."""
        for timestamp, obs, prediction in self.frame.itertuples(index=False, name=None):
            yield {
                "timestamp": timestamp,
                "OBS": float(obs),
                "TIDE_PRE_VAL": float(prediction),
                "MQC_FLAG": "G",
                "AI_FLAG": "1",
                "IS_DB_NULL": bool(pd.isna(obs)),
            }


def _identifier(value: Any, kind: str) -> str:
    text = str(value).strip()
    if not text or text in {".", ".."} or any(c in text for c in "/\\:"):
        raise ValueError(f"Invalid {kind}: {value!r}")
    return text


def _dataset_ids(value: Any) -> list[str]:
    values = value if isinstance(value, (list, tuple)) else [value]
    result: list[str] = []
    for entry in values:
        if not isinstance(entry, str):
            raise ValueError("dataset IDs must be nonempty strings")
        for part in entry.split("+"):
            item = _identifier(part, "dataset_id")
            if item not in result:
                result.append(item)
    if not result:
        raise ValueError("No dataset IDs were declared")
    return result


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _verify_hash(actual: str, expected: Any, description: str) -> None:
    if expected is not None and str(expected).strip().lower() != actual:
        raise ValueError(f"SHA-256 mismatch for {description}")


def _manifest(path: Path, identity_key: str, identity: str) -> tuple[dict[str, Any], str]:
    raw = path.read_bytes()
    manifest = json.loads(raw.decode("utf-8-sig"))
    if not isinstance(manifest, dict) or manifest.get(identity_key) != identity:
        raise ValueError(f"{identity_key} mismatch in {path}")
    return manifest, hashlib.sha256(raw).hexdigest()


def _identity(manifest: dict[str, Any], key: str, expected: str | None) -> str:
    direct = manifest.get(key)
    scope = manifest.get(f"{key}_scope")
    if direct is None and isinstance(scope, list) and len(scope) == 1:
        direct = scope[0]
    if not isinstance(direct, str) or not direct.strip():
        raise ValueError(f"Manifest requires one explicit {key}")
    actual = direct.strip()
    if expected is not None and actual != expected:
        raise ValueError(f"Manifest {key} mismatch: expected {expected!r}, found {actual!r}")
    if scope is not None and (not isinstance(scope, list) or scope != [actual]):
        raise ValueError(f"Manifest {key}_scope conflicts with {key}")
    return actual


def _minute(value: Any, name: str) -> Any:
    try:
        timestamp = pd.Timestamp(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"Invalid {name}: {value!r}") from error
    if pd.isna(timestamp) or timestamp.tzinfo is not None:
        raise ValueError(f"{name} must be a timezone-naive timestamp")
    if timestamp != timestamp.floor("min"):
        raise ValueError(f"{name} must fall on an exact minute")
    return timestamp


def _artifact_path(value: Any, directory: Path, expected: Path | None = None) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Artifact path must be a nonempty string")
    candidate = Path(value)
    if not candidate.is_absolute():
        candidate = directory / candidate
    candidate = candidate.resolve()
    if expected is not None and candidate != expected.resolve():
        raise ValueError(f"Manifest artifact path does not identify {expected}")
    return candidate


def _source_columns(path: Path) -> dict[str, str]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        header = next(csv.reader(stream), None)
    if not header:
        raise ValueError(f"Labeled source has no header: {path}")
    normalized: dict[str, str] = {}
    for column in header:
        name = column.strip().upper()
        if name in normalized:
            raise ValueError(f"Duplicate source column: {column}")
        normalized[name] = column
    mapping: dict[str, str] = {}
    for target, aliases in _ALIASES.items():
        candidates = [normalized[name] for name in aliases if name in normalized]
        if len(candidates) > 1:
            raise ValueError(f"Ambiguous source columns for {target}: {candidates}")
        if candidates:
            mapping[target] = candidates[0]
        elif target not in {"station", "sensor"}:
            raise ValueError(f"Labeled source is missing {target}: {path}")
    return mapping


def _numeric(series: Any, path: Path, column: str) -> Any:
    text = series.str.strip()
    missing = text.isin(["", "NaN", "nan", "NULL", "null", "None"])
    try:
        values = pd.to_numeric(text.mask(missing), errors="raise").astype(float)
    except (TypeError, ValueError) as error:
        raise ValueError(f"Invalid numeric {column} in {path}") from error
    if values.isin([float("inf"), float("-inf")]).any():
        raise ValueError(f"Infinite {column} in {path}")
    return values


def _read_labeled(
    path: Path, station: str, sensor: str, lower: Any, upper: Any
) -> tuple[Any, dict[str, Any]]:
    mapping = _source_columns(path)
    reverse = {source: target for target, source in mapping.items()}
    parts: list[Any] = []
    scanned = 0
    reversals = 0
    previous_timestamp = None
    with pd.read_csv(
        path, encoding="utf-8-sig", usecols=list(reverse), dtype=str,
        keep_default_na=False, chunksize=_CHUNK_ROWS,
    ) as reader:
        for chunk in reader:
            chunk = chunk.rename(columns=reverse)
            scanned += len(chunk)
            for key, expected in (("station", station), ("sensor", sensor)):
                if key in chunk and not chunk[key].str.strip().eq(expected).all():
                    raise ValueError(f"Source row {key} mismatch in {path}")
            try:
                timestamps = pd.to_datetime(chunk["timestamp"].str.strip(), errors="raise")
            except (TypeError, ValueError) as error:
                raise ValueError(f"Invalid source timestamp in {path}") from error
            if timestamps.isna().any() or getattr(timestamps.dt, "tz", None) is not None:
                raise ValueError(f"Source timestamps must be timezone-naive and present: {path}")
            if not timestamps.eq(timestamps.dt.floor("min")).all():
                raise ValueError(f"Source timestamp is not on an exact minute: {path}")
            reversals += int(timestamps.diff().lt(pd.Timedelta(0)).sum())
            if len(timestamps):
                if previous_timestamp is not None and timestamps.iloc[0] < previous_timestamp:
                    reversals += 1
                previous_timestamp = timestamps.iloc[-1]
            chunk["timestamp"] = timestamps
            selected = chunk.loc[timestamps.between(lower, upper)].copy()
            if selected.empty:
                continue
            selected["OBS"] = _numeric(selected["OBS"], path, "OBS")
            selected["TIDE_PRE_VAL"] = _numeric(selected["TIDE_PRE_VAL"], path, "TIDE_PRE_VAL")
            selected["label"] = selected["label"].str.strip()
            parts.append(selected[["timestamp", "OBS", "TIDE_PRE_VAL", "label"]])
    frame = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(
        columns=["timestamp", "OBS", "TIDE_PRE_VAL", "label"]
    )
    return frame, {
        "rows_scanned": scanned,
        "rows_in_range": len(frame),
        "out_of_order_transitions": reversals,
        "column_mapping": mapping,
        "row_identity_columns_verified": [key for key in ("station", "sensor") if key in mapping],
    }


def _snapshot_provenance(
    manifest: dict[str, Any], ids: list[str], records: dict[str, dict[str, Any]],
    snapshot_directory: Path,
) -> list[dict[str, Any]]:
    provenance = manifest.get("source_provenance", {})
    if not isinstance(provenance, dict):
        raise ValueError("Invalid snapshot source_provenance")
    references = provenance.get("dataset_manifests", provenance.get("datasets", []))
    if not isinstance(references, list):
        raise ValueError("Invalid snapshot dataset manifest references")
    checks: list[dict[str, Any]] = []
    if provenance.get("dataset_manifest_sha256") is not None:
        _verify_hash(records[ids[0]]["dataset_manifest_sha256"],
                     provenance["dataset_manifest_sha256"], "snapshot primary dataset manifest")
    for reference in references:
        if not isinstance(reference, dict):
            raise ValueError("Invalid snapshot dataset manifest reference")
        reference_ids = _dataset_ids(reference.get("dataset_id"))
        if len(reference_ids) != 1 or reference_ids[0] not in records:
            raise ValueError("Snapshot references an unrelated dataset manifest")
        dataset = records[reference_ids[0]]
        _verify_hash(dataset["dataset_manifest_sha256"],
                     reference.get("dataset_manifest_sha256"), "snapshot dataset manifest")
    source_references = [provenance, *references]
    verified_paths: dict[Path, str] = {}
    for reference in source_references:
        declared_hash = reference.get("joined_source_sha256")
        declared_path = reference.get("joined_source_path")
        if declared_hash is None:
            continue
        path = _artifact_path(declared_path, snapshot_directory)
        actual_hash = verified_paths.get(path)
        if actual_hash is None:
            actual_hash = _sha256(path)
            verified_paths[path] = actual_hash
        _verify_hash(actual_hash, declared_hash, f"snapshot source {path}")
    checks.extend({"path": str(path), "sha256": digest} for path, digest in verified_paths.items())
    return checks


def load_source(
    *, dataset_id: str | None = None, snapshot_id: str | None = None,
    station: str | None = None, sensor: str | None = None,
    start_time: Any, end_time: Any, warmup_minutes: int = 180,
    base: Path | str = BASE,
) -> QCStream:
    """Load raw labeled evidence and pad warmup through inclusive end by minute.

    Supply exactly one dataset ID (legacy ``a+b`` is supported) or snapshot ID.
    All provided hashes for the labeled artifacts and snapshot manifest links
    are checked before simulation. No DB connector or production module loads.
    """
    if (dataset_id is None) == (snapshot_id is None):
        raise ValueError("Supply exactly one of dataset_id or snapshot_id")
    if isinstance(warmup_minutes, bool) or not isinstance(warmup_minutes, int) or warmup_minutes < 0:
        raise ValueError("warmup_minutes must be a nonnegative integer")
    start = _minute(start_time, "start_time")
    end = _minute(end_time, "end_time")
    if end < start:
        raise ValueError("end_time must not precede start_time")
    lower = start - pd.Timedelta(minutes=warmup_minutes)
    root = Path(base).resolve()
    snapshot_manifest = None
    snapshot_hash = None
    snapshot_path = None
    if snapshot_id is not None:
        snapshot_id = _identifier(snapshot_id, "snapshot_id")
        snapshot_path = root / "reports" / "ocean_ai_snapshots" / snapshot_id / "snapshot_manifest.json"
        snapshot_manifest, snapshot_hash = _manifest(snapshot_path, "snapshot_id", snapshot_id)
        station = _identity(snapshot_manifest, "station", station)
        sensor = _identity(snapshot_manifest, "sensor", sensor)
        ids = _dataset_ids(snapshot_manifest.get("dataset_ids") or snapshot_manifest.get("dataset_id"))
        legacy = snapshot_manifest.get("dataset_id")
        if legacy is not None and _dataset_ids(legacy) not in ([ids[0]], ids):
            raise ValueError("Snapshot dataset_id conflicts with dataset_ids")
    else:
        ids = _dataset_ids(dataset_id)
    sources: list[dict[str, Any]] = []
    frames: list[Any] = []
    for item in ids:
        directory = root / "reports" / "dataset_previews" / item
        manifest_path = directory / "dataset_manifest.json"
        manifest, manifest_hash = _manifest(manifest_path, "dataset_id", item)
        station = _identity(manifest, "station", station)
        sensor = _identity(manifest, "sensor", sensor)
        labeled_path = directory / "joined_labeled.csv"
        declared = manifest.get("joined_labeled_csv")
        if declared is not None:
            if not isinstance(declared, dict):
                raise ValueError("Invalid joined_labeled_csv declaration")
            if "path" in declared:
                _artifact_path(declared["path"], directory, labeled_path)
        before = labeled_path.stat()
        source_hash = _sha256(labeled_path)
        _verify_hash(source_hash, declared.get("sha256") if declared else None,
                     f"labeled source {labeled_path}")
        frame, details = _read_labeled(labeled_path, station, sensor, lower, end)
        after = labeled_path.stat()
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            raise ValueError(f"Labeled source changed while reading: {labeled_path}")
        sources.append({
            "dataset_id": item, "path": str(labeled_path), "sha256": source_hash,
            "dataset_manifest_path": str(manifest_path), "dataset_manifest_sha256": manifest_hash,
            "declared_source_hash_verified": bool(declared and declared.get("sha256")), **details,
        })
        frames.append(frame)
    assert station is not None and sensor is not None
    referenced_sources: list[dict[str, Any]] = []
    if snapshot_manifest is not None and snapshot_path is not None:
        referenced_sources = _snapshot_provenance(
            snapshot_manifest, ids, {source["dataset_id"]: source for source in sources},
            snapshot_path.parent,
        )
    raw = pd.concat(frames, ignore_index=True)
    raw_count = len(raw)
    duplicate_mask = raw.duplicated("timestamp", keep=False)
    duplicate_rows = raw.loc[duplicate_mask]
    if not duplicate_rows.empty:
        conflicts = duplicate_rows.groupby("timestamp")[["OBS", "TIDE_PRE_VAL", "label"]].nunique(dropna=False)
        if conflicts.gt(1).any(axis=1).any():
            timestamps = conflicts.index[conflicts.gt(1).any(axis=1)]
            raise ValueError(f"Conflicting duplicate source values or labels at {timestamps[0]}")
    raw = raw.drop_duplicates("timestamp").sort_values("timestamp", kind="stable")
    labels = dict(zip(raw["timestamp"], raw["label"]))
    minute_index = pd.date_range(lower, end, freq="min", name="timestamp")
    aligned = raw.set_index("timestamp")[["OBS", "TIDE_PRE_VAL"]].reindex(minute_index)
    aligned = aligned.astype(float).reset_index()
    evaluation = aligned.loc[aligned["timestamp"].between(start, end)]
    label_counts = {str(key): int(value) for key, value in raw["label"].value_counts(dropna=False).items()}
    evaluation_labels = raw.loc[raw["timestamp"].between(start, end), "label"]
    metadata = {
        "source_kind": "snapshot_raw_labeled_csv" if snapshot_id else "dataset_raw_labeled_csv",
        "dataset_ids": ids, "snapshot_id": snapshot_id,
        "snapshot_manifest_path": str(snapshot_path) if snapshot_path else None,
        "snapshot_manifest_sha256": snapshot_hash, "sources": sources,
        "snapshot_referenced_sources_verified": referenced_sources,
        "station": station, "sensor": sensor,
        "start_time": start.isoformat(), "end_time": end.isoformat(),
        "warmup_start": lower.isoformat(), "warmup_minutes": warmup_minutes,
        "interval_closure": "inclusive", "time_alignment": "exact_minute",
        "raw_rows_in_range": raw_count, "raw_unique_minutes": len(raw),
        "exact_duplicate_rows_removed": raw_count - len(raw),
        "duplicate_minutes": int(duplicate_rows["timestamp"].nunique()),
        "out_of_order_transitions": sum(item["out_of_order_transitions"] for item in sources),
        "sorted_chronologically": True,
        "expected_minutes_including_warmup": len(aligned),
        "missing_source_minutes_including_warmup": len(aligned) - len(raw),
        "missing_observation_minutes_including_warmup": int(aligned["OBS"].isna().sum()),
        "missing_prediction_minutes_including_warmup": int(aligned["TIDE_PRE_VAL"].isna().sum()),
        "evaluation_minutes": len(evaluation),
        "evaluation_missing_observation_minutes": int(evaluation["OBS"].isna().sum()),
        "label_counts_including_warmup": label_counts,
        "evaluation_label_counts": {str(k): int(v) for k, v in evaluation_labels.value_counts().items()},
        "unknown_label_minutes_including_warmup": int((~raw["label"].isin(["G", "B"])).sum()),
        "qc_input_columns": ["timestamp", "OBS", "TIDE_PRE_VAL"],
        "reference_labels_in_qc_input": False, "source_ai_flags_used": False,
    }
    return QCStream(aligned, labels, metadata, station, sensor, start, end, lower)
