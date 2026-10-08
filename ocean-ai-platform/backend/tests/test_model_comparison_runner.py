"""Meaningful contract/failure tests; all learning here uses synthetic fixtures."""
import hashlib
import json
import sqlite3

import numpy as np
import pytest

from app.ml.comparison_runner import ComparisonBlocked, compare, digest, preflight, run_manual
from comparison_fixture import make_fixture, mutate_receipt, refresh, write_json


def blocked(path, authority, code):
    with pytest.raises(ComparisonBlocked) as caught:
        preflight(path, authority)
    assert caught.value.code == code


def test_same_fixed_origins_complete_with_no_operational_selection(tmp_path):
    path, authority = make_fixture(tmp_path / "input")
    prepared = preflight(path, authority)
    result = compare(prepared)
    assert all(v["eligible_origins"] == 11 for v in result["coverage"].values())
    assert all(v["missing_horizon_or_boundary_origins"] == 1 for v in result["coverage"].values())
    assert result["selected_operating_model"] is None and result["registered_models"] == result["deployed_models"] == 0
    assert result["acceptance_criteria_status"] == "NOT_DEFINED"
    assert result["service_latency"] == result["cost"] == "NOT_MEASURED"
    paired = result["paired_test_predictions"]
    actual, predicted = np.asarray([r["actual"] for r in paired]), np.asarray([r["ridge"] for r in paired])
    assert result["test_metrics"]["ridge"]["sample_count"] == len(paired)
    assert result["test_metrics"]["ridge"]["mae"] == pytest.approx(np.abs(predicted - actual).mean())
    assert result["test_prediction_roundtrip_verified"]


def test_test_targets_cannot_change_tuning_or_train_scaler(tmp_path):
    path, authority = make_fixture(tmp_path / "input")
    before = compare(preflight(path, authority))
    for row in authority.snapshots["TEST"]["records"]:
        row["value_standard"] += 10_000
    refresh(path, authority, "TEST")
    after = compare(preflight(path, authority))
    assert before["selected_ridge_alpha"] == after["selected_ridge_alpha"]
    assert before["artifact"] == after["artifact"]
    assert after["test_metrics"]["ridge"]["mae"] > 9000
    train_x = [r["features"][0]["value"] for r in authority.snapshots["TRAIN"]["records"][:-1]]
    assert after["artifact"]["mean"][0] == pytest.approx(np.mean(train_x))


def test_fixed_holdout_reference_and_membership_hash_change_rejected(tmp_path):
    path, authority = make_fixture(tmp_path / "input")
    manifest = json.loads(path.read_text())
    manifest["locked_holdout_sha256"] = "f" * 64
    write_json(path, manifest)
    blocked(path, authority, "LOCKED_HOLDOUT_MISMATCH")
    refresh(path, authority)
    authority.snapshots["TRAIN"]["records"][0]["value_standard"] += 0.25
    blocked(path, authority, "FIXTURE_APPROVED_SNAPSHOT_HASH_MISMATCH")


def test_future_feature_and_retroactive_qc_blocked(tmp_path):
    path, authority = make_fixture(tmp_path / "input")
    authority.snapshots["TRAIN"]["records"][0]["features"][0]["provenance"]["available_at"] = "2020-01-01T00:01:00Z"
    refresh(path, authority, "TRAIN")
    blocked(path, authority, "FEATURE_AS_OF_LEAKAGE")
    path, authority = make_fixture(tmp_path / "second")
    mutate_receipt(path, authority, "TRAIN", lambda receipt: receipt["observations"]["fixture-TRAIN-0"].update(qc_available_at="2020-01-01T00:01:00Z"))
    blocked(path, authority, "ORIGIN_QC_AVAILABLE_IN_FUTURE")


def test_cross_split_events_and_sensor_episodes_are_rejected(tmp_path):
    path, authority = make_fixture(tmp_path / "input")
    for row in authority.snapshots["TEST"]["records"]:
        row["event_id"] = "fixture-event-TRAIN"
    mutate_receipt(path, authority, "TEST", lambda receipt: [proof.update(event_id="fixture-event-TRAIN") for proof in receipt["observations"].values()])
    blocked(path, authority, "EVENT_GROUP_SPLIT_LEAKAGE")
    path, authority = make_fixture(tmp_path / "second")
    mutate_receipt(path, authority, "TEST", lambda receipt: [proof.update(sensor_episode_id="fixture-episode-TRAIN") for proof in receipt["observations"].values()])
    blocked(path, authority, "SENSOR_EPISODE_IDENTITY_VALIDITY_INCONSISTENT")


