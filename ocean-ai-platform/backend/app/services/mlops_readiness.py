"""Read-only evidence checks; registry entries never prove live model serving.

No model is deserialized, training started, approval created or state changed.
Until a deployment executor/probe exists, readiness deliberately fails closed.
"""
import hashlib
import math
import re
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.domain import ApprovalHistory, DatasetRegistry, ModelRegistry

CLASSIFICATION_METRICS = {
    "precision", "recall", "f1", "auroc", "false_positive_rate",
    "false_negative_rate", "latency",
}
RUNTIME_BLOCKER = {
    "code": "DEPLOYMENT_RUNTIME_NOT_CONFIGURED",
    "message": "실제 배포 실행기와 모델별 실행·상태 확인 근거가 연결되지 않았습니다.",
}


def metric_errors(metrics, task):
    if task not in {"CLASSIFICATION", "FORECASTING"}:
        return ["unsupported_target_task"]
    if not isinstance(metrics, dict):
        return ["metrics_missing"]
    normalized = {str(key).lower(): value for key, value in metrics.items()}
    required = {"mae", "rmse", "latency"} if task == "FORECASTING" else CLASSIFICATION_METRICS
    errors = [f"missing:{key}" for key in sorted(required - normalized.keys())]
    for key, value in normalized.items():
        try:
            number = float(value)
        except (TypeError, ValueError, OverflowError):
            errors.append(f"invalid:{key}")
            continue
        if isinstance(value, bool) or not math.isfinite(number):
            errors.append(f"nonfinite:{key}")
        elif task == "FORECASTING":
            if key != "bias" and number < 0:
                errors.append(f"negative:{key}")
        elif key == "latency":
            if number < 0:
                errors.append(f"negative:{key}")
        elif not 0 <= number <= 1:
            errors.append(f"out_of_range:{key}")
    return errors


def _latest_approval(db, kind, target):
    return db.query(ApprovalHistory).filter_by(
        approval_type=kind, target_id=target,
    ).order_by(ApprovalHistory.id.desc()).first()


def _snapshot_intact(dataset):
    """Read only hash-named files beneath the configured snapshot directory."""
    digest = dataset.data_hash or ""
    if not re.fullmatch(r"[0-9a-f]{64}", digest):
        return False
    try:
        root = Path(settings.DATASET_SNAPSHOT_DIR).resolve()
        path = (root / f"{digest}.json").resolve()
        if not path.is_relative_to(root):
            return False
        with path.open("rb") as stream:
            return hashlib.file_digest(stream, "sha256").hexdigest() == digest
    except (OSError, ValueError):
        return False


def model_readiness(db: Session, model: ModelRegistry, datasets=None):
    with db.no_autoflush:
        return _model_readiness(db, model, datasets)


