"""Local numeric-JSON serving with hash-bound real approval and rollback receipts."""
import hashlib
import os
import time
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
from app.ml.comparison_runner import ComparisonBlocked, _atomic_json, digest, preflight, read_json


def runtime_root():
    from app.ml.comparison_runner import reject_reparse
    path = Path(os.environ.get("OCEAN_MLOPS_ROOT", r"D:\AI_Observation\metadata\mlops"))
    reject_reparse(path)
    return path.resolve()


def predict_artifact(artifact, features, payload=None):
    try: return _predict_artifact(artifact, features, payload)
    except ComparisonBlocked: raise
    except (KeyError, TypeError, ValueError, IndexError, OverflowError) as exc:
        raise ComparisonBlocked("SERVING_NUMERIC_ARTIFACT_INVALID", type(exc).__name__) from exc


def _predict_artifact(artifact, features, payload=None):
    from app.ml.typed_adapters import validate_payload, signature
    values = np.asarray(features, dtype=float)
    if values.ndim != 1 or len(values) != len(artifact["features"]) or not np.isfinite(values).all():
        raise ComparisonBlocked("SERVING_FEATURE_CONTRACT_MISMATCH")
    schema = artifact.get("schema_version")
    if schema in {"typed-ridge-json-1", "robust-score-json-1"}:
        if not isinstance(payload, dict) or payload.get("representation") != artifact["representation"]:
            raise ComparisonBlocked("SERVING_TYPED_PAYLOAD_REQUIRED")
        if artifact.get("allowed_typed_signatures") and signature(payload) not in artifact["allowed_typed_signatures"]:
            raise ComparisonBlocked("SERVING_TYPED_SCOPE_NOT_APPROVED")
        values = np.concatenate([values, validate_payload(payload)])
    if schema == "robust-score-json-1":
        score = float(np.max(np.abs((values - artifact["median"]) / artifact["scale"])))
        return {"score": score, "bad_candidate": score > artifact["threshold"], "evidence_only": artifact["evidence_only"], "source_qc_mutation": False}
    if schema not in {"standard-scaled-ridge-json-1", "typed-ridge-json-1"}:
        raise ComparisonBlocked("UNSUPPORTED_NUMERIC_JSON_ARTIFACT")
    coef, mean, scale = np.asarray(artifact["coef"]), np.asarray(artifact["mean"]), np.asarray(artifact["scale"])
    if mean.shape != values.shape or scale.shape != values.shape or not np.isfinite([mean, scale]).all() or (scale <= 0).any():
        raise ComparisonBlocked("SERVING_NUMERIC_ARTIFACT_INVALID")
    result = ((values - mean) / scale) @ coef.T + np.asarray(artifact["intercept"])
    if not np.isfinite(result).all():
        raise ComparisonBlocked("SERVING_PREDICTION_NONFINITE")
    return {"prediction": np.asarray(result).tolist(), "representation": artifact.get("representation", "SCALAR"), "source_qc_mutation": False}


def _approved(db, kind, target, exact_hash):
    from app.models.domain import ApprovalHistory
    row = db.query(ApprovalHistory).filter_by(approval_type=kind, target_id=target).order_by(ApprovalHistory.id.desc()).first()
    if not row or row.approval_status != "APPROVED" or not row.approved_by or row.comment != "snapshot_sha256=" + exact_hash:
        raise ComparisonBlocked(kind + "_APPROVAL_MISSING")
    return row


