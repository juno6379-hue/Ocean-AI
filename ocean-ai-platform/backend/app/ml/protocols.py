"""Versioned model/split policy content and real reviewer-ledger authority."""
from pathlib import Path
import hashlib
import json
from app.ml.comparison_runner import ComparisonBlocked, clock, digest, read_json

ROLES = {"SPLIT_PROTOCOL", "EVALUATION_PROTOCOL", "ACCEPTANCE_POLICY"}
TASKS = {"FORECASTING", "ANOMALY_DETECTION", "QUALITY_REVIEW"}


def canonical_bytes(body):
    return json.dumps(body, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")


def validate_protocol(body, role, for_approval=False):
    try:
        return _validate_protocol(body, role, for_approval)
    except ComparisonBlocked:
        raise
    except (KeyError, TypeError, ValueError, AttributeError, OverflowError) as exc:
        raise ComparisonBlocked("MODEL_PROTOCOL_CONTRACT_INVALID", type(exc).__name__) from exc


def _validate_protocol(body, role, for_approval=False):
    if (role not in ROLES or body.get("schema_version") != "ocean-model-protocol-1" or body.get("role") != role
            or body.get("status") != "DRAFT" or not all(isinstance(body.get(k), str) and body[k] for k in
            ("protocol_id", "version", "domain", "item_id", "target_variable", "unit")) or body.get("task") not in TASKS
            or body.get("quantity_kind") not in {"SCALAR", "CIRCULAR_DEGREES", "SIGNED_RADIAL", "VECTOR_UV", "PROFILE_BINS", "TRAJECTORY"}):
        raise ComparisonBlocked("MODEL_PROTOCOL_SCHEMA_INVALID", role)
    if role == "SPLIT_PROTOCOL":
        strategy = body.get("split_strategy")
        if strategy not in {"station_holdout", "temporal_with_purge", "sensor_transition_holdout"}:
            raise ComparisonBlocked("EXPLICIT_SPLIT_STRATEGY_REQUIRED")
        if set(body.get("dataset_ids", {})) != {"TRAIN", "VALIDATION", "TEST"} or body.get("holdout_locked") is not True:
            raise ComparisonBlocked("FIXED_SPLIT_PROTOCOL_REQUIRED")
        prior = None
        for split in ("TRAIN", "VALIDATION", "TEST"):
            span = body["periods"][split]
            start, end = clock(span["start"], True), clock(span["end"], True)
            if start >= end or (prior and start < prior):
                raise ComparisonBlocked("PROTOCOL_TEMPORAL_OVERLAP")
            prior = end
            sha = body["member_ids_sha256"][split]
            if not isinstance(sha, str) or len(sha) != 64 or any(c not in "0123456789abcdef" for c in sha):
                raise ComparisonBlocked("FIXED_MEMBER_IDS_DIGEST_REQUIRED")
        groups = {"EVENT", "SOURCE_RECORD", "DOCUMENT_FAMILY"}
        if strategy != "temporal_with_purge":
            groups.add("SENSOR_EPISODE")
        if strategy == "station_holdout":
            groups.add("STATION")
        if set(body.get("disjoint_groups", [])) != groups:
            raise ComparisonBlocked("LEAKAGE_GROUP_POLICY_REQUIRED")
        if type(body.get("embargo_seconds")) is not int or body["embargo_seconds"] < 0:
            raise ComparisonBlocked("EXPLICIT_EMBARGO_REQUIRED")
    elif role == "EVALUATION_PROTOCOL":
        if not isinstance(body.get("feature_ids"), list) or not body["feature_ids"] or len(set(body["feature_ids"])) != len(body["feature_ids"]):
            raise ComparisonBlocked("FIXED_EVALUATION_FEATURES_REQUIRED")
        if body.get("test_pair_policy") != "ALL_APPROVED_COMMON_ORIGINS" or body.get("preprocessing_fit") not in {"TRAIN_ONLY", "TRAIN_VALIDATION_REFIT"}:
            raise ComparisonBlocked("EVALUATION_PROTOCOL_UNSUPPORTED")
        if type(body.get("lookback_seconds")) is not int or body["lookback_seconds"] < 0:
            raise ComparisonBlocked("EXPLICIT_FEATURE_LOOKBACK_REQUIRED")
        if type(body.get("horizon_seconds")) is not int or body["horizon_seconds"] < (1 if body["task"] == "FORECASTING" else 0):
            raise ComparisonBlocked("EXPLICIT_EVALUATION_HORIZON_REQUIRED")
        if body["task"] != "FORECASTING" and body["horizon_seconds"] != 0:
            raise ComparisonBlocked("POINTWISE_ADAPTER_HORIZON_MUST_BE_ZERO")
        if body["task"] == "FORECASTING" and not body.get("ridge_alphas"):
            raise ComparisonBlocked("FIXED_FORECAST_CANDIDATES_REQUIRED")
        if body["task"] == "FORECASTING":
            from app.ml.comparison_runner import finite
            values = body["ridge_alphas"]
            if not isinstance(values, list) or len(values) > 16 or len(set(values)) != len(values) or any(finite(v, "alpha") <= 0 for v in values):
                raise ComparisonBlocked("INVALID_RIDGE_ALPHA")
        else:
            if body.get("zero_mad_policy") != "UNIT_SCALE_ONE_EXPLICIT_ENGINEERING_BASELINE":
                raise ComparisonBlocked("EXPLICIT_ZERO_MAD_SCALE_POLICY_REQUIRED")
            values = body.get("normal_quantiles")
            if not isinstance(values, list) or not values or len(values) > 16 or len(set(values)) != len(values) or any(type(v) not in {int, float} or not 0 < v < 1 for v in values):
                raise ComparisonBlocked("FIXED_NORMAL_THRESHOLD_QUANTILES_REQUIRED")
        if body["task"] == "QUALITY_REVIEW" and body.get("human_label_policy") != "PRESERVE_ALL_QC_LABELS_BINARY_SCORE_ONLY_NORMAL_BAD":
            raise ComparisonBlocked("EXPLICIT_FULL_QC_LABEL_EVALUATION_POLICY_REQUIRED")
        if body["task"] != "FORECASTING" and body.get("positive_labels") != ["BAD"]:
            raise ComparisonBlocked("ONLY_EXPLICIT_BAD_BINARY_LABEL_ADAPTER_SUPPORTED")
        worker = body.get("worker_policy", {})
        if type(worker.get("max_attempts")) is not int or not 1 <= worker["max_attempts"] <= 3 or type(worker.get("lease_seconds")) is not int or not 30 <= worker["lease_seconds"] <= 3600:
            raise ComparisonBlocked("REVIEWED_BOUNDED_WORKER_POLICY_REQUIRED")
    else:
        limits = body.get("limits")
        required = {"min_test_samples", "max_local_p95_ms", "min_mae_improvement_fraction", "max_rmse_regression_fraction"} if body["task"] == "FORECASTING" else {"min_test_samples", "max_local_p95_ms", "min_f1", "max_false_positive_rate", "max_false_negative_rate"}
        if body["task"] == "QUALITY_REVIEW":
            required |= {"min_guide_rule_coverage", "min_human_qc_agreement", "max_false_good_rate"}
        if not isinstance(limits, dict) or set(limits) != required:
            raise ComparisonBlocked("ACCEPTANCE_LIMIT_KEYS_INVALID")
        for key, value in limits.items():
            if value is None and not for_approval:
                continue
            if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
                raise ComparisonBlocked("ACCEPTANCE_LIMIT_NOT_DEFINED", key)
            import math
            if not math.isfinite(value) or (key.endswith("fraction") or key in {"min_f1", "max_false_positive_rate", "max_false_negative_rate", "min_guide_rule_coverage", "min_human_qc_agreement", "max_false_good_rate"}) and value > 1:
                raise ComparisonBlocked("ACCEPTANCE_LIMIT_INVALID", key)
        if type(limits.get("min_test_samples")) is not int and (for_approval or limits.get("min_test_samples") is not None):
            raise ComparisonBlocked("MINIMUM_TEST_SAMPLE_COUNT_INVALID")
        if body.get("cost_policy") not in {"REQUIRES_MEASURED_COST", "LOCAL_PILOT_COST_NOT_REQUIRED"}:
            raise ComparisonBlocked("EXPLICIT_COST_POLICY_REQUIRED")
    return body


def validate_approved_protocol(db, body, expected_sha256, role):
    """A DRAFT content file is approved only by a latest real ledger decision."""
    from app.models.domain import ApprovalHistory
    validate_protocol(body, role, for_approval=True)
    if hashlib.sha256(canonical_bytes(body)).hexdigest() != expected_sha256:
        raise ComparisonBlocked("APPROVED_PROTOCOL_BODY_HASH_MISMATCH")
    decision = db.query(ApprovalHistory).filter_by(approval_type="MODEL_PROTOCOL", target_id=expected_sha256).order_by(ApprovalHistory.id.desc()).first()
    if not (decision and decision.approved_by and decision.approval_status == "APPROVED"
            and decision.comment == "snapshot_sha256=" + expected_sha256):
        raise ComparisonBlocked("MODEL_PROTOCOL_APPROVAL_MISSING", role)
    return {"approval_id": decision.id, "reviewer_id": decision.approved_by, "sha256": expected_sha256, "role": role}


def frozen_protocols(db, snapshot):
    root = Path(snapshot["source_contract_root"]).resolve()
    dependencies = snapshot.get("frozen_protocol_dependencies", [])
    result = {}
    for dep in dependencies:
        role = dep["role"]
        if role not in ROLES or role in result:
            raise ComparisonBlocked("PROTOCOL_DEPENDENCY_AMBIGUOUS", role)
        from app.ml.comparison_runner import reject_reparse
        reject_reparse(root / dep["path"])
        path = (root / dep["path"]).resolve()
        if not path.is_relative_to(root):
            raise ComparisonBlocked("PROTOCOL_DEPENDENCY_PATH_INVALID")
        body, sha = read_json(path)
        if sha != dep["sha256"]:
            raise ComparisonBlocked("PROTOCOL_DEPENDENCY_HASH_MISMATCH")
        validate_approved_protocol(db, body, sha, role)
        result[role] = {"body": body, "sha256": sha}
    if set(result) != ROLES:
        raise ComparisonBlocked("THREE_APPROVED_PROTOCOL_DEPENDENCIES_REQUIRED")
    return result


def evaluate_acceptance(report, policy):
    validate_protocol(policy, "ACCEPTANCE_POLICY", for_approval=True)
    limits, errors = policy["limits"], []
    metrics = report["test_metrics"]["ridge"] if report["task"] == "FORECASTING" else report["test_metrics"]["candidate"]
    if metrics["sample_count"] < limits["min_test_samples"]:
        errors.append("MINIMUM_TEST_SAMPLES_NOT_MET")
    if report.get("local_call_p95_ms") is None or report["local_call_p95_ms"] > limits["max_local_p95_ms"]:
        errors.append("LOCAL_CALL_LATENCY_BUDGET_NOT_MET")
    if report["task"] == "FORECASTING":
        baseline = report["test_metrics"]["persistence"]
        if baseline["mae"] <= 0 or metrics["mae"] > baseline["mae"] * (1 - limits["min_mae_improvement_fraction"]):
            errors.append("MINIMUM_MAE_IMPROVEMENT_NOT_MET_OR_ZERO_BASELINE")
        if metrics["rmse"] > baseline["rmse"] * (1 + limits["max_rmse_regression_fraction"]):
            errors.append("RMSE_REGRESSION_EXCEEDED")
    else:
        for metric, bound, comparator in (("f1", "min_f1", "min"), ("false_positive_rate", "max_false_positive_rate", "max"), ("false_negative_rate", "max_false_negative_rate", "max")):
            value = metrics.get(metric)
            if value is None or (value < limits[bound] if comparator == "min" else value > limits[bound]):
                errors.append("CLASSIFICATION_LIMIT_NOT_MET:" + metric)
    if policy["cost_policy"] == "REQUIRES_MEASURED_COST" and report.get("cost") == "NOT_MEASURED":
        errors.append("MEASURED_COST_REQUIRED")
    if report["task"] == "QUALITY_REVIEW":
        qc = report["test_metrics"]["full_qc_review"]
        for key, metric, minimum in (("min_guide_rule_coverage", "guide_rule_coverage", True), ("min_human_qc_agreement", "human_qc_agreement", True), ("max_false_good_rate", "false_good_rate", False)):
            value = qc[metric]
            if value is None or (value < limits[key] if minimum else value > limits[key]):
                errors.append("FULL_QC_LIMIT_NOT_MET:" + metric)
    return {"status": "PASS" if not errors else "FAIL", "policy_version": policy["version"], "blockers": errors,
            "automatic_deployment": False, "requires_independent_review_and_model_approval": True}
