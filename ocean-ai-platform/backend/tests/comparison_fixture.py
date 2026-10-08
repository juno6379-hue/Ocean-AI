"""Synthetic evidence only. This authority is never used by the production CLI.

It models a future approved dependency-freeze format for isolated runner tests.
No fixture represents user approval, ocean observations or a registered model.
"""
import copy
import hashlib
import json
from datetime import datetime, timedelta, timezone

from app.ml.comparison_runner import ComparisonBlocked, SCHEMA, SPLITS, digest
from app.services.source_contract_review import exact_scope_key


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False), encoding="utf-8")
    return hashlib.sha256(path.read_bytes()).hexdigest()


class SyntheticAuthority:
    evidence_mode = "SYNTHETIC_TEST_ONLY_NOT_USER_APPROVAL"
    def __init__(self, snapshots):
        self.snapshots = snapshots

    def snapshot(self, reference, split):
        snapshot = self.snapshots[split]
        if reference["dataset_id"] != snapshot["dataset_id"] or reference["sha256"] != digest(snapshot):
            raise ComparisonBlocked("FIXTURE_APPROVED_SNAPSHOT_HASH_MISMATCH")
        return copy.deepcopy(snapshot)


def make_fixture(root):
    root.mkdir(parents=True, exist_ok=True)
    raw = root / "synthetic-raw.bin"
    transform = root / "synthetic-transform.bin"
    codebook = root / "synthetic-codebook.bin"
    raw.write_bytes(b"SYNTHETIC TEST BYTES, NOT A REAL RAW SOURCE")
    transform.write_bytes(b"SYNTHETIC TEST BYTES, NOT A REAL PARQUET")
    codebook.write_bytes(b"SYNTHETIC TEST CODEBOOK, NOT A REAL QC POLICY")
    raw_sha = hashlib.sha256(raw.read_bytes()).hexdigest()
    parquet_sha = hashlib.sha256(transform.read_bytes()).hexdigest()
    codebook_sha = hashlib.sha256(codebook.read_bytes()).hexdigest()
    snapshots = {}
    for offset, split in enumerate(SPLITS):
        start = datetime(2020, 1, 1, tzinfo=timezone.utc) + timedelta(days=offset * 10)
        end = start + timedelta(hours=14)
        records, observations = [], {}
        sensor, station, event, episode = f"fixture-sensor-{split}", f"fixture-station-{split}", f"fixture-event-{split}", f"fixture-episode-{split}"
        for i in range(12):
            stamp = (start + timedelta(hours=i)).isoformat()
            oid = f"fixture-{split}-{i}"
            value = 10 + offset + i * 0.6 + (i % 3) * 0.15
            records.append({"id": oid, "station_id": station, "sensor_id": sensor, "variable_code": "FIXTURE_TEMPERATURE",
                "timestamp": stamp, "value_standard": value, "unit": "C", "event_id": event,
                "label": {"label_id": f"fixture-label-{split}"}, "validation_errors": [],
                "raw": {"station_id": station, "sensor_id": sensor, "variable_code": "FIXTURE_TEMPERATURE", "timestamp_utc": stamp,
                    "source_station_code": station, "physical_sensor_id": "physical-" + sensor,
                    "source_row_locator": f"fixture-row:{split}:{i}", "source_sha256": raw_sha, "parquet_sha256": parquet_sha,
                    "source_timezone_name": "UTC", "source_clock_semantics": "OBSERVED_AT",
                    "receive_time": stamp, "source_system": "SYNTHETIC_TEST_ONLY", "source_item_code": "TEST_TEMP",
                    "value_unit": "C", "qc_flag": "G ", "mqc_flag": None, "water_step": None, "from_depth": None, "to_depth": None},
                "features": [{"feature_id": "fixture_current_value", "feature_version": "fixture-feature-1", "value": value,
                    "provenance": {"available_at": stamp, "window_start": stamp, "window_end": stamp, "source_observation_ids": [oid]}}]})
            observations[oid] = {"physical_sensor_id": "physical-" + sensor, "sensor_episode_id": episode, "source_group": "SYNTHETIC_TEST_ONLY",
                "source_station_code": station, "canonical_station_id": station, "canonical_sensor_id": sensor, "source_month": start.strftime("%Y-%m"),
                "source_item_code": "TEST_TEMP", "source_row_locator": f"fixture-row:{split}:{i}", "timezone": "UTC",
                "source_clock_semantics": "OBSERVED_AT", "qc_rule_version": "fixture-qc-1", "event_id": event,
                "source_sha256": raw_sha, "parquet_sha256": parquet_sha, "source_qc_codebook_sha256": codebook_sha,
                "depth": {"step": None, "from": None, "to": None}, "unit": "C", "source_unit": "C",
                "standard_variable": "FIXTURE_TEMPERATURE", "validation_errors": [], "source_qc_raw": "G ", "source_mqc_raw": None,
                "effective_start": start.isoformat(), "effective_end": end.isoformat(), "available_at": stamp, "qc_available_at": stamp,
                "qc_effective_start": start.isoformat(), "qc_effective_end": end.isoformat(), "training_value_status": "ACCEPTED"}
            observations[oid]["exact_scope_key"] = exact_scope_key({"source_group": "SYNTHETIC_TEST_ONLY", "station_code": station,
                "item_code": "TEST_TEMP", "depth_step": None, "depth_from": None, "depth_to": None, "month": start.strftime("%Y-%m")})
        receipt = {"schema_version": "source-semantics-identity-period-event-1", "status": "APPROVED",
            "approval_complete": True, "approved_by": "SYNTHETIC_TEST_ACTOR_NOT_A_USER_APPROVAL", "validation_errors": [],
            "source_availability_policy": "RAW_AND_TRANSFORM_REQUIRED", "files": [
                {"path": raw.name, "sha256": raw_sha, "role": "RAW"},
                {"path": transform.name, "sha256": parquet_sha, "role": "PARQUET"},
                {"path": codebook.name, "sha256": codebook_sha, "role": "QC_CODEBOOK"}], "observations": observations}
        receipt_path = root / (split + "-synthetic-source-contract.json")
        receipt_sha = write_json(receipt_path, receipt)
        snapshots[split] = {"schema_version": "SYNTHETIC_TEST_FUTURE_DEPENDENCY_FREEZE_FORMAT", "dataset_id": f"fixture-dataset-{split}",
            "dataset_name": "SYNTHETIC_TEST_FAMILY", "split": split, "period_start": start.isoformat(), "period_end": end.isoformat(),
            "clock_contract": "UTC_WITH_EXPLICIT_OFFSET",
            "feature_version": "fixture-feature-1", "label_version": "fixture-label-1", "preprocessing_version": "fixture-preprocess-1",
            "qc_rule_version": "fixture-qc-1", "validation_errors": [], "records": records,
            "source_contracts": [{"path": receipt_path.name, "sha256": receipt_sha}], "_approval_actor": "SYNTHETIC_TEST_ACTOR_NOT_A_USER_APPROVAL"}
    manifest = {"schema_version": SCHEMA, "task": "FORECASTING", "data_domain": "SCALAR",
        "target_variable": "FIXTURE_TEMPERATURE", "unit": "C", "horizon_seconds": 3600,
        "feature_ids": ["fixture_current_value"], "ridge_alphas": [0.1, 1.0, 10.0], "refit_train_validation": False,
        "acceptance_criteria_status": "NOT_DEFINED", "splits": {split: {"dataset_id": snapshots[split]["dataset_id"],
        "sha256": digest(snapshots[split])} for split in SPLITS}, "fixture_notice": "SYNTHETIC TEST ONLY; NOT USER APPROVAL OR SOURCE DATA"}
    manifest["locked_holdout_sha256"] = manifest["splits"]["TEST"]["sha256"]
    manifest_path = root / "synthetic-comparison-manifest.json"
    write_json(manifest_path, manifest)
    return manifest_path, SyntheticAuthority(snapshots)


def refresh(manifest_path, authority, split=None):
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for part in SPLITS if split is None else [split]:
        manifest["splits"][part]["sha256"] = digest(authority.snapshots[part])
    manifest["locked_holdout_sha256"] = manifest["splits"]["TEST"]["sha256"]
    write_json(manifest_path, manifest)


def mutate_receipt(manifest_path, authority, split, mutate):
    dependency = authority.snapshots[split]["source_contracts"][0]
    path = manifest_path.parent / dependency["path"]
    data = json.loads(path.read_text(encoding="utf-8"))
    mutate(data)
    dependency["sha256"] = write_json(path, data)
    refresh(manifest_path, authority, split)