def load_candidate(db, model, revalidate=True):
    from app.ml.comparison_runner import DatabaseAuthority
    from app.core.config import settings
    from app.ml.comparison_runner import reject_reparse
    reject_reparse(model.artifact_path or "")
    path = Path(model.artifact_path or "").resolve()
    allowed = runtime_root()
    if not path.is_relative_to(allowed):
        raise ComparisonBlocked("CANDIDATE_ARTIFACT_OUTSIDE_RUNTIME_ROOT")
    artifact, sha = read_json(path)
    provenance = (model.metrics_json or {}).get("provenance")
    if not isinstance(provenance, dict) or sha != provenance.get("artifact_sha256"):
        raise ComparisonBlocked("CANDIDATE_ARTIFACT_HASH_MISMATCH")
    reject_reparse(provenance["report_path"])
    report_path = Path(provenance["report_path"]).resolve()
    if not report_path.is_relative_to(allowed):
        raise ComparisonBlocked("CANDIDATE_REPORT_OUTSIDE_RUNTIME_ROOT")
    report, report_sha = read_json(report_path)
    if report_sha != provenance["report_sha256"] or report.get("artifact_sha256") != sha or report.get("artifact") != artifact or report.get("acceptance", {}).get("status") != "PASS":
        raise ComparisonBlocked("CANDIDATE_EVALUATION_OR_ACCEPTANCE_INVALID")
    from app.ml.job_queue import code_fingerprint
    if report.get("code_sha256") != code_fingerprint():
        raise ComparisonBlocked("CANDIDATE_EXECUTION_CODE_CHANGED_REVIEW_REQUIRED")
    _approved(db, "MODEL_INDEPENDENT_REVIEW", model.model_version, report_sha)
    if revalidate:
        prepared = preflight(report["manifest_path"], DatabaseAuthority(db, settings.DATASET_SNAPSHOT_DIR))
        if prepared["manifest_sha256"] != report["manifest_sha256"] or prepared["origin_membership_sha256"] != report["origin_membership_sha256"]:
            raise ComparisonBlocked("CANDIDATE_SOURCE_DATASET_CHANGED")
    return artifact, report, report_sha


def deployment_identity(model, report_sha, artifact_sha):
    provenance = (model.metrics_json or {}).get("provenance", {})
    return {"model_version": model.model_version, "artifact_sha256": artifact_sha, "report_sha256": report_sha,
            "target_task": model.target_task, "target_variable": model.target_variable,
            "domain": provenance.get("domain"), "item_id": provenance.get("item_id"), "task": provenance.get("task"),
            "runtime": "LOCAL_NUMERIC_JSON_IN_PROCESS", "scope": "LOOPBACK_PILOT", "schema_version": "local-serving-identity-1"}


def scope_key(identity):
    return digest({k: identity.get(k) for k in ("domain", "item_id", "task", "target_variable")})


def deploy(db, model, rollback=False):
    if os.environ.get("OCEAN_LOCAL_MODEL_SERVING_ENABLED", "0") != "1":
        raise ComparisonBlocked("LOCAL_JSON_SERVING_DISABLED")
    if model.status not in ({"ARCHIVED", "APPROVED"} if rollback else {"APPROVED"}):
        raise ComparisonBlocked("MODEL_REGISTRY_DEPLOYMENT_STATE_INVALID")
    artifact, report, report_sha = load_candidate(db, model)
    identity = deployment_identity(model, report_sha, report["artifact_sha256"])
    identity_sha = digest(identity)
    _approved(db, "MODEL_ROLLBACK" if rollback else "MODEL_DEPLOY", model.model_version, identity_sha)
    # Smoke the same exact numerical artifact before changing pointer/registry.
    sample = report["serving_smoke_sample"]
    smoke = predict_artifact(artifact, sample["features"], sample.get("typed_payload"))
    root = runtime_root() / "serving"
    root.mkdir(parents=True, exist_ok=True)
    scope = scope_key(identity)
    if db.bind.dialect.name == "postgresql":
        from sqlalchemy import text
        db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": int(scope[:15], 16)})
    pointer = root / (scope + ".json")
    previous = read_json(pointer)[0] if pointer.exists() else None
    receipt = {"identity": identity, "identity_sha256": identity_sha, "smoke_result": smoke,
               "checked_at": datetime.now(timezone.utc).isoformat(), "healthy": True,
               "previous_identity": previous["identity"] if previous else None,
               "process_id_at_deployment": os.getpid(), "scope_key": scope,
               "operation": "ROLLBACK" if rollback else "DEPLOY"}
    # Registry transaction failure restores previous real pointer bytes; no old
    # champion artifact is deleted, and rollback needs its own exact approval.
    old_bytes = pointer.read_bytes() if pointer.exists() else None
    from app.models.domain import ModelRegistry
    try:
        _atomic_json(pointer, receipt)
        for other in db.query(ModelRegistry).filter_by(target_variable=model.target_variable, target_task=model.target_task, is_champion=True):
            other_provenance = (other.metrics_json or {}).get("provenance", {})
            if other.model_version != model.model_version and all(other_provenance.get(k) == identity.get(k) for k in ("domain", "item_id", "task")):
                other.is_champion, other.status, other.deployment_status = False, "ARCHIVED", "ARCHIVED"
        model.is_champion, model.status, model.deployment_status = True, "PRODUCTION", "PRODUCTION"
        model.deployment_stage, model.deployment_target = "LOCAL_PILOT", "loopback"
        model.deployed_at = datetime.now(timezone.utc).replace(tzinfo=None)
        db.commit()
    except Exception:
        db.rollback()
        if old_bytes is not None:
            _atomic_json(pointer, previous)
        elif pointer.exists():
            pointer.unlink()
        raise
    return receipt


