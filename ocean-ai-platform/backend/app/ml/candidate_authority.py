"""Verify worker receipts, independently replay, then register real candidates."""
import hashlib
from pathlib import Path
import numpy as np
from app.ml.comparison_runner import ComparisonBlocked, DatabaseAuthority, compare, preflight, read_json
from app.ml.serving import runtime_root, _approved


def verified_worker_receipt(db, path, replay=False):
    from app.core.config import settings
    from app.ml.job_queue import DurableQueue
    from app.ml.comparison_runner import reject_reparse
    reject_reparse(path)
    path = Path(path).resolve()
    if not path.is_relative_to(runtime_root() / "worker" / "attempts"):
        raise ComparisonBlocked("WORKER_RECEIPT_OUTSIDE_CONFIGURED_ROOT")
    report, report_sha = read_json(path)
    queue = DurableQueue(runtime_root() / "worker")
    with queue.connect() as ledger:
        job = ledger.execute("SELECT * FROM queue_jobs WHERE job_id=?", (report["job_id"],)).fetchone()
    if not job or job["state"] != "COMPLETED_CANDIDATE" or Path(job["receipt_path"]).resolve() != path or job["token"] != report["fencing_token"]:
        raise ComparisonBlocked("WORKER_RECEIPT_NOT_COMMITTED_OR_FENCED")
    if job["receipt_sha256"] != report_sha:
        raise ComparisonBlocked("WORKER_RECEIPT_HASH_CHANGED")
    from app.ml.job_queue import code_fingerprint
    if report["code_sha256"] != job["code_sha256"] or code_fingerprint() != job["code_sha256"]:
        raise ComparisonBlocked("WORKER_CODE_ENVIRONMENT_CHANGED")
    prepared = preflight(report["manifest_path"], DatabaseAuthority(db, settings.DATASET_SNAPSHOT_DIR))
    if prepared["manifest_sha256"] != report["manifest_sha256"] or prepared["origin_membership_sha256"] != report["origin_membership_sha256"]:
        raise ComparisonBlocked("WORKER_SOURCE_SNAPSHOT_CHANGED")
    reject_reparse(report["artifact_path"])
    artifact_path = Path(report["artifact_path"]).resolve()
    if not artifact_path.is_relative_to(path.parent):
        raise ComparisonBlocked("WORKER_ARTIFACT_PATH_INVALID")
    artifact, artifact_sha = read_json(artifact_path)
    if artifact_sha != report["artifact_sha256"]:
        raise ComparisonBlocked("WORKER_ARTIFACT_HASH_CHANGED")
    if artifact != report["artifact"]:
        raise ComparisonBlocked("WORKER_ARTIFACT_REPORT_CONTENT_MISMATCH")
    if replay:
        fresh = compare(prepared)
        if fresh["artifact"] != report["artifact"] or fresh["test_metrics"] != report["test_metrics"] or fresh["paired_test_predictions"] != report["paired_test_predictions"]:
            raise ComparisonBlocked("INDEPENDENT_REPLAY_DID_NOT_MATCH")
    return report, report_sha, prepared


def register_candidate(db, receipt_path, model_version):
    from app.models.domain import ModelRegistry, DatasetRegistry, RetrainingHistory
    report, sha, prepared = verified_worker_receipt(db, receipt_path)
    if report["acceptance"]["status"] != "PASS":
        raise ComparisonBlocked("ACCEPTANCE_LIMITS_NOT_PASSED")
    approval = _approved(db, "MODEL_INDEPENDENT_REVIEW", model_version, sha)
    existing = db.query(ModelRegistry).filter_by(model_version=model_version).first()
    if existing:
        if (existing.metrics_json or {}).get("provenance", {}).get("report_sha256") != sha:
            raise ComparisonBlocked("MODEL_VERSION_ALREADY_BOUND_TO_DIFFERENT_RECEIPT")
        return existing
    history = db.query(RetrainingHistory).filter_by(training_id=report["job_id"]).first()
    if history:
        raise ComparisonBlocked("JOB_ALREADY_BOUND_TO_MODEL_VERSION", history.candidate_model_id)
    m = prepared["manifest"]
    training = db.get(DatasetRegistry, m["splits"]["TRAIN"]["dataset_id"])
    metrics = dict(report["test_metrics"]["ridge" if m["task"] == "FORECASTING" else "candidate"])
    metrics["latency"] = report["local_call_p95_ms"]
    metrics["provenance"] = {"report_path": str(Path(receipt_path).resolve()), "report_sha256": sha,
        "artifact_sha256": report["artifact_sha256"], "protocol_hashes": report["protocol_hashes"],
        "snapshot_hashes": report["snapshot_hashes"], "task": m["task"], "domain": m.get("domain"), "item_id": m.get("item_id"),
        "independent_review_approval_id": approval.id, "job_id": report["job_id"]}
    model = ModelRegistry(model_name=m.get("item_id", m["target_variable"]) + ":" + m["task"],
        model_type=report["artifact"]["schema_version"], model_version=model_version, target_variable=m["target_variable"],
        target_task="FORECASTING" if m["task"] == "FORECASTING" else "CLASSIFICATION", dataset_version=training.dataset_version,
        feature_version=training.feature_version, label_version=training.label_version, preprocessing_version=training.preprocessing_version,
        artifact_path=report["artifact_path"], metrics_json=metrics, status="PENDING_APPROVAL", deployment_status="CANDIDATE",
        training_data_start=training.period_start, training_data_end=training.period_end, station_scope=str(training.station_scope), sensor_scope=str(training.sensor_scope))
    db.add(model)
    from app.ml.comparison_runner import clock
    db.add(RetrainingHistory(training_id=report["job_id"], candidate_model_id=model_version, training_start_time=clock(report["training_started_at"], True).replace(tzinfo=None),
        training_end_time=clock(report["training_finished_at"], True).replace(tzinfo=None), data_range_start=training.period_start, data_range_end=training.period_end,
        dataset_version=training.dataset_version, feature_version=training.feature_version,
        label_version=training.label_version, preprocessing_version=training.preprocessing_version, metrics_after_json=report["test_metrics"],
        comparison_result=report["acceptance"]["status"], approval_status="INDEPENDENT_REVIEW_COMPLETE_AWAITING_DEPLOYMENT"))
    db.commit(); db.refresh(model)
    return model