def test_source_record_overlap_and_source_raw_flags_are_rejected(tmp_path):
    path, authority = make_fixture(tmp_path / "input")
    authority.snapshots["TEST"]["records"][0]["raw"]["source_row_locator"] = "fixture-row:TRAIN:0"
    mutate_receipt(path, authority, "TEST", lambda receipt: receipt["observations"]["fixture-TEST-0"].update(source_row_locator="fixture-row:TRAIN:0"))
    blocked(path, authority, "SOURCE_RECORD_MEMBERSHIP_OVERLAP")
    path, authority = make_fixture(tmp_path / "second")
    mutate_receipt(path, authority, "TRAIN", lambda receipt: receipt["observations"]["fixture-TRAIN-0"].update(source_qc_raw="G"))
    blocked(path, authority, "SOURCE_QC_RAW_VALUE_CHANGED")


def test_station_literal_and_codebook_dependency_cannot_be_forged(tmp_path):
    from app.services.source_contract_review import exact_scope_key
    path, authority = make_fixture(tmp_path / "input")
    def corrupt(receipt):
        proof = receipt["observations"]["fixture-TRAIN-0"]
        proof["source_station_code"] = "different-source-station"
        proof["exact_scope_key"] = exact_scope_key({"source_group": "SYNTHETIC_TEST_ONLY", "station_code": "different-source-station",
            "item_code": "TEST_TEMP", "depth_step": None, "depth_from": None, "depth_to": None, "month": "2020-01"})
    mutate_receipt(path, authority, "TRAIN", corrupt)
    blocked(path, authority, "SOURCE_STATION_LITERAL_MISMATCH")
    path, authority = make_fixture(tmp_path / "second")
    mutate_receipt(path, authority, "TRAIN", lambda receipt: receipt["observations"]["fixture-TRAIN-0"].update(source_qc_codebook_sha256="a" * 64))
    blocked(path, authority, "QC_CODEBOOK_HASH_NOT_IN_CONTRACT")
    path, authority = make_fixture(tmp_path / "third")
    (path.parent / "synthetic-codebook.bin").write_bytes(b"changed codebook")
    blocked(path, authority, "SOURCE_HASH_MISMATCH")


def test_feature_and_receive_naive_clocks_rejected(tmp_path):
    path, authority = make_fixture(tmp_path / "input")
    authority.snapshots["TRAIN"]["records"][0]["features"][0]["provenance"]["available_at"] = "2020-01-01T00:00:00"
    refresh(path, authority, "TRAIN")
    blocked(path, authority, "CLOCK_OFFSET_REQUIRED")
    path, authority = make_fixture(tmp_path / "second")
    authority.snapshots["TRAIN"]["records"][0]["raw"]["receive_time"] = "2020-01-01T00:00:00"
    refresh(path, authority, "TRAIN")
    blocked(path, authority, "CLOCK_OFFSET_REQUIRED")


def test_verified_kst_month_across_utc_year_boundary_keeps_exact_scope(tmp_path):
    from datetime import datetime, timedelta, timezone
    path, authority = make_fixture(tmp_path / "input")
    snapshot = authority.snapshots["TRAIN"]
    kst = timezone(timedelta(hours=9))
    def shift(value):
        return (datetime.fromisoformat(value) - timedelta(hours=9)).astimezone(kst).isoformat()
    for key in ("period_start", "period_end"):
        snapshot[key] = shift(snapshot[key])
    for record in snapshot["records"]:
        record["timestamp"] = shift(record["timestamp"])
        record["raw"]["timestamp_utc"] = shift(record["raw"]["timestamp_utc"])
        record["raw"]["receive_time"] = shift(record["raw"]["receive_time"])
        record["raw"]["source_timezone_name"] = "Asia/Seoul"
        for key in ("available_at", "window_start", "window_end"):
            record["features"][0]["provenance"][key] = shift(record["features"][0]["provenance"][key])
    def shift_receipt(receipt):
        for proof in receipt["observations"].values():
            proof["timezone"] = "Asia/Seoul"
            for key in ("effective_start", "effective_end", "qc_effective_start", "qc_effective_end", "available_at", "qc_available_at"):
                proof[key] = shift(proof[key])
    mutate_receipt(path, authority, "TRAIN", shift_receipt)
    prepared = preflight(path, authority)
    assert prepared["rows"]["TRAIN"][0]["forecast_origin"].startswith("2019-12-31T15:")
    assert len(prepared["rows"]["TRAIN"]) == 11