def _model_readiness(db: Session, model: ModelRegistry, datasets=None):
    if isinstance((model.metrics_json or {}).get("provenance"), dict):
        return verified_model_readiness(db, model)
    datasets = datasets if datasets is not None else db.query(DatasetRegistry).all()
    blockers = []
    checks = {}

    def block(code, message):
        blockers.append({"code": code, "message": message})

    # Version is not globally unique across dataset families in this schema.
    matches = [d for d in datasets if d.dataset_version == model.dataset_version]
    checks["dataset"] = {"status": "BLOCKED", "matched_count": len(matches)}
    if len(matches) != 1:
        block("DATASET_REFERENCE_AMBIGUOUS" if matches else "DATASET_NOT_FOUND",
              "데이터셋 버전으로 승인 데이터셋을 하나로 식별할 수 없습니다.")
    else:
        dataset = matches[0]
        approval = _latest_approval(db, "DATASET", dataset.dataset_id)
        approved = bool(dataset.status == "APPROVED" and dataset.approved_by and approval
                        and approval.approval_status == "APPROVED" and approval.approved_by
                        and approval.approved_by == dataset.approved_by
                        and approval.comment == "snapshot_sha256=" + (dataset.data_hash or ""))
        intact = _snapshot_intact(dataset)
        lineage_matches = bool(
            all(getattr(model, field) and getattr(model, field) == getattr(dataset, field)
                for field in ("feature_version", "label_version", "preprocessing_version"))
            and model.target_variable in (dataset.variable_scope or [])
        )
        nonempty = bool(dataset.sample_count and dataset.sample_count > 0)
        checks["dataset"] = {
            "status": "SNAPSHOT_HASH_MATCH" if approved and intact and lineage_matches and nonempty else "BLOCKED",
            "dataset_id": dataset.dataset_id, "approved": approved,
            "snapshot_integrity_verified": intact, "version_scope_matches": lineage_matches,
            "evidence_lineage_verified": False,
            "sample_count": dataset.sample_count,
        }
        if not approved:
            block("DATASET_APPROVAL_MISSING", "스냅샷 해시에 연결된 데이터셋 승인 기록이 없습니다.")
        if not intact:
            block("DATASET_SNAPSHOT_INVALID", "데이터셋 스냅샷 파일 또는 해시 무결성이 확인되지 않았습니다.")
        if not lineage_matches:
            block("DATASET_LINEAGE_MISMATCH", "모델과 데이터셋의 Feature·라벨·전처리 버전 또는 대상 항목이 일치하지 않습니다.")
        if not nonempty:
            block("DATASET_EMPTY", "데이터셋에 학습 표본이 없습니다.")
        block("DATASET_EVIDENCE_LINEAGE_UNVERIFIED", "승인 라벨·실제 멤버십·사건 및 시간 분할의 재검증 기록이 모델에 연결되지 않았습니다.")

    # Never load untrusted pickle/joblib files; existence is not validity.
    artifact = str(model.artifact_path or "").strip()
    try:
        present = bool(artifact and Path(artifact).is_file() and Path(artifact).stat().st_size > 0)
    except (OSError, ValueError):
        present = False
    checks["artifact"] = {"status": "PRESENT_UNVERIFIED" if present else "MISSING", "file_present": present,
                          "integrity_verified": False, "runtime_load_verified": False}
    block("ARTIFACT_INTEGRITY_UNVERIFIED" if present else "ARTIFACT_MISSING",
          "모델 파일의 등록 해시 및 실행 검증 근거가 없습니다." if present else "실제 모델 파일이 없습니다.")

    errors = metric_errors(model.metrics_json, model.target_task)
    checks["evaluation"] = {"status": "DECLARED_UNVERIFIED" if not errors else "INVALID",
                            "metric_errors": errors, "held_out_evaluation_verified": False}
    if errors:
        block("EVALUATION_METRICS_INVALID", "필수 평가 지표가 없거나 유효하지 않습니다.")
    block("EVALUATION_PROVENANCE_UNVERIFIED", "독립 평가 데이터·모델 해시·평가 실행 기록을 연결하는 근거가 없습니다.")
    block("ACCEPTANCE_LIMITS_NOT_DEFINED", "업무별 품질·지연·비용 합격 기준의 승인 기록이 연결되지 않았습니다.")
    checks["acceptance_criteria"] = {"status": "NOT_DEFINED", "quality": None, "latency": None, "cost": None}

    approval = _latest_approval(db, "MODEL_DEPLOY", model.model_version)
    approved = bool(approval and approval.approval_status == "APPROVED" and approval.approved_by
                    and model.status in {"APPROVED", "PRODUCTION"})
    checks["approval"] = {"status": "RECORDED" if approved else "MISSING"}
    if not approved:
        block("MODEL_APPROVAL_MISSING", "현재 모델에 대한 유효한 배포 승인 기록이 없습니다.")
    blockers.append(dict(RUNTIME_BLOCKER))
    checks["runtime"] = {"status": "NOT_CONFIGURED", "deployment_verified": False}
    return {"model_version": model.model_version, "registry_status": model.status,
            "status": "BLOCKED", "ready_for_deployment": False, "operational_verified": False,
            "checks": checks, "blockers": blockers}


def get_mlops_readiness(db: Session):
    with db.no_autoflush:
        return _get_mlops_readiness(db)


def _get_mlops_readiness(db: Session):
    models = db.query(ModelRegistry).all()
    datasets = db.query(DatasetRegistry).all()
    blockers = [dict(RUNTIME_BLOCKER)]
    if not models:
        blockers.append({"code": "NO_REGISTERED_MODELS", "message": "등록된 모델이 없습니다."})
    approved_datasets = sum(d.status == "APPROVED" for d in datasets)
    if not approved_datasets:
        blockers.append({"code": "NO_APPROVED_DATASETS", "message": "승인 상태의 데이터셋이 없습니다."})
    execution = execution_status(db)
    model_states = [model_readiness(db, m, datasets) for m in models]
    operational_count = sum(m["operational_verified"] for m in model_states)
    ready_count = sum(m["ready_for_deployment"] for m in model_states)
    if execution["serving_configured"]:
        blockers = [b for b in blockers if b["code"] != "DEPLOYMENT_RUNTIME_NOT_CONFIGURED"]
    if not execution["approved_input_ready"]:
        blockers.append({"code": "NO_VERIFIED_APPROVED_TRAINING_INPUT", "message": "승인 원천·고정 분할·평가 기준을 모두 통과한 실제 입력이 없습니다."})
    return {
        "status": "OPERATING_LOCAL_PILOT" if operational_count else "APPROVED_CANDIDATE" if ready_count else "BLOCKED",
        "ready_for_deployment": bool(ready_count), "operational_model_count": operational_count,
        "training_worker_configured": execution["worker_configured"], "deployment_runtime_configured": execution["serving_configured"],
        "execution": execution,
        "acceptance_criteria_status": "VERIFIED_PER_CANDIDATE" if ready_count else "NOT_DEFINED",
        "counts": {"models": len(models), "datasets": len(datasets),
                   "approved_datasets": approved_datasets,
                   "registry_production_models": sum(m.status == "PRODUCTION" for m in models)},
        "blockers": blockers, "models": model_states,
        "verified_operational_model_count": operational_count,
    }