def health(db, scope=None):
    return validated_runtime(db, scope)[0]


def validated_runtime(db, scope=None):
    try: return _validated_runtime(db, scope)
    except ComparisonBlocked: raise
    except (OSError, KeyError, TypeError, ValueError, IndexError) as exc:
        raise ComparisonBlocked("SERVING_EVIDENCE_INVALID", type(exc).__name__) from exc


def _validated_runtime(db, scope=None):
    from app.models.domain import ModelRegistry
    if os.environ.get("OCEAN_LOCAL_MODEL_SERVING_ENABLED", "0") != "1":
        raise ComparisonBlocked("LOCAL_JSON_SERVING_DISABLED")
    root = runtime_root() / "serving"
    candidates = list(root.glob("*.json")) if root.exists() else []
    if scope is None:
        if len(candidates) != 1:
            raise ComparisonBlocked("SERVING_SCOPE_REQUIRED" if candidates else "NO_ACTIVE_LOCAL_MODEL")
        pointer = candidates[0]
    else:
        if not isinstance(scope, str) or len(scope) != 64 or any(c not in "0123456789abcdef" for c in scope):
            raise ComparisonBlocked("SERVING_SCOPE_INVALID")
        pointer = root / (scope + ".json")
    if not pointer.exists():
        raise ComparisonBlocked("NO_ACTIVE_LOCAL_MODEL")
    receipt, _ = read_json(pointer)
    identity = receipt["identity"]
    model = db.query(ModelRegistry).filter_by(model_version=identity["model_version"]).first()
    if not model or not model.is_champion or model.status != "PRODUCTION":
        raise ComparisonBlocked("SERVING_REGISTRY_IDENTITY_MISMATCH")
    artifact, report, report_sha = load_candidate(db, model)
    actual = deployment_identity(model, report_sha, report["artifact_sha256"])
    if actual != identity or digest(actual) != receipt["identity_sha256"]:
        raise ComparisonBlocked("SERVING_RUNTIME_IDENTITY_HASH_MISMATCH")
    _approved(db, "MODEL_ROLLBACK" if receipt["operation"] == "ROLLBACK" else "MODEL_DEPLOY", model.model_version, receipt["identity_sha256"])
    sample = report["serving_smoke_sample"]
    predict_artifact(artifact, sample["features"], sample.get("typed_payload"))
    return {"healthy": True, "identity": identity, "identity_sha256": receipt["identity_sha256"], "scope_key": scope_key(identity),
            "process_id": os.getpid(), "checked_at": datetime.now(timezone.utc).isoformat(), "numerical_probe_executed": True,
            "source_qc_mutation": False, "full_api_p95_status": "NOT_MEASURED", "throughput_status": "NOT_MEASURED"}, artifact


def rollback_previous(db, current):
    from app.models.domain import ModelRegistry
    provenance = (current.metrics_json or {}).get("provenance", {})
    path = runtime_root() / "serving" / (scope_key({**provenance, "target_variable": current.target_variable}) + ".json")
    receipt, _ = read_json(path)
    if receipt["identity"]["model_version"] != current.model_version or not receipt.get("previous_identity"):
        raise ComparisonBlocked("PREVIOUS_RUNTIME_IDENTITY_NOT_AVAILABLE")
    previous = db.query(ModelRegistry).filter_by(model_version=receipt["previous_identity"]["model_version"]).first()
    if previous is None:
        raise ComparisonBlocked("PREVIOUS_MODEL_NOT_FOUND")
    return deploy(db, previous, rollback=True)