def test_wrong_unit_raw_clock_and_typed_depth_rejected(tmp_path):
    path, authority = make_fixture(tmp_path / "input")
    authority.snapshots["TRAIN"]["records"][0]["unit"] = "cm"
    refresh(path, authority, "TRAIN")
    blocked(path, authority, "MIXED_TARGET_VARIABLE_OR_UNIT")
    path, authority = make_fixture(tmp_path / "second")
    mutate_receipt(path, authority, "TRAIN", lambda receipt: receipt["observations"]["fixture-TRAIN-0"].update(depth={"step": "", "from": None, "to": None}))
    blocked(path, authority, "SOURCE_DEPTH_MISMATCH")
    path, authority = make_fixture(tmp_path / "third")
    authority.snapshots["TRAIN"]["records"][0]["raw"]["timestamp_utc"] = "2020-01-01T00:01:00Z"
    refresh(path, authority, "TRAIN")
    blocked(path, authority, "RAW_STANDARD_CLOCK_MISMATCH")


def test_shared_source_scope_key_and_numeric_depth_types_are_not_collapsed(tmp_path):
    path, authority = make_fixture(tmp_path / "input")
    authority.snapshots["TRAIN"]["records"][0]["raw"]["water_step"] = 0
    mutate_receipt(path, authority, "TRAIN", lambda receipt: receipt["observations"]["fixture-TRAIN-0"].update(depth={"step": 0.0, "from": None, "to": None}))
    blocked(path, authority, "SOURCE_DEPTH_MISMATCH")
    path, authority = make_fixture(tmp_path / "second")
    mutate_receipt(path, authority, "TRAIN", lambda receipt: receipt["observations"]["fixture-TRAIN-0"].update(exact_scope_key="a" * 64))
    blocked(path, authority, "EXACT_SOURCE_SCOPE_KEY_MISMATCH")


def test_source_hash_receipt_hash_and_missing_raw_fail_closed(tmp_path):
    path, authority = make_fixture(tmp_path / "input")
    (path.parent / "synthetic-transform.bin").write_bytes(b"changed")
    blocked(path, authority, "SOURCE_HASH_MISMATCH")
    path, authority = make_fixture(tmp_path / "second")
    (path.parent / "TRAIN-synthetic-source-contract.json").write_text("{}")
    blocked(path, authority, "SOURCE_CONTRACT_HASH_MISMATCH")
    path, authority = make_fixture(tmp_path / "third")
    (path.parent / "synthetic-raw.bin").unlink()
    blocked(path, authority, "SOURCE_FILE_MISSING")


def test_missing_raw_only_allowed_inside_reviewed_snapshot_dependency_policy(tmp_path):
    path, authority = make_fixture(tmp_path / "input")
    for split in ("TRAIN", "VALIDATION", "TEST"):
        def mark_deleted(receipt):
            receipt.update(source_availability_policy="APPROVED_TRANSFORM_ONLY")
            for f in receipt["files"]:
                if f["role"] == "RAW":
                    f.update(original_path=f["path"], path=None, availability="ORIGINAL_DELETED")
        mutate_receipt(path, authority, split, mark_deleted)
    (path.parent / "synthetic-raw.bin").unlink()
    prepared = preflight(path, authority)
    assert all(row["source_availability_policy"] == "APPROVED_TRANSFORM_ONLY" for rows in prepared["rows"].values() for row in rows)
    mutate_receipt(path, authority, "TRAIN", lambda receipt: receipt.update(status="DRAFT_BLOCKED", approval_complete=False))
    blocked(path, authority, "SOURCE_CONTRACT_REVIEW_INCOMPLETE")


def test_cross_sensor_feature_window_and_future_sources_rejected(tmp_path):
    path, authority = make_fixture(tmp_path / "input")
    first, second = authority.snapshots["TRAIN"]["records"][:2]
    first["features"][0]["provenance"]["source_observation_ids"] = [second["id"]]
    refresh(path, authority, "TRAIN")
    blocked(path, authority, "FEATURE_SOURCE_AVAILABLE_IN_FUTURE")
    path, authority = make_fixture(tmp_path / "second")
    first = authority.snapshots["TRAIN"]["records"][0]
    first["features"][0]["provenance"]["window_start"] = "2019-12-31T23:00:00Z"
    refresh(path, authority, "TRAIN")
    blocked(path, authority, "FEATURE_AS_OF_LEAKAGE")