def execution_status(db):
    import os
    from datetime import datetime, timezone
    from app.ml.comparison_runner import clock, read_json, ComparisonBlocked
    from app.ml.job_queue import code_fingerprint
    from app.ml.serving import runtime_root, health
    from app.scripts.model_training_worker import process_creation_token
    result = {"code_implemented": True, "worker_configured": os.environ.get("OCEAN_TRAINING_WORKER_ENABLED", "0") == "1",
        "worker_running": False, "worker_status": "NOT_CONFIGURED", "serving_configured": os.environ.get("OCEAN_LOCAL_MODEL_SERVING_ENABLED", "0") == "1",
        "operational_verified": False, "live_local_model_count": 0, "approved_input_ready": False}
    try:
        root = runtime_root(); path = root / "worker" / "heartbeat.json"
        if path.exists():
            pulse, _ = read_json(path)
            age = (datetime.now(timezone.utc) - clock(pulse["checked_at"], True)).total_seconds()
            token = process_creation_token(pulse["pid"])
            valid = (pulse["status"] == "RUNNING" and 0 <= age <= 90 and token is not None
                and token == pulse["process_creation_token"] and pulse["code_sha256"] == code_fingerprint()
                and Path(pulse["queue_root"]).resolve() == root / "worker")
            result.update(worker_running=valid, worker_status="RUNNING" if valid else "STALE_OR_CHANGED", heartbeat_age_seconds=age,
                          worker_pid=pulse["pid"], worker_code_sha256=pulse["code_sha256"])
        pointers = list((root / "serving").glob("*.json")) if (root / "serving").exists() else []
        for pointer in pointers:
            try: health(db, pointer.stem); result["live_local_model_count"] += 1
            except (ComparisonBlocked, OSError, KeyError, TypeError, ValueError): pass
        result["operational_verified"] = result["live_local_model_count"] > 0
        from app.ml.comparison_runner import preflight, DatabaseAuthority
        for request in (root / "requests").glob("*.json") if (root / "requests").exists() else []:
            try:
                preflight(request, DatabaseAuthority(db, settings.DATASET_SNAPSHOT_DIR))
                result["approved_input_ready"] = True; break
            except (ComparisonBlocked, OSError, ValueError): pass
    except (ComparisonBlocked, OSError, KeyError, TypeError, ValueError):
        result["worker_status"] = "EVIDENCE_INVALID"
    return result


def verified_model_readiness(db, model):
    from app.ml.serving import load_candidate, deployment_identity, scope_key, health, _approved
    from app.ml.comparison_runner import ComparisonBlocked, digest
    checks, blockers, ready, operational = {}, [], False, False
    try:
        _, report, sha = load_candidate(db, model)
        identity = deployment_identity(model, sha, report["artifact_sha256"])
        checks["evaluation"] = {"held_out_evaluation_verified": True, "report_sha256": sha}
        checks["acceptance_criteria"] = report["acceptance"]
        _approved(db, "MODEL_DEPLOY", model.model_version, digest(identity))
        import os
        ready = os.environ.get("OCEAN_LOCAL_MODEL_SERVING_ENABLED", "0") == "1"
        if not ready: blockers.append({"code": "LOCAL_JSON_SERVING_DISABLED"})
        try:
            probe = health(db, scope_key(identity)); operational = probe["identity"] == identity
            checks["runtime"] = probe
        except ComparisonBlocked as exc: blockers.append({"code": exc.code})
    except (ComparisonBlocked, OSError, KeyError, TypeError, ValueError) as exc:
        blockers.append({"code": exc.code if isinstance(exc, ComparisonBlocked) else "MODEL_EVIDENCE_INVALID"})
    return {"model_version": model.model_version, "registry_status": model.status,
        "status": "OPERATING_LOCAL_PILOT" if operational else "APPROVED_CANDIDATE" if ready else "BLOCKED",
        "ready_for_deployment": ready, "operational_verified": operational, "checks": checks, "blockers": blockers}