def test_repeated_job_does_not_fit_again_and_tampered_completed_report_rejected(tmp_path, monkeypatch):
    path, authority = make_fixture(tmp_path / "input")
    root = tmp_path / "jobs"
    first = run_manual(path, authority, root, execute=True)
    assert first["status"] == "COMPARISON_COMPLETE_CANDIDATE_ONLY"
    monkeypatch.setattr("app.ml.comparison_runner.compare", lambda prepared: pytest.fail("duplicate fit"))
    repeated = run_manual(path, authority, root, execute=True)
    assert repeated["idempotent_reuse"] and repeated["job_id"] == first["job_id"]
    report = root / first["job_id"] / "comparison.json"
    data = json.loads(report.read_text())
    data["test_metrics"]["ridge"]["mae"] = 0
    write_json(report, data)
    rejected = run_manual(path, authority, root, execute=True)
    assert rejected["blockers"][0]["code"] == "COMPLETED_JOB_REPORT_HASH_MISMATCH"


def test_scope_busy_and_crashed_job_fail_closed(tmp_path):
    path, authority = make_fixture(tmp_path / "input")
    root = tmp_path / "jobs"
    result = run_manual(path, authority, root, execute=True)
    manifest = json.loads(path.read_text())
    manifest["ridge_alphas"] = [0.5]
    write_json(path, manifest)
    scope = digest({k: manifest[k] for k in ("task", "target_variable", "unit", "horizon_seconds")})
    with sqlite3.connect(root / "comparison_jobs.sqlite3") as db:
        db.execute("INSERT INTO scope_locks VALUES (?,?,?,?)", (scope, "crashed-job", 99999, "synthetic"))
    assert run_manual(path, authority, root, execute=True)["status"] == "SCOPE_BUSY_OR_RECOVERY_REQUIRED"
    with sqlite3.connect(root / "comparison_jobs.sqlite3") as db:
        db.execute("DELETE FROM scope_locks")
        db.execute("UPDATE jobs SET state='RUNNING' WHERE job_id=?", (result["job_id"],))
    manifest["ridge_alphas"] = [0.1, 1.0, 10.0]
    write_json(path, manifest)
    assert run_manual(path, authority, root, execute=True)["status"] == "RECOVERY_REQUIRED"


def test_failure_attempt_preserved_champion_untouched_and_no_automatic_retry(tmp_path, monkeypatch):
    path, authority = make_fixture(tmp_path / "input")
    champion = tmp_path / "existing-champion.bin"
    champion.write_bytes(b"KEEP ORIGINAL CHAMPION BYTES")
    champion_sha = hashlib.sha256(champion.read_bytes()).hexdigest()
    def fail(prepared):
        raise RuntimeError("injected synthetic worker failure")
    monkeypatch.setattr("app.ml.comparison_runner.compare", fail)
    result = run_manual(path, authority, tmp_path / "jobs", execute=True)
    assert result["status"] == "FAILED_QUARANTINED"
    assert (tmp_path / "jobs" / result["job_id"] / "failure.json").is_file()
    with sqlite3.connect(tmp_path / "jobs" / "comparison_jobs.sqlite3") as db:
        assert db.execute("SELECT state FROM jobs").fetchone()[0] == "FAILED_QUARANTINED"
        assert db.execute("SELECT count(*) FROM scope_locks").fetchone()[0] == 0
    assert hashlib.sha256(champion.read_bytes()).hexdigest() == champion_sha
    assert run_manual(path, authority, tmp_path / "jobs", execute=True)["status"] == "RECOVERY_REQUIRED"


def test_changed_inputs_during_fit_cannot_complete(tmp_path, monkeypatch):
    path, authority = make_fixture(tmp_path / "input")
    original_compare = compare
    def changing(prepared):
        result = original_compare(prepared)
        (path.parent / "synthetic-transform.bin").write_bytes(b"changed while fitting")
        return result
    monkeypatch.setattr("app.ml.comparison_runner.compare", changing)
    result = run_manual(path, authority, tmp_path / "jobs", execute=True)
    assert result["status"] == "FAILED_QUARANTINED" and result["blockers"][0]["code"] == "SOURCE_HASH_MISMATCH"
    assert not (tmp_path / "jobs" / result["job_id"] / "comparison.json").exists()


def test_blocked_preflight_creates_no_training_job_and_invalid_json_blocked(tmp_path):
    path, authority = make_fixture(tmp_path / "input")
    authority.snapshots["TRAIN"]["source_contracts"] = []
    refresh(path, authority, "TRAIN")
    root = tmp_path / "jobs"
    result = run_manual(path, authority, root, execute=True)
    assert result["status"] == "BLOCKED" and not result["training_started"] and not root.exists()
    path.write_text('{"schema_version":"x", "schema_version":"y"}')
    blocked(path, authority, "DUPLICATE_JSON_KEY")
    path.write_text('{"horizon_seconds":NaN}')
    blocked(path, authority, "NONFINITE_JSON_LITERAL")
